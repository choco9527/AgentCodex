import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_bridge import CodexClient, normalize_sessions, normalize_thread_id, render_table, thread_id_from_result


class SessionNormalizationTests(unittest.TestCase):
    def test_title_project_branch_and_time_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            index_path = codex_home / "session_index.jsonl"
            index_path.write_text(
                json.dumps(
                    {
                        "id": "thread-1",
                        "thread_name": "Implement payment settings",
                        "updated_at": "2026-05-21T07:15:46.394405Z",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            log_path = codex_home / "sessions" / "2026" / "05" / "21" / "rollout-thread-1.jsonl"
            log_path.parent.mkdir(parents=True)
            log_path.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {
                            "id": "thread-1",
                            "cwd": "/workspace/example-app",
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            summaries = normalize_sessions(
                {
                    "threads": [
                        {
                            "id": "thread-1",
                            "preview": "fallback preview",
                            "gitInfo": {"branch": "feature/payment-settings"},
                        }
                    ]
                },
                codex_home=codex_home,
            )

        self.assertEqual(summaries[0].title, "Implement payment settings")
        self.assertEqual(summaries[0].index, 1)
        self.assertEqual(summaries[0].project, "example-app")
        self.assertEqual(summaries[0].branch, "feature/payment-settings")
        self.assertEqual(summaries[0].updated_at, "05-21 15:15")

    def test_pinned_sessions_sort_first(self):
        summaries = normalize_sessions(
            [
                {
                    "id": "old-pinned",
                    "title": "Old pinned",
                    "updatedAt": "2026-05-01T00:00:00Z",
                    "pinned": True,
                },
                {
                    "id": "new-normal",
                    "title": "New normal",
                    "updatedAt": "2026-05-21T00:00:00Z",
                },
            ],
            codex_home=Path("/tmp/agentcodex-no-such-home"),
        )

        self.assertEqual([item.title for item in summaries], ["Old pinned", "New normal"])

    def test_table_uses_english_headers_by_default(self):
        summaries = normalize_sessions(
            [
                {
                    "id": "thread-1",
                    "title": "Example session",
                    "project": "project-a",
                    "branch": "main",
                    "updatedAt": "2026-05-21T00:00:00Z",
                }
            ],
            codex_home=Path("/tmp/agentcodex-no-such-home"),
        )

        first_line = render_table(summaries).splitlines()[0]
        self.assertTrue(first_line.startswith("Index | Title"))

    def test_table_supports_chinese_headers(self):
        summaries = normalize_sessions(
            [
                {
                    "id": "thread-1",
                    "title": "Example session",
                    "project": "project-a",
                    "branch": "main",
                    "updatedAt": "2026-05-21T00:00:00Z",
                }
            ],
            codex_home=Path("/tmp/agentcodex-no-such-home"),
        )

        first_line = render_table(summaries, lang="zh").splitlines()[0]
        self.assertTrue(first_line.startswith("序号 | 标题"))

    def test_thread_id_aliases_are_normalized(self):
        self.assertEqual(normalize_thread_id("thread-1"), "thread-1")
        self.assertEqual(normalize_thread_id({"threadId": "thread-2"}), "thread-2")
        self.assertEqual(normalize_thread_id({"conversationId": "thread-3"}), "thread-3")
        self.assertEqual(thread_id_from_result({"thread": {"id": "thread-4"}}), "thread-4")

    def test_default_app_server_command_uses_stdio_listen(self):
        with patch("os.path.exists", return_value=True):
            client = CodexClient(codex_binary="/opt/codex")
            self.assertEqual(client._build_app_server_command(), ["/opt/codex", "app-server", "--listen", "stdio://"])

    def test_configured_app_server_command_is_respected(self):
        with patch.dict("os.environ", {"CODEX_APP_SERVER_CMD": "codex app-server --listen stdio://"}):
            client = CodexClient(codex_binary="/opt/codex")
            self.assertEqual(client._build_app_server_command(), ["codex", "app-server", "--listen", "stdio://"])


if __name__ == "__main__":
    unittest.main()
