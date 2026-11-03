# Owned-upload inventory recovery

## Incident and scope (2026-11-03)

The durable local result reported `aether_single_remote_inventory_unverified`
at `uploads_ids_invalid_or_duplicate`, after two pages and 50 verified IDs.
That older combined diagnostic cannot establish whether the provider returned
a malformed ID, a within-page duplicate or a cross-page overlap. Do not claim
a confirmed provider root cause or successful publication from this repair.

## Recovery contract

`require_no_owned_title_match` still requires a complete owner-authenticated
inventory, including private and scheduled videos. On malformed or duplicate
upload-page IDs only, it performs one additional READ-ONLY inventory pass:
re-read the owner channel, discard pagination tokens, and start at page one
with 25 results instead of 50. Each pass retains the existing 100-page bound.
No job, paid-generation call, approval, render or upload is retried here.

The second pass must satisfy every original ownership, title, privacy, detail,
pagination and count gate independently. Valid IDs observed in the first pass,
including those in a defective page, must all be observed and detail-verified
in the complete second pass. Never merge partial passes, skip bad rows,
deduplicate an invalid page into success, or treat missing data as absence.
Persistent anomalies retain the stable top-level blocker. Safe diagnostics
distinguish invalid IDs, duplicates within a page and duplicates across pages,
and retain the first failure counters when a second pass fails. They contain
no IDs, titles, request URLs, provider payloads or credential material.

Title collisions and non-pagination failures are not retried by this recovery.
The existing bounded missing-detail re-read remains unchanged. Check the exact
09:00 KST deadline again after inventory verification, before spending on music
and before creating a first upload/approval.

## Execution ownership and verification

The 06:20 Asia/Seoul LaunchAgent `com.onnellab.aether-daily-local` remains the
only unattended local executor. This repair does not alter launchd, dispatch
a workflow, invoke production or mutate durable job/video/approval records.
A reporting task must not start a replacement worker. A repository commit
alone does not prove Mac adoption, a successful live inventory or publication.

Offline regression tests in `tests/test_aether_inventory_restart.py` compile
the actual guard definitions without importing production modules. Fixtures
exercise normal and transient pagination, persistent/malformed IDs, lost IDs
across retries, title collisions in every privacy state, missing details,
ownership/count/token/transport failures and diagnostic privacy. The deadline
checks are also inspected structurally at both production call sites.
Full integration and live production verification remain separate.
