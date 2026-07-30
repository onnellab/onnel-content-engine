#!/usr/bin/env python3
"""Collect configured Firebase Crashlytics issue metadata without stack traces."""
from __future__ import annotations
import csv, hashlib, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
FIELDS=["incident_id","app_slug","platform","app_version","os_version","title","affected_users","event_count","first_seen","last_seen","source","status"]
def main() -> int:
 config=json.loads((ROOT/"data/crashlytics_crash_sources.json").read_text(encoding="utf-8")); sources=config.get("apps",[]); coverage=config.get("coverage",[]); token=os.environ.get("FIREBASE_CRASHLYTICS_ACCESS_TOKEN",""); now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); state={"checked_at":now,"configured_apps":len(sources),"covered_apps":len(coverage),"state":"not_configured","imported":0}
 if not sources or not token:
  state["state"]="token_missing" if sources else "not_applicable" if coverage and all(item.get("state")=="not_applicable" for item in coverage) else "not_configured"; (ROOT/"data/crashlytics_sync_status.json").write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8"); print(state["state"]); return 0
 with (ROOT/"data/crash_incidents.csv").open(encoding="utf-8",newline="") as h: incidents={r["incident_id"]:r for r in csv.DictReader(h)}
 for source in sources:
  for key in ("app_slug","project","app_id","platform"):
   if not source.get(key): raise RuntimeError(f"Crashlytics source is missing {key}")
  url=f"https://firebasecrashlytics.googleapis.com/v1alpha/projects/{source['project']}/apps/{source['app_id']}/issues?pageSize=100"
  try:
   with urlopen(Request(url,headers={"Authorization":f"Bearer {token}","Accept":"application/json"}),timeout=30) as r: payload=json.loads(r.read().decode())
  except (HTTPError,URLError,TimeoutError,json.JSONDecodeError) as e: raise RuntimeError(f"Crashlytics request failed: {e}") from e
  for issue in payload.get("issues",[]):
   if not isinstance(issue,dict) or not issue.get("name"): continue
   iid=hashlib.sha256(f"crashlytics|{source['app_slug']}|{issue['name']}".encode()).hexdigest()[:16]; incidents[iid]={"incident_id":iid,"app_slug":source["app_slug"],"platform":source["platform"],"app_version":"","os_version":"","title":str(issue.get("title") or issue.get("issueType") or "Crashlytics issue"),"affected_users":str(issue.get("impactedUsersCount",0)),"event_count":str(issue.get("eventCount",0)),"first_seen":str(issue.get("firstSeen","")),"last_seen":str(issue.get("lastSeen","")),"source":"crashlytics","status":"new"}; state["imported"]+=1
 with (ROOT/"data/crash_incidents.csv").open("w",encoding="utf-8",newline="") as h: w=csv.DictWriter(h,fieldnames=FIELDS); w.writeheader(); w.writerows(incidents.values())
 state["state"]="collected"; (ROOT/"data/crashlytics_sync_status.json").write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8"); print(f"collected {state['imported']} Crashlytics issues"); return 0
if __name__=="__main__":
 try: raise SystemExit(main())
 except RuntimeError as e: print(e,file=sys.stderr); raise SystemExit(1)
