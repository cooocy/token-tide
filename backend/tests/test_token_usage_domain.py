from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from token_tide.token_usage.domain import (
    TokenUsageCheckpoint,
    TokenUsageEvent,
    TokenUsageTool,
)


def test_token_usage_tool_values_match_local_collectors() -> None:
    assert [tool.value for tool in TokenUsageTool] == [
        "claude",
        "codex",
        "opencode",
        "pi",
    ]


def test_token_usage_domain_types_are_immutable() -> None:
    checkpoint = TokenUsageCheckpoint(
        tool=TokenUsageTool.CODEX,
        cursor={"offset": 10},
    )

    with pytest.raises(FrozenInstanceError):
        checkpoint.tool = TokenUsageTool.CLAUDE  # type: ignore[misc]


def test_token_usage_checkpoints_keep_independent_tool_cursors() -> None:
    claude_checkpoint = TokenUsageCheckpoint(
        tool=TokenUsageTool.CLAUDE,
        cursor={"file": "claude.jsonl", "offset": 10},
    )
    codex_checkpoint = TokenUsageCheckpoint(
        tool=TokenUsageTool.CODEX,
        cursor={"file": "codex.jsonl", "offset": 20},
    )

    assert claude_checkpoint.cursor["offset"] == 10
    assert codex_checkpoint.cursor["offset"] == 20


def test_token_usage_event_records_tool_and_reporting_time() -> None:
    occurred_at = datetime(2026, 7, 30, 1, 0, tzinfo=UTC)
    reported_at = datetime(2026, 7, 30, 1, 5, tzinfo=UTC)

    event = TokenUsageEvent(
        source_event_id="event-1",
        tool=TokenUsageTool.PI,
        occurred_at=occurred_at,
        reported_at=reported_at,
        model="glm-5",
    )

    assert event.tool is TokenUsageTool.PI
    assert event.occurred_at is occurred_at
    assert event.reported_at is reported_at


def test_token_usage_event_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="token counts"):
        TokenUsageEvent(
            source_event_id="event-1",
            tool=TokenUsageTool.CLAUDE,
            occurred_at=datetime.now(UTC),
            reported_at=datetime.now(UTC),
            model="claude-sonnet",
            input_tokens=-1,
        )
