from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

BalanceChangeType = Literal["INITIAL", "SUPPLY", "CONSUMPTION"]


def serialize_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


class ApplicationInfo(BaseModel):
    app: str
    ts: str
    token_tide_commit: str = Field(alias="TOKEN_TIDE_COMMIT")


class BalanceValue(BaseModel):
    currency: str
    available_amount: str
    is_available: bool
    observed_at: datetime

    @field_serializer("observed_at", when_used="json")
    def serialize_observed_at(self, value: datetime) -> str | None:
        return serialize_utc_datetime(value)


class ProviderBalance(BaseModel):
    provider: str
    status: str
    last_refresh_at: datetime | None
    last_success_at: datetime | None
    error_code: str | None
    error_message: str | None
    balances: list[BalanceValue]

    @field_serializer("last_refresh_at", "last_success_at", when_used="json")
    def serialize_refresh_at(self, value: datetime | None) -> str | None:
        return serialize_utc_datetime(value)


class BalanceChangeEventValue(BaseModel):
    id: int
    currency: str
    previous_amount: str | None
    current_amount: str
    change_amount: str | None
    change_type: BalanceChangeType
    occurred_at: datetime

    @field_serializer("occurred_at", when_used="json")
    def serialize_occurred_at(self, value: datetime) -> str | None:
        return serialize_utc_datetime(value)


class BalanceHistory(BaseModel):
    provider: str
    currency: str | None
    events: list[BalanceChangeEventValue]


class ProviderRefreshResult(BaseModel):
    provider: str
    status: str
    started_at: datetime
    finished_at: datetime
    snapshot_count: int
    error_code: str | None = None
    error_message: str | None = None

    @field_serializer("started_at", "finished_at", when_used="json")
    def serialize_run_at(self, value: datetime) -> str | None:
        return serialize_utc_datetime(value)
