from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
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
    TokenUsageCheckpointValue,
    TokenUsageEventInput,
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
