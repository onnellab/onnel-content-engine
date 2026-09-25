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
from datetime import datetime, date
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

def iso_now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")

def save(payload: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = RESULT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(RESULT)

def trim(value: str, limit: int = 12000) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[-limit:]

def run_step(report: dict, name: str, args: list[str], *, timeout: int = 1800) -> tuple[int, str, str]:
    started = iso_now()
    try:
        completed = subprocess.run(
            args, cwd=REPO, text=True, capture_output=True, timeout=timeout, check=False,
        )
        code, stdout, stderr = completed.returncode, trim(completed.stdout), trim(completed.stderr)
    except subprocess.TimeoutExpired as error:
        code = 124
        stdout = trim(error.stdout or "")
        stderr = "local_worker_timeout"
    report["steps"].append({
        "name": name, "started_at": started, "finished_at": iso_now(),
        "exit_code": code, "stdout": stdout, "stderr": stderr,
    })
    save(report)
    return code, stdout, stderr
def json_stdout(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {}

def repo_sync(report: dict) -> bool:
    code, dirty, _ = run_step(report, "repo_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0:
        report["blockers"].append("repo_status_failed")
        return False
    run_step(report, "repo_fetch", ["git", "fetch", "origin", "main"], timeout=120)
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


def run_hosted_ops_workflows(report: dict) -> None:
    repo = "onnellab/onnel-content-engine"
    workflows = [
        ("app_operational_status", "Sync app operational status"),
        ("ai_operations", "Refresh AI Operations Sources"),
        ("store_reviews", "Sync Store Reviews"),
    ]
    report["hosted_workflows"] = {}
    for key, workflow in workflows:
        code, stdout, _ = run_step(
            report,
            f"dispatch_{key}",
            ["gh", "workflow", "run", workflow, "-R", repo, "--ref", "main"],
            timeout=90,
        )
        url = next((line.strip() for line in reversed(stdout.splitlines()) if "/actions/runs/" in line), "")
        run_id = url.rstrip("/").split("/")[-1] if url else ""
        state = {"workflow": workflow, "run_id": run_id, "status": "dispatch_failed"}
        report["hosted_workflows"][key] = state
        if code != 0 or not run_id.isdigit():
            report["blockers"].append(f"{key}_workflow_dispatch_failed")
            continue
        code, _, _ = run_step(
            report,
            f"watch_{key}",
            ["gh", "run", "watch", run_id, "-R", repo, "--exit-status", "--interval", "3"],
            timeout=1800,
        )
        state["status"] = "success" if code == 0 else "failed"
        if code != 0:
            report["blockers"].append(f"{key}_workflow_failed")

    code, clean, _ = run_step(report, "hosted_ops_local_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0 or clean.strip():
        report["blockers"].append("hosted_ops_repo_not_clean")
        return
    run_step(report, "hosted_ops_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    code, counts, _ = run_step(
        report, "hosted_ops_divergence",
        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
    )
    parts = counts.split()
    if code != 0 or len(parts) != 2 or int(parts[0]) != 0:
        report["blockers"].append("hosted_ops_divergence_invalid")
        return
    if int(parts[1]):
        code, _, _ = run_step(
            report, "hosted_ops_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180,
        )
        if code != 0:
            report["blockers"].append("hosted_ops_pull_failed")


def run_store_review_auto_replies(report: dict) -> None:
    code, stdout, _ = run_step(
        report,
        "queue_standing_store_review_replies",
        [sys.executable, "-B", "scripts/queue_standing_store_review_replies.py"],
        timeout=120,
    )
    payload = json_stdout(stdout)
    report["store_review_auto_replies"] = payload
    if code != 0:
        report["blockers"].append("store_review_auto_reply_queue_failed")
        return
    queued = payload.get("queued", []) if isinstance(payload, dict) else []
    if not isinstance(queued, list):
        report["blockers"].append("store_review_auto_reply_queue_invalid")
        return

    if payload.get("changed"):
        code, names, _ = run_step(
            report, "review_approval_changed_paths", ["git", "diff", "--name-only"], timeout=30,
        )
        changed = {line.strip() for line in names.splitlines() if line.strip()}
        if code != 0 or changed != {"data/store_review_approvals.json"}:
            report["blockers"].append("review_approval_unexpected_changes")
            return
        code, _, _ = run_step(
            report, "review_approval_stage", ["git", "add", "data/store_review_approvals.json"], timeout=30,
        )
        if code != 0:
            report["blockers"].append("review_approval_stage_failed")
            return
        code, _, _ = run_step(
            report, "review_approval_commit", ["git", "commit", "-m", "Queue standing store review replies"], timeout=120,
        )
        if code != 0:
            report["blockers"].append("review_approval_commit_failed")
            return
        run_step(report, "review_approval_fetch", ["git", "fetch", "origin", "main"], timeout=120)
        code, counts, _ = run_step(
            report, "review_approval_divergence",
            ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], timeout=30,
        )
        parts = counts.split()
        if code != 0 or len(parts) != 2:
            report["blockers"].append("review_approval_divergence_failed")
            return
        if int(parts[1]):
            code, _, _ = run_step(report, "review_approval_rebase", ["git", "rebase", "origin/main"], timeout=180)
            if code != 0:
                report["blockers"].append("review_approval_rebase_failed")
                return
        code, _, _ = run_step(report, "review_approval_push", ["git", "push", "origin", "HEAD:main"], timeout=180)
        if code != 0:
            report["blockers"].append("review_approval_push_failed")
            return

    published_ids: list[str] = []
    for row in queued:
        if not isinstance(row, dict):
            continue
        approval_id = str(row.get("approval_id", ""))
        review_id = str(row.get("review_id", ""))
        if not approval_id or not review_id:
            report["blockers"].append("store_review_auto_reply_record_invalid")
            continue
        code, dispatch_stdout, _ = run_step(
            report,
            f"dispatch_review_reply_{review_id}",
            [
                "gh", "workflow", "run", "Publish Approved Store Review Reply",
                "-R", "onnellab/onnel-content-engine", "--ref", "main",
                "-f", f"approval_id={approval_id}", "-f", "confirm_publish=PUBLISH",
            ],
            timeout=90,
        )
        url = next((line.strip() for line in reversed(dispatch_stdout.splitlines()) if "/actions/runs/" in line), "")
        run_id = url.rstrip("/").split("/")[-1] if url else ""
        if code != 0 or not run_id.isdigit():
            report["blockers"].append(f"store_review_reply_dispatch_failed:{review_id}")
            continue
        code, _, _ = run_step(
            report,
            f"watch_review_reply_{review_id}",
            ["gh", "run", "watch", run_id, "-R", "onnellab/onnel-content-engine", "--exit-status", "--interval", "3"],
            timeout=1200,
        )
        if code != 0:
            report["blockers"].append(f"store_review_reply_publish_failed:{review_id}")
        published_ids.append(review_id)

    if not published_ids:
        return

    code, dispatch_stdout, _ = run_step(
        report,
        "dispatch_review_verification_sync",
        ["gh", "workflow", "run", "Sync Store Reviews", "-R", "onnellab/onnel-content-engine", "--ref", "main"],
        timeout=90,
    )
    url = next((line.strip() for line in reversed(dispatch_stdout.splitlines()) if "/actions/runs/" in line), "")
    run_id = url.rstrip("/").split("/")[-1] if url else ""
    if code != 0 or not run_id.isdigit():
        report["blockers"].append("store_review_verification_sync_dispatch_failed")
        return
    code, _, _ = run_step(
        report,
        "watch_review_verification_sync",
        ["gh", "run", "watch", run_id, "-R", "onnellab/onnel-content-engine", "--exit-status", "--interval", "3"],
        timeout=1800,
    )
    if code != 0:
        report["blockers"].append("store_review_verification_sync_failed")
        return
    run_step(report, "review_verification_fetch", ["git", "fetch", "origin", "main"], timeout=120)
    code, _, _ = run_step(report, "review_verification_pull", ["git", "pull", "--ff-only", "origin", "main"], timeout=180)
    if code != 0:
        report["blockers"].append("store_review_verification_pull_failed")
        return
    with (REPO / "data/store_reviews.csv").open(encoding="utf-8", newline="") as handle:
        reviews = {row.get("review_id", ""): row for row in csv.DictReader(handle)}
    verified = []
    for review_id in published_ids:
        row = reviews.get(review_id, {})
        if row.get("developer_reply") and row.get("status") == "replied":
            verified.append(review_id)
        else:
            report["blockers"].append(f"store_review_reply_not_observed:{review_id}")
    report["store_review_auto_replies"]["store_observed"] = verified


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

def run_single_slot(report: dict, now: datetime, single_reconcile: dict) -> None:
    if now.weekday() not in {1, 5}:
        report["single_slot"] = {"status": "not_scheduled_today"}
        return
    if (now.hour, now.minute) >= (9, 0):
        report["single_slot"] = {"status": "blocked", "error": "aether_single_publish_time_stale"}
        report["blockers"].append("aether_single_publish_time_stale")
        return
    if single_reconcile.get("status") not in {"idle", "published", "scheduled", "processing"}:
        report["single_slot"] = {
            "status": "blocked",
            "error": "aether_single_existing_job_unsettled",
            "reconcile_status": single_reconcile.get("status"),
        }
        report["blockers"].append("aether_single_existing_job_unsettled")
        return

    slot = now.date().isoformat()
    for title in BACKLOG:
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

    code, stdout, _ = run_step(
        report, "aether_single_readiness",
        [sys.executable, "-B", "scripts/aether_single.py", "readiness"],
        timeout=180,
    )
    readiness = json_stdout(stdout)
    report["aether_single_readiness"] = readiness
    if code != 0:
        report["single_slot"] = {"status": "blocked", "error": "aether_single_readiness_failed"}
        report["blockers"].append("aether_single_readiness_failed")
        return
    yt = readiness.get("youtube_credentials") or {}
    lyria = readiness.get("lyria") or {}
    if not (
        yt.get("configured") is True
        and lyria.get("state") == "ready"
        and lyria.get("enabled") is True
        and lyria.get("gcloud_ready") is True
        and lyria.get("auth_ready") is True
    ):
        report["single_slot"] = {"status": "blocked", "error": "aether_single_readiness_not_ready"}
        report["blockers"].append("aether_single_readiness_not_ready")
        return

    try:
        lane, title, style = choose_lyria_plan()
    except (OSError, ValueError, RuntimeError) as error:
        report["single_slot"] = {"status": "blocked", "error": str(error)}
        report["blockers"].append(str(error))
        return
    code, stdout, _ = run_step(
        report,
        "new_lyria_single",
        [
            sys.executable, "-B", "scripts/aether_single.py", "worker",
            "--slot", slot, "--lane", lane, "--title", title, "--style", style,
            "--execute", "--publish",
        ],
        timeout=3600,
    )
    payload = json_stdout(stdout)
    report["single_slot"] = payload or {
        "status": "blocked", "title": title, "lane": lane,
        "error": "aether_single_worker_output_invalid",
    }
    if code != 0:
        report["blockers"].append(
            report["single_slot"].get("error") or "aether_single_worker_failed"
        )
        return
    if payload.get("video_id") and payload.get("status") in {"scheduled", "processing", "published"}:
        sync_playlists_after_upload(report)

def run_compilation_slot(report: dict, now: datetime) -> None:
    start = date(2026, 9, 27)
    delta = (now.date() - start).days
    if now.weekday() != 6 or delta < 0 or delta % 14:
        report["compilation_slot"] = {"status": "not_scheduled_today"}
        return
    theme = COMPILATION_THEMES[(delta // 14) % len(COMPILATION_THEMES)]
    code, stdout, _ = run_step(
        report,
        "aether_compilation_slot",
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
    if code != 0:
        report["blockers"].append(
            report["compilation_slot"].get("error") or "aether_compilation_worker_failed"
        )

def publish_local_ops_sources(report: dict) -> None:
    code, clean, _ = run_step(report, "ops_prewrite_status", ["git", "status", "--porcelain"], timeout=30)
    if code != 0 or clean.strip():
        report["blockers"].append("ops_snapshot_repo_not_clean")
        return
    run_step(report, "ops_prewrite_fetch", ["git", "fetch", "origin", "main"], timeout=120)
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
    run_step(
        report, "restore_generated_dashboard",
        ["git", "restore", "--", "generated/manual-publish/index.html"],
        timeout=30,
    )
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
    run_step(report, "ops_snapshot_postcommit_fetch", ["git", "fetch", "origin", "main"], timeout=120)
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
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"state": "already_running", "result": str(RESULT)}))
            return 3
        now = datetime.now(KST)
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

        run_youtube_reports(report)
        if args.probe:
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
        publish_local_ops_sources(report)
        run_hosted_ops_workflows(report)
        run_store_review_auto_replies(report)
        code, status, _ = run_step(report, "post_ops_repo_status", ["git", "status", "--porcelain"], timeout=30)
        if code != 0 or status.strip():
            report["blockers"].append("repo_dirty_after_ops_snapshot")
            finalize(report)
            print(json.dumps({"state": report["state"], "blockers": report["blockers"]}))
            return 2

        single_reconcile = run_reconcile(report)
        run_single_slot(report, now, single_reconcile)
        run_compilation_slot(report, now)
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
        payload = {
            "schema_version": 1,
            "kind": "onnellab_aether_local_daily_result",
            "mode": "probe" if args.probe else "daily",
            "started_at": iso_now(),
            "finished_at": iso_now(),
            "local_date": datetime.now(KST).date().isoformat(),
            "state": "failed",
            "steps": [],
            "blockers": [f"local_worker_exception:{type(error).__name__}"],
            "warnings": [],
        }
        save(payload)
        print(json.dumps({"state": "failed", "blockers": payload["blockers"]}))
        return 2
    finally:
        os.close(fd)

if __name__ == "__main__":
    raise SystemExit(main())
