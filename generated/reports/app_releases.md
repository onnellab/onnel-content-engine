# App Release Status

Generated: 2026-09-26T20:27:08+09:00

## Summary

| Area | Status | Count |
| --- | --- | --- |
| Store | in_review | 2 |
| Store | not_released | 2 |
| Store | unchanged | 10 |
| Store | updated | 1 |
| GitHub Release | archived | 1 |
| GitHub Release | planned | 5 |

## Store Snapshots

| App | Platform | Store version/package | Repository version | Comparison | Store | Release | Repository | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligna | android | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| Aligna | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| ClipNest | ios | 1.0.2 | 1.0.4 | local_ahead | unchanged | planned | onnellab/clipnest | Private test only; do not publish public GitHub Release |
| Melivra | android | com.onnellab.melivra | 1.0.1 | unknown | not_released | - | onnellab/melivra | No public store rollout yet |
| Melivra | ios | 6783644955 | 1.0.1 | unknown | not_released | - | onnellab/melivra | No public store rollout yet |
| Papira | android | com.onnellab.papira | - | unknown | in_review | - | onnellab/papira | Review status |
| Papira | ios | - | - | unknown | in_review | - | onnellab/papira | Review status |
| Quivra | android | 1.0.7 | 1.0.8 | local_ahead | unchanged | - | onnellab/quivra | Covered by private test release row |
| Quivra | ios | 1.0.7 | 1.0.8 | local_ahead | unchanged | planned | onnellab/quivra | Private test only; do not publish public GitHub Release |
| Segra | android | 1.0.5 | 1.0.5 | same | unchanged | planned | onnellab/segra | Add release artifact and checksum |
| Segra | ios | 1.0.4 | 1.0.5 | local_ahead | unchanged | - | onnellab/segra | Add release artifact and checksum |
| TagWeaver | android | 2.5.1 | 2.5.1 | same | unchanged | planned | onnellab/tagweaver | Add release artifact and checksum |
| TagWeaver | ios | 2.5.1 | 2.5.1 | same | updated | archived | onnellab/tagweaver | Create or verify release candidate |
| VaultXT | android | 2.0.0 | 2.0.0 | same | unchanged | - | onnellab/onnellab-text | No action |
| VaultXT | ios | 2.0.0 | 2.0.0 | same | unchanged | planned | onnellab/onnellab-text | Add release artifact and checksum |

## Release Candidates

| ID | App | Platform | Channel | Tag | Status | Publication gate | Release URL | Artifact | Store notes | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-0015 | TagWeaver | android | public | v2.5.1 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0014 | VaultXT | ios | public | v2.0.0 | planned | Waiting for artifact and public approval | - | - | 폴더와 하위 폴더를 만들고 폴더 색상으로 문서를 구분해요. 문서를 나누거나 하나로 합치는 기능을 추가했어요. 9개 언어를 지원하고, 작은 화면이나 큰 글씨에서도 설정을 쓰기 편하게 다듬었어요. 큰 파일에서 커서와 글자 입력에 생기던 일부 문제를 고치고, 문서를 바꿀 때 더 안정적으로 저장하도록 개선했어요. 무료로 문서함 문서와 열린 문서를 각각 10개, 문서별 스냅샷 10개, 최대 10조각 나누기와 문서 10개 합치기를 지원해요. iOS 15 이상에서 사용할 수 있어요. | Add release artifact and checksum |
| REL-0011 | Segra | android | public | v1.0.5 | planned | Public approved, waiting for artifact | - | - | - | Add release artifact and checksum |
| REL-0013 | TagWeaver | ios | public | v2.5.0 | archived | Archived | - | - | 이제 iOS에서도 저장을 누르면 선택한 원본 파일에 편집 내용이 바로 반영돼요. 편집 후 별도 사본을 내보내거나 지울 필요가 없어요. 원본 위치에 저장할 수 없는 경우에만 복사본 저장 위치를 선택해요. | No action |
| REL-0006 | ClipNest | ios | private_test | v1.0.4 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0016 | Quivra | ios | private_test | v1.0.8 | planned | Private test; public Release disabled | - | - | 일부 정상적인 MP4 파일이 변환 도중 너무 일찍 중단될 수 있던 문제를 수정했어요. 변환이 실제로 진행 중인 동안에는 긴 파일도 안정적으로 완료할 수 있도록 개선했어요. 변환할 수 없는 파일에 불필요한 재시도를 줄여 실패 결과를 더 빠르게 확인할 수 있어요. 파일 선택 화면에서는 Quivra가 지원하는 WAV, M4A, MOV, MP4 파일만 선택할 수 있도록 정리했어요. 기존 변환 음질과 영상 품질은 그대로 유지하면서 변환 안정성을 높였어요. | Private test only; do not publish public GitHub Release |

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| Quivra | android | unchanged | Covered by private test release row | Version/update date read from Google Play public page; Android snapshot version 1.0.8 is stale for public version 1.0.7 and was not merged. |
| TagWeaver | ios | updated | Create or verify release candidate | - |
| Segra | ios | unchanged | Add release artifact and checksum | - |
| TagWeaver | android | planned | Add release artifact and checksum | Updated from repository-ahead metadata after the same version was confirmed on the public store. Add release artifact, checksum, and set status=ready after verifying the release build. |
| VaultXT | ios | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| Segra | android | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| ClipNest | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.2. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| Quivra | ios | planned | Private test only; do not publish public GitHub Release | Generated from repository build metadata because repository version is ahead of store snapshot. Store version: 1.0.7. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. |
