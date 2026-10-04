# Content pipeline recovery — 2026-10-04

## Scope

The initial repair covered code and local verification. The user subsequently
authorized pausing existing writers, main integration, installed runner and
existing publisher-prompt updates, and verified supply/publication resumption.
No new paid usage or authentication/security changes are authorized.
A passing dry-run is not evidence of public publication.

## Initial observed installation

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

## Original operational follow-up (subsequently authorized)

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

The user subsequently approved that operational sequence. New paid usage,
credential, OAuth, and browser/OS-security changes remain outside that approval.


## Authorized operational execution

- Existing four writer workflows and the Windows 06:00 / Mac 09:00 tasks were
  paused before integrating `9cbc9ab9`, `10ff6925`, and `7e742bc6` into main.
- The installed Windows checkout was fast-forwarded, preserving `.tools` and
  personal files. Shell LF checkout policy fixes the reproduced WSL CRLF error;
  the existing rsvg-convert 2.58.0 is reused without installing system packages.
- The existing ChatGPT subscription supply runner completed successfully:
  `/tmp/onnel-content-supply-runs/20261004-111112-ntJtbN.log`, exit 0.
  Commit `825107c2` adds one English/Korean review pair (both 10.0) and eight ideas.
  Its 78 focused tests and topic/foundation/supply validators passed. These are
  supplied drafts, not evidence of public publication.
- The existing Mac automation keeps its identity and daily 09:00 recurrence.
  Its prompt now uses remote_browser, excludes Hashnode, joins latest receipts,
  preserves legacy duplicate holds, and requires specific verified permalinks.
- Mac file/terminal access works, but Chrome Apple Events JavaScript is disabled
  and this session has no separate interactive browser tool. No browser/security
  setting was changed. Overdue Medium TOPIC-0009 / TOPIC-0012 and LinkedIn
  TOPIC-0015 remain unposted by this recovery until access is available.
- Main `640a71b8` passes workflow lint. Its full unit run exposed a new-content
  distribution validation mismatch: the generator filtered unreleased stores,
  but the validator still required both registry URLs. Both now share verified
  public-store evidence. Tests cover iOS-only, Android-only, and no evidence.
- A broken source URL in both unpublished Papira drafts was replaced with the
  verified official App Store listing. Narrow LF rules for fingerprinted SVG/JSON
  inputs keep Windows and Linux review fingerprints equal; reviews remain 10.0.
- Manual dispatch supports `content_only=true` (default false). Combined with
  `dry_run=false`, it skips store checks, app-release preparation/publication,
  release reports/issues, and app-state staging. Existing cron/dry-run defaults
  are unchanged. CI now also covers new Markdown and its app/store/topic inputs.

The installed LF policy also requires refreshing pre-existing Windows shell
checkouts: the final local suite exposed an unchanged preflight script still
using CRLF. LF normalization changes no committed shell content.

Final pre-publication verification: 733 offline unit tests passed (90.451s);
actual-data offline dry-run passed without network attempts. All 494 protected
generated/topic files had identical before/after SHA256 values. Supply gate
confirms one qualified bilingual pair and eight ideas. Independent review found
no blocking issues.


## Verified publication and scheduler restoration

- `1e200556` passed all three remote unit-test matrix jobs (Ubuntu Python 3.12 /
  3.14, macOS Python 3.14) and workflow lint.
- Existing Windows supply task is enabled/Ready, next run 2026-10-05 06:00 KST.
  Its historical Task Scheduler result still refers to the old failed 06:00 run;
  the repaired runner was manually verified separately. A second installed-runner
  check exited 0 with healthy supply and no Codex usage.
- Existing Mac automation is ACTIVE with the corrected prompt and unchanged
  daily 09:00 recurrence. Browser posting remains blocked by unavailable
  interactive tools/disabled Apple Events JavaScript; security settings unchanged.
- Authorized content-only run `37171453259` succeeded. All five live app-release
  steps were skipped. TOPIC-0033/0034 became published at
  2026-10-04T11:34:40+09:00 (`0ad404ae`); status report commit is `83944bd5`.
- Both public URLs returned HTTP 200 with the correct title, Papira body, and
  official iOS link: `/blog/en/prepare-txt-manuscript-for-epub/` and
  `/blog/ko/prepare-txt-manuscript-for-epub/` on https://onnellab.com.
- This run posted zero Bluesky and zero Dev.to items; no new remote-browser
  publications were verified. Manual state and remote receipt inbox are unchanged.
  Every previously populated manifest posted_url is preserved.
- Due browser backlog after receipt join: X TOPIC-0033; LinkedIn TOPIC-0015;
  Medium TOPIC-0009 and TOPIC-0012. Eleven other remote-browser items remain future.
  Existing X dates October 6/10/14 are preserved. Hashnode remains excluded.
- The published pair consumes the current ready buffer; eight ideas remain and
  the resumed daily supplier will replenish it. This is not a failed supply run.
- Homepage deployment succeeded, but its separate localization check found an
  old Korean article image_specs value overwritten by stale engine metadata.
  The follow-up restores the prior Korean metadata and validates localization
  before any future homepage push; article body and canonical URL are unchanged.


## Final outcome

The final code change is `31f20116`. Its remote unit matrix passed; the additional
homepage guard has 60 focused passing tests. Follow-up content-only deployment
`37171941733` published zero new articles and zero API channel posts. The homepage
localization preflight passed for 239 source files, deployment succeeded, and the
separate nine-language regression workflow `37171984156` passed. Homepage content
commit: `cfbeefe0c555df300ff032ca6b3108899299b7e9`.

All four temporarily paused GitHub workflows are active again. Receipt/dashboard
run `37172104024` succeeded (`007a3caa` dashboard snapshot). Both existing daily
schedulers are restored; no extra schedule was created. Hashnode was neither
regenerated nor posted. No paid API model, credential, OAuth, or security setting
was changed. The remaining operational blocker is interactive browser access for
the four due X/LinkedIn/Medium items listed above. Existing Mac Chrome JavaScript
from Apple Events is disabled, and this session has no independent interactive
browser tool; an authorized browser connection or explicit approval of that
browser permission is needed before those posts can be executed and verified.
