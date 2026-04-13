import uuid
from pathlib import Path

import pytest

from Pipelines.ReportComposer import ReportComposer


class _Turn:
    def __init__(self):
        self.student_input = "My answer"
        self.question_generated = "Next question?"
        self.classifier_state = "partial"
        self.correct_answer = "Expected model answer"
        self.clarification = "Missed causal link"
        self.diagram_svg = None


@pytest.mark.asyncio
async def test_report_composer_writes_report_artifact(tmp_path: Path):
    composer = ReportComposer()
    composer._output_dir = tmp_path

    out = await composer.compose(
        session_id=uuid.uuid4(),
        concept_name="Test Concept",
        state_snapshot={"probe_turns": 2, "self_rating": 3, "last_classifier_confidence": 0.6},
        analyst={"overall_performance": "developing", "insight": "Keep practicing", "recommendations": []},
        turns=[_Turn()],
        diagram_svg="",
        ideal_answer="Ideal answer",
        review_schedule=[],
    )

    assert out.endswith(".html") or out.endswith(".pdf")
    assert Path(out).is_file()
