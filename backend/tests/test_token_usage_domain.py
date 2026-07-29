from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from token_tide.token_usage.domain import (
    TokenUsageCheckpoint,
    TokenUsageCollector,
    TokenUsageEvent,
    TokenUsageStream,
    TokenUsageTool,
)


def test_token_usage_tool_values_match_local_collectors() -> None:
    assert [tool.value for tool in TokenUsageTool] == [
        "claude",
        "codex",
        "opencode",
    ]


def test_token_usage_domain_types_are_immutable() -> None:
    collector = TokenUsageCollector(id="collector-1", name="MacBook")
    stream = TokenUsageStream(
        collector_id=collector.id,
        tool=TokenUsageTool.CODEX,
        stream_id="session-1",
    )
    checkpoint = TokenUsageCheckpoint(
        stream=stream,
        cursor={"offset": 10},
        revision=1,
    )

    with pytest.raises(FrozenInstanceError):
        checkpoint.revision = 2  # type: ignore[misc]


def test_token_usage_event_rejects_negative_counts() -> None:
    stream = TokenUsageStream(
        collector_id="collector-1",
        tool=TokenUsageTool.CLAUDE,
        stream_id="session-1",
    )

    with pytest.raises(ValueError, match="token counts"):
        TokenUsageEvent(
            source_event_id="event-1",
            stream=stream,
            occurred_at=datetime.now(UTC),
            model="claude-sonnet",
            input_tokens=-1,
        )


def test_token_usage_checkpoint_rejects_negative_revision() -> None:
    stream = TokenUsageStream(
        collector_id="collector-1",
        tool=TokenUsageTool.OPENCODE,
        stream_id="database-main",
    )

    with pytest.raises(ValueError, match="revision"):
        TokenUsageCheckpoint(stream=stream, cursor={}, revision=-1)
