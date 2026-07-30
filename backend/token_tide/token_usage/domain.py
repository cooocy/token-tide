from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class TokenUsageTool(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"


@dataclass(frozen=True)
class TokenUsageCheckpoint:
    tool: TokenUsageTool
    cursor: Mapping[str, object]


@dataclass(frozen=True)
class TokenUsageEvent:
    source_event_id: str
    tool: TokenUsageTool
    occurred_at: datetime
    reported_at: datetime
    model: str
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        token_fields = (
            self.input_tokens,
            self.output_tokens,
            self.cache_creation_tokens,
            self.cache_read_tokens,
            self.reasoning_tokens,
            self.total_tokens,
        )
        if any(value < 0 for value in token_fields):
            raise ValueError("token counts must not be negative")
