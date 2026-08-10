---
title: "How to Keep a Durable Research Reading Log"
published: true
canonical_url: "https://onnellab.github.io/blog/en/keep-durable-research-reading-log/"
tags: "research-reading-log"
---

> ONNELLAB note: This version focuses on the rendering and workflow details behind large text files.



# How to Keep a Durable Research Reading Log

A research reading log becomes durable when another person—or your future self—can identify the exact source, recover the relevant passage, understand what you concluded, and see how that conclusion supports a project claim. A folder of PDFs and free-form highlights may help during reading, but it usually loses meaning when filenames, links, and project context change.

## Question

How can I keep a research reading log that remains useful after a project ends?

## Short Answer

Give every source a stable identity, record the locator and access date, distinguish quotations from paraphrases, and connect each note to a specific claim or question. Preserve enough surrounding context to prevent a passage from being misread. Move each entry through a visible workflow—capture, verify, summarize, synthesize, and review—then export the collection in open, documented formats with independent backups and a project-end handoff note.

The durable unit is not the highlight. It is a traceable relationship:

**source → passage or result → interpretation → project claim → review status**

## Why Reading Logs Stop Being Useful

Most fragile logs preserve content but not provenance. A quotation may lack a page number. A URL may point to a publisher home page rather than the item read. A paraphrase may later look like the author's exact wording. Tags may describe a broad topic without showing which claim the source supports. Even a DOI does not preserve your local context or guarantee access to the full text.

Durability therefore has two parts. **Referential durability** means the source can still be identified when its location changes. **Interpretive durability** means the note still explains what was observed, how it was represented, and why it mattered. A DOI helps with the first part; a careful reading record supplies the second.

## The Minimum Durable Log Schema

Use one record per source version. If an article, dataset, report, or preprint changes substantially, create a new record and link the versions rather than silently overwriting the earlier note.

| Field | What to record | Why it matters |
| --- | --- | --- |
| `record_id` | A local, immutable ID such as `RL-2026-0042` | Keeps internal links stable when titles or filenames change |
| `source_identity` | Author or organization, title, container, date, version or edition | Distinguishes the work actually consulted |
| `stable_identifier` | DOI as `doi.org/...`, or another registered identifier when available | Separates identity from a changeable location |
| `locator` | Exact URL or repository path used; page, section, figure, table, timestamp, or dataset row | Lets a reviewer recover the evidence within the source |
| `accessed_at` | Full date in `YYYY-MM-DD` | Records when a changeable web resource was observed |
| `note_type` | `quote`, `paraphrase`, `summary`, or `observation` | Prevents your wording from being mistaken for source wording |
| `evidence` | A short quotation, precise paraphrase, result, or data observation | Preserves the relevant support without copying the whole work |
| `context` | Population, method, conditions, exceptions, and nearby argument | Reduces cherry-picking and scope errors |
| `claim_link` | The claim, research question, or claim ID this evidence bears on | Makes the citation trail inspectable |
| `relevance` | One or two sentences explaining why the evidence matters | Preserves project reasoning rather than topic similarity alone |
| `status` | `captured`, `verified`, `summarized`, `synthesized`, `reviewed`, or `needs_review` | Shows what has and has not been checked |
| `tags` | A small controlled set for topic, method, population, or project | Supports retrieval without replacing explicit claim links |

Optional fields can record rights or license, language, file checksum, archive location, conflicts, and related record IDs. Keep the required set small enough that it is completed consistently. A large schema with mostly empty fields is less durable than a modest schema used every time.

## Quote, Paraphrase, Summary, and Observation

Mark representation explicitly at capture time.

- A **quote** reproduces exact wording. Keep quotation marks, the most precise available locator, and only enough text for the research purpose.
- A **paraphrase** restates a specific passage in your own words. It still needs a citation and locator; changing the wording does not make the idea yours.
- A **summary** compresses a larger argument or work. Record the covered range and avoid attaching a single page if the note describes the entire paper.
- An **observation** records something you derived, such as a pattern noticed across a table. Label it as your analysis and retain the source data locator.

Do not “clean up” a quotation without marking omissions or changes. If a PDF has printed page numbers, record those rather than only the viewer's page count. For HTML, use a stable heading plus paragraph description; for audio or video, use a timestamp range; for datasets, identify the version, table or file, variables, and relevant rows or query.

## Connect Claims to Evidence, Not Just Sources

A bibliography shows what was read. A claim-evidence link shows what the reading does.

Assign important project claims stable local IDs, for example `C-014: the intervention improved retention under delayed testing`. A source record can then state whether its evidence **supports**, **qualifies**, **contradicts**, or merely **provides context for** `C-014`. This prevents a common failure in synthesis: several citations accumulating beside a sentence even though only one directly supports it.

Record limitations beside the evidence. Sample, geography, date range, measurement method, confidence interval, comparison group, and author-stated caveats can determine whether a finding transfers to your claim. “Relevant” should explain that relationship: “Directly tests the same outcome in adults, but the follow-up is only seven days” is more useful than “important paper.”

## Recommended Workflow

1. **Capture.** Create the record while the source is open. Copy the canonical bibliographic details, DOI or other identifier, the exact access URL, access date, locator, note type, and minimal evidence. Give the record a local ID immediately.
2. **Verify.** Resolve the DOI through doi.org, compare author, title, date, version, and container with the item you read, and correct metadata against the registration agency or publisher record. Reopen the locator and compare every quote character by character. A resolving link alone does not prove that the metadata or version is correct.
3. **Summarize.** Write the source's central question, method, result, and limitations in your own words. Keep this separate from quoted text. If you cannot explain the evidence without rereading, the record is not ready for synthesis.
4. **Synthesize.** Link the record to claims and to other records. State whether sources converge, differ because of methods or populations, or genuinely conflict. Preserve disagreement instead of averaging it into a vague conclusion.
5. **Review.** Recheck high-impact claims before publication or handoff. Confirm identifiers, links, quote boundaries, locators, rights constraints, personal data, and status. Set completed records to `reviewed` and unresolved issues to `needs_review`; never let an unchecked capture appear verified.

![Research reading log workflow](https://onnellab.github.io/blog-assets/en/keep-durable-research-reading-log/workflow-diagram.png "Capture, verify, summarize, synthesize, and review each source record")

The workflow is cyclical. Synthesis may expose a missing comparison, sending you back to capture. A new source version may require verification again. Status describes the current evidence state, not the value or prestige of the source.

## Stable Identifiers and the Limits of Links

Prefer a DOI when a source has one and display it as a full resolvable DOI URL, such as `doi.org/10.xxxx/xxxxx`. The DOI identifies a referent independently of its current web location, while the DOI record can be maintained as locations change. Keep the exact URL you accessed as a separate field because it documents the copy, repository, or landing page actually consulted.

Persistence is a managed promise, not a frozen page. DOI resolution depends on registrants maintaining records, and it does not guarantee that you have subscription rights, that supplemental files remain unchanged, or that a cited page is available. A plain URL is a locator rather than a complete identity. For a source without a registered identifier, capture full bibliographic details, version, URL, access date, and—when lawful and permitted—an institutional archive or local preservation copy.

When a source has multiple versions, record the identifier for the exact version read. DataCite's related-identifier model can express relationships such as previous version, new version, or version of a collection. Do not replace a preprint note with the final article and assume every quotation, page number, or result is identical.

## Copyright and Privacy Boundaries

A reading log is not permission to reproduce a source. Store the smallest excerpt needed to support analysis, preserve attribution and locator, and link to an authorized copy instead of redistributing full text. Copyright exceptions vary by jurisdiction and purpose. The U.S. Copyright Office, for example, states that fair use is case-specific and provides no fixed safe word count or percentage. Check the license, institutional policy, and applicable law before sharing a log or source package.

Research notes can also contain personal data: interview quotations, participant IDs, email addresses, health details, or sensitive annotations about individuals. Minimize what you collect, separate access-controlled data from the general reading log, use pseudonymous IDs where appropriate, and remove secrets from exports. The GDPR's data-minimization principle is a useful operational rule even when that regulation is not the governing law: retain only data adequate, relevant, and necessary for the stated purpose.

## Export, Backup, and Recovery

Do not let a single application be the only readable form of the log. Export at documented intervals and after major milestones.

| Format | Best use | Preservation note |
| --- | --- | --- |
| UTF-8 plain text or Markdown | Human-readable records and narrative summaries | Keep links and field labels explicit; avoid tool-only extensions |
| CSV | Flat tables and spreadsheet interchange | Document encoding, delimiter, line endings, and how lists or line breaks are escaped |
| JSON | Structured fields, arrays, and machine processing | Validate exports and retain a short data dictionary |
| PDF/A or searchable PDF | Fixed review or handoff snapshot | Use as a reading copy, not the sole editable or machine-readable source |

An export is not a backup until another copy is independent of the working system. Keep multiple copies in separate storage locations, include attachments only when rights permit, and periodically restore a sample into a clean folder. Check that identifiers, Unicode text, line breaks, and record relationships survived. A checksum can reveal accidental file changes, but it cannot prove that a quotation is accurate or that the collection is complete.

Use filenames that do not depend on titles alone, for example `RL-2026-0042.md`, and include a manifest listing record count, export date, schema version, included attachments, excluded restricted material, and checksum method. The Library of Congress recommends considering sustainability and continued accessibility when selecting formats; open, well-documented representations reduce dependence on one vendor, but no format removes the need for migration and review.

## Project-End Handoff

At project close, create a handoff package that someone can inspect without your original software or memory:

1. the exported log in at least one human-readable and one structured format;
2. a README stating the research question, scope, date range, schema, status meanings, tag vocabulary, and folder layout;
3. a claim index linking each major claim to supporting, qualifying, and contradictory records;
4. a manifest of files, versions, checksums, licenses, and access restrictions;
5. a list of `needs_review` records, broken or restricted links, missing sources, and unresolved disagreements;
6. the date and method of the last restoration check, plus the next review owner and date.

Do not flatten uncertainty during handoff. A clearly labeled unresolved record is safer than a polished statement whose evidence cannot be recovered.

## References

- [DOI Foundation: DOI Handbook](https://www.doi.org/doi-handbook/html/) defines DOI names, resolution, metadata, and persistence responsibilities.
- Crossref: Display guidelines recommends presenting Crossref DOIs as full resolvable DOI links.
- Crossref: Metadata retrieval documents official methods for checking deposited Crossref metadata.
- DataCite: Connecting versions with related identifiers explains how registered resource versions and formats can be related without conflating them.
- [Library of Congress: Recommended Formats Statement](https://www.loc.gov/preservation/resources/rfs/) describes format characteristics that support long-term survival and accessibility.
- IETF RFC 4180: Common Format and MIME Type for CSV Files and IETF RFC 8259: The JavaScript Object Notation Data Interchange Format document interoperable CSV and JSON representations.
- U.S. Copyright Office: Fair Use FAQ explains that quotation limits cannot be reduced to a universal word count or percentage.
- EUR-Lex: Regulation (EU) 2016/679, Article 5 states the principles of purpose limitation, data minimization, and accuracy for personal data.

## Conclusion

A durable research reading log preserves more than citations. It identifies the exact source and version, distinguishes source language from your interpretation, locates the evidence, connects it to a claim, records limitations, and exposes review state. Open exports, tested backups, and a clear handoff package then keep that reasoning usable after the original project and software are gone.

## FAQ

### Is a DOI enough to make a reading note durable?

No. A DOI improves source identification and resolution, but the note still needs the version, evidence locator, access date, context, claim link, and review status. It also does not replace a lawful backup or guarantee access to full text.

### Should every highlight become a log record?

No. Capture evidence that bears on a research question, method decision, or claim. Unfiltered highlights create review debt and make important evidence harder to find.

### Can I paraphrase without recording a page or section?

A paraphrase still depends on the source. Record the most precise locator available so a reviewer can compare your wording with the original context.

### What should I do when a link breaks?

Resolve the stable identifier, search the registration metadata or official repository, and record the replacement locator without deleting the old access history. If the source cannot be recovered, mark the entry `needs_review` and do not rely on it for a critical claim.

### How often should I review the log?

Review records before synthesis, before a high-impact claim is published, and at project handoff. Also schedule periodic checks for long-running work, especially for changeable web sources and living datasets.

---

Originally published at https://onnellab.github.io/blog/en/keep-durable-research-reading-log/
