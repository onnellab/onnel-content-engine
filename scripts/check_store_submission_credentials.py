#!/usr/bin/env python3
"""Validate store-submission credential shape without contacting either store."""
from __future__ import annotations
import argparse, json, os, sys

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("provider",choices=("google_play","app_store")); args=parser.parse_args()
    if args.provider=="google_play":
        try: value=json.loads(os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON",""))
        except json.JSONDecodeError: raise SystemExit("Google Play service-account JSON is invalid")
        if not isinstance(value,dict) or value.get("type")!="service_account" or not value.get("client_email") or not value.get("private_key") or not value.get("project_id"): raise SystemExit("Google Play service-account fields are incomplete")
    else:
        key_id=os.environ.get("APP_STORE_CONNECT_KEY_ID",""); issuer=os.environ.get("APP_STORE_CONNECT_ISSUER_ID",""); private=os.environ.get("APP_STORE_CONNECT_PRIVATE_KEY","")
        if not key_id or not issuer or "BEGIN PRIVATE KEY" not in private or "END PRIVATE KEY" not in private: raise SystemExit("App Store Connect API key fields are incomplete")
    print(f"{args.provider} credential shape is valid; no store API request was made")
    return 0
if __name__=="__main__": raise SystemExit(main())
