# Flutter Riverpod Firestore autosave QA profile

Apply this profile only when the QA packet selects
`flutter_riverpod_firestore_autosave_v1`. The profile is selected for an app
that uses Riverpod and Firestore and whose committed code or task contract
contains autosave/debounce/flush behavior. It does not apply to unrelated
Flutter apps.

The app's `APP_ANCHOR`, Execution Criteria, specification, and repository rules
remain the source of truth. If they define a 1.5-second debounce, no save
button, quiet status messaging, or a listener budget of one list listener plus
one open-document listener, QA must verify those exact requirements. QA must
not invent them for an app whose source of truth does not declare them.

## Blocking checks

Each item below must appear in `qa_report.json` with objective file, rule, test,
or command evidence. Missing evidence is `STOP`, not `PASS` or `N/A`.

### `architecture_state_boundary`

- Presentation depends on application, then domain/data; reverse imports do not
  bypass the app's declared architecture.
- UI does not reach into Firebase implementation details directly.
- Provider ownership and scope are explicit; global providers are minimal.
- Controller, provider, repository, and model names follow one repository
  convention.

### `riverpod_listener_lifecycle`

- UI uses `ref.watch` for reactive rendering and `ref.read` for actions.
- Every `ref.listen` has one clear owner and cannot duplicate or disappear
  during navigation, background/resume, or provider rebuilds.
- `autoDispose` cannot cancel a save or network operation that must finish.
- State transitions are atomic enough to avoid exposing partial save state.
- Any listener-count budget declared by the app's source of truth is verified
  across navigation and lifecycle transitions.

### `autosave_flush_integrity`

- No `base == null`, delayed-load, offline, navigation, or disposal path
  silently skips a required save.
- The declared debounce and exit-time flush both exist and are covered by
  evidence.
- Save failures do not block typing or navigation and retain a retry or local
  persistence path.
- Mobile lifecycle and web tab/page exit behavior provide the minimum guarantee
  that the app specification claims. Do not claim that an operating system
  guarantees asynchronous completion during process termination.

### `resource_disposal`

- `Timer`, `StreamSubscription`, controller, and lifecycle observer ownership
  is explicit.
- Disposal cancels obsolete work without discarding a required final save.
- No callback can use a disposed ref, notifier, controller, or widget state.

### `firestore_query_index`

- Every changed `where` plus `orderBy` query is checked for composite-index
  requirements.
- Server-side versus client-side sorting/filtering follows the documented v1
  strategy.
- Timestamp/null conversion cannot collapse ordering.
- Soft-delete queries and undo/restore behavior remain mutually consistent.

### `firestore_security_rules`

- Reads and writes are constrained by the authenticated owner on the server;
  client-supplied user IDs are not treated as authorization.
- Production Firestore/Storage Rules and required indexes are committed or
  otherwise referenced by objective deployment evidence.
- A different-UID denial test is required for release PASS. Missing emulator or
  provider evidence is `STOP`.

### `quiet_sync_ux`

- Offline, pending-write, cache, saved, and retry states are interpreted
  consistently.
- Status is conveyed through the app's declared unobtrusive surface rather than
  adding save buttons, blocking dialogs, or repeated popups.
- User-facing wording follows the app's tone rules without hiding actionable
  data-loss risk.

### `localization_tone`

- New user-facing text uses the repository localization mechanism rather than
  hard-coded strings.
- Wording follows the app's committed Korean/English tone and terminology.
- QA reports literal tone violations but does not rewrite product language
  without product authority.

## Report order

Present findings in this order inside the evidence for the applicable checks:

1. immediate fixes: compile, runtime, data-loss, security, or core UX failure;
2. v1 stabilization recommendations backed by an explicit rule or reproducible
   risk;
3. decisions to preserve because changing them would violate the source of
   truth;
4. patch scope, one file at a time, only when a patch is separately authorized.

QA is read-only. It must never return replacement source code as part of the
machine-readable report and must never merge, deploy, or weaken a gate.
