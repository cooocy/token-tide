"""create balance tables

Revision ID: 202607251100
Revises:
Create Date: 2026-07-25 11:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607251100"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "balance_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("available_amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("prepaid_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("granted_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_balance_snapshot_provider_currency_observed",
        "balance_snapshot",
        ["provider", "currency", "observed_at"],
    )
    op.create_table(
        "refresh_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_refresh_run_provider_started",
        "refresh_run",
        ["provider", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_refresh_run_provider_started", table_name="refresh_run")
    op.drop_table("refresh_run")
    op.drop_index(
        "idx_balance_snapshot_provider_currency_observed",
        table_name="balance_snapshot",
    )
    op.drop_table("balance_snapshot")
