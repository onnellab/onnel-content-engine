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

## 4. Initial content pilot (not activated)

- Editorial language: English.
- Planned ceiling: at most one separately reviewed educational guide per week.
- Suggested topics: practical workflows for offline music, metadata, TXT/EPUB, file management, and audio/video utilities.
- Gate: research → article → meaningful visuals → factual review → draft → explicit publication readiness check.
- No automatic back-catalog migration. Do not trigger Google Blogger API posts just because a canonical ONNELLAB article was released.
- A guide must have added value, real references where needed, correctly functioning links and images, and no misleading claims.
- Any AdSense-eligible editorial plan is not an assurance of AdSense approval, search rankings, or revenue.

## 5. Conditions before automated Blogger publishing can be enabled

All conditions below must be met, documented and independently verified:

- [ ] Dedicated Blogger API adapter implemented using Google's official OAuth 2.0 permission flow under the confirmed ONNELLAB Google account; consent is completed by the account owner as needed.
- [ ] Least-privilege credentials and refresh tokens stored only in approved secret storage, never Git or generated website pages.
- [ ] Target Blog ID is the verified `1829676614817439337`; no account mixing with other signed-in Google profiles.
- [ ] Separate posting state manifest/ledger records source article ID, language, draft ID, public Blogger post ID, permalink, and timing.
- [ ] Strict idempotency: retry never creates duplicate posts; an update targets a confirmed draft.
- [ ] Draft-first workflow, quality gate, and no public publishing from unreviewed content.
- [ ] Publish only after verifying the final actual Blogger public URL and content. If unavailable, keep pending and do not claim success.
- [ ] Tests cover OAuth denial/expiry, malformed content, duplicate retries, missing asset/canonical and incorrect account/blog ID.
- [ ] Channel failure does not alter ONNELLAB canonical site or other distribution pipelines.
- [ ] Rollback/recovery documented. No bulk publish on first connection.

No user password, cookie, recovery code or secret should be requested in chat or committed to a repository.

## 6. Search and advertising steps (not completed)

- [ ] Verify Blogger site ownership in Google Search Console under the intended account and review actual indexing data.
- [ ] Publish a sufficient body of original, helpful articles and assess site navigation, quality, and policy compliance before any AdSense application.
- [ ] Review privacy/cookie notices and consent settings when analytics, advertising, or new trackers are introduced.
- [ ] Apply to AdSense only through its genuine account/site workflow; preserve actual publisher ID/ads.txt only after provided by Google and verified.
- [ ] Integrate performance measurements into the ONNELLAB dashboard only from authenticated and real data sources.

## 7. Safety notes

The platform's built-in cookie notice must actually function for eligible visitors. The privacy statement documents the launch-day state; update it if analytics, ad tech, or data processing changes. Do not claim that posting every week guarantees SEO/AdSense outcomes. Keep the blog address on Blogspot until a separately verified custom domain/DNS change is intentionally made.

### Verification record

- Blog title, account and ID: verified from authenticated Blogger management UI.
- English/Seoul/search/HTTPS/comment settings: verified in Blogger settings UI.
- About/Contact/Privacy: created and checked on their exact public URLs.
- Essential Light, navigation menu and hidden profile: verified on the live Blogger homepage.
- General posts: 0 at launch; account advertising connection: not configured.
