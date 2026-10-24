"""Manual-only, same-review Google Play reply revision (never a new reply).

Called only by the existing canonical publisher workflow after an explicit
GitHub owner REPLACE dispatch. Fail closed on current store observation, an
unexpected original review/reply, an untrusted ID, or uncertain posting state.
The daily reader/LaunchAgent cannot call this operation.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from store_review_approvals import read_reviews
from sync_store_reviews import urlopen_with_retry

REVISION_PATH = Path(__file__).resolve().parents[1] / "data/store_review_reply_revisions.json"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
VALID_STATES = {"awaiting_owner_dispatch", "published_unverified", "store_verified"}


def observed_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require_owner_dispatch(*, actor: str, triggering_actor: str, repository: str, event: str,
                           run_id: str, run_attempt: str) -> None:
    if (actor != "onnellab" or triggering_actor != "onnellab"
            or repository != "onnellab/onnel-content-engine" or event != "workflow_dispatch"
            or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or not re.fullmatch(r"[1-9][0-9]*", run_attempt)):
        raise ValueError("Exact GitHub owner workflow dispatch is required for an existing reply revision")


def google_review_url(package: str, review_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", package) or not UUID.fullmatch(review_id):
        raise ValueError("Real Google Play package and review ID are required")
    return ("https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
            f"{urllib.parse.quote(package)}/reviews/{urllib.parse.quote(review_id)}")


def get_live_google_review(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "ONNELLAB-Store-Review-Publisher/1.0",
    })
    with urlopen_with_retry(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("comments"), list):
        raise ValueError("Google Play review response is incomplete")
    return payload


def current_comments(data: dict, expected_id: str) -> tuple[dict, str]:
    if data.get("reviewId") != expected_id:
        raise ValueError("Google Play review ID differs from the approved revision")
    user, developer = [], []
    for entry in data.get("comments", []):
        if not isinstance(entry, dict):
            raise ValueError("Invalid Google Play review comment")
        if isinstance(entry.get("userComment"), dict):
            user.append(entry["userComment"])
        if isinstance(entry.get("developerComment"), dict):
            developer.append(entry["developerComment"])
    if len(user) != 1 or len(developer) != 1:
        raise ValueError("Exactly one existing written review and posted reply must be observed")
    return user[0], str(developer[0].get("text", ""))


def bind_current_review(record: dict, review: dict) -> None:
    if (record.get("review_id") != review.get("review_id")
            or record.get("app_id") != review.get("app_id")
            or record.get("app_slug") != review.get("app_slug")
            or record.get("platform") != review.get("platform")
            or record.get("platform") != "android"
            or review.get("review_kind") != "review"
            or review.get("status") != "replied"
            or record.get("expected_review_body") != review.get("body")
            or str(record.get("rating")) != str(review.get("rating"))
            or record.get("app_version") != review.get("app_version")
            or review.get("developer_reply") not in (
                record.get("expected_current_reply"), record.get("replacement_reply"))):
        raise ValueError("Saved review identity/reply changed; owner must inspect before editing")
    original = record.get("expected_current_reply")
    replacement = record.get("replacement_reply")
    if (not isinstance(original, str) or not original
            or not isinstance(replacement, str) or not replacement
            or original == replacement or len(replacement) > 350
            or "— ONNELLAB" in replacement
            or record.get("status") not in VALID_STATES):
        raise ValueError("Invalid revision payload or state")


def verify_live_identity(user: dict, record: dict) -> None:
    if (user.get("text") != record["expected_review_body"]
            or str(user.get("starRating")) != str(record["rating"])
            or str(user.get("appVersionName")) != str(record["app_version"])):
        raise ValueError("Live Google Play review content or version changed")


def apply_revision(record: dict, review: dict, *, package: str, google_token: str,
                   actor: str, triggering_actor: str, repository: str, event: str, run_id: str,
                   run_attempt: str, getter=get_live_google_review, poster=None) -> str:
    """Return store_verified or published_unverified; never retry an uncertain POST."""
    require_owner_dispatch(actor=actor, triggering_actor=triggering_actor,
                           repository=repository, event=event, run_id=run_id,
                           run_attempt=run_attempt)
    bind_current_review(record, review)
    if not google_token or poster is None:
        raise ValueError("Google Play credentials/canonical publisher are required")
    url = google_review_url(package, record["review_id"])
    before = getter(url, google_token)
    user, observed = current_comments(before, record["review_id"])
    verify_live_identity(user, record)
    expected, replacement = record["expected_current_reply"], record["replacement_reply"]
    if observed == replacement:
        record["status"] = "store_verified"
        record.setdefault("publication", {})["store_observed_at"] = observed_at()
        record["publication"]["verification_source"] = "google_reviews_get"
        record["publication"]["error"] = ""
        return record["status"]
    if observed != expected:
        raise ValueError("Live developer reply differs from approved previous reply")
    if record["status"] != "awaiting_owner_dispatch":
        # A prior accepted/uncertain POST must never be repeated just because
        # eventual consistency has not surfaced the new reply.
        raise ValueError("Previous reply edit is not store-verified; no duplicate POST")
    if run_attempt != "1":
        raise ValueError("A rerun cannot originate a second external review reply edit")
    publication = record.setdefault("publication", {})
    publication["attempts"] = int(publication.get("attempts", 0)) + 1
    publication["last_attempt_at"] = observed_at()
    publication["workflow_run_id"] = run_id
    publication["workflow_run_attempt"] = run_attempt
    publication["approved_by"] = actor
    publication["approval_channel"] = "github_owner_workflow_dispatch"
    record["status"] = "published_unverified"  # set before external operation
    poster(url + ":reply", google_token, "POST", {"replyText": replacement})
    publication["published_at"] = observed_at()
    after = getter(url, google_token)
    user_after, observed_after = current_comments(after, record["review_id"])
    verify_live_identity(user_after, record)
    if observed_after == replacement:
        record["status"] = "store_verified"
        publication["store_observed_at"] = observed_at()
        publication["verification_source"] = "google_reviews_get"
        publication["error"] = ""
    else:
        publication["error"] = "store_observation_not_yet_confirmed"
    return record["status"]


def process_revision(revision_id: str, *, reviews_path: Path, stores_path: Path,
                     token: str, poster, getter=get_live_google_review,
                     revisions_path: Path = REVISION_PATH,
                     environment=None) -> int:
    env = dict(os.environ if environment is None else environment)
    require_owner_dispatch(actor=env.get("GITHUB_ACTOR", ""),
                           triggering_actor=env.get("REPLY_TRIGGERING_ACTOR", ""),
                           repository=env.get("GITHUB_REPOSITORY", ""),
                           event=env.get("GITHUB_EVENT_NAME", ""),
                           run_id=env.get("GITHUB_RUN_ID", ""),
                           run_attempt=env.get("REPLY_RUN_ATTEMPT", ""))
    recordset = json.loads(revisions_path.read_text(encoding="utf-8"))
    if recordset.get("schema_version") != 1 or not isinstance(recordset.get("requests"), list):
        raise ValueError("Invalid revision request ledger")
    matches = [r for r in recordset["requests"] if isinstance(r, dict) and r.get("revision_id") == revision_id]
    if len(matches) != 1 or not revision_id.startswith("revision-"):
        raise ValueError("Exact registered revision ID is required")
    record = matches[0]
    reviews = read_reviews(reviews_path)
    review = reviews.get(record.get("review_id", ""))
    if not review:
        raise ValueError("Original saved review is missing")
    bind_current_review(record, review)
    with stores_path.open(encoding="utf-8") as handle:
        import csv
        stores = [row for row in csv.DictReader(handle)
                  if row.get("app_id") == record["app_id"] and row.get("platform") == "android"]
    if len(stores) != 1:
        raise ValueError("Expected one Google Play package lookup")
    if (record.get("expected_public_store_version") != stores[0].get("version")
            or not record.get("target_version_under_review")):
        raise ValueError("Public store version changed or target update declaration is missing")
    try:
        checked = datetime.fromisoformat(stores[0]["checked_at"].replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - checked
        if checked.tzinfo is None or age < timedelta(minutes=-1) or age > timedelta(hours=24):
            raise ValueError("Store observation is stale")
    except (KeyError, ValueError, TypeError) as error:
        raise ValueError("Fresh public Android store observation is required") from error
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(stores[0].get("store_url", "")).query)
    package = query.get("id", [""])[0]
    try:
        outcome = apply_revision(record, review, package=package, google_token=token,
                                 actor=env["GITHUB_ACTOR"], triggering_actor=env["REPLY_TRIGGERING_ACTOR"],
                                 repository=env["GITHUB_REPOSITORY"], event=env["GITHUB_EVENT_NAME"],
                                 run_id=env["GITHUB_RUN_ID"], run_attempt=env["REPLY_RUN_ATTEMPT"],
                                 getter=getter, poster=poster)
    except Exception as error:
        # Never write credential-bearing HTTP error text to the public ledger.
        if record["status"] == "published_unverified":
            record.setdefault("publication", {})["error"] = "publication_or_verification_uncertain"
            record["publication"]["error_type"] = type(error).__name__
        raise
    finally:
        recordset["updated_at"] = observed_at()
        revisions_path.write_text(json.dumps(recordset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if outcome == "store_verified" else 2
