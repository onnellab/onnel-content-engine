# Repository Locations

This file records local repository paths that the content engine may need for release metadata or cross-repository automation.

Machine-readable app repository mappings live in:

```text
data/local_repositories.csv
```

Android version metadata can be synced from those mappings with:

```text
scripts/sync_android_versions_from_repos.py
```

## Primary WSL Checkouts

| Repository | WSL path | Notes |
| --- | --- | --- |
| onnellab-text | `/home/lue/dev/onnellab-text` | Primary WSL checkout for ONNELLAB text apps and packages. |
| melivra | `/home/lue/dev/melivra` | Primary WSL checkout for Melivra. |

## Other Related Checkouts

| Repository | Path | Notes |
| --- | --- | --- |
| onnellab-text | `/mnt/c/dev/onnellab-text` | Windows-mounted checkout. |
| melivra | `/mnt/c/dev/projects/melivra` | Windows-mounted project checkout. |
| onnel-content-engine | `/mnt/c/dev/onnel-content-engine` | Content automation repository. |
| onnellab.github.io | `/mnt/c/dev/onnellab.github.io` | Main ONNELLAB homepage repository. |
