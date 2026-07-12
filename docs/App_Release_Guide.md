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

## Repository

`repository` must use `owner/name` format.

If app releases are stored in separate app repositories, use the app repository.

If an artifact is intentionally distributed from a shared release repository, document that in `notes`.
