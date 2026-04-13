import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Content ──────────────────────────────────────────────────────────

class ConceptEdgeOut(BaseModel):
    id: uuid.UUID
    from_concept_id: uuid.UUID
    to_concept_id: uuid.UUID
    relationship: str

    model_config = {"from_attributes": True}


class ConceptOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    name: str
    description: str | None
    difficulty_level: int

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source_type: str
    chunk_count: int
    ingested_at: datetime
    project_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    source_type: str


class ConceptGraphResponse(BaseModel):
    document_id: uuid.UUID
    concepts: list[ConceptOut]
    edges: list[ConceptEdgeOut]


# ── Projects ─────────────────────────────────────────────────────────

class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreateRequest(BaseModel):
    name: str


# ── Session ──────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    concept_id: uuid.UUID
    user_id: uuid.UUID | None = None
    session_mode: Literal["socratic", "exam_prep"] = "socratic"
    use_stage2: bool = Field(
        default=False,
        description="Enable Stage 2 phased teaching (LangGraph). Ignored when session_mode is exam_prep.",
    )
    initial_message: str | None = Field(
        default=None,
        description="Optional first student message; otherwise tutor opens with a question.",
    )


class SessionStartResponse(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    concept_id: uuid.UUID
    prompt_version: str
    opening_question: str
    session_mode: Literal["socratic", "exam_prep"]
    exam_target_turns: int = Field(description="Planned number of graded rounds in exam_prep mode.")
    use_stage2: bool = False
    teaching_phase: str | None = None
    session_name: str | None = None


class SessionPhaseOut(BaseModel):
    session_id: uuid.UUID
    phase: str
    probe_turns: int
    max_probe_turns: int
    self_rating: int | None = None
    report_status: str | None = None
    last_reveal: dict | None = None
    last_tutor_plain: str | None = None


class ReflectRequest(BaseModel):
    rating: int = Field(ge=1, le=5, description="Self-reported understanding after reveal.")


class ReportStatusOut(BaseModel):
    session_id: uuid.UUID
    status: str
    pdf_path: str | None = None


class TurnRequest(BaseModel):
    answer: str


class TurnOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    student_input: str
    classifier_state: str
    question_generated: str
    created_at: datetime
    clarification: str | None = None
    diagram_svg: str | None = None
    clarification_status: str | None = None

    model_config = {"from_attributes": True}


class TurnClarificationOut(BaseModel):
    turn_id: uuid.UUID
    clarification: str | None = None
    diagram_svg: str | None = None
    status: str


class ExamResultOut(BaseModel):
    turns_graded: int
    points_earned: float
    points_possible: float
    score_percent: float


class SessionEndResponse(BaseModel):
    session_id: uuid.UUID
    summary: str | None = None
    exam: ExamResultOut | None = None


class SessionHistoryItem(BaseModel):
    session_id: uuid.UUID
    concept_id: uuid.UUID
    concept_name: str
    total_turns: int
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    name: str | None = None


# ── Progress ─────────────────────────────────────────────────────────

class MasteryOut(BaseModel):
    concept_id: uuid.UUID
    score: float
    repetitions: int
    easiness_factor: float
    next_review_date: date | None

    model_config = {"from_attributes": True}


class DueConceptOut(BaseModel):
    concept_id: uuid.UUID
    name: str
    next_review_date: date


class ProgressHistoryOut(BaseModel):
    mastery: list[MasteryOut]
    sessions: list[SessionHistoryItem]


class EvalClassifierRequest(BaseModel):
    dataset_path: str | None = None
    prompt_version: str = "v1.0.0"
