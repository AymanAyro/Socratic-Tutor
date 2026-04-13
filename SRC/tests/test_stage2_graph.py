"""Stage 2 teaching graph: probe gating, phase reducer, reflect Command path."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from Engine.graph import build_teaching_graph
from Engine.nodes import probe_mastery_allows_reveal
from Engine.state import replace_str


@pytest.mark.parametrize(
    ("probe_turns", "min_probe", "expected"),
    [
        (0, 3, False),
        (1, 3, False),
        (2, 3, True),
        (0, 1, True),
    ],
)
def test_probe_mastery_allows_reveal_respects_min_turns(probe_turns, min_probe, expected):
    assert (
        probe_mastery_allows_reveal(
            probe_turns,
            classifier_state="correct",
            confidence=0.99,
            min_probe_turns=min_probe,
            mastery_confidence_threshold=0.5,
        )
        is expected
    )


def test_probe_mastery_requires_correct_state():
    assert not probe_mastery_allows_reveal(
        5,
        classifier_state="partial",
        confidence=0.99,
        min_probe_turns=1,
        mastery_confidence_threshold=0.5,
    )


def test_replace_str_last_wins():
    assert replace_str("PROBE", "CONSOLIDATE") == "CONSOLIDATE"


@pytest.mark.asyncio
async def test_reflect_command_does_not_raise_invalid_phase_update():
    """Command(goto=reflect_consolidate) used to collide on `phase` in one super-step."""
    sid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    cid = str(uuid.uuid4())

    db = AsyncMock()

    async def _exec(*_a, **_k):
        r = MagicMock()
        concept = MagicMock()
        concept.name = "Test concept"
        r.scalar_one.return_value = concept
        return r

    db.execute = _exec
    db.flush = AsyncMock()

    initial = {
        "messages": [AIMessage(content="opening")],
        "phase": "REFLECT",
        "session_id": sid,
        "user_id": uid,
        "concept_id": cid,
        "concept_name": "Test concept",
        "document_id": str(uuid.uuid4()),
        "difficulty_level": 3,
        "max_probe_turns": 5,
        "opening_question": "What do you know?",
        "prompt_version": "v1.0.0",
        "session_mode": "socratic",
        "probe_turns": 2,
        "reveal_assets": {"ideal_answer": "Ideal text.", "diagram_svg": ""},
        "last_classifier_confidence": 0.8,
        "session_stats": {"classifier_sequence": [], "escape_hatch_count": 0},
    }
    cfg = {
        "configurable": {
            "thread_id": sid,
            "db": db,
            "redis": None,
            "asset_store": {},
        }
    }
    graph = build_teaching_graph(MemorySaver())
    await graph.ainvoke(initial, cfg)

    with patch(
        "Engine.nodes.generate_consolidation_question",
        new=AsyncMock(return_value="One consolidation check?"),
    ):
        out = await graph.ainvoke(
            Command(update={"self_rating": 4}, goto="reflect_consolidate"),
            cfg,
        )

    assert out.get("phase") == "CONSOLIDATE"
    assert out.get("self_rating") == 4
    msgs = out.get("messages") or []
    assert msgs and isinstance(msgs[-1], AIMessage)
