"""Add per-turn correct answers and per-session concept diagrams.

Revision ID: 006_turn_correct_answer
Revises: 005_stage3
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_turn_correct_answer"
down_revision: str | None = "005_stage3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("turns", sa.Column("correct_answer", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("concept_diagrams", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "concept_diagrams")
    op.drop_column("turns", "correct_answer")
