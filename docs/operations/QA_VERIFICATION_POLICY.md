# QA verification and release gate policy

All findings require objective evidence: file path, line, test output, platform
rule, or caller/contract reference. Do not report speculation. If evidence is
missing, record `STOP`; Release Gate treats `STOP` as `FAIL`.

Required checks: critical bugs (only crash, data loss, permission/security
boundary), recent-change Spec/Anchor/AGENTS compliance, iOS device risks
(sandbox/path, picker/provider access, security-scoped resources, plist/
entitlements/App Groups, plugin bridges, lifecycle), caller/contract/flow side
effects, unused code, objective quality, APP_ANCHOR user scenarios, Android/
iOS platform audit, and final release gate.

Each check must be `PASS`, `FAIL`, or `STOP`; include evidence. Severity is
only `CRITICAL`, `HIGH`, or `LOW`. A final PASS additionally requires analyze
0 errors, a passing app-owned `tool/performance_gate.sh`, storage integrity,
lifecycle safety, and no Spec/Anchor/AGENTS violation. A missing performance
gate is `not_configured` and blocks merge. Ambiguity is FAIL.

For Flutter layout stabilization, perform up to ten actual edit rounds in the
app repository. Prioritize bottom actions, fixed Columns, forms/keyboards,
modal sheets, SafeArea, scrolling, text scale, and hard-coded heights. Fix
only objective overflow risks while preserving UX and Anchor/Spec. Do not pass
without an edit when a fixable structural overflow risk is found.
