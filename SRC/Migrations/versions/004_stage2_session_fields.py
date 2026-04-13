"""Stage 2 session fields (phases, report, self-rating).

Revision ID: 004_stage2
Revises: 003_session_mode
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_stage2"
down_revision: str | None = "003_session_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("use_stage2", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("sessions", sa.Column("teaching_phase", sa.String(length=32), nullable=True))
    op.add_column("sessions", sa.Column("self_rating", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("report_pdf_path", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("report_status", sa.String(length=32), nullable=True))
    op.alter_column("sessions", "use_stage2", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "report_status")
    op.drop_column("sessions", "report_pdf_path")
    op.drop_column("sessions", "self_rating")
    op.drop_column("sessions", "teaching_phase")
    op.drop_column("sessions", "use_stage2")
