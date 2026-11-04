# STYLEMATCH-001 draft evaluation contract

Status: **DRAFT / UNAPPROVED / NOT FROZEN**. This document defines a proposed
experiment, not approval to collect data, select a model, run 001B or begin
STYLEMATCH-002. Only the 001A foundation has been implemented.

## Task and boundaries

Given one inspiration image, one active wardrobe and one human-identified
component category, rank existing wardrobe items that can acceptably recreate
that component's visible appearance, or abstain when no acceptable item exists.
This is component retrieval, not outfit generation, automatic extraction,
physical fit estimation or sensitive-characteristic inference.

Initial categories, **PROVISIONAL / UNAPPROVED**: tops (shirts, blouses, knitwear
and T-shirts), bottoms (trousers, jeans, skirts and shorts), outerwear (jackets
and coats worn over a top). Assign one primary category per garment before
labeling. Dresses, jumpsuits, underwear, swimwear, shoes, accessories, ambiguous
layering and items whose relevant surface is largely hidden are unsupported in
the initial pilot. Record exclusions rather than silently dropping failures.

Capture garments individually with a visible full garment, neutral lighting,
simple background and representative color. Avoid faces, personal surroundings,
names and location clues. Use authorized inspirations with a distinguishable
target component. Humans define component tasks and optional crops. Preserve
provenance, permission and all related-source/capture links; sanitized copies
and crops inherit the source grouping. Unreadable, severely occluded or
out-of-scope inputs receive an explicit exclusion reason before splitting.

## Proposed scale and decision criteria

Every numeric target in this table is **PROVISIONAL / UNAPPROVED**. The grounding
and category rules remain mandatory regardless of target approval.

| Proposal | Status |
| --- | --- |
| Four separately identified wardrobes, approximately 15 items each | PROVISIONAL / UNAPPROVED |
| Approximately 32 inspiration images and at least 64 component tasks | PROVISIONAL / UNAPPROVED |
| Two development wardrobes and two final-test wardrobes | PROVISIONAL / UNAPPROVED |
| At least 16 no-acceptable-match tasks | PROVISIONAL / UNAPPROVED |
| Initial three categories: tops, bottoms, outerwear | PROVISIONAL / UNAPPROVED |
| Matchable test Hit@3 >= 0.80 | PROVISIONAL / UNAPPROVED |
| Matchable test nDCG@5 >= 0.70 | PROVISIONAL / UNAPPROVED |
| No-match false acceptance <= 0.10 | PROVISIONAL / UNAPPROVED |
| Matchable false rejection <= 0.20 | PROVISIONAL / UNAPPROVED |
| Zero surfaced invalid/cross-wardrobe IDs | PROVISIONAL / UNAPPROVED numeric target; mandatory grounding invariant |
| Zero surfaced category violations | PROVISIONAL / UNAPPROVED numeric target; required output invariant |
| No paid services or infrastructure (zero spend) | PROVISIONAL / UNAPPROVED numeric target; current scope prohibition on paid services |

This scale limits capture and exhaustive labeling effort while exposing category
differences, multiple acceptable items and abstention behavior. It is a small
feasibility pilot: shared wardrobes, people, components and inspirations reduce
effective sample size. No-match counts are especially weak for estimating rare
errors. Do not assert statistical power or generalization to other populations.
Report exact eligible, excluded, matchable and no-match counts for each split and
category. Any scale change must be recorded before final-test unsealing.

## Human relevance and disagreement

Reviewers judge visible color/pattern, garment type, silhouette, texture and
appearance contribution within the component category. The field-level rubric,
attribute reliability and mandatory attribute gates await a development-only
pilot; do not invent fixed weights or acceptance gates now. Do not judge body
shape, sensitive traits or physical fit. Labels are human judgments, not a
model-generated ground truth.

Use the exact 0/1/2/3 rubric in [data-and-metrics.md](data-and-metrics.md). Label
every eligible wardrobe item for every task, including unacceptable candidates.
Multiple acceptable matches are expected. No-match means no grade 2/3 item, not
merely a poor first-ranked result. Show the whole candidate pool, randomize its
presentation order, and withhold model names, scores and rankings from reviewers.

Proposed procedure: independent human reviews, recorded pseudonymous reviewer
identity, uncertainty and short rationale; compare candidate grades and no-match
decisions. Preserve both original reviews privately. Resolve disagreement through
discussion or a separately identified adjudicator; document the resolution and
canonical reviewer identity. Unresolved tasks remain uncertain and unscorable.
Reviewer availability and disagreement sampling remain decisions for the pilot;
do not silently treat one person's repeated labels as independent reviewers.

## Split and sealing policy

Assign wardrobe partitions before tuning. Record the actual person overlap;
development and test need not be entirely different people. Exact-byte hashes,
source groups and related-capture groups cannot cross partitions. Inspiration
components and human crops stay with their source. Audit source relationships
manually because hashes do not establish absence of near-duplicates. Keep all
manifest identifiers pseudonymous and private where they expose personal data.

The development pilot may refine capture rules, category boundaries, attribute
gates, model candidates and thresholds. Select all confidence/abstention
thresholds, preprocessing, weights and hyperparameters on development only,
using the same task/label definitions across comparisons.

Before any final-test inference: obtain contract approval; resolve pilot choices;
record exact dataset and label hashes, split registry, code commit, dependency
lock, candidate revisions, prompt versions, thresholds, resource measurement
protocol, exclusion rules and uncertainty plan. Record the approval and freeze
identifier/date. A designated custodian should seal final-test images/labels and
restrict access; a JSON partition label alone does not enforce sealing. Log who
has seen what. Inference may access sealed inputs under the approved procedure;
threshold tuning must not access final-test judgments or outcomes. Deviations
require a logged amendment and a decision about a fresh holdout. **This slice
does not freeze the contract or establish a sealed dataset.**

## Proposed comparisons, not implemented

- Assisted attribute/rule baseline: human-confirmed observable attributes,
  category gating and transparent similarity rules. Measure annotation effort;
  field choices, weights and field-level gates await the development pilot.
- Embedding comparison: one verified candidate at a time, identical wardrobe
  pool and inputs, explicit preprocessing, normalized similarity if appropriate
  to the verified model, and a development-selected abstention threshold.
- Proposed hybrid: category/verified attribute constraints combined with
  embedding scores. Determine combination weights and fallback behavior only
  on development. Report cases where constraints discard acceptable candidates.
- Full inspiration versus human crop ablation: paired component tasks, same
  labels, split and retrieval pool. Use human crops only; automatic garment
  extraction is outside scope. Report missing/ambiguous crop cases and effort.

FashionCLIP, SigLIP2 and an unspecified lightweight VLM are candidates only.
[Candidate checklist](candidate-checklist.md) must be completed before selection.
No checkpoint is selected, downloaded, wrapped or run in 001A.

## Reporting and resource decisions

Use the [executable metric semantics](data-and-metrics.md), including empty lists,
duplicates, missing labels and zero relevant items. Retain raw predictions and
validated recommendations together. Never allow filtering to hide upstream
grounding/category errors. Report per-query outcomes and overall, split,
category and split/category metrics with denominators and uncertainty limits.
Assess approved test targets against the test partition, not the mixed overall
average. Compare runs on the same complete tasks; log every failure/exclusion.

CPU/GPU/RAM, latency, model-loading time, storage, embedding/caching cost and
annotation effort need an intended-machine measurement plan. Resource budgets
are **PENDING intended-machine evidence**, with no invented numeric limits.
Current host inventory is evidence about an accessible host only. Record exact
device/software, warm versus cold runs, batch size, repetitions, timing method,
peak-memory method and missing measurements. No engineering fixture can pass a
model RAM or latency budget. Failed runs need reasons and remain unscored;
missing resource values remain null with reasons. Define the final repeated-run
and group-aware uncertainty analysis before test sealing.
