#!/usr/bin/env python3
"""Render bounded public card fixtures only; no queue, network or publishing writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publishing
from topic_management import read_csv, TOPIC_HEADER

def main():
    before = {p: p.read_bytes() for p in (ROOT / "data" / "topics.csv",)}
    output = ROOT / "card-regression-evidence"
    output.mkdir(exist_ok=False)
    original = ROOT / ".comparison-old" / "scripts" / "publishing.py"
    spec = importlib.util.spec_from_file_location("baseline_card_publishing", original)
    baseline = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = baseline
    spec.loader.exec_module(baseline)
    rows = [r for r in read_csv(ROOT / "data/topics.csv", TOPIC_HEADER)
            if r["slug"] == "separate-source-notes-from-conclusions"]
    expected = {"en", "ko", "ja", "zh-Hans", "zh-Hant", "pt-BR", "de", "fr", "es"}
    if len(rows) != 9 or {r["primary_language"] for r in rows} != expected:
        raise ValueError("Expected exact nine-language public-source fixture")
    results = []
    for row in rows:
        path = ROOT / row["canonical_path"]
        meta, _ = publishing.parse_front_matter(path.read_text(encoding="utf-8"))
        article = publishing.Article(row, path, output/"unused.html", "/unused/", meta["title"], "",
                                     meta["description"], "/unused.png", "https://onnellab.com/unused.png")
        record = {"locale": row["primary_language"], "topic_id": row["id"]}
        current = publishing.social_card_svg(article)
        ns = {"s": "http://www.w3.org/2000/svg"}
        parsed = ET.fromstring(current)
        for selector, expected_text in (("s:text[@font-weight='760']", article.title),
                                        ("s:text[@fill='#5f5b54']", article.description)):
            actual_text = " ".join(n.text or "" for n in parsed.find(selector, ns).findall("s:tspan", ns))
            if actual_text != " ".join(expected_text.split()):
                raise AssertionError("Rendered card text incomplete: " + row["primary_language"])
        try:
            previous = baseline.social_card_svg(article)
        except baseline.PublishingError:
            previous = None
            record["baseline"] = "overflow_refused"
        else:
            if previous != current and row["primary_language"] != "en":
                raise AssertionError("Passing SVG unexpectedly changed: " + row["primary_language"])
            record["baseline"] = "english_full_text_repaired" if row["primary_language"] == "en" else "exact_svg_preserved"
        for label, content in (("after", current), ("before", previous)):
            if content is None:
                continue
            svg = output / (row["primary_language"] + "-" + label + ".svg")
            png = svg.with_suffix(".png")
            svg.write_text(content, encoding="utf-8")
            subprocess.run(publishing.rsvg_convert_command() + ["-w", "1200", "-h", "630", str(svg), "-o", str(png)], check=True)
            blob = png.read_bytes()
            if blob[:8] != b"\x89PNG\r\n\x1a\n" or int.from_bytes(blob[16:20], "big") != 1200 or int.from_bytes(blob[20:24], "big") != 630:
                raise AssertionError("Invalid rendered PNG")
            record[label + "_svg_sha256"] = hashlib.sha256(content.encode()).hexdigest()
            record[label + "_png_sha256"] = hashlib.sha256(blob).hexdigest()
        results.append(record)
    if any(p.read_bytes() != value for p, value in before.items()):
        raise AssertionError("Queue bytes changed")
    (output / "results.json").write_text(json.dumps({"baseline_commit": "c44880130edd0a0a5d07afec1a2565df120b2964", "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results))
if __name__ == "__main__":
    main()
