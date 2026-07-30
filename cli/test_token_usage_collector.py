import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cli.token_usage_collector import (
    ScanResult,
    scan_claude,
    scan_codex,
    scan_opencode,
    sync_tool,
)


def json_line(value: object) -> str:
    return json.dumps(value, separators=(",", ":")) + "\n"


class TokenUsageCollectorTest(unittest.TestCase):
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
                return {}

        client = Client()
        events = [{"source_event_id": str(index)} for index in range(3)]

        sync_tool(
            client,  # type: ignore[arg-type]
            "codex",
            lambda _cursor: ScanResult(
                events=events,
                cursor={"version": 1, "offset": 20},
            ),
            batch_size=2,
            verbose=False,
        )

        self.assertEqual(client.submissions[0][1]["offset"], 10)
        self.assertEqual(client.submissions[1][1]["offset"], 20)

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
            self.assertIn('"tool":"claude"', stdout.getvalue())

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


if __name__ == "__main__":
    unittest.main()
