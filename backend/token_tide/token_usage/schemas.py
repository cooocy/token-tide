from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_serializer, field_validator

from token_tide.token_usage.domain import TokenUsageTool

TokenCount = Annotated[int, Field(ge=0)]


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include timezone")
    return value.astimezone(UTC)


def serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


class TokenUsageEventInput(BaseModel):
    source_event_id: str = Field(min_length=64, max_length=64)
    occurred_at: datetime
    reported_at: datetime
    model: str = Field(min_length=1, max_length=255)
    provider: str = Field(default="", max_length=128)
    input_tokens: TokenCount = 0
    output_tokens: TokenCount = 0
    cache_creation_tokens: TokenCount = 0
    cache_read_tokens: TokenCount = 0
    reasoning_tokens: TokenCount = 0
    total_tokens: TokenCount = 0

    @field_validator("occurred_at", "reported_at")
    @classmethod
    def validate_datetime(cls, value: datetime) -> datetime:
        return utc_datetime(value)


class TokenUsageBatchInput(BaseModel):
    events: list[TokenUsageEventInput] = Field(max_length=500)
    next_cursor: dict[str, object]


class TokenUsageCheckpointValue(BaseModel):
    tool: TokenUsageTool
    cursor: dict[str, object]
    updated_at: datetime | None

    @field_serializer("updated_at", when_used="json")
    def serialize_updated_at(self, value: datetime | None) -> str | None:
        return serialize_utc(value)


class TokenUsageBatchResult(BaseModel):
    tool: TokenUsageTool
    created: int
    updated: int
    unchanged: int
    cursor: dict[str, object]


class TokenUsageTotals(BaseModel):
    event_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0


class TokenUsageToolSummary(TokenUsageTotals):
    tool: TokenUsageTool


class TokenUsageDay(BaseModel):
    date: date
    total_tokens: int
    tools: dict[TokenUsageTool, int]


class TokenUsageModelSummary(BaseModel):
    model: str
    event_count: int
    total_tokens: int


class TokenUsageOverview(BaseModel):
    totals: TokenUsageTotals
    tools: list[TokenUsageToolSummary]
    models: list[TokenUsageModelSummary]


class TokenUsageCalendarDay(BaseModel):
    date: date
    event_count: int
    total_tokens: int


class TokenUsageCalendar(BaseModel):
    start_date: date
    end_date: date
    timezone: str
    days: list[TokenUsageCalendarDay]


class TokenUsageSummary(BaseModel):
    start_time: datetime
    end_time: datetime
    timezone_offset_minutes: int
    totals: TokenUsageTotals
    tools: list[TokenUsageToolSummary]
    timeline: list[TokenUsageDay]
    models: list[TokenUsageModelSummary]

    @field_serializer("start_time", "end_time", when_used="json")
    def serialize_range_time(self, value: datetime) -> str | None:
        return serialize_utc(value)
