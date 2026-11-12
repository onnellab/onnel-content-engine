# ONNELLAB Google Blogger Channel — Operational Runbook

## 1. Verified channel identity (2026-11-12)

| Field | Verified value |
| --- | --- |
| Channel | ONNELLAB Guides |
| Platform | Google Blogger / Blogspot |
| Google account owner | `onnellab.app@gmail.com` (Blogger account verified in Google Chrome) |
| Blog ID | `1829676614817439337` |
| Public URL | `https://onnellab-guides.blogspot.com/` |
| Display name | `ONNELLAB` |
| Language | English (`en`) |
| Time zone | `Asia/Seoul` |
| Theme | Essential Light |
| Publishing status | Blog created; no general articles published |
| Automatic posting status | **DISABLED / NOT CONNECTED** |
| AdSense | **NOT ENABLED / NO APPROVAL CLAIM** |
| Google Analytics measurement ID | Not configured at initialization |
| Custom domain | Not configured; uses the verified Blogspot URL |

This file records the verified Blogger destination, **not** OAuth credentials, API access, Search Console ownership, or an AdSense account.

## 2. Live foundation pages

The following pages were created in Blogger under the ONNELLAB Google account, published, and their actual public page content was checked:

- [About](https://onnellab-guides.blogspot.com/p/about.html)
- [Contact](https://onnellab-guides.blogspot.com/p/contact.html)
- [Privacy Policy](https://onnellab-guides.blogspot.com/p/privacy-policy.html)

The primary navigation menu shows `HOME · ABOUT · CONTACT · PRIVACY POLICY`. The separate profile/sidebar gadget is hidden.

Public discovery and HTTPS redirection were observed enabled in Blogger settings. Search meta description was enabled and set. Comment moderation was set to always review. No advertising credentials, fake ads.txt entries, or fabricated analytics IDs were entered.

### Blog description

> Practical, clear guides from ONNELLAB on offline music, digital files, reading, media, and creative workflows. Learn the essentials and solve real problems.

### Search description

> Practical ONNELLAB guides to offline music, file organization, digital reading, media tools, and creative workflows. Clear steps, useful answers.

## 3. Role within ONNELLAB

1. `https://onnellab.com/` remains the official primary website and canonical destination of its own nine-language articles.
2. Blogger is a **secondary English-language educational channel** and an optional future AdSense experiment; it does not replace the official site.
3. An independent Blogger piece must answer a distinct search intent and contain original practical detail; it can link to relevant ONNELLAB material without making the guide depend on products.
4. If a substantially identical article is syndicated, identify its original ONNELLAB canonical article visibly and by the appropriate canonical metadata; do not present duplicate material as independent content.
5. Do not change the official site publishing frequency, original publication dates, or existing X/LinkedIn/Bluesky/Dev.to adapters.

Policy and quality gates are defined in `docs/Publishing_Guide.md` and `docs/GitHub_Actions.md`. They take priority over this status record.

## 4. Independent English editorial automation

- The owner approved **separate automatic English Blogger publication** on 2026-11-12, without requiring approval for each individual article when objective gates pass.
- A dedicated ChatGPT task runs **Mondays, Wednesdays and Fridays at 10:00 Asia/Seoul**, starting 2026-11-13. The task researches, drafts, validates, posts, and verifies Blogger articles. It is separate from the canonical site GitHub Actions workflow; **no Blogger step is added to that existing workflow**.
- Editorial language: English. Maximum: **three independently useful guides per KST ISO week, at most one per KST calendar date**, not an unconditional obligation to fill every slot.
- Suggested topics: practical workflows for offline music, metadata, TXT/EPUB, file management, and audio/video utilities.
- Gate: research → distinctly scoped English article → fact/links/rights review → `blogger_weekly.py check` → unique KST publication-date reservation + Git commit/push → draft through authenticated Blogger UI → record remote draft ID + Git commit/push → publish through verified ONNELLAB Blogger UI → independent public URL/content verification → record receipt + Git commit/push.
- The official Blogger web interface in a previously authenticated account is the initial posting transport. A future Blogger API/OAuth adapter is optional; never read cookies or browser tokens. A scheduled run must verify the signed-in account is `onnellab.app@gmail.com` and the actual Blog ID is `1829676614817439337` before any posting. If that cannot be established, stop; retain the work and report the blocker.
- An article may go live automatically only after the account/target verification, content originality, safety, and public-draft preview gates pass. The first real post is also an end-to-end transport acceptance test; no publication may be marked complete until its public body is verified. Do not publish solely to satisfy the schedule.
- No automatic back-catalog migration. Never change the canonical article release history or alter X/LinkedIn/Bluesky/Dev.to.
- Publishing is suspended for the affected slot if there is an uncertain duplicate, lost authentication, missing reference evidence, or an existing reserved draft whose remote state cannot be reconciled. Existing incomplete slots must be reconciled before proceeding to the next scheduled slot; never publish duplicates.
- AdSense approval, search visibility, or revenue are not assumed.

## 5. Activation and safety checklist

- [x] Created real Blogger channel and verified account identity, public blog ID, HTTPS URL, and essential pages.
- [x] Created a separate three-times-weekly agent schedule independent of the GitHub Actions canonical publishing workflow.
- [x] Implemented `scripts/blogger_weekly.py` with English-only quality checks, source-url requirements, substantial article length, reference/rights review attestations, exact-passage overlap rejection, duplicate KST date-slot/slug prevention and three-per-week cap, guarded state transitions, and public receipt verification.
- [x] Added offline regression tests in `tests/test_blogger_weekly.py`.
- [ ] First scheduled run: verify a real article draft, the authenticated browser account and Blog ID, preview, live-publication sequence, and exact public article content. This cannot be claimed complete until actually observed.
- [ ] Optional future API route: implement dedicated Blogger OAuth consent and secret storage, test refresh/scopes/account identity, and never borrow an unrelated Google account's YouTube token.

### Draft metadata contract

Create `drafts/blogger/en/<slug>.html` and `drafts/blogger/en/<slug>.json`. Keep them separate from `generated/markdown` and existing syndication drafts. The JSON includes `week` (current Asia/Seoul ISO week such as `2026-W46`), `slot` (the intended KST publication date as `YYYY-MM-DD`; retain this exact date for retries), `slug`, `language: en`, `title`, `primary_question`, `source_title`, `source_url` (HTTPS official ONNELLAB article), `source_path` (a real `generated/markdown/en/...` file), `body_path`, `fact_sources` (two or more factual citations each with `url` and specific `supports`), `new_examples` (two or more substantial new examples), and `review` with the following truthfully checked booleans: `technically_verified`, `distinct_search_intent`, `original_examples`, `sources_checked`, `links_checked`, `rights_checked`, `english_proofread`.

The HTML must be an independent, useful English guide (minimum 650 words), with at least three substantive H2 sections, six paragraphs, a list or steps, a clearly attributed link to its ONNELLAB source, and hyperlinks to the research references. Only basic safe HTML with absolute HTTPS links is accepted. This is **not** an excuse to pad length or pass checks without real editorial work.

### Run commands

```bash
python3 scripts/blogger_weekly.py status
python3 scripts/blogger_weekly.py check --brief drafts/blogger/en/<slug>.json
python3 scripts/blogger_weekly.py reserve --brief drafts/blogger/en/<slug>.json
# Commit and push the brief, HTML and reserved data/blogger_publications.json BEFORE remote UI work.
# Verify authenticated ONNELLAB account; create ONE Blogger draft and record its real numeric post ID.
python3 scripts/blogger_weekly.py record-draft --brief drafts/blogger/en/<slug>.json --post-id <real-numeric-Blogger-post-ID>
# Commit/push the draft receipt; publish the SAME draft if all checks pass.
python3 scripts/blogger_weekly.py record-published --brief drafts/blogger/en/<slug>.json --post-id <same-post-ID> --url https://onnellab-guides.blogspot.com/<actual-article-permalink>.html
# Commit/push verified receipt ONLY after remote HTTP and content checks pass.
```

`data/blogger_publications.json` is a separate checked-in operational ledger, created by the first successful reservation. Do not create it by guessing post IDs. If a run is interrupted after a particular KST date-slot reservation or draft creation, inspect the actual Blogger administration screen before resuming; **never** create a second remote post to overcome an uncertain state.

There is no personal per-article approval step; the user approved automatic operation subject to the documented gates. The browser route is allowed only through Google's real Blogger UI, with each run checking the signed-in ONNELLAB account and blog identity. Never inspect, copy, or commit Chrome cookies, tokens, passwords, passkeys, or recovery information.

## 6. Search and advertising steps (not completed)

- [ ] Verify Blogger site ownership in Google Search Console under the intended account and review actual indexing data.
- [ ] Publish a sufficient body of original, helpful articles and assess site navigation, quality, and policy compliance before any AdSense application.
- [ ] Review privacy/cookie notices and consent settings when analytics, advertising, or new trackers are introduced.
- [ ] Apply to AdSense only through its genuine account/site workflow; preserve actual publisher ID/ads.txt only after provided by Google and verified.
- [ ] Integrate performance measurements into the ONNELLAB dashboard only from authenticated and real data sources.

## 7. Safety notes

The platform's built-in cookie notice must actually function for eligible visitors. The privacy statement documents the launch-day state; update it if analytics, ad tech, or data processing changes. Do not claim that frequent posting guarantees SEO/AdSense outcomes. Keep the blog address on Blogspot until a separately verified custom domain/DNS change is intentionally made.

### Verification record

- Blog title, account and ID: verified from authenticated Blogger management UI.
- English/Seoul/search/HTTPS/comment settings: verified in Blogger settings UI.
- About/Contact/Privacy: created and checked on their exact public URLs.
- Essential Light, navigation menu and hidden profile: verified on the live Blogger homepage.
- General posts: 0 at launch; account advertising connection: not configured.
