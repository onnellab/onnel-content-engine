#!/usr/bin/env python3
"""Detect changes on official store-policy pages; never infer compliance."""
from __future__ import annotations
import hashlib,json,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 path=ROOT/"data/store_policy_watchlist.json"; data=json.loads(path.read_text(encoding="utf-8")); now=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
 for source in data.get("sources",[]):
  try:
   req=urllib.request.Request(source["url"],headers={"User-Agent":"ONNELLAB-Store-Policy-Scout/1.0"})
   with urllib.request.urlopen(req,timeout=30) as response: digest=hashlib.sha256(response.read()).hexdigest()
   changed=bool(source.get("content_hash") and source.get("content_hash")!=digest); source.update({"content_hash":digest,"checked_at":now,"status":"changed" if changed else "unchanged"})
  except OSError as error: source.update({"checked_at":now,"status":"failed","error":str(error)})
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"updated {path}"); return 0
if __name__=="__main__": raise SystemExit(main())
