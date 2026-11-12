#!/usr/bin/env python3
"""Guarded, independent three-times-weekly Blogger ledger (no account secrets).

An agent authors an original English HTML article and JSON brief. This tool
checks distinctness and quality, reserves one KST date slot before remote work, and
verifies actual public posts before marking them published. It never posts to
Blogger itself, and it never touches canonical ONNELLAB publishing manifests.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DRAFT_ROOT = ROOT / "drafts" / "blogger"
LEDGER = ROOT / "data" / "blogger_publications.json"
BLOG_ID = "1829676614817439337"
BLOG_HOST = "onnellab-guides.blogspot.com"
MAX_PER_WEEK = 3
ALLOWED_TAGS = {
    "h2", "h3", "h4", "p", "br", "hr", "strong", "em", "b", "i",
    "ul", "ol", "li", "a", "blockquote", "pre", "code", "img", "figure",
    "figcaption", "table", "thead", "tbody", "tr", "th", "td", "sup", "sub",
}
REQUIRED_REVIEWS = (
    "technically_verified", "distinct_search_intent", "original_examples",
    "sources_checked", "links_checked", "rights_checked", "english_proofread",
)


class BloggerGuardError(ValueError):
    pass


def refuse(message: str):
    raise BloggerGuardError(message)


def secure_url(value: str, *, host: str | None = None) -> bool:
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        p = urlsplit(value)
        return (
            p.scheme == "https" and bool(p.hostname) and not p.username
            and not p.password and p.port is None and not p.fragment
            and (host is None or p.hostname == host)
        )
    except ValueError:
        return False


def week_key(day: datetime | None = None) -> str:
    day = day or datetime.now(ZoneInfo("Asia/Seoul"))
    day = day.astimezone(ZoneInfo("Asia/Seoul"))
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def slot_key(day: datetime | None = None) -> str:
    """Date of a scheduled publishing slot in the Blogger owner's KST time zone."""
    day = day or datetime.now(ZoneInfo("Asia/Seoul"))
    return day.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()


def ensure_slot(slot: str, week: str) -> None:
    if not isinstance(slot, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", slot):
        refuse("Blogger slot must be a KST YYYY-MM-DD date")
    try:
        value = date.fromisoformat(slot)
    except ValueError:
        refuse("Blogger slot is not a real calendar date")
    iso_year, iso_week, _ = value.isocalendar()
    if f"{iso_year}-W{iso_week:02d}" != week:
        refuse("Blogger slot and ISO week do not match")


def relative_path(root: Path, value: str, prefix: Path) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        refuse("invalid file path")
    path = (root / value).resolve()
    if not path.is_relative_to((root / prefix).resolve()) or not path.is_file():
        refuse("file is missing or outside its allowed directory")
    if path.is_symlink():
        refuse("symlink inputs are not allowed")
    return path


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.h2: list[str] = []
        self._heading: list[str] | None = None
        self.links: list[str] = []
        self.list_count = 0
        self.p_count = 0

    def handle_starttag(self, tag, attrs):
        self._tag(tag, attrs)
        if tag == "h2":
            self._heading = []
        if tag in {"ol", "ul"}:
            self.list_count += 1
        if tag == "p":
            self.p_count += 1

    def handle_startendtag(self, tag, attrs):
        self._tag(tag, attrs)

    def _tag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            refuse(f"unsupported or unsafe article HTML tag: {tag}")
        attributes = dict(attrs)
        if len(attrs) != len(attributes):
            refuse("duplicated HTML attributes")
        for name, value in attrs:
            if name.lower().startswith("on") or name not in {"href", "src", "alt", "title"}:
                refuse(f"unsupported article HTML attribute: {name}")
            if name in {"href", "src"} and (not secure_url(value) or urlsplit(value).scheme != "https"):
                refuse("only absolute HTTPS links and images are allowed")
        if tag == "a":
            url = attributes.get("href", "")
            if not secure_url(url):
                refuse("anchor must contain HTTPS href")
            self.links.append(url)
        if tag == "img":
            if not secure_url(attributes.get("src", "")) or not attributes.get("alt", "").strip():
                refuse("images must have HTTPS source and nonempty alt text")
        if tag not in {"a", "img"} and any(x in attributes for x in ("href", "src")):
            refuse("invalid link or image attribute")

    def handle_data(self, data):
        self.parts.append(data)
        if self._heading is not None:
            self._heading.append(data)

    def handle_endtag(self, tag):
        if tag not in ALLOWED_TAGS:
            refuse(f"unsupported or unsafe article HTML close tag: {tag}")
        if tag == "h2" and self._heading is not None:
            self.h2.append(" ".join(self._heading).strip())
            self._heading = None

    @property
    def words(self) -> list[str]:
        return re.findall(r"[A-Za-z][A-Za-z0-9'’-]*", " ".join(self.parts))


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def validate(brief_path: Path, *, root: Path = ROOT) -> dict:
    brief_path = brief_path.resolve()
    if not brief_path.is_relative_to((root / "drafts" / "blogger").resolve()) or brief_path.suffix != ".json":
        refuse("brief must be a JSON file inside drafts/blogger")
    try:
        meta = json.loads(brief_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BloggerGuardError("invalid Blogger brief JSON") from exc
    if not isinstance(meta, dict):
        refuse("brief must be a JSON object")
    slug = meta.get("slug")
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 90:
        refuse("invalid Blogger article slug")
    if meta.get("language") != "en" or meta.get("week") != week_key():
        refuse("Blogger brief must be English and for the current KST publication week")
    slot = meta.get("slot", slot_key())
    ensure_slot(slot, meta["week"])
    title = meta.get("title")
    question = meta.get("primary_question")
    source_title = meta.get("source_title")
    if not all(isinstance(x, str) and len(x.strip()) >= 15 for x in (title, question, source_title)):
        refuse("title, primary_question, and source_title are required")
    if SequenceMatcher(None, title.lower(), source_title.lower()).ratio() >= 0.78:
        refuse("Blogger angle is too close to canonical article title")
    source_url = meta.get("source_url")
    if not secure_url(source_url, host="onnellab.com"):
        refuse("canonical source must use https://onnellab.com")
    source_path = relative_path(root, meta.get("source_path"), Path("generated/markdown/en"))
    body_path = relative_path(root, meta.get("body_path"), Path("drafts/blogger"))
    if body_path.suffix != ".html" or body_path.name != f"{slug}.html":
        refuse("body path must match the slug and use .html")
    content = body_path.read_text(encoding="utf-8")
    if len(content.encode("utf-8")) > 120_000:
        refuse("oversized Blogger article body")
    if "<!--" in content or "<!doctype" in content.lower() or "<!entity" in content.lower():
        refuse("HTML comments and document markup are not allowed")
    parser = ArticleParser()
    parser.feed(content)
    if len(parser.words) < 650 or len(parser.h2) < 3 or parser.list_count < 1 or parser.p_count < 6:
        refuse("Blogger article must provide substantive English guidance, sections, and steps")
    if source_url not in parser.links:
        refuse("the Blogger guide must transparently link its ONNELLAB source")
    references = meta.get("fact_sources")
    if not isinstance(references, list) or len(references) < 2 or len({r.get("url") for r in references if isinstance(r, dict)}) < 2:
        refuse("at least two distinct research sources are required")
    for ref in references:
        if not isinstance(ref, dict) or not secure_url(ref.get("url")) or not isinstance(ref.get("supports"), str) or len(ref["supports"].strip()) < 20:
            refuse("fact sources need genuine HTTPS URLs and concrete supporting notes")
        if ref["url"] not in parser.links:
            refuse("the article must link its documented factual references")
    if not isinstance(meta.get("new_examples"), list) or len(meta["new_examples"]) < 2 or any(not isinstance(x, str) or len(x) < 20 for x in meta["new_examples"]):
        refuse("two independently useful examples are required")
    review = meta.get("review")
    if not isinstance(review, dict) or any(review.get(field) is not True for field in REQUIRED_REVIEWS):
        refuse("all independent editorial reviews must be verified true")
    source_text = source_path.read_text(encoding="utf-8")
    source_tokens = _normalized_words(source_text)
    guide_tokens = _normalized_words(" ".join(parser.parts))
    if len(source_tokens) >= 28:
        source_runs = {tuple(source_tokens[i:i+28]) for i in range(len(source_tokens) - 27)}
        if any(tuple(guide_tokens[i:i+28]) in source_runs for i in range(max(0, len(guide_tokens) - 27))):
            refuse("Blogger article copies a long exact passage from the ONNELLAB source")
    return {
        "slug": slug, "week": meta["week"], "slot": slot, "title": title, "question": question,
        "source_url": source_url, "body_path": meta["body_path"],
        "sha256": sha256(content.encode("utf-8")).hexdigest(),
        "word_count": len(parser.words), "sections": parser.h2,
        "references": len(references),
    }


def read_ledger(path: Path = LEDGER) -> dict:
    if not path.exists():
        return {"schema_version": 1, "blog_id": BLOG_ID, "entries": []}
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BloggerGuardError("invalid Blogger ledger") from exc
    if (not isinstance(ledger, dict) or ledger.get("schema_version") != 1
            or ledger.get("blog_id") != BLOG_ID or not isinstance(ledger.get("entries"), list)):
        refuse("Blogger ledger has invalid schema or target Blog ID")
    slots, slugs, post_ids, week_counts = set(), set(), set(), {}
    for e in ledger["entries"]:
        if not isinstance(e, dict) or e.get("status") not in {"reserved", "draft", "published"}:
            refuse("invalid Blogger ledger entry")
        week = e.get("week")
        slug = e.get("slug")
        if not isinstance(week, str) or not re.fullmatch(r"\d{4}-W\d{2}", week):
            refuse("invalid Blogger ledger ISO week")
        if not isinstance(slug, str) or not slug or slug in slugs:
            refuse("duplicate Blogger article slug in ledger")
        slugs.add(slug)
        # Historical weekly-only reservations remain visible but must be reconciled
        # before adding another article to that week; never guess their date.
        slot = e.get("slot")
        if slot is not None:
            ensure_slot(slot, week)
        key = (week, slot)
        if key in slots:
            refuse("duplicate Blogger publication date slot in ledger")
        slots.add(key)
        week_counts[week] = week_counts.get(week, 0) + 1
        if week_counts[week] > MAX_PER_WEEK:
            refuse("Blogger publication week exceeds three reserved articles")
        pid = e.get("post_id")
        if pid:
            if pid in post_ids: refuse("duplicate Blogger remote post ID")
            post_ids.add(pid)
    return ledger


def save_ledger(ledger: dict, path: Path = LEDGER):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".new")
    try:
        tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def reserve(info: dict, path: Path = LEDGER):
    ensure_slot(info["slot"], info["week"])
    ledger = read_ledger(path)
    week_count = 0
    for e in ledger["entries"]:
        if e["slug"] == info["slug"] and (e["week"], e.get("slot"), e["sha256"]) == (info["week"], info["slot"], info["sha256"]):
            return e, False
        if e["slug"] == info["slug"]:
            refuse("Blogger article slug is already used")
        if e["week"] == info["week"]:
            week_count += 1
            if e.get("slot") is None:
                refuse("legacy weekly reservation needs reconciliation before adding a new slot")
            if e["slot"] == info["slot"]:
                refuse("another Blogger article is already reserved or posted for this KST date")
    if week_count >= MAX_PER_WEEK:
        refuse("Blogger has already reserved three articles for this KST week")
    entry = {k: info[k] for k in ("slug", "week", "slot", "title", "source_url", "body_path", "sha256")}
    entry.update(status="reserved", post_id="", posted_url="", created_at=now_utc(), verified_at="")
    ledger["entries"].append(entry)
    save_ledger(ledger, path)
    return entry, True


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_draft(info: dict, post_id: str, path: Path = LEDGER):
    if not re.fullmatch(r"[0-9]{10,25}", post_id):
        refuse("Blogger post ID must be numeric")
    ledger = read_ledger(path)
    row = next((e for e in ledger["entries"] if e["week"] == info["week"] and e.get("slot") == info["slot"] and e["slug"] == info["slug"] and e["sha256"] == info["sha256"]), None)
    if row is None: refuse("reserve and commit the week before creating a Blogger draft")
    if row["status"] == "published": refuse("this week is already published")
    if row.get("post_id") not in {"", post_id}: refuse("conflicting remote Blogger draft ID")
    row.update(status="draft", post_id=post_id)
    save_ledger(ledger, path)
    return row


def verify_public_post(info: dict, posted_url: str, *, fetch=None) -> bool:
    if not secure_url(posted_url, host=BLOG_HOST) or not re.fullmatch(r"/20[0-9]{2}/[0-1][0-9]/[a-z0-9-]+\.html", urlsplit(posted_url).path):
        refuse("invalid Blogger article permalink")
    if fetch is None:
        def fetch(url):
            request = Request(url, headers={"User-Agent": "ONNELLAB-Blogger-verifier/1.0"})
            with urlopen(request, timeout=18) as res:
                if res.status != 200 or res.geturl().split("?")[0] != url:
                    refuse("Blogger permalink did not resolve to exact public page")
                return res.read(1_200_000).decode("utf-8", errors="replace")
    raw = fetch(posted_url)
    if not isinstance(raw, str) or len(raw) < 250:
        refuse("Blogger public HTML is missing")
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).lower()
    if re.sub(r"\s+", " ", info["title"]).lower() not in text:
        refuse("Blogger public page does not contain expected title")
    matches = sum(1 for heading in info["sections"] if re.sub(r"\s+", " ", heading).lower() in text)
    if matches < min(2, len(info["sections"])):
        refuse("Blogger public page does not contain expected article sections")
    return True


def record_published(info: dict, post_id: str, posted_url: str, path: Path = LEDGER, *, fetch=None):
    ledger = read_ledger(path)
    row = next((e for e in ledger["entries"] if e["week"] == info["week"] and e.get("slot") == info["slot"] and e["slug"] == info["slug"] and e["sha256"] == info["sha256"]), None)
    if row is None or row.get("status") != "draft" or row.get("post_id") != post_id:
        refuse("Blogger draft must first be recorded with matching post ID")
    verify_public_post(info, posted_url, fetch=fetch)
    row.update(status="published", posted_url=posted_url, verified_at=now_utc())
    save_ledger(ledger, path)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "reserve", "record-draft", "record-published", "status"))
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--post-id")
    parser.add_argument("--url")
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    args = parser.parse_args()
    try:
        if args.action == "status":
            result = read_ledger(args.ledger)
        else:
            if args.brief is None: refuse("--brief is required")
            info = validate(args.brief)
            if args.action == "check":
                ledger = read_ledger(args.ledger)
                current = next((e for e in ledger["entries"] if e["week"] == info["week"] and e.get("slot") == info["slot"]), None)
                count = sum(e["week"] == info["week"] for e in ledger["entries"])
                has_legacy = any(e["week"] == info["week"] and e.get("slot") is None for e in ledger["entries"])
                result = {"quality": info, "slot_status": current or ("blocked" if count >= MAX_PER_WEEK or has_legacy else "available"), "week_count": count, "week_limit": MAX_PER_WEEK}
            elif args.action == "reserve":
                row, new = reserve(info, args.ledger)
                result = {"new_reservation": new, "entry": row}
            elif args.action == "record-draft":
                if not args.post_id: refuse("--post-id is required")
                result = record_draft(info, args.post_id, args.ledger)
            else:
                if not args.post_id or not args.url: refuse("--post-id and --url are required")
                result = record_published(info, args.post_id, args.url, args.ledger)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BloggerGuardError, OSError, UnicodeError) as exc:
        print(f"blogger guard refused: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
