"""Persist Digital Shield results and device-token bindings

Revision ID: 0003_auth_and_security_results
Revises: 0002_pending_actions
Create Date: 2026-11-09 02:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_and_security_results"
down_revision: Union[str, None] = "0002_pending_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_analyses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("risk_level", sa.String(length=10), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("indicators", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_analyses_user_id", "security_analyses", ["user_id"])

    op.create_table(
        "device_claims",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "device_credentials",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("device_credentials")
    op.drop_table("device_claims")
    op.drop_index("ix_security_analyses_user_id", table_name="security_analyses")
    op.drop_table("security_analyses")
