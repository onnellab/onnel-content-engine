# ONNELLAB English YouTube Shorts Strategy

## Scope

This document is a strategy assessment, not a scheduler or automatic ranking rule.
The short-video runtime publishes **English only** to **YouTube Shorts**. TikTok and
Naver Clip are deferred. App and article localization remain independent.

The assessment uses repository facts current on 2026-09-21:
data/apps_registry.csv, data/topics.csv, data/store_versions.csv, and the
existing short-video design. Strategy judgments are labeled as such.

## Eligibility facts

Released and content-eligible in the registry:

- TagWeaver — iOS + Android — 2 active English source topics.
- Quivra — iOS + Android — 2 active English source topics.
- VaultXT — iOS + Android — 4 active English source topics.
- Segra — iOS + Android — 2 active English source topics.
- Aligna — iOS + Android — 1 active English source topic.
- ClipNest — iOS only — 1 active English source topic.

Not currently eligible for automatic promotion:
- Papira — registry status in_review and content_eligible=false.
- Melivra — registry status development and content_eligible=false.
- Summer Sound — not present in apps_registry.csv; do not infer release status.

Registry gaps should be fixed in the registry before the video scheduler considers
an app. The video pipeline must not invent eligibility from memory or store URLs.

## Evaluation rubric

Strategy score uses a 1–5 scale and these weights:

| Dimension | Weight | Meaning |
| --- | ---: | --- |
| Visual demo clarity | 25% | Can a 15–30s screen recording show the value immediately? |
| Searchable problem clarity | 25% | Is the user problem easy to state in plain English? |
| Cross-platform reach | 15% | Does the registry expose both iOS and Android? |
| English topic supply | 10% | How much verified English source material exists now? |
| Store readiness | 10% | Is the app released and represented in current store snapshots? |
| Short-form differentiation | 15% | Does the demo have a memorable before/after or focused action? |

Scores are strategic judgments grounded in those facts, not measured market demand.

## Initial promotion order

| Order | App | Visual | Problem | Reach | EN supply | Store | Difference | Weighted |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | TagWeaver | 5 | 5 | 5 | 4 | 5 | 5 | 4.90 |
| 2 | Aligna | 5 | 5 | 5 | 2 | 5 | 4 | 4.55 |
| 3 | VaultXT | 3 | 5 | 5 | 5 | 5 | 4 | 4.35 |
| 4 | Quivra | 4 | 5 | 5 | 4 | 5 | 3 | 4.35 |
| 5 | Segra | 4 | 5 | 5 | 4 | 5 | 3 | 4.35 |
| 6 | ClipNest | 4 | 4 | 2 | 2 | 5 | 4 | 3.60 |

### Why this order

**TagWeaver first.** Metadata cleanup and track numbering have concrete before/after
states, both mobile platforms are available, and two English source topics already
exist. A viewer can understand the action without narration.

**Aligna second.** Batch rename + preview is unusually visual for a utility and has
a simple problem statement. Its one English topic is a supply constraint, so repeat
videos should use genuinely different demonstrations rather than paraphrasing one
script forever.

**VaultXT third.** It has the strongest English topic supply and broad platform
reach. The weakness is visual immediacy: “large file” and “safe editing” benefits
are harder to prove in a short recording without unsupported performance claims.

**Quivra fourth.** The conversion problem is globally understandable and has two
English topics. The conversion process itself is visually less distinctive, so the
video must show a clear input → action → result without pretending the app exposes
options it does not.

**Segra fifth.** Waveform trimming is visually legible and the problem is clear.
Its differentiation is narrower than TagWeaver/Aligna, so validate demand with a
smaller sample before increasing share.

**ClipNest sixth.** The copied-snippet workflow is easy to show, but the registry is
iOS-only and has one English source topic, reducing addressable reach and content
variety.

Do not turn this table into a permanent algorithm. Re-rank after real channel/store
evidence exists.
## First 12-video test mix

Use actual approved footage and the named source topic; do not invent features.

1. TagWeaver — TOPIC-0008 — MP3 metadata cleanup — problem_solution.
2. Aligna — TOPIC-0012 — preview a batch rename before applying it — problem_solution.
3. VaultXT — TOPIC-0001 — reading a very large TXT file — problem_solution.
4. Quivra — TOPIC-0007 — local media conversion without server upload — problem_solution.
5. Segra — TOPIC-0009 — trim an audio recording without a full editing project — quick_demo.
6. TagWeaver — TOPIC-0029 — multi-disc track numbering — quick_demo.
7. VaultXT — TOPIC-0031 — inspect a large log without altering the original — problem_solution.
8. ClipNest — TOPIC-0010 — reuse copied text snippets on iPhone — quick_demo.
9. Aligna — TOPIC-0012 — a distinct preview-before-apply demonstration — quick_demo.
10. Quivra — TOPIC-0018 — explain the output-format decision before conversion — problem_solution.
11. Segra — TOPIC-0015 — verify clips before combining them — quick_demo.
12. VaultXT — TOPIC-0003 — TXT vs EPUB for long reading — problem_solution.

A repeated source topic is acceptable only when the recording teaches a genuinely
different sub-workflow. Do not create near-duplicate videos just to fill cadence.

## Measurement and re-ranking

Measure each video/app cohort without inventing universal benchmarks:

- first-seconds retention and full-video completion;
- average view duration relative to video length;
- rewatches where available;
- profile/channel-to-store clicks where measurable;
- store page visits/install signals where available;
- daily/weekly installs or sales correlated with publication windows;
- comments that reveal a concrete use case or confusion.

Use comparable windows and enough videos before changing priority. A single viral
or weak post is not sufficient evidence. Keep organic discovery separate from paid
campaigns if paid promotion is introduced later.
## Template assessment after English-only revision

### Quick demo

Strengths:
- one stage chip plus step count gives orientation without competing with footage;
- central uncropped recording remains the dominant visual;
- a quiet ONNELLAB footer gives continuity without turning every frame into an ad;
- final three seconds name the trusted app and supported platforms.

Best use: visible, sequential utilities such as batch rename, tag edits, trimming,
clipboard reuse, or a simple conversion flow.

Risk: too many captions can make a 15-second video feel instructional rather than
effortless. Prefer 2–4 meaningful steps.

### Problem → solution

Strengths:
- one active PROBLEM / SOLUTION / TRY IT chip is calmer than three simultaneous pills;
- the hook establishes why the screen recording matters;
- the closing slate identifies the app only after useful content has been shown.

Best use: search-led problems and workflows whose value needs one sentence of context.

Risk: the problem phase should be brief. Do not spend four seconds restating a title
when the app action itself can start sooner.

## English copy quality policy

The system no longer produces localized video variants. That removes cross-language
consistency and machine-translation drift from the publishing path, but it does not
make copy quality automatic.

Author video copy directly in plain English:
- concrete noun + verb beats abstract marketing language;
- use short imperatives for actions;
- keep one claim per caption;
- use globally understandable vocabulary and avoid slang;
- preserve product terminology from verified sources;
- never translate a Korean sentence literally when natural English would express
  the same verified meaning differently.

Deterministic validators enforce length, line count, timing and safe metadata only.
They must not assign a fake language-quality score. Naturalness and factual fidelity
remain review responsibilities.
## Review cadence

After the first 12 videos:
1. compare apps on retention/completion and measurable store movement;
2. inspect which template performs better for each app type;
3. retire weak hooks before adding more apps or platforms;
4. increase share for apps with repeatable evidence, not merely the largest topic pool;
5. only then consider a second publishing platform.

TikTok and Naver Clip remain out of scope for this test. The purpose of phase one is
to make one English YouTube channel operationally boring, measurable and reliable.
