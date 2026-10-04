# Content pipeline recovery — 2026-10-04

## Scope

This repair covers local code, regression tests, and a review branch. It does not
activate a scheduler, execute the supply model, publish articles, rotate tokens,
or deploy the dashboard. A passing dry-run is not evidence of public publication.

## Observed installation

- Windows task `ONNELLAB Codex Content Supply` is enabled and Ready, scheduled for
  06:00 Asia/Seoul. Its last observed run was 2026-10-04 06:00:01 KST with result
  `4294967295` (`0xFFFFFFFF`), not success.
- Its action invokes Ubuntu WSL and
  `/mnt/c/dev/onnel-content-engine/scripts/run_codex_content_supply.sh`.
  That installed checkout was at `05ca67e`, behind remote `610a2ee`.
- The WSL Codex executable exists and a read-only status check confirmed a
  ChatGPT subscription login without exposing authentication values. No supply run logs were found at the old
  `/tmp/onnel-content-supply-runs` location. The precise cause of the historical
  task failure remains unconfirmed; absence of logs is not proof of a login issue.
- No matching 09:00 publisher was found in the accessible Windows tasks or
  ChatGPT automations. Further read-only inspection of the connected Mac found
  `.codex/automations/onnellab-work-publisher/automation.toml`: ID
  `onnellab-work-publisher`, status `ACTIVE`, daily 09:00 recurrence. Its obsolete
  prompt still selects `work_browser`, includes Hashnode, and writes
  `data/work_browser_publications.json`. These conflict with the current
  `remote_browser`, Hashnode exclusion, and `data/remote_browser_publications.json`
  contract. The file was not modified. Recent execution success and authenticated
  browser availability were not verified; ACTIVE configuration alone proves neither.

## Code changes

- Supply qualification reuses the publication gate's current article fingerprint,
  mandatory checks, and strict score above 9.0, including scheduled pairs.
- Supply execution uses a disposable origin/main clone, keeps the installed
  checkout untouched, logs preflight errors, checks 10 GiB free space, requires
  ChatGPT login, and validates both a qualified pair and eight remaining ideas.
  Protected records/assets and unexpected files cannot enter the content commit.
  Concurrent remote changes reject the push instead of silently rebasing content.
- Melivra's obsolete writing-tool description is corrected from its official
  Google Play listing. Melivra and Papira are explicitly content eligible with
  Android-only and iOS-only public recommendation constraints, respectively.
  Product source notes and draft scaffolds carry the platform restrictions.
  New social install links additionally require a matching public store snapshot
  with a version; absent, in-review, or unverified platforms use the canonical
  article fallback. Existing posted URLs are preserved unchanged.
- API automation owns Bluesky and Dev.to; X, LinkedIn, and Medium belong to the
  remote browser worker. The publishing workflow no longer supplies or rotates
  X API credentials. This does not change stored credentials.
- Generation joins remote publication history and preserves recorded copies and
  URLs. Legacy profile-only completion records block regeneration/reposting but
  are not promoted to verified posted permalinks. Reconciliation rejects
  conflicting specific URLs and retains existing evidence for identical URLs.
  Hashnode remains excluded; historical records are audit evidence only.

## Operational follow-up, not executed by this repair

1. Review and merge the repair branch only after the local test/review gate.
   Main-branch path triggers include dashboard reconciliation/deployment,
   app-privacy publication, and Dev.to article updates for files touched by this
   repair. Include those effects in the separate operational deployment decision;
   the review-branch push does not trigger these main-only workflows.
2. Update the installed supply runner from the reviewed code without discarding
   personal changes. Merely pushing a branch does not update the task's checkout.
3. Update the existing Mac `onnellab-work-publisher` prompt to the current
   remote-browser contract: select `remote_browser`, exclude Hashnode, read the
   latest state and remote receipt inbox before composing, and append only verified
   permalinks to `data/remote_browser_publications.json`. Preserve its existing
   identity/schedule; do not create a second publisher. Confirm recent execution
   and the ordinary Chrome session without changing authentication or OS security.
4. When an operational supply run is authorized, confirm the existing ChatGPT
   subscription login without exposing credentials, then inspect the new complete
   run log and the resulting supply report. Do not infer success from task state.
5. Check canonical publication and channel-specific post permalinks separately.
   Existing profile-only completion records require evidence reconciliation, not
   automatic reposting. Keep overdue items pending when browser authentication or
   a reliable existing permalink cannot be verified.

At repair time the live topic inventory still has zero ideas and zero qualified
pairs. Code repair alone does not replenish that inventory. Existing Markdown,
topics, manifest receipts, and publication-state files must remain unchanged by
local verification.

## Main integration side effects and approval boundary

Final independent local verification: 725 offline unit tests passed, and the
actual-data pipeline dry-run passed with network access blocked. Topic, app
registry, and foundation validators passed. Git whitespace checks passed;
generated output, topic tables, and publication receipt/state files were unchanged.
The healthy-supply command correctly still fails for zero qualified pairs/ideas.

| Workflow | Trigger relevant to this patch | External write |
| --- | --- | --- |
| `publish-app-privacy-policies.yml` | push to main touching `data/apps_registry.csv` or `scripts/publishing.py` | Builds privacy pages and pushes changes to `onnellab/onnellab.github.io` main: `/privacy/<slug>/`, localized variants, and compatibility paths. |
| `update-devto-article.yml` | push to main touching `scripts/generate_syndication_drafts.py` or `scripts/validate_syndication_drafts.py` | No dry-run guard. Defaults to TOPIC-0001/en, PUTs Dev.to article 4128952, then updates engine state and deploys `/ops/` through homepage main. |
| `reconcile-remote-browser-publications.yml` | push to main touching the reconciler source; also hourly at minute 17 UTC | Reconciles receipts, pushes engine state, and pushes the generated `/ops/` dashboard to homepage main. |
| `publishing.yml` | every push to main is dry-run; daily 00:00 UTC and explicit non-dry workflow dispatch are live | Live runs may publish app releases, canonical articles, and API-owned Bluesky/Dev.to posts. |

The current Dev.to target is
`https://dev.to/onnellab/how-to-read-large-txt-files-without-lag-92n`.
These are configured effects, not proof that any external write occurred during
this repair. Every listed push trigger is main-only.

There is no existing global "merge without any publication" switch. A safe
integration is possible only with a separately authorized read-only integration
window: pause the affected publishing/deployment/update workflows and any other
external writers that pull main, confirm no such jobs are queued/running, merge
the validated branch, and run validation-only checks. Keep operational writers
paused until their resumption/deployment scope is explicitly approved. An
alternative is a separately reviewed fail-closed publish opt-in gate on every
external-write path before integration. `[skip ci]` alone does not control
scheduled or already-running writers and is insufficient.

Required additional approval is for the temporary operational pause/cancellation
and main integration, then separately for deploying the installed supply runner,
updating the existing Mac publisher prompt, and resuming real supply/publication.
No credential, OAuth, or OS-security changes are required by the code repair.
