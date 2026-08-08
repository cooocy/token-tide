from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.orm import Session

from token_tide.response import ApplicationError
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.models import (
    TokenUsageCheckpointModel,
    TokenUsageEventModel,
)
from token_tide.token_usage.schemas import (
    TokenUsageBatchInput,
    TokenUsageBatchResult,
    TokenUsageCalendar,
    TokenUsageCalendarDay,
    TokenUsageCheckpointValue,
    TokenUsageDay,
    TokenUsageEventInput,
    TokenUsageModelSummary,
    TokenUsageOverview,
    TokenUsageSummary,
    TokenUsageToolSummary,
    TokenUsageTotals,
)

EVENT_FIELDS = (
    "occurred_at",
    "model",
    "provider",
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "reasoning_tokens",
    "total_tokens",
)
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
    "reasoning_tokens",
    "total_tokens",
)
MAX_SUMMARY_RANGE = timedelta(days=31)
MAX_CALENDAR_DAYS = 371


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TokenUsageService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def checkpoint(self, tool: TokenUsageTool) -> TokenUsageCheckpointValue:
        with self.session_factory() as session:
            checkpoint = session.get(TokenUsageCheckpointModel, tool.value)
            if checkpoint is None:
                return TokenUsageCheckpointValue(
                    tool=tool,
                    cursor={},
                    updated_at=None,
                )
            return TokenUsageCheckpointValue(
                tool=tool,
                cursor=checkpoint.cursor,
                updated_at=checkpoint.updated_at,
            )

    def totals(self, tool: TokenUsageTool | None) -> TokenUsageTotals:
        statement = self._totals_statement()
        if tool is not None:
            statement = statement.where(TokenUsageEventModel.tool == tool.value)

        with self.session_factory() as session:
            row = session.execute(statement).one()
        return self._totals_from_mapping(row._mapping)

    def overview(self) -> TokenUsageOverview:
        tool_statement = select(
            TokenUsageEventModel.tool,
            *self._aggregate_columns(),
        ).group_by(TokenUsageEventModel.tool)
        model_total = func.coalesce(
            func.sum(TokenUsageEventModel.total_tokens),
            0,
        ).label("total_tokens")
        model_statement = (
            select(
                TokenUsageEventModel.model,
                func.count(TokenUsageEventModel.id).label("event_count"),
                model_total,
            )
            .group_by(TokenUsageEventModel.model)
            .order_by(
                model_total.desc(),
                func.lower(TokenUsageEventModel.model),
            )
        )

        with self.session_factory() as session:
            totals_row = session.execute(self._totals_statement()).one()
            tool_rows = session.execute(tool_statement).all()
            model_rows = session.execute(model_statement).all()

        tool_totals = {
            TokenUsageTool(row.tool): self._totals_from_mapping(row._mapping)
            for row in tool_rows
        }
        return TokenUsageOverview(
            totals=self._totals_from_mapping(totals_row._mapping),
            tools=[
                TokenUsageToolSummary(
                    tool=usage_tool,
                    **tool_totals.get(
                        usage_tool,
                        TokenUsageTotals(),
                    ).model_dump(),
                )
                for usage_tool in TokenUsageTool
            ],
            models=[
                TokenUsageModelSummary(
                    model=row.model,
                    event_count=int(row.event_count),
                    total_tokens=int(row.total_tokens),
                )
                for row in model_rows
            ],
        )

    def calendar(
        self,
        start_date: date,
        end_date: date,
        calendar_timezone: tzinfo,
        timezone_name: str,
        now: datetime | None = None,
    ) -> TokenUsageCalendar:
        if start_date > end_date:
            raise ApplicationError(
                422,
                42206,
                "start-date must not be after end-date",
            )
        day_count = (end_date - start_date).days + 1
        if day_count > MAX_CALENDAR_DAYS:
            raise ApplicationError(
                422,
                42207,
                "Token usage calendar range cannot exceed 371 days",
            )

        local_dates = [
            start_date + timedelta(days=offset)
            for offset in range(day_count)
        ]
        day_ranges = [
            (
                local_date,
                datetime.combine(
                    local_date,
                    time.min,
                    calendar_timezone,
                ).astimezone(UTC),
                datetime.combine(
                    local_date + timedelta(days=1),
                    time.min,
                    calendar_timezone,
                ).astimezone(UTC),
            )
            for local_date in local_dates
        ]
        local_date_bucket = case(
            *[
                (
                    TokenUsageEventModel.occurred_at < day_end,
                    literal_column(f"'{local_date.isoformat()}'"),
                )
                for local_date, _day_start, day_end in day_ranges
            ],
            else_=None,
        ).label("local_date")
        statement = (
            select(
                local_date_bucket,
                func.count(TokenUsageEventModel.id).label("event_count"),
                func.coalesce(
                    func.sum(TokenUsageEventModel.total_tokens),
                    0,
                ).label("total_tokens"),
            )
            .where(
                TokenUsageEventModel.occurred_at >= day_ranges[0][1],
                TokenUsageEventModel.occurred_at < day_ranges[-1][2],
            )
            .group_by("local_date")
            .order_by("local_date")
        )

        bounds_statement = select(
            func.min(TokenUsageEventModel.occurred_at).label("first_event_at"),
        )
        with self.session_factory() as session:
            rows = session.execute(statement).all()
            bounds = session.execute(bounds_statement).one()

        daily_totals = {
            date.fromisoformat(str(row.local_date)): (
                int(row.event_count),
                int(row.total_tokens),
            )
            for row in rows
            if row.local_date is not None
        }
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            raise ValueError("now must include timezone")
        current_year = current_time.astimezone(calendar_timezone).year
        if bounds.first_event_at is None:
            available_years = [current_year]
        else:
            first_year = normalize_datetime(
                bounds.first_event_at,
            ).astimezone(calendar_timezone).year
            available_years = list(
                range(current_year, min(current_year, first_year) - 1, -1)
            )

        return TokenUsageCalendar(
            start_date=start_date,
            end_date=end_date,
            timezone=timezone_name,
            available_years=available_years,
            days=[
                TokenUsageCalendarDay(
                    date=local_date,
                    event_count=daily_totals.get(local_date, (0, 0))[0],
                    total_tokens=daily_totals.get(local_date, (0, 0))[1],
                )
                for local_date in local_dates
            ],
        )

    def summary(
        self,
        tool: TokenUsageTool | None,
        start_time: datetime,
        end_time: datetime,
        timezone_offset_minutes: int,
        calendar_timezone: tzinfo | None = None,
    ) -> TokenUsageSummary:
        start_time = self._require_aware_datetime(start_time)
        end_time = self._require_aware_datetime(end_time)
        if start_time >= end_time:
            raise ApplicationError(422, 42202, "start-time must be before end-time")
        if end_time - start_time > MAX_SUMMARY_RANGE:
            raise ApplicationError(422, 42203, "Token usage range cannot exceed 31 days")

        statement = select(TokenUsageEventModel).where(
            TokenUsageEventModel.occurred_at >= start_time,
            TokenUsageEventModel.occurred_at < end_time,
        )
        if tool is not None:
            statement = statement.where(TokenUsageEventModel.tool == tool.value)
        statement = statement.order_by(
            TokenUsageEventModel.occurred_at,
            TokenUsageEventModel.id,
        )

        with self.session_factory() as session:
            events = session.scalars(statement).all()

        totals = self._empty_totals()
        tool_totals = {
            usage_tool: self._empty_totals()
            for usage_tool in TokenUsageTool
        }
        model_totals: dict[str, dict[str, int]] = {}
        offset = timedelta(minutes=timezone_offset_minutes)
        daily_totals: dict[date, dict[TokenUsageTool, int]] = {}

        for event in events:
            event_tool = TokenUsageTool(event.tool)
            self._add_event(totals, event)
            self._add_event(tool_totals[event_tool], event)

            model = model_totals.setdefault(
                event.model,
                {"event_count": 0, "total_tokens": 0},
            )
            model["event_count"] += 1
            model["total_tokens"] += event.total_tokens

            occurred_at = normalize_datetime(event.occurred_at)
            local_date = (
                occurred_at.astimezone(calendar_timezone).date()
                if calendar_timezone is not None
                else (occurred_at + offset).date()
            )
            day = daily_totals.setdefault(
                local_date,
                {usage_tool: 0 for usage_tool in TokenUsageTool},
            )
            day[event_tool] += event.total_tokens

        if calendar_timezone is None:
            first_date = (start_time + offset).date()
            last_date = (end_time - timedelta(microseconds=1) + offset).date()
        else:
            first_date = start_time.astimezone(calendar_timezone).date()
            last_date = (
                end_time - timedelta(microseconds=1)
            ).astimezone(calendar_timezone).date()
        timeline: list[TokenUsageDay] = []
        current_date = first_date
        while current_date <= last_date:
            day_tools = daily_totals.get(
                current_date,
                {usage_tool: 0 for usage_tool in TokenUsageTool},
            )
            timeline.append(
                TokenUsageDay(
                    date=current_date,
                    total_tokens=sum(day_tools.values()),
                    tools=day_tools,
                )
            )
            current_date += timedelta(days=1)

        return TokenUsageSummary(
            start_time=start_time,
            end_time=end_time,
            timezone_offset_minutes=timezone_offset_minutes,
            totals=TokenUsageTotals(**totals),
            tools=[
                TokenUsageToolSummary(tool=usage_tool, **tool_totals[usage_tool])
                for usage_tool in TokenUsageTool
            ],
            timeline=timeline,
            models=[
                TokenUsageModelSummary(model=model, **values)
                for model, values in sorted(
                    model_totals.items(),
                    key=lambda item: (-item[1]["total_tokens"], item[0].lower()),
                )
            ],
        )

    def ingest(
        self,
        tool: TokenUsageTool,
        batch: TokenUsageBatchInput,
    ) -> TokenUsageBatchResult:
        source_ids = [event.source_event_id for event in batch.events]
        if len(source_ids) != len(set(source_ids)):
            raise ApplicationError(
                422,
                42201,
                "Duplicate source_event_id in batch",
            )

        created = updated = unchanged = 0
        with self.session_factory() as session:
            existing = {
                event.source_event_id: event
                for event in session.scalars(
                    select(TokenUsageEventModel).where(
                        TokenUsageEventModel.tool == tool.value,
                        TokenUsageEventModel.source_event_id.in_(source_ids),
                    )
                )
            }
            for value in batch.events:
                event = existing.get(value.source_event_id)
                if event is None:
                    session.add(self._new_event(tool, value))
                    created += 1
                elif self._event_changed(event, value):
                    self._update_event(event, value)
                    updated += 1
                else:
                    unchanged += 1

            now = datetime.now(UTC)
            checkpoint = session.get(TokenUsageCheckpointModel, tool.value)
            if checkpoint is None:
                checkpoint = TokenUsageCheckpointModel(
                    tool=tool.value,
                    cursor=batch.next_cursor,
                    updated_at=now,
                )
                session.add(checkpoint)
            else:
                checkpoint.cursor = batch.next_cursor
                checkpoint.updated_at = now
            session.commit()

        return TokenUsageBatchResult(
            tool=tool,
            created=created,
            updated=updated,
            unchanged=unchanged,
            cursor=batch.next_cursor,
        )

    @staticmethod
    def _require_aware_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ApplicationError(
                422,
                42204,
                "Token usage range timestamps must include timezone",
            )
        return value.astimezone(UTC)

    @staticmethod
    def _empty_totals() -> dict[str, int]:
        return {"event_count": 0, **{field: 0 for field in TOKEN_FIELDS}}

    @staticmethod
    def _aggregate_columns() -> list[object]:
        return [
            func.count(TokenUsageEventModel.id).label("event_count"),
            *[
                func.coalesce(
                    func.sum(getattr(TokenUsageEventModel, field)),
                    0,
                ).label(field)
                for field in TOKEN_FIELDS
            ],
        ]

    @classmethod
    def _totals_statement(cls):
        return select(*cls._aggregate_columns())

    @staticmethod
    def _totals_from_mapping(values) -> TokenUsageTotals:
        return TokenUsageTotals(
            event_count=int(values["event_count"]),
            **{
                field: int(values[field])
                for field in TOKEN_FIELDS
            },
        )

    @staticmethod
    def _add_event(
        totals: dict[str, int],
        event: TokenUsageEventModel,
    ) -> None:
        totals["event_count"] += 1
        for field in TOKEN_FIELDS:
            totals[field] += getattr(event, field)

    @staticmethod
    def _new_event(
        tool: TokenUsageTool,
        value: TokenUsageEventInput,
    ) -> TokenUsageEventModel:
        return TokenUsageEventModel(
            tool=tool.value,
            **value.model_dump(),
        )

    @staticmethod
    def _event_changed(
        event: TokenUsageEventModel,
        value: TokenUsageEventInput,
    ) -> bool:
        for field in EVENT_FIELDS:
            stored = getattr(event, field)
            incoming = getattr(value, field)
            if field == "occurred_at":
                stored = normalize_datetime(stored)
                incoming = normalize_datetime(incoming)
            if stored != incoming:
                return True
        return False

    @staticmethod
    def _update_event(
        event: TokenUsageEventModel,
        value: TokenUsageEventInput,
    ) -> None:
        for field in (*EVENT_FIELDS, "reported_at"):
            setattr(event, field, getattr(value, field))
