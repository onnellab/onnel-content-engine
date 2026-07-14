# App Release Status

Generated: 2026-07-14T11:29:37+09:00

## Summary

| Area | Status | Count |
| --- | --- | --- |
| Store | unchanged | 11 |
| GitHub Release | planned | 2 |
| GitHub Release | released | 4 |

## Store Snapshots

| App | Platform | Store version/package | Local version | Comparison | Store | Release | Repository | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Aligna | android | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| Aligna | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/aligna | No action |
| ClipNest | ios | 1.0.2 | - | unknown | unchanged | planned | onnellab/clipnest | Private test only; do not publish public GitHub Release |
| Quivra | android | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/quivra | No action |
| Quivra | ios | 1.0.6 | 1.0.6 | same | unchanged | - | onnellab/quivra | No action |
| Segra | android | 1.0.2 | 1.0.2 | same | unchanged | released | onnellab/segra | No action |
| Segra | ios | 1.0.1 | 1.0.2 | local_ahead | unchanged | - | onnellab/segra | Platform rollout not public |
| TagWeaver | android | 2.1.3 | 2.1.3 | same | unchanged | released | onnellab/tagweaver | No action |
| TagWeaver | ios | 2.2 | 2.1.3 | store_ahead | unchanged | released | onnellab/tagweaver | No action |
| VaultXT | android | 1.0.3 | 1.0.6 | local_ahead | unchanged | - | onnellab/onnellab-text | Covered by private test release row |
| VaultXT | ios | 1.0.3 | 1.0.6 | local_ahead | unchanged | planned | onnellab/onnellab-text | Private test only; do not publish public GitHub Release |

## Release Candidates

| ID | App | Platform | Channel | Tag | Status | Publication gate | Release URL | Artifact | Store notes | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-0001 | TagWeaver | android | public | v2.1.3 | released | Released | https://github.com/onnellab/tagweaver/releases/tag/v2.1.3 | - | Local Flutter build metadata version. | No action |
| REL-0002 | VaultXT | ios | private_test | v1.0.6 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |
| REL-0003 | Segra | android | public | v1.0.2 | released | Released | https://github.com/onnellab/segra/releases/tag/v1.0.2 | - | Local Flutter build metadata version. | No action |
| REL-0004 | TagWeaver | ios | public | v2.2 | released | Released | https://github.com/onnellab/tagweaver/releases/tag/v2.2 | - | 사소한 버그를 수정하고 안정성을 개선했어요. | No action |
| REL-0005 | ClipNest | ios | public | v1.0.2 | released | Released | https://github.com/onnellab/clipnest/releases/tag/v1.0.2 | - | 사소한 버그를 수정하고 안정성을 개선했어요. | No action |
| REL-0006 | ClipNest | ios | private_test | v1.0.4 | planned | Private test; public Release disabled | - | - | 사소한 버그를 수정하고 안정성을 개선했어요. | Private test only; do not publish public GitHub Release |

## Attention Queue

| App | Platform | Status | Next action | Notes |
| --- | --- | --- | --- | --- |
| VaultXT | android | unchanged | Covered by private test release row | Version/update date read from Google Play public page; release notes from Android snapshot. Imported from /home/lue/dev/onnellab-text/vaultxt/pubspec.yaml version 1.0.6+52; confirm against Play Console if needed. |
| Segra | ios | unchanged | Platform rollout not public | - |
| VaultXT | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.3. Add release artifact, checksum, and keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
| ClipNest | ios | planned | Private test only; do not publish public GitHub Release | Generated from local build metadata because local version is ahead of store snapshot. Store version: 1.0.2. Add release artifact and checksum only for private testing. Keep private until the version is publicly released. Private test channel; not promoted to public GitHub Release. |
