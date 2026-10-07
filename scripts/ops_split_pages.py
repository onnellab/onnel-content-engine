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

APP_DESCRIPTION_KO_FALLBACK = {
    "aligna": "파일 이름을 규칙대로 한 번에 정리해요.",
    "clipnest": "클립보드와 자주 쓰는 문구를 저장해 빠르게 다시 붙여넣어요.",
    "melivra": "로컬 음악을 정리하고 재생하는 오프라인 음악 플레이어예요.",
    "papira": "완성된 TXT 원고를 EPUB 전자책으로 만드는 오프라인 제작 도구예요.",
    "quivra": "WAV·M4A·MP4·MOV 파일을 간단하게 변환해요.",
    "segra": "MP3와 WAV 오디오를 자르고, 합치고, 영상으로 만들어요.",
    "tagweaver": "MP3/FLAC 태그·평점·앨범 아트·가사를 오프라인으로 편집해요.",
    "vaultxt": "대용량 텍스트를 로컬에서 편집하고 자동저장, 검색, 스냅샷으로 관리해요.",
}

STORE_STATUS_KO = {
    "unchanged": "변경 없음",
    "new": "신규",
    "updated": "업데이트",
    "in_review": "심사 중",
    "not_found": "미확인",
    "error": "오류",
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
.ops-topbar{position:sticky;top:0;z-index:10;border-bottom:1px solid rgba(221,212,202,.85);background:rgba(255,250,245,.94);backdrop-filter:blur(14px)}
.ops-bar{max-width:1180px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.ops-brand{display:flex;align-items:center;gap:10px;font-weight:800;color:inherit;text-decoration:none}
.ops-mark{width:32px;height:32px;display:block;object-fit:contain}
.ops-lang{min-height:31px;border:1px solid var(--ink);background:var(--ink);color:#fff;padding:6px 10px;border-radius:999px;font:inherit;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap}
.ops-lang:focus-visible{outline:2px solid var(--blue);outline-offset:3px}
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
.funnel-controls{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 14px}.funnel-controls button{min-height:34px;border:1px solid var(--line);border-radius:999px;padding:6px 11px;background:#fff;color:#625c54;font:inherit;font-size:12px;font-weight:750;cursor:pointer}.funnel-controls button.is-active{border-color:#b9cbe0;background:var(--blue-soft);color:#315f91}
.funnel-window[hidden]{display:none}.funnel-platform-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.funnel-card{padding:15px;border:1px solid #e8e0d7;border-radius:10px;background:#fffdf9}.funnel-card h3{margin:0 0 12px;font-size:15px}.funnel-chain{display:flex;align-items:stretch;gap:7px}.funnel-step{flex:1;min-width:0;padding:10px;border:1px solid #e8e0d7;border-radius:8px;background:#fff}.funnel-step span{display:block;color:#827d72;font-size:10px;line-height:1.35}.funnel-step b{display:block;margin-top:5px;font-size:20px;line-height:1}.funnel-arrow{display:flex;align-items:center;color:#aaa196;font-size:15px}.funnel-purchase{margin-top:10px;padding-top:10px;border-top:1px solid #ece4dc;color:#6f695f;font-size:12px}.funnel-purchase b{color:#3e3933;font-size:15px}.funnel-freshness{margin-top:8px;color:#8a8379;font-size:10px}.funnel-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.funnel-summary .detail-stat{background:var(--lilac-soft)}.funnel-note{margin-top:12px;color:#746f69;font-size:11px;line-height:1.55}
@media(max-width:680px){.ops-wrap{padding:18px 15px 42px}.ops-route-grid,.app-grid{grid-template-columns:1fr}.app-grid{gap:10px}.app-card{grid-template-columns:46px minmax(0,1fr);gap:13px;min-height:0;padding:15px}.app-card>img{width:44px;height:44px;border-radius:11px}.detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-hero{grid-template-columns:54px minmax(0,1fr);padding:17px}.detail-hero img{width:52px;height:52px;border-radius:12px}.ops-head h1{font-size:29px}.funnel-platform-grid{grid-template-columns:1fr}.funnel-chain{gap:5px}.funnel-step{padding:8px}.funnel-step b{font-size:17px}}
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
        ("home", "/ops/", "홈", "Home"),
        ("apps", "/ops/apps/", "앱", "Apps"),
        ("publishing", "/ops/publishing/", "게시", "Publishing"),
        ("media", "/ops/media/", "미디어", "Media"),
        ("settings", "/ops/settings/", "설정", "Settings"),
    )
    links = []
    for key, href, ko_label, en_label in entries:
        current_attr = ' aria-current="page"' if key == current else ""
        links.append(
            f'<a href="{href}"{current_attr}><span data-ko="{_esc(ko_label)}" data-en="{_esc(en_label)}">{_esc(ko_label)}</span></a>'
        )
    return '<nav class="ops-nav" aria-label="ONNELLAB Ops">' + "".join(links) + "</nav>"


def _page(title: str, current: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)} · ONNELLAB Ops</title>
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet,noimageindex">
<link rel="icon" href="/favicon.svg?v=20260712-ol-transparent-v2" type="image/svg+xml">
<style>{OPS_BASE_CSS}</style>
</head>
<body>
<header class="ops-topbar">
  <div class="ops-bar">
    <a class="ops-brand" href="/" aria-label="ONNELLAB home">
      <img class="ops-mark" src="/favicon.svg?v=20260712-ol-transparent-v2" alt="" width="32" height="32">
      <span>ONNELLAB Ops</span>
    </a>
    <button class="ops-lang" id="ops-lang-toggle" type="button">English</button>
  </div>
</header>
<main class="ops-wrap">
{_nav(current)}
{body}
</main>
<script>
(() => {{
  const storageKey = 'onnellab-ops-language';
  let language = localStorage.getItem(storageKey) === 'en' ? 'en' : 'ko';
  const button = document.getElementById('ops-lang-toggle');
  const applyLanguage = () => {{
    document.documentElement.lang = language === 'en' ? 'en' : 'ko';
    document.querySelectorAll('[data-ko][data-en]').forEach((element) => {{
      element.textContent = language === 'en' ? element.dataset.en : element.dataset.ko;
    }});
    document.querySelectorAll('[data-placeholder-ko][data-placeholder-en]').forEach((element) => {{
      element.setAttribute('placeholder', language === 'en' ? element.dataset.placeholderEn : element.dataset.placeholderKo);
    }});
    if (button) button.textContent = language === 'en' ? '한국어' : 'English';
  }};
  if (button) button.addEventListener('click', () => {{
    language = language === 'en' ? 'ko' : 'en';
    localStorage.setItem(storageKey, language);
    applyLanguage();
  }});
  applyLanguage();
}})();
</script>
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
body[data-ops-view="publishing"] main>.credential-panel:not(.github-connection-panel),
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


def _ko_app_description(homepage_repo: Path, slug: str, fallback: str) -> str:
    description_path = homepage_repo / "src" / "content" / "apps" / slug / "description-ko.md"
    if description_path.exists():
        lines = description_path.read_text(encoding="utf-8").splitlines()
        for label in ("간단한 설명:", "랜딩 부제:", "부제:"):
            try:
                index = lines.index(label)
            except ValueError:
                continue
            for candidate in lines[index + 1:]:
                candidate = candidate.strip()
                if candidate:
                    return candidate
    return APP_DESCRIPTION_KO_FALLBACK.get(slug, fallback)


def _store_status_ko(value: object) -> str:
    text = str(value or "—")
    return STORE_STATUS_KO.get(text, text)


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


def _app_summary(
    app: Mapping[str, object],
    store_items: Sequence[Mapping[str, object]],
    releases: Sequence[Mapping[str, object]],
    dependencies: Sequence[Mapping[str, object]],
    language: str,
) -> str:
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
    if language == "ko":
        parts = [
            f"저장소 {version or '—'}",
            f"스토어 {len(stores)}개",
            f"릴리즈 {len(app_releases)}개",
            f"플러그인 {plugin_count}개",
        ]
    else:
        parts = [
            f"repo {version or '—'}",
            f"{len(stores)} stores",
            f"{len(app_releases)} releases",
            f"{plugin_count} plugins",
        ]
    return " · ".join(parts)


def _app_card(app: Mapping[str, object], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]]) -> str:
    slug = str(app.get("slug") or "")
    title = str(app.get("app_name") or slug)
    status = str(app.get("status") or "")
    status_kind = "released" if status == "released" else "preparing"
    status_ko = "출시됨" if status_kind == "released" else "출시 준비 중"
    status_en = "Released" if status_kind == "released" else "Preparing for release"
    description_en = str(app.get("one_line_description") or "")
    description_ko = _ko_app_description(homepage_repo, slug, description_en)
    summary_ko = _app_summary(app, store_items, releases, dependencies, "ko")
    summary_en = _app_summary(app, store_items, releases, dependencies, "en")
    platforms = [value.strip() for value in str(app.get("platforms") or "").split("|") if value.strip()]
    badges = "".join(f"<span>{_esc('iOS' if value == 'ios' else 'Android' if value == 'android' else value)}</span>" for value in platforms)
    return f"""
<a class="app-card" href="/ops/apps/{_esc(slug)}/" style="{_accent_style(slug)}" data-app-row data-app-title="{_esc(title.lower())}">
  <img src="{_esc(_app_icon_path(homepage_repo, slug))}" alt="" width="64" height="64" loading="lazy">
  <div class="app-copy">
    <div class="title-row"><h2>{_esc(title)}</h2><span class="status-badge" data-status-kind="{status_kind}" data-ko="{_esc(status_ko)}" data-en="{_esc(status_en)}">{_esc(status_ko)}</span></div>
    <p data-ko="{_esc(description_ko)}" data-en="{_esc(description_en)}">{_esc(description_ko)}</p>
    <div class="platform-badges" aria-label="Platforms">{badges}</div>
    <div class="ops-meta" data-ko="{_esc(summary_ko)}" data-en="{_esc(summary_en)}">{_esc(summary_ko)}</div>
  </div>
</a>
"""


def _apps_index(apps: Sequence[Mapping[str, object]], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]]) -> str:
    cards = "".join(_app_card(app, homepage_repo, store_items, releases, dependencies) for app in sorted(apps, key=lambda item: str(item.get("app_name") or "").lower()))
    body = f"""
<header class="ops-head">
  <p class="eyebrow" data-ko="앱" data-en="Apps">앱</p>
  <h1 data-ko="앱 관리" data-en="App management">앱 관리</h1>
  <p data-ko="앱별 상태를 한곳에서 비교하고, 세부 운영 정보는 각 앱 페이지에서 확인해요." data-en="Compare app status in one place and open each app for detailed operations.">앱별 상태를 한곳에서 비교하고, 세부 운영 정보는 각 앱 페이지에서 확인해요.</p>
</header>
<label class="app-search"><span data-ko="앱 찾기" data-en="Find an app">앱 찾기</span><input type="search" placeholder="앱 이름을 검색해요" data-placeholder-ko="앱 이름을 검색해요" data-placeholder-en="Search app name" data-app-search></label>
<p class="empty-note" data-app-empty hidden data-ko="일치하는 앱이 없어요." data-en="No matching apps.">일치하는 앱이 없어요.</p>
<section class="app-grid" aria-label="앱 목록">{cards}</section>
<p class="ops-legacy-link"><span data-ko="이전 상세 조작이 필요한 항목은" data-en="For legacy controls, keep using the">이전 상세 조작이 필요한 항목은</span> <a href="/ops/legacy/" data-ko="기존 통합 콘솔" data-en="legacy console">기존 통합 콘솔</a><span data-ko="에서 계속 사용할 수 있어요." data-en=".">에서 계속 사용할 수 있어요.</span></p>
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


def _bilingual_store_row(item: Mapping[str, object]) -> str:
    platform = "App Store" if str(item.get("platform") or "") == "ios" else "Play Store"
    version = str(item.get("version") or "—")
    status_en = str(item.get("status") or "—")
    status_ko = _store_status_ko(status_en)
    checked = str(item.get("checked_at") or "—")
    ko = f"버전 {version} · {status_ko} · 확인 {checked}"
    en = f"Version {version} · {status_en} · checked {checked}"
    return (
        f'<div class="detail-row"><b>{platform}</b>'
        f'<span data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</span></div>'
    )


def _bilingual_price_row(item: Mapping[str, object]) -> str:
    product_name = str(item.get("product_name") or "Product")
    price = str(item.get("price") or "—")
    currency = str(item.get("currency") or "")
    product_type = str(item.get("product_type") or "")
    type_ko = {
        "pro": "Pro",
        "paid_download": "유료 다운로드",
        "ai_credit": "AI 크레딧",
    }.get(product_type, product_type)
    ko = f"{price} {currency} · {type_ko}".strip()
    en = f"{price} {currency} · {product_type}".strip()
    return (
        f'<div class="detail-row"><b>{_esc(product_name)}</b>'
        f'<span data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</span></div>'
    )


def _funnel_number(value: object) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _funnel_source_message(
    funnel_summary: Mapping[str, object],
    source: str,
    slug: str,
) -> tuple[str, str]:
    source_status = funnel_summary.get("source_status", {})
    if not isinstance(source_status, Mapping):
        source_status = {}
    source_payload = source_status.get(source, {})
    if not isinstance(source_payload, Mapping):
        source_payload = {}
    status = str(source_payload.get("status") or "")
    if source == "apple":
        apps_payload = source_payload.get("apps", {})
        if isinstance(apps_payload, Mapping):
            app_payload = apps_payload.get(slug, {})
            if isinstance(app_payload, Mapping):
                app_status = str(app_payload.get("status") or "")
                if app_status == "waiting_for_snapshot":
                    return (
                        "Apple 과거 데이터 스냅샷을 생성하는 중이에요. 지난달을 포함한 사용 가능한 과거 데이터가 준비되면 자동으로 채워져요.",
                        "Apple is generating the historical snapshot. Available past data, including last month, will populate automatically when ready.",
                    )
                if app_status == "waiting_for_first_report":
                    return (
                        "Apple 첫 분석 보고서를 기다리는 중이에요. 최초 연결 후 보통 24~48시간이 걸려요.",
                        "Waiting for Apple's first analytics report. Initial setup usually takes 24–48 hours.",
                    )
                if app_status.startswith("setup_http_") or app_status == "setup_required":
                    return (
                        "App Store Connect 분석 보고서 요청 권한을 확인해 주세요.",
                        "Check permission to request App Store Connect analytics reports.",
                    )
                if app_status == "error":
                    message = str(app_payload.get("message") or "")
                    if "403" in message:
                        return (
                            "현재 App Store Connect API 키에 분석 보고서 권한이 없어요. 최초 연결에는 Admin 역할 API 키가 필요해요.",
                            "The current App Store Connect API key cannot access Analytics Reports. Initial setup requires an Admin-role API key.",
                        )
                    return (
                        "App Store Connect 분석 동기화 중 오류가 발생했어요.",
                        "App Store Connect analytics sync reported an error.",
                    )
        if status == "not_configured":
            return (
                "App Store Connect 분석 연결이 필요해요.",
                "App Store Connect analytics is not configured.",
            )
    if source == "google":
        if status == "not_configured":
            return (
                "Play Console 보고서 연결이 필요해요.",
                "Google Play reporting is not configured.",
            )
        if status == "error":
            return (
                "Play Console 보고서 동기화 중 오류가 발생했어요.",
                "Google Play report sync reported an error.",
            )
    return (
        "선택한 기간에 수집된 데이터가 아직 없어요.",
        "No data has been collected for this period yet.",
    )


def _funnel_step(label_ko: str, label_en: str, value: object) -> str:
    display = _funnel_number(value)
    return (
        '<div class="funnel-step">'
        f'<span data-ko="{_esc(label_ko)}" data-en="{_esc(label_en)}">{_esc(label_ko)}</span>'
        f"<b>{_esc(display)}</b>"
        "</div>"
    )


def _funnel_platform_card(
    *,
    title: str,
    platform_payload: Mapping[str, object],
    window: int,
    source: str,
    slug: str,
    funnel_summary: Mapping[str, object],
) -> tuple[str, Mapping[str, object] | None]:
    windows = platform_payload.get("windows", {})
    window_payload = windows.get(str(window), {}) if isinstance(windows, Mapping) else {}
    has_data = (
        isinstance(window_payload, Mapping)
        and int(window_payload.get("days_with_data") or 0) > 0
    )
    latest_date = str(platform_payload.get("latest_date") or "")
    if not has_data:
        ko, en = _funnel_source_message(funnel_summary, source, slug)
        return (
            f'<article class="funnel-card"><h3>{_esc(title)}</h3>'
            f'<div class="empty-note" data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</div>'
            "</article>",
            None,
        )

    assert isinstance(window_payload, Mapping)
    steps: list[str] = []
    if source == "apple":
        steps.extend(
            [
                _funnel_step("노출", "Impressions", window_payload.get("impressions")),
                '<div class="funnel-arrow" aria-hidden="true">→</div>',
                _funnel_step("제품 페이지 조회", "Product page views", window_payload.get("store_visitors")),
                '<div class="funnel-arrow" aria-hidden="true">→</div>',
                _funnel_step("최초 다운로드", "First-time downloads", window_payload.get("installs")),
            ]
        )
        purchase_ko, purchase_en = "구매", "Purchases"
    else:
        steps.extend(
            [
                _funnel_step("스토어 방문", "Store listing visitors", window_payload.get("store_visitors")),
                '<div class="funnel-arrow" aria-hidden="true">→</div>',
                _funnel_step("신규 설치", "First-time installers", window_payload.get("installs")),
            ]
        )
        purchase_ko, purchase_en = "구매", "Purchases"

    purchases = _funnel_number(window_payload.get("purchases"))
    days = int(window_payload.get("days_with_data") or 0)
    freshness_ko = f"데이터 {days}일분" + (f" · 최근 {latest_date}" if latest_date else "")
    freshness_en = f"{days} day(s) of data" + (f" · latest {latest_date}" if latest_date else "")
    return (
        f'<article class="funnel-card"><h3>{_esc(title)}</h3>'
        f'<div class="funnel-chain">{"".join(steps)}</div>'
        '<div class="funnel-purchase">'
        f'<span data-ko="{purchase_ko}" data-en="{purchase_en}">{purchase_ko}</span> '
        f"<b>{_esc(purchases)}</b></div>"
        f'<div class="funnel-freshness" data-ko="{_esc(freshness_ko)}" data-en="{_esc(freshness_en)}">{_esc(freshness_ko)}</div>'
        "</article>",
        window_payload,
    )


def _combined_metric(
    app_platforms: set[str],
    ios_window: Mapping[str, object] | None,
    android_window: Mapping[str, object] | None,
    metric: str,
) -> object:
    payloads: list[Mapping[str, object]] = []
    if "ios" in app_platforms:
        if ios_window is None or ios_window.get(metric) is None:
            return None
        payloads.append(ios_window)
    if "android" in app_platforms:
        if android_window is None or android_window.get(metric) is None:
            return None
        payloads.append(android_window)
    if not payloads:
        return None
    return sum(int(payload.get(metric) or 0) for payload in payloads)


def _funnel_section(
    app: Mapping[str, object],
    funnel_summary: Mapping[str, object],
) -> str:
    slug = str(app.get("slug") or "")
    apps_payload = funnel_summary.get("apps", {})
    app_payload = apps_payload.get(slug, {}) if isinstance(apps_payload, Mapping) else {}
    if not isinstance(app_payload, Mapping):
        app_payload = {}
    platforms = app_payload.get("platforms", {})
    if not isinstance(platforms, Mapping):
        platforms = {}
    ios_payload = platforms.get("ios", {})
    android_payload = platforms.get("android", {})
    if not isinstance(ios_payload, Mapping):
        ios_payload = {}
    if not isinstance(android_payload, Mapping):
        android_payload = {}
    app_platforms = {
        value.strip()
        for value in str(app.get("platforms") or "").split("|")
        if value.strip() in {"ios", "android"}
    }

    windows_html: list[str] = []
    for window in (7, 30, 90):
        apple_card, ios_window = _funnel_platform_card(
            title="App Store",
            platform_payload=ios_payload,
            window=window,
            source="apple",
            slug=slug,
            funnel_summary=funnel_summary,
        )
        google_card, android_window = _funnel_platform_card(
            title="Play Store",
            platform_payload=android_payload,
            window=window,
            source="google",
            slug=slug,
            funnel_summary=funnel_summary,
        )
        combined_installs = _combined_metric(app_platforms, ios_window, android_window, "installs")
        combined_purchases = _combined_metric(app_platforms, ios_window, android_window, "purchases")
        combined_available = combined_installs is not None or combined_purchases is not None
        if combined_available:
            combined_html = (
                '<div class="funnel-summary">'
                '<div class="detail-stat"><span data-ko="양 스토어 설치 합계" data-en="Combined installs">양 스토어 설치 합계</span>'
                f"<b>{_esc(_funnel_number(combined_installs))}</b></div>"
                '<div class="detail-stat"><span data-ko="양 스토어 구매 합계" data-en="Combined purchases">양 스토어 구매 합계</span>'
                f"<b>{_esc(_funnel_number(combined_purchases))}</b></div>"
                "</div>"
            )
        else:
            combined_html = (
                '<div class="funnel-note" data-ko="양 스토어 합계는 두 스토어의 해당 지표가 모두 수집된 경우에만 표시해요." '
                'data-en="Combined totals appear only when the required metric is available for every supported store.">'
                "양 스토어 합계는 두 스토어의 해당 지표가 모두 수집된 경우에만 표시해요.</div>"
            )
        hidden = "" if window == 30 else " hidden"
        windows_html.append(
            f'<div class="funnel-window" data-funnel-window="{window}"{hidden}>'
            f'<div class="funnel-platform-grid">{apple_card}{google_card}</div>'
            f"{combined_html}"
            '<div class="funnel-note" data-ko="스토어 방문·제품 페이지 조회의 정의가 달라 방문 수는 합산하지 않아요. Android에는 App Store의 노출과 동등한 공개 지표를 만들지 않아요." '
            'data-en="Store-visitor definitions differ, so visitor counts are not summed. Android does not invent an App-Store-equivalent impressions metric.">'
            "스토어 방문·제품 페이지 조회의 정의가 달라 방문 수는 합산하지 않아요. Android에는 App Store의 노출과 동등한 공개 지표를 만들지 않아요.</div>"
            "</div>"
        )

    return (
        '<section class="detail-section" id="funnel">'
        '<h2 data-ko="유입·전환" data-en="Acquisition & conversion">유입·전환</h2>'
        '<div class="funnel-controls" role="group" aria-label="기간">'
        '<button type="button" data-funnel-period="7" data-ko="7일" data-en="7 days">7일</button>'
        '<button type="button" data-funnel-period="30" class="is-active" data-ko="30일" data-en="30 days">30일</button>'
        '<button type="button" data-funnel-period="90" data-ko="90일" data-en="90 days">90일</button>'
        "</div>"
        + "".join(windows_html)
        + """<script>
(() => {
  const buttons = [...document.querySelectorAll('[data-funnel-period]')];
  const windows = [...document.querySelectorAll('[data-funnel-window]')];
  buttons.forEach((button) => button.addEventListener('click', () => {
    const period = button.dataset.funnelPeriod;
    buttons.forEach((item) => item.classList.toggle('is-active', item === button));
    windows.forEach((item) => { item.hidden = item.dataset.funnelWindow !== period; });
  }));
})();
</script></section>"""
    )


def _app_detail(app: Mapping[str, object], homepage_repo: Path, store_items: Sequence[Mapping[str, object]], releases: Sequence[Mapping[str, object]], reviews: Sequence[Mapping[str, object]], dependencies: Sequence[Mapping[str, object]], pricing: Sequence[Mapping[str, object]], funnel_summary: Mapping[str, object]) -> str:
    slug = str(app.get("slug") or "")
    title = str(app.get("app_name") or slug)
    description_en = str(app.get("one_line_description") or "")
    description_ko = _ko_app_description(homepage_repo, slug, description_en)
    status_kind = "released" if str(app.get("status") or "") == "released" else "preparing"
    status_ko = "출시됨" if status_kind == "released" else "출시 준비 중"
    status_en = "Released" if status_kind == "released" else "Preparing for release"
    app_stores = [item for item in store_items if _match(item, app)]
    app_releases = [item for item in releases if _match(item, app)]
    app_reviews = [item for item in reviews if _match(item, app)]
    app_deps = [item for item in dependencies if _match(item, app)]
    app_prices = [item for item in pricing if str(item.get("app_slug") or "") == slug]
    ios_version, ios_status = _store_stat(app_stores, "ios")
    android_version, android_status = _store_stat(app_stores, "android")
    ios_status_ko = _store_status_ko(ios_status)
    android_status_ko = _store_status_ko(android_status)
    ios_status_en = "No data" if ios_status == "수집 기록 없음" else ios_status
    android_status_en = "No data" if android_status == "수집 기록 없음" else android_status
    repo_version = next((str(item.get("resolved_version") or item.get("declared_version") or "—") for item in app_deps if str(item.get("package_type") or "") == "app_version"), "—")
    latest_release = next((str(item.get("tag") or item.get("version") or "—") for item in reversed(app_releases)), "—")
    pending_reviews = sum(1 for item in app_reviews if str(item.get("status") or "") != "replied" and not item.get("developer_reply"))
    platform_badges = "".join(f"<span>{_esc('iOS' if value == 'ios' else 'Android' if value == 'android' else value)}</span>" for value in str(app.get("platforms") or "").split("|") if value)
    store_rows = "".join(_bilingual_store_row(item) for item in app_stores) or (
        '<div class="empty-note" data-ko="스토어 상태 기록이 없어요." '
        'data-en="No store status is available.">스토어 상태 기록이 없어요.</div>'
    )
    price_rows = "".join(_bilingual_price_row(item) for item in app_prices) or (
        '<div class="empty-note" data-ko="등록된 유료 제품 가격이 없어요." '
        'data-en="No paid product price is registered.">등록된 유료 제품 가격이 없어요.</div>'
    )
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
    dependency_ko = f"{len(dependency_names)}개 · {dependency_text or '표시할 플러그인 없음'}"
    dependency_en = f"{len(dependency_names)} items · {dependency_text or 'No plugins to display'}"
    body = f"""
<header class="ops-head">
  <p class="eyebrow" data-ko="앱 운영" data-en="App Operations">앱 운영</p>
  <a href="/ops/apps/" style="font-size:13px;color:#746f69;text-decoration:none" data-ko="← 앱 목록" data-en="← Apps">← 앱 목록</a>
</header>
<section class="detail-hero" style="{_accent_style(slug)}">
  <img src="{_esc(_app_icon_path(homepage_repo, slug))}" alt="" width="64" height="64">
  <div>
    <div class="title-row"><h1>{_esc(title)}</h1><span class="status-badge" data-status-kind="{status_kind}" data-ko="{_esc(status_ko)}" data-en="{_esc(status_en)}">{_esc(status_ko)}</span></div>
    <p data-ko="{_esc(description_ko)}" data-en="{_esc(description_en)}">{_esc(description_ko)}</p>
    <div class="platform-badges">{platform_badges}</div>
  </div>
</section>
<nav class="detail-tabs" aria-label="앱 세부">
  <a href="#overview" data-ko="개요" data-en="Overview">개요</a>
  <a href="#funnel" data-ko="유입·전환" data-en="Acquisition">유입·전환</a>
  <a href="#store" data-ko="스토어·수익" data-en="Store & revenue">스토어·수익</a>
  <a href="#reviews" data-ko="리뷰" data-en="Reviews">리뷰</a>
  <a href="#technical" data-ko="기술·운영" data-en="Technical">기술·운영</a>
</nav>
<section class="detail-section" id="overview"><h2 data-ko="개요" data-en="Overview">개요</h2><div class="detail-grid">
  <div class="detail-stat"><span>App Store</span><b>{_esc(ios_version)}</b><span data-ko="{_esc(ios_status_ko)}" data-en="{_esc(ios_status_en)}">{_esc(ios_status_ko)}</span></div>
  <div class="detail-stat"><span>Play Store</span><b>{_esc(android_version)}</b><span data-ko="{_esc(android_status_ko)}" data-en="{_esc(android_status_en)}">{_esc(android_status_ko)}</span></div>
  <div class="detail-stat"><span>GitHub main</span><b>{_esc(repo_version)}</b></div>
  <div class="detail-stat"><span data-ko="최근 릴리즈" data-en="Latest release">최근 릴리즈</span><b>{_esc(latest_release)}</b></div>
</div></section>
{_funnel_section(app, funnel_summary)}
<section class="detail-section" id="store"><h2 data-ko="스토어·수익" data-en="Store & revenue">스토어·수익</h2><div class="detail-list">{store_rows}{price_rows}</div></section>
<section class="detail-section" id="reviews"><h2 data-ko="리뷰" data-en="Reviews">리뷰</h2><div class="detail-grid"><div class="detail-stat"><span data-ko="수집 리뷰" data-en="Collected reviews">수집 리뷰</span><b>{len(app_reviews)}</b></div><div class="detail-stat"><span data-ko="답변 대기" data-en="Awaiting reply">답변 대기</span><b>{pending_reviews}</b></div></div></section>
<section class="detail-section" id="technical"><h2 data-ko="기술·운영" data-en="Technical & operations">기술·운영</h2><div class="detail-list">
  <div class="detail-row"><b>Flutter / <span data-ko="플러그인" data-en="plugins">플러그인</span></b><span data-ko="{_esc(dependency_ko)}" data-en="{_esc(dependency_en)}">{_esc(dependency_ko)}</span></div>
  <div class="detail-row"><b data-ko="고급 운영" data-en="Advanced operations">고급 운영</b><span><a href="/ops/legacy/" data-ko="기존 통합 콘솔에서 릴리즈 승인·리뷰 답변 등 기존 조작을 계속 사용할 수 있어요." data-en="Use the legacy console for release approvals, review replies, and other existing controls.">기존 통합 콘솔에서 릴리즈 승인·리뷰 답변 등 기존 조작을 계속 사용할 수 있어요.</a></span></div>
  <div class="detail-row"><b data-ko="공개 제품 페이지" data-en="Public product page">공개 제품 페이지</b><span><a href="/apps/{_esc(slug)}/">onnellab.com/apps/{_esc(slug)}</a></span></div>
</div></section>
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
    funnel_summary: Mapping[str, object] | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    funnel_summary = funnel_summary or {}
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
        app_path.write_text(
            _app_detail(
                app,
                homepage_repo,
                store_items,
                releases,
                reviews,
                dependencies,
                pricing,
                funnel_summary,
            ),
            encoding="utf-8",
        )
        pages.append(app_path)
    return pages
