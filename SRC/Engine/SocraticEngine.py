import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from difflib import SequenceMatcher

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Engine.AntiAnswerGuard import AntiAnswerGuard
from Engine.QuestionGenerator import QuestionGenerator
from Engine.UnderstandingClassifier import UnderstandingClassifier
from Models.Content import Concept
from Models.Session import Turn, TutorSession
from Stats.Metrics import (
    CLASSIFIER_STATE,
    ESCAPE_HATCH_ACTIVATIONS,
    GUARDRAIL_TRIGGERS,
    REPETITION_RETRIES,
    TOKENS_PER_TURN,
    TURN_LATENCY,
)
from Utils.ContextManager import TurnLike
from Utils.StreamingHandler import collect_stream
from config import get_settings


def _exam_turn_points(state: str) -> float:
    return {"correct": 1.0, "partial": 0.65, "wrong": 0.0, "stuck": 0.25}.get(state, 0.0)


@dataclass
class TurnOutcome:
    question_text: str
    classifier_state: str
    stuck_streak: int
    guardrail_triggered: bool
    tokens_used: int
    latency_ms: float
    prompt_version: str


class SocraticEngine:
    def __init__(self, db: AsyncSession, redis: Redis | None = None) -> None:
        self._db = db
        self._redis = redis
        self._settings = get_settings()
        self._classifier = UnderstandingClassifier(db, redis)
        self._generator = QuestionGenerator(db)
        self._guard = AntiAnswerGuard(db)

    def resolve_mode(self, state: str, stuck_streak: int, concept_id: uuid.UUID) -> str:
        if state == "stuck" and stuck_streak >= self._settings.max_stuck_streak:
            ESCAPE_HATCH_ACTIVATIONS.labels(concept_id=str(concept_id)).inc()
            return "micro_explain_then_ask"
        if state == "correct":
            return "deepen"
        if state == "partial":
            return "probe_gap"
        if state == "wrong":
            return "reframe"
        return "scaffold"

    async def _compute_stuck_streak(self, session: TutorSession, new_state: str) -> int:
        prev = (
            await self._db.execute(
                select(Turn)
                .where(Turn.session_id == session.id)
                .order_by(Turn.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if new_state != "stuck":
            return 0
        if prev and prev.classifier_state == "stuck":
            return prev.stuck_streak + 1
        return 1

    def _prior_question_strings(
        self, memory_turns: list[TurnLike], opening_question: str | None
    ) -> list[str]:
        out: list[str] = []
        if opening_question and opening_question.strip():
            out.append(opening_question.strip())
        for t in memory_turns:
            out.append(t.question_generated.strip())
        return out

    def _is_near_duplicate(self, new_q: str, prior: list[str]) -> bool:
        n = new_q.lower().strip()
        if len(n) < 14:
            return False
        thr = self._settings.repetition_similarity_threshold
        for p in prior:
            if not p:
                continue
            if SequenceMatcher(None, n, p.lower().strip()).ratio() >= thr:
                return True
        return False

    async def _prior_turns(self, session_id: uuid.UUID) -> list[Turn]:
        return list(
            (
                await self._db.execute(
                    select(Turn).where(Turn.session_id == session_id).order_by(Turn.created_at.asc())
                )
            ).scalars().all()
        )

    async def opening_question_stream(
        self, session: TutorSession, concept: Concept
    ) -> AsyncIterator[str]:
        mode = getattr(session, "session_mode", None) or "socratic"
        async for chunk in self._generator.generate_opening_stream(
            session.id, concept, session_mode=mode
        ):
            yield chunk

    async def process_turn(
        self,
        session: TutorSession,
        concept: Concept,
        student_answer: str,
        memory_turns: list[TurnLike],
        prompt_version: str,
    ) -> AsyncIterator[dict]:
        t0 = time.perf_counter()
        cr = await self._classifier.classify(
            concept.id, concept.name, student_answer, session.id
        )
        CLASSIFIER_STATE.labels(state=cr.state).inc()
        stuck_streak = await self._compute_stuck_streak(session, cr.state)
        mode = self.resolve_mode(cr.state, stuck_streak, concept.id)

        tokens = cr.tokens_used
        guard_triggered = False
        repetition_triggered = False
        question_text = ""
        max_retries = self._settings.max_guardrail_retries
        prior_q_texts = self._prior_question_strings(memory_turns, session.opening_question)
        session_mode = getattr(session, "session_mode", None) or "socratic"

        prior_turns_db = await self._prior_turns(session.id)
        points_prior = sum(_exam_turn_points(t.classifier_state) for t in prior_turns_db)
        n_prior = len(prior_turns_db)
        turn_score = _exam_turn_points(cr.state)
        exam_denom = n_prior + 1
        exam_avg = (points_prior + turn_score) / exam_denom if exam_denom else 0.0

        for attempt in range(max_retries + 1):
            stream = self._generator.generate_stream(
                session.id,
                concept.id,
                cr.state,
                cr.gap,
                mode,
                memory_turns,
                session.opening_question,
                student_answer,
                session_mode=session_mode,
            )
            question_text, _ = await collect_stream(stream)
            passes, gtokens = await self._guard.check_passes(
                question_text, concept.name, session.id
            )
            tokens += gtokens
            repetitive = self._is_near_duplicate(question_text, prior_q_texts)
            if repetitive:
                repetition_triggered = True
                REPETITION_RETRIES.inc()

            if passes and not repetitive:
                break

            if not passes:
                guard_triggered = True
                GUARDRAIL_TRIGGERS.inc()

            if attempt < max_retries and (not passes or repetitive):
                yield {"event": "regenerating", "data": "retry"}
                continue

            question_text = (
                "What is one concrete example from the material that relates to this concept?"
            )
            break

        elapsed = time.perf_counter() - t0
        TURN_LATENCY.observe(elapsed)
        TOKENS_PER_TURN.observe(max(tokens, 0))

        chunk_size = 32
        for i in range(0, len(question_text), chunk_size):
            yield {"event": "token", "data": question_text[i : i + chunk_size]}

        done_payload: dict = {
            "classifier_state": cr.state,
            "stuck_streak": stuck_streak,
            "guardrail_triggered": guard_triggered,
            "repetition_triggered": repetition_triggered,
            "latency_ms": round(elapsed * 1000, 2),
            "tokens_used": tokens,
            "prompt_version": prompt_version,
            "session_mode": session_mode,
        }
        if session_mode == "exam_prep":
            done_payload["exam_turn_score"] = round(turn_score, 3)
            done_payload["exam_turn_index"] = exam_denom
            done_payload["exam_average_score"] = round(exam_avg, 4)
            done_payload["exam_target_turns"] = self._settings.exam_target_turns
            done_payload["exam_points_earned_total"] = round(points_prior + turn_score, 3)
            done_payload["exam_points_possible_total"] = float(exam_denom)

        yield {"event": "done", "data": json.dumps(done_payload)}

    def build_outcome_from_done(
        self, question_text: str, done: dict, classifier_state: str, stuck_streak: int
    ) -> TurnOutcome:
        return TurnOutcome(
            question_text=question_text,
            classifier_state=classifier_state,
            stuck_streak=stuck_streak,
            guardrail_triggered=done.get("guardrail_triggered", False),
            tokens_used=int(done.get("tokens_used", 0)),
            latency_ms=float(done.get("latency_ms", 0)),
            prompt_version=str(done.get("prompt_version", "v1.0.0")),
        )
