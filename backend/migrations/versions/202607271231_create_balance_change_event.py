"""create balance change event

Revision ID: 202607271231
Revises: 202607251800
Create Date: 2026-07-27 12:31:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607271231"
down_revision: str | None = "202607251800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "balance_change_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("previous_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("current_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("change_amount", sa.Numeric(20, 2), nullable=True),
        sa.Column("change_type", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["balance_snapshot.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )
    op.create_index(
        "idx_balance_change_event_provider_currency_occurred",
        "balance_change_event",
        ["provider", "currency", "occurred_at"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO balance_change_event (
                snapshot_id,
                provider,
                currency,
                previous_amount,
                current_amount,
                change_amount,
                change_type,
                occurred_at
            )
            SELECT
                snapshot.id,
                snapshot.provider,
                snapshot.currency,
                NULL,
                snapshot.available_amount,
                NULL,
                'INITIAL',
                snapshot.observed_at
            FROM balance_snapshot AS snapshot
            WHERE NOT EXISTS (
                SELECT 1
                FROM balance_snapshot AS newer
                WHERE newer.provider = snapshot.provider
                  AND newer.currency = snapshot.currency
                  AND (
                    newer.observed_at > snapshot.observed_at
                    OR (
                        newer.observed_at = snapshot.observed_at
                        AND newer.id > snapshot.id
                    )
                  )
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "idx_balance_change_event_provider_currency_occurred",
        table_name="balance_change_event",
    )
    op.drop_table("balance_change_event")
