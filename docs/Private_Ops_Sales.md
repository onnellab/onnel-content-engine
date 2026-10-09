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
- `earnings/earnings_YYYYMM.zip` actual Google fee, usually posted after the
  reporting month; fee refunds must reverse fee expense
- Distinct currencies **never** sum together.

Apple:
- `GET /v1/salesReports`, Team API key and `APP_STORE_VENDOR_NUMBER`
  Actions secret required; set Vendor Number from App Store Connect
  Payments and Financial Reports.
- Sales reports show customer prices and proceeds. Their difference cannot
  be claimed as platform fees because of tax/currency variations.
- Initially the Apple API collection only backfills a bounded lookback.

The source status explicitly shows missing credentials/financial reports and
never silently treats missing reports as zero sales.

Before updating deployment workflows, add `ONNELLAB_OPS_PASSWORD` as a
strong random (minimum 24-character) repository secret. Keep it out of Git,
issue comments, CI logs, public HTML, analytics and support screenshots.
