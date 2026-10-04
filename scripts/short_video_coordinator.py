"""Shared slot coordination for cooperating Shorts workers; CLI is read-only.

GitHub Contents SHA comparison serializes claims on a dedicated state branch.
This cannot fence an old worker that does not use this ledger. Operators must
first confirm legacy-writer fencing; a configuration flag is not proof of it.
No stale claim expires automatically. Unknown upload outcomes require provider
reconciliation, never another insert. Provider observation belongs to the caller.
"""
from __future__ import annotations

import argparse
import base64
import copy
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import parse_qs, quote, urlsplit

from video_product_eligibility import public_video_platforms

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data/video_rotation.json"
KST = timezone(timedelta(hours=9), "Asia/Seoul")
STATUSES = {"claimed", "uploading", "reconcile_required", "completed"}


class CoordinationError(ValueError):
    pass


class CASConflict(CoordinationError):
    pass


def aware(value):
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise CoordinationError("invalid_timestamp") from None


def validate_config(config):
    if config.get("schema_version") != 1:
        raise CoordinationError("invalid_coordinator_config")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config.get("repository", "")):
        raise CoordinationError("invalid_ledger_repository")
    if not re.fullmatch(r"shorts-coordination-[A-Za-z0-9_-]+", config.get("branch", "")):
        raise CoordinationError("dedicated_state_branch_required")
    if not re.fullmatch(r"shorts/[A-Za-z0-9_-]+\.json", config.get("path", "")):
        raise CoordinationError("invalid_ledger_path")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", config.get("owner_id", "")):
        raise CoordinationError("invalid_owner_id")


def config_blockers(config):
    validate_config(config)
    blockers = []
    if config.get("enabled") is not True:
        blockers.append("coordinator_disabled")
    fence = config.get("legacy_writer_fencing", {})
    if not isinstance(fence, dict) or fence.get("confirmed") is not True or not str(fence.get("evidence", "")).strip():
        blockers.append("legacy_writer_not_fenced")
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", config.get("channel_id", "")):
        blockers.append("expected_channel_not_configured")
    return blockers


def next_slot(now):
    if now.tzinfo is None:
        raise CoordinationError("timezone_aware_clock_required")
    local = now.astimezone(KST)
    for offset in range(7):
        candidate = (local + timedelta(days=offset)).replace(hour=9, minute=0, second=0, microsecond=0)
        if candidate.weekday() in {0, 2, 4}:
            return candidate.isoformat()
    raise CoordinationError("schedule_error")


def slot_key(channel, slot):
    moment = aware(slot)
    if moment.isoformat() != slot or moment.utcoffset() != timedelta(hours=9) or moment.weekday() not in {0, 2, 4} or (moment.hour, moment.minute, moment.second, moment.microsecond) != (9, 0, 0, 0):
        raise CoordinationError("invalid_mwf_kst_slot")
    return f"{channel}::{slot}"


def validate_receipt(receipt, channel):
    if not isinstance(receipt, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", receipt.get("video_id", "")):
        raise CoordinationError("invalid_video_receipt")
    parsed = urlsplit(receipt.get("posted_url", ""))
    video = receipt["video_id"]
    host = (parsed.hostname or "").removeprefix("www.")
    valid_url = parsed.scheme == "https" and parsed.port in {None, 443} and not parsed.username and not parsed.password and (
        (host == "youtube.com" and (parsed.path == f"/shorts/{video}" or (parsed.path == "/watch" and parse_qs(parsed.query).get("v") == [video])))
        or (host == "youtu.be" and parsed.path == f"/{video}"))
    if not valid_url or receipt.get("channel_id") != channel:
        raise CoordinationError("receipt_identity_mismatch")
    if (receipt.get("privacy_status"), receipt.get("upload_status"), receipt.get("processing_status")) != ("public", "processed", "succeeded"):
        raise CoordinationError("public_provider_confirmation_required")
    aware(receipt.get("verified_at"))
    aware(receipt.get("published_at"))


def validate_ledger(ledger):
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("slots"), dict):
        raise CoordinationError("invalid_shared_ledger")
    for key, row in ledger["slots"].items():
        if not isinstance(row, dict) or row.get("status") not in STATUSES:
            raise CoordinationError("invalid_shared_slot")
        if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", row.get("channel_id", "")) or key != slot_key(row["channel_id"], row.get("slot")):
            raise CoordinationError("invalid_shared_slot_identity")
        if not re.fullmatch(r"[0-9a-f]{64}", row.get("payload_sha256", "")) or not re.fullmatch(r"[0-9a-f]{32}", row.get("claim_token", "")) or not row.get("owner_id") or not re.fullmatch(r"APP-\d{4}", row.get("app_id", "")) or not row.get("scenario_id"):
            raise CoordinationError("invalid_shared_slot_payload")
        aware(row.get("claimed_at"))
        aware(row.get("updated_at"))
        if row["status"] == "completed":
            validate_receipt(row.get("receipt"), row["channel_id"])
    return ledger


class GitHubLedger:
    """Uses existing gh authentication; never changes credentials or provisions a branch."""
    def __init__(self, config, run=subprocess.run):
        validate_config(config)
        self.config, self.run = config, run
        self.endpoint = f"repos/{config['repository']}/contents/{config['path']}"

    def request(self, args, body=None):
        result = self.run(["gh", "api", *args], input=json.dumps(body) if body is not None else None,
                          capture_output=True, text=True, encoding="utf-8", timeout=45)
        if result.returncode:
            if "HTTP 409" in result.stderr:
                raise CASConflict("shared_ledger_changed")
            if "HTTP 404" in result.stderr:
                raise CoordinationError("shared_ledger_not_provisioned")
            raise CoordinationError("shared_ledger_request_failed")  # Never echo auth-bearing output.
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise CoordinationError("invalid_ledger_response") from None

    def read(self):
        response = self.request([self.endpoint + "?ref=" + quote(self.config["branch"], safe="")])
        try:
            ledger = json.loads(base64.b64decode(response["content"]))
            sha = response["sha"]
            if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise CoordinationError("invalid_ledger_response") from None
        return validate_ledger(ledger), sha

    def compare_and_swap(self, expected, ledger):
        if not re.fullmatch(r"[0-9a-f]{40,64}", expected):
            raise CoordinationError("existing_ledger_sha_required")
        validate_ledger(ledger)
        self.request(["--method", "PUT", self.endpoint, "--input", "-"], {
            "message": "Coordinate approved Shorts slot", "branch": self.config["branch"], "sha": expected,
            "content": base64.b64encode((json.dumps(ledger, sort_keys=True, indent=2) + "\n").encode()).decode()})


class Coordinator:
    def __init__(self, store, config, *, clock=lambda: datetime.now(timezone.utc), claim_token=None):
        validate_config(config)
        self.store, self.config, self.clock = store, copy.deepcopy(config), clock
        # Persist this in the owning local state before claiming. A new process
        # may resume only with that local token, never one copied from the ledger.
        self.claim_token = claim_token or uuid.uuid4().hex
        if not re.fullmatch(r"[0-9a-f]{32}", self.claim_token):
            raise CoordinationError("invalid_claim_token")

    def mutate(self, operation):
        blockers = config_blockers(self.config)
        if blockers:
            raise CoordinationError(",".join(blockers))
        for _ in range(3):
            state, sha = self.store.read()
            validate_ledger(state)
            updated = copy.deepcopy(state)
            result = operation(updated)
            if updated == state:
                return result
            try:
                self.store.compare_and_swap(sha, updated)
                return result
            except CASConflict:
                continue
        raise CoordinationError("shared_ledger_contention")

    def claim(self, slot, app, payload_sha256):
        key = slot_key(self.config["channel_id"], slot)
        if next_slot(self.clock()) != slot or aware(slot) > self.clock():
            raise CoordinationError("slot_not_due")
        if not re.fullmatch(r"[0-9a-f]{64}", payload_sha256) or not re.fullmatch(r"APP-\d{4}", app.get("app_id", "")) or not app.get("scenario_id"):
            raise CoordinationError("invalid_claim_payload")

        def operation(state):
            previous = state["slots"].get(key)
            if previous:
                if previous["owner_id"] != self.config["owner_id"] or previous["claim_token"] != self.claim_token:
                    raise CoordinationError("slot_owned")
                if (previous["app_id"], previous["scenario_id"], previous["payload_sha256"]) != (app["app_id"], app["scenario_id"], payload_sha256):
                    raise CoordinationError("immutable_payload")
                if previous["status"] != "claimed":
                    raise CoordinationError("already_completed" if previous["status"] == "completed" else "reconcile_required")
                return copy.deepcopy(previous)
            if any(r["channel_id"] == self.config["channel_id"] and r["status"] != "completed" for r in state["slots"].values()):
                raise CoordinationError("channel_has_unresolved_slot")
            stamp = self.clock().isoformat()
            record = {"slot": slot, "channel_id": self.config["channel_id"], "owner_id": self.config["owner_id"], "claim_token": self.claim_token,
                      "app_id": app["app_id"], "scenario_id": app["scenario_id"], "payload_sha256": payload_sha256,
                      "status": "claimed", "claimed_at": stamp, "updated_at": stamp}
            state["slots"][key] = record
            return copy.deepcopy(record)
        return self.mutate(operation)

    def transition(self, slot, payload_sha256, status, receipt=None):
        key = slot_key(self.config["channel_id"], slot)
        if receipt is not None:
            validate_receipt(receipt, self.config["channel_id"])

        def operation(state):
            row = state["slots"].get(key)
            if not row or row["owner_id"] != self.config["owner_id"] or row["claim_token"] != self.claim_token:
                raise CoordinationError("slot_owned_or_missing")
            if row["payload_sha256"] != payload_sha256:
                raise CoordinationError("immutable_payload")
            if row["status"] == "completed":
                if status == "completed" and row.get("receipt") == receipt:
                    return copy.deepcopy(row)
                raise CoordinationError("receipt_conflict")
            allowed = {"uploading": {"claimed"}, "reconcile_required": {"uploading", "reconcile_required"}, "completed": {"uploading", "reconcile_required"}}
            if row["status"] not in allowed.get(status, set()):
                raise CoordinationError("invalid_slot_transition")
            row.update(status=status, updated_at=self.clock().isoformat())
            if receipt is not None:
                row["receipt"] = copy.deepcopy(receipt)
            return copy.deepcopy(row)
        return self.mutate(operation)

    def mark_upload_started(self, slot, payload_sha256):
        return self.transition(slot, payload_sha256, "uploading")

    def mark_reconcile_required(self, slot, payload_sha256):
        return self.transition(slot, payload_sha256, "reconcile_required")

    def complete(self, slot, payload_sha256, receipt):
        return self.transition(slot, payload_sha256, "completed", receipt)


def eligible_apps(root=ROOT, platform="android_emulator"):
    """Coverage is source eligibility only, not a claim of working capture hardware."""
    scenarios = json.loads((root / "data/video_recording_scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    store_platform = "android" if platform == "android_emulator" else "ios"
    eligible, coverage = [], []
    with (root / "data/apps_registry.csv").open(encoding="utf-8-sig", newline="") as stream:
        for app in csv.DictReader(stream):
            if app.get("status") != "released":
                continue
            reasons = []
            candidates = [s for s in scenarios if s.get("app_id") == app["app_id"] and s.get("production_eligible") is True]
            supported = [s for s in candidates if platform in s.get("platforms", [])]
            released_platforms = public_video_platforms(app, root / "data/store_versions.csv")
            if app.get("content_eligible") != "true": reasons.append("not_content_eligible")
            if store_platform not in released_platforms: reasons.append("no_released_host_platform_store_evidence")
            if not candidates: reasons.append("recording_scenario_missing")
            elif not supported: reasons.append("recording_platform_unsupported")
            row = {"app_id": app["app_id"], "app_name": app["app_name"], "released_platforms": released_platforms, "blockers": reasons, "capture_verified": False}
            coverage.append(row)
            if not reasons:
                scenario = sorted(supported, key=lambda s: s["scenario_id"])[0]
                eligible.append({"app_id": app["app_id"], "app_name": app["app_name"], "scenario_id": scenario["scenario_id"], "platform": platform, "topic_ids": scenario.get("topics", [])})
    return eligible, coverage


def plan(config, ledger, apps, now):
    validate_ledger(ledger)
    blockers = config_blockers(config)
    slot = next_slot(now)
    due = aware(slot) <= now
    rows = [r for r in ledger["slots"].values() if r["channel_id"] == config.get("channel_id")]
    if not due: blockers.append("slot_not_due")
    if any(r["status"] != "completed" for r in rows): blockers.append("channel_has_unresolved_slot")
    if any(r["slot"] == slot and r["status"] == "completed" for r in rows): blockers.append("already_completed")
    last = {}
    for row in rows:
        if row["status"] == "completed":
            stamp = aware(row["receipt"]["published_at"])
            last[row["app_id"]] = max(last.get(row["app_id"], datetime.min.replace(tzinfo=timezone.utc)), stamp)
    selected = min(apps, key=lambda a: (last.get(a["app_id"], datetime.min.replace(tzinfo=timezone.utc)), a["app_id"])) if apps else None
    if not selected: blockers.append("no_supported_eligible_app")
    return {"slot": slot, "timezone": "Asia/Seoul", "cadence": "MO,WE,FR 09:00", "due": due, "selected_app": selected,
            "blockers": blockers, "ready_to_claim": not blockers, "legacy_fencing_is_operator_assertion": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "readiness"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--ledger-file", type=Path, help="Read-only saved ledger snapshot; never claim from it")
    parser.add_argument("--now", help="ISO timestamp for offline planning")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        blockers = config_blockers(config)
        ledger = {"schema_version": 1, "slots": {}}
        loaded = False
        if args.ledger_file:
            ledger = json.loads(args.ledger_file.read_text(encoding="utf-8")); loaded = True
        elif not blockers:
            try:
                ledger, _ = GitHubLedger(config).read(); loaded = True
            except CoordinationError as exc:
                blockers.append(str(exc))
        apps, coverage = eligible_apps(platform=config.get("platform", "android_emulator"))
        result = plan(config, ledger, apps, aware(args.now) if args.now else datetime.now(timezone.utc))
        if not loaded: blockers.append("shared_ledger_not_read")
        result["blockers"] = sorted(set(result["blockers"] + blockers))
        result.update(ready_to_claim=not result["blockers"], coverage=coverage, shared_ledger_read=loaded,
                      read_only=True, execution_supported_by_this_cli=False,
                      execution_prerequisites=["verified_youtube_credentials", "native_runtime", "managed_recording_source", "exclusive_avd_ownership", "disk_floor", "legacy_writer_fencing"])
        print(json.dumps(result, indent=2))
        return 0
    except (CoordinationError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc) if isinstance(exc, CoordinationError) else "coordinator_input_or_transport_error"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
