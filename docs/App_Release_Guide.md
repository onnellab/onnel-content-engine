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

The script records App Store version metadata from the public lookup endpoint. Google Play package URLs are recorded as `manual_check` because this automation does not depend on an unstable public Play Store scraping path.

Use the snapshot as a signal. Create a GitHub Release row only when the new public release artifact is available and the change notes can be tied to that artifact.

Release candidate rows can be prepared from updated store snapshots:

```text
scripts/prepare_app_release_rows.py
```

The generated rows use `status=planned`. They do not upload anything until `artifact_path`, `checksum_sha256`, and any final release notes are filled and the row is changed to `status=ready`.

## Repository

`repository` must use `owner/name` format.

If app releases are stored in separate app repositories, use the app repository.

If an artifact is intentionally distributed from a shared release repository, document that in `notes`.
