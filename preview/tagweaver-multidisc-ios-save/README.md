# TagWeaver iOS save wording correction

Nine complete corrected manuscripts are prepared here for the existing `number-tracks-multi-disc-mp3-album` article. Only the inaccurate iOS save sentence is replaced, using the independently reviewed wording from the October 18 proposal. Historical frontmatter, dates, URLs, links, headings, images and all unrelated prose are unchanged.

These are preparation files. The inherited `status: published` frontmatter refers to the original article and does not mean this correction has been deployed.

## Why published sources remain unchanged

The canonical engine currently has only the original English and Korean topic records for this historical article. The other seven translations exist only in the homepage repository. The publisher exports registered engine source paths and has no staged-correction input. Editing only the two engine manuscripts would allow a partial two-language correction. Editing homepage main directly would bypass the required sole publisher.

The next required step is to validate a scoped application route for all nine historical translations through the existing Publishing Pipeline. This preparation does not implement that route, dispatch CI, create new topic IDs, requeue the old article, or change any schedule.

## Review and verification

- Nine complete manuscripts with one exact sentence replacement each
- All eleven current target blobs still match the original proposal
- Independent semantic, omission, terminology and naturalness review passed for the replacement text
- Exact frontmatter, headings and Markdown link targets preserved
- Native quality checks, corrected-page rendering and deployment remain unrun

See `manifest.json` for exact target paths and expected blobs, and `editorial_review.json` for the locale-specific review. Before applying, re-read current heads and every target blob; do not overwrite a changed source.
