# App Release Status

Generated: 2026-08-14T10:54:51+09:00

## Summary

| Area | Status | Count |
| --- | --- | --- |
| Store | failed | 1 |
| Store | manual_check | 1 |
| Store | unchanged | 11 |
| GitHub Release | planned | 6 |

## Store Snapshots

| App | Platform | Store version/package | Local version | Comparison | Store | Release | Repository | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligna | android | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| Aligna | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| ClipNest | ios | 1.0.2 | - | unknown | unchanged | planned | onnellab/clipnest | Private test only; do not publish public GitHub Release |
| Melivra | android | com.onnellab.melivra | - | unknown | manual_check | - | onnellab/melivra | Check Google Play update manually |
| Melivra | ios | - | - | unknown | failed | - | onnellab/melivra | Fix store lookup error |
| Quivra | android | 1.0.7 | 1.0.6 | store_ahead | unchanged | - | onnellab/quivra | Sync local metadata |
| Quivra | ios | 1.0.7 | 1.0.6 | store_ahead | unchanged | planned | onnellab/quivra | Add release artifact and checksum |
| Segra | android | 1.0.5 | 1.0.2 | store_ahead | unchanged | planned | onnellab/segra | Add release artifact and checksum |
| Segra | ios | 1.0.4 | 1.0.2 | store_ahead | unchanged | - | onnellab/segra | Sync local metadata |
| TagWeaver | android | 2.2.2 | 2.1.3 | store_ahead | unchanged | planned | onnellab/tagweaver | Add release artifact and checksum |
| TagWeaver | ios | 2.2.2 | 2.1.3 | store_ahead | unchanged | planned | onnellab/tagweaver | Add release artifact and checksum |
| VaultXT | android | 1.0.3 | 1.0.6 | local_ahead | unchanged | - | onnellab/onnellab-text | Covered by private test release row |
| VaultXT | ios | 1.0.3 | 1.0.6 | local_ahead | unchanged | planned | onnellab/onnellab-text | Private test only; do not publish public GitHub Release |

## Release Candidates

| ID | App | Platform | Channel | Tag | Status | Publication gate | Release URL | Artifact | Store notes | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-0008 | TagWeaver | android | public | v2.1.4 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0002 | VaultXT | ios | private_test | v1.0.6 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0011 | Segra | android | public | v1.0.5 | planned | Waiting for artifact and public approval | - | - | - | Add release artifact and checksum |
| REL-0010 | TagWeaver | ios | public | v2.2.2 | planned | Waiting for artifact and public approval | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Add release artifact and checksum |
| REL-0006 | ClipNest | ios | private_test | v1.0.4 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0009 | Quivra | ios | public | v1.0.7 | planned | Waiting for artifact and public approval | - | - | 일부 정상적인 MP4 파일이 변환 도중 너무 일찍 중단될 수 있던 문제를 수정했어요. 변환이 실제로 진행 중인 동안에는 긴 파일도 안정적으로 완료할 수 있도록 개선했어요. 변환할 수 없는 파일에 불필요한 재시도를 줄여 실패 결과를 더 빠르게 확인할 수 있어요. 파일 선택 화면에서는 Quivra가 지원하는 WAV, M4A, MOV, MP4 파일만 선택할 수 있도록 정리했어요. 기존 변환 음질과 영상 품질은 그대로 유지하면서 변환 안정성을 높였어요. | Add release artifact and checksum |

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| Quivra | android | unchanged | Sync local metadata | Version/update date read from Google Play public page; release notes from Android snapshot. Imported from /mnt/c/dev/projects/quivra/pubspec.yaml version 1.0.6+77; confirm against Play Console if needed. |
| VaultXT | android | unchanged | Covered by private test release row | Version/update date read from Google Play public page; release notes from Android snapshot. Imported from /home/lue/dev/onnellab-text/vaultxt/pubspec.yaml version 1.0.6+52; confirm against Play Console if needed. |
| Segra | ios | unchanged | Sync local metadata | - |
| Melivra | ios | failed | Fix store lookup error | App Store lookup returned no result for 6783644955 |
| Melivra | android | manual_check | Check Google Play update manually | Google Play has no stable public version lookup in this automation. |
| TagWeaver | android | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| VaultXT | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.3. Add release artifact, checksum, and keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| Segra | android | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| TagWeaver | ios | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
| ClipNest | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.2. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| Quivra | ios | planned | Add release artifact and checksum | Generated from public store version snapshot. Patch notes must describe changes since the previous public release. |
