"""LangGraph node implementations for Stage 2 teaching."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from Engine.agents.ConsolidationGen import generate_consolidation_question
from Engine.agents.DiagramAgent import generate_concept_diagram_mermaid
from Engine.agents.IdealAnswer import generate_ideal_answer
from Engine.agents.PerformanceAnalyst import analyse_session_performance
from Engine.state import TeachingState
from Models.Content import Concept
from Models.Session import Turn, TutorSession
from Pipelines.MermaidRenderer import render_mermaid_to_svg
from Stats.MasteryTracker import MasteryTracker
from Stats.Metrics import (
    CLASSIFIER_STATE,
    ESCAPE_HATCH_ACTIVATIONS,
    GUARDRAIL_TRIGGERS,
    PHASE_TRANSITIONS,
    REPETITION_RETRIES,
    REVEAL_WAIT_TIME,
    SELF_RATING_GAP,
    TOKENS_PER_TURN,
    TURN_LATENCY,
)
from Utils.ContextManager import TurnLike
from Utils.StreamingHandler import collect_stream
from config import get_settings
from database import AsyncSessionLocal
from Engine.AntiAnswerGuard import AntiAnswerGuard
from Engine.QuestionGenerator import QuestionGenerator
from Engine.UnderstandingClassifier import UnderstandingClassifier

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _exam_turn_points(state: str) -> float:
    return {"correct": 1.0, "partial": 0.65, "wrong": 0.0, "stuck": 0.25}.get(state, 0.0)


def _max_probe_turns(difficulty: int, settings) -> int:
    d = max(1, min(5, difficulty))
    base = settings.max_probe_turns_default
    return max(settings.min_probe_turns, min(10, base + max(0, d - 3)))


def max_probe_turns_for_difficulty(difficulty: int) -> int:
    return _max_probe_turns(difficulty, get_settings())


def probe_mastery_allows_reveal(
    probe_turns_before_answer: int,
    *,
    classifier_state: str,
    confidence: float,
    min_probe_turns: int,
    mastery_confidence_threshold: float,
) -> bool:
    """True if this probe answer may end PROBE due to mastery (honors min probe exchanges)."""
    turns_after_this = probe_turns_before_answer + 1
    return (
        classifier_state == "correct"
        and confidence >= mastery_confidence_threshold
        and turns_after_this >= min_probe_turns
    )


def _prior_question_strings(memory_turns: list[TurnLike], opening_question: str | None) -> list[str]:
    out: list[str] = []
    if opening_question and opening_question.strip():
        out.append(opening_question.strip())
    for t in memory_turns:
        out.append(t.question_generated.strip())
    return out


def _is_near_duplicate(new_q: str, prior: list[str], threshold: float) -> bool:
    n = new_q.lower().strip()
    if len(n) < 14:
        return False
    for p in prior:
        if not p:
            continue
        if SequenceMatcher(None, n, p.lower().strip()).ratio() >= threshold:
            return True
    return False


async def _compute_stuck_streak(db: AsyncSession, session_id: uuid.UUID, new_state: str) -> int:
    prev = (
        await db.execute(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(Turn.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if new_state != "stuck":
        return 0
    if prev and prev.classifier_state == "stuck":
        return prev.stuck_streak + 1
    return 1


async def _sync_teaching_row(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    phase: str | None = None,
    self_rating: int | None = None,
    report_pdf_path: str | None = None,
    report_status: str | None = None,
) -> None:
    vals: dict[str, Any] = {}
    if phase is not None:
        vals["teaching_phase"] = phase
    if self_rating is not None:
        vals["self_rating"] = self_rating
    if report_pdf_path is not None:
        vals["report_pdf_path"] = report_pdf_path
    if report_status is not None:
        vals["report_status"] = report_status
    if vals:
        await db.execute(update(TutorSession).where(TutorSession.id == session_id).values(**vals))


async def _background_assets_job(
    session_key: str,
    concept_id: uuid.UUID,
    difficulty: int,
    asset_store: dict[str, Any],
) -> None:
    settings = get_settings()
    slot = asset_store.setdefault(session_key, {})
    slot["status"] = "pending"
    t0 = time.perf_counter()
    try:
        async with AsyncSessionLocal() as db:
            ideal = await generate_ideal_answer(db, concept_id, difficulty=difficulty)
            mermaid = await generate_concept_diagram_mermaid(db, concept_id)
        svg = ""
        diagram_failed = False
        try:
            svg = await render_mermaid_to_svg(mermaid)
        except Exception:
            diagram_failed = True
            if not settings.mermaid_fallback_on_error:
                raise
        slot.update(
            {
                "status": "ready",
                "ideal_answer": ideal,
                "diagram_mermaid": mermaid,
                "diagram_svg": svg or "",
                "diagram_failed": diagram_failed,
            }
        )
    except Exception as e:
        logger.exception("Background reveal prep failed session=%s", session_key)
        slot.update({"status": "failed", "error": str(e), "ideal_answer": "", "diagram_svg": ""})
    finally:
        REVEAL_WAIT_TIME.observe(time.perf_counter() - t0)


def schedule_stage2_reveal_background(
    session_key: str,
    concept_id: uuid.UUID,
    difficulty: int,
    asset_store: dict[str, Any],
) -> None:
    """Start ideal-answer + diagram generation without blocking. Call once per session (session start), or from probe_turn if not yet dispatched."""
    asyncio.create_task(
        _background_assets_job(session_key, concept_id, difficulty, asset_store),
    )


async def _generate_reveal_assets_inline(
    concept_id: uuid.UUID,
    difficulty: int,
) -> tuple[str, str, bool]:
    """Synchronous path for reveal when background job has not finished."""
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        ideal = await generate_ideal_answer(db, concept_id, difficulty=difficulty)
        mermaid = await generate_concept_diagram_mermaid(db, concept_id)
    svg = ""
    diagram_failed = False
    try:
        svg = await render_mermaid_to_svg(mermaid)
    except Exception:
        diagram_failed = True
        if not settings.mermaid_fallback_on_error:
            raise
    return ideal, svg or "", diagram_failed


def _resolve_mode(state: str, stuck_streak: int, concept_id: uuid.UUID, settings) -> str:
    if state == "stuck" and stuck_streak >= settings.max_stuck_streak:
        ESCAPE_HATCH_ACTIVATIONS.labels(concept_id=str(concept_id)).inc()
        return "micro_explain_then_ask"
    if state == "correct":
        return "deepen"
    if state == "partial":
        return "probe_gap"
    if state == "wrong":
        return "reframe"
    return "scaffold"


async def probe_turn(state: TeachingState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    db: AsyncSession = cfg["db"]
    redis = cfg.get("redis")
    asset_store: dict[str, Any] = cfg.get("asset_store") or {}
    settings = get_settings()

    session_uuid = uuid.UUID(state["session_id"])
    concept_uuid = uuid.UUID(state["concept_id"])
    concept_row = (await db.execute(select(Concept).where(Concept.id == concept_uuid))).scalar_one()
    session_row = (await db.execute(select(TutorSession).where(TutorSession.id == session_uuid))).scalar_one()

    msgs = state.get("messages") or []
    last = msgs[-1]
    if not isinstance(last, HumanMessage):
        return {}
    student_answer = (last.content or "").strip()

    t0 = time.perf_counter()
    out: dict[str, Any] = {}
    if not state.get("background_dispatched"):
        schedule_stage2_reveal_background(
            state["session_id"],
            concept_uuid,
            int(state.get("difficulty_level") or concept_row.difficulty_level),
            asset_store,
        )
        out["background_dispatched"] = True

    max_turns = int(state.get("max_probe_turns") or _max_probe_turns(concept_row.difficulty_level, settings))
    probe_turns = int(state.get("probe_turns") or 0)
    opening = state.get("opening_question") or ""

    prior_db = list(
        (
            await db.execute(
                select(Turn).where(Turn.session_id == session_uuid).order_by(Turn.created_at.asc())
            )
        ).scalars().all()
    )
    memory = [TurnLike(t.student_input, t.question_generated) for t in prior_db]

    classifier = UnderstandingClassifier(db, redis)
    cr = await classifier.classify(concept_uuid, concept_row.name, student_answer, session_uuid)
    CLASSIFIER_STATE.labels(state=cr.state).inc()
    stuck = await _compute_stuck_streak(db, session_uuid, cr.state)
    mode = _resolve_mode(cr.state, stuck, concept_uuid, settings)

    force_reveal = bool(state.get("force_reveal"))
    wants_reveal = student_answer.strip() == "/reveal" or force_reveal
    can_early_reveal = probe_turns >= settings.min_probe_turns
    mastery_ok = probe_mastery_allows_reveal(
        probe_turns,
        classifier_state=cr.state,
        confidence=cr.confidence,
        min_probe_turns=settings.min_probe_turns,
        mastery_confidence_threshold=settings.mastery_confidence_threshold,
    )
    over_cap = probe_turns >= max_turns

    should_reveal = mastery_ok or over_cap or (wants_reveal and can_early_reveal) or (
        wants_reveal and over_cap
    )

    stats = dict(state.get("session_stats") or {})
    seq = list(stats.get("classifier_sequence") or [])
    seq.append(cr.state)
    stats["classifier_sequence"] = seq
    stats["escape_hatch_count"] = int(stats.get("escape_hatch_count") or 0)
    if mode == "micro_explain_then_ask":
        stats["escape_hatch_count"] = stats["escape_hatch_count"] + 1

    prompt_version = state.get("prompt_version") or session_row.prompt_version

    if should_reveal:
        PHASE_TRANSITIONS.labels(from_phase="PROBE", to_phase="REVEAL").inc()
        turn = Turn(
            id=uuid.uuid4(),
            session_id=session_uuid,
            student_input=student_answer,
            classifier_state=cr.state,
            stuck_streak=stuck,
            question_generated="[Reveal — Socratic phase complete.]",
            guardrail_triggered=False,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            tokens_used=cr.tokens_used,
            prompt_version=prompt_version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(turn)
        session_row.total_turns = session_row.total_turns + 1
        if session_row.user_id:
            mt = MasteryTracker(db)
            await mt.apply_classifier_state(session_row.user_id, concept_uuid, cr.state, session_uuid)
        await _sync_teaching_row(db, session_uuid, phase="REVEAL")
        await db.flush()
        return {
            **out,
            "probe_turns": probe_turns + 1,
            "phase": "REVEAL",
            "mastery_signal": mastery_ok,
            "last_classifier_state": cr.state,
            "last_classifier_confidence": cr.confidence,
            "session_stats": stats,
            "force_reveal": False,
        }

    generator = QuestionGenerator(db)
    guard = AntiAnswerGuard(db)
    tokens = cr.tokens_used
    guard_triggered = False
    repetition_triggered = False
    question_text = ""
    max_retries = settings.max_guardrail_retries
    prior_q_texts = _prior_question_strings(memory, opening)
    session_mode = state.get("session_mode") or "socratic"

    prior_turns_db = prior_db
    points_prior = sum(_exam_turn_points(t.classifier_state) for t in prior_turns_db)
    n_prior = len(prior_turns_db)
    turn_score = _exam_turn_points(cr.state)
    exam_denom = n_prior + 1
    exam_avg = (points_prior + turn_score) / exam_denom if exam_denom else 0.0

    for attempt in range(max_retries + 1):
        stream = generator.generate_stream(
            session_uuid,
            concept_uuid,
            cr.state,
            cr.gap,
            mode,
            memory,
            opening,
            student_answer,
            session_mode=session_mode,
        )
        question_text, _ = await collect_stream(stream)
        passes, gtokens = await guard.check_passes(question_text, concept_row.name, session_uuid)
        tokens += gtokens
        repetitive = _is_near_duplicate(question_text, prior_q_texts, settings.repetition_similarity_threshold)
        if repetitive:
            repetition_triggered = True
            REPETITION_RETRIES.inc()
        if passes and not repetitive:
            break
        if not passes:
            guard_triggered = True
            GUARDRAIL_TRIGGERS.inc()
        if attempt < max_retries and (not passes or repetitive):
            continue
        question_text = (
            "What is one concrete example from the material that relates to this concept?"
        )
        break

    elapsed = time.perf_counter() - t0
    TURN_LATENCY.observe(elapsed)
    TOKENS_PER_TURN.observe(max(tokens, 0))

    turn = Turn(
        id=uuid.uuid4(),
        session_id=session_uuid,
        student_input=student_answer,
        classifier_state=cr.state,
        stuck_streak=stuck,
        question_generated=question_text.strip(),
        guardrail_triggered=guard_triggered,
        latency_ms=round(elapsed * 1000, 2),
        tokens_used=tokens,
        prompt_version=prompt_version,
        created_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    session_row.total_turns = session_row.total_turns + 1
    if session_row.user_id:
        mt = MasteryTracker(db)
        await mt.apply_classifier_state(session_row.user_id, concept_uuid, cr.state, session_uuid)
    await _sync_teaching_row(db, session_uuid, phase="PROBE")
    await db.flush()

    ai_msg = AIMessage(content=question_text.strip())
    return {
        **out,
        "messages": [ai_msg],
        "probe_turns": probe_turns + 1,
        "last_classifier_state": cr.state,
        "last_classifier_confidence": cr.confidence,
        "session_stats": stats,
        "phase": "PROBE",
        "force_reveal": False,
    }


async def reveal_work(state: TeachingState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    db: AsyncSession = cfg["db"]
    asset_store: dict[str, Any] = cfg.get("asset_store") or {}
    settings = get_settings()
    sid = state["session_id"]

    deadline = time.perf_counter() + settings.reveal_poll_timeout_seconds
    slot: dict[str, Any] = {}
    while time.perf_counter() < deadline:
        slot = asset_store.get(sid) or {}
        if slot.get("status") in ("ready", "failed"):
            break
        await asyncio.sleep(settings.reveal_poll_interval_seconds)

    slot = asset_store.get(sid) or {}
    ideal = (slot.get("ideal_answer") or "").strip()
    svg = (slot.get("diagram_svg") or "").strip()
    diagram_failed = bool(slot.get("diagram_failed"))

    if not ideal:
        try:
            concept_uuid = uuid.UUID(state["concept_id"])
            diff = int(state.get("difficulty_level") or 3)
            ideal, svg, diagram_failed = await _generate_reveal_assets_inline(concept_uuid, diff)
            merge = asset_store.setdefault(sid, {})
            merge.update(
                {
                    "status": "ready",
                    "ideal_answer": ideal,
                    "diagram_svg": svg,
                    "diagram_failed": diagram_failed,
                }
            )
        except Exception:
            logger.exception("Inline reveal generation failed session=%s", sid)
            ideal = (
                "We could not generate the full model answer right now. "
                "Please review your course materials for this concept."
            )
            diagram_failed = True

    probe_turns = int(state.get("probe_turns") or 0)
    summary = {
        "probe_turns": probe_turns,
        "last_classifier": state.get("last_classifier_state"),
        "mastery_signal": bool(state.get("mastery_signal")),
    }
    payload = {
        "type": "reveal",
        "ideal_answer": ideal,
        "concept_diagram_svg": svg,
        "diagram_failed": diagram_failed,
        "probe_summary": summary,
    }
    await _sync_teaching_row(db, uuid.UUID(sid), phase="REFLECT")
    await db.flush()
    PHASE_TRANSITIONS.labels(from_phase="REVEAL", to_phase="REFLECT").inc()
    return {
        "messages": [AIMessage(content=json.dumps(payload))],
        "phase": "REFLECT",
        "reveal_assets": {
            "ideal_answer": ideal,
            "diagram_svg": svg,
            "diagram_failed": diagram_failed,
        },
    }


async def reflect_consolidate(state: TeachingState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    db: AsyncSession = cfg["db"]
    rating = state.get("self_rating")
    if rating is None or int(rating) < 1:
        return {}
    rating = int(rating)
    session_uuid = uuid.UUID(state["session_id"])
    concept_uuid = uuid.UUID(state["concept_id"])
    concept_row = (await db.execute(select(Concept).where(Concept.id == concept_uuid))).scalar_one()
    assets = state.get("reveal_assets") or {}
    ideal = str(assets.get("ideal_answer") or "")
    conf = float(state.get("last_classifier_confidence") or 0.0)
    gap = float(rating) - conf * 5.0
    SELF_RATING_GAP.observe(gap)

    q = await generate_consolidation_question(
        db,
        session_uuid,
        concept_name=concept_row.name,
        ideal_answer=ideal,
        self_rating=rating,
    )
    await _sync_teaching_row(db, session_uuid, phase="CONSOLIDATE", self_rating=rating)
    await db.flush()
    PHASE_TRANSITIONS.labels(from_phase="REFLECT", to_phase="CONSOLIDATE").inc()
    return {
        "messages": [AIMessage(content=q)],
        "phase": "CONSOLIDATE",
        "consolidation_question": q,
        "consolidate_attempts": 0,
        "needs_report": False,
    }


async def consolidate_turn(state: TeachingState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    db: AsyncSession = cfg["db"]
    redis = cfg.get("redis")
    session_uuid = uuid.UUID(state["session_id"])
    concept_uuid = uuid.UUID(state["concept_id"])
    concept_row = (await db.execute(select(Concept).where(Concept.id == concept_uuid))).scalar_one()

    msgs = state.get("messages") or []
    last = msgs[-1]
    if not isinstance(last, HumanMessage):
        return {}

    student_answer = (last.content or "").strip()
    classifier = UnderstandingClassifier(db, redis)
    cr = await classifier.classify(concept_uuid, concept_row.name, student_answer, session_uuid)
    CLASSIFIER_STATE.labels(state=cr.state).inc()
    attempts = int(state.get("consolidate_attempts") or 0)
    ok = cr.state in ("correct", "partial")

    prompt_version = state.get("prompt_version") or "v1.0.0"
    turn = Turn(
        id=uuid.uuid4(),
        session_id=session_uuid,
        student_input=student_answer,
        classifier_state=cr.state,
        stuck_streak=0,
        question_generated="[Consolidation check.]",
        guardrail_triggered=False,
        latency_ms=0.0,
        tokens_used=cr.tokens_used,
        prompt_version=prompt_version,
        created_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    sess = (await db.execute(select(TutorSession).where(TutorSession.id == session_uuid))).scalar_one()
    sess.total_turns = sess.total_turns + 1
    if sess.user_id:
        mt = MasteryTracker(db)
        await mt.apply_classifier_state(sess.user_id, concept_uuid, cr.state, session_uuid)

    if ok:
        PHASE_TRANSITIONS.labels(from_phase="CONSOLIDATE", to_phase="END").inc()
        await _sync_teaching_row(db, session_uuid, phase="END")
        await db.flush()
        return {
            "last_consolidate_state": cr.state,
            "needs_report": True,
            "phase": "END",
            "consolidate_attempts": attempts,
        }

    if attempts >= 1:
        PHASE_TRANSITIONS.labels(from_phase="CONSOLIDATE", to_phase="END").inc()
        await _sync_teaching_row(db, session_uuid, phase="END")
        await db.flush()
        return {
            "last_consolidate_state": cr.state,
            "needs_report": True,
            "phase": "END",
            "consolidate_attempts": attempts + 1,
        }

    rating = int(state.get("self_rating") or 3)
    assets = state.get("reveal_assets") or {}
    ideal = str(assets.get("ideal_answer") or "")
    q = await generate_consolidation_question(
        db,
        session_uuid,
        concept_name=concept_row.name,
        ideal_answer=ideal,
        self_rating=rating,
    )
    await db.flush()
    return {
        "messages": [AIMessage(content=q)],
        "consolidate_attempts": attempts + 1,
        "last_consolidate_state": cr.state,
        "consolidation_question": q,
        "phase": "CONSOLIDATE",
        "needs_report": False,
    }


async def report_work(state: TeachingState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    db: AsyncSession = cfg["db"]
    session_uuid = uuid.UUID(state["session_id"])
    if (state.get("report_status") or "").lower() == "ready" and state.get("report_pdf_path"):
        return {}
    await _sync_teaching_row(db, session_uuid, report_status="pending")
    await db.flush()

    turns = list(
        (
            await db.execute(
                select(Turn).where(Turn.session_id == session_uuid).order_by(Turn.created_at.asc())
            )
        ).scalars().all()
    )
    concept_row = (await db.execute(select(Concept).where(Concept.id == uuid.UUID(state["concept_id"])))).scalar_one()
    assets = state.get("reveal_assets") or {}
    rating = state.get("self_rating")
    conf = float(state.get("last_classifier_confidence") or 0.0)

    payload = {
        "concepts": [{"id": state["concept_id"], "name": concept_row.name}],
        "probe_turns_per_concept": {state["concept_id"]: int(state.get("probe_turns") or 0)},
        "classifier_sequences": {state["concept_id"]: list((state.get("session_stats") or {}).get("classifier_sequence") or [])},
        "rating_gap": {state["concept_id"]: {"self_rating": rating, "classifier_confidence": conf}},
        "escape_hatch_count": int((state.get("session_stats") or {}).get("escape_hatch_count") or 0),
        "mastery_delta": {},
    }
    analyst = await analyse_session_performance(db, session_id=session_uuid, payload=payload)
    from Pipelines.ReportComposer import ReportComposer

    composer = ReportComposer()
    pdf_path = await composer.compose(
        session_id=session_uuid,
        concept_name=concept_row.name,
        state_snapshot=dict(state),
        analyst=analyst,
        turns=turns,
        diagram_svg=str(assets.get("diagram_svg") or ""),
        ideal_answer=str(assets.get("ideal_answer") or ""),
    )
    await _sync_teaching_row(
        db,
        session_uuid,
        report_status="ready",
        report_pdf_path=pdf_path,
        phase="END",
    )
    await db.flush()
    PHASE_TRANSITIONS.labels(from_phase="CONSOLIDATE", to_phase="REPORT").inc()
    return {
        "report_pdf_path": pdf_path,
        "report_status": "ready",
        "analyst_json": analyst,
        "phase": "END",
        "needs_report": False,
    }
