# App Release Guide

This document defines how ONNELLAB app releases become GitHub Releases.

GitHub Releases are only for real app release artifacts. They are not a general content distribution channel.

## Rule

Create a row in `data/app_releases.csv` only when a new public app release is ready.

Allowed:

* `build_type = release`
* a real version and tag
* a real artifact file path
* a checksum for the artifact
* a previous tag when this is not the first public release

Blocked:

* debug builds
* dev builds
* internal builds
* test builds
* duplicate tags in the same repository
* missing artifacts

## Release Note Structure

Each GitHub Release should explain what changed from the previous release:

```text
# AppName v1.2.0

## What changed
- ...

## Compatibility
- ...

## Upgrade notes
- ...

## Checks
- Release build verified
- Debug build excluded
- Version tag: v1.2.0
```

## Manifest

The release manifest path is:

```text
data/app_releases.csv
```

Required fields:

```text
release_id
app_id
app_slug
app_name
repository
tag
version
platform
build_type
artifact_path
checksum_sha256
previous_tag
status
release_date
release_title
summary
changes
compatibility
upgrade_notes
notes
```

Status values:

```text
planned
ready
released
failed
archived
```

Only `ready` rows are eligible for GitHub Release automation.

Do not use artifact existence as a publishing decision. A release file may be a private TestFlight, Play Console internal test, or another non-public build. The automation can collect and checksum those files, but it must not mark a row `ready` until the public release is explicitly approved.

Run a safe preview with:

```text
scripts/create_github_releases.py --dry-run
```

Real automation creates GitHub Release drafts by default:

```text
scripts/create_github_releases.py
```

To create public releases instead of drafts:

```text
scripts/create_github_releases.py --publish
```

Required token:

```text
ONNELLAB_RELEASE_TOKEN
```

If `ONNELLAB_RELEASE_TOKEN` is not set, the script falls back to `GITHUB_TOKEN`.

For releases in a different repository, `ONNELLAB_RELEASE_TOKEN` must have release/content write permission for that repository.

## Store Version Snapshots

Store pages can be checked before preparing release rows:

```text
scripts/check_store_versions.py
```

The snapshot path is:

```text
data/store_versions.csv
```

The script records App Store version metadata from the public lookup endpoint. Android versions can be supplied from:

```text
data/android_store_versions.csv
```

Validate Android source data with:

```text
scripts/validate_android_store_versions.py
```

Supported Android source values are `play_console_export`, `manual_entry`, and `local_build_metadata`.

Sync `local_build_metadata` rows from configured app repositories with:

```text
scripts/sync_android_versions_from_repos.py
```

Repository mappings are configured in:

```text
data/local_repositories.csv
```

Import a Play Console style CSV export with:

```text
scripts/import_android_store_versions.py path/to/play-console-export.csv
```

Google Play package URLs are recorded as `manual_check` only when no Android source row exists, because this automation does not depend on an unstable public Play Store scraping path.

Use the snapshot as a signal. Create a GitHub Release row only when the new public release artifact is available and the change notes can be tied to that artifact.

Release candidate rows can be prepared from updated store snapshots:

```text
scripts/prepare_app_release_rows.py
```

The generated rows use `status=planned`. They do not upload anything until `artifact_path`, `checksum_sha256`, final release notes, and public release approval are present.

Release artifacts are configured in:

```text
data/app_release_config.csv
```

Validate it with:

```text
scripts/validate_app_release_config.py
```

Default artifact location:

```text
generated/releases/{app_slug}/{version}/{platform}/*-release.*
```

Publication approvals are recorded in:

```text
data/app_release_publications.csv
```

Use `public_release=true` only after the build is meant to be public, not just available as a private test artifact.

Example approval row:

```csv
release_id,public_release,approved_at,notes
REL-0002,true,2026-07-12T09:00:00+09:00,Approved after App Store release became public.
```

Leave the release ID absent, or use `public_release=false`, while the artifact is only for TestFlight, Play Console internal testing, local QA, or any other private test channel.

When exactly one matching release artifact exists, this command fills `artifact_path` and calculates `checksum_sha256`. It promotes the row to `status=ready` only when `data/app_release_publications.csv` approves that release ID:

```text
scripts/fill_ready_app_releases.py
```

Local release artifacts can be collected into `generated/releases/` with:

```text
scripts/collect_release_artifacts.py
```

iOS release artifacts are produced by Codemagic for the current workflow, so iOS planned rows remain in `planned` until an `.ipa` is provided or copied into the configured artifact path.

Codemagic artifact URLs can be recorded in:

```text
data/codemagic_artifacts.csv
```

Example Codemagic artifact row:

```csv
release_id,app_id,app_slug,version,platform,artifact_url,artifact_name,notes
REL-0002,APP-0003,vaultxt,1.0.6,ios,/artifacts/.../VaultXT.ipa,VaultXT.ipa,Copied from the Codemagic build artifact link.
```

Use either the full `https://api.codemagic.io/artifacts/...` URL or the `/artifacts/...` path. Do not record debug, dev, internal, or test artifact names.

Download recorded Codemagic artifacts with:

```text
CODEMAGIC_API_TOKEN=... scripts/download_codemagic_artifacts.py
```

The GitHub Actions secret name is:

```text
CODEMAGIC_API_TOKEN
```

The token is only required when `data/codemagic_artifacts.csv` contains a matching artifact URL that must be downloaded.

Generate the release status report with:

```text
scripts/generate_app_release_report.py
```

The report is written to:

```text
generated/reports/app_releases.md
```

The report compares store snapshot versions with local `pubspec.yaml` versions from `data/local_repositories.csv`. Comparison values:

```text
same
local_ahead
store_ahead
unknown
```

Sync the report to the fixed GitHub Issue with:

```text
scripts/sync_app_release_issue.py
```

## Repository

`repository` must use `owner/name` format.

If app releases are stored in separate app repositories, use the app repository.

If an artifact is intentionally distributed from a shared release repository, document that in `notes`.
