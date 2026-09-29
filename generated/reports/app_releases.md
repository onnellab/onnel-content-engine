# App Release Status

Generated: 2026-09-29T21:55:42+09:00

## Summary

| Area | Status | Count |
| --- | --- | --- |
| Store | in_review | 2 |
| Store | not_released | 2 |
| Store | unchanged | 9 |
| Store | updated | 2 |
| GitHub Release | archived | 3 |
| GitHub Release | planned | 6 |

## Store Snapshots

| App | Platform | Store version/package | Repository version | Comparison | Store | Release | Repository | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligna | android | 1.0.7 | 1.0.7 | same | updated | - | onnellab/aligna | Create or verify release candidate |
| Aligna | ios | 1.0.6 | 1.0.7 | local_ahead | updated | planned | onnellab/aligna | Private test only; do not publish public GitHub Release |
| ClipNest | ios | 1.0.2 | 1.0.4 | local_ahead | unchanged | planned | onnellab/clipnest | Private test only; do not publish public GitHub Release |
| Melivra | android | com.onnellab.melivra | 1.0.3 | unknown | not_released | - | onnellab/melivra | No public store rollout yet |
| Melivra | ios | 6783644955 | 1.0.3 | unknown | not_released | - | onnellab/melivra | No public store rollout yet |
| Papira | android | com.onnellab.papira | - | unknown | in_review | - | onnellab/papira | Review status |
| Papira | ios | - | - | unknown | in_review | - | onnellab/papira | Review status |
| Quivra | android | 1.0.9 | 1.0.9 | same | unchanged | planned | onnellab/quivra | Add release artifact and checksum |
| Quivra | ios | 1.0.9 | 1.0.9 | same | unchanged | archived | onnellab/quivra | No action |
| Segra | android | 1.0.6 | 1.0.6 | same | unchanged | planned | onnellab/segra | Add release artifact and checksum |
| Segra | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/segra | No action |
| TagWeaver | android | 2.5.2 | 2.5.2 | same | unchanged | planned | onnellab/tagweaver | Add release artifact and checksum |
| TagWeaver | ios | 2.5.2 | 2.5.2 | same | unchanged | archived | onnellab/tagweaver | No action |
| VaultXT | android | 2.0.1 | 2.0.1 | same | unchanged | planned | onnellab/onnellab-text | Add release artifact and checksum |
| VaultXT | ios | 2.0.1 | 2.0.1 | same | unchanged | archived | onnellab/onnellab-text | No action |

## Release Candidates

| ID | App | Platform | Channel | Tag | Status | Publication gate | Release URL | Artifact | Store notes | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-0018 | TagWeaver | android | public | v2.5.2 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0014 | VaultXT | ios | public | v2.0.0 | archived | Archived | - | - | Melivra에서 받은 가사 파일의 이름을 더 알아보기 쉽게 표시해요. | No action |
| REL-0017 | Segra | android | public | v1.0.6 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0013 | TagWeaver | ios | public | v2.5.0 | archived | Archived | - | - | Melivra에서 보낸 음악 파일을 열어 태그를 편집하는 흐름을 개선했어요. | No action |
| REL-0006 | ClipNest | ios | private_test | v1.0.4 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0009 | Quivra | ios | public | v1.0.7 | archived | Archived | - | - | Melivra에서 보낸 오디오 파일을 받아 변환하는 흐름을 개선했어요. | No action |
| REL-0019 | Quivra | android | public | v1.0.9 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0020 | VaultXT | android | public | v2.0.1 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0021 | Aligna | ios | private_test | v1.0.7 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| Aligna | android | updated | Create or verify release candidate | Version/update date read from Google Play public page; matching Android snapshot used as fallback metadata. Imported from github:onnellab/aligna/pubspec.yaml version 1.0.7+23; confirm against Play Console if needed. |
| TagWeaver | android | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| Segra | android | planned | Add release artifact and checksum | Updated from repository-ahead metadata after the same version was confirmed on the public store. Add release artifact, checksum, and set status=ready after verifying the release build. |
| ClipNest | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.2. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| Quivra | android | planned | Add release artifact and checksum | Updated from repository-ahead metadata after the same version was confirmed on the public store. Add release artifact, checksum, and set status=ready after verifying the release build. |
| VaultXT | android | planned | Add release artifact and checksum | Updated from repository-ahead metadata after the same version was confirmed on the public store. Add release artifact, checksum, and set status=ready after verifying the release build. |
| Aligna | ios | planned | Private test only; do not publish public GitHub Release | Generated from repository build metadata because repository version is ahead of store snapshot. Store version: 1.0.6. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. |
