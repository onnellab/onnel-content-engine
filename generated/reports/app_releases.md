# App Release Status

Generated: 2026-10-09T06:21:44+09:00

## Summary

| Area | Status | Count |
| --- | --- | --- |
| Store | in_review | 1 |
| Store | unchanged | 11 |
| Store | updated | 3 |
| GitHub Release | archived | 1 |
| GitHub Release | planned | 2 |
| GitHub Release | released | 7 |

## Store Snapshots

| App | Platform | Store version/package | Repository version | Comparison | Store | Release | Repository | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligna | android | 1.0.7 | 1.0.7 | same | unchanged | released | onnellab/aligna | No action |
| Aligna | ios | 1.0.7 | 1.0.7 | same | unchanged | - | onnellab/aligna | No action |
| ClipNest | ios | 1.0.2 | 1.0.4 | local_ahead | unchanged | planned | onnellab/clipnest | Private test only; do not publish public GitHub Release |
| Melivra | android | 1.0.6 | 1.0.6 | same | unchanged | released | onnellab/melivra | No action |
| Melivra | ios | 6783644955 | 1.0.6 | unknown | in_review | - | onnellab/melivra | Review status |
| Papira | android | 2.0.1 | - | unknown | unchanged | - | onnellab/papira | No action |
| Papira | ios | 2.0.1 | - | unknown | unchanged | - | onnellab/papira | No action |
| Quivra | android | 1.0.10 | 1.0.10 | same | updated | released | onnellab/quivra | Create or verify release candidate |
| Quivra | ios | 1.0.9 | 1.0.10 | local_ahead | unchanged | planned | onnellab/quivra | Private test only; do not publish public GitHub Release |
| Segra | android | 1.0.6 | 1.0.6 | same | unchanged | released | onnellab/segra | No action |
| Segra | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/segra | No action |
| TagWeaver | android | 2.5.3 | 2.5.3 | same | updated | released | onnellab/tagweaver | Create or verify release candidate |
| TagWeaver | ios | 2.5.3 | 2.5.3 | same | updated | released | onnellab/tagweaver | No action |
| VaultXT | android | 2.0.1 | 2.0.1 | same | unchanged | released | onnellab/onnellab-text | No action |
| VaultXT | ios | 2.0.1 | 2.0.1 | same | unchanged | archived | onnellab/onnellab-text | No action |

## Release Candidates

| ID | App | Platform | Channel | Tag | Status | Automatic publication | Release URL | Artifact | Store notes | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-0018 | TagWeaver | android | public | v2.5.2 | released | Public GitHub Release published | https://github.com/onnellab/tagweaver/releases/tag/v2.5.2 | - | - | No action |
| REL-0014 | VaultXT | ios | public | v2.0.0 | archived | Archived | - | - | Melivra에서 받은 가사 파일의 이름을 더 알아보기 쉽게 표시해요. | No action |
| REL-0017 | Segra | android | public | v1.0.6 | released | Public GitHub Release published | https://github.com/onnellab/segra/releases/tag/v1.0.6 | - | - | No action |
| REL-0025 | TagWeaver | ios | public | v2.5.3 | released | Public GitHub Release published | https://github.com/onnellab/tagweaver/releases/tag/v2.5.3 | - | - 화면 모드에서 시스템 설정, 라이트, 다크를 직접 선택할 수 있어요. - 라이브러리 탐색과 저장 피드백을 더 자연스럽게 다듬었어요. - 최신 ONNELLAB 디자인 규칙에 맞춰 화면의 일관성과 접근성을 개선했어요. | No action |
| REL-0006 | ClipNest | ios | private_test | v1.0.4 | planned | Private test; public GitHub Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0024 | Quivra | ios | private_test | v1.0.10 | planned | Private test; public GitHub Release disabled | - | - | Melivra에서 보낸 오디오 파일을 받아 변환하는 흐름을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0019 | Quivra | android | public | v1.0.9 | released | Public GitHub Release published | https://github.com/onnellab/quivra/releases/tag/v1.0.9 | - | - | No action |
| REL-0020 | VaultXT | android | public | v2.0.1 | released | Public GitHub Release published | https://github.com/onnellab/onnellab-text/releases/tag/v2.0.1 | - | - | No action |
| REL-0021 | Aligna | android | public | v1.0.7 | released | Public GitHub Release published | https://github.com/onnellab/aligna/releases/tag/v1.0.7 | - | - | No action |
| REL-0023 | Melivra | android | public | v1.0.6 | released | Public GitHub Release published | https://github.com/onnellab/melivra/releases/tag/v1.0.6 | - | - | No action |

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| Quivra | android | updated | Create or verify release candidate | Version/update date read from Google Play public page; matching Android snapshot used as fallback metadata. Imported from github:onnellab/quivra/pubspec.yaml version 1.0.10+85; confirm against Play Console if needed. |
| TagWeaver | android | updated | Create or verify release candidate | Version/update date read from Google Play public page; matching Android snapshot used as fallback metadata. Imported from github:onnellab/tagweaver/pubspec.yaml version 2.5.3+97; confirm against Play Console if needed. |
| ClipNest | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.2. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| Quivra | ios | planned | Private test only; do not publish public GitHub Release | Generated from repository build metadata because repository version is ahead of store snapshot. Store version: 1.0.9. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. |
