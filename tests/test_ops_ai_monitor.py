"""Regression checks for conservative, readable AI operations status."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from ops_ai_monitor import METRIC_GROUPS, analyze, render_home, render_monitoring


def report(**overrides):
    base = {
        "generated_at": "2026-10-08T00:21:00Z",
        "refresh_status": {"status": "complete", "steps": [{"script": "collect.py", "status": "ok"}]},
        "summary": {"reviews_triaged": 11, "replies_published": 3,
                    "qa_reports_passed": 0, "qa_reports_blocked": 0,
                    "new_crash_incidents": 0, "os_updates_to_review": 1,
                    "os_impact_tasks": 7, "store_policy_tasks": 23},
        "requires_attention": [],
        "policy_alerts": [{
            "task_id": "policy-1", "app_slug": "melivra", "store": "google_play",
            "status": "deferred", "kind": "billing",
            "summary": "The requirement is still outstanding.",
            "operational_note": "Review at release.",
            "reference_url": "https://developer.android.com/google/play/billing/migrate-gpblv8",
        }],
    }
    base.update(overrides)
    return base


NOW = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)


class AiOpsMonitoringTest(unittest.TestCase):
    def test_all_source_metrics_are_mapped_once(self):
        all_names = [key for _, _, fields in METRIC_GROUPS for key, _, _ in fields]
        self.assertEqual(len(all_names), 40)
        self.assertEqual(len(all_names), len(set(all_names)))

    def test_explicitly_deferred_is_not_actionable_or_resolved(self):
        data = analyze(report(), now=NOW)
        self.assertEqual(data["collection"], "complete")
        self.assertEqual(data["immediate"], [])
        self.assertEqual(len(data["deferred"]), 1)
        self.assertIn("보류 1건", render_home(report()))

    def test_source_refresh_is_not_qa_pass(self):
        page = render_monitoring(report())
        self.assertIn("자료 갱신 완료", page)
        self.assertIn("QA 보고서 기록이 없어요.", page)
        self.assertIn("검증 통과를 뜻하지는 않아요.", page)
        self.assertNotIn("전체 검증 통과", page)
        self.assertIn("0건 항목", page)
        self.assertIn("스토어 정책 분석 작업", page)
        self.assertIn("23</strong>", page)
        self.assertIn("Melivra · Google Play", page)
        self.assertIn('class="ai-alert-more"', page)
        self.assertIn('data-ai-generated-at=', page)
        self.assertIn('Snapshot is outdated', page)

    def test_repeated_policy_attention_counts_one_action(self):
        policy = {**report()["policy_alerts"][0], "status": "review_required"}
        needs = [{"task_id": "policy-1", "category": "store_policy_alert", "actions": "Fix it"}]
        state = analyze(report(policy_alerts=[policy], requires_attention=needs), now=NOW)
        self.assertEqual(len(state["immediate"]), 1)
        self.assertEqual(len(state["deferred"]), 0)

    def test_refresh_failure_is_distinct_from_non_applicable(self):
        data = report(refresh_status={"status": "complete", "steps": [
            {"script": "failed.py", "status": "unavailable"},
            {"script": "not_needed.py", "status": "not_applicable"},
        ]})
        self.assertEqual(analyze(data, now=NOW)["collection"], "partial")
        page = render_monitoring(data)
        self.assertIn("수집 실패 단계", page)
        self.assertIn("failed.py", page)
        self.assertNotIn("not_needed.py</code>", page)

    def test_old_report_and_missing_report_cannot_look_healthy(self):
        old = analyze(report(), now=datetime(2026, 10, 12, tzinfo=timezone.utc))
        self.assertEqual(old["collection"], "stale")
        self.assertEqual(analyze({}, now=NOW)["collection"], "missing")
        self.assertIn("확인 불가", render_home({}))
        self.assertIn("보고서가 없어", render_monitoring({}))

    def test_untrusted_report_text_is_escaped_and_links_safe(self):
        unsafe = report(policy_alerts=[{
            "app_slug": '<img src=x onerror=alert(1)>',
            "status": "deferred",
            "summary": "</script><script>alert(1)</script>",
            "reference_url": "javascript:alert(1)",
        }])
        page = render_monitoring(unsafe)
        self.assertNotIn('<img src=x', page)
        self.assertNotIn("<script>alert", page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn("&lt;script&gt;", page)

    def test_cross_locale_page_preserves_korean_and_english(self):
        page = render_monitoring(report())
        self.assertIn('data-ko="보류된 정책 알림" data-en="Deferred policy alerts"', page)
        self.assertIn("2026.10.08 09:21 KST", page)
        self.assertIn('data-ko="분석한 리뷰" data-en="Reviews triaged"', page)

    def test_ops_deploy_workflows_always_seal_monitoring_and_sales(self):
        workflow_dir = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        protecting = 0
        for path in workflow_dir.glob("*.yml"):
            body = path.read_text(encoding="utf-8")
            if "node scripts/private_ops_publish.mjs seal-site" not in body:
                continue
            protecting += 1
            self.assertNotIn("cp generated/manual-publish/index.html", body)
            self.assertIn("ONNELLAB_OPS_PASSWORD", body)
        self.assertGreaterEqual(protecting, 9)
        import inspect
        from ops_split_pages import build_split_ops_pages
        builder = inspect.getsource(build_split_ops_pages)
        self.assertIn('output_dir / "monitoring" / "index.html"', builder)
        self.assertIn('output_dir / "sales" / "index.html"', builder)


if __name__ == "__main__":
    unittest.main()
