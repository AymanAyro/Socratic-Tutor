"""Stage 3 turn clarifications and session naming.

Revision ID: 005_stage3
Revises: 004_stage2
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_stage3"
down_revision: str | None = "004_stage2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("turns", sa.Column("clarification", sa.Text(), nullable=True))
    op.add_column("turns", sa.Column("diagram_svg", sa.Text(), nullable=True))
    op.add_column(
        "turns",
        sa.Column(
            "clarification_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.alter_column("turns", "clarification_status", server_default=None)
    op.add_column("sessions", sa.Column("name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "name")
    op.drop_column("turns", "clarification_status")
    op.drop_column("turns", "diagram_svg")
    op.drop_column("turns", "clarification")
