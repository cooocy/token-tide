import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cli.token_usage_collector import (
    ScanResult,
    scan_claude,
    scan_codex,
    scan_opencode,
    scan_pi,
    sync_tool,
)


def json_line(value: object) -> str:
    return json.dumps(value, separators=(",", ":")) + "\n"


class TokenUsageCollectorTest(unittest.TestCase):
    def test_default_logging_shows_result_without_verbose_stages(self) -> None:
        class Client:
            @staticmethod
            def checkpoint(_tool: str) -> dict[str, object]:
                return {"version": 1}

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = sync_tool(
                Client(),  # type: ignore[arg-type]
                "claude",
                lambda cursor: ScanResult(events=[], cursor=cursor),
                batch_size=500,
                verbose=False,
            )

        output = stderr.getvalue()
        self.assertEqual(result.events, 0)
        self.assertIn("[claude] sync started", output)
        self.assertIn("[claude] no changes", output)
        self.assertNotIn("fetching checkpoint", output)
        self.assertNotIn("scanning local data", output)

    def test_only_final_batch_advances_cursor(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.submissions: list[tuple[list[dict[str, object]], dict[str, object]]] = []

            def checkpoint(self, _tool: str) -> dict[str, object]:
                return {"version": 1, "offset": 10}

            def submit(
                self,
                _tool: str,
                events: list[dict[str, object]],
                cursor: dict[str, object],
            ) -> dict[str, object]:
                self.submissions.append((events, cursor))
                return {
                    "created": len(events),
                    "updated": 0,
                    "unchanged": 0,
                }

        client = Client()
        events = [{"source_event_id": str(index)} for index in range(3)]

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = sync_tool(
                client,  # type: ignore[arg-type]
                "codex",
                lambda _cursor: ScanResult(
                    events=events,
                    cursor={"version": 1, "offset": 20},
                ),
                batch_size=2,
                verbose=True,
            )

        self.assertEqual(client.submissions[0][1]["offset"], 10)
        self.assertEqual(client.submissions[1][1]["offset"], 20)
        self.assertEqual(result.created, 3)
        self.assertIn("uploading batch=1/2", stderr.getvalue())
        self.assertIn("sync completed events=3", stderr.getvalue())

    def test_claude_resumes_offset_and_outputs_invalid_complete_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            projects = root / "projects" / "project"
            projects.mkdir(parents=True)
            log = projects / "session.jsonl"
            first = self.claude_record("message-1", "2026-07-30T01:00:00Z")
            log.write_text(json_line(first), encoding="utf-8")

            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(root)}):
                initial = scan_claude({})
                unchanged = scan_claude(initial.cursor)
                with log.open("a", encoding="utf-8") as output:
                    output.write("{invalid}\n")
                    output.write(
                        json_line(
                            {
                                "timestamp": "2026-07-30T01:30:00Z",
                                "message": {"usage": "invalid"},
                            }
                        )
                    )
                    output.write(
                        json_line(
                            self.claude_record(
                                "message-2",
                                "2026-07-30T02:00:00Z",
                            )
                        )
                    )
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    appended = scan_claude(initial.cursor)

            self.assertEqual(len(initial.events), 1)
            self.assertEqual(unchanged.events, [])
            self.assertEqual(len(appended.events), 1)
            invalid = [
                json.loads(line)
                for line in stdout.getvalue().splitlines()
            ]
            self.assertEqual(invalid[0]["occurred_at"], None)
            self.assertEqual(
                invalid[1]["occurred_at"],
                "2026-07-30T01:30:00Z",
            )
            self.assertNotIn("raw", invalid[0])
            self.assertNotIn("raw", invalid[1])

    def test_codex_restores_cumulative_usage_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            sessions = home / "sessions"
            sessions.mkdir()
            log = sessions / "session.jsonl"
            log.write_text(
                json_line({"type": "session_meta", "payload": {"id": "session-1"}})
                + json_line(
                    {
                        "type": "turn_context",
                        "payload": {"model": "gpt-5"},
                    }
                )
                + json_line(self.codex_total(10, 4, 14, "2026-07-30T01:00:00Z")),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
                initial = scan_codex({})
                with log.open("a", encoding="utf-8") as output:
                    output.write(
                        json_line(
                            self.codex_total(
                                18,
                                7,
                                25,
                                "2026-07-30T02:00:00Z",
                            )
                        )
                    )
                appended = scan_codex(initial.cursor)

            self.assertEqual(initial.events[0]["total_tokens"], 14)
            self.assertEqual(appended.events[0]["input_tokens"], 8)
            self.assertEqual(appended.events[0]["output_tokens"], 3)
            self.assertEqual(appended.events[0]["total_tokens"], 11)

    def test_opencode_reloads_message_updated_at_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "opencode.db"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    """
                    CREATE TABLE message (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        time_created INTEGER NOT NULL,
                        time_updated INTEGER NOT NULL,
                        data TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO message VALUES (?, ?, ?, ?, ?)",
                    (
                        "message-1",
                        "session-1",
                        1,
                        10,
                        json.dumps(self.opencode_record(5)),
                    ),
                )
                connection.commit()

            with patch.dict(os.environ, {"OPENCODE_DATA_DIR": str(root)}):
                initial = scan_opencode({})
                with sqlite3.connect(database) as connection:
                    connection.execute(
                        "UPDATE message SET time_updated = ?, data = ? WHERE id = ?",
                        (20, json.dumps(self.opencode_record(8)), "message-1"),
                    )
                    connection.commit()
                updated = scan_opencode(initial.cursor)

            self.assertEqual(initial.events[0]["output_tokens"], 5)
            self.assertEqual(updated.events[0]["output_tokens"], 8)
            self.assertEqual(
                initial.events[0]["source_event_id"],
                updated.events[0]["source_event_id"],
            )

    def test_pi_collects_all_usage_types_and_deduplicates_cloned_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            entries = [
                {
                    "type": "session",
                    "version": 3,
                    "id": "session-1",
                    "timestamp": "2026-08-01T01:00:00Z",
                    "cwd": "/project",
                },
                {
                    "type": "model_change",
                    "id": "model-1",
                    "parentId": None,
                    "timestamp": "2026-08-01T01:00:01Z",
                    "provider": "anthropic",
                    "modelId": "claude-sonnet-4",
                },
                self.pi_assistant("assistant-1"),
                {
                    "type": "compaction",
                    "id": "compaction-1",
                    "parentId": "assistant-1",
                    "timestamp": "2026-08-01T01:02:00Z",
                    "summary": "summary",
                    "usage": self.pi_usage(2, 1, 0, 0),
                },
                {
                    "type": "message",
                    "id": "tool-1",
                    "parentId": "compaction-1",
                    "timestamp": "2026-08-01T01:03:00Z",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": "call-1",
                        "toolName": "subagent",
                        "content": [],
                        "isError": False,
                        "usage": self.pi_usage(3, 2, 0, 0),
                    },
                },
                {
                    "type": "message",
                    "id": "tool-2",
                    "parentId": "tool-1",
                    "timestamp": "2026-08-01T01:04:00Z",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": "call-2",
                        "toolName": "subagent",
                        "content": [],
                        "isError": False,
                        "details": {"provider": "openai", "model": "gpt-5"},
                        "usage": self.pi_usage(4, 2, 0, 0),
                    },
                },
            ]
            original = sessions / "original.jsonl"
            clone = sessions / "clone.jsonl"
            original.write_text("".join(json_line(entry) for entry in entries), encoding="utf-8")
            cloned_entries = [
                {**entries[0], "id": "session-2", "parentSession": str(original)},
                *entries[1:],
            ]
            clone.write_text(
                "".join(json_line(entry) for entry in cloned_entries),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {"PI_CODING_AGENT_SESSION_DIR": str(sessions)},
            ):
                result = scan_pi({})

            self.assertEqual(len(result.events), 4)
            assistant = next(
                event
                for event in result.events
                if event["model"] == "claude-sonnet-4"
                and event["total_tokens"] == 20
            )
            self.assertEqual(assistant["provider"], "anthropic")
            self.assertEqual(assistant["input_tokens"], 10)
            self.assertEqual(assistant["output_tokens"], 5)
            self.assertEqual(assistant["cache_creation_tokens"], 2)
            self.assertEqual(assistant["cache_read_tokens"], 3)
            self.assertEqual(assistant["total_tokens"], 20)
            events = {event["model"]: event for event in result.events}
            self.assertEqual(events["pi-internal"]["total_tokens"], 5)
            self.assertEqual(events["gpt-5"]["provider"], "openai")
            summary_events = [
                event
                for event in result.events
                if event["model"] == "claude-sonnet-4"
                and event["total_tokens"] == 3
            ]
            self.assertEqual(len(summary_events), 1)

    def test_pi_resumes_offset_and_uses_settings_session_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            agent_dir = Path(temporary) / "agent"
            sessions = agent_dir / "custom-sessions" / "project"
            sessions.mkdir(parents=True)
            (agent_dir / "settings.json").write_text(
                json.dumps({"sessionDir": "custom-sessions"}),
                encoding="utf-8",
            )
            log = sessions / "session.jsonl"
            legacy_assistant = self.pi_assistant("assistant-1")
            legacy_assistant.pop("id")
            legacy_assistant.pop("parentId")
            log.write_text(json_line(legacy_assistant), encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "PI_CODING_AGENT_DIR": str(agent_dir),
                    "PI_CODING_AGENT_SESSION_DIR": "",
                },
            ):
                initial = scan_pi({})
                unchanged = scan_pi(initial.cursor)
                with log.open("a", encoding="utf-8") as output:
                    next_assistant = self.pi_assistant("assistant-2")
                    next_assistant["timestamp"] = "2026-08-01T01:05:00Z"
                    output.write(json_line(next_assistant))
                appended = scan_pi(initial.cursor)

            self.assertEqual(len(initial.events), 1)
            self.assertEqual(unchanged.events, [])
            self.assertEqual(len(appended.events), 1)

    def test_pi_skips_zero_usage_and_reports_invalid_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sessions = Path(temporary)
            zero = self.pi_assistant("assistant-zero")
            zero["message"]["usage"] = self.pi_usage(0, 0, 0, 0)  # type: ignore[index]
            invalid = self.pi_assistant("assistant-invalid")
            invalid["timestamp"] = "2026-08-01T01:06:00Z"
            invalid["message"]["usage"] = {"input": -1}  # type: ignore[index]
            (sessions / "session.jsonl").write_text(
                json_line(zero) + json_line(invalid),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with (
                patch.dict(
                    os.environ,
                    {"PI_CODING_AGENT_SESSION_DIR": str(sessions)},
                ),
                redirect_stdout(stdout),
            ):
                result = scan_pi({})

            self.assertEqual(result.events, [])
            errors = [json.loads(line) for line in stdout.getvalue().splitlines()]
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["tool"], "pi")
            self.assertNotIn("raw", errors[0])

    @staticmethod
    def claude_record(message_id: str, timestamp: str) -> dict[str, object]:
        return {
            "timestamp": timestamp,
            "requestId": f"request-{message_id}",
            "message": {
                "id": message_id,
                "model": "claude-sonnet",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        }

    @staticmethod
    def codex_total(
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        timestamp: str,
    ) -> dict[str, object]:
        return {
            "type": "event_msg",
            "timestamp": timestamp,
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": input_tokens,
                        "cached_input_tokens": 0,
                        "output_tokens": output_tokens,
                        "reasoning_output_tokens": 0,
                        "total_tokens": total_tokens,
                    }
                },
            },
        }

    @staticmethod
    def opencode_record(output_tokens: int) -> dict[str, object]:
        return {
            "role": "assistant",
            "modelID": "glm-5",
            "providerID": "zai",
            "time": {"created": 1785373200000},
            "tokens": {
                "input": 10,
                "output": output_tokens,
                "reasoning": 0,
                "total": 10 + output_tokens,
                "cache": {"write": 0, "read": 0},
            },
        }

    @staticmethod
    def pi_usage(
        input_tokens: int,
        output_tokens: int,
        cache_read: int,
        cache_write: int,
    ) -> dict[str, object]:
        return {
            "input": input_tokens,
            "output": output_tokens,
            "cacheRead": cache_read,
            "cacheWrite": cache_write,
            "totalTokens": input_tokens + output_tokens + cache_read + cache_write,
            "cost": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "total": 0,
            },
        }

    @classmethod
    def pi_assistant(cls, entry_id: str) -> dict[str, object]:
        return {
            "type": "message",
            "id": entry_id,
            "parentId": None,
            "timestamp": "2026-08-01T01:01:00Z",
            "message": {
                "role": "assistant",
                "content": [],
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "usage": cls.pi_usage(10, 5, 3, 2),
                "stopReason": "stop",
                "timestamp": 1785546060000,
            },
        }


if __name__ == "__main__":
    unittest.main()
