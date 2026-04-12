import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from Engine.SocraticEngine import SocraticEngine
from Models.Content import Concept
from Models.Schemas import (
    ExamResultOut,
    SessionEndResponse,
    SessionHistoryItem,
    SessionStartRequest,
    SessionStartResponse,
    TurnOut,
)
from Models.Session import Turn, TutorSession, User
from Stats.MasteryTracker import MasteryTracker
from Stats.SessionAnalytics import load_session
from Stores.LLM.PromptRegistry import PromptRegistry
from Stats.Metrics import EXAM_SESSION_SCORE_PERCENT, QUESTIONS_PER_SESSION, SESSION_DURATION_SECONDS
from Utils.ContextManager import TurnLike
from Utils.StreamingHandler import collect_stream, sse_event
from config import get_settings

logger = logging.getLogger(__name__)


class SessionController:
    async def ensure_user(self, db: AsyncSession, user_id: uuid.UUID | None) -> uuid.UUID:
        if user_id is None:
            u = User(id=uuid.uuid4(), created_at=datetime.now(timezone.utc))
            db.add(u)
            await db.flush()
            return u.id
        existing = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if existing is None:
            db.add(User(id=user_id, created_at=datetime.now(timezone.utc)))
            await db.flush()
        return user_id

    async def start_session(self, db: AsyncSession, body: SessionStartRequest) -> SessionStartResponse:
        user_id = await self.ensure_user(db, body.user_id)
        concept = (
            await db.execute(select(Concept).where(Concept.id == body.concept_id))
        ).scalar_one_or_none()
        if concept is None:
            raise HTTPException(
                status_code=404,
                detail="Concept not found. Ingest a document on the Content page and select a concept.",
            )
        now = datetime.now(timezone.utc)
        mode = body.session_mode
        session = TutorSession(
            id=uuid.uuid4(),
            user_id=user_id,
            concept_id=concept.id,
            prompt_version="pending",
            total_turns=0,
            started_at=now,
            session_mode=mode,
        )
        db.add(session)
        try:
            await db.flush()
        except SQLAlchemyError as e:
            _orig = getattr(e, "orig", None)
            msg = (f"{_orig} {e}").lower()
            logger.exception("start_session flush failed")
            if "session_mode" in msg or "undefinedcolumn" in msg:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Database schema is missing session_mode (or migrations are behind). "
                        "From the SRC folder run: uv run alembic upgrade head"
                    ),
                ) from e
            raise HTTPException(
                status_code=503,
                detail="Could not save the session. Check Postgres is running and run: uv run alembic upgrade head",
            ) from e
        registry = PromptRegistry(db)
        resolved = await registry.get_prompt("socratic", session.id)
        prompt_version = resolved.version_id
        session.prompt_version = prompt_version

        engine = SocraticEngine(db, None)
        opening_stream = engine.opening_question_stream(session, concept)
        try:
            opening_text, _ = await collect_stream(opening_stream)
            session.opening_question = opening_text.strip()
        except Exception:
            logger.exception("Opening question generation failed session=%s", session.id)
            session.opening_question = (
                f"Let's explore {concept.name}. What do you already know about this topic?"
            )
        await db.flush()

        settings = get_settings()
        return SessionStartResponse(
            session_id=session.id,
            user_id=user_id,
            concept_id=concept.id,
            prompt_version=prompt_version,
            opening_question=session.opening_question or "",
            session_mode=mode,
            exam_target_turns=settings.exam_target_turns,
        )

    async def stream_turn(
        self,
        db: AsyncSession,
        redis,
        session_id: uuid.UUID,
        student_answer: str,
    ) -> AsyncIterator[str]:
        session = await load_session(db, session_id)
        if session is None or session.ended_at is not None:
            yield sse_event("error", "invalid or ended session")
            return
        concept = (
            await db.execute(select(Concept).where(Concept.id == session.concept_id))
        ).scalar_one()
        turns = (
            (
                await db.execute(
                    select(Turn)
                    .where(Turn.session_id == session_id)
                    .order_by(Turn.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        memory = [TurnLike(t.student_input, t.question_generated) for t in turns]

        engine = SocraticEngine(db, redis)
        registry = PromptRegistry(db)
        resolved = await registry.get_prompt("socratic", session_id)
        prompt_version = resolved.version_id

        question_parts: list[str] = []
        classifier_state = "partial"
        stuck_streak = 0
        done_meta: dict = {}

        try:
            async for item in engine.process_turn(
                session, concept, student_answer, memory, prompt_version
            ):
                ev = item.get("event", "")
                data = item.get("data", "")
                yield sse_event(ev, data)
                if ev == "token":
                    question_parts.append(data)
                if ev == "done":
                    try:
                        done_meta = json.loads(data)
                        classifier_state = done_meta.get("classifier_state", classifier_state)
                        stuck_streak = int(done_meta.get("stuck_streak", stuck_streak))
                    except json.JSONDecodeError:
                        done_meta = {}
        except Exception:
            logger.exception("Turn processing failed session=%s", session_id)
            yield sse_event("error", "The model encountered an error. Please try again.")
            return

        full_question = "".join(question_parts).strip()
        if full_question:
            turn = Turn(
                id=uuid.uuid4(),
                session_id=session_id,
                student_input=student_answer,
                classifier_state=classifier_state,
                stuck_streak=stuck_streak,
                question_generated=full_question,
                guardrail_triggered=bool(done_meta.get("guardrail_triggered", False)),
                latency_ms=float(done_meta.get("latency_ms", 0)),
                tokens_used=int(done_meta.get("tokens_used", 0)),
                prompt_version=done_meta.get("prompt_version", prompt_version),
                created_at=datetime.now(timezone.utc),
            )
            db.add(turn)
            session.total_turns = session.total_turns + 1
            if session.user_id:
                mt = MasteryTracker(db)
                await mt.apply_classifier_state(
                    session.user_id, concept.id, classifier_state, session_id
                )

    async def list_sessions(
        self, db: AsyncSession, user_id: uuid.UUID | None = None, concept_id: uuid.UUID | None = None
    ) -> list[SessionHistoryItem]:
        stmt = (
            select(TutorSession, Concept.name)
            .join(Concept, Concept.id == TutorSession.concept_id)
            .order_by(TutorSession.started_at.desc())
        )
        if user_id is not None:
            stmt = stmt.where(TutorSession.user_id == user_id)
        if concept_id is not None:
            stmt = stmt.where(TutorSession.concept_id == concept_id)
        rows = (await db.execute(stmt)).all()
        return [
            SessionHistoryItem(
                session_id=s.id,
                concept_id=s.concept_id,
                concept_name=cname,
                total_turns=s.total_turns,
                started_at=s.started_at,
                ended_at=s.ended_at,
                summary=s.summary_text,
            )
            for s, cname in rows
        ]

    async def list_turns(self, db: AsyncSession, session_id: uuid.UUID) -> list[TurnOut]:
        rows = (
            await db.execute(
                select(Turn).where(Turn.session_id == session_id).order_by(Turn.created_at.asc())
            )
        ).scalars().all()
        return [TurnOut.model_validate(t) for t in rows]

    async def end_session(self, db: AsyncSession, session_id: uuid.UUID) -> SessionEndResponse:
        session = await load_session(db, session_id)
        if session is None:
            return SessionEndResponse(session_id=session_id, summary=None)
        now = datetime.now(timezone.utc)
        session.ended_at = now
        turns = (
            (
                await db.execute(
                    select(Turn)
                    .where(Turn.session_id == session_id)
                    .order_by(Turn.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        lines = [f"Turns: {len(turns)}", f"Concept: {session.concept_id}"]
        for t in turns[-5:]:
            lines.append(f"- state={t.classifier_state} Q: {t.question_generated[:120]}...")
        session.summary_text = "\n".join(lines)

        duration_s = max(0.0, (now - session.started_at).total_seconds())
        SESSION_DURATION_SECONDS.observe(duration_s)
        QUESTIONS_PER_SESSION.observe(len(turns))

        exam_out: ExamResultOut | None = None
        if getattr(session, "session_mode", "socratic") == "exam_prep" and turns:
            weights = {"correct": 1.0, "partial": 0.65, "wrong": 0.0, "stuck": 0.25}
            earned = sum(weights.get(t.classifier_state, 0.0) for t in turns)
            possible = float(len(turns))
            pct = round(100.0 * earned / possible, 2) if possible else 0.0
            exam_out = ExamResultOut(
                turns_graded=len(turns),
                points_earned=round(earned, 3),
                points_possible=possible,
                score_percent=pct,
            )
            EXAM_SESSION_SCORE_PERCENT.observe(pct)

        return SessionEndResponse(session_id=session_id, summary=session.summary_text, exam=exam_out)
