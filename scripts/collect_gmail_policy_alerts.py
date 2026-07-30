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
from email.utils import parseaddr
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"


def record_sync(account_alias: str, state: str, imported: int, checked_at: str) -> None:
    path = ROOT / "data/gmail_policy_alert_sync_status.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        payload = {}
    accounts = payload.get("accounts", {}) if isinstance(payload.get("accounts"), dict) else {}
    accounts[account_alias] = {"checked_at": checked_at, "state": state, "imported": imported}
    states = {item.get("state") for item in accounts.values() if isinstance(item, dict)}
    aggregate_state = "collected" if "collected" in states else "disabled" if states == {"disabled"} else "not_connected"
    result = {
        "checked_at": checked_at,
        "state": aggregate_state,
        "imported": sum(int(item.get("imported", 0)) for item in accounts.values() if isinstance(item, dict)),
        "accounts": accounts,
    }
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


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
    account_alias = os.environ.get("GMAIL_ACCOUNT_ALIAS", "default").strip() or "default"
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", account_alias):
        raise RuntimeError("GMAIL_ACCOUNT_ALIAS must be a short non-sensitive alias")
    imported = 0
    if not config.get("enabled"):
        record_sync(account_alias, "disabled", imported, now)
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
        message = call(f"{GMAIL}/messages/{item['id']}?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date&metadataHeaders=Message-ID", token=token)
        meta = headers(message); sender, subject = meta.get("from", ""), meta.get("subject", "")
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict): continue
            sender_address = parseaddr(sender)[1].lower()
            if str(rule.get("sender", "")).lower() != sender_address or not re.search(str(rule.get("subject_pattern", "^$")), subject, re.IGNORECASE): continue
            store, kind = rule.get("store"), rule.get("kind")
            slugs = rule.get("app_slugs")
            if not isinstance(slugs, list): slugs = [rule.get("app_slug")]
            slugs = [slug for slug in slugs if isinstance(slug, str) and slug]
            if store not in {"google_play", "app_store"} or kind not in {"warning", "rejection", "deadline", "metadata", "privacy", "billing", "other"} or not slugs: continue
            message_identity = meta.get("message-id", "").strip() or f"{account_alias}|{item['id']}"
            fingerprint = hashlib.sha256(message_identity.encode()).hexdigest()[:12]
            summary = f"Mapped mailbox policy alert detected (rule {index}; message {fingerprint}). Review the store console."
            event_key = str(rule.get("event_key", "")).strip()
            for slug in slugs:
                existing = next((alert for alert in alerts.values() if event_key and alert.get("event_key") == event_key and alert.get("app_slug") == slug), None)
                identity = event_key or message_identity
                alert_id = hashlib.sha256(f"gmail|{identity}|{slug}|{index}".encode()).hexdigest()[:16]
                target = existing or alerts.get(alert_id)
                if target is None:
                    target = {"alert_id": alert_id, "store": store, "app_slug": slug, "kind": kind, "summary": summary, "reference_url": "", "occurred_at": now, "imported_at": now, "status": "new", "source": "gmail_mapped_alert", "source_accounts": [account_alias]}
                    if event_key: target["event_key"] = event_key
                    alerts[alert_id] = target
                    imported += 1
                else:
                    source_accounts = target.setdefault("source_accounts", [])
                    if account_alias not in source_accounts: source_accounts.append(account_alias)
    alerts_path.write_text(json.dumps({"alerts": sorted(alerts.values(), key=lambda item: item["occurred_at"], reverse=True)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    record_sync(account_alias, "collected", imported, now)
    print(f"collected {imported} mapped Gmail policy alerts for {account_alias}")
    return 0


if __name__ == "__main__":
    try: raise SystemExit(main())
    except RuntimeError as error:
        print(error, file=sys.stderr); raise SystemExit(1)
