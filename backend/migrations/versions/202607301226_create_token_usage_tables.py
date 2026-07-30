"""create token usage tables

Revision ID: 202607301226
Revises: 202607271231
Create Date: 2026-07-30 12:26:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607301226"
down_revision: str | None = "202607271231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usage_event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tool", sa.String(length=16), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cache_creation_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cache_read_tokens", sa.BigInteger(), nullable=False),
        sa.Column("reasoning_tokens", sa.BigInteger(), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tool",
            "source_event_id",
            name="uq_token_usage_event_tool_source",
        ),
    )
    op.create_index(
        "idx_token_usage_event_tool_occurred",
        "token_usage_event",
        ["tool", "occurred_at"],
    )
    op.create_table(
        "token_usage_checkpoint",
        sa.Column("tool", sa.String(length=16), nullable=False),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tool"),
    )


def downgrade() -> None:
    op.drop_table("token_usage_checkpoint")
    op.drop_index(
        "idx_token_usage_event_tool_occurred",
        table_name="token_usage_event",
    )
    op.drop_table("token_usage_event")
