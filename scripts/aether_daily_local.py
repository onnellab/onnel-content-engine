#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, date
from uuid import uuid4
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
STATE = Path.home() / "Library/Application Support/ONNELLAB/content-engine/daily-aether"
RESULT = STATE / "result.json"
LOCK = STATE / "worker.lock"
KST = ZoneInfo("Asia/Seoul")

BACKLOG = [
    "Beyond the Road of Falling Petals",
    "The First Lantern of Autumn",
    "Beyond the Silent Stone Gate",
    "The Meadow Where Skylarks Sing",
    "The Old Library of Everlight",
    "When the Northern Lights Returned",
]
COMPILATION_THEMES = ["open_roads", "lantern_towns", "woodland_water", "starlit_rest"]
# These sleeps occur only inside the launchd-owned daily worker, before any
# compilation job/render/upload exists. They never retry uncertain publication.
COMPILATION_ASSET_RETRY_DELAYS = (45, 120)
MAX_SAME_DAY_COMPILATION_RECOVERIES = 2
AETHER_ASSET_PROGRESS = (Path.home() / "Library/Application Support/ONNELLAB"
                         / "content-engine/aether-inn/assets/registration-progress.json")

TITLE_BANK = {
    "quiet_road": [
        "The Road Beneath the Pale Morning Sky",
        "Lanterns Along the Rain-Washed Road",
        "Where the Meadow Path Turns Home",
        "A Quiet Mile Beyond the Village Gate",
        "The Inn at the End of the Long Road",
    ],
    "skybound_flight": [
        "Sails Above the Silver Cloud Sea",
        "The Airship Route Beyond Dawn",
        "Where Floating Islands Meet the Wind",
        "Cloud Harbors of the Eastern Sky",
        "The Flight Across the Sapphire Thermals",
    ],
    "open_sea_voyage": [
        "Sails Beyond the Amber Harbor",
        "The Sea Road to Distant Islands",
        "Where the Western Wind Fills the Sails",
        "Across the Blue Beyond the Lighthouse",
        "The Voyage Beneath a Wide Morning Sky",
    ],
    "deepwater_descent": [
        "Ruins Beneath the Luminous Tide",
        "The Descent to the Sunken Archive",
        "Where Coral Lights the Ancient Gate",
        "Below the Sea of Sleeping Stars",
        "The Deepwater Path to Forgotten Halls",
    ],
    "traveler_march": [
        "The Caravan Road Beneath Bright Banners",
        "Travelers Through the Harvest Gate",
        "The Guild Road on Festival Morning",
        "A March Across the Kingdom Road",
        "The Long Procession Toward Everlight",
    ],
    "triumphal_return": [
        "The Gates Opened When We Came Home",
        "Banners Above the Returning Road",
        "The Day the Harbor Welcomed Us Home",
        "Homecoming Beyond the Golden Walls",
        "When the Long Journey Reached the Capital",
    ],
    "frontier_surge": [
        "Across the Frontier Before Sunrise",
        "The Pass Beyond the Racing Plains",
        "Toward the Horizon of the New Kingdom",
        "The Ridge Where the Wild Road Begins",
        "Beyond the Gate to the Northern Frontier",
    ],
    "night_wonder": [
        "Aurora Above the Sleeping Kingdom",
        "The Night Road Beneath Returning Stars",
        "Moonlight at the Last Reunion",
        "Where the Northern Sky Remembers Us",
        "The Farewell Beneath a Quiet Constellation",
    ],
}

COMMON_STYLE = (
    " Nostalgic JRPG/MMORPG fantasy travel identity. Begin with immediate melodic movement; "
    "use warm guitar, midrange piano, mellow strings, cello or flute as appropriate. "
    "Develop gradually with a memorable but non-fatiguing melody and finish clearly on the tonal home. "
    "No combat music, military aggression, EDM, anime-pop, trailer bombast, or unresolved ending."
)

def now_kst() -> datetime:
    return datetime.now(KST)

def iso_now() -> str:
    return now_kst().isoformat(timespec="seconds")

def save(payload: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    target = RESULT.with_name("probe-result.json") if payload.get("mode") == "probe" else RESULT
    if payload.get("mode") == "single_today":
        target = RESULT.with_name("single-today-result.json")
    if payload.get("mode") == "sleep":
        target = RESULT.with_name("sleep-result.json")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(target)

def trim(value: str | bytes | None, limit: int = 12000) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = (value or "").strip()
    return value if len(value) <= limit else value[-limit:]

def run_step(report: dict, name: str, args: list[str], *, timeout: int = 1800) -> tuple[int, str, str]:
    started = iso_now()
    report["active_step"] = {"name": name, "started_at": started}
    save(report)
    try:
        completed = subprocess.run(
            args, cwd=REPO, text=True, capture_output=True, timeout=timeout, check=False,
        )
        code, stdout, stderr = completed.returncode, trim(completed.stdout), trim(completed.stderr)
    except subprocess.TimeoutExpired as error:
        code = 124
        stdout = trim(error.stdout or "")
        stderr = "local_worker_timeout"
    except OSError as error:
        code, stdout = 127, ""
        stderr = f"local_worker_start_failed:{type(error).__name__}"
    report["steps"].append({
        "name": name, "started_at": started, "finished_at": iso_now(),
        "exit_code": code, "stdout": stdout, "stderr": stderr,
    })
    report.pop("active_step", None)
    save(report)
    return code, stdout, stderr
def json_stdout(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("local_worker_json_object_required")
    return payload

def repo_sync(report: dict) -> bool:
    code, dirty, _ = run_step(report, "repo_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0:
        report["blockers"].append("repo_status_failed")
        return False
    code, _, _ = run_step(report, "repo_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    if code != 0:
        report["blockers"].append("repo_fetch_failed")
        return False
    code, counts, _ = run_step(
        report, "repo_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    if code != 0:
        report["blockers"].append("repo_divergence_failed")
        return False
    parts = counts.split()
    ahead = int(parts[0]) if len(parts) == 2 else 0
    behind = int(parts[1]) if len(parts) == 2 else 0
    report["repository"] = {"dirty": bool(dirty.strip()), "ahead": ahead, "behind": behind}
    if dirty.strip():
        report["blockers"].append("repo_worktree_dirty")
        return False
    if behind:
        code, _, _ = run_step(report, "repo_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180)
        if code != 0:
            report["blockers"].append("repo_pull_failed")
            return False
    if ahead:
        report["blockers"].append("repo_local_ahead_of_origin")
        return False
    return True

def choose_lyria_plan() -> tuple[str, str, str]:
    lanes_payload = json.loads((REPO / "data/aether_single_lanes.json").read_text(encoding="utf-8"))
    lanes = {row["id"]: row for row in lanes_payload["lanes"]}
    rules = lanes_payload["rules"]
    queue_path = Path.home() / "Library/Application Support/ONNELLAB/content-engine/aether-inn/singles/queue.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else {"jobs": {}}
    jobs = sorted(
        [j for j in queue.get("jobs", {}).values() if j.get("lane") in lanes],
        key=lambda j: (str(j.get("slot", "")), str(j.get("id", ""))),
    )
    used = {str(j.get("title", "")).casefold() for j in jobs}
    catalog_payload = json.loads((REPO / "data/aether_catalog.json").read_text(encoding="utf-8"))
    catalog = catalog_payload.get("songs", []) if isinstance(catalog_payload, dict) else catalog_payload
    used.update(str(row.get("title", "")).casefold() for row in catalog if isinstance(row, dict))
    order = list(lanes)
    start = len(jobs) % len(order)
    order = order[start:] + order[:start]

    def allowed(lane_id: str) -> bool:
        lane = lanes[lane_id]
        max_calm = int(rules.get("max_consecutive_calm", 2))
        tail = jobs[-max_calm:] if max_calm else []
        if len(tail) == max_calm and all(lanes[j["lane"]].get("energy") == "calm" for j in tail):
            if lane.get("energy") == "calm":
                return False
        recent = jobs[-7:]
        if len(recent) == 7:
            high = sum(lanes[j["lane"]].get("energy") == "high_motion" for j in recent)
            traversal = sum(bool(lanes[j["lane"]].get("traversal")) for j in recent)
            if high < int(rules.get("min_high_motion_in_window", 3)) and lane.get("energy") != "high_motion":
                return False
            if traversal < int(rules.get("min_traversal_in_window", 2)) and not lane.get("traversal"):
                return False
        return True
    for lane_id in order:
        if not allowed(lane_id):
            continue
        for title in TITLE_BANK.get(lane_id, []):
            if title.casefold() in used:
                continue
            style = str(lanes[lane_id].get("direction", "")).strip() + COMMON_STYLE
            return lane_id, title, style
    raise RuntimeError("lyria_title_pool_exhausted")

def run_youtube_reports(report: dict) -> None:
    report["youtube"] = {}
    for profile in ("onnellab", "aether_inn"):
        code, stdout, stderr = run_step(
            report,
            f"youtube_report_{profile}",
            [sys.executable, "-B", "scripts/youtube_report_run.py", "--profile", profile, "sync"],
            timeout=180,
        )
        payload = json_stdout(stdout)
        report["youtube"][profile] = payload or {
            "profile": profile,
            "state": "blocked",
            "error": "youtube_report_output_invalid" if code == 0 else "youtube_report_failed",
        }
        if code != 0:
            report["blockers"].append(f"youtube_report_{profile}_failed")


# gh run watch relies on the /jobs API; its HTTP 502 is not proof
# that the already-dispatched workflow run itself failed.
WORKFLOW_RECHECK_INTERVAL_SECONDS = 10
WORKFLOW_RECHECK_MAX_POLLS = 90
WORKFLOW_RECHECK_MAX_API_ERRORS = 6


def watch_hosted_run(
    report: dict, *, label: str, run_id: str, workflow: str,
    watch_timeout: int = 1800, max_polls: int = WORKFLOW_RECHECK_MAX_POLLS,
) -> dict:
    """Verify an existing workflow run without creating a new attempt.

    A nonzero gh watch exit is ambiguous. Read only the original ID's
    /actions/runs endpoint, with exact workflow/branch/event matching.
    Incomplete/unavailable evidence is unverified, never a proven failure.
    """
    repo = "onnellab/onnel-content-engine"
    if not isinstance(run_id, str) or not run_id.isdecimal():
        return {"status": "unverified", "verification_error": "invalid_run_id"}
    code, _, _ = run_step(
        report, f"watch_{label}",
        ["gh", "run", "watch", run_id, "-R", repo, "--exit-status", "--interval", "3"],
        timeout=watch_timeout,
    )
    if code == 0:
        return {"status": "success", "watch_exit_code": 0,
                "verification_source": "gh_run_watch_exit_status"}

    # Only safe run metadata enters the local report; do not read logs/jobs.
    selection = "{id: .id, name: .name, path: .path, display_title: .display_title, status: .status, conclusion: .conclusion, event: .event, head_branch: .head_branch}"
    expected = report.get("hosted_workflows", {}).get(label, {})
    dispatch_key = expected.get("dispatch_key", "")
    api_errors = 0
    for attempt in range(1, max_polls + 1):
        if attempt > 1:
            time.sleep(WORKFLOW_RECHECK_INTERVAL_SECONDS)
        result_code, stdout, _ = run_step(
            report, f"verify_{label}_run_{attempt}",
            ["gh", "api", "-X", "GET", f"repos/{repo}/actions/runs/{run_id}",
             "--jq", selection],
            timeout=45,
        )
        if result_code != 0:
            api_errors += 1
            if api_errors >= WORKFLOW_RECHECK_MAX_API_ERRORS:
                return {"status": "unverified", "verification_source": "same_run_api",
                        "verification_error": "run_api_unavailable",
                        "watch_exit_code": code, "api_error_count": api_errors}
            continue
        try:
            observed = json.loads(stdout)
        except (TypeError, ValueError):
            return {"status": "unverified", "verification_source": "same_run_api",
                    "verification_error": "invalid_run_metadata",
                    "watch_exit_code": code}
        if not hosted_run_identity_matches(
            observed, workflow=workflow, run_id=run_id, dispatch_key=dispatch_key,
        ):
            return {"status": "unverified", "verification_source": "same_run_api",
                    "verification_error": "run_identity_mismatch",
                    "watch_exit_code": code}
        api_errors = 0
        status = observed.get("status")
        if status == "completed":
            conclusion = observed.get("conclusion")
            if conclusion not in {
                "success", "failure", "cancelled", "timed_out",
                "action_required", "neutral", "skipped", "stale",
            }:
                return {"status": "unverified", "verification_source": "same_run_api",
                        "verification_error": "unknown_run_conclusion",
                        "watch_exit_code": code}
            if conclusion == "success":
                report.setdefault("warnings", []).append(
                    f"workflow_watch_error_recovered:{label}"
                )
            return {"status": "success" if conclusion == "success" else "failed",
                    "verification_source": "same_run_api",
                    "watch_exit_code": code, "observed_conclusion": conclusion}
        if status not in {"queued", "in_progress", "requested", "waiting", "pending"}:
            return {"status": "unverified", "verification_source": "same_run_api",
                    "verification_error": "unknown_run_status",
                    "watch_exit_code": code}
    return {"status": "unverified", "verification_source": "same_run_api",
            "verification_error": "run_completion_not_observed",
            "watch_exit_code": code}


# A workflow_dispatch HTTP 5xx can be returned AFTER GitHub accepted the
# event. Correlate by the unique run-name; never issue a second POST here.
DISPATCH_RECHECK_INTERVAL_SECONDS = 10
DISPATCH_RECHECK_MAX_POLLS = 6
WORKFLOW_DISPATCH_PATHS = {
    "Sync app operational status": ".github/workflows/sync-app-operational-status.yml",
    "Refresh AI Operations Sources": ".github/workflows/refresh-ai-operations.yml",
    "Sync Store Reviews": ".github/workflows/sync-store-reviews.yml",
    "Deploy Ops Dashboard": ".github/workflows/deploy-ops-dashboard.yml",
}
WORKFLOW_DISPATCH_TITLES = {
    "Sync app operational status": "Daily app status",
    "Refresh AI Operations Sources": "Daily AI operations",
    "Sync Store Reviews": "Daily store reviews",
    "Deploy Ops Dashboard": "Daily ops dashboard",
}


def hosted_run_identity_matches(
    observed: object, *, workflow: str, run_id: str | None = None,
    dispatch_key: str = "",
) -> bool:
    """Bind a run to stable workflow path plus its durable dispatch identity.

    GitHub may expose run-name in both name and display_title. Neither a fixed
    name comparison nor a startswith/prefix match identifies a workflow safely.
    """
    expected_path = WORKFLOW_DISPATCH_PATHS.get(workflow)
    if not expected_path or not isinstance(observed, dict):
        return False
    if (type(observed.get("id")) is not int or observed["id"] <= 0
            or (run_id is not None and str(observed["id"]) != run_id)
            or observed.get("path") != expected_path
            or observed.get("event") != "workflow_dispatch"
            or observed.get("head_branch") != "main"
            or not isinstance(dispatch_key, str)):
        return False
    if dispatch_key:
        title = f"{WORKFLOW_DISPATCH_TITLES[workflow]} [{dispatch_key}]"
        return observed.get("display_title") == title
    # Older retained runs have no dispatch key; the exact run ID and path are
    # still mandatory in watch_hosted_run. Do not invent a historical key.
    return run_id is not None


def hosted_run_blocker(label: str, state: dict) -> str:
    if state.get("status") != "failed":
        return f"{label}_workflow_verification_unavailable"
    if state.get("observed_conclusion") == "cancelled":
        return f"{label}_workflow_cancelled"
    return f"{label}_workflow_failed"


def reconcile_ambiguous_dispatch(
    report: dict, *, label: str, workflow: str, dispatch_key: str,
    started_at: str,
) -> dict:
    """Read-only lookup for the unique workflow_dispatch; never retry POST."""
    repo = "onnellab/onnel-content-engine"
    earliest = datetime.fromisoformat(started_at).timestamp() - 30
    projection = (
        "{workflow_runs: [.workflow_runs[] | "
        "{id, name, display_title, path, event, head_branch, created_at}]}"
    )
    successful_reads = 0
    for attempt in range(1, DISPATCH_RECHECK_MAX_POLLS + 1):
        if attempt > 1:
            time.sleep(DISPATCH_RECHECK_INTERVAL_SECONDS)
        code, stdout, _ = run_step(
            report, f"reconcile_dispatch_{label}_{attempt}",
            [
                "gh", "api", "-X", "GET",
                f"repos/{repo}/actions/runs?event=workflow_dispatch&branch=main&per_page=30",
                "--jq", projection,
            ],
            timeout=45,
        )
        if code != 0:
            continue
        try:
            observed = json.loads(stdout)
        except (TypeError, ValueError):
            return {"verification_error": "dispatch_run_list_invalid"}
        if not isinstance(observed, dict) or not isinstance(observed.get("workflow_runs"), list):
            return {"verification_error": "dispatch_run_list_invalid"}
        successful_reads += 1
        candidates = []
        for row in observed["workflow_runs"]:
            if not hosted_run_identity_matches(
                row, workflow=workflow, dispatch_key=dispatch_key,
            ) or not isinstance(row.get("created_at"), str):
                continue
            try:
                created = datetime.fromisoformat(
                    row["created_at"].replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                continue
            if created >= earliest:
                candidates.append(str(row["id"]))
        if len(candidates) == 1:
            return {
                "run_id": candidates[0],
                "verification_source": "unique_dispatch_key_run_lookup",
            }
        if len(candidates) > 1:
            return {
                "verification_error": "multiple_correlated_runs",
                "candidate_run_ids": candidates,
            }
    return {
        "verification_error": (
            "no_correlated_run_observed" if successful_reads
            else "dispatch_run_list_unavailable"
        ),
        "read_attempts": DISPATCH_RECHECK_MAX_POLLS,
    }


def dispatch_hosted_workflow(
    report: dict, *, label: str, workflow: str, extra_args: tuple[str, ...] = (),
) -> dict:
    """One POST maximum. An uncertain response can only be reconciled by GET."""
    repo = "onnellab/onnel-content-engine"
    dispatch_key = f"{now_kst():%Y%m%dT%H%M%S}-{label}-{uuid4().hex[:12]}"
    started_at = iso_now()
    state = {
        "workflow": workflow,
        "run_id": "",
        "status": "dispatching",
        "dispatch_key": dispatch_key,
        "dispatch_started_at": started_at,
    }
    # run_step saves this identity before the one possible side-effecting POST.
    report.setdefault("hosted_workflows", {})[label] = state
    code, stdout, _ = run_step(
        report, f"dispatch_{label}",
        [
            "gh", "workflow", "run", workflow, "-R", repo, "--ref", "main",
            "-f", f"daily_dispatch_key={dispatch_key}", *extra_args,
        ],
        timeout=90,
    )
    url = next(
        (line.strip() for line in reversed(stdout.splitlines()) if "/actions/runs/" in line),
        "",
    )
    run_id = url.rstrip("/").split("/")[-1] if url else ""
    if code == 0 and run_id.isdecimal():
        state.update(
            run_id=run_id, status="dispatched",
            verification_source="gh_workflow_dispatch_run_url",
        )
        return state

    # Any missing/uncertain response is NOT evidence of non-creation.
    # Never repeat the workflow_dispatch, even on HTTP 503 or a CLI timeout.
    recovered = reconcile_ambiguous_dispatch(
        report, label=label, workflow=workflow,
        dispatch_key=dispatch_key, started_at=started_at,
    )
    state.update(recovered)
    state["dispatch_exit_code"] = code
    if state.get("run_id"):
        state["status"] = "dispatched"
        report.setdefault("warnings", []).append(
            f"workflow_dispatch_response_reconciled:{label}"
        )
    else:
        state["status"] = "dispatch_unverified"
    return state


def run_hosted_ops_workflows(report: dict) -> bool:
    repo = "onnellab/onnel-content-engine"
    workflows = [
        ("app_operational_status", "Sync app operational status", ["-f", "deploy_dashboard=false"]),
        ("ai_operations", "Refresh AI Operations Sources", []),
        ("store_reviews", "Sync Store Reviews", ["-f", "deploy_dashboard=false"]),
    ]
    report["hosted_workflows"] = {}
    for key, workflow, extra_args in workflows:
        state = dispatch_hosted_workflow(
            report, label=key, workflow=workflow, extra_args=tuple(extra_args),
        )
        if not state["run_id"]:
            report["blockers"].append(f"{key}_workflow_dispatch_unverified")
            return False
        state.update(watch_hosted_run(
            report, label=key, run_id=state["run_id"], workflow=workflow,
        ))
        if state["status"] != "success":
            report["blockers"].append(hosted_run_blocker(key, state))
            return False

    code, clean, _ = run_step(report, "hosted_ops_local_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0 or clean.strip():
        report["blockers"].append("hosted_ops_repo_not_clean")
        return False
    code, _, _ = run_step(report, "hosted_ops_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    if code != 0:
        report["blockers"].append("hosted_ops_fetch_failed")
        return False
    code, counts, _ = run_step(
        report, "hosted_ops_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    parts = counts.split()
    if code != 0 or len(parts) != 2 or int(parts[0]) != 0:
        report["blockers"].append("hosted_ops_divergence_invalid")
        return False
    if int(parts[1]):
        code, _, _ = run_step(
            report, "hosted_ops_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("hosted_ops_pull_failed")
            return False
    return True


def run_store_review_auto_replies(report: dict) -> None:
    """Legacy function name retained; this stage only prepares owner notifications."""
    code, stdout, _ = run_step(
        report, "prepare_store_review_notifications",
        [sys.executable, "-B", "scripts/queue_standing_store_review_replies.py"],
        timeout=120,
    )
    payload = json_stdout(stdout)
    report["store_review_notifications"] = payload
    report["store_review_auto_replies"] = {"mode": "disabled", "queued": [], "publication_allowed": False}
    if code != 0:
        report["blockers"].append("store_review_notification_prepare_failed")
        return
    if (payload.get("mode") != "notify_only" or payload.get("queued") != []
            or payload.get("publication_allowed") is not False
            or not isinstance(payload.get("notifications"), list)):
        report["blockers"].append("store_review_notification_contract_invalid")
        return
    # The scheduled reporting task delivers pending notifications to the owner
    # and records its message receipt. Preparing this outbox is not delivery.
    if not payload.get("changed"):
        return
    allowed = {"data/store_review_approvals.json", "data/store_review_notifications.json"}
    code, names, _ = run_step(
        report, "review_notification_changed_paths", ["git", "diff", "--name-only"], timeout=30,
    )
    changed = {line.strip() for line in names.splitlines() if line.strip()}
    if code != 0 or not changed or not changed.issubset(allowed):
        report["blockers"].append("review_notification_unexpected_changes")
        return
    for name, argv, timeout in (
        ("stage", ["git", "add", *sorted(changed)], 30),
        ("commit", ["git", "commit", "-m", "Prepare store review owner notifications"], 120),
        ("fetch", ["git", "fetch", "origin", "main"], 120),
        ("rebase", ["git", "rebase", "origin/main"], 180),
        ("push", ["git", "push", "origin", "HEAD:main"], 180),
    ):
        code, _, _ = run_step(report, f"review_notification_{name}", argv, timeout=timeout)
        if code != 0:
            report["blockers"].append(f"review_notification_{name}_failed")
            return


def run_ops_dashboard_deploy(report: dict) -> None:
    workflow = "Deploy Ops Dashboard"
    state = dispatch_hosted_workflow(
        report, label="ops_dashboard", workflow=workflow,
    )
    if not state["run_id"]:
        report["blockers"].append("ops_dashboard_workflow_dispatch_unverified")
        return
    state.update(watch_hosted_run(
        report, label="ops_dashboard", run_id=state["run_id"], workflow=workflow,
    ))
    if state["status"] != "success":
        report["blockers"].append(hosted_run_blocker("ops_dashboard", state))
        return
    code, _, _ = run_step(report, "ops_dashboard_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    if code != 0:
        report["blockers"].append("ops_dashboard_fetch_failed")
        return
    code, counts, _ = run_step(
        report, "ops_dashboard_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    parts = counts.split()
    if code != 0 or len(parts) != 2 or int(parts[0]) != 0:
        report["blockers"].append("ops_dashboard_divergence_invalid")
        return
    if int(parts[1]):
        code, _, _ = run_step(
            report, "ops_dashboard_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("ops_dashboard_pull_failed")

def run_reconcile(report: dict) -> dict:
    code, stdout, _ = run_step(
        report, "aether_single_reconcile",
        [sys.executable, "-B", "scripts/aether_single.py", "reconcile", "--execute"],
        timeout=900,
    )
    single = json_stdout(stdout)
    report["aether_single_reconcile"] = single
    if code != 0:
        report["blockers"].append(single.get("error") or "aether_single_reconcile_failed")
    code, stdout, _ = run_step(
        report, "aether_compilation_reconcile",
        [sys.executable, "-B", "scripts/aether_compilation.py", "reconcile", "--execute"],
        timeout=900,
    )
    compilation = json_stdout(stdout)
    report["aether_compilation_reconcile"] = compilation
    if code != 0:
        report["blockers"].append(compilation.get("error") or "aether_compilation_reconcile_failed")

    code, stdout, _ = run_step(
        report, "aether_playlist_sync",
        [sys.executable, "-B", "scripts/aether_playlists.py", "--execute"],
        timeout=900,
    )
    playlists = json_stdout(stdout)
    report["aether_playlists"] = playlists
    if code != 0 or playlists.get("state") != "synced":
        report["blockers"].append(playlists.get("error") or "aether_playlist_sync_failed")
    return single

def sync_playlists_after_upload(report: dict) -> None:
    code, stdout, _ = run_step(
        report, "aether_playlist_sync_after_upload",
        [sys.executable, "-B", "scripts/aether_playlists.py", "--execute"],
        timeout=900,
    )
    payload = json_stdout(stdout)
    report["aether_playlists_after_upload"] = payload
    if code != 0 or payload.get("state") != "synced":
        report["blockers"].append(payload.get("error") or "aether_playlist_sync_after_upload_failed")

def choose_approved_new_single() -> dict | None:
    """Plan a no-duplicate Lyria concept only when its *own* cover is ready.

    The launchd-owned caller may spend up to $0.08 for a single audio candidate;
    it must not spend merely to discover a missing owner-approved cover.
    """
    from aether_single import FINAL, SingleQueue, enforce_lane_rotation
    from aether_existing_cover import ASSETS_ROOT, approved_cover
    from aether_cover import lane_direction
    from aether_planner import inspect_candidate, read_catalog
    from short_video_pipeline import VideoError

    registry = json.loads((REPO / "data/aether_single_lanes.json").read_text(encoding="utf-8"))
    lanes = registry.get("lanes", [])
    # Prefer traversal/high-motion concepts when compatible with canonical rotation.
    ordered = sorted(lanes, key=lambda row: (
        row.get("energy") != "high_motion",
        not bool(row.get("traversal")),
        row.get("id", ""),
    ))
    catalog = read_catalog()
    queue = SingleQueue()
    with queue.lock():
        state = queue._read()
        if any(j.get("upload") and j.get("status") not in FINAL for j in state["jobs"].values()):
            raise VideoError("aether_single_existing_job_unsettled")
        used_titles = {str(j.get("title") or "") for j in state["jobs"].values()}
        for row in ordered:
            lane = str(row.get("id", ""))
            if lane not in TITLE_BANK:
                continue
            try:
                enforce_lane_rotation(state, lane)
            except VideoError:
                continue
            style = lane_direction(lane) + COMMON_STYLE
            for title in TITLE_BANK[lane]:
                if title in used_titles or inspect_candidate(title, style, catalog)["metadata_gate"] == "rejected":
                    continue
                try:
                    approved_cover(title, ASSETS_ROOT)
                except VideoError:
                    continue
                return {"title": title, "style": style, "lane": lane}
    return None


def check_new_single_inputs(*, refresh_sources: bool = False) -> dict:
    """Verify price/terms before consuming a title/job; never call a model.

    Only the launchd-owned slot requests public-source refresh. Read-only status
    checks leave it disabled. The generator rechecks the same source hashes.
    """
    import aether_paid_guard as paid_guard
    from lyria_config import CONFIG_PATH, load_settings
    from short_video_credentials import CredentialError

    settings = load_settings(CONFIG_PATH)
    if not settings:
        raise CredentialError("lyria_not_configured")
    if not settings["enabled"]:
        raise CredentialError("lyria_generation_disabled")
    paid_guard.require_no_unsettled_intents()
    if refresh_sources:
        from aether_lyria_rights import collect, SourceError
        try:
            collect(root=paid_guard.PROOF_PATH.parent)
        except SourceError as error:
            reason = str(error).rsplit(":", 1)[-1]
            import re
            if not re.fullmatch(r"[a-z_0-9]{1,100}", reason):
                reason = "aether_lyria_provider_sources_refresh_failed"
            raise CredentialError(reason) from None
    return paid_guard.load_paid_proof(settings["project_id"])


def run_single_slot(report: dict, single_reconcile: dict) -> None:
    now = now_kst()
    if now.weekday() not in {1, 5}:
        report["single_slot"] = {"status": "not_scheduled_today"}
        return
    if (now.hour, now.minute) >= (9, 0):
        report["single_slot"] = {"status": "blocked", "error": "aether_single_publish_time_stale"}
        report["blockers"].append("aether_single_publish_time_stale")
        return
    slot = now.date().isoformat()
    reconcile_status = single_reconcile.get("status")
    if reconcile_status in {"scheduled", "processing", "published"} and single_reconcile.get("job_id"):
        if (
            single_reconcile.get("slot") == slot
            and single_reconcile.get("video_id")
        ):
            report["single_slot"] = {**single_reconcile, "reused_existing_job": True}
            return
        if reconcile_status in {"scheduled", "processing"}:
            report["single_slot"] = {
                "status": "blocked",
                "error": "aether_single_existing_job_unsettled",
                "reconcile_status": reconcile_status,
                "job_id": single_reconcile.get("job_id"),
                "video_id": single_reconcile.get("video_id"),
                "slot": single_reconcile.get("slot"),
            }
            report["blockers"].append("aether_single_existing_job_unsettled")
            return
    if reconcile_status not in {"idle", "published"}:
        report["single_slot"] = {
            "status": "blocked",
            "error": "aether_single_existing_job_unsettled",
            "reconcile_status": reconcile_status,
        }
        report["blockers"].append("aether_single_existing_job_unsettled")
        return

    for title in BACKLOG:
        current = now_kst()
        if current.date().isoformat() != slot or (current.hour, current.minute) >= (9, 0):
            report["single_slot"] = {"status": "blocked", "error": "aether_single_publish_time_stale"}
            report["blockers"].append("aether_single_publish_time_stale")
            return
        code, stdout, _ = run_step(
            report,
            f"backlog_{title}",
            [
                sys.executable, "-B", "scripts/aether_single.py", "backlog-worker",
                "--slot", slot, "--title", title, "--execute", "--publish",
            ],
            timeout=2400,
        )
        payload = json_stdout(stdout)
        if payload.get("status") == "already_public":
            continue
        report["single_slot"] = payload or {
            "status": "blocked", "title": title, "error": "aether_single_backlog_output_invalid",
        }
        if code != 0:
            report["blockers"].append(
                report["single_slot"].get("error") or "aether_single_backlog_failed"
            )
            return
        if payload.get("video_id") and payload.get("status") in {"scheduled", "processing", "published"}:
            sync_playlists_after_upload(report)
        return

    # Only after every canonical backlog title has been confirmed public may
    # this owner-authorized single Lyria 3 Pro slot be considered.
    current = now_kst()
    if current.date().isoformat() != slot or (current.hour, current.minute) >= (9, 0):
        error = "aether_single_publish_time_stale"
        report["single_slot"] = {"status": "blocked", "error": error}
        report["blockers"].append(error)
        return
    # Leave sufficient time for generation, offline review, rendering and a
    # private publishAt upload. Never charge for a likely missed 09:00 slot.
    if (current.hour, current.minute) >= (8, 0):
        error = "aether_lyria_generation_window_closed"
        report["single_slot"] = {"status": "blocked", "error": error}
        report["blockers"].append(error)
        return
    # Fail before planning creates another job or consumes its approved title.
    # These are the existing checks, not replacement authorization or a retry.
    try:
        evidence = check_new_single_inputs(refresh_sources=True)
        report["single_generation_inputs"] = evidence
    except Exception as error:
        from short_video_pipeline import VideoError
        import re
        reason = str(error) if isinstance(error, VideoError) and re.fullmatch(r"[a-z_0-9]{1,100}", str(error)) else "aether_single_input_preflight_failed"
        report["single_slot"] = {
            "status": "blocked", "source_kind": "new_lyria", "slot": slot,
            "stage": "generation_preflight", "error": reason,
            "created_new_job": False, "generation_attempted": False,
            "upload_attempted": False,
        }
        report["blockers"].append(reason)
        return
    current = now_kst()
    if current.date().isoformat() != slot or current.hour >= 8:
        reason = "aether_lyria_generation_window_closed"
        report["single_slot"] = {"status": "blocked", "error": reason,
                                 "created_new_job": False, "generation_attempted": False,
                                 "upload_attempted": False}
        report["blockers"].append(reason)
        return
    try:
        concept = choose_approved_new_single()
    except Exception as error:
        reason = str(error) if str(error) == "aether_single_existing_job_unsettled" else "aether_lyria_concept_preflight_failed"
        report["single_slot"] = {"status": "blocked", "error": reason}
        report["blockers"].append(reason)
        return
    if not concept:
        error = "aether_lyria_approved_cover_unavailable"
        report["single_slot"] = {"status": "blocked", "error": error,
                                 "source_kind": "new_lyria", "spent_usd": 0.0}
        report["blockers"].append(error)
        return
    # All actual execution still belongs to the existing durable single worker.
    # It rechecks the spend gate, cover, queue, exact publishAt and upload state.
    code, stdout, _ = run_step(
        report, "new_lyria_single",
        [
            sys.executable, "-B", "scripts/aether_single.py", "worker",
            "--slot", slot, "--title", concept["title"],
            "--style", concept["style"], "--lane", concept["lane"],
            "--execute", "--publish",
        ],
        timeout=2400,
    )
    payload = json_stdout(stdout)
    report["single_slot"] = payload or {
        "status": "blocked", "source_kind": "new_lyria",
        "title": concept["title"], "error": "aether_lyria_single_output_invalid",
    }
    if code != 0:
        report["blockers"].append(
            report["single_slot"].get("error") or "aether_lyria_single_failed"
        )
    elif payload.get("video_id") and payload.get("status") in {"scheduled", "processing", "published"}:
        sync_playlists_after_upload(report)


def run_today_single_slot(report: dict) -> None:
    from aether_single_today import SLOT, TITLE, LANE, canonical_style, require_target, load_cost_estimate
    from short_video_pipeline import VideoError
    try:
        require_target(SLOT, TITLE, canonical_style(), LANE)
        from aether_single import SingleQueue, YouTube, find_existing_public_video, require_no_owned_title_match
        from aether_single_today import job_id
        queue = SingleQueue()
        with queue.lock():
            existing = queue._read()["jobs"].get(job_id())
        # An exact, previously bound job belongs to the durable worker. Never
        # apply a no-duplicate inventory gate to its own upload or require a new
        # price receipt merely to reconcile already-paid artifacts. The worker
        # and paid adapter still recheck cost evidence if generation is needed.
        if existing:
            require_target(existing.get("slot"), existing.get("title"),
                           existing.get("style"), existing.get("lane"))
            if (existing.get("same_day_release") or {}).get("job_id") != job_id():
                raise VideoError("aether_single_today_generation_binding_invalid")
            report["resumed_existing_job"] = job_id()
        else:
            # Refresh official base-price/rights sources before binding the
            # owner-approved estimate. Never label the estimate an invoice.
            report["single_generation_inputs"] = check_new_single_inputs(refresh_sources=True)
            report["single_cost_estimate"] = load_cost_estimate()
            api = YouTube(profile="aether_inn")
            api.verify()
            for title in BACKLOG:
                if not find_existing_public_video(api, title):
                    raise VideoError("aether_single_backlog_not_public")
            require_no_owned_title_match(api, TITLE)
    except VideoError as error:
        report["single_slot"] = {"status": "blocked", "error": str(error),
                                 "created_new_job": False, "generation_attempted": False,
                                 "upload_attempted": False}
        report["blockers"].append(str(error))
        return
    code, stdout, _ = run_step(report, "same_day_single",
        [sys.executable, "-B", "scripts/aether_single.py", "worker",
         "--slot", SLOT, "--title", TITLE, "--style", canonical_style(), "--lane", LANE,
         "--same-day-release", "--execute", "--publish"], timeout=2400)
    payload = json_stdout(stdout) or {"status": "blocked", "error": "aether_single_today_output_invalid"}
    report["single_slot"] = payload
    if code != 0:
        report["blockers"].append(payload.get("error") or "aether_single_today_failed")
    elif payload.get("video_id") and payload.get("status") in {"scheduled", "processing", "published"}:
        sync_playlists_after_upload(report)


def run_sleep_slot(report: dict, now: datetime, reconciled: dict | None = None) -> None:
    """Same producer and queue, fixed three-source pilot, no new timer."""
    from aether_sleep_contract import CONCEPTS, PROPOSED_SLOTS, runtime_enabled
    if not runtime_enabled():
        report["sleep_slot"] = {"status": "disabled", "error": "sleep_pilot_disabled"}
        return
    local_date = now.astimezone(KST).date().isoformat()
    if local_date not in PROPOSED_SLOTS:
        report["sleep_slot"] = {"status": "not_scheduled_today"}
        return
    if reconciled and reconciled.get("series") == "aether_inn_sleep":
        report["sleep_slot"] = reconciled
        return  # Never run the same job twice within a daily pass.
    from aether_sleep_request import gui_requested, load_cost_estimate, PROJECT
    if gui_requested(now=now):
        from aether_sleep_guard import ROOT as sleep_root
        from aether_single import SingleQueue
        queue = SingleQueue()
        concept_id = CONCEPTS[PROPOSED_SLOTS.index(local_date)][0]
        with queue.lock():
            existing = [job for job in queue._read()["jobs"].values()
                        if job.get("concept_id") == concept_id]
        # Do not refresh/change proof after any irreversible reservation, nor
        # require fresh pricing merely to recover a completed paid source.
        reserved = (sleep_root / ("reservation-" + concept_id + ".json")).exists()
        generated = any(list((queue.root / "jobs" / job["id"] / "lyria").glob("*/manifest.json"))
                        for job in existing)
        if not reserved and not generated:
            report["sleep_generation_inputs"] = check_new_single_inputs(refresh_sources=True)
            # Source collection can finish after this slot's initial timestamp.
            # Validate the refreshed evidence at the actual current time, while
            # retaining all request/date/expiry checks in load_cost_estimate.
            report["sleep_cost_estimate"] = load_cost_estimate(PROJECT, now=now_kst())
    code, stdout, _ = run_step(
        report, "aether_sleep_slot",
        [sys.executable, "-B", "scripts/aether_single.py", "sleep-worker",
         "--concept", CONCEPTS[PROPOSED_SLOTS.index(local_date)][0],
         "--slot", local_date, "--execute", "--publish"], timeout=3600,
    )
    result = json_stdout(stdout) or {"status": "blocked", "error": "sleep_worker_output_invalid"}
    report["sleep_slot"] = result
    if code != 0 or result.get("status") in {"blocked", "reconcile_required", "rejected"}:
        report["blockers"].append(result.get("error") or "sleep_worker_failed")
    elif result.get("video_id"):
        sync_playlists_after_upload(report)


def scheduled_compilation_theme(now: datetime) -> str | None:
    start = date(2026, 9, 27)
    delta = (now.date() - start).days
    if now.weekday() != 6 or delta < 0 or delta % 14:
        return None
    return COMPILATION_THEMES[(delta // 14) % len(COMPILATION_THEMES)]


def compilation_asset_timeout_report(theme: str, slot: str) -> dict:
    """Fail closed, preserving the last private asset checkpoint on hard timeout."""
    result = {"status": "blocked", "error": "aether_asset_registration_timeout"}
    try:
        info = json.loads(AETHER_ASSET_PROGRESS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return result
    stages = {"locate_mybox_source", "materialize_audio", "review_audio",
              "materialize_cover", "render_cover", "manifest_ready"}
    if (isinstance(info, dict) and info.get("schema_version") == 1
            and info.get("theme") == theme and info.get("slot") == slot
            and info.get("stage") in stages):
        result["last_stage"] = info["stage"]
        title = info.get("title")
        if isinstance(title, str) and len(title) <= 200:
            result["last_title"] = title
    return result


def run_compilation_slot(report: dict, now: datetime, *, recovery: bool = False) -> None:
    """Run only the scheduled compilation; retry transient MYBOX reads before upload.

    The compilation publisher runs at most once per invocation. Materialization
    retries cannot produce a video, and their result is checkpointed durably.
    """
    theme = scheduled_compilation_theme(now)
    if theme is None:
        report["compilation_slot"] = {"status": "not_scheduled_today"}
        return

    stage = "aether_compilation_assets_recovery" if recovery else "aether_compilation_assets"
    for attempt in range(len(COMPILATION_ASSET_RETRY_DELAYS) + 1):
        if attempt:
            time.sleep(COMPILATION_ASSET_RETRY_DELAYS[attempt - 1])
        step = stage if not attempt else f"{stage}_retry_{attempt}"
        code, stdout, _ = run_step(
            report,
            step,
            [
                sys.executable, "-B", "scripts/aether_compilation_assets.py", "sync",
                "--execute", "--theme", theme, "--slot", now.date().isoformat(),
            ],
            timeout=1800,
        )
        assets = (compilation_asset_timeout_report(theme, now.date().isoformat())
                  if code == 124 else json_stdout(stdout) or {
                      "status": "blocked", "error": "aether_asset_registration_output_invalid",
                  })
        report["aether_compilation_assets"] = assets
        if code == 0 and assets.get("status") == "ready":
            break
        error = assets.get("error") or "aether_asset_registration_failed"
        if error == "aether_asset_source_materialization_failed" and attempt < len(COMPILATION_ASSET_RETRY_DELAYS):
            report["compilation_slot"] = {
                "status": "waiting_for_mybox",
                "theme": theme,
                "error": error,
                "asset_retry_count": attempt + 1,
            }
            save(report)
            continue
        report["compilation_slot"] = {"status": "blocked", "theme": theme, "error": error}
        if error not in report["blockers"]:
            report["blockers"].append(error)
        return

    step = "aether_compilation_slot_recovery" if recovery else "aether_compilation_slot"
    code, stdout, _ = run_step(
        report,
        step,
        [
            sys.executable, "-B", "scripts/aether_compilation.py", "worker",
            "--theme", theme, "--slot", now.date().isoformat(), "--execute", "--publish",
        ],
        timeout=3600,
    )
    payload = json_stdout(stdout)
    report["compilation_slot"] = payload or {
        "status": "blocked", "theme": theme, "error": "aether_compilation_output_invalid",
    }
    if code != 0 or report["compilation_slot"].get("status") in {"blocked", "rejected", "reconcile_required", "idle"}:
        error = report["compilation_slot"].get("error") or "aether_compilation_worker_failed"
        if error not in report["blockers"]:
            report["blockers"].append(error)


def compilation_resume_allowed(report: dict, now: datetime) -> bool:
    """Fail closed unless ONLY today's pre-publication MYBOX materialization failed."""
    if not isinstance(report, dict) or report.get("kind") != "onnellab_aether_local_daily_result":
        return False
    if report.get("mode") != "daily" or report.get("local_date") != now.date().isoformat():
        return False
    if report.get("state") != "partial":
        return False
    theme = scheduled_compilation_theme(now)
    slot = report.get("compilation_slot")
    assets = report.get("aether_compilation_assets")
    if not theme or not isinstance(slot, dict) or not isinstance(assets, dict):
        return False
    error = "aether_asset_source_materialization_failed"
    if (
        report.get("blockers") != [error]
        or slot.get("status") != "blocked"
        or slot.get("theme") != theme
        or slot.get("error") != error
        or assets.get("status") != "blocked"
        or assets.get("error") != error
        or slot.get("job_id") or slot.get("video_id") or slot.get("upload")
    ):
        return False
    if report.get("aether_compilation_reconcile", {}).get("status") != "idle":
        return False
    if report.get("aether_playlists", {}).get("state") != "synced":
        return False
    attempts = report.get("compilation_recovery_attempts", [])
    if not isinstance(attempts, list) or len(attempts) >= MAX_SAME_DAY_COMPILATION_RECOVERIES:
        return False
    steps = report.get("steps")
    if not isinstance(steps, list):
        return False
    # Never re-attempt asset registration after a render/upload may have begun;
    # even an interrupted or uncertain first worker call is a hard stop here.
    if any(
        isinstance(row, dict) and str(row.get("name", "")).startswith("aether_compilation_slot")
        for row in steps
    ):
        return False
    return any(
        isinstance(row, dict)
        and str(row.get("name", "")).startswith("aether_compilation_assets")
        and row.get("exit_code") != 0
        for row in steps
    )


def resume_compilation(report: dict, now: datetime) -> bool:
    """Called ONLY when launchd invokes this same worker again on the same day."""
    if not compilation_resume_allowed(report, now):
        return False
    history = report.setdefault("compilation_recovery_attempts", [])
    attempt = {
        "number": len(history) + 1,
        "started_at": iso_now(),
        "original_error": "aether_asset_source_materialization_failed",
    }
    history.append(attempt)
    report["state"] = "running"
    report.pop("finished_at", None)
    save(report)
    # Never use an unverified/stale repo; no YouTube reports, Ops workflows,
    # review publishers, single jobs or playlist changes run in this path.
    if not repo_sync(report):
        attempt.update(status="blocked", finished_at=iso_now(), error="aether_compilation_recovery_repository_blocked")
        finalize(report)
        return False
    report["blockers"] = [
        error for error in report["blockers"]
        if error != "aether_asset_source_materialization_failed"
    ]
    run_compilation_slot(report, now, recovery=True)
    attempt["status"] = report["compilation_slot"].get("status", "blocked")
    attempt["error"] = report["compilation_slot"].get("error")
    attempt["finished_at"] = iso_now()
    finalize(report)
    return not report["blockers"]


def publish_local_ops_sources(report: dict) -> None:
    code, clean, _ = run_step(report, "ops_prewrite_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0 or clean.strip():
        report["blockers"].append("ops_snapshot_repo_not_clean")
        return
    code, _, _ = run_step(report, "ops_prewrite_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    if code != 0:
        report["blockers"].append("ops_snapshot_fetch_failed")
        return
    code, counts, _ = run_step(
        report, "ops_prewrite_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    if code != 0:
        report["blockers"].append("ops_snapshot_divergence_failed")
        return
    parts = counts.split()
    if len(parts) != 2 or int(parts[0]) != 0:
        report["blockers"].append("ops_snapshot_local_ahead")
        return
    if int(parts[1]):
        code, _, _ = run_step(
            report, "ops_prewrite_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("ops_snapshot_pull_failed")
            return
    code, _, _ = run_step(
        report, "ai_provider_pricing",
        [sys.executable, "-B", "scripts/sync_ai_provider_pricing.py"],
        timeout=180,
    )
    if code != 0:
        report["blockers"].append("ai_provider_pricing_sync_failed")
    code, stdout, _ = run_step(
        report, "youtube_ops_snapshot",
        [
            sys.executable, "-B", "scripts/sync_youtube_ops_snapshot.py",
            "--snapshot-only",
            "--homepage-repo", str(Path.home() / "Projects" / "onnellab.github.io"),
        ],
        timeout=300,
    )
    if code != 0:
        report["blockers"].append("youtube_ops_snapshot_failed")
        return
    # The legacy generated/manual-publish/index.html was deliberately removed
    # from tracked sources. Restoring an untracked/nonexistent path emits a
    # spurious Git pathspec error despite a successful /ops/ deployment.
    code, _, _ = run_step(
        report, "dashboard_generated_track_check",
        ["git", "ls-files", "--cached", "--error-unmatch", "--", "generated/manual-publish/index.html"],
        timeout=30,
    )
    if code == 0:
        restored, _, _ = run_step(
            report, "restore_generated_dashboard",
            ["git", "restore", "--", "generated/manual-publish/index.html"],
            timeout=30,
        )
        if restored != 0:
            report["blockers"].append("ops_generated_dashboard_restore_failed")
            return
    elif code == 1:
        report["generated_dashboard_restore"] = "not_tracked_not_required"
    else:
        report["blockers"].append("ops_generated_dashboard_tracking_check_failed")
        return
    code, names, _ = run_step(
        report, "ops_snapshot_changed_paths",
        ["git", "diff", "--name-only"], timeout=30,
    )
    if code != 0:
        report["blockers"].append("ops_snapshot_diff_failed")
        return
    changed = {line.strip() for line in names.splitlines() if line.strip()}
    allowed = {"data/youtube_ops_snapshot.json", "data/ai_provider_pricing_status.json"}
    unexpected = sorted(changed - allowed)
    if unexpected:
        report["warnings"].append("ops_snapshot_extra_generated_changes_restored")
        report["ops_snapshot_unexpected_paths"] = unexpected
        run_step(report, "restore_extra_generated_changes", ["git", "restore", "--", *unexpected], timeout=30)
        changed -= set(unexpected)
    if not changed:
        report["ops_snapshot_commit"] = {"status": "unchanged"}
        return
    code, _, _ = run_step(
        report, "ops_snapshot_stage",
        ["git", "add", *sorted(changed)], timeout=30,
    )
    if code != 0:
        report["blockers"].append("ops_snapshot_stage_failed")
        return
    code, _, _ = run_step(
        report, "ops_snapshot_commit_git",
        ["git", "commit", "-m", "Refresh local daily operations sources"],
        timeout=120,
    )
    if code != 0:
        report["blockers"].append("ops_snapshot_commit_failed")
        return
    code, sha, _ = run_step(report, "ops_snapshot_commit_sha", ["git", "rev-parse", "HEAD"], timeout=30)
    report["ops_snapshot_commit"] = {"status": "committed", "sha": sha.strip() if code == 0 else ""}
    code, _, _ = run_step(report, "ops_snapshot_postcommit_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    if code != 0:
        report["blockers"].append("ops_snapshot_postcommit_fetch_failed")
        return
    code, counts, _ = run_step(
        report, "ops_snapshot_postcommit_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    if code != 0:
        report["blockers"].append("ops_snapshot_postcommit_divergence_failed")
        return
    parts = counts.split()
    ahead = int(parts[0]) if len(parts) == 2 else 0
    behind = int(parts[1]) if len(parts) == 2 else 0
    if behind:
        code, _, _ = run_step(
            report, "ops_snapshot_rebase",
            ["git", "rebase", "origin/main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("ops_snapshot_rebase_failed")
            return
    if ahead or behind:
        code, _, _ = run_step(
            report, "ops_snapshot_push",
            ["git", "push", "origin", "HEAD:main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("ops_snapshot_push_failed")
            return
    report["ops_snapshot_commit"]["pushed"] = True

def finalize(report: dict) -> None:
    report["finished_at"] = iso_now()
    report["state"] = "partial" if report["blockers"] else "complete"
    save(report)
def main() -> int:
    parser = argparse.ArgumentParser(description="Local fail-closed Aether daily worker")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--sleep-only", action="store_true")
    mode.add_argument("--single-today", action="store_true")
    mode.add_argument("--request-single-today", action="store_true")
    mode.add_argument("--request-sleep-today", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    report: dict | None = None
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"state": "already_running", "result": str(RESULT)}))
            return 3
        now = now_kst()
        if args.request_sleep_today:
            from aether_sleep_request import record_request
            print(json.dumps(record_request(now=now), ensure_ascii=False))
            return 0
        if args.request_single_today:
            from aether_single_today import record_request
            print(json.dumps(record_request(now=now), ensure_ascii=False))
            return 0
        if not (args.probe or args.sleep_only or args.single_today):
            from aether_single_today import pending_request
            # The registered GUI launchd service retains its original plist,
            # interpreter, security session and locks. The remote tmux shell
            # records the request and observes output; it does not impersonate
            # that session, unlock a keychain, or create another executor.
            if os.environ.get("XPC_SERVICE_NAME") == "com.onnellab.aether-daily-local":
                args.single_today = pending_request(now=now)
                from aether_sleep_request import gui_requested
                args.sleep_only = gui_requested(now=now)
                if args.single_today and args.sleep_only:
                    raise ValueError('aether_conflicting_same_day_requests')
        if args.single_today:
            report = {"schema_version": 1, "kind": "onnellab_aether_local_single_today_result",
                      "mode": "single_today", "started_at": now.isoformat(timespec="seconds"),
                      "local_date": now.date().isoformat(), "state": "running",
                      "steps": [], "blockers": [], "warnings": []}
            save(report)
            if repo_sync(report):
                run_today_single_slot(report)
            finalize(report)
            print(json.dumps(report, ensure_ascii=False))
            return 2 if report["blockers"] else 0
        if args.sleep_only:
            # Explicit same-owner continuation. Preserve daily reports and never
            # repeat fantasy/Ops/compilation stages on a same-day invocation.
            report = {"schema_version": 1, "kind": "onnellab_aether_local_sleep_result",
                      "mode": "sleep", "started_at": now.isoformat(timespec="seconds"),
                      "local_date": now.date().isoformat(), "state": "running",
                      "steps": [], "blockers": [], "warnings": []}
            save(report)
            if repo_sync(report):
                run_sleep_slot(report, now_kst())
            finalize(report)
            print(json.dumps(report, ensure_ascii=False))
            return 2 if report["blockers"] else 0
        if not args.probe and RESULT.exists():
            try:
                existing = json.loads(RESULT.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                print(json.dumps({"state": "blocked", "error": "local_daily_result_unreadable"}))
                return 2
            if not isinstance(existing, dict):
                print(json.dumps({"state": "blocked", "error": "local_daily_result_invalid"}))
                return 2
            if existing.get("local_date") == now.date().isoformat():
                if (
                    existing.get("kind") != "onnellab_aether_local_daily_result"
                    or existing.get("mode") != "daily"
                ):
                    print(json.dumps({"state": "blocked", "error": "local_daily_result_invalid"}))
                    return 2
                if existing.get("state") == "complete":
                    print(json.dumps({
                        "state": "already_complete",
                        "local_date": existing.get("local_date"),
                        "finished_at": existing.get("finished_at"),
                    }))
                    return 0
                if compilation_resume_allowed(existing, now):
                    report = existing
                    return 0 if resume_compilation(report, now) else 2
                # A partial/failed/unsettled daily pass must NEVER repeat the
                # whole Ops/YouTube/publisher pipeline on a same-day relaunch.
                print(json.dumps({
                    "state": "already_recorded",
                    "local_date": existing.get("local_date"),
                    "original_state": existing.get("state"),
                    "blockers": existing.get("blockers", []),
                }, ensure_ascii=False))
                return 2
        report = {
            "schema_version": 1,
            "kind": "onnellab_aether_local_daily_result",
            "mode": "probe" if args.probe else "daily",
            "started_at": now.isoformat(timespec="seconds"),
            "local_date": now.date().isoformat(),
            "state": "running",
            "steps": [],
            "blockers": [],
            "warnings": [],
        }
        save(report)
        if not repo_sync(report):
            finalize(report)
            print(json.dumps({"state": report["state"], "blockers": report["blockers"]}))
            return 2

        if args.probe:
            run_youtube_reports(report)
            code, stdout, _ = run_step(
                report, "single_readiness_probe",
                [sys.executable, "-B", "scripts/aether_single.py", "readiness"], timeout=180,
            )
            report["single_readiness_probe"] = json_stdout(stdout)
            if code != 0:
                report["blockers"].append("single_readiness_probe_failed")
            code, stdout, _ = run_step(
                report, "compilation_readiness_probe",
                [sys.executable, "-B", "scripts/aether_compilation.py", "readiness"], timeout=180,
            )
            report["compilation_readiness_probe"] = json_stdout(stdout)
            if code != 0:
                report["blockers"].append("compilation_readiness_probe_failed")
            finalize(report)
            print(json.dumps({"state": report["state"], "blockers": report["blockers"]}))
            return 0 if not report["blockers"] else 2
        # The 08:00 generation / 09:00 publication deadlines cannot wait for
        # hosted Actions (which can queue or take hours). The same launchd
        # owner performs the original music stages once, before reporting/Ops.
        # run_single_slot still enforces the real current date and deadlines;
        # this does not recover, reschedule or revive a stale single.
        report["execution_order"] = "aether_before_reporting_and_hosted_ops"
        single_reconcile = run_reconcile(report)
        run_single_slot(report, single_reconcile)
        run_sleep_slot(report, now_kst(), single_reconcile)
        run_compilation_slot(report, now_kst())
        save(report)
        # Capture reports AFTER music so the later snapshot/deploy reflects the
        # outcome of this pass, not only the inventory from before production.
        run_youtube_reports(report)
        publish_local_ops_sources(report)
        hosted_sources_ready = run_hosted_ops_workflows(report)
        if hosted_sources_ready:
            run_store_review_auto_replies(report)
            run_ops_dashboard_deploy(report)
        else:
            report["hosted_ops_downstream"] = "skipped_unverified_or_failed_source"
        # Preserve the post-Ops repository check and any earlier music IDs.
        # Music already ran once; hosted failures never trigger another attempt.
        code, status, _ = run_step(report, "post_ops_repo_status", ["git", "status", "--porcelain"], timeout=30)
        if code != 0 or status.strip():
            report["blockers"].append("repo_dirty_after_ops_snapshot")
            finalize(report)
            print(json.dumps({"state": report["state"], "blockers": report["blockers"]}))
            return 2

        finalize(report)
        print(json.dumps({
            "state": report["state"],
            "local_date": report["local_date"],
            "single_slot": report.get("single_slot"),
            "compilation_slot": report.get("compilation_slot"),
            "blockers": report["blockers"],
        }, ensure_ascii=False))
        return 0 if not report["blockers"] else 2
    except Exception as error:
        blocker = f"local_worker_exception:{type(error).__name__}"
        if report is not None:
            # Keep original dates, completed steps and durable job/video/approval IDs.
            report["state"] = "failed"
            report["finished_at"] = iso_now()
            report.setdefault("blockers", []).append(blocker)
            save(report)
        # Before this invocation owns a report, leave the existing result untouched.
        blockers = report["blockers"] if report is not None else [blocker]
        print(json.dumps({"state": "failed", "blockers": blockers}))
        return 2
    finally:
        os.close(fd)

if __name__ == "__main__":
    raise SystemExit(main())


