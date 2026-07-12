#!/usr/bin/env python3
"""Build a local manual publishing dashboard from generated drafts."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOCIAL_MANIFEST = ROOT / "generated" / "social" / "manifest.json"
DEFAULT_SYNDICATION_MANIFEST = ROOT / "generated" / "syndication" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "generated" / "manual-publish" / "index.html"


PLATFORM_LABELS = {
    "x": "X",
    "linkedin": "LinkedIn",
    "bluesky": "Bluesky",
    "devto": "Dev.to",
    "hashnode": "Hashnode",
    "medium": "Medium",
}


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path_value: str) -> str:
    path = ROOT / path_value
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


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


def social_items(manifest_path: Path) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for post in manifest.get("posts", []):
        if not isinstance(post, dict):
            continue
        platform = str(post.get("platform", ""))
        draft_path = str(post.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(post.get("canonical_url", ""))
        card_asset_path = str(post.get("card_asset_path", ""))
        items.append(
            {
                "kind": "social",
                "topic_id": post.get("topic_id", ""),
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": post.get("language", ""),
                "slug": post.get("slug", ""),
                "template_id": post.get("template_id", ""),
                "is_variant": bool(post.get("is_variant")),
                "status": post.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": card_asset_path,
                "card_asset_href": asset_href(card_asset_path),
                "text": text,
                "length": post.get("weighted_length") or len(text),
                "posted_url": post.get("posted_url", ""),
                "error_type": post.get("error_type", ""),
                "error": post.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
            }
        )
    return items


def syndication_items(manifest_path: Path) -> list[dict[str, object]]:
    manifest = read_json(manifest_path)
    items: list[dict[str, object]] = []
    for draft in manifest.get("drafts", []):
        if not isinstance(draft, dict):
            continue
        platform = str(draft.get("platform", ""))
        draft_path = str(draft.get("draft_path", ""))
        text = read_text(draft_path)
        canonical_url = str(draft.get("canonical_url", ""))
        items.append(
            {
                "kind": "syndication",
                "topic_id": draft.get("topic_id", ""),
                "platform": platform,
                "platform_label": PLATFORM_LABELS.get(platform, platform),
                "language": draft.get("language", ""),
                "slug": draft.get("slug", ""),
                "template_id": "markdown",
                "is_variant": False,
                "status": draft.get("status", ""),
                "draft_path": draft_path,
                "canonical_url": canonical_url,
                "card_asset_path": "",
                "card_asset_href": "",
                "text": text,
                "length": len(text),
                "posted_url": draft.get("posted_url", ""),
                "error_type": draft.get("error_type", ""),
                "error": draft.get("error", ""),
                "open_url": compose_url(platform, text, canonical_url),
            }
        )
    return items


def html_document(items: list[dict[str, object]]) -> str:
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    total = len(items)
    manual = sum(1 for item in items if item["status"] in {"draft", "failed", "variant"})
    posted = sum(1 for item in items if item["status"] == "posted")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ONNELLAB Manual Publish</title>
  <style>
    :root {{
      --ink: #171717;
      --muted: #646464;
      --line: #d9d4cf;
      --surface: #fffaf5;
      --panel: #ffffff;
      --blue: #2c6fbb;
      --peach: #f0b29d;
      --lilac: #b9a6d8;
      --ok: #2b7a4b;
      --warn: #a65f00;
      --bad: #b3261e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--surface);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 250, 245, 0.96);
      backdrop-filter: blur(12px);
    }}
    .bar {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      letter-spacing: 0;
    }}
    .mark {{
      width: 30px;
      height: 30px;
      display: grid;
      place-items: center;
      border: 1px solid var(--ink);
      background: #f5d3c7;
      color: var(--ink);
      font-size: 13px;
      font-weight: 900;
    }}
    .summary {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 13px;
    }}
    .pill {{
      border: 1px solid var(--line);
      padding: 5px 8px;
      background: var(--panel);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px 20px 48px;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) repeat(3, minmax(120px, 160px));
      gap: 10px;
      margin-bottom: 18px;
    }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      padding: 8px 10px;
      font: inherit;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
      gap: 14px;
      align-items: start;
    }}
    article {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
    }}
    .thumb {{
      width: 100%;
      aspect-ratio: 1.91 / 1;
      object-fit: cover;
      display: block;
      border-bottom: 1px solid var(--line);
      background: #eee;
    }}
    .body {{
      padding: 12px;
    }}
    .meta {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }}
    .tag {{
      font-size: 12px;
      border: 1px solid var(--line);
      padding: 3px 6px;
      color: var(--muted);
      background: #fff;
    }}
    .tag.status-posted {{ color: var(--ok); border-color: #b7d9c5; }}
    .tag.status-failed {{ color: var(--bad); border-color: #efb5b0; }}
    .tag.status-approved {{ color: var(--blue); border-color: #acc9e7; }}
    h2 {{
      font-size: 15px;
      line-height: 1.35;
      margin: 0 0 8px;
    }}
    textarea {{
      width: 100%;
      min-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      padding: 10px;
      font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: var(--ink);
      background: #fff;
    }}
    .actions {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    button, a.button {{
      min-height: 36px;
      border: 1px solid var(--ink);
      background: var(--ink);
      color: #fff;
      padding: 8px 10px;
      font: inherit;
      text-decoration: none;
      text-align: center;
      cursor: pointer;
      border-radius: 6px;
    }}
    button.secondary, a.secondary {{
      background: #fff;
      color: var(--ink);
      border-color: var(--line);
    }}
    .note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .error {{
      margin-top: 8px;
      color: var(--bad);
      font-size: 12px;
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .empty {{
      border: 1px dashed var(--line);
      padding: 28px;
      color: var(--muted);
      background: var(--panel);
      text-align: center;
    }}
    @media (max-width: 760px) {{
      .bar {{ align-items: flex-start; flex-direction: column; }}
      .controls {{ grid-template-columns: 1fr 1fr; }}
      .controls input {{ grid-column: 1 / -1; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="bar">
      <div class="brand"><div class="mark">OL</div><div>ONNELLAB Manual Publish</div></div>
      <div class="summary">
        <span class="pill">total {total}</span>
        <span class="pill">manual {manual}</span>
        <span class="pill">posted {posted}</span>
      </div>
    </div>
  </header>
  <main>
    <div class="controls">
      <input id="search" type="search" placeholder="Search topic, platform, language, status">
      <select id="platform"><option value="">All platforms</option></select>
      <select id="language"><option value="">All languages</option></select>
      <select id="status"><option value="">All statuses</option></select>
    </div>
    <div id="grid" class="grid"></div>
    <div id="empty" class="empty" hidden>No drafts match the current filters.</div>
  </main>
  <script id="manual-data" type="application/json">{data}</script>
  <script>
    const items = JSON.parse(document.getElementById('manual-data').textContent);
    const grid = document.getElementById('grid');
    const empty = document.getElementById('empty');
    const filters = {{
      search: document.getElementById('search'),
      platform: document.getElementById('platform'),
      language: document.getElementById('language'),
      status: document.getElementById('status'),
    }};

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

    function statusClass(status) {{
      return 'status-' + String(status || 'draft').replace(/[^a-z0-9]+/g, '-');
    }}

    function render() {{
      const query = filters.search.value.trim().toLowerCase();
      const platform = filters.platform.value;
      const language = filters.language.value;
      const status = filters.status.value;
      const visible = items.filter((item) => {{
        const haystack = [item.topic_id, item.platform_label, item.language, item.status, item.template_id, item.text].join(' ').toLowerCase();
        return (!query || haystack.includes(query))
          && (!platform || item.platform_label === platform)
          && (!language || item.language === language)
          && (!status || item.status === status);
      }});
      grid.textContent = '';
      empty.hidden = visible.length !== 0;
      visible.forEach((item) => grid.appendChild(card(item)));
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
      actions.append(copy, open);
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
      note.textContent = item.draft_path + ' / length ' + item.length;
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

    Object.values(filters).forEach((input) => input.addEventListener('input', render));
    render();
  </script>
</body>
</html>
"""


def build_manual_publish_site(
    social_manifest: Path = DEFAULT_SOCIAL_MANIFEST,
    syndication_manifest: Path = DEFAULT_SYNDICATION_MANIFEST,
    output: Path = DEFAULT_OUTPUT,
) -> Path:
    items = social_items(social_manifest) + syndication_items(syndication_manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_document(items), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local manual publishing dashboard")
    parser.add_argument("--social-manifest", type=Path, default=DEFAULT_SOCIAL_MANIFEST)
    parser.add_argument("--syndication-manifest", type=Path, default=DEFAULT_SYNDICATION_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = build_manual_publish_site(args.social_manifest, args.syndication_manifest, args.output)
    print(f"generated {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
