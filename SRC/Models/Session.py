import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    """Opaque client-supplied identity (no auth in v1)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TutorSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0.0")
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="socratic")
    use_stage2: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    teaching_phase: Mapped[str | None] = mapped_column(String(32), nullable=True)
    self_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    concept_diagrams: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)

    turns: Mapped[list["Turn"]] = relationship(back_populates="session")
    mastery_scores: Mapped[list["MasteryScore"]] = relationship(back_populates="session")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    student_input: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_state: Mapped[str] = mapped_column(String(32), nullable=False)
    stuck_streak: Mapped[int] = mapped_column(Integer, default=0)
    question_generated: Mapped[str] = mapped_column(Text, nullable=False)
    guardrail_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagram_svg: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    session: Mapped["TutorSession"] = relationship(back_populates="turns")


class MasteryScore(Base):
    __tablename__ = "mastery_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    easiness_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    session: Mapped["TutorSession | None"] = relationship(back_populates="mastery_scores")
