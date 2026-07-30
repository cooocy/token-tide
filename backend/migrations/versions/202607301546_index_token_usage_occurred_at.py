"""index token usage occurred time

Revision ID: 202607301546
Revises: 202607301226
Create Date: 2026-07-30 15:46:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202607301546"
down_revision: str | None = "202607301226"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_token_usage_event_occurred",
        "token_usage_event",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_token_usage_event_occurred",
        table_name="token_usage_event",
    )
