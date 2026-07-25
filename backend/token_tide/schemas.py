from datetime import datetime

from pydantic import BaseModel, Field


class ApplicationInfo(BaseModel):
    app: str
    ts: str
    token_tide_commit: str = Field(alias="TOKEN_TIDE_COMMIT")


class BalanceValue(BaseModel):
    currency: str
    available_amount: str
    prepaid_amount: str | None
    granted_amount: str | None
    is_available: bool
    observed_at: datetime


class ProviderBalance(BaseModel):
    provider: str
    status: str
    last_refresh_at: datetime | None
    last_success_at: datetime | None
    error_code: str | None
    error_message: str | None
    balances: list[BalanceValue]


class HistoryPoint(BalanceValue):
    pass


class BalanceHistory(BaseModel):
    provider: str
    currency: str | None
    points: list[HistoryPoint]


class ProviderRefreshResult(BaseModel):
    provider: str
    status: str
    started_at: datetime
    finished_at: datetime
    snapshot_count: int
    error_code: str | None = None
    error_message: str | None = None
