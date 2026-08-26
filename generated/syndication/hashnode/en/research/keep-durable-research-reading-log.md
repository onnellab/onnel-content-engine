---
title: "How to Keep a Durable Research Reading Log"
canonical_url: "https://onnellab.github.io/blog/en/keep-durable-research-reading-log/"
tags: "software-engineering,research,data"
cover_image: "https://onnellab.github.io/blog-assets/en/keep-durable-research-reading-log/social-card.png"
publication_id: ""
content_profile: "hashnode-native-v3"
---



A durable research reading log lets another person identify the source, recover evidence, understand your interpretation, and connect it to a claim. PDFs and free-form highlights often lose meaning when links and context change.

## The constraint to solve

Give every source a stable identity, locator, and access date; distinguish quotations from paraphrases; and connect notes to claims. Preserve enough context to prevent misreading. Move entries through capture, verification, summary, synthesis, and review, then create open-format exports, independent backups, and a handoff note.

The durable unit is not the highlight. It is a traceable relationship:

**source → passage or result → interpretation → project claim → review status**

## Why Reading Logs Stop Being Useful

Fragile logs preserve content but not provenance: a quotation lacks a page, a URL points only to a publisher home page, a paraphrase looks like exact wording, or broad tags replace a claim link. A DOI still cannot preserve local context or guarantee full-text access.

**Referential durability** keeps the source identifiable when its location changes. **Interpretive durability** preserves what you observed, how you represented it, and why it mattered. A stable identifier helps with the first; the reading record supplies the second.

## The Minimum Durable Log Schema

Use one record per source version. When a source changes substantially, create a new record and link versions instead of overwriting the earlier note.

| Field | What to record | Why it matters |
| --- | --- | --- |
| `record_id` | Immutable ID such as `RL-2026-0042` | Keeps internal links stable |
| `source_identity` | Author, title, container, date, version | Identifies the work consulted |
| `stable_identifier` | Full `doi.org/...` URL or another registered ID | Separates identity from location |
| `locator` | Access URL plus page, section, figure, timestamp, or dataset row | Recovers evidence within the source |
| `accessed_at` | Full date in `YYYY-MM-DD` | Records when a changeable web resource was observed |
| `note_type` | `quote`, `paraphrase`, `summary`, or `observation` | Separates your wording from the source |
| `evidence` | Short quotation, paraphrase, result, or observation | Preserves relevant support |
| `context` | Population, method, conditions, exceptions | Reduces scope errors |
| `claim_link` | Related claim, question, or claim ID | Makes the trail inspectable |
| `relevance` | Why the evidence matters | Preserves project reasoning |
| `status` | `captured`, `verified`, `summarized`, `synthesized`, `reviewed`, or `needs_review` | Shows what has and has not been checked |
| `tags` | Controlled topic, method, population, or project terms | Supports retrieval |

Optional fields can cover rights, language, checksums, archives, conflicts, and related records. A modest schema completed every time is better than a large, mostly empty one.

## Quote, Paraphrase, Summary, and Observation

Mark representation explicitly at capture time.

- A **quote** reproduces exact wording and needs quotation marks and a precise locator.
- A **paraphrase** restates a passage but still needs a citation and locator.
- A **summary** compresses a wider range; record that range.
- An **observation** is your analysis; label it and retain the source-data locator.

Mark any omission or change to a quotation. Use printed PDF pages where available, stable HTML headings, timestamp ranges for media, and dataset version plus table, variables, and relevant rows or query.

## Connect Claims to Evidence, Not Just Sources

A bibliography shows what was read; a claim-evidence link shows what the reading does. Give important claims stable local IDs. For each record, state whether the evidence **supports**, **qualifies**, **contradicts**, or only **provides context for** the linked claim. This prevents several adjacent citations from appearing to support a statement when only one does.

Record limitations beside the evidence. Sample, geography, date range, method, uncertainty, comparison group, and author caveats affect whether a finding transfers. “Same adult outcome, but only seven days of follow-up” is more useful than “important paper.”

## Implementation path

1. **Capture.** While the source is open, record bibliographic details, identifier, exact access URL and date, locator, note type, minimal evidence, and a local ID.
2. **Verify.** Resolve the identifier; compare author, title, date, version, and container with an official record; then reopen the locator and check quotations. Resolution alone does not prove the version is correct.
3. **Summarize.** Separately state the question, method, result, and limitations in your own words.
4. **Synthesize.** Link records to claims and explain whether sources converge, differ, or conflict.
5. **Review.** Before publication or handoff, recheck identifiers, quote boundaries, locators, rights, personal data, and status. Use `reviewed` or `needs_review` honestly.

![Research reading log workflow](https://onnellab.github.io/blog-assets/en/keep-durable-research-reading-log/workflow-diagram.svg "Capture, verify, summarize, synthesize, and review each source record")

Repeat capture or verification when synthesis exposes a gap or a new version appears. Status describes processing state, not source prestige.

## Stable Identifiers and the Limits of Links

Prefer a DOI when available and display it as a full URL such as `doi.org/10.xxxx/xxxxx`. Keep the exact accessed URL separately because it identifies the copy, repository, or landing page consulted.

Persistence depends on maintained records; it does not guarantee access, unchanged supplements, or an available cited page. Without a registered identifier, record full bibliographic details, version, URL, access date, and a permitted archive copy when appropriate.

For multiple versions, identify the exact one read and link version relationships. Never replace a preprint note with the final article while assuming quotations, pages, and results are identical.

## Copyright and Privacy Boundaries

A reading log is not permission to reproduce a source. Store the smallest necessary excerpt, preserve attribution and locator, and link to an authorized copy instead of redistributing full text. Copyright exceptions vary; the U.S. Copyright Office provides no fixed safe word count or percentage. Check the license, policy, and applicable law before sharing.

Notes can contain personal data. Minimize collection, separate access-controlled material, use pseudonymous IDs where appropriate, and remove secrets from exports. Retain only data adequate, relevant, and necessary for the stated purpose.

## Export, Backup, and Recovery

Export in documented formats at set intervals and major milestones.

| Format | Best use | Preservation note |
| --- | --- | --- |
| UTF-8 text or Markdown | Human-readable records | Keep links and field labels explicit |
| CSV | Flat-table exchange | Document encoding, delimiter, and escaping |
| JSON | Structured fields and arrays | Validate and retain a data dictionary |
| PDF/A or searchable PDF | Fixed review snapshot | Do not use as the sole editable source |

An export becomes a backup only when a copy is independent of the working system. Keep separate copies, include only permitted attachments, and periodically restore a sample. Check identifiers, Unicode, line breaks, and relationships. A checksum detects file changes, not inaccurate quotations or missing records.

Use ID-based filenames such as `RL-2026-0042.md`. A manifest should list record count, export date, schema version, attachments, exclusions, and checksum method. Open, documented formats reduce vendor dependence but still require review and migration.

## Project-End Handoff

At project close, create a handoff package usable without the original software:

1. the exported log in at least one human-readable and one structured format;
2. a README stating the research question, scope, date range, schema, status meanings, tag vocabulary, and folder layout;
3. a claim index linking each major claim to supporting, qualifying, and contradictory records;
4. a manifest of files, versions, checksums, licenses, and access restrictions;
5. a list of `needs_review` records, broken or restricted links, missing sources, and unresolved disagreements;
6. the date and method of the last restoration check, plus the next review owner and date.

Keep uncertainty visible. A labeled unresolved record is safer than a polished claim with unrecoverable evidence.

## When a focused tool helps

No current ONNELLAB app is required or specifically documented for this product-neutral workflow. Use any tool that can preserve the schema, stable links, open exports, and access controls described above; the method should remain portable if that tool changes.

## References

- [DOI Foundation: DOI Handbook](https://www.doi.org/doi-handbook/html/) defines DOI names, resolution, metadata, and persistence responsibilities.
- [Crossref: Display guidelines](https://www.crossref.org/display-guidelines/) recommends presenting Crossref DOIs as full resolvable DOI links.
- Crossref: Metadata retrieval documents official methods for checking deposited Crossref metadata.
- DataCite: Connecting versions explains how registered resource versions and formats can be related without conflating them.
- Library of Congress: Recommended Formats Statement describes format characteristics that support long-term survival and accessibility.
- IETF RFC 4180 and IETF RFC 8259 document interoperable CSV and JSON representations.
- U.S. Copyright Office: Fair Use Index explains that fair use depends on the circumstances.
- EUR-Lex: Regulation (EU) 2016/679, Article 5 states principles including purpose limitation, data minimization, and accuracy.

## Takeaway

A durable research reading log preserves more than citations. It identifies the exact source and version, distinguishes source language from your interpretation, locates the evidence, connects it to a claim, records limitations, and exposes review state. Open exports, tested backups, and a clear handoff package then keep that reasoning usable after the original project and software are gone.
