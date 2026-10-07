from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_manual_publish_site import html_document
from ops_split_pages import (
    _ai_provider_health,
    _bilingual_price_row,
    _bilingual_store_row,
    _diagnose_funnel,
    _funnel_source_message,
    _json_script,
    _release_sync_health,
    _review_source_health,
    _safe_href,
    build_split_ops_pages,
)
from validate_manual_publish_site import validate_dashboard


class OpsSplitPagesTest(unittest.TestCase):
    def test_embedded_review_json_cannot_break_out_of_script(self):
        value = [{"title": "</script><img src=x onerror=alert(1)> & details"}]
        encoded = _json_script(value)
        self.assertNotIn("</script>", encoded.lower())
        self.assertIn(r"\u003c", encoded)
        self.assertEqual(json.loads(encoded), value)

    def test_review_source_health_flags_snapshot_mismatch(self):
        status = {
            "checked_at": "2026-10-08T06:50:00Z",
            "snapshot_matches": False,
            "stores": [
                {"app_slug": "tagweaver", "platform": "ios", "state": "verified", "current_reviews": 2},
                {"app_slug": "quivra", "platform": "android", "state": "verified", "current_reviews": 3},
            ],
        }
        result = _review_source_health("tagweaver", status)
        self.assertIn("동기화 파일 일치 재확인 필요", result)
        self.assertNotIn("Play Store 리뷰", result)
        self.assertIn("2026-10-08T06:50:00Z", result)

    def test_ai_price_warning_and_release_sync_health_are_explicit(self):
        ai = _ai_provider_health({
            "outcome": "changed",
            "checked_at": "2026-10-08T06:30:00Z",
            "providers": [{"status": "warning"}],
        })
        self.assertIn("가격 확인 필요 (changed)", ai)
        self.assertIn("2026-10-08T06:30:00Z", ai)
        release = _release_sync_health({
            "outcome": "error",
            "checked_at": "2026-10-08T06:15:00Z",
        })
        self.assertIn("동기화 확인 필요 (error)", release)
        self.assertIn("2026-10-08T06:15:00Z", release)

    def test_store_links_reject_unsafe_and_show_official_urls(self):
        self.assertNotIn("javascript:", _bilingual_store_row({
            "platform": "ios", "store_url": "javascript:alert(1)",
        }))
        html = _bilingual_store_row({
            "platform": "android", "store_url": "https://play.google.com/store/apps/details?id=example",
        })
        self.assertIn("스토어에서 보기", html)
        self.assertIn("https://play.google.com/", html)

    def test_ai_credit_displays_provenance_for_cost_calculation(self):
        html = _bilingual_price_row({
            "product_name": "AI credits",
            "product_type": "ai_credit",
            "price": "3900",
            "currency": "KRW",
            "ai_margin_status": "loss",
            "ai_net_revenue_usd": "2.50",
            "ai_provider_cost_usd": "3.00",
            "ai_profit_usd": "-0.50",
            "ai_cost_basis": "Provider unit rate with 1.8x safety factor.",
        })
        self.assertIn("AI 원가 계산 근거", html)
        self.assertIn("Provider unit rate with 1.8x safety factor.", html)
        self.assertIn("economics-callout loss", html)

    def test_app_detail_links_disallow_unsafe_url_schemes(self):
        self.assertEqual(_safe_href("javascript:alert(1)"), "")
        self.assertEqual(_safe_href("//evil.example/path"), "")
        self.assertEqual(_safe_href("https://developer.apple.com/docs"), "https://developer.apple.com/docs")
        self.assertEqual(_safe_href("/release-notes/example/"), "/release-notes/example/")

    def test_split_pages_keep_legacy_payload_and_use_apps_card_design(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            homepage = root / "homepage"
            app_dir = homepage / "src" / "content" / "apps" / "tagweaver"
            app_dir.mkdir(parents=True)
            (app_dir / "app.md").write_text("title: TagWeaver\nicon: assets\\icon\\tagweaver.png\n", encoding="utf-8")
            (app_dir / "description-ko.md").write_text(
                "간단한 설명:\nMP3/FLAC 태그를 오프라인으로 편집해요.\n",
                encoding="utf-8",
            )
            output = root / "ops"
            app = {
                "app_id": "APP-0002",
                "app_name": "TagWeaver",
                "slug": "tagweaver",
                "status": "released",
                "platforms": "ios|android",
                "one_line_description": "Offline MP3/FLAC Tag Editor",
            }
            store_items = [
                {"app_id": "APP-0002", "app_slug": "tagweaver", "platform": "ios", "version": "2.5.2", "status": "unchanged", "checked_at": "2026-10-07", "store_url": "https://apps.apple.com/app/id6759609875"},
                {"app_id": "APP-0002", "app_slug": "tagweaver", "platform": "android", "version": "2.5.2", "status": "unchanged", "checked_at": "2026-10-07", "store_url": "https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2"},
            ]
            dependencies = [
                {"app_id": "APP-0002", "app_slug": "tagweaver", "package_type": "app_version", "package_name": "tagweaver", "declared_version": "2.5.2+96", "resolved_version": "2.5.2"},
                {"app_id": "APP-0002", "app_slug": "tagweaver", "package_type": "dependency", "package_name": "file_picker", "declared_version": "^10.0.0", "resolved_version": "10.0.0", "source": "pubspec.lock", "status": "ok"},
                {"app_id": "APP-0002", "app_slug": "tagweaver", "package_type": "dependency", "package_name": "just_audio", "declared_version": "^0.10.5", "resolved_version": "0.10.5", "source": "pubspec.lock", "status": "warning"},
            ]
            releases = [
                {
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "release_id": "REL-0099",
                    "tag": "v2.5.2",
                    "version": "2.5.2",
                    "status": "ready",
                    "release_channel": "public",
                    "platform": "android",
                    "repository": "onnellab/tagweaver",
                    "release_type": "notes_only",
                    "release_date": "2026-10-01",
                    "public_release": "false",
                    "release_url": "https://example.com/release/tagweaver",
                    "release_notes": "Tag editing stability update",
                }
            ]
            reviews = [
                {
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "review_id": "review-ios-1",
                    "platform": "ios",
                    "rating": "2",
                    "title": "Could not save",
                    "body": "Save failed once.",
                    "reviewer_language": "en",
                    "territory": "US",
                    "app_version": "2.5.2",
                    "updated_at": "2026-10-06T10:00:00Z",
                    "status": "pending",
                    "review_kind": "review",
                    "suggested_reply": "Thanks for the report. Please try the latest version.",
                    "reply_category": "bug",
                    "reply_language": "en",
                    "approval_translation_required": True,
                    "review_translation_ko": "저장이 한 번 실패했어요.",
                    "reply_translation_ko": "제보 감사합니다. 최신 버전을 이용해 주세요.",
                    "triage": {
                        "category": "bug",
                        "similar_reviews": 2,
                        "requires_human_approval": True,
                        "facts": [{"text": "TagWeaver edits tags offline."}],
                        "issue_draft": "Investigate intermittent save failure.",
                    },
                },
                {
                    "app_id": "APP-0002",
                    "app_slug": "tagweaver",
                    "review_id": "report-google-1",
                    "platform": "android",
                    "rating": "4",
                    "body": "Works well.",
                    "reviewer_language": "en",
                    "territory": "KR",
                    "app_version": "2.5.2",
                    "updated_at": "2026-10-06T11:00:00Z",
                    "status": "pending",
                    "review_kind": "review",
                    "suggested_reply": "Thank you for using TagWeaver.",
                    "reply_category": "praise",
                    "reply_language": "en",
                    "approval_translation_required": False,
                    "triage": {},
                },
            ]
            pricing = [
                {
                    "app_slug": "tagweaver",
                    "app_name": "TagWeaver",
                    "product_name": "TagWeaver Pro",
                    "product_type": "pro",
                    "platform": "android",
                    "price": "5500",
                    "currency": "KRW",
                    "pricing": "free download with optional pro purchase",
                    "price_verification": "live_store",
                    "price_source": "google_play",
                    "price_note": "Live Google Play price (Korea)",
                    "checked_at": "2026-10-07T12:00:00Z",
                }
            ]
            build_split_ops_pages(
                output,
                legacy_html=html_document([]),
                homepage_repo=homepage,
                apps=[app],
                publication_items=[],
                releases=releases,
                store_items=store_items,
                reviews=reviews,
                dependencies=dependencies,
                pricing=pricing,
                review_sync_status={
                    "checked_at": "2026-10-08T06:50:00+09:00",
                    "snapshot_matches": True,
                    "stores": [
                        {"app_slug": "tagweaver", "platform": "ios", "state": "verified", "current_reviews": 1},
                        {"app_slug": "tagweaver", "platform": "android", "state": "verified", "current_reviews": 1},
                    ],
                },
                release_sync_status={
                    "checked_at": "2026-10-08T06:51:00+09:00",
                    "outcome": "synced",
                },
                site_items=[
                    {
                        "kind": "app",
                        "slug": "tagweaver",
                        "name": "TagWeaver",
                        "landing_updated_at": "2026-10-05T10:00:00+09:00",
                        "screenshots_updated_at": "2026-10-04T10:00:00+09:00",
                        "assets_updated_at": "2026-10-03T10:00:00+09:00",
                        "screenshot_count": 7,
                    }
                ],
                ai_manager_report={
                    "policy_alerts": [
                        {
                            "app_slug": "tagweaver",
                            "store": "App Store",
                            "kind": "metadata",
                            "status": "review_required",
                            "summary": "Check the current store warning.",
                            "operational_note": "Review before the next release.",
                            "occurred_at": "2026-10-07T09:00:00Z",
                            "reference_url": "https://developer.apple.com/",
                        }
                    ]
                },
                funnel_summary={
                    "source_status": {
                        "apple": {"status": "ok", "apps": {"tagweaver": {"status": "ok"}}},
                        "google": {"status": "ok"},
                    },
                    "apps": {
                        "tagweaver": {
                            "platforms": {
                                "ios": {
                                    "latest_date": "2026-10-06",
                                    "windows": {
                                        "30": {
                                            "impressions": 1234,
                                            "store_visitors": 234,
                                            "installs": 45,
                                            "purchases": 2,
                                            "days_with_data": 12,
                                        }
                                    },
                                },
                                "android": {
                                    "latest_date": "2026-10-06",
                                    "windows": {
                                        "30": {
                                            "impressions": None,
                                            "store_visitors": 345,
                                            "installs": 23,
                                            "purchases": 1,
                                            "days_with_data": 12,
                                        }
                                    },
                                },
                            },
                            "combined": {
                                "30": {"store_visitors": None, "impressions": None, "installs": 68, "purchases": 3}
                            },
                        }
                    },
                },
            )

            validate_dashboard(output / "index.html")
            home_html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn(
                'body[data-ops-view="home"] main>.status-section:not([aria-label="AI operation status"])',
                home_html,
            )
            self.assertIn('aria-label="AI operation status"', home_html)
            self.assertTrue((output / "publishing" / "index.html").exists())
            self.assertTrue((output / "media" / "index.html").exists())
            self.assertTrue((output / "settings" / "index.html").exists())
            self.assertTrue((output / "legacy" / "index.html").exists())

            settings_html = (output / "settings" / "index.html").read_text(encoding="utf-8")
            publishing_html = (output / "publishing" / "index.html").read_text(encoding="utf-8")
            self.assertIn('body data-ops-view="settings"', settings_html)
            self.assertIn('id="github-connection-panel"', settings_html)
            self.assertIn('id="sync-auth"', settings_html)
            self.assertIn('body[data-ops-view="settings"] main>.tool-panel,', settings_html)
            self.assertIn(
                'body[data-ops-view="publishing"] main>.credential-panel:not(.github-connection-panel),',
                publishing_html,
            )

            apps_html = (output / "apps" / "index.html").read_text(encoding="utf-8")
            self.assertIn('class="app-card"', apps_html)
            self.assertIn('class="title-row"', apps_html)
            self.assertIn('class="status-badge"', apps_html)
            self.assertIn('class="platform-badges"', apps_html)
            self.assertIn('/app-assets/tagweaver/assets/icon/tagweaver.png', apps_html)
            self.assertIn('/ops/apps/tagweaver/', apps_html)
            self.assertIn('class="ops-topbar"', apps_html)
            self.assertIn('href="/" aria-label="ONNELLAB home"', apps_html)
            self.assertIn('id="ops-lang-toggle"', apps_html)
            self.assertIn('data-ko="앱 관리" data-en="App management"', apps_html)
            self.assertIn("MP3/FLAC 태그를 오프라인으로 편집해요.", apps_html)
            self.assertIn("Offline MP3/FLAC Tag Editor", apps_html)
            self.assertIn('data-ko="출시됨" data-en="Released"', apps_html)

            detail = (output / "apps" / "tagweaver" / "index.html").read_text(encoding="utf-8")
            self.assertIn('id="funnel"', detail)
            self.assertIn("2.5.2", detail)
            self.assertIn("file_picker", detail)
            self.assertIn('data-ko="앱 운영" data-en="App Operations"', detail)
            self.assertIn('data-ko="변경 없음" data-en="unchanged"', detail)
            self.assertIn("onnellab-ops-language", detail)
            self.assertIn('data-funnel-period="7"', detail)
            self.assertIn('data-funnel-period="30" class="is-active"', detail)
            self.assertIn('data-funnel-period="90"', detail)
            self.assertIn('data-funnel-window="30">', detail)
            self.assertIn('data-funnel-window="7" hidden', detail)
            self.assertIn(">1,234</b>", detail)
            self.assertIn(">234</b>", detail)
            self.assertIn(">345</b>", detail)
            self.assertIn(">68</b>", detail)
            self.assertIn(">3</b>", detail)
            self.assertIn('data-ko="양 스토어 설치 합계" data-en="Combined installs"', detail)
            self.assertIn('data-ko="양 스토어 구매 합계" data-en="Combined purchases"', detail)
            self.assertNotIn("Combined visitors", detail)
            self.assertNotIn("양 스토어 방문 합계", detail)
            self.assertIn("선택한 기간에 수집된 데이터가 아직 없어요.", detail)
            self.assertIn('data-en="Diagnosis & evaluation"', detail)
            self.assertIn("internal ONNELLAB operating heuristic", detail)
            self.assertIn('data-review-sync', detail)
            self.assertIn('data-review-action="approve"', detail)
            self.assertIn("data/store_review_approvals.json", detail)
            self.assertIn("publish-store-review-reply.yml", detail)
            self.assertIn("confirm_publish: 'PUBLISH'", detail)
            self.assertIn("if (!queuedApprovalId)", detail)
            self.assertIn("return existing.approval_id;", detail)
            self.assertIn("Publication dispatch failed; press again to retry.", detail)
            self.assertIn("String(item.review_id || '').startsWith('report-')", detail)
            self.assertIn("/[가-힣]/.test", detail)
            self.assertIn("sync-store-reviews.yml", detail)
            self.assertIn("deploy_dashboard: 'true'", detail)
            self.assertIn("Could not save", detail)
            self.assertIn("저장이 한 번 실패했어요.", detail)
            self.assertIn("Investigate intermittent save failure.", detail)
            self.assertNotIn('data-release-approve-index=', detail)
            self.assertNotIn("data/app_release_publications.csv", detail)
            self.assertIn("자동 공개 대기", detail)
            self.assertIn("Ready for automatic publication", detail)
            self.assertIn("REL-0099", detail)
            self.assertIn("Tag editing stability update", detail)
            self.assertIn("just_audio", detail)
            self.assertIn("pubspec.lock", detail)
            self.assertIn("https://apps.apple.com/app/id6759609875", detail)
            self.assertIn("https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2", detail)
            self.assertIn("스토어에서 보기", detail)
            self.assertIn("정상", detail)
            self.assertIn("확인 필요 (warning)", detail)
            self.assertIn("2.5.2+96", detail)
            self.assertIn("onnellab/tagweaver", detail)
            self.assertIn("notes_only", detail)
            self.assertIn("TagWeaver Pro", detail)
            self.assertIn("스토어 실가격 확인", detail)
            self.assertIn("google_play", detail)
            self.assertIn("사이트·자산 최신성", detail)
            self.assertIn("2026-10-05T10:00:00+09:00", detail)
            self.assertIn("7장", detail)
            self.assertIn("정책·운영 경고", detail)
            self.assertIn("Check the current store warning.", detail)
            self.assertIn("Review before the next release.", detail)
            self.assertIn("스토어별 리뷰 수집 검증", detail)
            self.assertIn("최신 목록 검증됨", detail)
            self.assertIn("2026-10-08T06:50:00+09:00", detail)
            self.assertIn("릴리즈 동기화 검증", detail)
            self.assertIn("GitHub 릴리즈 동기화 완료", detail)
            self.assertIn("2026-10-08T06:51:00+09:00", detail)
            self.assertNotIn("기존 통합 콘솔에서 릴리즈 승인·리뷰 답변", detail)
            self.assertNotIn('href="/ops/legacy/"', detail)

    def test_funnel_diagnosis_is_conservative_and_actionable(self):
        no_data = _diagnose_funnel("google", None, 30)
        self.assertEqual(no_data["kind"], "wait")
        self.assertIn("판단 대기", no_data["title_ko"])

        small = _diagnose_funnel(
            "google",
            {"store_visitors": 8, "installs": 4, "purchases": 1, "days_with_data": 2},
            30,
        )
        self.assertEqual(small["kind"], "wait")
        self.assertIn("표본", small["title_ko"])

        traffic_leak = _diagnose_funnel(
            "apple",
            {
                "impressions": 1000,
                "store_visitors": 50,
                "installs": 20,
                "purchases": 2,
                "days_with_data": 10,
            },
            30,
        )
        self.assertEqual(traffic_leak["kind"], "low")
        self.assertIn("제품 페이지 진입", traffic_leak["title_ko"])

        conversion_leak = _diagnose_funnel(
            "google",
            {"store_visitors": 200, "installs": 10, "purchases": 1, "days_with_data": 10},
            30,
        )
        self.assertEqual(conversion_leak["kind"], "low")
        self.assertIn("스토어 전환", conversion_leak["title_ko"])

        monetization = _diagnose_funnel(
            "google",
            {"store_visitors": 200, "installs": 40, "purchases": 0, "days_with_data": 10},
            30,
        )
        self.assertEqual(monetization["kind"], "warn")
        self.assertIn("구매 전환", monetization["title_ko"])

        traffic_priority = _diagnose_funnel(
            "google",
            {"store_visitors": 725, "installs": 243, "purchases": 12, "days_with_data": 21},
            30,
        )
        self.assertEqual(traffic_priority["kind"], "good")
        self.assertIn("유입량", traffic_priority["title_ko"])
        self.assertIn("traffic", traffic_priority["title_en"].lower())

    def test_apple_analytics_403_has_actionable_bilingual_message(self):
        ko, en = _funnel_source_message(
            {
                "source_status": {
                    "apple": {
                        "status": "error",
                        "apps": {
                            "tagweaver": {
                                "status": "error",
                                "message": "HTTP Error 403: Forbidden",
                            }
                        },
                    }
                }
            },
            "apple",
            "tagweaver",
        )
        self.assertIn("Admin 역할 API 키", ko)
        self.assertIn("Admin-role API key", en)

    def test_apple_snapshot_wait_message_mentions_historical_data(self):
        ko, en = _funnel_source_message(
            {
                "source_status": {
                    "apple": {
                        "status": "waiting",
                        "apps": {
                            "tagweaver": {
                                "status": "waiting_for_snapshot",
                            }
                        },
                    }
                }
            },
            "apple",
            "tagweaver",
        )
        self.assertIn("과거 데이터 스냅샷", ko)
        self.assertIn("지난달", ko)
        self.assertIn("historical snapshot", en)
        self.assertIn("last month", en)


if __name__ == "__main__":
    unittest.main()
