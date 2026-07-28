#!/usr/bin/env python3
"""Map verified OS-release-note changes to affected app review tasks."""
from __future__ import annotations
import csv, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    sources=json.loads((ROOT/"data/os_update_watchlist.json").read_text(encoding="utf-8")).get("sources",[])
    changed=[source for source in sources if source.get("status")=="changed"]
    with (ROOT/"data/apps_registry.csv").open(encoding="utf-8",newline="") as handle: apps=list(csv.DictReader(handle))
    tasks=[]
    for source in changed:
        platform=source.get("platform","")
        for app in apps:
            if platform in app.get("platforms",""):
                tasks.append({"task_id":f"os-{platform}-{app['app_slug']}","app_slug":app["app_slug"],"platform":platform,"status":"review_required","evidence":{"url":source.get("url"),"content_hash":source.get("content_hash"),"checked_at":source.get("checked_at")},"scope":["OS/API deprecation","permission and file-provider behavior","plugin compatibility","foreground/background lifecycle"],"conclusion":"No compatibility claim made; inspect the official changed release note and app code before action."})
    output={"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"tasks":tasks}
    path=ROOT/"data/os_update_impact_tasks.json"; path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"generated {path}"); return 0
if __name__=="__main__": raise SystemExit(main())
