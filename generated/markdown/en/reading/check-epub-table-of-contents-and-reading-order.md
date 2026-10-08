---
title: "Check an EPUB’s Table of Contents and Chapter Order"
card_title: "Check an EPUB’s Table of Contents and Chapter Order"
slug: "check-epub-table-of-contents-and-reading-order"
category: "reading"
language: "en"
description: "Compare an exported EPUB with your intended chapter list, test navigation links and reading order, and trace any mismatch back to the source."
status: "review"
topic_id: "TOPIC-0053"
search_intent: "troubleshoot"
primary_keyword: "check an EPUB’s table of contents"
secondary_keywords: "EPUB chapter order|EPUB navigation checks|missing EPUB chapters|Papira"
related_apps: "Papira"
tags: "EPUB|table of contents|reading order|navigation|ebook checks"
short_answer: "Write down the expected chapters, open the exported EPUB in a separate reader, test each contents link, and read across chapter boundaries. Record mismatches, correct the source or export setup, regenerate and check again."
canonical_url: "https://onnellab.com/blog/en/check-epub-table-of-contents-and-reading-order/"
image_specs: "Expected chapters|Contents links|Reading order|Correct and regenerate"
---

# Check an EPUB’s Table of Contents and Chapter Order

An EPUB opens, but do its links and chapter sequence match your manuscript? To check an EPUB’s table of contents, compare it with your intended chapter list, then test both contents links and ordinary reading.

This guide starts after export and focuses on inspection rather than cover, encoding, or manuscript setup.

## Question

How can I check that an exported EPUB’s contents links and chapter order match my manuscript?

## Short Answer

Write down the expected chapters, open the exported EPUB in a separate reader, test each contents link, and read across chapter boundaries. Record mismatches, correct the source or export setup, regenerate and check again. Keep the original manuscript and previous export until the replacement has been checked.

## Separate the Three Things You Are Checking

The **contents label** is the text you select in the reader’s table of contents. The **link target** is where it opens. The **reading order** is the sequence encountered when reading without selecting another entry.

EPUB 3 represents navigation and default reading order separately: its navigation document supplies the table of contents, while the package’s spine orders content documents. The order within each document also matters. These distinctions are defined in [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/). You do not need to edit those internal files to carry out the checks below.

| Check | What it tells you | What still needs checking |
| --- | --- | --- |
| Compare the displayed contents with your list | Whether expected entries and understandable labels appear | Where each link goes |
| Open each contents link | Whether it reaches the intended heading and opening text | What comes next during ordinary reading |
| Continue across chapter boundaries | Whether the reading sequence matches your plan | Whether all contents links are correct |
| Run EPUBCheck | Whether the package meets the EPUB rules it checks | Whether the book matches your editorial intent |

A page headed “Contents” inside the book and the reader’s contents menu may be presented separately. Inspect the menu, and check a contents page too if the exported book includes one.

## Make an Expected Chapter List

Using the manuscript as your reference, list the intended chapters in order, including expected front and back matter such as a preface or afterword. Decide which sections belong in the contents; every paragraph does not need an entry.

For repeated headings such as “Notes,” add a short phrase from each opening paragraph to your private check sheet. Use recognizable text rather than reader page numbers, which can change with layout settings.

Record the export filename, source revision, converter version, and reader name and version. After regeneration, confirm that the reader opens the new file. Preserve annotations before removing an older library copy.

## Use a Small Check Sheet

This invented teaching example is not an actual defect report or device test. The expected sequence is “Arrival,” “The Trail,” then “Return.” Copy the columns and record your own observations.

| Expected heading | Contents label | Actual destination | Following chapter | Result | Source or setup follow-up |
| --- | --- | --- | --- | --- | --- |
| 1 Arrival | 1 Arrival | 1 Arrival | 2 The Trail | Matches | None |
| 2 The Trail | 2 The Trail | 3 Return | Not checked yet | Wrong destination | Check the source boundary and documented export rules |
| 3 Return | 3 Return | 3 Return | End of body | Matches this check | Check any intended afterword separately |

The second row does not prove that chapter 2 is absent. Search for its opening text or continue from chapter 1 before deciding whether the chapter is missing or its link is incorrect.

## Recommended Workflow

1. **Open the correct export.** Keep the source and EPUB filenames visible in your notes. Use a reader that supports the file, and check its import or sync behavior before opening a private manuscript.
2. **Compare the whole contents list.** Look for missing sections, unexpected entries, repeated labels, and a sequence that differs from your reference. Expand collapsed groups where the reader provides them.
3. **Test every contents link.** Compare each destination’s heading and opening passage with the reference. Record where it lands; opening somewhere in the book does not establish that the destination is correct.
4. **Test ordinary reading separately.** Begin before the first intended body chapter. Continue across its ending into the next chapter without using the contents menu. Check front matter and transitions near the beginning, middle, and end, then check the remaining chapter boundaries before treating the whole book as checked.
5. **Inspect the end.** Confirm that the final chapter reaches its intended ending and that any afterword or appendix remains reachable. Keep expected auxiliary material distinct from the main chapter sequence.
6. **Check the same export in another reader when distribution requires it.** If the results differ, record the file and reader versions. A difference is evidence to investigate; it does not by itself identify which component is responsible.

![Illustrative flow from an expected chapter list to contents-link checks, reading-order checks, and source correction before regenerating the EPUB.](/blog-assets/en/check-epub-table-of-contents-and-reading-order/workflow-diagram.svg "Check links and reading order separately before regenerating")

The diagram illustrates a suggested workflow, not a screenshot or completed test.

## Diagnose the Mismatch Before Changing the Source

| Symptom | Evidence to collect | Next step |
| --- | --- | --- |
| A chapter is missing from the contents | Does its opening text still appear during ordinary reading? | If present, inspect heading recognition and the intended contents scope; if absent, check source completeness and export boundaries |
| A correct-looking label opens the wrong chapter | Record the opened heading and text | Compare the source boundary and documented heading rules; reproduce with a small sample |
| Two entries have the same label | Compare both targets and the corresponding source headings | Decide whether the repetition is intentional before changing a title or removing a marker |
| Links work, but ordinary reading skips or reorders chapters | Record the actual transition and the expected next chapter | Check source sequence and available export settings; retain the result for diagnosis if the source is correct |
| Only one reader shows the problem | Confirm that both readers opened the same export revision | Repeat the exact transition and compare versions before blaming the manuscript or reader |

Change one relevant thing at a time. Correct the working manuscript or a documented conversion setting, export to a distinguishable new file, and retest the affected entry and neighboring transitions. Finish by repeating the whole contents-link check because a structural change may affect more than one destination.

If a clean source still produces the mismatch, preserve the original and create a short sample using text you own or may share. Describe the expected and observed destinations when seeking support. Do not send an unpublished full manuscript merely to demonstrate one navigation issue.

## Keep Validation and Reading Checks Together

[EPUBCheck](https://www.w3.org/publishing/epubcheck/) checks publications against EPUB specifications. Use its report to investigate package errors and warnings, then repeat validation on the regenerated file. A successful report cannot decide whether “Chapter 2” contains the chapter you intended.

Likewise, opening a book successfully in one reader does not establish full conformance, accessibility, or compatibility with every reading system. Keep the validation report, your navigation observations, and any untested readers or sections separate. For confidential text, choose a local validation workflow or review a service’s data handling before uploading the book.

## Where ONNELLAB Fits

If you need to regenerate an EPUB from a finished TXT manuscript, Papira is an optional ONNELLAB tool for that step. Its official listings describe offline EPUB assembly with a cover, book details, and a table of contents. Edit the manuscript elsewhere and inspect the exported EPUB in another reader: Papira does not provide body-text editing or an EPUB reader.

Heading recognition depends on the documented platform and version. Do not assume that app interface languages establish which chapter-heading patterns are recognized, or that iOS and Android behave identically. This workflow therefore does not prescribe one automatic-detection rule for every manuscript. Check the current instructions for your installed version and verify the resulting contents against your list.

See the official [Papira App Store listing](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) or [Papira Google Play listing](https://play.google.com/store/apps/details?id=com.onnellab.papira) for your platform and region. The inspection method above also works with other EPUB exporters.

## Related Guide

If the mismatch takes you back to source preparation, use [How to Prepare a TXT Manuscript for Reliable EPUB Conversion](/blog/en/prepare-txt-manuscript-for-epub/). That guide covers the earlier preparation stage; this check sheet belongs after export.

## References

- [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) describes navigation documents and the spine that defines default reading order.
- [W3C EPUBCheck](https://www.w3.org/publishing/epubcheck/) documents the EPUB conformance checker.
- [Papira on the App Store](https://apps.apple.com/us/app/papira-txt-to-epub-converter/id6803919552) and [Papira on Google Play](https://play.google.com/store/apps/details?id=com.onnellab.papira) describe the product’s scope and platform-specific guidance.

## Conclusion

Compare intention with observation: list expected chapters, test every contents link, and inspect ordinary reading order. Preserve evidence of differences, correct the source or supported export setup, and check the new file before sharing it.

## FAQ

### Does a visible chapter title prove its contents link is correct?

No. Open the entry and compare its destination’s heading and opening text. Check the label and target separately.

### Is a chapter missing if it does not appear in the contents menu?

Not necessarily. Its text may still exist in the reading sequence. Look for the opening passage and compare the intended contents scope before diagnosing missing content.

### Why can the links work while chapters appear in the wrong order?

Selecting a link and continuing through the book exercise different navigation paths. Record the actual next chapter as a separate result, then compare it with the manuscript and export setup.

### Does passing EPUBCheck mean the book is ready to distribute?

It is one useful check. You still need to confirm the intended text, navigation, reading sequence, and the requirements of your audience or distributor. It is not an editorial or accessibility sign-off.

### Should I fix the exported EPUB directly?

Prefer correcting the source or documented export settings so the next export includes the fix. If a publishing workflow requires package editing, record that step and keep it reproducible rather than maintaining two conflicting versions.

### Can I do these reading checks inside Papira?

No. Papira assembles finished TXT manuscripts into EPUB; it is not an EPUB reader. Open the exported file in a separate reader, and use a text editor when the manuscript needs correction.
