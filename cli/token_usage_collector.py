#!/usr/bin/env python3
#
# Required:
#   TOKEN_TIDE_TOKEN_USAGE_TOKEN=<server token>
#   TOKEN_TIDE_BASE_URL=<API base URL>
#
# TOKEN_TIDE_BASE_URL can alternatively be passed as:
#   --base-url https://token-tide.example.com/api
#
# Optional:
#   --batch-size 500
#   --timeout-seconds 15
#   -v / --verbose  (show checkpoint, scan and per-batch details)
#   CLAUDE_CONFIG_DIR, CODEX_HOME, OPENCODE_DATA_DIR
#   PI_CODING_AGENT_DIR, PI_CODING_AGENT_SESSION_DIR
#
# Example:
#   TOKEN_TIDE_BASE_URL=https://token-tide.example.com/api \
#   TOKEN_TIDE_TOKEN_USAGE_TOKEN=secret \
#   python3 cli/token_usage_collector.py -v
#
"""Incrementally upload local coding-agent token usage to TokenTide."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Optional

TOOLS = ("claude", "codex", "opencode", "pi")
MAX_BATCH_SIZE = 500
CURSOR_VERSION = 1
SEMVER_PREFIX = re.compile(r"^\d+\.\d+\.\d+")


@dataclass(frozen=True)
class ScanResult:
    events: list[dict[str, object]]
    cursor: dict[str, object]


@dataclass(frozen=True)
class SyncResult:
    tool: str
    events: int
    batches: int
    created: int
    updated: int
    unchanged: int
    duration_seconds: float


def print_banner(lines: list[str], *, file: Any = sys.stderr) -> None:
    width = max(len(line) for line in lines) + 4
    top = "╭" + "─" * (width - 2) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    print(top, file=file)
    for line in lines:
        print(f"│  {line}{' ' * (width - len(line) - 4)}│", file=file)
    print(bottom, file=file)


def stable_hash(*values: object) -> str:
    encoded = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def utc_string(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def token_int(mapping: dict[str, Any], key: str) -> int:
    value = mapping.get(key, 0)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{key} must be a non-negative number")
    return int(value)


def output_invalid(
    tool: str,
    source: str,
    position: object,
    error: str,
    occurred_at: Optional[datetime] = None,
) -> None:
    print(
        json.dumps(
            {
                "tool": tool,
                "occurred_at": (
                    utc_string(occurred_at) if occurred_at is not None else None
                ),
                "source": source,
                "position": position,
                "error": error,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


def recursive_files(root: Path, suffix: str) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(candidate for candidate in root.rglob(f"*{suffix}") if candidate.is_file())


def file_key(file_path: Path) -> str:
    return stable_hash(str(file_path.resolve()))


def file_identity(file_path: Path) -> dict[str, int]:
    stat_result = file_path.stat()
    return {
        "device": stat_result.st_dev,
        "inode": stat_result.st_ino,
    }


def initial_offset(
    file_path: Path,
    state: dict[str, object],
) -> tuple[int, dict[str, int]]:
    identity = file_identity(file_path)
    saved_identity = state.get("identity")
    offset = state.get("offset", 0)
    if (
        saved_identity != identity
        or not isinstance(offset, int)
        or offset < 0
        or file_path.stat().st_size < offset
    ):
        return 0, identity
    return offset, identity


def complete_lines(file_path: Path, offset: int) -> tuple[list[tuple[int, bytes]], int]:
    lines: list[tuple[int, bytes]] = []
    with file_path.open("rb") as source:
        source.seek(offset)
        while True:
            position = source.tell()
            raw = source.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                try:
                    json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    break
            lines.append((position, raw))
            offset = source.tell()
    return lines, offset


def decode_json_line(
    tool: str,
    source: str,
    position: int,
    raw: bytes,
) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        output_invalid(
            tool,
            source,
            position,
            str(error),
        )
        return None
    if not isinstance(value, dict):
        output_invalid(tool, source, position, "record must be an object")
        return None
    return value


def event_value(
    source_event_id: str,
    occurred_at: datetime,
    model: str,
    *,
    provider: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    reasoning_tokens: int = 0,
    total_tokens: int = 0,
) -> dict[str, object]:
    return {
        "source_event_id": source_event_id,
        "occurred_at": utc_string(occurred_at),
        "reported_at": utc_string(datetime.now(UTC)),
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation_tokens,
        "cache_read_tokens": cache_read_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def cursor_files(cursor: dict[str, object]) -> dict[str, dict[str, object]]:
    if cursor.get("version") != CURSOR_VERSION:
        return {}
    files = cursor.get("files")
    if not isinstance(files, dict):
        return {}
    return {
        str(key): value
        for key, value in files.items()
        if isinstance(value, dict)
    }


def claude_config_paths() -> list[Path]:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    if configured is not None:
        roots = []
        for raw in configured.split(","):
            if not raw.strip():
                continue
            root = expand_path(raw.strip())
            if root.name == "projects":
                root = root.parent
            if (root / "projects").is_dir() and root not in roots:
                roots.append(root)
        if not roots:
            raise RuntimeError("CLAUDE_CONFIG_DIR has no directory containing projects/")
        return roots
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [
        root
        for root in (xdg / "claude", home / ".claude")
        if (root / "projects").is_dir()
    ]


def unwrap_claude(raw: dict[str, Any]) -> dict[str, Any]:
    nested = raw.get("data")
    if isinstance(nested, dict):
        progress = nested.get("message")
        if isinstance(progress, dict) and isinstance(progress.get("message"), dict):
            return progress
    return raw


def claude_event(
    raw: dict[str, Any],
    source: str,
    position: int,
) -> Optional[tuple[dict[str, object], tuple[int, int]]]:
    entry = unwrap_claude(raw)
    message = entry.get("message")
    if not isinstance(message, dict) or "usage" not in message:
        return None
    occurred_at = parse_timestamp(entry.get("timestamp"))
    try:
        usage = message["usage"]
        if not isinstance(usage, dict):
            raise ValueError("usage must be an object")
        version = entry.get("version")
        if isinstance(version, str) and not SEMVER_PREFIX.match(version):
            raise ValueError("unsupported version")
        model = message.get("model")
        if occurred_at is None:
            raise ValueError("timestamp must include timezone")
        if not isinstance(model, str) or not model or model == "<synthetic>":
            raise ValueError("model is missing or synthetic")
        cache_detail = usage.get("cache_creation")
        if isinstance(cache_detail, dict):
            cache_creation = token_int(
                cache_detail,
                "ephemeral_5m_input_tokens",
            ) + token_int(cache_detail, "ephemeral_1h_input_tokens")
        else:
            cache_creation = token_int(usage, "cache_creation_input_tokens")
        input_tokens = token_int(usage, "input_tokens")
        output_tokens = token_int(usage, "output_tokens")
        cache_read = token_int(usage, "cache_read_input_tokens")
        message_id = message.get("id")
        identity = (
            ("message", message_id)
            if isinstance(message_id, str) and message_id
            else ("fallback", source, position, raw)
        )
        event = event_value(
            stable_hash("claude", identity),
            occurred_at,
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            total_tokens=input_tokens + output_tokens + cache_creation + cache_read,
        )
        rank = (
            0 if entry.get("isSidechain") is True else 1,
            int(event["total_tokens"]),
        )
        return event, rank
    except (TypeError, ValueError) as error:
        output_invalid(
            "claude",
            source,
            position,
            str(error),
            occurred_at,
        )
        return None


def scan_claude(cursor: dict[str, object]) -> ScanResult:
    previous_files = cursor_files(cursor)
    next_files = dict(previous_files)
    preferred: dict[str, tuple[dict[str, object], tuple[int, int]]] = {}
    for file_path in [
        candidate
        for root in claude_config_paths()
        for candidate in recursive_files(root / "projects", ".jsonl")
    ]:
        key = file_key(file_path)
        state = previous_files.get(key, {})
        offset, identity = initial_offset(file_path, state)
        lines, next_offset = complete_lines(file_path, offset)
        for position, raw_bytes in lines:
            raw = decode_json_line("claude", key, position, raw_bytes)
            if raw is None:
                continue
            candidate = claude_event(raw, key, position)
            if candidate is None:
                continue
            event, rank = candidate
            source_id = str(event["source_event_id"])
            current = preferred.get(source_id)
            if current is None or rank > current[1]:
                preferred[source_id] = (event, rank)
        next_files[key] = {"identity": identity, "offset": next_offset}
    return ScanResult(
        events=[value[0] for value in preferred.values()],
        cursor={"version": CURSOR_VERSION, "files": next_files},
    )


def codex_home_paths() -> list[Path]:
    configured = os.environ.get("CODEX_HOME")
    if configured is None:
        return [Path.home() / ".codex"]
    return [expand_path(raw.strip()) for raw in configured.split(",") if raw.strip()]


def codex_files() -> list[Path]:
    files: list[Path] = []
    seen: set[tuple[Path, Path]] = set()
    for home in codex_home_paths():
        roots = [
            root
            for root in (home / "sessions", home / "archived_sessions")
            if root.is_dir()
        ] or [home]
        for root in roots:
            for file_path in recursive_files(root, ".jsonl"):
                relative = file_path.relative_to(root)
                identity = (home.resolve(), relative)
                if identity not in seen:
                    seen.add(identity)
                    files.append(file_path)
    return sorted(files)


def numeric_usage(raw: dict[str, Any]) -> dict[str, int]:
    return {
        key: token_int(raw, key)
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
        )
    }


def subtract_usage(
    current: dict[str, int],
    previous: dict[str, int],
) -> dict[str, int]:
    return {key: max(0, value - previous.get(key, 0)) for key, value in current.items()}


def scan_codex(cursor: dict[str, object]) -> ScanResult:
    previous_files = cursor_files(cursor)
    next_files = dict(previous_files)
    events: list[dict[str, object]] = []
    for file_path in codex_files():
        key = file_key(file_path)
        state = previous_files.get(key, {})
        offset, identity = initial_offset(file_path, state)
        reset = offset == 0
        model = "" if reset else str(state.get("model") or "")
        session_id = "" if reset else str(state.get("session_id") or "")
        event_index = 0 if reset else int(state.get("event_index") or 0)
        saved_totals = state.get("previous_totals")
        previous_totals = (
            {
                str(name): int(value)
                for name, value in saved_totals.items()
                if isinstance(value, int)
            }
            if not reset and isinstance(saved_totals, dict)
            else {}
        )
        lines, next_offset = complete_lines(file_path, offset)
        for position, raw_bytes in lines:
            raw = decode_json_line("codex", key, position, raw_bytes)
            if raw is None:
                continue
            payload = raw.get("payload")
            if not isinstance(payload, dict):
                continue
            raw_type = raw.get("type")
            if raw_type == "session_meta":
                candidate_id = payload.get("id")
                if isinstance(candidate_id, str) and candidate_id:
                    session_id = candidate_id
                continue
            if raw_type == "turn_context":
                candidate_model = payload.get("model") or payload.get("model_name")
                if isinstance(candidate_model, str) and candidate_model:
                    model = candidate_model
                continue
            if raw_type != "event_msg" or payload.get("type") != "token_count":
                continue
            event_index += 1
            try:
                occurred_at = parse_timestamp(raw.get("timestamp"))
                info = payload.get("info")
                if occurred_at is None or not isinstance(info, dict):
                    raise ValueError("token_count requires timestamp and info")
                total_raw = info.get("total_token_usage")
                total_usage = numeric_usage(total_raw) if isinstance(total_raw, dict) else {}
                last_raw = info.get("last_token_usage")
                if isinstance(last_raw, dict):
                    usage = numeric_usage(last_raw)
                elif total_usage:
                    usage = subtract_usage(total_usage, previous_totals)
                else:
                    raise ValueError("token_count has no usage object")
                if total_usage:
                    previous_totals = total_usage
                candidate_model = (
                    payload.get("model")
                    or payload.get("model_name")
                    or info.get("model")
                )
                if isinstance(candidate_model, str) and candidate_model:
                    model = candidate_model
                raw_input = usage["input_tokens"]
                cached = min(usage["cached_input_tokens"], raw_input)
                output = usage["output_tokens"]
                reasoning = usage["reasoning_output_tokens"]
                total = usage["total_tokens"] or raw_input + output
                if raw_input == 0 and output == 0 and reasoning == 0:
                    continue
                logical_session = session_id or file_path.stem
                events.append(
                    event_value(
                        stable_hash("codex", logical_session, event_index),
                        occurred_at,
                        model or "gpt-5",
                        input_tokens=raw_input - cached,
                        output_tokens=output,
                        cache_read_tokens=cached,
                        reasoning_tokens=reasoning,
                        total_tokens=total,
                    )
                )
            except (TypeError, ValueError) as error:
                output_invalid(
                    "codex",
                    key,
                    position,
                    str(error),
                    parse_timestamp(raw.get("timestamp")),
                )
        next_files[key] = {
            "identity": identity,
            "offset": next_offset,
            "model": model,
            "session_id": session_id,
            "event_index": event_index,
            "previous_totals": previous_totals,
        }
    return ScanResult(
        events=events,
        cursor={"version": CURSOR_VERSION, "files": next_files},
    )


def pi_agent_dir() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_DIR")
    return expand_path(configured) if configured else Path.home() / ".pi" / "agent"


def pi_session_dir() -> Path:
    configured = os.environ.get("PI_CODING_AGENT_SESSION_DIR")
    if configured:
        return expand_path(configured)

    agent_dir = pi_agent_dir()
    settings_path = agent_dir / "settings.json"
    if not settings_path.is_file():
        return agent_dir / "sessions"
    try:
        settings = json.loads(settings_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Unable to read Pi settings {settings_path}: {error}") from error
    if not isinstance(settings, dict):
        raise RuntimeError(f"Pi settings must be an object: {settings_path}")
    session_dir = settings.get("sessionDir")
    if session_dir is None:
        return agent_dir / "sessions"
    if not isinstance(session_dir, str) or not session_dir.strip():
        raise RuntimeError(f"Pi sessionDir must be a non-empty string: {settings_path}")
    expanded = Path(os.path.expanduser(session_dir.strip()))
    if not expanded.is_absolute():
        expanded = agent_dir / expanded
    return expanded.resolve()


def pi_usage(raw: object) -> dict[str, int]:
    if not isinstance(raw, dict):
        raise ValueError("usage must be an object")
    input_tokens = token_int(raw, "input")
    output_tokens = token_int(raw, "output")
    cache_creation = token_int(raw, "cacheWrite")
    cache_read = token_int(raw, "cacheRead")
    known = input_tokens + output_tokens + cache_creation + cache_read
    total = token_int(raw, "totalTokens") or known
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation,
        "cache_read_tokens": cache_read,
        "total_tokens": total,
    }


def pi_event(
    raw: dict[str, Any],
    source: str,
    position: int,
    current_provider: str,
    current_model: str,
) -> Optional[dict[str, object]]:
    raw_type = raw.get("type")
    message = raw.get("message") if raw_type == "message" else None
    role = message.get("role") if isinstance(message, dict) else None
    if role == "assistant":
        usage_raw = message.get("usage")
        provider = message.get("provider")
        model = message.get("model")
    elif role == "toolResult" and isinstance(message, dict) and "usage" in message:
        usage_raw = message.get("usage")
        details = message.get("details")
        details = details if isinstance(details, dict) else {}
        provider_value = message.get("provider") or details.get("provider")
        model_value = message.get("model") or details.get("model")
        provider = provider_value if isinstance(provider_value, str) else ""
        model = model_value if isinstance(model_value, str) and model_value else "pi-internal"
    elif raw_type in ("compaction", "branch_summary") and "usage" in raw:
        usage_raw = raw.get("usage")
        provider = current_provider
        model = current_model or "pi-internal"
    else:
        return None

    occurred_at = parse_timestamp(raw.get("timestamp"))
    try:
        if occurred_at is None:
            raise ValueError("timestamp must include timezone")
        if not isinstance(provider, str):
            raise ValueError("provider must be a string")
        if not isinstance(model, str) or not model:
            raise ValueError("model is required")
        usage = pi_usage(usage_raw)
        if usage["total_tokens"] == 0:
            return None
        message_timestamp = message.get("timestamp") if isinstance(message, dict) else None
        tool_call_id = message.get("toolCallId") if isinstance(message, dict) else None
        response_id = message.get("responseId") if isinstance(message, dict) else None
        return event_value(
            stable_hash(
                "pi",
                raw.get("timestamp"),
                raw_type,
                role,
                message_timestamp,
                tool_call_id,
                response_id,
                raw.get("summary"),
                provider,
                model,
                usage,
            ),
            occurred_at,
            model,
            provider=provider,
            **usage,
        )
    except (TypeError, ValueError) as error:
        output_invalid(
            "pi",
            source,
            position,
            str(error),
            occurred_at,
        )
        return None


def scan_pi(cursor: dict[str, object]) -> ScanResult:
    previous_files = cursor_files(cursor)
    next_files = dict(previous_files)
    events: dict[str, dict[str, object]] = {}
    for file_path in recursive_files(pi_session_dir(), ".jsonl"):
        key = file_key(file_path)
        state = previous_files.get(key, {})
        offset, identity = initial_offset(file_path, state)
        reset = offset == 0
        current_provider = "" if reset else str(state.get("provider") or "")
        current_model = "" if reset else str(state.get("model") or "")
        lines, next_offset = complete_lines(file_path, offset)
        for position, raw_bytes in lines:
            raw = decode_json_line("pi", key, position, raw_bytes)
            if raw is None:
                continue
            raw_type = raw.get("type")
            if raw_type == "model_change":
                provider = raw.get("provider")
                model = raw.get("modelId")
                if isinstance(provider, str) and provider:
                    current_provider = provider
                if isinstance(model, str) and model:
                    current_model = model
                continue
            message = raw.get("message")
            if (
                raw_type == "message"
                and isinstance(message, dict)
                and message.get("role") == "assistant"
            ):
                provider = message.get("provider")
                model = message.get("model")
                if isinstance(provider, str) and provider:
                    current_provider = provider
                if isinstance(model, str) and model:
                    current_model = model
            event = pi_event(
                raw,
                key,
                position,
                current_provider,
                current_model,
            )
            if event is not None:
                events[str(event["source_event_id"])] = event
        next_files[key] = {
            "identity": identity,
            "offset": next_offset,
            "provider": current_provider,
            "model": current_model,
        }
    return ScanResult(
        events=list(events.values()),
        cursor={"version": CURSOR_VERSION, "files": next_files},
    )


def opencode_paths() -> list[Path]:
    configured = os.environ.get("OPENCODE_DATA_DIR")
    if configured is not None:
        return [expand_path(raw.strip()) for raw in configured.split(",") if raw.strip()]
    return [Path.home() / ".local" / "share" / "opencode"]


def opencode_db_path(root: Path) -> Optional[Path]:
    default = root / "opencode.db"
    if default.is_file():
        return default
    candidates = sorted(
        candidate
        for candidate in root.glob("opencode-*.db")
        if re.fullmatch(r"opencode-[A-Za-z0-9_-]+\.db", candidate.name)
    )
    return candidates[0] if candidates else None


def opencode_event(
    raw: dict[str, Any],
    message_id: str,
    source: str,
    position: object,
) -> Optional[dict[str, object]]:
    if raw.get("role") not in (None, "assistant"):
        return None
    occurred_at: Optional[datetime] = None
    try:
        tokens = raw.get("tokens")
        model = raw.get("modelID")
        provider = raw.get("providerID")
        time_value = raw.get("time")
        created = time_value.get("created") if isinstance(time_value, dict) else None
        if not isinstance(tokens, dict):
            raise ValueError("tokens must be an object")
        if not isinstance(model, str) or not model:
            raise ValueError("modelID is required")
        if not isinstance(created, (int, float)):
            raise ValueError("time.created is required")
        occurred_at = datetime.fromtimestamp(created / 1000, tz=UTC)
        cache = tokens.get("cache")
        cache = cache if isinstance(cache, dict) else {}
        input_tokens = token_int(tokens, "input")
        raw_output = token_int(tokens, "output")
        cache_creation = token_int(cache, "write")
        cache_read = token_int(cache, "read")
        reasoning = token_int(tokens, "reasoning")
        known = input_tokens + raw_output + cache_creation + cache_read
        total = token_int(tokens, "total") or known
        if total == 0:
            return None
        return event_value(
            stable_hash("opencode", message_id),
            occurred_at,
            model,
            provider=provider if isinstance(provider, str) else "",
            input_tokens=input_tokens,
            output_tokens=raw_output + max(0, total - known),
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            reasoning_tokens=reasoning,
            total_tokens=total,
        )
    except (OSError, OverflowError, TypeError, ValueError) as error:
        output_invalid(
            "opencode",
            source,
            position,
            str(error),
            occurred_at,
        )
        return None


def scan_opencode(cursor: dict[str, object]) -> ScanResult:
    previous_databases = (
        cursor.get("databases")
        if cursor.get("version") == CURSOR_VERSION
        and isinstance(cursor.get("databases"), dict)
        else {}
    )
    previous_files = cursor_files(cursor)
    next_databases = dict(previous_databases)
    next_files = dict(previous_files)
    events: dict[str, dict[str, object]] = {}
    for root in opencode_paths():
        database = opencode_db_path(root)
        if database is not None:
            key = file_key(database)
            state = previous_databases.get(key)
            identity = file_identity(database)
            watermark = (
                int(state.get("time_updated", -1))
                if isinstance(state, dict) and state.get("identity") == identity
                else -1
            )
            maximum = watermark
            try:
                uri = f"file:{database}?mode=ro"
                with sqlite3.connect(uri, uri=True) as connection:
                    current_maximum = connection.execute(
                        "SELECT MAX(time_updated) FROM message"
                    ).fetchone()[0]
                    if current_maximum is not None and int(current_maximum) < watermark:
                        watermark = -1
                        maximum = -1
                    rows = connection.execute(
                        """
                        SELECT id, time_updated, data
                        FROM message
                        WHERE time_updated >= ?
                        ORDER BY time_updated, id
                        """,
                        (watermark,),
                    )
                    for message_id, time_updated, data in rows:
                        maximum = max(maximum, int(time_updated))
                        try:
                            raw = json.loads(data)
                        except (TypeError, json.JSONDecodeError) as error:
                            output_invalid(
                                "opencode",
                                key,
                                message_id,
                                str(error),
                            )
                            continue
                        if not isinstance(raw, dict):
                            output_invalid(
                                "opencode",
                                key,
                                message_id,
                                "record must be an object",
                            )
                            continue
                        event = opencode_event(raw, str(message_id), key, message_id)
                        if event is not None:
                            events[str(event["source_event_id"])] = event
            except sqlite3.Error as error:
                raise RuntimeError(
                    f"Unable to read OpenCode database {database}: {error}"
                ) from error
            next_databases[key] = {
                "identity": identity,
                "time_updated": maximum,
            }
            continue

        for file_path in recursive_files(root / "storage" / "message", ".json"):
            key = file_key(file_path)
            raw_bytes = file_path.read_bytes()
            fingerprint = hashlib.sha256(raw_bytes).hexdigest()
            state = previous_files.get(key, {})
            if state.get("fingerprint") == fingerprint:
                continue
            try:
                raw = json.loads(raw_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                output_invalid(
                    "opencode",
                    key,
                    0,
                    str(error),
                )
            else:
                if isinstance(raw, dict):
                    message_id = raw.get("id")
                    if not isinstance(message_id, str) or not message_id:
                        message_id = file_path.stem
                    event = opencode_event(raw, message_id, key, 0)
                    if event is not None:
                        events[str(event["source_event_id"])] = event
                else:
                    output_invalid(
                        "opencode",
                        key,
                        0,
                        "record must be an object",
                    )
            stat_result = file_path.stat()
            next_files[key] = {
                "identity": file_identity(file_path),
                "size": stat_result.st_size,
                "mtime_ns": stat_result.st_mtime_ns,
                "fingerprint": fingerprint,
            }
    return ScanResult(
        events=list(events.values()),
        cursor={
            "version": CURSOR_VERSION,
            "databases": next_databases,
            "files": next_files,
        },
    )


class TokenTideClient:
    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def checkpoint(self, tool: str) -> dict[str, object]:
        data = self._request("GET", f"/token-usage/{tool}/checkpoint")
        cursor = data.get("cursor")
        if not isinstance(cursor, dict):
            raise RuntimeError(f"Server returned an invalid {tool} cursor")
        return cursor

    def submit(
        self,
        tool: str,
        events: list[dict[str, object]],
        cursor: dict[str, object],
    ) -> dict[str, object]:
        return self._request(
            "POST",
            f"/token-usage/{tool}/events/batch",
            {"events": events, "next_cursor": cursor},
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        body: Optional[dict[str, object]] = None,
    ) -> dict[str, object]:
        encoded = (
            json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
            if body is not None
            else None
        )
        request = urllib.request.Request(
            self.base_url + endpoint,
            data=encoded,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.token}",
                **({"Content-Type": "application/json"} if encoded is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"TokenTide HTTP {error.code}: {detail}") from error
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise RuntimeError(f"TokenTide request failed: {error}") from error
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise RuntimeError("TokenTide returned an unsuccessful response")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("TokenTide response has no data object")
        return data


def sync_tool(
    client: TokenTideClient,
    tool: str,
    scanner: Callable[[dict[str, object]], ScanResult],
    batch_size: int,
) -> SyncResult:
    started_at = time.monotonic()
    print(f"▶  {tool}", file=sys.stderr)
    previous_cursor = client.checkpoint(tool)
    result = scanner(previous_cursor)
    if not result.events and result.cursor == previous_cursor:
        duration = time.monotonic() - started_at
        print(f"◀  {tool}  no changes  ⏱ {duration:.2f}s", file=sys.stderr)
        return SyncResult(tool, 0, 0, 0, 0, 0, duration)
    batches = [
        result.events[index : index + batch_size]
        for index in range(0, len(result.events), batch_size)
    ]
    if not batches:
        batches = [[]]
    created = updated = unchanged = 0
    for index, batch in enumerate(batches):
        final = index == len(batches) - 1
        try:
            response = client.submit(
                tool,
                batch,
                result.cursor if final else previous_cursor,
            )
        except RuntimeError as error:
            raise RuntimeError(
                f"batch={index + 1}/{len(batches)} failed: {error}"
            ) from error
        counts: dict[str, int] = {}
        for name in ("created", "updated", "unchanged"):
            value = response.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise RuntimeError(f"Server returned an invalid {name} count")
            counts[name] = value
        created += counts["created"]
        updated += counts["updated"]
        unchanged += counts["unchanged"]
    duration = time.monotonic() - started_at
    parts = [
        f"events={len(result.events)}",
        f"batches={len(batches)}",
        f"created={created}",
        f"updated={updated}",
        f"unchanged={unchanged}",
    ]
    print(f"◀  {tool}  {'  '.join(parts)}  ⏱ {duration:.2f}s", file=sys.stderr)
    return SyncResult(
        tool=tool,
        events=len(result.events),
        batches=len(batches),
        created=created,
        updated=updated,
        unchanged=unchanged,
        duration_seconds=duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally upload Claude, Codex, OpenCode and Pi token usage",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("TOKEN_TIDE_BASE_URL"),
        help="TokenTide API base URL (or TOKEN_TIDE_BASE_URL)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=MAX_BATCH_SIZE,
        help=f"events per request, 1-{MAX_BATCH_SIZE}",
    )
    parser.add_argument("--timeout-seconds", type=float, default=15)
    args = parser.parse_args()
    token = os.environ.get("TOKEN_TIDE_TOKEN_USAGE_TOKEN")
    if not args.base_url:
        parser.error("--base-url or TOKEN_TIDE_BASE_URL is required")
    if not token:
        parser.error("TOKEN_TIDE_TOKEN_USAGE_TOKEN is required")
    if not 1 <= args.batch_size <= MAX_BATCH_SIZE:
        parser.error(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")

    started_at = time.monotonic()
    print_banner([
        "󰓦  TokenTide Sync Started",
        f"Tools: {', '.join(TOOLS)}",
    ])
    client = TokenTideClient(args.base_url, token, args.timeout_seconds)
    scanners: dict[str, Callable[[dict[str, object]], ScanResult]] = {
        "claude": scan_claude,
        "codex": scan_codex,
        "opencode": scan_opencode,
        "pi": scan_pi,
    }
    failures: list[str] = []
    results: list[SyncResult] = []
    for tool in TOOLS:
        try:
            results.append(
                sync_tool(
                    client,
                    tool,
                    scanners[tool],
                    args.batch_size,
                )
            )
        except (OSError, RuntimeError, sqlite3.Error) as error:
            failures.append(tool)
            print(f"✖  {tool}  sync failed: {error}", file=sys.stderr)
    duration = time.monotonic() - started_at
    totals = {
        field: sum(getattr(result, field) for result in results)
        for field in ("events", "batches", "created", "updated", "unchanged")
    }
    icon = "󰅙" if failures else "󰗠"
    banner_lines = [
        f"{icon}  TokenTide Sync Completed",
        f"󰄬 Succeeded: {len(results)}  󰅖 Failed: {len(failures)}",
        f"Events: {totals['events']}  Batches: {totals['batches']}",
        f"Created: {totals['created']}  Updated: {totals['updated']}  Unchanged: {totals['unchanged']}",
        f"⏱ Duration: {duration:.2f}s",
    ]
    if failures:
        banner_lines.insert(2, f"Failed: {', '.join(failures)}")
    print_banner(banner_lines)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
