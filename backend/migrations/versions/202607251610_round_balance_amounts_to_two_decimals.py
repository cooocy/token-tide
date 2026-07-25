"""round balance amounts to two decimals

Revision ID: 202607251610
Revises: 202607251100
Create Date: 2026-07-25 16:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607251610"
down_revision: str | None = "202607251100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE balance_snapshot
        SET available_amount = ROUND(available_amount, 2),
            prepaid_amount = ROUND(prepaid_amount, 2),
            granted_amount = ROUND(granted_amount, 2)
        """
    )
    op.alter_column(
        "balance_snapshot",
        "available_amount",
        existing_type=sa.Numeric(20, 8),
        type_=sa.Numeric(20, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "balance_snapshot",
        "prepaid_amount",
        existing_type=sa.Numeric(20, 8),
        type_=sa.Numeric(20, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "balance_snapshot",
        "granted_amount",
        existing_type=sa.Numeric(20, 8),
        type_=sa.Numeric(20, 2),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "balance_snapshot",
        "granted_amount",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Numeric(20, 8),
        existing_nullable=True,
    )
    op.alter_column(
        "balance_snapshot",
        "prepaid_amount",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Numeric(20, 8),
        existing_nullable=True,
    )
    op.alter_column(
        "balance_snapshot",
        "available_amount",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Numeric(20, 8),
        existing_nullable=False,
    )
