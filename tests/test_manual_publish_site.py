from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_manual_publish_site import build_manual_publish_site, current_verification_report, latest_git_time  # noqa: E402


class ManualPublishSiteTest(unittest.TestCase):
    def test_builds_dashboard_with_social_and_syndication_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            social_draft = root / "x.txt"
            social_draft.write_text("Post text\nhttps://onnellab.github.io/blog/en/example/", encoding="utf-8")
            syndication_draft = root / "devto.md"
            syndication_draft.write_text("# Article\n\nBody", encoding="utf-8")
            hashnode_draft = root / "hashnode.md"
            hashnode_draft.write_text(
                """---
title: "Hashnode Title"
canonical_url: "https://onnellab.github.io/blog/en/example/"
tags: "alpha,beta"
cover_image: "https://onnellab.github.io/card.png"
publication_id: ""
---

# Hashnode Title

Body
""",
                encoding="utf-8",
            )
            social_manifest = root / "social.json"
            syndication_manifest = root / "syndication.json"
            manual_state = root / "manual_publish_state.json"
            output = root / "manual" / "index.html"
            social_manifest.write_text(
                json.dumps(
                    {
                        "posts": [
                            {
                                "topic_id": "TOPIC-0001",
                                "platform": "x",
                                "language": "en",
                                "category": "reading",
                                "slug": "example",
                                "template_id": "x",
                                "is_variant": False,
                                "status": "draft",
                                "draft_path": social_draft.relative_to(ROOT).as_posix()
                                if social_draft.is_relative_to(ROOT)
                                else social_draft.as_posix(),
                                "canonical_url": "https://onnellab.github.io/blog/en/example/",
                                "card_asset_path": "generated/assets/blog/en/example/social-card.png",
                                "weighted_length": 48,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            syndication_manifest.write_text(
                json.dumps(
                    {
                        "drafts": [
                            {
                                "topic_id": "TOPIC-0001",
                                "platform": "devto",
                                "language": "en",
                                "category": "reading",
                                "slug": "example",
                                "status": "draft",
                                "draft_path": syndication_draft.as_posix(),
                                "canonical_url": "https://onnellab.github.io/blog/en/example/",
                            },
                            {
                                "topic_id": "TOPIC-0001",
                                "platform": "hashnode",
                                "language": "en",
                                "category": "reading",
                                "slug": "example",
                                "status": "draft",
                                "draft_path": hashnode_draft.as_posix(),
                                "canonical_url": "https://onnellab.github.io/blog/en/example/",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manual_state.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "updated_at": "2026-07-13T10:00:00+09:00",
                        "done": {
                            "TOPIC-0001::x::en::x": {
                                "topic_id": "TOPIC-0001",
                                "platform": "x",
                                "language": "en",
                                "template_id": "x",
                                "verification_method": "existing_chrome_profile",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            build_manual_publish_site(social_manifest, syndication_manifest, output, ROOT / "data" / "topics.csv", manual_state)

            html = output.read_text(encoding="utf-8")
            self.assertIn("ONNELLAB 게시 상태 대시보드", html)
            self.assertIn("ONNELLAB Publish Status Dashboard", html)
            self.assertIn("동기화 연결", html)
            self.assertIn("공개 프로필 확인", html)
            self.assertIn("공개 확인", html)
            self.assertIn("ONNELLAB_GITHUB_PAGES_TOKEN 입력 후 동기화와 공개 확인을 실행할 수 있습니다.", html)
            self.assertIn("ONNELLAB_GITHUB_PAGES_TOKEN", html)
            self.assertIn("자동 포스팅 연결", html)
            self.assertIn("Bluesky 앱 패스워드", html)
            self.assertIn("Dev.to API key", html)
            self.assertIn('id="bluesky-app-password"', html)
            self.assertIn('id="devto-api-key"', html)
            self.assertIn("onnellab-publishing-credentials", html)
            self.assertIn("credentialEnvBlock", html)
            self.assertIn("export BLUESKY_APP_PASSWORD", html)
            self.assertIn("export DEVTO_API_KEY", html)
            self.assertIn("python3 scripts/run_with_local_env.py -- python3 scripts/post_core_distribution.py", html)
            self.assertIn("python3 scripts/run_with_local_env.py -- python3 scripts/sync_publishing_secrets.py", html)
            self.assertIn("저장은 이 브라우저에만 유지됩니다.", html)
            self.assertIn("지금 자동 포스팅 실행", html)
            self.assertIn("runPostingNow", html)
            self.assertIn("actions/workflows/publishing.yml/dispatches", html)
            self.assertIn("dry_run: 'false'", html)
            self.assertIn("doneReportRecord", html)
            self.assertIn("verificationReportRecord", html)
            self.assertIn("current_verification_report", Path(ROOT / "scripts" / "build_manual_publish_site.py").read_text(encoding="utf-8"))
            self.assertIn("pendingReportReason", html)
            self.assertIn("reportPath = 'data/manual_publication_verification_report.json'", html)
            self.assertIn("contents/${reportPath}", html)
            self.assertIn("loadRemoteState({ refreshDashboardData: true })", html)
            self.assertIn("verificationPendingReason", html)
            self.assertIn("actions.append(open, doneButton, detailToggle)", html)
            self.assertIn("반복어 수정 명령 복사", html)
            self.assertIn("copyRepetitionFixCommand", html)
            self.assertIn("python3 scripts/reduce_social_repetition.py && python3 scripts/build_manual_publish_site.py", html)
            self.assertIn(".app-status-card { display: flex; flex-direction: column; gap: 10px; }", html)
            self.assertIn(".app-status-row:only-of-type { flex: 1 1 auto; }", html)
            self.assertIn('id="lang-toggle"', html)
            self.assertIn("https://twitter.com/intent/tweet", html)
            self.assertIn("https://dev.to/new", html)
            self.assertIn('"platform": "hashnode"', html)
            self.assertIn('"publish_title": "Hashnode Title"', html)
            self.assertIn('"publish_body": "# Hashnode Title\\n\\nBody"', html)
            self.assertIn('"publish_tags": "alpha,beta"', html)
            self.assertIn('"publish_canonical_url": "https://onnellab.github.io/blog/en/example/"', html)
            self.assertIn('"publish_cover_image": "https://onnellab.github.io/card.png"', html)
            self.assertIn('"seo_description": "Learn why very large TXT files can feel slow', html)
            self.assertIn("appendHashnodePublishFields", html)
            self.assertIn("hashnodeQuickCopyRows", html)
            self.assertIn("copyBodyAndOpen", html)
            self.assertIn("본문 복사 후 열기", html)
            self.assertIn("copyAndOpenText", html)
            self.assertIn("/blog-assets/en/example/social-card.png", html)
            self.assertIn("statePath = 'data/manual_publish_state.json'", html)
            self.assertIn("manual-state-data", html)
            self.assertIn("existing_chrome_profile", html)
            self.assertIn("remoteState = JSON.parse(document.getElementById('manual-state-data').textContent)", html)
            self.assertIn("setAppBadge", html)
            self.assertIn("Enable badge", html)
            self.assertIn('name="robots" content="noindex,nofollow,noarchive"', html)
            self.assertIn("Twitter", html)
            self.assertIn('"publishing_mode": "manual"', html)
            self.assertIn('"publishing_mode": "automatic"', html)
            self.assertIn('id="mode"', html)
            self.assertIn('id="toggle-variants"', html)
            self.assertIn("수동 게시 필요", html)
            self.assertIn("자동화 대상", html)
            self.assertIn("platform-badge", html)
            self.assertIn("오늘 할 일", html)
            self.assertIn('data-view="due"', html)
            self.assertIn("currentView = 'due'", html)
            self.assertIn("앱 운영 상태", html)
            self.assertIn('id="app-status-grid"', html)
            self.assertIn("release-data", html)
            self.assertIn("릴리즈 후보", html)
            self.assertIn("예정일", html)
            self.assertIn("App Store / Play Store 현재 공개 버전", html)
            self.assertIn("현재 버전 게시일", html)
            self.assertIn("출시 정보", html)
            self.assertIn("GitHub Release", html)
            self.assertIn("store-data", html)
            self.assertIn("release_notes", html)
            self.assertIn('"platform": "android"', html)
            self.assertIn("상세 보기", html)
            self.assertIn("card-detail", html)
            self.assertIn("링크 카드 사용", html)
            self.assertIn("이미지 첨부 없이 링크 카드로 게시", html)
            self.assertIn("usesLinkPreviewCard", html)
            self.assertIn("지금 게시할 수동 항목이 없습니다", html)
            self.assertIn("매체별 상태", html)
            self.assertIn('id="platform-summary"', html)
            self.assertIn("blogPlatformName", html)
            self.assertIn("blog-data", html)
            self.assertIn("다음 게시 예정", html)
            self.assertIn("function nextBlogScheduledDate()", html)
            self.assertIn("function nextAutomatedBlogSlot()", html)
            self.assertIn("86400000 * 3", html)
            self.assertIn("|| nextScheduled", html)
            self.assertNotIn('"status": "archived"', html)
            self.assertIn("사이트 갱신 상태", html)
            self.assertIn('id="site-status-grid"', html)
            self.assertIn("site-data", html)
            self.assertIn("유료 제품 가격", html)
            self.assertIn("Paid product pricing", html)
            self.assertIn('id="pricing-status-grid"', html)
            self.assertIn("pricing-data", html)
            self.assertIn("renderPricingStatusSummary", html)
            self.assertIn("스토어 확인 필요", html)
            self.assertIn("Aligna Pro", html)
            self.assertIn("3,300 KRW", html)
            self.assertIn("Melivra AI Credits 5000", html)
            self.assertIn("34.99 USD", html)
            self.assertIn("VaultXT Pro", html)
            self.assertIn("9,900 KRW", html)
            self.assertIn("if (item.product_type === 'ai_credit') return item.product_name", html)
            self.assertIn("메인 홈페이지 갱신", html)
            self.assertIn("앱 소개 페이지 갱신", html)
            self.assertIn("스크린샷 갱신", html)
            self.assertIn("mode-manual", html)
            self.assertIn("function revealTokenInput()", html)
            self.assertIn("syncButtonLarge.disabled = false", html)
            self.assertIn("syncAuthPanel.hidden = false", html)
            self.assertIn("keepButtonLabel(badgeButton, t('badgeReady'))", html)
            self.assertIn("function publishedItemUrl(item)", html)
            self.assertIn("verify-manual-publications.yml/dispatches", html)
            self.assertIn("triggerPublicationVerification", html)
            self.assertIn("refreshDashboardDataFromPublishedPage", html)
            self.assertIn("loadRemoteState({ refreshDashboardData: true })", html)
            self.assertIn("pollVerificationRun", html)
            self.assertIn("latestVerificationRun", html)
            self.assertIn('id="verification-run-link"', html)
            self.assertIn("verificationRunLink", html)
            self.assertIn("setVerificationRunLink(run)", html)
            self.assertIn("refreshVerificationRunLink", html)
            self.assertIn("verification-report-data", html)
            self.assertNotIn("verification-summary", html)
            self.assertNotIn("renderVerificationSummary", html)
            self.assertNotIn("advanced-summary", html)
            self.assertIn("readEmbeddedJson(doc, 'site-data')", html)
            self.assertIn("release-sync-data", html)
            self.assertIn("releaseSyncSummaryText", html)
            self.assertIn("GitHub Release 확인", html)
            self.assertIn("className = 'spinner'", html)
            self.assertIn("verificationQueued", html)
            self.assertIn("verificationRunning", html)
            self.assertIn("자동 재확인", html)
            self.assertIn("verification-automatic", html)
            self.assertIn("공개 페이지 확인", html)
            self.assertIn("직접 완료", html)
            self.assertIn("completedAt", html)
            self.assertIn("게시 완료", html)
            self.assertIn("postedOrVerifiedAt(item)", html)
            self.assertIn("const platformBadge = document.createElement('div');", html)
            self.assertNotIn("const platformBadge = document.createElement(platformProfile ? 'a' : 'div');", html)
            self.assertNotIn('id="sync-state"', html)
            self.assertNotIn('id="label-total"', html)
            self.assertIn("/favicon.svg?v=20260712-ol-transparent-v2", html)
            self.assertIn("./icon-180.png?v=20260713-dashboard-bg", html)
            self.assertIn(">English</button>", html)
            manifest = (output.parent / "manifest.webmanifest").read_text(encoding="utf-8")
            self.assertIn("./icon-180.png?v=20260713-dashboard-bg", manifest)
            self.assertIn("./icon-192.png?v=20260713-dashboard-bg", manifest)
            self.assertIn("./icon-512.png?v=20260713-dashboard-bg", manifest)
            self.assertIn('"purpose": "any maskable"', manifest)
            self.assertNotIn("favicon-16x16.png", manifest)
            self.assertTrue((output.parent / "manifest.webmanifest").exists())
            self.assertTrue((output.parent / "sw.js").exists())
            self.assertIn("onnellab-manual-publish-v5", (output.parent / "sw.js").read_text(encoding="utf-8"))

    def test_filters_stale_verification_report_items(self) -> None:
        report = current_verification_report(
            {
                "version": 1,
                "checked_at": "2026-07-14T14:00:00+09:00",
                "items": [
                    {"manual_key": "TOPIC-0007::x::en::x", "status": "verified"},
                    {"manual_key": "TOPIC-0002::x::en::x", "status": "pending"},
                ],
            },
            [{"manual_key": "TOPIC-0007::x::en::x"}],
        )

        self.assertEqual(report["counts"], {"checked": 1, "already_done": 0, "verified": 1, "pending": 0})
        self.assertEqual(report["items"], [{"manual_key": "TOPIC-0007::x::en::x", "status": "verified"}])

    def test_latest_git_time_falls_back_to_file_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            page = repo / "page.md"
            page.write_text("updated", encoding="utf-8")

            value = latest_git_time(repo, [page])

        self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}T")


if __name__ == "__main__":
    unittest.main()
