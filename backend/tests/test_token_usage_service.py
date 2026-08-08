from datetime import UTC, date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from token_tide.database import Base
from token_tide.response import ApplicationError
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.models import (
    TokenUsageCheckpointModel,
    TokenUsageEventModel,
)
from token_tide.token_usage.schemas import (
    TokenUsageBatchInput,
    TokenUsageEventInput,
    TokenUsageTotals,
)
from token_tide.token_usage.service import TokenUsageService


@pytest.fixture
def service() -> tuple[TokenUsageService, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return TokenUsageService(factory), factory


def event(**overrides: object) -> TokenUsageEventInput:
    values: dict[str, object] = {
        "source_event_id": "a" * 64,
        "occurred_at": datetime(2026, 7, 30, 1, tzinfo=UTC),
        "reported_at": datetime(2026, 7, 30, 2, tzinfo=UTC),
        "model": "gpt-5",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    values.update(overrides)
    return TokenUsageEventInput.model_validate(values)


def test_empty_checkpoint_is_returned_before_first_ingest(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service

    checkpoint = usage_service.checkpoint(TokenUsageTool.CODEX)

    assert checkpoint.cursor == {}
    assert checkpoint.updated_at is None


def test_ingest_is_idempotent_and_updates_checkpoint(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, factory = service
    batch = TokenUsageBatchInput(
        events=[event()],
        next_cursor={"version": 1, "offset": 10},
    )

    first = usage_service.ingest(TokenUsageTool.CODEX, batch)
    second = usage_service.ingest(TokenUsageTool.CODEX, batch)

    assert (first.created, first.updated, first.unchanged) == (1, 0, 0)
    assert (second.created, second.updated, second.unchanged) == (0, 0, 1)
    assert usage_service.checkpoint(TokenUsageTool.CODEX).cursor["offset"] == 10
    with factory() as session:
        assert len(session.scalars(select(TokenUsageEventModel)).all()) == 1
        assert session.get(TokenUsageCheckpointModel, "codex") is not None


def test_changed_source_event_updates_usage_and_reported_time(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, factory = service
    usage_service.ingest(
        TokenUsageTool.OPENCODE,
        TokenUsageBatchInput(events=[event()], next_cursor={"version": 1}),
    )
    next_reported_at = datetime(2026, 7, 30, 3, tzinfo=UTC)

    result = usage_service.ingest(
        TokenUsageTool.OPENCODE,
        TokenUsageBatchInput(
            events=[event(output_tokens=8, total_tokens=18, reported_at=next_reported_at)],
            next_cursor={"version": 1, "time_updated": 20},
        ),
    )

    assert result.updated == 1
    with factory() as session:
        stored = session.scalar(select(TokenUsageEventModel))
        assert stored is not None
        assert stored.output_tokens == 8
        assert stored.reported_at.replace(tzinfo=UTC) == next_reported_at


def test_batch_rejects_duplicate_source_ids(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    batch = TokenUsageBatchInput(
        events=[event(), event()],
        next_cursor={"version": 1},
    )

    with pytest.raises(ApplicationError, match="Duplicate"):
        usage_service.ingest(TokenUsageTool.CLAUDE, batch)


def test_batch_rejects_more_than_500_events() -> None:
    with pytest.raises(ValidationError):
        TokenUsageBatchInput(
            events=[
                event(source_event_id=f"{index:064x}")
                for index in range(501)
            ],
            next_cursor={"version": 1},
        )


def test_totals_aggregate_all_history_and_token_fields(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="b" * 64,
                    input_tokens=70,
                    output_tokens=30,
                    cache_creation_tokens=10,
                    total_tokens=120,
                )
            ],
            next_cursor={"version": 1},
        ),
    )
    usage_service.ingest(
        TokenUsageTool.CLAUDE,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="c" * 64,
                    input_tokens=25,
                    output_tokens=15,
                    cache_read_tokens=5,
                    reasoning_tokens=3,
                    total_tokens=50,
                )
            ],
            next_cursor={"version": 1},
        ),
    )

    totals = usage_service.totals(None)

    assert totals.event_count == 2
    assert totals.input_tokens == 95
    assert totals.output_tokens == 45
    assert totals.cache_creation_tokens == 10
    assert totals.cache_read_tokens == 5
    assert totals.reasoning_tokens == 3
    assert totals.total_tokens == 170


def test_totals_filter_tool_and_return_zero_for_empty_result(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    assert usage_service.totals(None).model_dump() == {
        "event_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }
    usage_service.ingest(
        TokenUsageTool.PI,
        TokenUsageBatchInput(events=[event()], next_cursor={"version": 1}),
    )

    assert usage_service.totals(TokenUsageTool.PI).total_tokens == 15
    assert usage_service.totals(TokenUsageTool.CLAUDE).total_tokens == 0


def test_overview_aggregates_all_history_by_tool_and_model(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="b" * 64,
                    model="gpt-5",
                    input_tokens=70,
                    output_tokens=30,
                    total_tokens=100,
                ),
                event(
                    source_event_id="c" * 64,
                    model="gpt-5-mini",
                    input_tokens=30,
                    output_tokens=20,
                    total_tokens=50,
                ),
            ],
            next_cursor={"version": 1},
        ),
    )
    usage_service.ingest(
        TokenUsageTool.CLAUDE,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="d" * 64,
                    model="claude-sonnet-4",
                    input_tokens=25,
                    output_tokens=15,
                    cache_read_tokens=5,
                    total_tokens=45,
                )
            ],
            next_cursor={"version": 1},
        ),
    )

    overview = usage_service.overview()

    assert overview.totals.event_count == 3
    assert overview.totals.total_tokens == 195
    assert {
        item.tool: (item.event_count, item.total_tokens)
        for item in overview.tools
    } == {
        TokenUsageTool.CLAUDE: (1, 45),
        TokenUsageTool.CODEX: (2, 150),
        TokenUsageTool.OPENCODE: (0, 0),
        TokenUsageTool.PI: (0, 0),
    }
    assert [
        (item.model, item.event_count, item.total_tokens)
        for item in overview.models
    ] == [
        ("gpt-5", 1, 100),
        ("gpt-5-mini", 1, 50),
        ("claude-sonnet-4", 1, 45),
    ]


def test_overview_returns_empty_tools_and_models(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service

    overview = usage_service.overview()

    assert overview.totals == TokenUsageTotals()
    assert [item.tool for item in overview.tools] == list(TokenUsageTool)
    assert all(item.total_tokens == 0 for item in overview.tools)
    assert overview.models == []


def test_summary_aggregates_tools_models_and_local_calendar_days(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="b" * 64,
                    occurred_at=datetime(2026, 7, 29, 15, 30, tzinfo=UTC),
                    model="gpt-5",
                    input_tokens=70,
                    output_tokens=30,
                    total_tokens=100,
                )
            ],
            next_cursor={"version": 1},
        ),
    )
    usage_service.ingest(
        TokenUsageTool.CLAUDE,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="c" * 64,
                    occurred_at=datetime(2026, 7, 29, 16, 30, tzinfo=UTC),
                    model="claude-sonnet-4",
                    input_tokens=25,
                    output_tokens=15,
                    cache_read_tokens=5,
                    total_tokens=45,
                )
            ],
            next_cursor={"version": 1},
        ),
    )

    summary = usage_service.summary(
        tool=None,
        start_time=datetime(2026, 7, 29, 15, tzinfo=UTC),
        end_time=datetime(2026, 7, 30, 16, tzinfo=UTC),
        timezone_offset_minutes=480,
    )

    assert summary.totals.event_count == 2
    assert summary.totals.total_tokens == 145
    assert summary.totals.cache_read_tokens == 5
    assert [day.date.isoformat() for day in summary.timeline] == [
        "2026-07-29",
        "2026-07-30",
    ]
    assert summary.timeline[0].tools[TokenUsageTool.CODEX] == 100
    assert summary.timeline[1].tools[TokenUsageTool.CLAUDE] == 45
    assert summary.timeline[1].total_tokens == 45
    assert [model.model for model in summary.models] == [
        "gpt-5",
        "claude-sonnet-4",
    ]
    assert {item.tool: item.total_tokens for item in summary.tools} == {
        TokenUsageTool.CLAUDE: 45,
        TokenUsageTool.CODEX: 100,
        TokenUsageTool.OPENCODE: 0,
        TokenUsageTool.PI: 0,
    }


def test_summary_filters_one_tool_and_keeps_zero_days(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(events=[event()], next_cursor={"version": 1}),
    )

    summary = usage_service.summary(
        tool=TokenUsageTool.CLAUDE,
        start_time=datetime(2026, 7, 29, tzinfo=UTC),
        end_time=datetime(2026, 7, 31, tzinfo=UTC),
        timezone_offset_minutes=0,
    )

    assert summary.totals.total_tokens == 0
    assert [day.total_tokens for day in summary.timeline] == [0, 0]
    assert summary.models == []


def test_summary_uses_calendar_timezone_across_daylight_saving_change(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="d" * 64,
                    occurred_at=datetime(2026, 3, 8, 4, 30, tzinfo=UTC),
                    total_tokens=10,
                ),
                event(
                    source_event_id="e" * 64,
                    occurred_at=datetime(2026, 3, 8, 5, 30, tzinfo=UTC),
                    total_tokens=20,
                ),
            ],
            next_cursor={"version": 1},
        ),
    )

    summary = usage_service.summary(
        tool=None,
        start_time=datetime(2026, 3, 7, 5, tzinfo=UTC),
        end_time=datetime(2026, 3, 9, 4, tzinfo=UTC),
        timezone_offset_minutes=-240,
        calendar_timezone=ZoneInfo("America/New_York"),
    )

    assert [day.date.isoformat() for day in summary.timeline] == [
        "2026-03-07",
        "2026-03-08",
    ]
    assert [day.total_tokens for day in summary.timeline] == [10, 20]


def test_calendar_aggregates_local_days_and_zero_fills_across_dst(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, _ = service
    usage_service.ingest(
        TokenUsageTool.CODEX,
        TokenUsageBatchInput(
            events=[
                event(
                    source_event_id="d" * 64,
                    occurred_at=datetime(2026, 3, 8, 4, 30, tzinfo=UTC),
                    total_tokens=10,
                ),
                event(
                    source_event_id="e" * 64,
                    occurred_at=datetime(2026, 3, 8, 5, 30, tzinfo=UTC),
                    total_tokens=20,
                ),
            ],
            next_cursor={"version": 1},
        ),
    )

    calendar = usage_service.calendar(
        start_date=date(2026, 3, 6),
        end_date=date(2026, 3, 8),
        calendar_timezone=ZoneInfo("America/New_York"),
        timezone_name="America/New_York",
    )

    assert calendar.timezone == "America/New_York"
    assert [day.date.isoformat() for day in calendar.days] == [
        "2026-03-06",
        "2026-03-07",
        "2026-03-08",
    ]
    assert [day.event_count for day in calendar.days] == [0, 1, 1]
    assert [day.total_tokens for day in calendar.days] == [0, 10, 20]


@pytest.mark.parametrize(
    ("start_date", "end_date", "message"),
    [
        (date(2026, 8, 2), date(2026, 8, 1), "after"),
        (date(2025, 7, 31), date(2026, 8, 6), "371 days"),
    ],
)
def test_calendar_rejects_invalid_ranges(
    service: tuple[TokenUsageService, sessionmaker[Session]],
    start_date: date,
    end_date: date,
    message: str,
) -> None:
    usage_service, _ = service

    with pytest.raises(ApplicationError, match=message):
        usage_service.calendar(
            start_date=start_date,
            end_date=end_date,
            calendar_timezone=ZoneInfo("Asia/Shanghai"),
            timezone_name="Asia/Shanghai",
        )


@pytest.mark.parametrize(
    ("start_time", "end_time", "message"),
    [
        (
            datetime(2026, 7, 30, tzinfo=UTC),
            datetime(2026, 7, 30, tzinfo=UTC),
            "before",
        ),
        (
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 7, 30, tzinfo=UTC),
            "31 days",
        ),
        (
            datetime(2026, 7, 29),
            datetime(2026, 7, 30, tzinfo=UTC),
            "timezone",
        ),
    ],
)
def test_summary_rejects_invalid_ranges(
    service: tuple[TokenUsageService, sessionmaker[Session]],
    start_time: datetime,
    end_time: datetime,
    message: str,
) -> None:
    usage_service, _ = service

    with pytest.raises(ApplicationError, match=message):
        usage_service.summary(
            tool=None,
            start_time=start_time,
            end_time=end_time,
            timezone_offset_minutes=0,
        )


def test_failed_commit_does_not_persist_event_or_checkpoint(
    service: tuple[TokenUsageService, sessionmaker[Session]],
) -> None:
    usage_service, factory = service
    batch = TokenUsageBatchInput(
        events=[event()],
        next_cursor={"version": 1, "offset": 10},
    )

    with (
        patch.object(Session, "commit", side_effect=RuntimeError("commit failed")),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        usage_service.ingest(TokenUsageTool.CODEX, batch)

    with factory() as session:
        assert session.scalar(select(TokenUsageEventModel)) is None
        assert session.scalar(select(TokenUsageCheckpointModel)) is None
