# Review response policy

Every public reply requires a human approval. The system may draft and classify
but may not publish, create a pull request, merge code, or deploy a release.

Never claim an unverified cause, a future release date, a refund outcome, or a
bug fix. Do not request personal data, order numbers, account identifiers, or
document contents in a public reply.

Reviews concerning payment, refunds, privacy, security, legal matters, data
loss, or ratings of one to three stars always require manual approval.



## Notify-first supersession, 2026-10-14

The former 2026-09-24 standing scheduled reply authorization is revoked. Fetch
and classify reviews as before, but first notify the owner in their existing
assistant chat. No scheduled writer may publish any reply. A new explicit
per-review owner approval must name the exact reply and target and retain the
verified owner-message reference and content binding. Generated drafts, old
queued/failed records, notification delivery receipts, and old standing-policy
records are not approval. Preserve published history; never retroactively send
pending drafts or automatically retry a failed/uncertain public write.

## Owner correction of an already-published reply, 2026-10-24

An already-posted developer reply is **not** a new pending text review.
The explicit per-review owner-chat approval requirement above remains
unchanged for **new replies**. Editing an existing Google Play reply
requires a separate, authenticated **manual owner** confirmation in the
existing publisher workflow: GitHub actor and triggering actor must both
be `onnellab`, event must be `workflow_dispatch`, and the owner must
supply an exact registered `revision-...` ID with `REPLACE`. The proposed
record is not itself approval; a scheduled worker, status report, other
GitHub actor, or workflow rerun may not create a new posting attempt.

Before any API mutation, the canonical publisher must observe the real
Google Play review ID and match the original review body, rating, version
and the existing developer reply exactly, using a fresh public-version
snapshot. A changed source or currently unverified outcome fails closed.
The original reply may be replaced no more than once for that revision
ID. Only an exact subsequent Google Play `reviews.get` observation may
yield `store_verified`. A prior uncertain attempt may be checked again
by the owner but never posted again. This is not an exemption to
credential isolation, the 350-character limit, or all other review
safety rules; no scheduled task may initiate or retry the change.

