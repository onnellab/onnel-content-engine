---
title: "How to Number Tracks in a Multi-Disc MP3 Album"
card_title: "How to Number Tracks in a Multi-Disc MP3 Album"
slug: "number-tracks-multi-disc-mp3-album"
category: "music"
language: "en"
description: "Number tracks in a multi-disc MP3 album safely by separating track position from disc position, preserving originals, and testing a small copy."
status: "draft"
topic_id: "TOPIC-0029"
search_intent: "workflow"
primary_keyword: "number tracks in a multi-disc MP3 album"
secondary_keywords: "MP3 track number|disc number tags|ID3 TRCK TPOS|TagWeaver"
related_apps: "TagWeaver"
tags: "multi-disc MP3 album|MP3 track number|disc number tags|ID3 TRCK TPOS"
short_answer: "Keep each song's position on its own disc in the track field and the disc's position in the disc field, use totals only when verified, edit copies first, and test a representative set in the destination library."
canonical_url: ""
published_at: ""
updated_at: ""
image_specs: "Backup-first multi-disc numbering workflow|TRCK and TPOS field map|Destination library verification"
---

# How to Number Tracks in a Multi-Disc MP3 Album

A boxed set has two kinds of order: songs within each disc and discs within the set. Record those positions separately, preserve uncertain information, and verify a sample before changing the whole album.

## Question

How should I number tracks in a multi-disc MP3 album?

## Short Answer

Keep the song's position on its own disc in the track field and the disc's position in the disc field. For example, the fourth song on disc two of a three-disc set can be represented as track `4` with disc `2`; use totals such as `4/11` and `2/3` only when the complete counts are verified. Edit copies, keep one album title and album-artist convention across the set, save a small representative batch, and inspect the written tags and destination library before expanding the edit.

## Define Track Position and Disc Position

**Track position** answers “which song is this on this disc?” In ID3v2, the `TRCK` frame carries that value. The ID3v2.4 frame definition permits a numeric position followed by an optional slash and total, such as `4/11`. A plain `4` is still a position; it does not require a total to be meaningful.

**Disc position** answers “which disc is this in the set?” The `TPOS` frame uses the same position-and-optional-total pattern for a part within a set. Thus `2/3` means part two of a three-part set. In an ordinary release, that part is usually a physical or logical disc, but the tag identifies a part of a set rather than promising how every music application will label it.

These fields describe different axes. `TRCK=4/11` and `TPOS=2/3` preserve “track four on disc two.” Writing only a continuous number such as track 15 may preserve one listening order, but it no longer records where disc two begins. Continuous numbering can be an intentional private convention, but it should not be confused with the release's per-disc positions.

## Decide the Numbering Convention Before Editing

Start from a trustworthy track list: the release booklet, the publisher or label's official listing, or another source that clearly identifies the exact edition. Deluxe editions, regional editions, reissues, and bonus-disc versions can have different counts. A listing for a similarly titled release is not enough evidence.

Write a tiny plan before changing files:

- the exact album title used by every track in the set;
- the shared album-artist value, if the release calls for one;
- the number of discs that are actually present;
- the per-disc track count, including whether bonus material belongs to a separate disc;
- whether totals are known well enough to store;
- whether the collection will preserve printed per-disc numbering or use a deliberately documented personal convention.

Per-disc numbering is the most faithful default when the source identifies discs separately. Disc one starts at track one, disc two starts at track one again, and `TPOS` distinguishes them. Do not invent a missing disc or total merely to make every field look complete. A known position without a verified total is better than a precise-looking error.

## Build a Field Map Before a Batch Edit

A field map makes the intended change visible before it reaches the files. For a two-disc album, a small sample might look like this:

| File role | Track field (`TRCK`) | Disc field (`TPOS`) | What to verify |
| --- | --- | --- | --- |
| First song on disc 1 | `1/10` | `1/2` | Correct edition and ten-song disc count |
| Last song on disc 1 | `10/10` | `1/2` | No skipped or duplicated position |
| First song on disc 2 | `1/12` | `2/2` | Track numbering restarts intentionally |
| Last song on disc 2 | `12/12` | `2/2` | Set and per-disc totals agree with source |

## Protect the Original and Select Files by Disc

Metadata edits can affect many files quickly, so reversibility matters more than speed. Keep an untouched copy outside the working folder. A backup is useful only if it remains separate from the files being edited.

Group working copies by actual disc before applying shared values. A folder named `CD2` is a clue, not proof; compare it with the authoritative track list. Remove uncertain files from the batch. Share only values that are genuinely common: album data across the set and disc position within one disc. Keep titles and track positions song-specific unless a reviewed sequence tool assigns them.

## Recommended Workflow

1. **Preserve the source.** Copy the complete album to a working location and keep the original unchanged. Confirm that all expected discs and files are present.
2. **Identify the exact edition.** Compare titles, durations, bonus material, and printed disc boundaries with a trustworthy listing. Mark unmatched files instead of forcing them into the sequence.
3. **Choose per-disc or continuous numbering.** Prefer per-disc positions plus a separate disc field when reproducing a multi-disc release. If a personal continuous sequence is required, document that it is a collection convention.
4. **Create the field map.** List each file's intended title, `TRCK` position, optional track total, `TPOS` position, and optional disc total. Check for duplicates and gaps within every disc.
5. **Edit one representative subset.** Include the first and last track of one disc and the first track of the next disc. This sample exposes boundary and restart mistakes.
6. **Save explicitly, then reopen.** Close the editor or clear the selection, reopen the same files, and inspect the stored values. A value visible before saving is not proof that it was written.
7. **Test the destination library.** Import only the sample. Inspect album grouping, disc boundaries, displayed order, and the first transition between discs. Treat this as evidence for that specific app and version, not a universal rule.
8. **Expand in disc-sized batches.** Apply only the reviewed map, reopen each completed disc, and compare its first, last, and one middle track with the plan.
9. **Retain the backup through a second check.** Keep it until the full album has been reopened and tested after the library's normal refresh or re-import procedure.

![Workflow diagram](/blog-assets/en/number-tracks-multi-disc-mp3-album/workflow-diagram.svg "Backup-first workflow for assigning and verifying track and disc positions")

## Verify More Than the Visible Sort Order

A correct-looking list can hide incorrect tags. A library might retain imported metadata, cache an earlier value, or apply its own presentation rules. First reopen the files in a metadata reader or editor and check the stored `TRCK` and `TPOS` values. Then follow the destination application's documented refresh or re-import behavior for the small test set.

Check the first and last track of every disc, transitions between discs, and any differently sized bonus disc. Scan for duplicate or missing positions, inconsistent totals, and one disc value accidentally applied to the whole album. Successful playback does not prove the numbering: these tags describe audio but do not repair it, establish factual accuracy, or guarantee gapless playback.

## Common Failure Modes and Safe Responses

| Symptom | Likely data issue to inspect | Safe response |
| --- | --- | --- |
| Disc two appears before disc one | Missing or inconsistent disc positions | Reopen files and compare `TPOS` values with the field map |
| Tracks interleave across discs | Disc values are absent, inconsistent, or ignored by that destination | Verify stored tags, then consult and test the destination's behavior |
| One disc has duplicate positions | A shared track value was batch-applied | Restore affected copies or reapply song-specific positions from the map |
| The album splits into groups | Album or album-artist text differs | Compare exact text before changing numbering again |
| A total is wrong on only some files | Mixed edition data or partial batch selection | Verify the edition and make totals consistent only when known |
| The editor and player disagree | Cached library data or different field support may be involved | Check the file itself, then refresh only the test set as documented |

## ONNELLAB Application

[TagWeaver](/apps/tagweaver/) is a focused local MP3 metadata editor that can be used to apply a reviewed track-and-disc field map to selected files. Repository-maintained app facts describe single-track editing in the free experience and batch editing as part of the optional Pro one-time purchase. Its official store listings document track and disc values among the editable metadata; platform details should be checked in the listing for the device being used.

The app does not determine the correct edition or invent trustworthy positions. Use it after the track list and conventions are settled, keep the backup outside the working selection, save explicitly, and verify a small result. On iOS, follow the app's documented copy-save behavior rather than assuming the original file is replaced in place.

## References

- [ID3.org: ID3v2.4.0 frame definitions](https://id3.org/id3v2.4.0-frames) defines `TRCK` for position in a set and `TPOS` for the part of a set, including optional totals after a slash.
- [ID3.org: ID3v2.4.0 structure](https://id3.org/id3v2.4.0-structure) documents the tag and frame structure that carries ID3v2 metadata.
- [ID3.org: ID3v2.3.0 specification](https://id3.org/id3v2.3.0) provides the earlier ID3v2.3 definitions relevant to files and tools that use that version.
- [TagWeaver on the App Store](https://apps.apple.com/app/id6759609875) is the official iOS product and platform listing.
- [TagWeaver on Google Play](https://play.google.com/store/apps/details?id=com.onnellab.tagweaver2) is the official Android product and platform listing.

## Conclusion

To number tracks in a multi-disc MP3 album without losing its structure, treat track position and disc position as separate facts. Verify the exact edition, map each file before editing, preserve originals, and prove the boundary behavior with a small sample. Totals, leading zeroes, filenames, and destination display choices are secondary conventions; accurate `TRCK` and `TPOS` positions plus a reversible workflow form the dependable core.

## FAQ

### Should disc two restart at track one?

Usually yes when preserving a release whose discs have their own printed sequences. Store the restarted track position in `TRCK` and distinguish the disc with `TPOS`. A continuous sequence is possible as a personal convention, but document that choice.

### Must I include totals such as `4/11` and `2/3`?

No. The totals are optional. Include them only when the exact edition and complete counts are verified; a correct current position is safer than an incorrect total.

### Will adding disc numbers make every player sort the album correctly?

No universal behavior should be assumed. Correct fields preserve the data, while each destination decides how to read, group, cache, and display it. Test a representative copy in the specific destination.

### Can I use filenames instead of track and disc tags?

Filenames can aid folder inspection, but they do not prove that embedded `TRCK` and `TPOS` values were written. Keep filename changes separate and reversible.

### Does changing these tags affect audio quality?

Track and disc positions are metadata, not audio samples. The conceptual edit does not improve or re-encode sound, but you should still preserve originals and verify the editor's actual output.
