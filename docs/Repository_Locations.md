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

Flutter SDK 버전 제약과 앱별 직접 의존성(플러그인) 버전 스냅샷도 매번 동일한 매핑에서 관리할 수 있습니다.

```text
scripts/sync_flutter_plugin_versions.py
```

기본 출력:

```text
data/app_flutter_dependency_versions.csv
generated/reports/app_flutter_dependency_versions.md
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
