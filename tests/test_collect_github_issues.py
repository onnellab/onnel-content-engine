from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collect_github_issues as collector


class FakeResponse:
    def __init__(self, payload: object, link: str = "") -> None:
        self.payload = payload
        self.headers = {"Link": link}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class QueueOpener:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout: int):
        self.requests.append((request, timeout))
        return self.responses.pop(0)


class GitHubIssueCollectorTest(unittest.TestCase):
    def repository_csv(self, directory: Path) -> Path:
        path = directory / "app_release_config.csv"
        path.write_text(
            "app_id,app_slug,repository,artifact_pattern,notes\n"
            "APP-1,one,onnellab/one,pattern,notes\n"
            "APP-2,two,onnellab/two,pattern,notes\n",
            encoding="utf-8",
        )
        return path

    def test_fetches_all_pages_and_excludes_pull_requests(self) -> None:
        next_url = "https://api.github.com/repos/onnellab/one/issues?page=2"
        opener = QueueOpener(
            [
                FakeResponse(
                    [
                        {"number": 1, "title": "Bug", "html_url": "https://github.com/onnellab/one/issues/1"},
                        {"number": 2, "title": "PR", "pull_request": {}},
                    ],
                    f'<{next_url}>; rel="next"',
                ),
                FakeResponse([{"number": 3, "title": "Crash"}]),
            ]
        )

        issues = collector.fetch_open_issues("onnellab/one", "token", opener)

        self.assertEqual([item["number"] for item in issues], [1, 3])
        self.assertEqual(len(opener.requests), 2)
        self.assertEqual(opener.requests[0][0].get_header("Authorization"), "Bearer token")

    def test_collect_stores_metadata_only_and_marks_missing_issue_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            existing = [
                {
                    "issue_id": "github:onnellab/one#9",
                    "repository": "onnellab/one",
                    "number": 9,
                    "status": "open",
                    "first_seen_at": "2026-07-20T00:00:00+00:00",
                }
            ]
            opener = QueueOpener(
                [
                    FakeResponse(
                        [
                            {
                                "number": 1,
                                "title": "Large file crash",
                                "body": "private log must not be stored",
                                "user": {"login": "someone"},
                                "comments": 4,
                                "labels": [{"name": "bug"}],
                                "html_url": "https://github.com/onnellab/one/issues/1",
                                "created_at": "2026-07-27T00:00:00Z",
                                "updated_at": "2026-07-28T00:00:00Z",
                            }
                        ]
                    ),
                    FakeResponse([]),
                ]
            )
            with patch.object(collector, "REPOSITORIES_PATH", self.repository_csv(directory)):
                items = collector.collect(
                    {"enabled": True, "repositories": []},
                    existing,
                    "token",
                    checked_at="2026-07-28T01:00:00+00:00",
                    opener=opener,
                )

        new_issue = next(item for item in items if item["number"] == 1)
        closed = next(item for item in items if item["number"] == 9)
        self.assertNotIn("body", new_issue)
        self.assertNotIn("user", new_issue)
        self.assertNotIn("comments", new_issue)
        self.assertEqual(new_issue["labels"], ["bug"])
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(closed["first_seen_at"], "2026-07-20T00:00:00+00:00")

    def test_unknown_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            with patch.object(collector, "REPOSITORIES_PATH", self.repository_csv(directory)):
                with self.assertRaisesRegex(ValueError, "unknown app repository"):
                    collector.configured_repositories(
                        {"enabled": True, "repositories": ["onnellab/missing"]}
                    )

    def test_workflow_is_read_only_for_app_issues(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "collect-github-issues.yml").read_text()

        self.assertIn("issues: read", workflow)
        self.assertIn("collect_github_issues.py", workflow)
        self.assertIn("ONNELLAB_GITHUB_PAGES_TOKEN", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("gh issue", workflow)


if __name__ == "__main__":
    unittest.main()
