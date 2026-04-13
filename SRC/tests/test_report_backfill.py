import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from Engine.nodes import report_work


class _Turn:
    def __init__(
        self,
        *,
        turn_id: uuid.UUID,
        student_input: str = "answer",
        question_generated: str = "question?",
        clarification: str | None = None,
        diagram_svg: str | None = None,
        clarification_status: str = "pending",
    ) -> None:
        self.id = turn_id
        self.student_input = student_input
        self.question_generated = question_generated
        self.classifier_state = "partial"
        self.correct_answer = None
        self.clarification = clarification
        self.diagram_svg = diagram_svg
        self.clarification_status = clarification_status
        self.stuck_streak = 0
        self.guardrail_triggered = False
        self.latency_ms = 0.0
        self.tokens_used = 0
        self.prompt_version = "v1.0.0"


@pytest.mark.asyncio
async def test_report_work_backfills_missing_turn_assets():
    sid = uuid.uuid4()
    cid = uuid.uuid4()

    concept = MagicMock()
    concept.name = "Artificial Intelligence"
    session = MagicMock()
    session.name = "AI Tutoring"
    session.user_id = None
    session.report_status = None
    session.total_turns = 1

    pending_turn = _Turn(turn_id=uuid.uuid4())
    ready_turn = _Turn(
        turn_id=uuid.uuid4(),
        clarification="Already ready",
        diagram_svg="<svg><g></g></svg>",
        clarification_status="ready",
    )
    updated_pending_turn = _Turn(
        turn_id=pending_turn.id,
        clarification="Backfilled explanation",
        diagram_svg="<svg><g>Turn diagram</g></svg>",
        clarification_status="ready",
    )
    updated_pending_turn.correct_answer = "Expected model answer"

    fetch_turn_batches = [[pending_turn, ready_turn], [updated_pending_turn, ready_turn]]
    execute_calls = 0
    db = AsyncMock()

    async def _exec(*_a, **_k):
        nonlocal execute_calls
        execute_calls += 1
        r = MagicMock()
        if execute_calls == 1:
            r.scalar_one.return_value = session
        elif execute_calls == 2:
            r.scalars.return_value.all.return_value = fetch_turn_batches[0]
        elif execute_calls == 3:
            r.scalar_one.return_value = concept
        elif execute_calls == 4:
            r.scalars.return_value.all.return_value = fetch_turn_batches[1]
        else:
            r.scalar_one_or_none.return_value = None
        return r

    db.execute = _exec
    db.flush = AsyncMock()

    composer_result = "C:\\reports\\fake.html"
    compose_mock = AsyncMock(return_value=composer_result)
    analyst_mock = AsyncMock(return_value={"overall_performance": "developing", "insight": "x", "recommendations": []})

    with (
        patch("Engine.nodes.generate_clarification", new=AsyncMock(return_value="Backfilled explanation")),
        patch("Engine.nodes.generate_turn_diagram", new=AsyncMock(return_value="graph TD; A-->B")),
        patch("Engine.nodes.render_mermaid_to_svg", new=AsyncMock(return_value="<svg><g>Turn diagram</g></svg>")),
        patch("Engine.nodes.analyse_session_performance", new=analyst_mock),
        patch("Pipelines.ReportComposer.ReportComposer.compose", new=compose_mock),
    ):
        out = await report_work(
            {
                "session_id": str(sid),
                "concept_id": str(cid),
                "probe_turns": 2,
                "last_classifier_confidence": 0.7,
                "session_stats": {"classifier_sequence": ["partial"]},
                "self_rating": 3,
                "reveal_assets": {"ideal_answer": "Ideal", "diagram_svg": "<svg><g></g></svg>"},
            },
            {"configurable": {"db": db}},
        )

    compose_turns = compose_mock.await_args.kwargs["turns"]
    assert compose_turns[0].correct_answer == "Expected model answer"
    assert compose_turns[0].clarification == "Backfilled explanation"
    assert compose_turns[0].diagram_svg == "<svg><g>Turn diagram</g></svg>"
    assert compose_turns[0].clarification_status == "ready"
    assert out["report_pdf_path"] == composer_result
