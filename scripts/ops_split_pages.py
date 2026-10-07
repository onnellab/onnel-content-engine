#!/usr/bin/env python3
"""Build the split ONNELLAB Ops information architecture around the legacy console."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ACCENT_PALETTE = (
    ("#cfd8cc", "#f3f6ef", "#4d6248"),
    ("#d9cfc7", "#f7f1ec", "#6a5548"),
    ("#d5d1c4", "#f6f3ea", "#635d48"),
    ("#cbd6d7", "#eef5f5", "#486163"),
    ("#d7cfdb", "#f4eff5", "#614f68"),
    ("#cdd3dc", "#f0f3f7", "#4b5b70"),
    ("#d8d0c5", "#f7f2eb", "#665846"),
    ("#d2d6c7", "#f4f6ed", "#5a6246"),
    ("#d6c9c9", "#f7efef", "#6b4f4f"),
    ("#c8d6cf", "#eef6f2", "#4a6357"),
    ("#d8d4c9", "#f7f4ec", "#655f4d"),
    ("#cfd2dc", "#f1f3f8", "#505b73"),
    ("#d6cdd2", "#f7f0f3", "#674f5b"),
)
ACCENT_OVERRIDES = {
    "tagweaver": ("#ded2b5", "#fbf7ec", "#6a5a2e"),
    "vaultxt": ("#c8d6cf", "#eef6f2", "#4a6357"),
    "clipnest": ("#d6c9c9", "#f7efef", "#6b4f4f"),
}

OPS_BASE_CSS = r"""
:root{
  --ink:#191714;--muted:#746f69;--line:#ded6ca;--surface:#fffaf5;--panel:#fff;
  --blue:#2e6fbb;--blue-soft:#e8f1fb;--lilac:#d8cdf7;--lilac-soft:#f4f0ff;
  --peach:#f4c3b4;--peach-soft:#fff0ea;--sky:#cfe6ff;--sky-soft:#eef7ff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;word-break:keep-all}
a{color:inherit}
.ops-wrap{max-width:1180px;margin:0 auto;padding:22px 20px 56px}
.ops-nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:30px}
.ops-nav a{display:inline-flex;align-items:center;min-height:38px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#fffdf9;color:#5d574f;text-decoration:none;font-size:13px;font-weight:750}
.ops-nav a[aria-current="page"]{border-color:#b9cbe0;background:var(--blue-soft);color:#315f91}
.ops-nav a:hover{border-color:#b9cbe0;background:var(--blue-soft)}
.ops-head{margin:10px 0 28px}
.ops-head .eyebrow{margin:0 0 10px;color:#827d72;font-size:12px;font-weight:680;letter-spacing:.08em;text-transform:uppercase}
.ops-head h1{margin:0;color:#36332f;font-size:34px;line-height:1.12}
.ops-head p{max-width:760px;margin:14px 0 0;color:#5b574f;font-size:16px;line-height:1.65}
.ops-route-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.ops-route-card{display:block;min-height:140px;padding:20px;border:1px solid var(--line);border-radius:12px;background:#fff;text-decoration:none;transition:transform 140ms ease,border-color 140ms ease,box-shadow 140ms ease}
.ops-route-card:hover{transform:translateY(-2px);border-color:#cfc5b7;box-shadow:0 10px 22px rgba(58,49,38,.055)}
.ops-route-card b{display:block;font-size:20px;margin-bottom:8px;color:#3e3933}
.ops-route-card span{display:block;color:#6f695f;font-size:14px;line-height:1.55}
.ops-route-card small{display:block;margin-top:18px;color:#817b72;font-size:12px;font-weight:700}
.ops-legacy-link{margin-top:22px;font-size:12px;color:#827d72}
.ops-legacy-link a{font-weight:750}
.app-search{display:grid;gap:8px;max-width:360px;margin-bottom:28px;color:#6f695f;font-size:13px;font-weight:620}
.app-search input{min-height:44px;border:1px solid #ded6ca;border-radius:8px;padding:9px 12px;background:rgba(255,253,248,.78);color:#3f3b35;font:inherit;font-weight:500}
.app-search input:focus{border-color:#cfc5b7;outline:2px solid #827d72;outline-offset:3px}
.app-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.app-card{position:relative;display:grid;grid-template-columns:54px minmax(0,1fr);align-items:start;gap:16px;min-height:128px;border:1px solid var(--accent-border,#e0d8cb);border-radius:11px;padding:18px;background:linear-gradient(135deg,rgba(255,253,248,.96) 16%,var(--accent-bg,#fffdf8)),#fffdf8;color:inherit;text-decoration:none;transition:transform 140ms ease,border-color 140ms ease,background 140ms ease,box-shadow 140ms ease}
.app-card[hidden]{display:none}
.app-card:hover,.app-card:focus-visible{border-color:var(--accent-border,#d8cec0);background:linear-gradient(135deg,#fffdf8 10%,var(--accent-bg,#fffdf8) 92%),#fffdf8;box-shadow:0 10px 22px rgba(58,49,38,.055);transform:translateY(-2px)}
.app-card:focus-visible{outline:2px solid #827d72;outline-offset:3px}
.app-card>img{width:52px;height:52px;border-radius:13px;box-shadow:0 0 0 1px var(--accent-border,#ddd5c8);object-fit:cover}
.app-copy{min-width:0}.title-row{display:flex;align-items:center;flex-wrap:wrap;gap:7px 10px}.title-row h2{margin:0;color:#3e3933;font-size:19px;line-height:1.25}
.status-badge{border:1px solid transparent;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:650;line-height:1.35;white-space:nowrap}
.status-badge[data-status-kind="released"]{border-color:#c9d8d2;background:#edf5f2;color:#49645a}
.status-badge[data-status-kind="preparing"]{border-color:#e1cfc5;background:#f9eee8;color:#765849}
.app-copy>p{margin:8px 0 0;color:#5f5a50;font-size:14px;line-height:1.55}
.platform-badges{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}
.platform-badges span{border:1px solid var(--accent-border,#ddd5c8);border-radius:999px;padding:2px 7px;background:color-mix(in srgb,var(--accent-bg,#faf8f5) 80%,#fffdf8);color:var(--accent-text,#737067);font-size:11px;line-height:1.4}
.ops-meta{margin-top:10px;color:#827d72;font-size:11px;line-height:1.45}
.detail-hero{display:grid;grid-template-columns:68px minmax(0,1fr);gap:18px;align-items:start;padding:22px;border:1px solid var(--accent-border,#e0d8cb);border-radius:13px;background:linear-gradient(135deg,rgba(255,253,248,.96) 16%,var(--accent-bg,#fffdf8)),#fffdf8}
.detail-hero img{width:64px;height:64px;border-radius:15px;box-shadow:0 0 0 1px var(--accent-border,#ddd5c8)}
.detail-hero h1{margin:0 0 8px;font-size:30px;color:#3e3933}.detail-hero p{margin:8px 0 0;color:#5f5a50;line-height:1.6}
.detail-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 22px}.detail-tabs a{min-height:36px;display:inline-flex;align-items:center;padding:7px 11px;border:1px solid var(--line);border-radius:999px;background:#fff;text-decoration:none;font-size:12px;font-weight:750;color:#6a645b}
.detail-section{margin-top:18px;padding:20px;border:1px solid var(--line);border-radius:12px;background:#fff}.detail-section h2{margin:0 0 14px;font-size:19px}.detail-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.detail-stat{padding:14px;border:1px solid #e8e0d7;border-radius:9px;background:#fffdf9}.detail-stat span{display:block;color:#827d72;font-size:11px}.detail-stat b{display:block;margin-top:6px;font-size:18px;overflow-wrap:anywhere}
.detail-list{display:grid;gap:8px}.detail-row{padding:12px;border:1px solid #e8e0d7;border-radius:9px;background:#fffdf9}.detail-row b{display:block;margin-bottom:5px;font-size:13px}.detail-row span{display:block;color:#6f695f;font-size:12px;line-height:1.55;overflow-wrap:anywhere}
.empty-note{padding:15px;border:1px dashed #d9d0c6;border-radius:9px;background:#fffdf9;color:#746f69;font-size:13px;line-height:1.6}
@media(max-width:680px){.ops-wrap{padding:18px 15px 42px}.ops-route-grid,.app-grid{grid-template-columns:1fr}.app-grid{gap:10px}.app-card{grid-template-columns:46px minmax(0,1fr);gap:13px;min-height:0;padding:15px}.app-card>img{width:44px;height:44px;border-radius:11px}.detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-hero{grid-template-columns:54px minmax(0,1fr);padding:17px}.detail-hero img{width:52px;height:52px;border-radius:12px}.ops-head h1{font-size:29px}}
"""


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _hash_slug(value: str) -> int:
    result = 0
    for char in value:
        result = ((result * 31) + ord(char)) & 0xFFFFFFFF
    return result


def _accent(slug: str) -> tuple[str, str, str]:
    return ACCENT_OVERRIDES.get(slug, ACCENT_PALETTE[_hash_slug(slug) % len(ACCENT_PALETTE)])


def _accent_style(slug: str) -> str:
    border, background, text = _accent(slug)
    return f"--accent-border:{border};--accent-bg:{background};--accent-text:{text};"


def _nav(current: str) -> str:
    entries = (
        ("home", "/ops/", "홈"),
        ("apps", "/ops/apps/", "앱"),
        ("publishing", "/ops/publishing/", "게시"),
        ("media", "/ops/media/", "미디어"),
        ("settings", "/ops/settings/", "설정"),
    )
    links = []
    for key, href, label in entries:
        current_attr = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{href}"{current_attr}>{label}</a>')
    return '<nav class="ops-nav" aria-label="ONNELLAB Ops">' + "".join(links) + "</nav>"


def _page(title: str, current: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)} · ONNELLAB Ops</title>
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>{OPS_BASE_CSS}</style>
</head>
<body>
<main class="ops-wrap">
{_nav(current)}
{body}
</main>
</body>
</html>
"""


def _home_body(app_count: int, publication_attention: int) -> str:
    return f"""
<header class="ops-head">
  <p class="eyebrow">Operations</p>
  <h1>ONNELLAB Ops</h1>
  <p>홈에서는 상황만 빠르게 보고, 실제 관리는 앱·게시·미디어·설정 페이지에서 나눠서 해요.</p>
</header>
<section class="ops-route-grid" aria-label="운영 메뉴">
  <a class="ops-route-card" href="/ops/apps/"><b>앱</b><span>스토어 상태, 릴리즈, 리뷰, 가격과 앞으로의 유입 퍼널을 앱별로 모아봐요.</span><small>{app_count} apps</small></a>
  <a class="ops-route-card" href="/ops/publishing/"><b>게시</b><span>블로그·소셜 발행 대기와 공개 확인, 사이트 갱신 및 발행 품질을 관리해요.</span><small>{publication_attention} items need attention</small></a>
  <a class="ops-route-card" href="/ops/media/"><b>미디어</b><span>ONNELLAB Shorts와 Aether Inn 채널, YouTube·Lyria 연결 상태를 따로 봐요.</span><small>2 brands</small></a>
  <a class="ops-route-card" href="/ops/settings/"><b>설정</b><span>자동 포스팅과 App Store / Play Store 연결 정보를 관리해요.</span><small>Connections</small></a>
</section>
<p class="ops-legacy-link">이전 전체 화면이 필요한 동안에는 <a href="/ops/legacy/">기존 통합 콘솔</a>도 남겨둬요.</p>
"""


def _absolutize_legacy_assets(document: str) -> str:
    return (
        document.replace('href="./manifest.webmanifest"', 'href="/ops/manifest.webmanifest"')
        .replace('href="./icon-180.png', 'href="/ops/icon-180.png')
        .replace('src="./libsodium-sumo.js"', 'src="/ops/libsodium-sumo.js"')
        .replace('src="./libsodium-wrappers.js"', 'src="/ops/libsodium-wrappers.js"')
        .replace("navigator.serviceWorker.register('./sw.js')", "navigator.serviceWorker.register('/ops/sw.js')")
    )


def _legacy_view(document: str, view: str, intro: str) -> str:
    document = _absolutize_legacy_assets(document)
    document = document.replace("<body>", f'<body data-ops-view="{_esc(view)}">', 1)
    document = document.replace("<main>", "<main>" + _nav(view) + intro, 1)
    title = {
        "home": "ONNELLAB Ops",
        "publishing": "게시 · ONNELLAB Ops",
        "media": "미디어 · ONNELLAB Ops",
        "settings": "설정 · ONNELLAB Ops",
        "legacy": "기존 통합 콘솔 · ONNELLAB Ops",
    }.get(view, "ONNELLAB Ops")
    document = document.replace("<title>ONNELLAB Ops Dashboard</title>", f"<title>{_esc(title)}</title>", 1)
    if view != "legacy":
        document = document.replace("appTitle: 'ONNELLAB 게시 상태 대시보드'", "appTitle: 'ONNELLAB Ops'")
        document = document.replace("appTitle: 'ONNELLAB Publish Status Dashboard'", "appTitle: 'ONNELLAB Ops'")
    view_css = r"""
<style>
main>.ops-nav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 22px}
main>.ops-nav a{display:inline-flex;align-items:center;min-height:38px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#fffdf9;color:#5d574f;text-decoration:none;font-size:13px;font-weight:750}
main>.ops-nav a[aria-current="page"]{border-color:#b9cbe0;background:var(--blue-soft);color:#315f91}
.ops-view-intro{margin:6px 0 22px;padding:18px 20px;border:1px solid var(--line);border-radius:10px;background:#fff}
.ops-view-intro h1{margin:0 0 7px;font-size:26px}.ops-view-intro p{margin:0;color:var(--muted);font-size:14px;line-height:1.6}
main>.ops-head{margin:6px 0 24px}main>.ops-head .eyebrow{margin:0 0 9px;color:#827d72;font-size:12px;font-weight:680;letter-spacing:.08em;text-transform:uppercase}
main>.ops-head h1{margin:0;color:#36332f;font-size:34px;line-height:1.12}main>.ops-head>p:last-child{max-width:760px;margin:12px 0 0;color:#5b574f;font-size:15px;line-height:1.65}
main>.ops-route-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:20px}
main>.ops-route-grid>.ops-route-card{display:block;min-height:140px;padding:20px;border:1px solid var(--line);border-radius:12px;background:#fff;color:inherit;text-decoration:none;transition:transform 140ms ease,border-color 140ms ease,box-shadow 140ms ease}
main>.ops-route-grid>.ops-route-card:hover{transform:translateY(-2px);border-color:#cfc5b7;box-shadow:0 10px 22px rgba(58,49,38,.055)}
main>.ops-route-grid>.ops-route-card b{display:block;font-size:20px;margin-bottom:8px;color:#3e3933}
main>.ops-route-grid>.ops-route-card span{display:block;color:#6f695f;font-size:14px;line-height:1.55}
main>.ops-route-grid>.ops-route-card small{display:block;margin-top:18px;color:#817b72;font-size:12px;font-weight:700}
main>.ops-legacy-link{margin:0 0 22px;color:#827d72;font-size:12px}main>.ops-legacy-link a{font-weight:750}
@media(max-width:680px){main>.ops-route-grid{grid-template-columns:1fr}main>.ops-head h1{font-size:29px}}
body[data-ops-view="home"] main>.overview,
body[data-ops-view="home"] main>.atm-action,
body[data-ops-view="home"] main>.ytw,
body[data-ops-view="home"] main>.yt-settings,
body[data-ops-view="home"] main>.tool-panel,
body[data-ops-view="home"] main>.credential-panel,
body[data-ops-view="home"] main>#grid,
body[data-ops-view="home"] main>#empty,
body[data-ops-view="home"] main>.platform-status,
body[data-ops-view="home"] main>.status-section{display:none!important}
body[data-ops-view="publishing"] main>.ytw,
body[data-ops-view="publishing"] main>.yt-settings,
body[data-ops-view="publishing"] main>.credential-panel,
body[data-ops-view="publishing"] details[aria-label="App operation status"],
body[data-ops-view="publishing"] details[aria-label="AI operation status"],
body[data-ops-view="publishing"] details[aria-label="Store customer reviews"],
body[data-ops-view="publishing"] details[aria-label="Paid product pricing status"]{display:none!important}
body[data-ops-view="media"] main>.overview,
body[data-ops-view="media"] main>.atm-action,
body[data-ops-view="media"] main>.tool-panel,
body[data-ops-view="media"] main>.credential-panel,
body[data-ops-view="media"] main>#grid,
body[data-ops-view="media"] main>#empty,
body[data-ops-view="media"] main>.platform-status,
body[data-ops-view="media"] main>.status-section{display:none!important}
body[data-ops-view="settings"] main>.overview,
body[data-ops-view="settings"] main>.atm-action,
body[data-ops-view="settings"] main>.ytw,
body[data-ops-view="settings"] main>.yt-settings,
body[data-ops-view="settings"] main>.tool-panel,
body[data-ops-view="settings"] main>#grid,
body[data-ops-view="settings"] main>#empty,
body[data-ops-view="settings"] main>.platform-status,
body[data-ops-view="settings"] main>.status-section{display:none!important}
</style>
"""
    return document.replace("</head>", view_css + "</head>", 1)


def _app_icon_path(homepage_repo: Path, slug: str) -> str:
    if slug == "papira":
        return "/app-assets/papira/icon.png"
    app_md = homepage_repo / "src" / "content" / "apps" / slug / "app.md"
    if not app_md.exists():
        return "/favicon.svg"
    match = re.search(r"^icon:\s*(.+?)\s*$", app_md.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        return "/favicon.svg"
    relative = match.group(1).strip().replace("\\", "/").lstrip("/")
    return f"/app-assets/{slug}/{relative}"


def _app_summary(app: Mapping[str, object], store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]]) -> str:
    slug = str(app.get("slug") or "")
    stores = [item for item in store_items if str(item.get("app_slug") or "") == slug]
    app_releases = [item for item in releases if str(item.get("app_slug") or "") == slug]
    deps = [item for item in dependencies if str(item.get("app_slug") or "") == slug]
    version = next(
        (
            str(item.get("resolved_version") or item.get("declared_version") or "")
            for item in deps
            if str(item.get("package_type") or "") == "app_version"
        ),
        "",
    )
    plugin_count = sum(
        1
        for item in deps
        if str(item.get("package_type") or "") != "app_version"
        and not (
            str(item.get("package_type") or "") == "dependency"
            and str(item.get("declared_version") or "") == "sdk:flutter"
        )
    )
    parts = [f"repo {version or '—'}", f"{len(stores)} stores", f"{len(app_releases)} releases", f"{plugin_count} plugins"]
    return " · ".join(parts)


def _app_card(app: Mapping[str, object], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]]) -> str:
    slug = str(app.get("slug") or "")
    title = str(app.get("app_name") or slug)
    status = str(app.get("status") or "")
    status_kind = "released" if status == "released" else "preparing"
    status_label = "Released" if status_kind == "released" else "Preparing for release"
    description = str(app.get("one_line_description") or "")
    platforms = [value.strip() for value in str(app.get("platforms") or "").split("|") if value.strip()]
    badges = "".join(f"<span>{_esc('iOS' if value == 'ios' else 'Android' if value == 'android' else value)}</span>" for value in platforms)
    return f"""
<a class="app-card" href="/ops/apps/{_esc(slug)}/" style="{_accent_style(slug)}" data-app-row data-app-title="{_esc(title.lower())}">
  <img src="{_esc(_app_icon_path(homepage_repo, slug))}" alt="" width="64" height="64" loading="lazy">
  <div class="app-copy">
    <div class="title-row"><h2>{_esc(title)}</h2><span class="status-badge" data-status-kind="{status_kind}">{status_label}</span></div>
    <p>{_esc(description)}</p>
    <div class="platform-badges" aria-label="Platforms">{badges}</div>
    <div class="ops-meta">{_esc(_app_summary(app, store_items, releases, dependencies))}</div>
  </div>
</a>
"""


def _apps_index(apps: Sequence[Mapping[str, object]], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]]) -> str:
    cards = "".join(_app_card(app, homepage_repo, store_items, releases, dependencies) for app in sorted(apps, key=lambda item: str(item.get("app_name") or "").lower()))
    body = f"""
<header class="ops-head">
  <p class="eyebrow">Apps</p>
  <h1>앱 관리</h1>
  <p>앱별 상태를 한곳에서 비교하고, 세부 운영 정보는 각 앱 페이지에서 확인해요.</p>
</header>
<label class="app-search"><span>앱 찾기</span><input type="search" placeholder="앱 이름을 검색해요" data-app-search></label>
<p class="empty-note" data-app-empty hidden>일치하는 앱이 없어요.</p>
<section class="app-grid" aria-label="앱 목록">{cards}</section>
<p class="ops-legacy-link">이전 상세 조작이 필요한 항목은 <a href="/ops/legacy/">기존 통합 콘솔</a>에서 계속 사용할 수 있어요.</p>
<script>
(()=>{{const input=document.querySelector('[data-app-search]');const rows=[...document.querySelectorAll('[data-app-row]')];if(!(input instanceof HTMLInputElement))return;input.addEventListener('input',()=>{{const q=input.value.trim().toLowerCase();let visible=0;for(const row of rows){{const hide=q&&!String(row.dataset.appTitle||'').includes(q);row.hidden=!!hide;if(!hide)visible++;}}const empty=document.querySelector('[data-app-empty]');if(empty instanceof HTMLElement)empty.hidden=visible>0;}});}})();
</script>
"""
    return _page("앱", "apps", body)


def _match(item: Mapping[str, object], app: Mapping[str, object]) -> bool:
    slug = str(app.get("slug") or "")
    app_id = str(app.get("app_id") or "")
    return str(item.get("app_slug") or "") == slug or (app_id and str(item.get("app_id") or "") == app_id)


def _store_stat(store_items: Sequence[Mapping[str, object]], platform: str) -> tuple[str, str]:
    item = next((row for row in store_items if str(row.get("platform") or "") == platform), None)
    if not item:
        return ("—", "수집 기록 없음")
    version = str(item.get("version") or "—")
    status = str(item.get("status") or "—")
    return (version, status)


def _app_detail(app: Mapping[str, object], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], reviews: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]], pricing: Sequence[Mapping[str, object]]) -> str:
    slug = str(app.get("slug") or "")
    title = str(app.get("app_name") or slug)
    app_stores = [item for item in store_items if _match(item, app)]
    app_releases = [item for item in releases if _match(item, app)]
    app_reviews = [item for item in reviews if _match(item, app)]
    app_deps = [item for item in dependencies if _match(item, app)]
    app_prices = [item for item in pricing if str(item.get("app_slug") or "") == slug]
    ios_version, ios_status = _store_stat(app_stores, "ios")
    android_version, android_status = _store_stat(app_stores, "android")
    repo_version = next((str(item.get("resolved_version") or item.get("declared_version") or "—") for item in app_deps if str(item.get("package_type") or "") == "app_version"), "—")
    latest_release = next((str(item.get("tag") or item.get("version") or "—") for item in reversed(app_releases)), "—")
    pending_reviews = sum(1 for item in app_reviews if str(item.get("status") or "") != "replied" and not item.get("developer_reply"))
    platform_badges = "".join(f"<span>{_esc('iOS' if value == 'ios' else 'Android' if value == 'android' else value)}</span>" for value in str(app.get("platforms") or "").split("|") if value)
    store_rows = "".join(
        f'<div class="detail-row"><b>{"App Store" if str(item.get("platform") or "") == "ios" else "Play Store"}</b><span>버전 {_esc(item.get("version") or "—")} · {_esc(item.get("status") or "—")} · 확인 {_esc(item.get("checked_at") or "—")}</span></div>'
        for item in app_stores
    ) or '<div class="empty-note">스토어 상태 기록이 없어요.</div>'
    price_rows = "".join(
        f'<div class="detail-row"><b>{_esc(item.get("product_name") or "Product")}</b><span>{_esc(item.get("price") or "—")} {_esc(item.get("currency") or "")} · {_esc(item.get("product_type") or "")}</span></div>'
        for item in app_prices
    ) or '<div class="empty-note">등록된 유료 제품 가격이 없어요.</div>'
    dependency_names = [
        str(item.get("package_name") or "")
        for item in app_deps
        if str(item.get("package_type") or "") != "app_version"
        and not (
            str(item.get("package_type") or "") == "dependency"
            and str(item.get("declared_version") or "") == "sdk:flutter"
        )
    ]
    dependency_text = ", ".join(dependency_names[:8]) + ("…" if len(dependency_names) > 8 else "")
    body = f"""
<header class="ops-head"><p class="eyebrow">App Operations</p><a href="/ops/apps/" style="font-size:13px;color:#746f69;text-decoration:none">← 앱 목록</a></header>
<section class="detail-hero" style="{_accent_style(slug)}">
  <img src="{_esc(_app_icon_path(homepage_repo, slug))}" alt="" width="64" height="64">
  <div><div class="title-row"><h1>{_esc(title)}</h1><span class="status-badge" data-status-kind="{'released' if str(app.get('status') or '') == 'released' else 'preparing'}">{'Released' if str(app.get('status') or '') == 'released' else 'Preparing for release'}</span></div><p>{_esc(app.get("one_line_description") or "")}</p><div class="platform-badges">{platform_badges}</div></div>
</section>
<nav class="detail-tabs" aria-label="앱 세부"><a href="#overview">개요</a><a href="#funnel">유입·전환</a><a href="#store">스토어·수익</a><a href="#reviews">리뷰</a><a href="#technical">기술·운영</a></nav>
<section class="detail-section" id="overview"><h2>개요</h2><div class="detail-grid">
  <div class="detail-stat"><span>App Store</span><b>{_esc(ios_version)}</b><span>{_esc(ios_status)}</span></div>
  <div class="detail-stat"><span>Play Store</span><b>{_esc(android_version)}</b><span>{_esc(android_status)}</span></div>
  <div class="detail-stat"><span>GitHub main</span><b>{_esc(repo_version)}</b></div>
  <div class="detail-stat"><span>최근 릴리즈</span><b>{_esc(latest_release)}</b></div>
</div></section>
<section class="detail-section" id="funnel"><h2>유입·전환</h2><div class="empty-note">스토어 분석 수집을 붙일 자리예요. 통합 기준은 양 스토어에서 비교 가능한 상세 페이지 유입 → 설치 → 결제로 두고, Apple 노출은 iOS 전용 상위 퍼널로 분리해요.</div></section>
<section class="detail-section" id="store"><h2>스토어·수익</h2><div class="detail-list">{store_rows}{price_rows}</div></section>
<section class="detail-section" id="reviews"><h2>리뷰</h2><div class="detail-grid"><div class="detail-stat"><span>수집 리뷰</span><b>{len(app_reviews)}</b></div><div class="detail-stat"><span>답변 대기</span><b>{pending_reviews}</b></div></div></section>
<section class="detail-section" id="technical"><h2>기술·운영</h2><div class="detail-list"><div class="detail-row"><b>Flutter / 플러그인</b><span>{len(dependency_names)} rows · {_esc(dependency_text or "표시할 플러그인 없음")}</span></div><div class="detail-row"><b>고급 운영</b><span><a href="/ops/legacy/">기존 통합 콘솔에서 릴리즈 승인·리뷰 답변 등 기존 조작을 계속 사용할 수 있어요.</a></span></div><div class="detail-row"><b>공개 제품 페이지</b><span><a href="/apps/{_esc(slug)}/">onnellab.com/apps/{_esc(slug)}</a></span></div></div></section>
"""
    return _page(title, "apps", body)


def build_split_ops_pages(
    output_dir: Path,
    *,
    legacy_html: str,
    homepage_repo: Path,
    apps: Sequence[Mapping[str, object]],
    publication_items: Sequence[Mapping[str, object]],
    releases: Sequence[Mapping[str, object]],
    store_items: Sequence[Mapping[str, object]],
    reviews: Sequence[Mapping[str, object]],
    dependencies: Sequence[Mapping[str, object]],
    pricing: Sequence[Mapping[str, object]],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    attention = sum(1 for item in publication_items if str(item.get("status") or "") in {"draft", "failed"})
    home_intro = _home_body(len(apps), attention)
    pages: list[Path] = []
    views = {
        "home": (output_dir / "index.html", home_intro),
        "publishing": (output_dir / "publishing" / "index.html", '<section class="ops-view-intro"><h1>게시</h1><p>발행 대기, 공개 확인, 사이트 갱신과 발행 품질만 모아봐요.</p></section>'),
        "media": (output_dir / "media" / "index.html", '<section class="ops-view-intro"><h1>미디어</h1><p>ONNELLAB Shorts와 Aether Inn 운영을 게시 대시보드에서 분리했어요.</p></section>'),
        "settings": (output_dir / "settings" / "index.html", '<section class="ops-view-intro"><h1>설정</h1><p>자동 포스팅과 스토어 연결 정보를 여기에서 관리해요.</p></section>'),
        "legacy": (output_dir / "legacy" / "index.html", '<section class="ops-view-intro"><h1>기존 통합 콘솔</h1><p>분리 이전의 전체 기능을 그대로 보존한 화면이에요. 새 구조 이관이 끝날 때까지 안전망으로 유지해요.</p></section>'),
    }
    for view, (path, intro) in views.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_legacy_view(legacy_html, view, intro), encoding="utf-8")
        pages.append(path)

    apps_dir = output_dir / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    apps_index = apps_dir / "index.html"
    apps_index.write_text(_apps_index(apps, homepage_repo, store_items, releases, dependencies), encoding="utf-8")
    pages.append(apps_index)

    for app in apps:
        slug = str(app.get("slug") or "")
        if not slug:
            continue
        app_dir = apps_dir / slug
        app_dir.mkdir(parents=True, exist_ok=True)
        app_path = app_dir / "index.html"
        app_path.write_text(_app_detail(app, homepage_repo, store_items, releases, reviews, dependencies, pricing), encoding="utf-8")
        pages.append(app_path)
    return pages
