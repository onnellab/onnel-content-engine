# Four-week marketing measurement

This is an offline ledger, not a publisher or scheduler. It reads existing social
and syndication manifests, joins exact publication identities with manual and
remote-browser receipts, and reports a 28-day window. It does not change published
copy, links, accounts, schedules, credentials, or analytics settings. Hashnode and unselected social variants are excluded. Medium is user-excluded
from new distribution and unpublished demand; existing Medium publication
receipts remain visible as historical measurements. Existing YouTube publication records may
be supplied explicitly in `extra_publications`; the tool does not access a private
video queue automatically.

All released, content-eligible apps start with weight 1. Public store platforms are
reported from matching store evidence, so Melivra is Android only and Papira is iOS
only. These weights are an experiment baseline, not a change to publication
cadence or a claim that every app has runnable video footage.

## Run a bounded report

```powershell
python scripts/marketing_measurement.py report --start 2026-10-04T00:00:00+09:00 --as-of 2026-10-11T00:00:00+09:00
```

Output is JSON on stdout. Save it to an explicitly chosen private local path if
needed. Both timestamps require time zones. The window ends exclusively 28 days
after the start. `as_of` limits the observed portion; it does not reconstruct a
historical snapshot. The four weekly buckets contain days 0-6, 7-13, 14-20, 21-27.
Records outside the observed portion remain visible with `week: null`.

Each record retains its material/topic, app IDs, channel, exact `manual_key`,
recorded URL, due time, and publication evidence. A receipt overrides an old API
failure for duplicate prevention, while `historical_error_present`, `error_type`,
`last_attempt_at`, and `retry_count_snapshot` remain separate. Retry counts are
current lifetime snapshots, **not** attempts made in each week. An old profile URL
can block reposting without becoming a specific post permalink.
`publication_permalink_recorded` checks the URL shape and recorded evidence; it is
not a new live URL verification. Identical duplicate inputs are counted once;
conflicting duplicates stop the report. No historical receipts are rewritten.

## Metrics and attribution

Missing metrics remain `null`, including suppressed or unavailable export data.
An explicitly observed zero remains zero. The manifest's default zero counters
are not imported as analytics observations. Publication count is not reach,
conversion, purchase count, or revenue.

`data/marketing_measurement.json` contains empty `metric_samples` initially.
Samples are explicit aggregate exports with exactly these fields:

```json
{
  "sample_id": "export-row-1",
  "manual_key": "TOPIC-0033::x::en::x",
  "app_id": "APP-0008",
  "source": "app_store_connect_export",
  "period_start": "2026-10-04T00:00:00+09:00",
  "period_end": "2026-10-11T00:00:00+09:00",
  "dimensions": {"store_platform": "ios", "campaign": "example-only"},
  "metrics": {"unique_impressions": null, "total_downloads": null, "preorders": null},
  "evidence_path": "an-explicit-private-aggregate-export.csv",
  "evidence_sha256": "replace-with-the-real-64-character-sha256"
}
```

This example is not a valid observation until backed by a real export and a
matching campaign on the recorded publication's destination URL. Never copy an
app-wide store total onto each post. Shared campaign tokens cannot establish
attribution to a different app on a multi-app article: the destination's App Store
ID or Play package must match that app's registry store identity. Shared campaigns across posts cannot establish
material-level attribution and are rejected; keep such totals in their original
store-level export. File hashes bind the provided evidence but do not independently
verify a manually transcribed value. Compare its campaign, app, period, filters,
and metric definition before importing. Do not include personal identifiers.
Overlapping samples for the same dimensions are rejected rather than summed.
Unique-user metrics across periods or dimensions must not be casually added.

Supported sources and definitions, checked against official documentation on
2026-10-04:

| Source | Counts accepted | Derived rate |
| --- | --- | --- |
| `channel_export` | `impressions`, `link_clicks` | link clicks / impressions |
| `google_play_export` | `listing_visitors`, `listing_button_click_users`, `listing_acquisitions` | listing button-click users / listing visitors |
| `app_store_connect_export` | `unique_impressions`, `unique_product_page_views`, `total_downloads`, `preorders`, `first_time_downloads` | (total downloads + pre-orders) / unique impressions |

Google Play's current listing report measures button clicks and CTR. Clicking
Install, Open, or Pre-register does not establish an installation. Acquisitions
are a separate Statistics/export metric and are not inferred from CTR. Use the
export's combined unique click count; do not sum overlapping button-user counts.
UTM source and campaign are supported listing dimensions. See [Google Play's
official listing metrics](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en).

Apple's conversion denominator is unique device **impressions**, not product page
views. Total downloads includes first-time downloads and redownloads. A pre-order
counts when placed and must not count again when fulfilled. Supply an explicit
pre-order count, including zero when known; otherwise the derived rate stays
unknown. See [Apple's metric definitions](https://developer.apple.com/help/app-store-connect-analytics/reference/metrics-definitions).

## Proposed tracking links

The command returns a proposed URL only. It never edits old posts, retrofits old
attribution, or changes a published URL. Use a non-personal campaign identifier
unique to app/material/channel/window (`campaign_token` provides a deterministic
27-character token). Changes to live distribution remain a separate operation.

```powershell
python scripts/marketing_measurement.py tracking-link --store google_play --url 'https://play.google.com/store/apps/details?id=com.onnellab.melivra' --channel x --campaign 'melivra-local-x-w1'
```

For Play Console listing segmentation this adds top-level `utm_source` and
`utm_campaign`, as documented in the listing dimensions above. It does **not**
implement the Android Install Referrer API or claim device-level install
attribution. Existing `referrer` or campaign parameters are rejected, not replaced.

Apple links use `pt` (provider), `ct` (campaign), and `mt=8`. The provider token must
come from an existing App Store Connect campaign link; the tool requires it and
never invents one. Campaign generation in App Store Connect requires existing
analytics data. Campaign visibility can be delayed or withheld by thresholds;
missing rows do not imply zero. Apple's documented first-download campaign window
is 24 hours, with the most recent link receiving attribution when several were
clicked. See [Apple's campaign-link documentation](https://developer.apple.com/help/app-store-connect-analytics/acquisition/campaign-links).

## Decide what to test next

Keep the baseline equal until comparable observations exist. Record a hypothesis
for one material change, preserve channel/time/locale/store filters, and compare
like-for-like periods. Missing attribution suggests a measurement experiment, not
more spend or an app ranking. Small samples and hidden metrics support no winner
claim. This module proposes collecting comparable exports and leaves every
`weight_change` null; it never changes weights automatically.

The user's report of 13 TagWeaver purchases is retained only as an unverified
note. Channel attribution and settlement are unknown. It is not entered into
conversion metrics or used to increase TagWeaver's baseline allocation.
