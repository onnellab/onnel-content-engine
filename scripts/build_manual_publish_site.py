#!/usr/bin/env python3
"""Build a hosted manual publishing dashboard from generated drafts."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOPICS = ROOT / "data" / "topics.csv"
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "generated" / "manual-publish" / "index.html"
KST = ZoneInfo("Asia/Seoul")


PLATFORM_LABELS = {
    "x": "X",
    "linkedin": "LinkedIn",
    "bluesky": "Bluesky",
    "devto": "Dev.to",
    "hashnode": "Hashnode",
    "medium": "Medium",
}

SOCIAL_DUE_DELAYS_DAYS = {"x": 0, "linkedin": 1, "bluesky": 1}
SYNDICATION_DUE_DELAYS_DAYS = {"devto": 2, "hashnode": 3, "medium": 4}


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_topics(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["id"]: {key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)}


def read_text(path_value: str) -> str:
    path = ROOT / path_value
    if not path.exists():
        path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def parse_topic_datetime(value: str) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def due_at_for(topic: dict[str, str] | None, platform: str, kind: str) -> str:
    if not topic:
        return ""
    base = parse_topic_datetime(topic.get("published_at", "") or topic.get("scheduled_at", ""))
    if not base:
        return ""
    delays = SOCIAL_DUE_DELAYS_DAYS if kind == "social" else SYNDICATION_DUE_DELAYS_DAYS
    delay = delays.get(platform)
    if delay is None:
        return ""
    return (base + timedelta(days=delay)).isoformat()


def item_key(topic_id: object, platform: str, language: object, template_id: object) -> str:
    return "::".join([str(topic_id), platform, str(language), str(template_id)])


def asset_href(path_value: str) -> str:
    if not path_value:
        return ""
    if path_value.startswith("generated/"):
        return "../" + path_value.removeprefix("generated/")
    return "../" + path_value


def compose_url(platform: str, text: str, canonical_url: str) -> str:
    if platform == "x":
        return "https://twitter.com/intent/tweet?text=" + quote(text)
    if platform == "bluesky":
        return "https://bsky.app/intent/compose?text=" + quote(text)
    if platform == "linkedin":
        return "https://www.linkedin.com/sharing/share-offsite/?url=" + quote(canonical_url)
    if platform == "devto":
        return "https://dev.to/new"
    if platform == "hashnode":
        return "https://hashnode.com/draft"
    if platform == "medium":
        return "https://medium.com/new-story"
    return canonical_url


def social_items(manifest_path: Path, topics: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for post in manifest.get("posts", []):
        if not isinstance(post, dict):
            continue
        platform = str(post.get("platform", ""))
        topic_id = post.get("topic_id", "")
        language = post.get("language", "")
        template_id = post.get("template_id", "")
        draft_path = str(post.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(post.get("canonical_url", ""))
        card_asset_path = str(post.get("card_asset_path", ""))
        items.append(
            {
                "kind": "social",
                "topic_id": topic_id,
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": language,
                "slug": post.get("slug", ""),
                "template_id": template_id,
                "manual_key": item_key(topic_id, platform, language, template_id),
                "is_variant": bool(post.get("is_variant")),
                "status": post.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": card_asset_path,
                "card_asset_href": asset_href(card_asset_path),
                "text": text,
                "length": post.get("weighted_length") or len(text),
                "approved_at": post.get("approved_at", ""),
                "posted_url": post.get("posted_url", ""),
                "posted_at": post.get("posted_at", ""),
                "last_attempt_at": post.get("last_attempt_at", ""),
                "error_type": post.get("error_type", ""),
                "error": post.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
                "due_at": due_at_for(topics.get(str(topic_id)), platform, "social"),
            }
        )
    return items


def syndication_items(manifest_path: Path, topics: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for draft in manifest.get("drafts", []):
        if not isinstance(draft, dict):
            continue
        platform = str(draft.get("platform", ""))
        topic_id = draft.get("topic_id", "")
        language = draft.get("language", "")
        template_id = "markdown"
        draft_path = str(draft.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(draft.get("canonical_url", ""))
        items.append(
            {
                "kind": "syndication",
                "topic_id": topic_id,
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": language,
                "slug": draft.get("slug", ""),
                "template_id": template_id,
                "manual_key": item_key(topic_id, platform, language, template_id),
                "is_variant": False,
                "status": draft.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": "",
                "card_asset_href": "",
                "text": text,
                "length": len(text),
                "approved_at": draft.get("approved_at", ""),
                "posted_url": draft.get("posted_url", ""),
                "posted_at": draft.get("posted_at", ""),
                "last_attempt_at": draft.get("last_attempt_at", ""),
                "error_type": draft.get("error_type", ""),
                "error": draft.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
                "due_at": due_at_for(topics.get(str(topic_id)), platform, "syndication"),
            }
        )
    return items


def html_document(items: list[dict[str, object]]) -> str:
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    total = len(items)
    manual = sum(1 for item in items if item["status"] in {"draft", "failed", "variant", "approved"})
    posted = sum(1 for item in items if item["status"] == "posted")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ONNELLAB Manual Publish</title>
  <meta name="theme-color" content="#fffaf5">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="ONNEL Publish">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <link rel="manifest" href="./manifest.webmanifest">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <style>
    :root {{
      --ink: #171717; --muted: #666; --line: #d9d4cf; --surface: #fffaf5; --panel: #fff;
      --blue: #2c6fbb; --peach: #f0b29d; --ok: #2b7a4b; --bad: #b3261e;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--ink); background: var(--surface); }}
    header {{ position: sticky; top: 0; z-index: 5; border-bottom: 1px solid var(--line); background: rgba(255, 250, 245, .96); backdrop-filter: blur(12px); }}
    .bar {{ max-width: 1180px; margin: 0 auto; padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 800; letter-spacing: 0; }}
    .mark {{ width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid var(--ink); background: #f5d3c7; font-size: 13px; font-weight: 900; }}
    .summary {{ display: flex; gap: 8px; flex-wrap: wrap; color: var(--muted); font-size: 13px; }}
    .pill {{ border: 1px solid var(--line); padding: 5px 8px; background: var(--panel); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px 20px 48px; }}
    .auth {{ display: grid; grid-template-columns: minmax(220px, 1fr) auto auto auto; gap: 8px; margin-bottom: 12px; }}
    .controls {{ display: grid; grid-template-columns: minmax(220px, 1fr) repeat(4, minmax(120px, 160px)); gap: 10px; margin-bottom: 18px; }}
    .platforms {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; margin-bottom: 18px; }}
    .platform-card {{ border: 1px solid var(--line); background: var(--panel); padding: 10px; border-radius: 8px; }}
    .platform-card strong {{ display: block; font-size: 14px; margin-bottom: 6px; }}
    .platform-card span {{ display: block; color: var(--muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }}
    input, select {{ width: 100%; min-height: 38px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); padding: 8px 10px; font: inherit; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 14px; align-items: start; }}
    article {{ border: 1px solid var(--line); background: var(--panel); border-radius: 8px; overflow: hidden; }}
    .thumb {{ width: 100%; aspect-ratio: 1.91 / 1; object-fit: cover; display: block; border-bottom: 1px solid var(--line); background: #eee; }}
    .body {{ padding: 12px; }}
    .meta {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }}
    .tag {{ font-size: 12px; border: 1px solid var(--line); padding: 3px 6px; color: var(--muted); background: #fff; }}
    .tag.status-posted {{ color: var(--ok); border-color: #b7d9c5; }}
    .tag.status-failed {{ color: var(--bad); border-color: #efb5b0; }}
    .tag.status-approved {{ color: var(--blue); border-color: #acc9e7; }}
    .tag.status-due {{ color: #fff; border-color: var(--bad); background: var(--bad); }}
    .tag.status-done {{ color: var(--ok); border-color: #b7d9c5; background: #f2fbf5; }}
    h2 {{ font-size: 15px; line-height: 1.35; margin: 0 0 8px; }}
    textarea {{ width: 100%; min-height: 180px; resize: vertical; border: 1px solid var(--line); padding: 10px; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; color: var(--ink); background: #fff; }}
    .actions {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }}
    button, a.button {{ min-height: 36px; border: 1px solid var(--ink); background: var(--ink); color: #fff; padding: 8px 10px; font: inherit; text-decoration: none; text-align: center; cursor: pointer; border-radius: 6px; }}
    button.secondary, a.secondary {{ background: #fff; color: var(--ink); border-color: var(--line); }}
    .note {{ margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }}
    .error {{ margin-top: 8px; color: var(--bad); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }}
    .empty {{ border: 1px dashed var(--line); padding: 28px; color: var(--muted); background: var(--panel); text-align: center; }}
    @media (max-width: 760px) {{
      .bar {{ align-items: flex-start; flex-direction: column; }}
      .auth, .controls {{ grid-template-columns: 1fr 1fr; }}
      .auth input, .controls input {{ grid-column: 1 / -1; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="brand"><div class="mark">OL</div><div>ONNELLAB Manual Publish</div></div>
      <div class="summary">
        <span class="pill">total {total}</span>
        <span class="pill"><span id="due-count">0</span> due</span>
        <span class="pill">manual {manual}</span>
        <span class="pill">posted {posted}</span>
        <span class="pill" id="sync-state">offline</span>
      </div>
    </div>
  </header>
  <main>
    <div class="auth">
      <input id="token" type="password" autocomplete="off" placeholder="GitHub token for synced done state">
      <button id="save-token" type="button">Connect sync</button>
      <button id="refresh-state" type="button" class="secondary">Refresh</button>
      <button id="enable-badge" type="button" class="secondary">Enable badge</button>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search topic, platform, language, status">
      <select id="platform"><option value="">All platforms</option></select>
      <select id="language"><option value="">All languages</option></select>
      <select id="status"><option value="">All statuses</option></select>
      <select id="visibility"><option value="active">Active only</option><option value="all">Show done</option><option value="due">Due only</option></select>
    </div>
    <div id="platform-summary" class="platforms"></div>
    <div id="grid" class="grid"></div>
    <div id="empty" class="empty" hidden>No drafts match the current filters.</div>
  </main>
  <script id="manual-data" type="application/json">{data}</script>
  <script>
    const items = JSON.parse(document.getElementById('manual-data').textContent);
    const stateRepo = 'onnellab/onnel-content-engine';
    const statePath = 'data/manual_publish_state.json';
    const stateBranch = 'main';
    const tokenKey = 'onnellab-manual-publish-token';
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    const dueCount = document.getElementById('due-count');
    const syncState = document.getElementById('sync-state');
    const filters = {{
      search: document.getElementById('search'),
      platform: document.getElementById('platform'),
      language: document.getElementById('language'),
      status: document.getElementById('status'),
      visibility: document.getElementById('visibility'),
    }};
    const tokenInput = document.getElementById('token');
    const badgeButton = document.getElementById('enable-badge');
    const platformSummary = document.getElementById('platform-summary');
    let remoteState = {{ done: {{}}, updated_at: '', version: 1 }};
    let remoteSha = '';

    tokenInput.value = sessionStorage.getItem(tokenKey) || '';

    function optionize(select, values) {{
      values.forEach((value) => {{
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}
    optionize(filters.platform, [...new Set(items.map((item) => item.platform_label))].sort());
    optionize(filters.language, [...new Set(items.map((item) => item.language))].sort());
    optionize(filters.status, [...new Set(items.map((item) => item.status))].sort());

    function githubToken() {{
      return sessionStorage.getItem(tokenKey) || tokenInput.value.trim();
    }}

    function setSync(label) {{
      syncState.textContent = label;
    }}

    function decodeBase64Unicode(value) {{
      const binary = atob(value.replace(/\\n/g, ''));
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }}

    function encodeBase64Unicode(value) {{
      const bytes = new TextEncoder().encode(value);
      let binary = '';
      bytes.forEach((byte) => binary += String.fromCharCode(byte));
      return btoa(binary);
    }}

    async function githubRequest(path, options = {{}}) {{
      const token = githubToken();
      if (!token) throw new Error('GitHub token is required for sync');
      const response = await fetch('https://api.github.com' + path, {{
        ...options,
        headers: {{
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Authorization': 'Bearer ' + token,
          ...(options.headers || {{}}),
        }},
      }});
      const text = await response.text();
      const data = text ? JSON.parse(text) : {{}};
      if (!response.ok) throw new Error(data.message || 'GitHub request failed');
      return data;
    }}

    async function loadRemoteState() {{
      setSync('syncing');
      try {{
        const data = await githubRequest(`/repos/${{stateRepo}}/contents/${{statePath}}?ref=${{stateBranch}}`);
        remoteSha = data.sha;
        remoteState = JSON.parse(decodeBase64Unicode(data.content));
        remoteState.done ||= {{}};
        setSync('synced');
      }} catch (error) {{
        setSync('sync error');
        console.error(error);
      }}
      render();
    }}

    async function updateAppBadge() {{
      const count = items.filter(isDue).length;
      if (!('setAppBadge' in navigator) || !('clearAppBadge' in navigator)) return;
      try {{
        if (count > 0) await navigator.setAppBadge(count);
        else await navigator.clearAppBadge();
      }} catch (error) {{
        console.warn(error);
      }}
    }}

    async function saveRemoteState(message) {{
      remoteState.updated_at = new Date().toISOString();
      const content = encodeBase64Unicode(JSON.stringify(remoteState, null, 2) + '\\n');
      const payload = {{ message, content, branch: stateBranch }};
      if (remoteSha) payload.sha = remoteSha;
      const data = await githubRequest(`/repos/${{stateRepo}}/contents/${{statePath}}`, {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload),
      }});
      remoteSha = data.content.sha;
      setSync('synced');
    }}

    async function copyText(text, button) {{
      await navigator.clipboard.writeText(text);
      flash(button, 'Copied');
    }}

    async function copyImage(src, button) {{
      if (!src || !window.ClipboardItem) {{
        flash(button, 'Open image');
        return;
      }}
      const response = await fetch(src);
      const blob = await response.blob();
      await navigator.clipboard.write([new ClipboardItem({{ [blob.type]: blob }})]);
      flash(button, 'Image copied');
    }}

    async function copyThenOpen(item, button) {{
      await navigator.clipboard.writeText(item.text);
      window.open(item.open_url, '_blank', 'noopener,noreferrer');
      flash(button, 'Opened');
    }}

    function flash(button, label) {{
      const original = button.textContent;
      button.textContent = label;
      setTimeout(() => {{ button.textContent = original; }}, 1200);
    }}

    function isDone(item) {{
      return item.status === 'posted' || Boolean(remoteState.done?.[item.manual_key]);
    }}

    async function markDone(item, button) {{
      remoteState.done ||= {{}};
      remoteState.done[item.manual_key] = {{
        topic_id: item.topic_id,
        platform: item.platform,
        language: item.language,
        template_id: item.template_id,
        marked_at: new Date().toISOString(),
      }};
      flash(button, 'Saving');
      await saveRemoteState('Mark manual publish item done');
      render();
    }}

    async function undoDone(item, button) {{
      if (remoteState.done) delete remoteState.done[item.manual_key];
      flash(button, 'Saving');
      await saveRemoteState('Undo manual publish item done');
      render();
    }}

    function dueDate(item) {{
      if (!item.due_at) return null;
      const date = new Date(item.due_at);
      return Number.isNaN(date.getTime()) ? null : date;
    }}

    function isDue(item) {{
      if (isDone(item) || item.is_variant) return false;
      if (!['draft', 'failed', 'approved'].includes(item.status)) return false;
      const date = dueDate(item);
      return date ? Date.now() >= date.getTime() : false;
    }}

    function formatDue(item) {{
      const date = dueDate(item);
      if (!date) return '';
      return new Intl.DateTimeFormat('ko-KR', {{ dateStyle: 'medium', timeStyle: 'short' }}).format(date);
    }}

    function parseDate(value) {{
      if (!value) return null;
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? null : date;
    }}

    function formatDate(value) {{
      const date = parseDate(value);
      if (!date) return 'none';
      return new Intl.DateTimeFormat('ko-KR', {{ dateStyle: 'medium', timeStyle: 'short' }}).format(date);
    }}

    function daysAgo(value) {{
      const date = parseDate(value);
      if (!date) return 'no record';
      const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86400000));
      return days === 0 ? 'today' : `${{days}} day${{days === 1 ? '' : 's'}} ago`;
    }}

    function latestDate(values) {{
      return values.map(parseDate).filter(Boolean).sort((a, b) => b - a)[0] || null;
    }}

    function renderPlatformSummary() {{
      const platforms = [...new Set(items.map((item) => item.platform_label))].sort();
      platformSummary.textContent = '';
      platforms.forEach((label) => {{
        const rows = items.filter((item) => item.platform_label === label && !item.is_variant);
        const posted = rows.filter((item) => item.status === 'posted');
        const failed = rows.filter((item) => item.status === 'failed');
        const drafts = rows.filter((item) => ['draft', 'approved'].includes(item.status));
        const latestPosted = latestDate(posted.map((item) => item.posted_at));
        const latestAttempt = latestDate(rows.map((item) => item.last_attempt_at || item.approved_at || item.posted_at));
        const card = document.createElement('div');
        card.className = 'platform-card';
        const title = document.createElement('strong');
        title.textContent = label;
        const status = document.createElement('span');
        status.textContent = `${{posted.length}} posted / ${{drafts.length}} waiting / ${{failed.length}} failed`;
        const postedLine = document.createElement('span');
        postedLine.textContent = 'last posted: ' + (latestPosted ? `${{formatDate(latestPosted.toISOString())}} (${{daysAgo(latestPosted.toISOString())}})` : 'none');
        const attemptLine = document.createElement('span');
        attemptLine.textContent = 'last update: ' + (latestAttempt ? `${{formatDate(latestAttempt.toISOString())}} (${{daysAgo(latestAttempt.toISOString())}})` : 'none');
        card.append(title, status, postedLine, attemptLine);
        platformSummary.appendChild(card);
      }});
    }}

    function statusClass(status) {{
      return 'status-' + String(status || 'draft').replace(/[^a-z0-9]+/g, '-');
    }}

    function render() {{
      const query = filters.search.value.trim().toLowerCase();
      const platform = filters.platform.value;
      const language = filters.language.value;
      const status = filters.status.value;
      const visibility = filters.visibility.value;
      const visible = items.filter((item) => {{
        const haystack = [item.topic_id, item.platform_label, item.language, item.status, item.template_id, item.text].join(' ').toLowerCase();
        const done = isDone(item);
        const due = isDue(item);
        return (!query || haystack.includes(query))
          && (!platform || item.platform_label === platform)
          && (!language || item.language === language)
          && (!status || item.status === status)
          && (visibility === 'all' || (visibility === 'due' ? due : !done));
      }});
      dueCount.textContent = String(items.filter(isDue).length);
      grid.textContent = '';
      empty.hidden = visible.length !== 0;
      visible.forEach((item) => grid.appendChild(card(item)));
      renderPlatformSummary();
      updateAppBadge();
    }}

    function card(item) {{
      const article = document.createElement('article');
      if (item.card_asset_href) {{
        const img = document.createElement('img');
        img.className = 'thumb';
        img.src = item.card_asset_href;
        img.alt = item.topic_id + ' social card';
        article.appendChild(img);
      }}
      const body = document.createElement('div');
      body.className = 'body';
      const meta = document.createElement('div');
      meta.className = 'meta';
      [item.platform_label, item.language, item.status, item.template_id, item.kind].forEach((value, index) => {{
        const span = document.createElement('span');
        span.className = 'tag' + (index === 2 ? ' ' + statusClass(value) : '');
        span.textContent = value;
        meta.appendChild(span);
      }});
      if (isDue(item)) {{
        const due = document.createElement('span');
        due.className = 'tag status-due';
        due.textContent = 'due';
        meta.appendChild(due);
      }}
      if (isDone(item)) {{
        const done = document.createElement('span');
        done.className = 'tag status-done';
        done.textContent = 'done';
        meta.appendChild(done);
      }}
      const title = document.createElement('h2');
      title.textContent = item.topic_id + ' / ' + item.slug + (item.is_variant ? ' / variant' : '');
      const textarea = document.createElement('textarea');
      textarea.value = item.text;
      textarea.spellcheck = false;
      const actions = document.createElement('div');
      actions.className = 'actions';
      const copy = document.createElement('button');
      copy.textContent = item.kind === 'syndication' ? 'Copy markdown' : 'Copy post';
      copy.onclick = () => copyText(textarea.value, copy);
      const open = document.createElement('button');
      open.textContent = 'Copy and open';
      open.onclick = () => copyThenOpen({{ ...item, text: textarea.value }}, open);
      const doneButton = document.createElement('button');
      doneButton.className = 'secondary';
      doneButton.textContent = isDone(item) ? 'Undo done' : 'Mark done';
      doneButton.onclick = () => isDone(item) ? undoDone(item, doneButton) : markDone(item, doneButton);
      actions.append(copy, open, doneButton);
      if (item.card_asset_href) {{
        const copyImg = document.createElement('button');
        copyImg.className = 'secondary';
        copyImg.textContent = 'Copy image';
        copyImg.onclick = () => copyImage(item.card_asset_href, copyImg);
        const openImg = document.createElement('a');
        openImg.className = 'button secondary';
        openImg.textContent = 'Open image';
        openImg.href = item.card_asset_href;
        openImg.target = '_blank';
        openImg.rel = 'noopener noreferrer';
        actions.append(copyImg, openImg);
      }}
      const note = document.createElement('div');
      note.className = 'note';
      note.textContent = item.draft_path + ' / length ' + item.length + (item.due_at ? ' / due ' + formatDue(item) : '');
      body.append(meta, title, textarea, actions, note);
      if (item.error) {{
        const error = document.createElement('div');
        error.className = 'error';
        error.textContent = item.error;
        body.appendChild(error);
      }}
      article.appendChild(body);
      return article;
    }}

    document.getElementById('save-token').onclick = async () => {{
      sessionStorage.setItem(tokenKey, tokenInput.value.trim());
      await loadRemoteState();
    }};
    document.getElementById('refresh-state').onclick = loadRemoteState;
    badgeButton.onclick = async () => {{
      if ('Notification' in window && Notification.permission === 'default') {{
        await Notification.requestPermission();
      }}
      await updateAppBadge();
      flash(badgeButton, 'Badge ready');
    }};
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(console.warn);
    Object.values(filters).forEach((input) => input.addEventListener('input', render));
    if (tokenInput.value) loadRemoteState(); else render();
  </script>
</body>
</html>
"""


def pwa_manifest_document() -> str:
    return json.dumps(
        {
            "name": "ONNELLAB Manual Publish",
            "short_name": "ONNEL Publish",
            "start_url": "/manual-publish/",
            "scope": "/manual-publish/",
            "display": "standalone",
            "background_color": "#fffaf5",
            "theme_color": "#fffaf5",
            "icons": [
                {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
                {"src": "/favicon-32x32.png", "sizes": "32x32", "type": "image/png"},
                {"src": "/favicon-16x16.png", "sizes": "16x16", "type": "image/png"},
            ],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def service_worker_document() -> str:
    return """const CACHE = 'onnellab-manual-publish-v1';
const ASSETS = ['./', './index.html', './manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
"""


def build_manual_publish_site(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    output: Path = DEFAULT_OUTPUT,
    topics_path: Path = DEFAULT_TOPICS,
) -> Path:
    topics = read_topics(topics_path)
    items = social_items(social_manifest, topics) + syndication_items(syndication_manifest, topics)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_document(items), encoding="utf-8")
    (output.parent / "manifest.webmanifest").write_text(pwa_manifest_document(), encoding="utf-8")
    (output.parent / "sw.js").write_text(service_worker_document(), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hosted manual publishing dashboard")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_manual_publish_site(args.social_manifest, args.syndication_manifest, args.output, args.topics)
    print(f"generated {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
