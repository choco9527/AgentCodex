import json
import tempfile
import unittest
from pathlib import Path

from codex_client import normalize_sessions, render_table


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


if __name__ == "__main__":
    unittest.main()
