"""drop granted amount

Revision ID: 202607251800
Revises: 202607251710
Create Date: 2026-07-25 18:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202607251800"
down_revision: str | None = "202607251710"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("balance_snapshot", "granted_amount")


def downgrade() -> None:
    op.add_column(
        "balance_snapshot",
        sa.Column("granted_amount", sa.Numeric(20, 2), nullable=True),
    )
