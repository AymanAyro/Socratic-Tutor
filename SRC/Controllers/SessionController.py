import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from Engine.SocraticEngine import SocraticEngine
from Engine.nodes import max_probe_turns_for_difficulty, schedule_stage2_reveal_background
from Models.Content import Concept
from Models.Schemas import (
    ExamResultOut,
    ReflectRequest,
    SessionEndResponse,
    SessionHistoryItem,
    SessionPhaseOut,
    SessionStartRequest,
    SessionStartResponse,
    TurnClarificationOut,
    TurnOut,
)
from Models.Session import Turn, TutorSession, User
from Stats.MasteryTracker import MasteryTracker
from Stats.SessionAnalytics import load_session
from Stores.LLM.PromptRegistry import PromptRegistry
from Stores.LLM.factory import get_generation_client
from Stats.Metrics import EXAM_SESSION_SCORE_PERCENT, QUESTIONS_PER_SESSION, SESSION_DURATION_SECONDS
from Utils.ContextManager import TurnLike
from Utils.StreamingHandler import collect_stream, sse_event
from config import get_settings

logger = logging.getLogger(__name__)


class SessionController:
    async def _generate_session_name(self, topic: str, created_at: datetime) -> str:
        date_str = created_at.strftime("%b %d")
        fallback = f"{topic} · {date_str}"
        try:
            settings = get_settings()
            gen = get_generation_client()
            prompt = (
                f"Generate a 3-5 word session title for a tutoring session on: {topic}. "
                "Output only the title."
            )
            title, _ = await gen.generate(
                prompt=prompt,
                system="Return only a short title with no punctuation beyond spaces.",
                model=settings.generation_model_id,
            )
            cleaned = " ".join((title or "").split()).strip(" -:.")
            if not cleaned:
                return fallback
            return f"{cleaned} · {date_str}"
        except Exception:
            logger.exception("Session name generation failed topic=%s", topic)
            return fallback

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

    async def start_session(
        self,
        db: AsyncSession,
        body: SessionStartRequest,
        *,
        redis=None,
        teaching_graph=None,
        stage2_asset_store: dict[str, Any] | None = None,
    ) -> SessionStartResponse:
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
        settings = get_settings()
        use_stage2 = bool(body.use_stage2 or settings.enable_stage2_graph) and mode != "exam_prep"
        session = TutorSession(
            id=uuid.uuid4(),
            user_id=user_id,
            concept_id=concept.id,
            prompt_version="pending",
            total_turns=0,
            started_at=now,
            session_mode=mode,
            use_stage2=use_stage2,
            teaching_phase="PROBE" if use_stage2 else None,
            name=await self._generate_session_name(concept.name, now),
        )
        db.add(session)
        try:
            await db.flush()
        except SQLAlchemyError as e:
            _orig = getattr(e, "orig", None)
            msg = (f"{_orig} {e}").lower()
            logger.exception("start_session flush failed")
            if "session_mode" in msg or "undefinedcolumn" in msg or "use_stage2" in msg:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Database schema is behind (session_mode / Stage 2 columns). "
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

        engine = SocraticEngine(db, redis)
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

        if use_stage2:
            if teaching_graph is None or stage2_asset_store is None:
                raise HTTPException(
                    status_code=503,
                    detail="Stage 2 teaching graph is not initialized (check server startup / LANGGRAPH_CHECKPOINT_BACKEND).",
                )
            opening = session.opening_question or ""
            cfg = {
                "configurable": {
                    "thread_id": str(session.id),
                    "db": db,
                    "redis": redis,
                    "asset_store": stage2_asset_store,
                }
            }
            initial: dict[str, Any] = {
                "messages": [AIMessage(content=opening)],
                "phase": "PROBE",
                "session_id": str(session.id),
                "user_id": str(user_id),
                "concept_id": str(concept.id),
                "concept_name": concept.name,
                "document_id": str(concept.document_id),
                "difficulty_level": int(concept.difficulty_level),
                "max_probe_turns": max_probe_turns_for_difficulty(int(concept.difficulty_level)),
                "opening_question": opening,
                "prompt_version": prompt_version,
                "session_mode": mode,
                "probe_turns": 0,
                "background_dispatched": True,
                "session_stats": {"classifier_sequence": [], "escape_hatch_count": 0},
                "consolidate_attempts": 0,
                "needs_report": False,
            }
            schedule_stage2_reveal_background(
                str(session.id),
                concept.id,
                int(concept.difficulty_level),
                stage2_asset_store,
            )
            await teaching_graph.ainvoke(initial, cfg)

        return SessionStartResponse(
            session_id=session.id,
            user_id=user_id,
            concept_id=concept.id,
            prompt_version=prompt_version,
            opening_question=session.opening_question or "",
            session_mode=mode,
            exam_target_turns=settings.exam_target_turns,
            use_stage2=use_stage2,
            teaching_phase=session.teaching_phase,
            session_name=session.name,
        )

    async def stream_turn(
        self,
        db: AsyncSession,
        redis,
        session_id: uuid.UUID,
        student_answer: str,
        *,
        teaching_graph=None,
        stage2_asset_store: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        session = await load_session(db, session_id)
        if session is None or session.ended_at is not None:
            yield sse_event("error", "invalid or ended session")
            return
        if getattr(session, "use_stage2", False):
            async for line in self._stream_stage2_turn(
                db,
                redis,
                session_id,
                student_answer,
                teaching_graph=teaching_graph,
                stage2_asset_store=stage2_asset_store,
            ):
                yield line
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

    async def _stream_stage2_turn(
        self,
        db: AsyncSession,
        redis,
        session_id: uuid.UUID,
        student_answer: str,
        *,
        teaching_graph,
        stage2_asset_store: dict[str, Any] | None,
    ) -> AsyncIterator[str]:
        if teaching_graph is None or stage2_asset_store is None:
            yield sse_event("error", "Stage 2 graph unavailable.")
            return
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": redis,
                "asset_store": stage2_asset_store,
            }
        }
        snap = await teaching_graph.aget_state(cfg)
        phase = (snap.values or {}).get("phase", "PROBE")
        if phase not in ("PROBE", "CONSOLIDATE"):
            yield sse_event(
                "error",
                "This phase does not accept a free-text answer. Use reflect or wait for the next step.",
            )
            return
        try:
            out = await teaching_graph.ainvoke(
                {"messages": [HumanMessage(content=student_answer)]},
                cfg,
            )
        except Exception:
            logger.exception("Stage 2 graph invoke failed session=%s", session_id)
            yield sse_event("error", "The teaching graph encountered an error. Try again.")
            return

        msgs = out.get("messages") or []
        if not msgs:
            yield sse_event("done", json.dumps({"stage2": True, "phase": out.get("phase")}))
            return
        last = msgs[-1]
        if isinstance(last, AIMessage):
            content = last.content or ""
            if isinstance(content, str) and content.strip().startswith("{") and '"type": "reveal"' in content:
                yield sse_event("reveal_start", "")
                try:
                    payload = json.loads(content)
                    ideal = payload.get("ideal_answer") or ""
                    chunk_size = 48
                    for i in range(0, len(ideal), chunk_size):
                        yield sse_event("reveal_chunk", ideal[i : i + chunk_size])
                    done_payload = {
                        "stage2": True,
                        "phase": out.get("phase"),
                        "reveal": payload,
                    }
                    yield sse_event("reveal_done", json.dumps(done_payload))
                except json.JSONDecodeError:
                    yield sse_event("token", content)
                    yield sse_event(
                        "done",
                        json.dumps({"stage2": True, "phase": out.get("phase")}),
                    )
            else:
                text = content if isinstance(content, str) else str(content)
                chunk_size = 32
                for i in range(0, len(text), chunk_size):
                    yield sse_event("token", text[i : i + chunk_size])
                last_turn = (
                    await db.execute(
                        select(Turn)
                        .where(Turn.session_id == session_id)
                        .order_by(Turn.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                done_payload = {
                    "classifier_state": out.get("last_classifier_state", "partial"),
                    "stuck_streak": int(last_turn.stuck_streak) if last_turn else 0,
                    "guardrail_triggered": False,
                    "latency_ms": 0.0,
                    "tokens_used": 0,
                    "prompt_version": out.get("prompt_version", "v1.0.0"),
                    "session_mode": out.get("session_mode", "socratic"),
                    "stage2": True,
                    "phase": out.get("phase"),
                }
                yield sse_event("done", json.dumps(done_payload))
        else:
            yield sse_event("done", json.dumps({"stage2": True, "phase": out.get("phase")}))

    async def get_teaching_phase(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        teaching_graph,
        stage2_asset_store: dict[str, Any] | None,
    ) -> SessionPhaseOut:
        session = await load_session(db, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if not getattr(session, "use_stage2", False) or teaching_graph is None or stage2_asset_store is None:
            raise HTTPException(status_code=400, detail="Not a Stage 2 session")
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": None,
                "asset_store": stage2_asset_store,
            }
        }
        snap = await teaching_graph.aget_state(cfg)
        vals = snap.values
        last_reveal: dict | None = None
        last_plain: str | None = None
        for m in reversed(vals.get("messages") or []):
            if isinstance(m, AIMessage):
                c = m.content if isinstance(m.content, str) else ""
                cs = c.strip()
                if not cs:
                    continue
                is_reveal_json = cs.startswith("{") and '"type": "reveal"' in cs
                if is_reveal_json and last_reveal is None:
                    try:
                        last_reveal = json.loads(cs)
                    except json.JSONDecodeError:
                        last_reveal = None
                elif not is_reveal_json and last_plain is None:
                    last_plain = cs
        consolidation = vals.get("consolidation_question")
        last_tutor = consolidation if isinstance(consolidation, str) and consolidation.strip() else last_plain
        return SessionPhaseOut(
            session_id=session_id,
            phase=str(vals.get("phase") or session.teaching_phase or "PROBE"),
            probe_turns=int(vals.get("probe_turns") or 0),
            max_probe_turns=int(vals.get("max_probe_turns") or 0),
            self_rating=vals.get("self_rating"),
            report_status=session.report_status,
            last_reveal=last_reveal,
            last_tutor_plain=last_tutor,
        )

    async def submit_reflect(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        body: ReflectRequest,
        *,
        teaching_graph,
        stage2_asset_store: dict[str, Any] | None,
    ) -> SessionPhaseOut:
        session = await load_session(db, session_id)
        if session is None or session.ended_at is not None:
            raise HTTPException(status_code=400, detail="invalid or ended session")
        if not getattr(session, "use_stage2", False) or teaching_graph is None or stage2_asset_store is None:
            raise HTTPException(status_code=400, detail="Not a Stage 2 session")
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": None,
                "asset_store": stage2_asset_store,
            }
        }
        await teaching_graph.ainvoke(
            Command(update={"self_rating": body.rating}, goto="reflect_consolidate"),
            cfg,
        )
        return await self.get_teaching_phase(
            db, session_id, teaching_graph=teaching_graph, stage2_asset_store=stage2_asset_store
        )

    async def reveal_early(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        teaching_graph,
        stage2_asset_store: dict[str, Any] | None,
        redis,
    ) -> SessionPhaseOut:
        settings = get_settings()
        session = await load_session(db, session_id)
        if session is None or session.ended_at is not None:
            raise HTTPException(status_code=400, detail="invalid or ended session")
        if not getattr(session, "use_stage2", False) or teaching_graph is None or stage2_asset_store is None:
            raise HTTPException(status_code=400, detail="Not a Stage 2 session")
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": redis,
                "asset_store": stage2_asset_store,
            }
        }
        snap = await teaching_graph.aget_state(cfg)
        vals = snap.values
        probe_turns = int(vals.get("probe_turns") or 0)
        if probe_turns < settings.min_probe_turns:
            raise HTTPException(
                status_code=400,
                detail=f"Reveal is available after at least {settings.min_probe_turns} probe turn(s).",
            )
        await teaching_graph.ainvoke(
            Command(update={"phase": "REVEAL", "force_reveal": True}, goto="reveal_work"),
            cfg,
        )
        return await self.get_teaching_phase(
            db, session_id, teaching_graph=teaching_graph, stage2_asset_store=stage2_asset_store
        )

    async def _finalize_stage2_report(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        teaching_graph,
        stage2_asset_store: dict[str, Any] | None,
        redis,
    ) -> None:
        if teaching_graph is None or stage2_asset_store is None:
            return
        session = await load_session(db, session_id)
        if session is None or not getattr(session, "use_stage2", False):
            return
        if getattr(session, "report_status", None) == "ready":
            return
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": redis,
                "asset_store": stage2_asset_store,
            }
        }
        try:
            await teaching_graph.ainvoke(
                Command(update={"needs_report": True}, goto="report_work"),
                cfg,
            )
        except Exception:
            logger.exception("Stage 2 report finalization failed session=%s", session_id)

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
                name=s.name,
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

    async def get_turn_clarification(
        self, db: AsyncSession, turn_id: uuid.UUID
    ) -> TurnClarificationOut:
        turn = (await db.execute(select(Turn).where(Turn.id == turn_id))).scalar_one_or_none()
        if turn is None:
            raise HTTPException(status_code=404, detail="Turn not found")
        return TurnClarificationOut(
            turn_id=turn.id,
            clarification=turn.clarification,
            diagram_svg=turn.diagram_svg,
            status=turn.clarification_status,
        )

    async def end_session(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        *,
        teaching_graph=None,
        stage2_asset_store: dict[str, Any] | None = None,
        redis=None,
    ) -> SessionEndResponse:
        session = await load_session(db, session_id)
        if session is None:
            return SessionEndResponse(session_id=session_id, summary=None)
        if getattr(session, "use_stage2", False):
            await self._finalize_stage2_report(
                db,
                session_id,
                teaching_graph=teaching_graph,
                stage2_asset_store=stage2_asset_store,
                redis=redis,
            )
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
