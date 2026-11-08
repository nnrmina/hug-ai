"""Persist pending (human-in-the-loop) agent actions

Revision ID: 0002_pending_actions
Revises: 0001_initial_schema
Create Date: 2026-11-09 01:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_pending_actions"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("intent", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("action_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_actions_expires_at", "pending_actions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_pending_actions_expires_at", table_name="pending_actions")
    op.drop_table("pending_actions")
