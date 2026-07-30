from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from token_tide.database import Base


class TokenUsageEventModel(Base):
    __tablename__ = "token_usage_event"
    __table_args__ = (
        UniqueConstraint(
            "tool",
            "source_event_id",
            name="uq_token_usage_event_tool_source",
        ),
        Index(
            "idx_token_usage_event_tool_occurred",
            "tool",
            "occurred_at",
        ),
        Index(
            "idx_token_usage_event_occurred",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tool: Mapped[str] = mapped_column(String(16), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_creation_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class TokenUsageCheckpointModel(Base):
    __tablename__ = "token_usage_checkpoint"

    tool: Mapped[str] = mapped_column(String(16), primary_key=True)
    cursor: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
