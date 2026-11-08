---
title: "Distinguish Recording Dates from Release Dates in Music Metadata"
description: "Separate recording, original release and edition dates, keep source notes, and leave uncertain music metadata dates unknown."
language: "en"
slug: "distinguish-recording-date-from-release-date"
category: "music"
short_answer: "A recording date describes when the performance was recorded; a release date describes when music was issued. Identify the exact edition, compare its official information and booklet, and keep each date with its source. Do not invent a recording date from a release year."
primary_keyword: "recording date versus release date"
secondary_keywords: ""
card_title: "Distinguish Recording Dates from Release Dates in Music Metadata"
status: "draft"
related_apps: ""
search_intent: "workflow"
tags: "recording date versus release date"
canonical_url: "https://onnellab.com/blog/en/distinguish-recording-date-from-release-date/"
---

# Distinguish Recording Dates from Release Dates in Music Metadata

A recording date describes when the performance was recorded; a release date describes when music was issued. Identify the exact edition, compare its official information and booklet, and keep each date with its source. Do not invent a recording date from a release year.

## Start with one edition

An album folder can contain several plausible years. Before editing anything, identify the edition you own using its format, label, catalog number and track list. Do not assume that a page for another edition describes your files.

MusicBrainz treats an edition's issue date as a release property. Its [release documentation](https://musicbrainz.org/doc/Release) helps explain this distinction. Use the artist's or label's information and the matching booklet to investigate your particular copy.

## Keep three questions separate

| Question | Evidence to look for | What not to assume |
| --- | --- | --- |
| When was this performance recorded? | An explicit session date in the booklet or official notes | The release year is the recording year |
| When was the recording originally released? | Official information identifying the first issue | A later edition's date is the original date |
| When was this edition issued? | Information for the matching edition and territory | Every edition has the same date |

A remastering year, copyright notice or file modification timestamp does not, by itself, answer all three questions.

## Five steps before changing a date

1. Keep a backup and inspect one track first. Write down the existing date values without overwriting them.
2. Match the edition. Note the label, catalog number, format and territory where available.
3. Read the booklet and official release page. Record what each source actually calls the date, plus its page number or URL.
4. Keep only the precision supported by the evidence. If only a year is known, do not add an invented month or day. Mark unresolved conflicts in a separate note.
5. Check the editor's field definitions and the player's display before saving a test copy. A field called “Year” may not preserve all these distinctions. Reopen the saved copy and inspect it before considering a wider edit.

The [ID3v2.4 specification](https://id3.org/id3v2.4.0-frames) distinguishes recording, original-release and release timestamps. That does not prove that a particular editor exposes each field or that a player displays it as expected. This workflow does not prescribe a tag mapping.

## An invented example

Suppose a booklet explicitly says a performance was recorded in 1998, official notes identify its first issue in 2000, and your matching edition was issued in 2024. Keep those three statements separately with their sources. The 2024 edition does not make the performance a 2024 recording.

If the recording date is absent, write “unknown” in your research notes. Do not fill the gap by copying 2000 or 2024 into a recording-date field.

## Common questions

### Should I change every track together?
Not yet. An album may combine sessions or bonus material. Check whether the evidence applies to all tracks before considering a batch edit.

### Which date should my player show?
That depends on your filing goal and the player's behavior. First preserve the distinct facts; then test how the player reads a copy. Do not sacrifice source information just to make the display look tidy.

### What if two sources disagree?
Keep both references and describe the conflict. Check that they refer to the same edition and territory. Leave the uncertain value unresolved rather than selecting the more convenient year.

## Next step

Pick one album and make a source note before editing its tags. For a separate problem, read [how to distinguish duplicate files from different recordings](/blog/en/distinguish-duplicate-music-files-from-different-recordings/). Date notes alone cannot prove that two files contain the same recording.
