from datetime import UTC, datetime
from unittest.mock import patch

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
