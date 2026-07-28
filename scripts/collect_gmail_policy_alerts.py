#!/usr/bin/env python3
"""Detect explicitly mapped store-alert emails without retaining email content."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


def call(url: str, method: str = "GET", token: str = "", payload: bytes | None = None, content_type: str = "application/json") -> dict:
    headers = {"Accept": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    if payload is not None: headers["Content-Type"] = content_type
    try:
        with urlopen(Request(url, data=payload, headers=headers, method=method), timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Gmail policy alert collection failed: {error}") from error
    if not isinstance(data, dict): raise RuntimeError("Gmail response was not an object")
    return data


def access_token() -> str:
    required = {key: os.environ.get(key, "") for key in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")}
    if not all(required.values()): raise RuntimeError("Gmail OAuth credentials are incomplete")
    payload = urlencode({"client_id": required["GMAIL_CLIENT_ID"], "client_secret": required["GMAIL_CLIENT_SECRET"], "refresh_token": required["GMAIL_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    token = call("https://oauth2.googleapis.com/token", "POST", payload=payload, content_type="application/x-www-form-urlencoded").get("access_token")
    if not isinstance(token, str) or not token: raise RuntimeError("Gmail OAuth response had no access token")
    return token


def headers(message: dict) -> dict[str, str]:
    items = message.get("payload", {}).get("headers", []) if isinstance(message.get("payload"), dict) else []
    return {str(item.get("name", "")).lower(): str(item.get("value", "")) for item in items if isinstance(item, dict)}


def main() -> int:
    config = json.loads((ROOT / "data/gmail_policy_alert_config.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sync = {"checked_at": now, "state": "disabled", "imported": 0}
    if not config.get("enabled"):
        (ROOT / "data/gmail_policy_alert_sync_status.json").write_text(json.dumps(sync, indent=2) + "\n", encoding="utf-8")
        print("Gmail policy alert collection is disabled")
        return 0
    label, rules = str(config.get("label", "")), config.get("rules", [])
    if not label or not isinstance(rules, list) or not rules: raise RuntimeError("enabled Gmail collection requires a label and at least one mapping rule")
    token = access_token()
    listing = call(f"{GMAIL}/messages?" + urlencode({"q": f"label:{label}", "maxResults": "100"}), token=token)
    alerts_path = ROOT / "data/store_policy_alerts.json"
    payload = json.loads(alerts_path.read_text(encoding="utf-8"))
    alerts = {item.get("alert_id"): item for item in payload.get("alerts", [])}
    for item in listing.get("messages", []):
        if not isinstance(item, dict) or not item.get("id"): continue
        message = call(f"{GMAIL}/messages/{item['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date", token=token)
        meta = headers(message); sender, subject = meta.get("from", ""), meta.get("subject", "")
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict): continue
            if rule.get("sender") != sender or not re.search(str(rule.get("subject_pattern", "^$")), subject, re.IGNORECASE): continue
            store, slug, kind = rule.get("store"), rule.get("app_slug"), rule.get("kind")
            if store not in {"google_play", "app_store"} or kind not in {"warning", "rejection", "deadline", "metadata", "privacy", "billing", "other"} or not isinstance(slug, str) or not slug: continue
            fingerprint = hashlib.sha256(str(item["id"]).encode()).hexdigest()[:12]
            summary = f"Mapped mailbox policy alert detected (rule {index}; message {fingerprint}). Review the store console."
            alert_id = hashlib.sha256(f"gmail|{item['id']}|{index}".encode()).hexdigest()[:16]
            alerts.setdefault(alert_id, {"alert_id": alert_id, "store": store, "app_slug": slug, "kind": kind, "summary": summary, "reference_url": "", "occurred_at": now, "imported_at": now, "status": "new", "source": "gmail_mapped_alert"})
            sync["imported"] += 1
    alerts_path.write_text(json.dumps({"alerts": sorted(alerts.values(), key=lambda item: item["occurred_at"], reverse=True)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync["state"] = "collected"
    (ROOT / "data/gmail_policy_alert_sync_status.json").write_text(json.dumps(sync, indent=2) + "\n", encoding="utf-8")
    print(f"collected {sync['imported']} mapped Gmail policy alerts")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr); raise SystemExit(1)
