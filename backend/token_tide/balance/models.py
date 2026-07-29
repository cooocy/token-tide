from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from token_tide.database import Base


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshot"
    __table_args__ = (
        Index(
            "idx_balance_snapshot_provider_currency_observed",
            "provider",
            "currency",
            "observed_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    available_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BalanceChangeEvent(Base):
    __tablename__ = "balance_change_event"
    __table_args__ = (
        Index(
            "idx_balance_change_event_provider_currency_occurred",
            "provider",
            "currency",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("balance_snapshot.id"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    previous_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    current_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    change_type: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RefreshRun(Base):
    __tablename__ = "refresh_run"
    __table_args__ = (Index("idx_refresh_run_provider_started", "provider", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
