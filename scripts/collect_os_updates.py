#!/usr/bin/env python3
"""Detect changed official Android/iOS release-note pages for AI-Scout review."""
from __future__ import annotations
import hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    path=ROOT/"data/os_update_watchlist.json"; data=json.loads(path.read_text(encoding="utf-8")); now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for source in data.get("sources",[]):
        try:
            request=urllib.request.Request(source["url"],headers={"User-Agent":"ONNELLAB-OS-Scout/1.0"})
            with urllib.request.urlopen(request,timeout=30) as response: body=response.read()
            digest=hashlib.sha256(body).hexdigest(); changed=bool(source.get("content_hash") and source.get("content_hash")!=digest)
            source.update({"content_hash":digest,"checked_at":now,"status":"changed" if changed else "unchanged"})
        except OSError as error: source.update({"checked_at":now,"status":"failed","error":str(error)})
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"updated {path}"); return 0
if __name__=="__main__": raise SystemExit(main())
