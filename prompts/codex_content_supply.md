# ONNELLAB bilingual content supply run

Work autonomously inside this repository to ensure the publication pipeline has at least one qualified English/Korean article pair and a durable idea backlog. Every selected subject must also support distinct, useful downstream copy for X, LinkedIn, Bluesky, Dev.to, Hashnode, and Medium after canonical publication.

Boundaries:

- Modify only content supply data and generated content under `data/topics.csv`, `topics/topics.csv`, `generated/markdown`, `generated/images`, `generated/assets/blog`, `generated/metadata`, and `generated/reviews`.
- Do not commit, push, schedule, publish, deploy, edit workflows, edit scripts, change application/release data, or mark anything `scheduled` or `published`.
- Preserve existing published content and unrelated state.
- Never lower a quality threshold or weaken a validator to make content pass.
- Use official or primary sources for factual claims. Keep quotations minimal and use links in the References section.
- English and Korean counterparts must share category and slug and must be genuinely localized, not mechanically duplicated.

Procedure:

1. Run `python3 scripts/check_content_supply.py` and inspect `data/topics.csv`, existing articles, app registry, and relevant source documentation.
2. If a bilingual pair is already `scheduled`, or both counterparts are `review` with scores greater than `9.0`, make no article changes. Still replenish the idea pool if fewer than 8 `idea` rows remain.
3. Otherwise complete the most advanced active bilingual pair. If none exists, select the highest-priority useful `idea`. Prefer topic diversity and avoid duplicating existing slugs.
4. When the selected idea has only one language, add a genuinely localized counterpart with `scripts/add_topic.py`. When no suitable idea exists, add a new evergreen English/Korean pair based on real user problems supported by released ONNELLAB apps.
5. Move the selected pair through the documented topic states without skipping validation. You may use `scripts/approve_topic.py` and the existing generation scripts to create scaffolds, but rewrite both Markdown files into complete, useful articles before review.
6. Each article must include aligned localized sections, a direct short answer, definitions, numbered workflow, comparison table, practical cautions, product mention only after education, related topics, FAQ, and official references. Keep claims conservative and evergreen.
7. Run image specification, image asset, internal-link, and article evaluation scripts. Revise the content and assets until both review scores are strictly greater than `9.0` and every mandatory check passes. Leave both topics in `review`.
8. Keep at least 8 remaining `idea` rows. Add diverse evergreen English seed ideas when needed; do not create near-duplicates or promotional-only ideas.
9. Before finalizing an article, check that its opening, concise takeaway, workflow, cautions, and canonical references are strong enough to yield genuinely different short social hooks and full syndication drafts. Do not add channel files directly; the publishing workflow generates and validates them after canonical publication.
10. Run `python3 scripts/validate_topics.py`, `python3 scripts/validate_foundation.py`, and `python3 scripts/check_content_supply.py --require-qualified-pair`.
11. Finish with a concise report of the selected pair, new ideas, review scores, sources, channel adaptability, and validation commands. If safe completion is impossible, leave no partial invalid topic transition and explain the blocker.
