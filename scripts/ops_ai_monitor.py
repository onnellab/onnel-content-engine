#!/usr/bin/env python3
"""Presentation-only AI operations health overview for ONNELLAB Ops.

Keep existing report collection/decision logic unchanged. This layer never
promotes a zero count to a successful verification or a deferral to a fix.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


METRIC_GROUPS = (
    ("리뷰·고객 대응", "Reviews & customer care", (
        ("reviews_triaged", "분석한 리뷰", "Reviews triaged"),
        ("high_risk_reports", "고위험 리뷰", "High-risk reviews"),
        ("replies_queued", "답변 게시 대기", "Replies queued"),
        ("replies_published", "답변 게시됨", "Replies published"),
        ("pricing_patterns", "가격 관련 반복 문제", "Pricing patterns"),
        ("issues_created", "생성된 이슈", "Issues created"),
        ("open_app_github_issues", "열린 앱 이슈", "Open app issues"),
    )),
    ("품질·검증", "Quality & verification", (
        ("new_crash_incidents", "신규 크래시", "New crashes"),
        ("doctor_high_findings", "고위험 진단 결과", "High-risk doctor findings"),
        ("qa_reports_passed", "통과된 QA 보고서", "QA reports passed"),
        ("qa_reports_blocked", "중단된 QA 보고서", "QA reports blocked"),
        ("policy_assessments_pending", "정책 영향 검토 대기", "Policy assessments pending"),
        ("policy_assessment_failures", "실패한 정책 검토", "Failed policy assessments"),
        ("release_candidates_failed", "릴리즈 후보 실패", "Failed release candidates"),
        ("ios_device_qa_blocked", "차단된 iOS 검증", "Blocked iOS QA"),
    )),
    ("OS·스토어 정책", "OS & store policies", (
        ("os_updates_to_review", "검토할 OS 업데이트", "OS updates to review"),
        ("os_impact_tasks", "OS 영향 분석 작업", "OS impact tasks"),
        ("store_policy_tasks", "스토어 정책 분석 작업", "Store policy tasks"),
        ("store_policy_mailboxes_connected", "연결된 정책 메일함", "Connected policy mailboxes"),
    )),
    ("개발 작업", "Development tasks", (
        ("coder_tasks_proposed", "제안된 수정 작업", "Proposed fixes"),
        ("coder_tasks_approved_pending", "승인 후 실행 대기", "Approved fixes awaiting execution"),
        ("coder_draft_prs", "작성된 초안 PR", "Draft PRs created"),
    )),
    ("내부 테스트·출시", "Private tests & release", (
        ("store_submissions_blocked", "차단된 스토어 제출", "Blocked store submissions"),
        ("internal_test_uploads", "내부 테스트 업로드", "Internal test uploads"),
        ("internal_store_processing", "스토어 처리 중", "Processing in stores"),
        ("internal_store_processed", "스토어 처리됨", "Processed in stores"),
        ("internal_store_processing_failed", "스토어 처리 실패", "Store processing failures"),
        ("new_internal_test_feedback", "신규 테스트 의견", "New tester feedback"),
        ("internal_test_high_findings", "고위험 테스트 결과", "High-risk test findings"),
        ("internal_test_passed", "통과된 내부 테스트", "Internal tests passed"),
        ("internal_test_failed", "실패한 내부 테스트", "Internal tests failed"),
        ("internal_test_ready_for_upload", "업로드 준비된 빌드", "Builds ready to upload"),
        ("internal_test_available_to_testers", "테스터 사용 가능", "Available to testers"),
        ("private_test_builds_dispatched", "빌드 요청됨", "Builds dispatched"),
        ("private_test_builds_artifact_ready", "빌드 산출물 준비됨", "Build artifacts ready"),
        ("private_test_builds_failed", "빌드 실패", "Build failures"),
        ("private_test_orchestrations_active", "테스트 진행 중", "Active test orchestrations"),
        ("private_test_orchestrations_failed", "테스트 자동화 실패", "Failed test orchestrations"),
        ("android_aab_expiring", "만료 임박한 AAB", "AABs expiring soon"),
        ("android_aab_expired", "만료된 AAB", "Expired AABs"),
    )),
)

ATTENTION_TYPES = {
    "store_policy_alert": ("스토어 정책 확인", "Review store policy"),
    "coder_approved_pending": ("승인된 개발 작업 대기", "Approved fix awaiting execution"),
    "qa_blocked": ("QA 중단", "QA blocked"),
    "release_candidate_failed": ("릴리즈 후보 실패", "Release candidate failed"),
    "ios_device_qa_blocked": ("iOS 검증 중단", "iOS QA blocked"),
    "internal_test_high_finding": ("고위험 테스트 결과", "High-risk test finding"),
    "internal_test_failed": ("내부 테스트 실패", "Internal test failed"),
    "private_test_build_failed": ("테스트 빌드 실패", "Test build failed"),
    "internal_store_processing_failed": ("스토어 처리 실패", "Store processing failed"),
    "android_aab_expired": ("Android 빌드 만료", "Android build expired"),
    "android_aab_expiring": ("Android 빌드 만료 임박", "Android build expiring"),
    "private_test_orchestration_failed": ("테스트 자동화 실패", "Test orchestration failed"),
}
DEFERRED = {"deferred"}
RESOLVED = {"pass", "dismissed", "resolved"}


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _loc(ko: str, en: str, tag: str = "span", css: str = "") -> str:
    cls = f' class="{_esc(css)}"' if css else ""
    return f'<{tag}{cls} data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</{tag}>'


def _date(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def _time(value: object) -> str:
    parsed = _date(value)
    return parsed.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d %H:%M KST") if parsed else "—"


def _count(summary: Mapping[str, object], key: str) -> int | None:
    value = summary.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _list(value: object) -> list[Mapping[str, object]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _safe_url(value: object) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def _alert_id(item: Mapping[str, object]) -> str:
    return str(item.get("task_id") or "").strip()


def _alert_state(item: Mapping[str, object]) -> str:
    status = str(item.get("status") or "").strip().lower()
    return "resolved" if status in RESOLVED else "deferred" if status in DEFERRED else "active"

def analyze(report: Mapping[str, object] | None, now: datetime | None = None) -> dict[str, object]:
    """Conservatively distinguish collection health, alerts and unverified work."""
    report = report if isinstance(report, Mapping) else {}
    snapshot = _date(report.get("generated_at"))
    as_of = now or datetime.now(timezone.utc)
    as_of = as_of.astimezone(timezone.utc)
    refresh = report.get("refresh_status")
    refresh = refresh if isinstance(refresh, Mapping) else {}
    bad_steps = [x for x in _list(refresh.get("steps"))
                 if str(x.get("status") or "").lower() in {"failed", "unavailable", "error"}]
    status = str(refresh.get("status") or "").lower()
    if snapshot is None or snapshot - as_of > timedelta(minutes=15):
        collection = "missing"
    elif as_of - snapshot > timedelta(hours=48):
        collection = "stale"
    elif bad_steps or status in {"failed", "partial", "incomplete", "error"}:
        collection = "partial"
    elif status == "complete":
        collection = "complete"
    else:
        collection = "unknown"

    alerts = [x for x in _list(report.get("policy_alerts")) if _alert_state(x) != "resolved"]
    active_alerts = [x for x in alerts if _alert_state(x) == "active"]
    deferred_alerts = [x for x in alerts if _alert_state(x) == "deferred"]
    active_ids = {_alert_id(x) for x in active_alerts if _alert_id(x)}
    attention = [x for x in _list(report.get("requires_attention"))
                 if not (_alert_id(x) and _alert_id(x) in active_ids)]
    summary = report.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    return {
        "has_report": snapshot is not None,
        "generated": _time(report.get("generated_at")),
        "collection": collection,
        "bad_steps": bad_steps,
        "immediate": attention + active_alerts,
        "deferred": deferred_alerts,
        "summary": summary,
    }


def _collection_label(collection: str) -> tuple[str, str]:
    return {
        "complete": ("자료 갱신 완료", "Sources refreshed"),
        "partial": ("일부 수집 확인 필요", "Some sources need attention"),
        "stale": ("자료 갱신 지연", "Snapshot is outdated"),
        "missing": ("자료 없음", "No report available"),
        "unknown": ("수집 상태 미확인", "Source status unknown"),
    }.get(collection, ("수집 상태 미확인", "Source status unknown"))


def _metric(count: int | None) -> str:
    return str(count) if count is not None else "—"


def render_home(report: Mapping[str, object] | None) -> str:
    state = analyze(report)
    if not state["has_report"]:
        summary = _loc("AI 점검 자료가 아직 없어요.", "AI operations data is not available.")
        count_text = _loc("확인 불가", "Unavailable")
    else:
        summary = _loc(*_collection_label(str(state["collection"])))
        count_text = _loc(f'즉시 확인 {len(state["immediate"])}건 · 보류 {len(state["deferred"])}건',
                          f'{len(state["immediate"])} actionable · {len(state["deferred"])} deferred')
    return (
        '<section class="ai-home-preview" aria-label="AI operations summary">'
        '<div><h2>' + _loc("AI 운영 점검", "AI operations", "span") + '</h2>'
        '<p>' + summary + ' · ' + count_text + '</p>'
        '<small>' + _loc("보고서 갱신", "Report updated") + ' · ' + _esc(state["generated"]) + '</small></div>'
        '<a href="/ops/monitoring/">' + _loc("점검 상세 보기", "View monitoring details") + ' →</a>'
        '</section>'
    )


def _attention_card(item: Mapping[str, object], *, deferred: bool = False, policy: bool = False) -> str:
    category = str(item.get("category") or "")
    kind = str(item.get("kind") or "policy")
    labels = ATTENTION_TYPES.get(category, ("조치 내용 확인", "Action needs review"))
    if policy:
        app = str(item.get("app_slug") or "—")
        store = str(item.get("store") or "—")
        title = _esc(app + " · " + store)
        labels = ("스토어 정책 보류", "Store policy deferred") if deferred else ("스토어 정책 확인", "Store policy review")
        detail = str(item.get("summary") or "")
        note = str(item.get("operational_note") or "")
    else:
        title = _loc(*labels, "span")
        detail = str(item.get("actions") or item.get("evidence") or "")
        note = ""
    body = '<p>' + _esc(detail or "—") + '</p>'
    if note:
        body += '<p class="ai-note">' + _loc("현재 조치", "Current action") + ' · ' + _esc(note) + '</p>'
    date = item.get("occurred_at")
    if date:
        body += '<small>' + _loc("최초 감지", "Detected") + ' · ' + _esc(_time(date)) + '</small>'
    ref = _safe_url(item.get("reference_url"))
    if ref:
        body += '<a class="ai-link" href="' + _esc(ref) + '" target="_blank" rel="noopener noreferrer">' + _loc("공식 참고 문서 ↗", "Official reference ↗") + '</a>'
    return (
        '<article class="ai-alert-row" data-alert-priority="' + ("deferred" if deferred else "actionable") + '">'
        '<div class="ai-alert-head"><strong>' + title + '</strong><span class="ai-state-label">'
        + _loc(*labels, "span") + '</span></div>' + body + '</article>'
    )

def render_monitoring(report: Mapping[str, object] | None) -> str:
    """Full detail page: urgent items first, zero metrics tucked away."""
    state = analyze(report)
    summary = state["summary"]
    has_report = state["has_report"]
    collection = str(state["collection"])
    status_ko, status_en = _collection_label(collection)
    immediate = state["immediate"]
    deferred = state["deferred"]
    crashes = _count(summary, "new_crash_incidents") if has_report else None
    stats = (
        (_loc("즉시 확인", "Needs action"), _metric(len(immediate) if has_report else None)),
        (_loc("보류된 정책 알림", "Deferred policy alerts"), _metric(len(deferred) if has_report else None)),
        (_loc("신규 크래시", "New crashes"), _metric(crashes)),
    )
    kpis = "".join('<div class="ai-kpi"><span>' + label + '</span><strong>' + _esc(number) + '</strong></div>'
                   for label, number in stats)
    attention_cards = "".join(_attention_card(x, policy="status" in x) for x in immediate)
    deferred_cards = "".join(_attention_card(x, deferred=True, policy=True) for x in deferred)
    if not has_report:
        attention_cards = '<div class="ai-empty">' + _loc("보고서가 없어 조치 필요 여부를 판단할 수 없어요.",
                                                         "No report is available to determine required actions.") + '</div>'
    elif not attention_cards:
        attention_cards = '<div class="ai-empty">' + _loc("보고서에 즉시 조치 대상으로 분류된 항목이 없어요. 검증 통과를 뜻하지는 않아요.",
                                                         "No immediate actions are listed. This does not mean all tests passed.") + '</div>'
    if not deferred_cards:
        deferred_cards = '<p class="ai-empty">' + _loc("보류 중인 정책 알림이 없어요.", "No deferred policy alerts.") + '</p>'

    headline = '<p class="ai-updated">' + _loc("보고서 시각", "Report generated") + ' · ' + _esc(state["generated"]) + '</p>'
    header = (
        '<header class="ops-head"><p class="eyebrow">' + _loc("운영 모니터링", "Operations monitoring") + '</p>'
        '<h1>' + _loc("AI 운영 점검", "AI operations") + '</h1>'
        '<p>' + _loc("먼저 확인할 항목을 보고, 나머지는 분야별로 펼쳐볼 수 있어요.",
                     "See what needs attention first, then expand details by area.") + '</p>'
        '</header><div class="ai-source-line"><span class="ai-source-state" data-collection="' + _esc(collection) + '">'
        + _loc(status_ko, status_en) + '</span>' + headline + '</div>'
    )
    freshness_notice = ''
    if collection != "complete":
        freshness_notice = '<p class="ai-health-note">' + _loc(
            "자료 갱신 상태가 확인되지 않았거나 일부 수집이 누락됐어요. 0건을 문제없음으로 해석하지 마세요.",
            "Sources may be stale or incomplete. Zero counts must not be treated as clearance."
        ) + '</p>'
    bad_steps = state["bad_steps"]
    if bad_steps:
        steps = "".join('<li><code>' + _esc(x.get("script") or "unknown") + '</code> · '
                        + _esc(x.get("status") or "unknown") + '</li>' for x in bad_steps)
        freshness_notice += '<details class="ai-details"><summary>' + _loc("수집 실패 단계", "Source refresh failures") + '</summary><ul>' + steps + '</ul></details>'

    change_keys = ("os_updates_to_review", "os_impact_tasks", "store_policy_tasks")
    change_labels = dict((key, (ko, en)) for group in METRIC_GROUPS for key, ko, en in group[2])
    change_rows = ''.join(
        '<div class="ai-count-row">' + _loc(*change_labels[key]) +
        '<strong>' + _metric(_count(summary, key) if has_report else None) + '</strong></div>'
        for key in change_keys
    )
    qa_passed = _count(summary, "qa_reports_passed") if has_report else None
    qa_blocked = _count(summary, "qa_reports_blocked") if has_report else None
    if qa_passed == 0 and qa_blocked == 0:
        qa_notice = '<p class="ai-health-note">' + _loc("QA 보고서 기록이 없어요. 검증 통과로 표시하지 않아요.",
                                                        "No QA reports recorded; verification is not marked as passed.") + '</p>'
    else:
        qa_notice = ''

    groups = []
    for group_ko, group_en, definitions in METRIC_GROUPS:
        visible = []
        zero = []
        for key, ko, en in definitions:
            count = _count(summary, key) if has_report else None
            item = '<div class="ai-count-row" title="' + _esc(key) + '">' + _loc(ko, en) + '<strong>' + _metric(count) + '</strong></div>'
            (zero if count == 0 else visible).append(item)
        hidden = (
            '<details class="ai-zero-items"><summary>' +
            _loc(f'0건 항목 {len(zero)}개 표시', f'Show {len(zero)} zero-count items') +
            '</summary><div class="ai-row-list">' + "".join(zero) + '</div></details>'
        ) if zero else ''
        if not visible:
            visible = ['<p class="ai-empty">' + _loc("별도 표시할 활동이 없어요.", "No additional activity to show.") + '</p>']
        groups.append(
            '<details class="ai-details"><summary>' + _loc(group_ko, group_en) +
            '<span class="ai-chevron" aria-hidden="true">⌄</span></summary>'
            '<div class="ai-details-body"><div class="ai-row-list">' + ''.join(visible) +
            '</div>' + hidden + '</div></details>'
        )
    # Do not suppress unknown fields: retain auditable access to later report additions.
    mapped = {key for group in METRIC_GROUPS for key, _, _ in group[2]}
    extra = sorted(str(x) for x in summary if x not in mapped)
    extras = ''
    if extra:
        extras = '<details class="ai-details"><summary>' + _loc("새로 추가된 원본 항목", "New raw report fields") + '</summary><div class="ai-row-list">' + ''.join(
            '<div class="ai-count-row"><code>' + _esc(key) + '</code><strong>' + _esc(summary[key]) + '</strong></div>'
            for key in extra
        ) + '</div></details>'
    return (
        header + '<section class="ai-kpis" aria-label="Top AI operations counts">' + kpis + '</section>'
        + freshness_notice
        + '<section class="ai-monitor-section"><h2>' + _loc("지금 확인할 항목", "Items needing attention") +
        '</h2><div class="ai-alert-list">' + attention_cards + '</div></section>'
        + '<section class="ai-monitor-section"><h2>' + _loc("보류된 정책 알림", "Deferred policy alerts") +
        '</h2><div class="ai-alert-list">' + deferred_cards + '</div></section>'
        + '<section class="ai-monitor-section"><h2>' + _loc("OS·스토어 정책 변경 모니터링", "OS & store policy monitoring") +
        '</h2><div class="ai-row-list">' + change_rows + '</div><p class="ai-meta">' +
        _loc("분석 작업 수는 실제 문제·조치 필요 건수와 달라요.", "Task counts do not equal actionable incidents.") + '</p></section>'
        + '<section class="ai-monitor-section"><h2>' + _loc("세부 운영 지표", "Detailed operations") +
        '</h2>' + qa_notice + '<div class="ai-groups">' + ''.join(groups) + extras + '</div></section>'
        + '<p class="ai-meta">' + _loc("표시값은 마지막 보고서 스냅샷 기준이에요. 수집 결과와 품질 판정을 구분해요.",
                                     "Values reflect the last report snapshot. Collection and quality verification are separate.") + '</p>'
    )
