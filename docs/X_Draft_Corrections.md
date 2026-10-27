# One-item X draft corrections

`scripts/regenerate_x_draft.py` derives one English primary X draft from a
reviewed JSON source in `data/x_draft_corrections/`. It does not post, approve,
schedule, generate article/card assets, or change other channels.

The source binds the exact published article, canonical URL, manual key, old
draft bytes and digest, and a complete replacement opening. The old CTA and
store URL tail remain byte-identical. Only the selected text and its manifest
`weighted_length` change. All other manifest fields and draft files remain
unchanged. Existing approvals are not copied onto changed text: approved,
posted, or receipt-backed items are rejected rather than reset.

Run without `--write` first, then use the same source with `--write` after
review. The output includes the draft digest (with terminal LF) and prospective
submitted-body digest (without one terminal LF). These are not posting receipts.

```text
python3 scripts/regenerate_x_draft.py data/x_draft_corrections/TOPIC-0039.json
python3 scripts/regenerate_x_draft.py data/x_draft_corrections/TOPIC-0039.json --write
```

The selected draft must already exist, be unapproved/unposted, and have a
published canonical source. Both publication history inputs are mandatory.
Duplicate identities, changed source bytes, symlinks, malformed JSON and
overlong/incomplete openings fail closed. Staging preserves the prior social
tree and rolls back if the final directory replacement fails. The existing
social-generation lock is shared; cross-computer writers still require Git
compare-and-swap and a fresh main read.

The general generator and its fallback hook are deliberately unchanged. It can
regenerate the old unposted copy before publication. Therefore the browser
publisher must re-read main's exact draft and current publication records
immediately before posting; a digest mismatch stops the post. Reapply the
reviewed correction only while its bound inputs and history are still valid.
After publication, the existing receipt-backed historical preservation applies.
This is a narrow correction path, not a global claim that every English hook
has been fixed.

Never manually edit generated drafts or forge approvals/publication hashes.
Never use the observation-only recovery schema to disguise newly submitted
bytes. Record the actual author, URL/ID, submitted bytes and observation time
only after the approved browser UI publication is verified. Keep server posting
time separate when unavailable.

No changes to `publishing.py` or privacy workflows are needed. Publishing that
module itself would trigger unrelated privacy-page automation and is outside
this correction scope.
