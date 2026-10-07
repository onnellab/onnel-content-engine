#!/usr/bin/env python3
"""Build the split ONNELLAB Ops information architecture around the legacy console."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlsplit


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
.diagnosis-panel{margin-top:14px;padding:15px;border:1px solid #dfd7e9;border-radius:10px;background:linear-gradient(135deg,#fbf9ff,#fffdf9)}.diagnosis-panel h3{margin:0 0 10px;font-size:15px}.diagnosis-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.diagnosis-card{padding:12px;border:1px solid #e8e0d7;border-radius:9px;background:#fff}.diagnosis-card[data-kind="good"]{background:#f1f8f4;border-color:#cfe0d5}.diagnosis-card[data-kind="warn"]{background:#fff8ef;border-color:#ead7bd}.diagnosis-card[data-kind="low"]{background:#fff2f0;border-color:#ebc8c3}.diagnosis-card[data-kind="wait"]{background:#f7f5f1}.diagnosis-card h4{margin:0 0 6px;font-size:13px}.diagnosis-card p{margin:5px 0 0;color:#686159;font-size:12px;line-height:1.55}.rate-row{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.rate-pill{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #e5ddd4;border-radius:999px;background:#fffdf9;color:#696158;font-size:10px}.diagnosis-note{margin-top:10px;color:#8b8379;font-size:10px;line-height:1.5}
.subsection-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:18px 0 10px}.subsection-head h3{margin:0;font-size:15px}.subsection-head p{margin:0;color:#827d72;font-size:11px}.ops-actions{display:flex;gap:7px;flex-wrap:wrap}.ops-button{min-height:34px;border:1px solid #cfc5b7;border-radius:8px;padding:7px 10px;background:#fff;color:#514b44;font:inherit;font-size:12px;font-weight:750;cursor:pointer}.ops-button.primary{border-color:#b9cbe0;background:var(--blue-soft);color:#315f91}.ops-button:disabled{opacity:.55;cursor:not-allowed}.ops-message{min-height:18px;margin-top:8px;color:#6f695f;font-size:11px;line-height:1.5}.ops-message.is-error{color:#9c3f36}.token-note{margin:10px 0;padding:10px 12px;border:1px solid #ded6ca;border-radius:8px;background:#fffaf2;color:#6f695f;font-size:11px;line-height:1.5}.token-note[hidden]{display:none}.token-note a{font-weight:750}
.review-list,.release-list,.dependency-list,.pricing-list{display:grid;gap:10px}.review-card,.release-card,.dependency-card,.pricing-card{padding:14px;border:1px solid #e8e0d7;border-radius:10px;background:#fffdf9}.review-head,.release-head,.pricing-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.review-head strong,.release-head strong,.pricing-head strong{font-size:14px}.review-rating,.mini-badge{display:inline-flex;align-items:center;min-height:24px;padding:3px 7px;border:1px solid #ddd4ca;border-radius:999px;background:#fff;color:#655e55;font-size:10px;font-weight:750}.mini-badge.good{border-color:#c7ddd0;background:#eef7f2;color:#49675a}.mini-badge.warn{border-color:#e4d1b7;background:#fff7eb;color:#795d37}.mini-badge.bad{border-color:#e4c4bf;background:#fff1ef;color:#844d47}.review-meta,.release-meta,.pricing-meta,.dependency-meta{margin-top:5px;color:#827d72;font-size:10px;line-height:1.5}.review-body{margin:10px 0 0;white-space:pre-wrap;font-size:13px;line-height:1.6}.review-translation{margin-top:10px;padding:10px;border:1px solid #e5ddd4;border-radius:8px;background:#fff}.review-translation b{display:block;margin-bottom:5px;font-size:11px}.review-translation p{margin:0;font-size:12px;line-height:1.55}.review-card label{display:grid;gap:5px;margin-top:10px;color:#716a61;font-size:11px;font-weight:700}.review-card textarea{width:100%;min-height:92px;border:1px solid #dcd3c8;border-radius:8px;padding:9px;background:#fff;color:#302c28;font:inherit;font-size:12px;line-height:1.5;resize:vertical}.review-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.review-card details{margin-top:10px}.review-card details summary{cursor:pointer;color:#655e55;font-size:11px;font-weight:750}.triage-box{margin-top:7px;padding:9px;border:1px solid #e4dced;border-radius:8px;background:#faf7ff;color:#675d70;font-size:11px;line-height:1.55;white-space:pre-wrap}.release-card p,.pricing-card p,.dependency-card p{margin:7px 0 0;color:#696158;font-size:11px;line-height:1.55}.release-card a,.pricing-card a{font-weight:700}.economics-callout{margin-top:9px;padding:9px;border:1px solid #c8dfd1;border-radius:8px;background:#eff8f3;color:#4d6758;font-size:11px;line-height:1.5}.economics-callout.loss{border-color:#e5c5c0;background:#fff1ef;color:#824e48}.site-freshness{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
@media(max-width:680px){.ops-wrap{padding:18px 15px 42px}.ops-route-grid,.app-grid{grid-template-columns:1fr}.app-grid{gap:10px}.app-card{grid-template-columns:46px minmax(0,1fr);gap:13px;min-height:0;padding:15px}.app-card>img{width:44px;height:44px;border-radius:11px}.detail-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.detail-hero{grid-template-columns:54px minmax(0,1fr);padding:17px}.detail-hero img{width:52px;height:52px;border-radius:12px}.ops-head h1{font-size:29px}.funnel-platform-grid,.diagnosis-grid,.site-freshness{grid-template-columns:1fr}.funnel-chain{gap:5px}.funnel-step{padding:8px}.funnel-step b{font-size:17px}.review-head,.release-head,.pricing-head{align-items:flex-start}.review-card,.release-card,.dependency-card,.pricing-card{padding:12px}}
"""


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _safe_href(value: object) -> str:
    candidate = str(value or "").strip()
    if candidate.startswith("/") and not candidate.startswith("//"):
        return candidate
    parsed = urlsplit(candidate)
    return candidate if parsed.scheme in {"https", "http"} and parsed.netloc else ""


def _json_script(value: object) -> str:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


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
body[data-ops-view="home"] main>.status-section:not([aria-label="AI operation status"]){display:none!important}
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
<p class="ops-legacy-link"><span data-ko="리뷰·릴리즈 승인 등 앱별 운영은 각 앱 페이지에서 처리해요. 이전 화면과 비교할 때만" data-en="Manage reviews, release approvals, and other app operations in each app page. Open the">리뷰·릴리즈 승인 등 앱별 운영은 각 앱 페이지에서 처리해요. 이전 화면과 비교할 때만</span> <a href="/ops/legacy/" data-ko="기존 통합 콘솔" data-en="legacy console">기존 통합 콘솔</a><span data-ko="을 열면 돼요." data-en=" only to compare with the previous interface.">을 열면 돼요.</span></p>
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
    published = str(item.get("published_at") or item.get("release_date") or "")
    notes = str(item.get("release_notes") or "")
    ko = f"버전 {version} · {status_ko} · 확인 {checked}"
    en = f"Version {version} · {status_en} · checked {checked}"
    extra = ""
    if published:
        extra += (
            f'<span data-ko="공개 {_esc(published)}" data-en="published {_esc(published)}">공개 {_esc(published)}</span>'
        )
    if notes:
        extra += (
            f'<span><b data-ko="릴리즈 노트" data-en="Release notes">릴리즈 노트</b> · {_esc(notes)}</span>'
        )
    return (
        f'<div class="detail-row"><b>{platform}</b>'
        f'<span data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</span>{extra}</div>'
    )


def _bilingual_price_row(item: Mapping[str, object]) -> str:
    product_name = str(item.get("product_name") or "Product")
    price = str(item.get("price") or "—")
    currency = str(item.get("currency") or "")
    product_type = str(item.get("product_type") or "")
    platform = str(item.get("platform") or "")
    pricing_model = str(item.get("pricing") or item.get("pricing_model") or "—")
    verification = str(item.get("price_verification") or "unknown")
    source = str(item.get("price_source") or "—")
    note = str(item.get("price_note") or "")
    checked = str(item.get("checked_at") or "—")
    error = str(item.get("price_error") or "")
    platform_label = "App Store" if platform == "ios" else "Play Store" if platform == "android" else "공통"
    platform_en = "App Store" if platform == "ios" else "Play Store" if platform == "android" else "Shared"
    type_ko = {
        "pro": "Pro",
        "paid_download": "유료 다운로드",
        "ai_credit": "AI 크레딧",
        "subscription": "구독",
        "in_app_purchase": "인앱 구매",
    }.get(product_type, product_type or "유료 제품")
    type_en = {
        "paid_download": "Paid download",
        "ai_credit": "AI credit",
        "subscription": "Subscription",
        "in_app_purchase": "In-app purchase",
    }.get(product_type, product_type or "Paid product")
    verification_ko = "스토어 실가격 확인" if verification == "live_store" else "수동/추가 확인 필요"
    verification_en = "Live store verified" if verification == "live_store" else "Manual / needs verification"
    badge_class = "good" if verification == "live_store" else "warn"

    economics = ""
    if item.get("ai_margin_status"):
        margin_status = str(item.get("ai_margin_status") or "")
        net = str(item.get("ai_net_revenue_usd") or "—")
        provider_cost = str(item.get("ai_provider_cost_usd") or "—")
        profit = str(item.get("ai_profit_usd") or "—")
        margin_percent = str(item.get("ai_margin_percent") or "")
        economics_class = " loss" if margin_status == "loss" else ""
        margin_ko = f" / 마진 {margin_percent}%" if margin_percent else ""
        margin_en = f" / margin {margin_percent}%" if margin_percent else ""
        economics = (
            f'<div class="economics-callout{economics_class}">'
            '<b data-ko="AI 크레딧 경제성" data-en="AI credit economics">AI 크레딧 경제성</b> · '
            f'<span data-ko="순수익 ${_esc(net)} / 공급자 비용 ${_esc(provider_cost)} / 이익 ${_esc(profit)}{_esc(margin_ko)}" '
            f'data-en="Net revenue ${_esc(net)} / provider cost ${_esc(provider_cost)} / profit ${_esc(profit)}{_esc(margin_en)}">'
            f'순수익 ${_esc(net)} / 공급자 비용 ${_esc(provider_cost)} / 이익 ${_esc(profit)}{_esc(margin_ko)}</span></div>'
        )

    error_html = (
        f'<p class="ops-message is-error"><b data-ko="가격 확인 오류" data-en="Price verification error">가격 확인 오류</b> · {_esc(error)}</p>'
        if error
        else ""
    )
    note_html = f"<p>{_esc(note)}</p>" if note else ""
    return (
        '<article class="pricing-card">'
        '<div class="pricing-head">'
        f'<strong>{_esc(product_name)}</strong>'
        f'<span class="mini-badge {badge_class}" data-ko="{_esc(verification_ko)}" data-en="{_esc(verification_en)}">{_esc(verification_ko)}</span>'
        "</div>"
        f'<div class="pricing-meta"><span data-ko="{_esc(platform_label)}" data-en="{_esc(platform_en)}">{_esc(platform_label)}</span> · '
        f'<span data-ko="{_esc(type_ko)}" data-en="{_esc(type_en)}">{_esc(type_ko)}</span></div>'
        f'<p><b data-ko="가격" data-en="Price">가격</b> · {_esc(price)} {_esc(currency)}</p>'
        f'<p><b data-ko="과금 모델" data-en="Pricing model">과금 모델</b> · {_esc(pricing_model)}</p>'
        f'<p><b data-ko="가격 출처" data-en="Price source">가격 출처</b> · {_esc(source)} · '
        f'<span data-ko="확인 {_esc(checked)}" data-en="checked {_esc(checked)}">확인 {_esc(checked)}</span></p>'
        f"{note_html}{error_html}{economics}"
        "</article>"
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


def _metric_int(payload: Mapping[str, object] | None, key: str) -> int | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rate_value(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _diagnose_funnel(
    source: str,
    payload: Mapping[str, object] | None,
    window: int,
) -> dict[str, object]:
    days = _metric_int(payload, "days_with_data") or 0
    visitors = _metric_int(payload, "store_visitors")
    installs = _metric_int(payload, "installs")
    purchases = _metric_int(payload, "purchases")
    impressions = _metric_int(payload, "impressions") if source == "apple" else None
    rates: list[tuple[str, str, float]] = []

    page_rate = _rate_value(visitors, impressions)
    install_rate = _rate_value(installs, visitors)
    purchase_rate = _rate_value(purchases, installs)
    if source == "apple" and page_rate is not None:
        rates.append(("노출→제품 페이지", "Impression→product page", page_rate))
    if install_rate is not None:
        rates.append(
            (
                "제품 페이지→다운로드" if source == "apple" else "스토어 방문→설치",
                "Product page→download" if source == "apple" else "Store visitor→install",
                install_rate,
            )
        )
    if purchase_rate is not None:
        rates.append(("설치→구매", "Install→purchase", purchase_rate))

    sample_floor = {7: 10, 30: 20, 90: 30}.get(window, 20)
    volume_target = {7: 250, 30: 1000, 90: 2500}.get(window, 1000)
    source_ko = "App Store" if source == "apple" else "Play Store"
    source_en = source_ko

    if not isinstance(payload, Mapping) or days <= 0 or visitors is None:
        return {
            "kind": "wait",
            "title_ko": f"{source_ko} · 판단 대기",
            "title_en": f"{source_en} · Waiting for data",
            "assessment_ko": "아직 진단할 수 있는 퍼널 데이터가 없어요.",
            "assessment_en": "There is not enough funnel data to diagnose yet.",
            "action_ko": "수집이 시작된 뒤 다시 확인해요.",
            "action_en": "Check again after collection starts.",
            "rates": rates,
        }

    if days < 3 or visitors < sample_floor:
        return {
            "kind": "wait",
            "title_ko": f"{source_ko} · 표본이 아직 작아요",
            "title_en": f"{source_en} · Sample still small",
            "assessment_ko": f"{days}일치 데이터와 방문 {visitors:,}건만 있어 강한 결론을 내리지 않아요.",
            "assessment_en": f"Only {days} days and {visitors:,} visits are available, so the diagnostic stays conservative.",
            "action_ko": "표본이 더 쌓일 때까지 추세만 관찰해요.",
            "action_en": "Watch the trend until more data accumulates.",
            "rates": rates,
        }

    if source == "apple" and impressions and page_rate is not None and page_rate < 0.08:
        return {
            "kind": "low",
            "title_ko": "App Store · 제품 페이지 진입이 가장 먼저 새요",
            "title_en": "App Store · Product-page entry is the first leak",
            "assessment_ko": f"노출 {impressions:,}건 중 제품 페이지 조회 비율이 {_pct(page_rate)}예요.",
            "assessment_en": f"Product-page views are {_pct(page_rate)} of {impressions:,} impressions.",
            "action_ko": "검색 메타데이터·아이콘·스토어 노출 문맥부터 점검하는 우선순위가 높아요.",
            "action_en": "Prioritize search metadata, icon, and store-discovery context.",
            "rates": rates,
        }

    if install_rate is not None and install_rate < 0.10:
        return {
            "kind": "low",
            "title_ko": f"{source_ko} · 스토어 전환이 약해요",
            "title_en": f"{source_en} · Store conversion is weak",
            "assessment_ko": f"방문→설치 전환이 {_pct(install_rate)}라 유입보다 스토어 설득 단계가 먼저 보여요.",
            "assessment_en": f"Visit-to-install conversion is {_pct(install_rate)}, so the store-page persuasion step stands out before traffic volume.",
            "action_ko": "첫 스크린샷·짧은 설명·가격/가치 제안을 우선 점검해요.",
            "action_en": "Review the first screenshots, short description, and price/value proposition first.",
            "rates": rates,
        }

    if (
        installs is not None
        and installs >= max(10, sample_floor // 2)
        and purchases is not None
        and purchases == 0
    ):
        return {
            "kind": "warn",
            "title_ko": f"{source_ko} · 설치 뒤 구매 전환을 관찰해야 해요",
            "title_en": f"{source_en} · Watch post-install purchase conversion",
            "assessment_ko": f"설치 {installs:,}건이 있지만 이 기간의 구매 집계는 0건이에요.",
            "assessment_en": f"There are {installs:,} installs but zero recorded purchases in this window.",
            "action_ko": "유료 기능 노출 시점·무료/Pro 경계·가격 전달을 확인해요.",
            "action_en": "Check when paid value appears, the free/Pro boundary, and price communication.",
            "rates": rates,
        }

    if install_rate is not None and install_rate >= 0.25 and visitors < volume_target:
        return {
            "kind": "good",
            "title_ko": f"{source_ko} · 전환은 버티고 있고 다음 과제는 유입량이에요",
            "title_en": f"{source_en} · Conversion is holding; traffic is the next priority",
            "assessment_ko": f"방문→설치 전환이 {_pct(install_rate)}인데 방문량은 내부 운영 목표({volume_target:,})보다 작아요.",
            "assessment_en": f"Visit-to-install conversion is {_pct(install_rate)}, while traffic is below the internal operating target ({volume_target:,}).",
            "action_ko": "스토어 전환을 크게 흔들기보다 검색·콘텐츠·외부 노출을 늘리는 쪽을 우선해요.",
            "action_en": "Prioritize search, content, and external discovery before materially changing the store conversion surface.",
            "rates": rates,
        }

    if visitors < volume_target:
        return {
            "kind": "warn",
            "title_ko": f"{source_ko} · 지금은 유입량 확대가 더 중요해요",
            "title_en": f"{source_en} · Traffic volume is the bigger opportunity",
            "assessment_ko": f"전환이 치명적으로 꺾이진 않았지만 방문량이 내부 운영 목표({volume_target:,})보다 작아요.",
            "assessment_en": f"Conversion is not the clearest failure, but traffic remains below the internal operating target ({volume_target:,}).",
            "action_ko": "ASO 키워드·콘텐츠 링크·스토어 노출 기회를 늘려요.",
            "action_en": "Increase ASO keyword coverage, content links, and store-discovery opportunities.",
            "rates": rates,
        }

    return {
        "kind": "good",
        "title_ko": f"{source_ko} · 뚜렷한 단일 병목은 없어요",
        "title_en": f"{source_en} · No single obvious bottleneck",
        "assessment_ko": "현재 내부 진단 규칙에서는 한 단계가 유독 크게 무너진 모습은 아니에요.",
        "assessment_en": "Under the internal diagnostic rules, no single step is disproportionately weak.",
        "action_ko": "기간별 추세를 계속 보면서 가장 먼저 악화되는 단계를 잡아요.",
        "action_en": "Keep watching period trends and act on the first step that deteriorates.",
        "rates": rates,
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _diagnosis_card(source: str, payload: Mapping[str, object] | None, window: int) -> str:
    diagnosis = _diagnose_funnel(source, payload, window)
    rates = "".join(
        '<span class="rate-pill">'
        f'<span data-ko="{_esc(ko)}" data-en="{_esc(en)}">{_esc(ko)}</span>'
        f"<b>{_esc(_pct(value))}</b></span>"
        for ko, en, value in diagnosis["rates"]  # type: ignore[index]
    )
    return (
        f'<article class="diagnosis-card" data-kind="{_esc(diagnosis["kind"])}">'
        f'<h4 data-ko="{_esc(diagnosis["title_ko"])}" data-en="{_esc(diagnosis["title_en"])}">{_esc(diagnosis["title_ko"])}</h4>'
        f'<p data-ko="{_esc(diagnosis["assessment_ko"])}" data-en="{_esc(diagnosis["assessment_en"])}">{_esc(diagnosis["assessment_ko"])}</p>'
        f'<p><b data-ko="다음 행동" data-en="Next action">다음 행동</b> · '
        f'<span data-ko="{_esc(diagnosis["action_ko"])}" data-en="{_esc(diagnosis["action_en"])}">{_esc(diagnosis["action_ko"])}</span></p>'
        f'<div class="rate-row">{rates}</div>'
        "</article>"
    )


def _funnel_diagnosis_html(
    app_platforms: set[str],
    ios_window: Mapping[str, object] | None,
    android_window: Mapping[str, object] | None,
    window: int,
) -> str:
    cards: list[str] = []
    if "ios" in app_platforms:
        cards.append(_diagnosis_card("apple", ios_window, window))
    if "android" in app_platforms:
        cards.append(_diagnosis_card("google", android_window, window))
    if not cards:
        return ""
    return (
        '<div class="diagnosis-panel">'
        '<h3 data-ko="진단·평가" data-en="Diagnosis & evaluation">진단·평가</h3>'
        f'<div class="diagnosis-grid">{"".join(cards)}</div>'
        '<div class="diagnosis-note" '
        'data-ko="이 평가는 업계 평균이 아니라 ONNELLAB 운영용 내부 휴리스틱이에요. 표본이 작으면 결론을 보류하고, 실제 퍼널에서 먼저 새는 단계를 찾는 용도예요." '
        'data-en="This is an internal ONNELLAB operating heuristic, not an industry benchmark. It stays conservative on small samples and is meant to identify the first leaking step in the observed funnel.">'
        '이 평가는 업계 평균이 아니라 ONNELLAB 운영용 내부 휴리스틱이에요. 표본이 작으면 결론을 보류하고, 실제 퍼널에서 먼저 새는 단계를 찾는 용도예요.'
        "</div></div>"
    )


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
        diagnosis_html = _funnel_diagnosis_html(
            app_platforms,
            ios_window,
            android_window,
            window,
        )
        hidden = "" if window == 30 else " hidden"
        windows_html.append(
            f'<div class="funnel-window" data-funnel-window="{window}"{hidden}>'
            f'<div class="funnel-platform-grid">{apple_card}{google_card}</div>'
            f"{combined_html}"
            '<div class="funnel-note" data-ko="스토어 방문·제품 페이지 조회의 정의가 달라 방문 수는 합산하지 않아요. Android에는 App Store의 노출과 동등한 공개 지표를 만들지 않아요." '
            'data-en="Store-visitor definitions differ, so visitor counts are not summed. Android does not invent an App-Store-equivalent impressions metric.">'
            "스토어 방문·제품 페이지 조회의 정의가 달라 방문 수는 합산하지 않아요. Android에는 App Store의 노출과 동등한 공개 지표를 만들지 않아요.</div>"
            f"{diagnosis_html}"
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


def _review_card_html(item: Mapping[str, object], index: int) -> str:
    platform = "App Store" if str(item.get("platform") or "") == "ios" else "Play Store"
    rating = str(item.get("rating") or "—")
    is_rating_only = str(item.get("review_kind") or "") == "rating_only"
    is_replied = str(item.get("status") or "") == "replied" or bool(str(item.get("developer_reply") or "").strip())
    status_ko = "별점만" if is_rating_only else "답변 완료" if is_replied else "답변 대기"
    status_en = "Rating only" if is_rating_only else "Replied" if is_replied else "Awaiting reply"
    meta_parts = [
        str(item.get("reviewer_language") or ""),
        str(item.get("territory") or ""),
        f'v{item.get("app_version")}' if item.get("app_version") else "",
        str(item.get("updated_at") or item.get("created_at") or ""),
    ]
    meta = " · ".join(value for value in meta_parts if value)
    title = str(item.get("title") or "")
    body = str(item.get("body") or "")
    suggested = str(item.get("suggested_reply") or "")
    developer_reply = str(item.get("developer_reply") or "")
    translation_required = bool(item.get("approval_translation_required"))
    review_translation = str(item.get("review_translation_ko") or "")
    reply_translation = str(item.get("reply_translation_ko") or "")
    triage = item.get("triage") if isinstance(item.get("triage"), Mapping) else {}
    triage = triage if isinstance(triage, Mapping) else {}
    manual_play = str(item.get("platform") or "") == "android" and str(item.get("review_id") or "").startswith("report-")

    translation_html = ""
    if translation_required and not is_replied and not is_rating_only:
        translation_html = (
            '<div class="review-translation">'
            '<b data-ko="리뷰 한국어 번역" data-en="Korean review translation">리뷰 한국어 번역</b>'
            f'<p>{_esc(review_translation or "번역이 아직 없어요.")}</p></div>'
            '<label><span data-ko="답변 한국어 번역 · 승인 확인용" data-en="Korean reply translation · approval check">답변 한국어 번역 · 승인 확인용</span>'
            f'<textarea data-review-translation>{_esc(reply_translation)}</textarea></label>'
        )

    triage_html = ""
    if triage:
        category = str(triage.get("category") or "—")
        similar = str(triage.get("similar_reviews") or "0")
        manual = bool(triage.get("requires_human_approval"))
        facts_raw = triage.get("facts")
        facts = []
        if isinstance(facts_raw, list):
            for fact in facts_raw:
                if isinstance(fact, Mapping):
                    text = str(fact.get("text") or "")
                    if text:
                        facts.append(text)
        issue = str(triage.get("issue_draft") or "")
        triage_body = (
            f'<div class="triage-box"><b>AI triage</b> · {_esc(category)} · '
            f'<span data-ko="유사 리뷰 {_esc(similar)}개" data-en="{_esc(similar)} similar reviews">유사 리뷰 {_esc(similar)}개</span>'
            + (' · <span data-ko="사람 승인 필요" data-en="Human approval required">사람 승인 필요</span>' if manual else "")
        )
        if facts:
            triage_body += '<br><b data-ko="승인된 사실" data-en="Approved facts">승인된 사실</b> · ' + _esc(" ".join(facts))
        triage_body += "</div>"
        if issue:
            triage_body += (
                '<div class="triage-box"><b data-ko="GitHub 이슈 초안" data-en="GitHub issue draft">GitHub 이슈 초안</b><br>'
                + _esc(issue)
                + "</div>"
            )
        triage_html = (
            '<details><summary data-ko="AI 분류·근거 보기" data-en="Show AI triage & evidence">AI 분류·근거 보기</summary>'
            + triage_body
            + "</details>"
        )

    existing_reply_html = ""
    if developer_reply:
        existing_reply_html = (
            '<div class="review-translation"><b data-ko="현재 개발자 답변" data-en="Current developer reply">현재 개발자 답변</b>'
            f'<p>{_esc(developer_reply)}</p></div>'
        )

    actions_html = ""
    if not is_replied and not is_rating_only:
        approve_ko = "Play Console에서 수동 답변" if manual_play else "승인하고 게시"
        approve_en = "Manual reply in Play Console" if manual_play else "Approve & publish"
        disabled = " disabled" if manual_play or (translation_required and (not review_translation or not reply_translation)) else ""
        actions_html = (
            '<label><span data-ko="답변 초안" data-en="Reply draft">답변 초안</span>'
            f'<textarea data-review-reply>{_esc(suggested)}</textarea></label>'
            '<div class="review-actions">'
            '<button class="ops-button" type="button" data-review-action="draft" data-ko="추천 초안 복원" data-en="Reset suggested draft">추천 초안 복원</button>'
            '<button class="ops-button" type="button" data-review-action="copy" data-ko="답변 복사" data-en="Copy reply">답변 복사</button>'
            f'<button class="ops-button primary" type="button" data-review-action="approve"{disabled} data-ko="{_esc(approve_ko)}" data-en="{_esc(approve_en)}">{_esc(approve_ko)}</button>'
            '</div><div class="ops-message" data-review-message></div>'
        )

    body_html = (
        '<p class="review-body" data-ko="별점만 남긴 평가예요." data-en="This entry contains a rating only.">별점만 남긴 평가예요.</p>'
        if is_rating_only
        else f'<p class="review-body">{_esc(body or "—")}</p>'
    )
    title_html = f'<strong class="review-body">{_esc(title)}</strong>' if title else ""
    return (
        f'<article class="review-card" data-review-index="{index}">'
        '<div class="review-head">'
        f'<strong>{_esc(platform)}</strong><span class="review-rating">{_esc(rating)} / 5</span></div>'
        f'<div class="review-meta">{_esc(meta)} · '
        f'<span data-ko="{_esc(status_ko)}" data-en="{_esc(status_en)}">{_esc(status_ko)}</span></div>'
        f'{title_html}{body_html}{translation_html}{triage_html}{existing_reply_html}{actions_html}'
        "</article>"
    )


def _release_card_html(item: Mapping[str, object], index: int) -> str:
    tag = str(item.get("tag") or item.get("version") or item.get("release_id") or "Release")
    status = str(item.get("status") or "—")
    channel = str(item.get("release_channel") or "public")
    release_id = str(item.get("release_id") or "")
    date = str(item.get("released_at") or item.get("release_date") or "—")
    url = _safe_href(item.get("release_url"))
    notes = str(item.get("release_notes") or "")
    if channel != "public":
        state_ko, state_en, badge_class = "내부 테스트", "Private test", "warn"
    elif status == "released":
        state_ko, state_en, badge_class = "자동 공개 완료", "Automatically published", "good"
    elif status == "ready":
        state_ko, state_en, badge_class = "자동 공개 준비됨", "Ready for automatic publication", "good"
    else:
        state_ko, state_en, badge_class = "자동 공개 대기", "Awaiting automatic publication", "warn"
    link_html = f'<p><a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" data-ko="릴리즈 페이지 열기" data-en="Open release page">릴리즈 페이지 열기</a></p>' if url else ""
    notes_html = f'<p><b data-ko="릴리즈 노트" data-en="Release notes">릴리즈 노트</b> · {_esc(notes)}</p>' if notes else ""
    return (
        f'<article class="release-card" data-release-index="{index}">'
        '<div class="release-head">'
        f'<strong>{_esc(tag)}</strong><span class="mini-badge {badge_class}" data-ko="{_esc(state_ko)}" data-en="{_esc(state_en)}">{_esc(state_ko)}</span>'
        '</div>'
        f'<div class="release-meta">{_esc(release_id)} · {_esc(status)} · {_esc(channel)} · {_esc(date)}</div>'
        f'{notes_html}{link_html}</article>'
    )


def _dependency_card_html(item: Mapping[str, object]) -> str:
    name = str(item.get("package_name") or item.get("package") or "—")
    kind = str(item.get("package_type") or "dependency")
    declared = str(item.get("declared_version") or item.get("flutter_constraint") or "—")
    resolved = str(item.get("resolved_version") or item.get("current_version") or "—")
    source = str(item.get("source") or "")
    source_html = f' · <span data-ko="출처 {_esc(source)}" data-en="source {_esc(source)}">출처 {_esc(source)}</span>' if source else ""
    return (
        '<article class="dependency-card">'
        f'<strong>{_esc(name)}</strong>'
        f'<div class="dependency-meta">{_esc(kind)}{source_html}</div>'
        f'<p><span data-ko="선언" data-en="Declared">선언</span> {_esc(declared)} · '
        f'<span data-ko="해결/현재" data-en="Resolved/current">해결/현재</span> {_esc(resolved)}</p>'
        '</article>'
    )


def _app_controls_script(
    reviews: Sequence[Mapping[str, object]],
) -> str:
    reviews_json = _json_script(list(reviews))
    return rf"""
<script id="app-review-data" type="application/json">{reviews_json}</script>
<script>
(() => {{
  const repo = 'onnellab/onnel-content-engine';
  const branch = 'main';
  const tokenKey = 'onnellab-manual-publish-token';
  const approvalsPath = 'data/store_review_approvals.json';
  const reviews = JSON.parse(document.getElementById('app-review-data').textContent || '[]');
  const currentLang = () => localStorage.getItem('onnellab-ops-language') === 'en' ? 'en' : 'ko';
  const label = (ko, en) => currentLang() === 'en' ? en : ko;
  const token = () => (localStorage.getItem(tokenKey) || '').trim();

  const updateTokenNotes = () => {{
    document.querySelectorAll('[data-app-token-note]').forEach((node) => {{
      node.hidden = Boolean(token());
    }});
  }};

  async function githubRequest(path, options = {{}}) {{
    if (!token()) throw new Error(label('GitHub 연결이 필요해요. 설정에서 토큰을 연결해 주세요.', 'GitHub connection is required. Connect a token in Settings.'));
    const headers = {{
      Accept: 'application/vnd.github+json',
      Authorization: 'Bearer ' + token(),
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {{}}),
    }};
    const response = await fetch('https://api.github.com' + path, {{...options, headers}});
    const text = await response.text();
    let data = {{}};
    if (text) {{
      try {{ data = JSON.parse(text); }} catch {{ data = {{}}; }}
    }}
    if (!response.ok) {{
      const safeMessage = String(data.message || 'GitHub request failed').slice(0, 240);
      throw new Error('GitHub HTTP ' + response.status + ': ' + safeMessage);
    }}
    return data;
  }}

  function encodeBase64Unicode(value) {{
    const bytes = new TextEncoder().encode(value);
    let binary = '';
    bytes.forEach((byte) => {{ binary += String.fromCharCode(byte); }});
    return btoa(binary);
  }}

  function decodeBase64Unicode(value) {{
    const binary = atob(String(value || '').replace(/\n/g, ''));
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }}

  function flash(button, text) {{
    if (!button) return;
    const previous = button.textContent;
    button.textContent = text;
    window.setTimeout(() => {{ if (!button.disabled) button.textContent = previous; }}, 1800);
  }}

  function setMessage(node, text, isError = false) {{
    if (!node) return;
    node.textContent = text;
    node.classList.toggle('is-error', isError);
  }}

  async function copyText(value, button) {{
    await navigator.clipboard.writeText(String(value || ''));
    flash(button, label('복사됨', 'Copied'));
  }}

  async function queueApprovedStoreReply(item, reply) {{
    const cleanReply = String(reply || '').replace(/\\s+/g, ' ').trim();
    if (!cleanReply) throw new Error(label('답변을 입력해 주세요.', 'A reply is required.'));
    if (cleanReply.length > 1000) throw new Error(label('답변은 1000자 이하여야 해요.', 'Reply must be 1000 characters or fewer.'));
    if (/(will be fixed|next update|guaranteed|refund approved|다음 업데이트|고쳐드리|환불해드리)/i.test(cleanReply)) {{
      throw new Error(label('확정 약속 문구가 포함되어 승인할 수 없어요.', 'The reply contains a prohibited promise.'));
    }}
    const data = await githubRequest('/repos/' + repo + '/contents/' + approvalsPath + '?ref=' + branch);
    const approvals = JSON.parse(decodeBase64Unicode(data.content));
    approvals.approvals ||= [];
    const existing = approvals.approvals.find(
      (entry) => entry.review_id === item.review_id && ['queued', 'published'].includes(entry.status)
    );
    if (existing) {{
      if (existing.status === 'queued' && existing.reply === cleanReply && existing.approval_id) {{
        return existing.approval_id;
      }}
      throw new Error(label('이미 다른 답변으로 승인됐거나 게시된 리뷰예요.', 'This review already has a different active approval or has been published.'));
    }}
    const approvedAt = new Date().toISOString();
    const approvalId = 'review-' + item.review_id;
    approvals.approvals.push({{
      approval_id: approvalId,
      review_id: item.review_id,
      app_id: item.app_id || '',
      app_slug: item.app_slug || '',
      platform: item.platform || '',
      reply: cleanReply,
      approved_at: approvedAt,
      approved_by: 'dashboard_token_holder',
      note: '',
      status: 'queued',
      publication: {{attempts: 0, published_at: '', external_response_id: ''}},
    }});
    approvals.updated_at = approvedAt;
    await githubRequest('/repos/' + repo + '/contents/' + approvalsPath, {{
      method: 'PUT',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        message: 'Queue approved reply for ' + item.review_id,
        content: encodeBase64Unicode(JSON.stringify(approvals, null, 2) + '\n'),
        branch,
        sha: data.sha,
      }}),
    }});
    return approvalId;
  }}

  async function dispatchApprovedStoreReply(approvalId) {{
    await githubRequest('/repos/' + repo + '/actions/workflows/publish-store-review-reply.yml/dispatches', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        ref: branch,
        inputs: {{approval_id: approvalId, confirm_publish: 'PUBLISH'}},
      }}),
    }});
  }}

  async function dispatchReviewSync(button) {{
    const message = document.querySelector('[data-review-sync-message]');
    try {{
      button.disabled = true;
      setMessage(message, label('전체 앱 리뷰 동기화를 요청하는 중이에요…', 'Requesting review sync for all apps…'));
      await githubRequest('/repos/' + repo + '/actions/workflows/sync-store-reviews.yml/dispatches', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ref: branch, inputs: {{deploy_dashboard: 'true'}}}}),
      }});
      setMessage(message, label('리뷰 동기화를 요청했어요. 완료 후 대시보드가 자동 갱신돼요.', 'Review sync requested. The dashboard will refresh after completion.'));
      button.textContent = label('동기화 요청됨', 'Sync requested');
    }} catch (error) {{
      setMessage(message, String(error.message || error), true);
      button.disabled = false;
    }}
  }}

  function bindReviewCards() {{
    document.querySelectorAll('[data-review-index]').forEach((card) => {{
      const item = reviews[Number(card.dataset.reviewIndex)];
      if (!item) return;
      const reply = card.querySelector('[data-review-reply]');
      const replyTranslation = card.querySelector('[data-review-translation]');
      const draft = card.querySelector('[data-review-action="draft"]');
      const copy = card.querySelector('[data-review-action="copy"]');
      const approve = card.querySelector('[data-review-action="approve"]');
      const message = card.querySelector('[data-review-message]');
      const manualPlay = item.platform === 'android' && String(item.review_id || '').startsWith('report-');
      const translationRequired = Boolean(item.approval_translation_required);
      const translationsReady = () => !translationRequired || (
        /[가-힣]/.test(String(item.review_translation_ko || '')) &&
        /[가-힣]/.test(String(replyTranslation?.value || ''))
      );
      const updateApproval = () => {{
        if (approve) approve.disabled = manualPlay || !translationsReady();
      }};
      if (draft && reply) draft.addEventListener('click', () => {{
        reply.value = item.suggested_reply || '';
        if (replyTranslation) replyTranslation.value = item.reply_translation_ko || '';
        updateApproval();
        reply.focus();
      }});
      if (copy && reply) copy.addEventListener('click', () => copyText(reply.value || item.suggested_reply || '', copy));
      if (replyTranslation) replyTranslation.addEventListener('input', updateApproval);
      if (reply) reply.addEventListener('input', () => {{
        if (replyTranslation && reply.value.trim() !== String(item.suggested_reply || '').trim()) {{
          replyTranslation.value = '';
        }}
        updateApproval();
      }});
      let queuedApprovalId = '';
      if (approve && !manualPlay) approve.addEventListener('click', async () => {{
        if (!translationsReady()) {{
          setMessage(message, label('한국어 번역 확인이 필요해요.', 'Korean translation confirmation is required.'), true);
          return;
        }}
        try {{
          approve.disabled = true;
          if (!queuedApprovalId) {{
            setMessage(message, label('승인을 저장하는 중이에요…', 'Saving approval…'));
            queuedApprovalId = await queueApprovedStoreReply(item, reply?.value || item.suggested_reply || '');
          }}
          if (reply) reply.readOnly = true;
          if (replyTranslation) replyTranslation.readOnly = true;
          if (draft) draft.disabled = true;
          setMessage(message, label('게시를 요청하는 중이에요…', 'Requesting publication…'));
          await dispatchApprovedStoreReply(queuedApprovalId);
          approve.textContent = label('게시 요청됨', 'Publish requested');
          setMessage(message, label('승인 저장과 게시 요청이 완료됐어요.', 'Approval saved and publication requested.'));
        }} catch (error) {{
          const retryNote = queuedApprovalId
            ? label('승인은 저장됐어요. 게시 요청만 실패해 다시 누르면 재시도해요. ', 'Approval is saved. Publication dispatch failed; press again to retry. ')
            : '';
          setMessage(message, retryNote + String(error.message || error), true);
          approve.disabled = false;
        }}
      }});
      updateApproval();
    }});
  }}

  const syncButton = document.querySelector('[data-review-sync]');
  if (syncButton) syncButton.addEventListener('click', () => dispatchReviewSync(syncButton));
  bindReviewCards();
  updateTokenNotes();
}})();
</script>
"""


def _source_health_line(title_ko: str, title_en: str, value_ko: str, value_en: str, severity: str = "") -> str:
    color_class = " good" if severity == "ok" else " warn" if severity in {"warning", "error"} else ""
    return (
        '<div class="detail-row">'
        f'<b data-ko="{_esc(title_ko)}" data-en="{_esc(title_en)}">{_esc(title_ko)}</b>'
        f'<span class="mini-badge{color_class}" data-ko="{_esc(value_ko)}" data-en="{_esc(value_en)}">{_esc(value_ko)}</span>'
        "</div>"
    )


def _review_source_health(slug: str, status: Mapping[str, object]) -> str:
    stores = status.get("stores", [])
    rows = [
        entry
        for entry in stores
        if isinstance(entry, Mapping) and str(entry.get("app_slug") or "") == slug
    ] if isinstance(stores, list) else []
    verified_snapshot = status.get("snapshot_matches") is True
    checked = str(status.get("checked_at") or "—")
    if not rows:
        return _source_health_line(
            "리뷰 수집 검증", "Review source verification",
            "검증 기록 없음", "No verification record", "warning",
        )
    fragments: list[str] = []
    for provider in ("ios", "android"):
        for entry in rows:
            if str(entry.get("platform") or "") != provider:
                continue
            source = "App Store" if provider == "ios" else "Play Store"
            state = str(entry.get("state") or "unknown")
            count = entry.get("current_reviews")
            count_ko = f" · 현재 {count}건" if count is not None else ""
            count_en = f" · {count} current reviews" if count is not None else ""
            if state == "not_released":
                state_ko, state_en = "미출시", "Not released"
                severity = ""
            elif state == "verified" and verified_snapshot:
                state_ko, state_en = "최신 목록 검증됨", "Current list verified"
                severity = "ok"
            elif state == "verified":
                state_ko, state_en = "동기화 파일 일치 재확인 필요", "Snapshot mismatch; recheck needed"
                severity = "warning"
            else:
                state_ko, state_en = f"미검증 ({state})", f"Unverified ({state})"
                severity = "warning"
            fragments.append(_source_health_line(
                f"{source} 리뷰", f"{source} reviews",
                f"{state_ko}{count_ko}", f"{state_en}{count_en}", severity,
            ))
    if not fragments:
        return _source_health_line(
            "리뷰 수집 검증", "Review source verification",
            "검증 기록 없음", "No verification record", "warning",
        )
    fragments.append(
        '<p class="ops-meta" '
        f'data-ko="마지막 리뷰 수집 검증: {_esc(checked)}" '
        f'data-en="Last review sync verification: {_esc(checked)}">'
        f'마지막 리뷰 수집 검증: {_esc(checked)}</p>'
    )
    return '<div class="detail-list">' + "".join(fragments) + "</div>"


def _ai_provider_health(status: Mapping[str, object]) -> str:
    outcome = str(status.get("outcome") or "unknown")
    checked = str(status.get("checked_at") or "—")
    providers = status.get("providers", [])
    statuses = [
        str(entry.get("status") or "unknown")
        for entry in providers
        if isinstance(entry, Mapping)
    ] if isinstance(providers, list) else []
    healthy = outcome in {"ok", "unchanged"} and all(value in {"ok", "unchanged", "manual_ok"} for value in statuses)
    ko = "공급자 가격 검증 정상" if healthy else f"가격 확인 필요 ({outcome})"
    en = "Provider price verification OK" if healthy else f"Pricing check needed ({outcome})"
    return (
        '<div class="detail-list">'
        + _source_health_line(
            "AI 공급자 가격", "AI provider pricing",
            ko, en, "ok" if healthy else "warning",
        )
        + '<p class="ops-meta" '
        f'data-ko="마지막 AI 가격 확인: {_esc(checked)}" '
        f'data-en="Last provider price check: {_esc(checked)}">'
        f'마지막 AI 가격 확인: {_esc(checked)}</p>'
        + "</div>"
    )


def _release_sync_health(status: Mapping[str, object]) -> str:
    outcome = str(status.get("outcome") or "unknown")
    checked = str(status.get("checked_at") or "—")
    ok = outcome in {"synced", "skipped", "not_found"}
    display_ko = {
        "synced": "GitHub 릴리즈 동기화 완료",
        "skipped": "동기화 건너뜀",
        "not_found": "대상 릴리즈 없음",
    }.get(outcome, f"동기화 확인 필요 ({outcome})")
    display_en = {
        "synced": "GitHub releases synchronized",
        "skipped": "Sync skipped",
        "not_found": "No matching release",
    }.get(outcome, f"Release sync needs review ({outcome})")
    return (
        '<div class="detail-list">'
        + _source_health_line(
            "전역 릴리즈 동기화", "Global release synchronization",
            display_ko, display_en, "ok" if ok else "warning",
        )
        + '<p class="ops-meta" '
        f'data-ko="마지막 릴리즈 확인: {_esc(checked)}" '
        f'data-en="Last release check: {_esc(checked)}">'
        f'마지막 릴리즈 확인: {_esc(checked)}</p>'
        + "</div>"
    )


def _app_detail(
    app: Mapping[str, object],
    homepage_repo: Path,
    store_items: Sequence[Mapping[str, object]],
    releases: Sequence[Mapping[str, object]],
    reviews: Sequence[Mapping[str, object]],
    dependencies: Sequence[Mapping[str, object]],
    pricing: Sequence[Mapping[str, object]],
    funnel_summary: Mapping[str, object],
    site_items: Sequence[Mapping[str, object]] = (),
    ai_manager_report: Mapping[str, object] | None = None,
    review_sync_status: Mapping[str, object] | None = None,
    ai_provider_pricing_status: Mapping[str, object] | None = None,
    release_sync_status: Mapping[str, object] | None = None,
) -> str:
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
    review_health_html = _review_source_health(slug, review_sync_status or {})
    release_health_html = _release_sync_health(release_sync_status or {})
    has_ai_products = any(
        item.get("product_type") == "ai_credit" or item.get("ai_margin_status")
        for item in app_prices
    )
    ai_health_html = _ai_provider_health(ai_provider_pricing_status or {}) if has_ai_products else ""
    app_site = next(
        (
            item
            for item in site_items
            if str(item.get("kind") or "") == "app"
            and str(item.get("slug") or "") == slug
        ),
        {},
    )
    report = ai_manager_report if isinstance(ai_manager_report, Mapping) else {}
    policy_alerts_raw = report.get("policy_alerts", []) if isinstance(report, Mapping) else []
    app_policy_alerts = [
        item
        for item in policy_alerts_raw
        if isinstance(item, Mapping) and str(item.get("app_slug") or "") == slug
    ] if isinstance(policy_alerts_raw, list) else []

    ios_version, ios_status = _store_stat(app_stores, "ios")
    android_version, android_status = _store_stat(app_stores, "android")
    ios_status_ko = _store_status_ko(ios_status)
    android_status_ko = _store_status_ko(android_status)
    ios_status_en = "No data" if ios_status == "수집 기록 없음" else ios_status
    android_status_en = "No data" if android_status == "수집 기록 없음" else android_status
    repo_version = next(
        (
            str(item.get("resolved_version") or item.get("declared_version") or "—")
            for item in app_deps
            if str(item.get("package_type") or "") == "app_version"
        ),
        "—",
    )
    latest_release = next(
        (str(item.get("tag") or item.get("version") or "—") for item in reversed(app_releases)),
        "—",
    )
    pending_reviews = sum(
        1
        for item in app_reviews
        if str(item.get("review_kind") or "") != "rating_only"
        and str(item.get("status") or "") != "replied"
        and not item.get("developer_reply")
    )
    rating_only_reviews = sum(
        1 for item in app_reviews if str(item.get("review_kind") or "") == "rating_only"
    )
    pending_releases = sum(
        1
        for item in app_releases
        if str(item.get("release_channel") or "public") == "public"
        and str(item.get("status") or "") in {"planned", "ready"}
    )
    platform_badges = "".join(
        f"<span>{_esc('iOS' if value == 'ios' else 'Android' if value == 'android' else value)}</span>"
        for value in str(app.get("platforms") or "").split("|")
        if value
    )

    store_rows = "".join(_bilingual_store_row(item) for item in app_stores) or (
        '<div class="empty-note" data-ko="스토어 상태 기록이 없어요." '
        'data-en="No store status is available.">스토어 상태 기록이 없어요.</div>'
    )
    price_rows = "".join(_bilingual_price_row(item) for item in app_prices) or (
        '<div class="empty-note" data-ko="등록된 유료 제품 가격이 없어요." '
        'data-en="No paid product price is registered.">등록된 유료 제품 가격이 없어요.</div>'
    )
    review_rows = "".join(
        _review_card_html(item, index) for index, item in enumerate(app_reviews)
    ) or (
        '<div class="empty-note" data-ko="수집된 리뷰가 없어요." '
        'data-en="No collected reviews.">수집된 리뷰가 없어요.</div>'
    )
    release_rows = "".join(
        _release_card_html(item, index) for index, item in enumerate(app_releases)
    ) or (
        '<div class="empty-note" data-ko="릴리즈 기록이 없어요." '
        'data-en="No release records.">릴리즈 기록이 없어요.</div>'
    )
    visible_deps = [
        item
        for item in app_deps
        if str(item.get("package_type") or "") != "app_version"
        and not (
            str(item.get("package_type") or "") == "dependency"
            and str(item.get("declared_version") or "") == "sdk:flutter"
        )
    ]
    dependency_rows = "".join(_dependency_card_html(item) for item in visible_deps) or (
        '<div class="empty-note" data-ko="표시할 Flutter/플러그인 항목이 없어요." '
        'data-en="No Flutter/plugin rows to display.">표시할 Flutter/플러그인 항목이 없어요.</div>'
    )
    if isinstance(app_site, Mapping) and app_site:
        site_html = (
            '<div class="site-freshness">'
            '<div class="detail-stat"><span data-ko="앱 페이지 갱신" data-en="App page updated">앱 페이지 갱신</span>'
            f'<b>{_esc(app_site.get("landing_updated_at") or "—")}</b></div>'
            '<div class="detail-stat"><span data-ko="스크린샷 갱신" data-en="Screenshots updated">스크린샷 갱신</span>'
            f'<b>{_esc(app_site.get("screenshots_updated_at") or "—")}</b>'
            f'<span data-ko="{_esc(app_site.get("screenshot_count") or 0)}장" data-en="{_esc(app_site.get("screenshot_count") or 0)} screenshots">{_esc(app_site.get("screenshot_count") or 0)}장</span></div>'
            '<div class="detail-stat"><span data-ko="에셋 갱신" data-en="Assets updated">에셋 갱신</span>'
            f'<b>{_esc(app_site.get("assets_updated_at") or "—")}</b></div>'
            "</div>"
        )
    else:
        site_html = (
            '<div class="empty-note" data-ko="사이트·스크린샷 최신성 기록이 없어요." '
            'data-en="No site/screenshot freshness record is available.">사이트·스크린샷 최신성 기록이 없어요.</div>'
        )

    alert_cards: list[str] = []
    for alert in app_policy_alerts:
        kind = str(alert.get("kind") or "policy alert")
        status = str(alert.get("status") or "review_required")
        summary = str(alert.get("summary") or "Review the store-console warning.")
        note = str(alert.get("operational_note") or "")
        store = str(alert.get("store") or "store")
        occurred = str(alert.get("occurred_at") or "")
        reference = _safe_href(alert.get("reference_url"))
        detail = (
            f'<p>{_esc(summary)}</p>'
            + (f'<p><b data-ko="현재 조치" data-en="Current action">현재 조치</b> · {_esc(note)}</p>' if note else "")
            + (f'<p><b data-ko="감지" data-en="Detected">감지</b> · {_esc(occurred)}</p>' if occurred else "")
            + (
                f'<p><a href="{_esc(reference)}" target="_blank" rel="noopener noreferrer" '
                'data-ko="공식 참고 열기" data-en="Open official reference">공식 참고 열기</a></p>'
                if reference
                else ""
            )
        )
        alert_cards.append(
            '<article class="release-card">'
            '<div class="release-head">'
            f'<strong>{_esc(store)} · {_esc(kind)}</strong>'
            f'<span class="mini-badge warn">{_esc(status)}</span>'
            f'</div>{detail}</article>'
        )
    alerts_html = "".join(alert_cards) or (
        '<div class="empty-note" data-ko="현재 앱별 정책·운영 경고가 없어요." '
        'data-en="There are no current app-specific policy or operations alerts.">현재 앱별 정책·운영 경고가 없어요.</div>'
    )

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

<section class="detail-section" id="overview">
  <h2 data-ko="개요" data-en="Overview">개요</h2>
  <div class="detail-grid">
    <div class="detail-stat"><span>App Store</span><b>{_esc(ios_version)}</b><span data-ko="{_esc(ios_status_ko)}" data-en="{_esc(ios_status_en)}">{_esc(ios_status_ko)}</span></div>
    <div class="detail-stat"><span>Play Store</span><b>{_esc(android_version)}</b><span data-ko="{_esc(android_status_ko)}" data-en="{_esc(android_status_en)}">{_esc(android_status_ko)}</span></div>
    <div class="detail-stat"><span>GitHub main</span><b>{_esc(repo_version)}</b></div>
    <div class="detail-stat"><span data-ko="최근 릴리즈" data-en="Latest release">최근 릴리즈</span><b>{_esc(latest_release)}</b></div>
  </div>
</section>

{_funnel_section(app, funnel_summary)}

<section class="detail-section" id="store">
  <h2 data-ko="스토어·수익" data-en="Store & revenue">스토어·수익</h2>
  <div class="subsection-head"><h3 data-ko="스토어 버전·상태" data-en="Store versions & status">스토어 버전·상태</h3></div>
  <div class="detail-list">{store_rows}</div>
  <div class="subsection-head">
    <h3 data-ko="가격·수익 구조" data-en="Pricing & unit economics">가격·수익 구조</h3>
    <p data-ko="구매 건수는 유입·전환에서 따로 보고, 여기서는 가격과 단위 경제성만 봐요." data-en="Purchase counts stay in Acquisition; this section focuses on pricing and unit economics.">구매 건수는 유입·전환에서 따로 보고, 여기서는 가격과 단위 경제성만 봐요.</p>
  </div>
  <div class="pricing-list">{price_rows}</div>
  {('<div class="subsection-head"><h3 data-ko="AI 공급자 가격 검증" data-en="AI provider pricing verification">AI 공급자 가격 검증</h3></div>' + ai_health_html) if has_ai_products else ""}
</section>

<section class="detail-section" id="reviews">
  <div class="subsection-head">
    <h2 data-ko="리뷰" data-en="Reviews">리뷰</h2>
    <div class="ops-actions">
      <button class="ops-button primary" type="button" data-review-sync data-ko="리뷰 동기화" data-en="Sync reviews">리뷰 동기화</button>
    </div>
  </div>
  <div class="detail-grid">
    <div class="detail-stat"><span data-ko="수집 리뷰" data-en="Collected reviews">수집 리뷰</span><b>{len(app_reviews)}</b></div>
    <div class="detail-stat"><span data-ko="답변 대기" data-en="Awaiting reply">답변 대기</span><b>{pending_reviews}</b></div>
    <div class="detail-stat"><span data-ko="별점만" data-en="Rating only">별점만</span><b>{rating_only_reviews}</b></div>
    <div class="detail-stat"><span data-ko="동기화 범위" data-en="Sync scope">동기화 범위</span><b data-ko="전체 앱" data-en="All apps">전체 앱</b></div>
  </div>
  <div class="subsection-head"><h3 data-ko="스토어별 리뷰 수집 검증" data-en="Review collection verification by store">스토어별 리뷰 수집 검증</h3></div>
  {review_health_html}
  <div class="token-note" data-app-token-note hidden>
    <span data-ko="답변 승인·게시와 리뷰 동기화에는 GitHub 연결이 필요해요." data-en="Review approval, publishing, and sync require a GitHub connection.">답변 승인·게시와 리뷰 동기화에는 GitHub 연결이 필요해요.</span>
    <a href="/ops/settings/" data-ko="설정에서 연결" data-en="Connect in Settings">설정에서 연결</a>
  </div>
  <div class="ops-message" data-review-sync-message></div>
  <div class="review-list">{review_rows}</div>
</section>

<section class="detail-section" id="technical">
  <h2 data-ko="기술·운영" data-en="Technical & operations">기술·운영</h2>
  <div class="detail-row">
    <b data-ko="공개 제품 페이지" data-en="Public product page">공개 제품 페이지</b>
    <span><a href="/apps/{_esc(slug)}/">onnellab.com/apps/{_esc(slug)}</a></span>
  </div>
  <div class="subsection-head"><h3 data-ko="사이트·자산 최신성" data-en="Site & asset freshness">사이트·자산 최신성</h3></div>
  {site_html}
  <div class="subsection-head"><h3 data-ko="정책·운영 경고" data-en="Policy & operations alerts">정책·운영 경고</h3></div>
  <div class="release-list">{alerts_html}</div>
  <div class="subsection-head">
    <h3 data-ko="릴리즈 운영" data-en="Release operations">릴리즈 운영</h3>
    <p data-ko="자동 공개 대기 {pending_releases}건" data-en="{pending_releases} awaiting automatic publication">자동 공개 대기 {pending_releases}건</p>
  </div>
  <div class="release-list">{release_rows}</div>
  <div class="subsection-head"><h3 data-ko="릴리즈 동기화 검증" data-en="Release synchronization verification">릴리즈 동기화 검증</h3></div>
  {release_health_html}
  <div class="subsection-head">
    <h3 data-ko="Flutter·플러그인" data-en="Flutter & plugins">Flutter·플러그인</h3>
    <p data-ko="표시 {len(visible_deps)}개" data-en="{len(visible_deps)} visible items">표시 {len(visible_deps)}개</p>
  </div>
  <div class="dependency-list">{dependency_rows}</div>
</section>

{_app_controls_script(app_reviews)}
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
    site_items: Sequence[Mapping[str, object]] = (),
    ai_manager_report: Mapping[str, object] | None = None,
    review_sync_status: Mapping[str, object] | None = None,
    ai_provider_pricing_status: Mapping[str, object] | None = None,
    release_sync_status: Mapping[str, object] | None = None,
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
                site_items,
                ai_manager_report,
                review_sync_status,
                ai_provider_pricing_status,
                release_sync_status,
            ),
            encoding="utf-8",
        )
        pages.append(app_path)
    return pages
