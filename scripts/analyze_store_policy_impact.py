#!/usr/bin/env python3
"""Create evidence-only review tasks for changed official store-policy pages."""
from __future__ import annotations
import csv,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 sources=json.loads((ROOT/"data/store_policy_watchlist.json").read_text(encoding="utf-8")).get("sources",[])
 existing=json.loads((ROOT/"data/store_policy_impact_tasks.json").read_text(encoding="utf-8")).get("tasks",[]) if (ROOT/"data/store_policy_impact_tasks.json").exists() else []
 existing_by_id={task.get("task_id"):task for task in existing}
 alerts=json.loads((ROOT/"data/store_policy_alerts.json").read_text(encoding="utf-8")).get("alerts",[])
 changed=[source for source in sources if source.get("status")=="changed"]
 with (ROOT/"data/apps_registry.csv").open(encoding="utf-8",newline="") as handle: apps=list(csv.DictReader(handle))
 tasks=[]
 for source in changed:
  platform="android" if source.get("store")=="google_play" else "ios"
  for app in apps:
   app_slug=app.get("app_slug") or app.get("slug")
   if not app_slug: continue
   if platform in app.get("platforms",""):
    task={"task_id":f"policy-{source['store']}-{app_slug}","app_slug":app_slug,"store":source["store"],"status":"review_required","evidence":{"url":source["url"],"content_hash":source.get("content_hash"),"checked_at":source.get("checked_at")},"scope":["store listing","permissions and privacy disclosures","billing and subscriptions","SDK policy implications"],"conclusion":"No violation inferred. Compare the changed official policy with app code and store metadata before action."}; task.update({key:value for key,value in existing_by_id.get(task["task_id"],{}).items() if key in {"status","approved_by","approved_at"}}); tasks.append(task)
 for alert in alerts:
  alert_status=alert.get("status", "new")
  if alert_status in {"resolved", "dismissed"}: continue
  task_id=f"policy-alert-{alert['alert_id']}"
  previous=existing_by_id.get(task_id,{})
  task_status=previous.get("status", "review_required") if alert_status == "new" else alert_status
  evidence={"alert_id":alert["alert_id"],"kind":alert["kind"],"summary":alert["summary"],"reference_url":alert.get("reference_url", ""),"occurred_at":alert["occurred_at"]}
  for key in ("operational_note", "status_updated_at"):
   if alert.get(key): evidence[key]=alert[key]
  task={"task_id":task_id,"app_slug":alert["app_slug"],"store":alert["store"],"status":task_status,"evidence":evidence,"scope":["stated store requirement only"],"conclusion":"Console alert recorded. Do not infer a remedy; verify the cited requirement and obtain human approval before any store submission, appeal, or release."}
  task.update({key:value for key,value in previous.items() if key in {"approved_by","approved_at"}}); tasks.append(task)
 path=ROOT/"data/store_policy_impact_tasks.json"; path.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"tasks":tasks},ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"generated {path}"); return 0
if __name__=="__main__": raise SystemExit(main())
