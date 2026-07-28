#!/usr/bin/env python3
"""Send only the Manager report summary to an explicitly enabled HTTPS webhook."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
 config=json.loads((ROOT/"data/ai_manager_webhook_config.json").read_text(encoding="utf-8"))
 if not config.get("enabled"): print("AI Manager webhook is disabled"); return 0
 url=os.environ.get("OPS_MANAGER_WEBHOOK_URL","")
 if not url.startswith("https://"): raise SystemExit("OPS_MANAGER_WEBHOOK_URL must be an HTTPS URL when webhook is enabled")
 report=json.loads((ROOT/"data/ai_manager_daily_report.json").read_text(encoding="utf-8")); summary=report.get("summary",{})
 text="AI Manager daily report\n"+f"Generated: {report.get('generated_at','')}\n"+"\n".join(f"• {key.replace('_',' ')}: {value}" for key,value in summary.items())
 fmt=config.get("format")
 if fmt=="slack": payload={"text":text}
 elif fmt=="discord": payload={"content":text}
 elif fmt=="generic": payload={"report":report}
 else: raise SystemExit("webhook format must be slack, discord, or generic")
 try:
  with urlopen(Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","User-Agent":"ONNELLAB-AI-Manager"},method="POST"),timeout=20) as response:
   if response.status < 200 or response.status >= 300: raise RuntimeError(f"unexpected webhook status: {response.status}")
 except (HTTPError,URLError,TimeoutError,RuntimeError) as error: print(f"Manager webhook failed: {error}",file=sys.stderr); return 1
 print("sent AI Manager webhook summary"); return 0
if __name__=="__main__": raise SystemExit(main())
