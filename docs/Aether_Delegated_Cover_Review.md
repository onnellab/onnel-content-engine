# Separately attributed delegated single-cover review

This is evidence support, not automatic image approval. The authorized operator
must first inspect the real finished artwork and verify separate commercial-use
rights. Never generate a passing record from filenames, tests, a provider name,
or the presence of an image. Tests use synthetic fixtures only.

Historical entries without `quality_basis` retain their existing owner-attested
behavior and policy hashes. A new entry may explicitly use
`quality_basis=dot_delegated_visual_v1` only for `kind=finished_cover`. Existing
`commercial_use_confirmed=true` and `quality_accepted=true` gates still apply;
false or missing flags remain blockers. Do not rewrite an owner's rejection.

Add `quality_review` containing a safe asset-root-relative JSON `path` and its
actual lowercase SHA-256. The separate record is limited to 64 KiB and requires:

- `schema_version: 1`, `kind: aether_cover_quality_review`, `profile: aether_inn`;
- the exact `title` and `source_sha256` of the reviewed finished source;
- `reviewer_kind: dot_delegated`, `verdict: accepted`;
- a bounded `authority_reference` to the verified user delegation, and an actual
  timezone-aware, non-future `reviewed_at` timestamp;
- nonempty factual `notes`, at most 4000 characters;
- `checks`, each explicitly true: `full_resolution`, `thumbnail_scale`,
  `song_scene_fit`, `geometry_materials`, `full_bleed`, `exact_title`,
  `legibility`, and `no_watermark_or_duplicate_brand`.

The reference documents the source of authority; it does not authenticate a user
message online. The private ledger is an authorized input, not a public approval
endpoint. Rejected or inconclusive reviews must not be converted to accepted.
Unbranded delegated backgrounds are deliberately unsupported: they would still
need a distinct review after typography is added. Review that finished image
instead. The renderer's final dimensions, hash and full-bleed checks remain.

The importer reports `dot_reviewed_existing_cover`, separately attributed
quality metadata, and the exact review hash. New delegated jobs use policy
version 4. Historical owner-approved jobs keep version 3 and their original
approval bytes and upload sessions; there is no migration or regeneration.

This change does not install a runtime, stage an image, create an approval,
enqueue a song, start paid generation, or upload anything. Production remains
owned by the existing single Mac executor and its normal publication checks.
