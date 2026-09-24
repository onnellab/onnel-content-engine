# Store pricing synchronization

## Purpose

`scripts/sync_store_pricing.py` records current customer-facing prices for
ONNELLAB apps and store products in `data/store_pricing_snapshot.json`.
The snapshot is operational dashboard data, never a credential store.

The production territory is South Korea (`KR`; Apple territory `KOR`).
A live value is shown as verified only when the collector observed that value
from the relevant store source during the current synchronization.

## Sources

Paid app downloads use public store surfaces:
- Apple iTunes Search/Lookup API with `country=kr`.
- The Google Play public product page with `hl=ko&gl=KR`.

Apple in-app purchases use App Store Connect API with the existing
profile credentials already configured for store review operations. The worker
lists the app's IAPs, reads each price schedule, and resolves the currently
effective Korean customer price from manual and automatic schedule records.

Google managed in-app products use the Google Play Developer API
`inappproducts` resource. Auto-renewing subscriptions use the monetization
subscriptions resource and the Korean regional base-plan price.

## Safety and fallback

The collector reuses the existing App Store Connect and Google Play
service-account credential helpers. Tokens, private keys, service-account JSON,
and authorization headers are never written to the snapshot or dashboard.

Each store gets an explicit state. A failed or unavailable source never becomes
a zero price and never overwrites a verified price with an invented value.
Not-released and in-review apps remain explicitly marked as such.

`data/app_pricing.csv` remains the product mapping and manual fallback.
The dashboard replaces a manual row only when a live result can be matched
unambiguously to the same product. Ambiguous matches remain manual-only.
Live App Store and Google Play prices are rendered as platform-specific rows.

A partial price refresh does not block unrelated review, status, YouTube, or
dashboard refreshes. Its incomplete source state remains visible in the durable
snapshot for the daily operations report.

## Scheduled operation

The existing `sync-store-reviews.yml` workflow runs the pricing collector
with the same encrypted Actions secrets after authenticated review collection.
It runs the focused pricing tests first, commits the safe pricing snapshot with
the other operational state, rebuilds `/ops/`, and deploys the result.

Manual diagnostic run:

    python3 -B scripts/sync_store_pricing.py

Without configured store credentials this can still inspect public paid-download
prices, while IAP/subscription coverage is reported as partial rather than
misrepresented as current.
