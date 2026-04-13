"""Unit tests for guard parsing, fallback rotation, and surrender detection."""

import pytest

from Engine.AntiAnswerGuard import interpret_guard_model_output
from Engine.student_signals import is_student_surrender
from Engine.tutor_fallback import is_near_duplicate_question, pick_fallback_question


@pytest.mark.parametrize(
    "raw,expected_pass",
    [
        ("NO", True),
        ("NO.", True),
        ("Answer: NO", True),
        ("The result is **NO**", True),
        ("```\nNO\n```", True),
        ("YES", False),
        ("Answer: YES — violates rule", False),
        ("I think NO because it is a question", True),
        ("YES\n\nActually NO", True),
        ("", True),
        ("Maybe", True),
    ],
)
def test_interpret_guard_model_output(raw: str, expected_pass: bool) -> None:
    assert interpret_guard_model_output(raw) is expected_pass


def test_pick_fallback_rotates_away_from_prior() -> None:
    prior = [
        "What is one concrete example from the material that relates to Linear Algebra?",
    ]
    q = pick_fallback_question("Linear Algebra", prior, 0.82, rotation_seed=0)
    assert q != prior[0]
    assert "Linear Algebra" in q


def test_pick_fallback_stable_when_no_collision() -> None:
    q = pick_fallback_question("RAG", [], 0.82, rotation_seed=0)
    assert "RAG" in q
    assert len(q) > 20


def test_is_near_duplicate_respects_threshold() -> None:
    a = "What is one concrete example from the material that relates to X?"
    assert is_near_duplicate_question(a, [a], 0.82)
    assert not is_near_duplicate_question("Short", ["Long prior question here?"], 0.82)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("no", True),
        ("No.", True),
        ("NO!", True),
        ("nope", True),
        ("I don't know", True),
        ("not sure", True),
        ("I know vectors", False),
        ("nothingburger", False),
    ],
)
def test_is_student_surrender(text: str, expected: bool) -> None:
    assert is_student_surrender(text) is expected
