# ONNELLAB Ops — encrypted dashboard and private store sales

The Ops routes are published to GitHub Pages as **ciphertext HTML**. Every HTML
page uses AES-256-GCM with a 600,000-iteration PBKDF2-derived key; the shared
password lives only in the Actions secret `ONNELLAB_OPS_PASSWORD` and in the
owner's password manager. A login form decrypts within the visitor's browser.
This is **not server-side authentication**: URLs, assets, and ciphertext remain
public. Use a server-side access-control provider if URL-level access denial,
per-user accounts or revocable sessions become requirements.

All direct Ops writers must invoke `node scripts/private_ops_publish.mjs
seal-site ...` and validate the sealed HTML; no workflow may copy plaintext
`generated/manual-publish/*.html` into the public homepage. The generator
directory is excluded from Git. Historic public revisions are not erased by
this migration. Before enabling the new pipeline, retire old service worker
caches and validate the live site only serves ciphertext.

## Finance

Scheduled `sync-store-sales.yml` uses existing store report credentials and
writes only `data/private_store_sales.enc.json` to the public repo. The
decrypted JSON is transient CI workspace material. Never commit transaction
IDs, purchaser details, plaintext sales summaries or raw vendor reports.
Public dashboard HTML contains no raw finance values.

Google Play:
- `sales/salesreport_YYYYMM.zip` estimated sales, charged amount in buyer
  sale currency; month current-to-date if source has posted it
- `earnings/earnings_YYYYMM.zip` and
  `earnings/earnings_YYYYMM_<account-identifier>.zip` actual Google fee,
  usually posted after the reporting month; fee refunds must reverse expense.
  The collector reports unmatched ZIP filenames as counts, without exposing
  account identifiers.
- Original foreign currencies are not directly summed. Dated ECB KRW reference estimates are shown separately, alongside original-currency breakdowns.

Apple:
- `GET /v1/salesReports`, Team API key and `APP_STORE_VENDOR_NUMBER`
  Actions secret required; set Vendor Number from App Store Connect
  Payments and Financial Reports.
- Finance reporting uses dedicated `APP_STORE_FINANCE_KEY_ID`,
  `APP_STORE_FINANCE_ISSUER_ID`, and
  `APP_STORE_FINANCE_PRIVATE_KEY_BASE64` Actions secrets (base64 of the
  downloaded .p8 private key). Create a Team key with **Finance** role under
  App Store Connect > Users and Access > Integrations > Team Keys.
  Do not overwrite `APP_STORE_CONNECT_*` secrets used by app release.
  If a Team key returns HTTP 401 even on `GET /v1/apps?limit=1`, check
  that Key ID, Issuer ID, and .p8 belong to the same active Team key.
- Sales reports show customer prices and proceeds. Their difference cannot
  be claimed as platform fees because of tax/currency variations.
- Daily Apple sales are backfilled from 2026-03-01 (subject to Apple's
  one-year availability). Apple IAP product identifiers can differ from the
  public app ID; the collector maps via exact App Store Connect app SKU,
  parent identifier, or public app identifier. The daily parser mapping has
  its own versioned checkpoint: after a mapping upgrade, previously checked
  historical dates are fully re-read once, and their prior rows are replaced
  rather than added. Fetched and unavailable day checkpoints are encrypted;
  after reconciliation the last 14 days are refreshed daily.
  Unknown seller/product IDs stay unmatched, never guessed by product name.
- `GET /v1/financeReports` with `reportType=FINANCIAL`,
  `regionCode=ZZ`, fiscal-month `YYYY-MM` reads consolidated settled
  proceeds. Older confirmed fiscal months are checkpointed; the last two
  fiscal months are rechecked for corrections.
- **Do not infer Apple's commission** from customer price and proceeds:
  applicable taxes are included in that difference. Verified Korean Apple
  commission e-Tax Invoices/Cash Receipts are currently downloaded manually
  under App Store Connect > Reports > Create Reports > Tax Statements;
  no documented Tax Statements download endpoint is connected.
- The grant-specific CSV exports only Google earnings fee transactions with
  confirmed non-KR buyer countries. Fee refunds remain negative. Original
  currencies and estimated KRW equivalents are exported in different columns;
  the report is not a substitute for official vendor invoices or acceptance
  by the grant administrator.

## Date ranges and KRW reference totals

The sealed `/ops/sales/` page supports month, year, custom inclusive dates,
and all-time sales from 2026-01-01 through today's KST calendar date. All
store/country/app filters apply to each selection, the original-currency
breakdown, and CSV exports. The primary net sales figure is
`customer gross + refunds`; it is NOT a bank settlement amount or business
profit. Google fee expense is displayed separately and never double-subtracted.
Apple fiscal-month settlements are displayed separately and never added again
to daily sales totals.

`store_fx_rates.py` uses the official ECB historic reference series
`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml` as its
primary conversion source. If a currency is not quoted by the ECB (e.g.
SAR or UAH), it retrieves that date's official rates from the
National Bank of Ukraine (NBU) open-data endpoint
`https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange`.
NBU rates are hryvnia-per-unit, so KRW-per-unit is derived as
`UAH per source currency / UAH per KRW`. NBU does not publish CLP;
the National Bank of Poland (NBP) official table A publishes both CLP
and KRW in PLN-per-unit, enabling `PLN per CLP / PLN per KRW` with a
common published reference date (at most 7 calendar days old):
`https://api.nbp.pl/api/exchangerates/tables/a/`.
NBU/NBP fallbacks are each bounded to 30 distinct dates per sync and
cached by day. Every money field retains FX source and effective date.
ECB conversions use the transaction date or most recent preceding rate within
7 calendar days; NBU uses the official dated observation.

The code rounds each report-row gross and refund to won and computes the
net as their sum. Google confirmed fees convert only when confirmed by the
Earnings source. Original foreign-currency figures and each FX source/date
remain attached to the output.
For Apple fiscal-month proceeds, the month-end reference rate is a clearly
labeled estimate, NOT Apple's actual bank settlement exchange rate.

All source amounts/currencies, conversion rates and quote dates are retained.
The full FX-enriched ledger remains encrypted, not publicly committed in
plaintext. Unconvertible currencies are labeled `미환산` and **excluded from
partial KRW sums**, which explicitly disclose missing rows. Temporary ECB
outages may use exact-date prior encrypted rate cache; they must not fabricate
or silently assume FX quotes.

The source status explicitly shows missing credentials/financial reports and
never silently treats missing reports as zero sales.

Before updating deployment workflows, add `ONNELLAB_OPS_PASSWORD` as a
strong random (minimum 24-character) repository secret. Keep it out of Git,
issue comments, CI logs, public HTML, analytics and support screenshots.
