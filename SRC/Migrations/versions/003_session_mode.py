"""Add session_mode to sessions.

Revision ID: 003_session_mode
Revises: 002_add_projects
Create Date: 2026-04-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_session_mode"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("session_mode", sa.String(length=32), nullable=False, server_default="socratic"),
    )
    op.alter_column("sessions", "session_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("sessions", "session_mode")
