# STYLEMATCH-001 draft evaluation contract

Status: **DRAFT / UNAPPROVED / NOT FROZEN**. This document defines a proposed
final-study experiment. The owner separately authorized 001B development
preparation and local use of their own garment photos. Handling/inspiration
decisions and accepted human labels are recorded privately. On 2026-11-14 the
owner authorized the development-only [001C comparison](development-benchmarks.md),
including one verified local encoder. Final-test collection, contract freeze and
STYLEMATCH-002 remain outside that authorization. The numeric final-study gates
below are still provisional; the 001C protocol does not approve them.

The [001E part 2 amendment A1](#001e-amendment-a1--owner-review-draft) below is
the current **DRAFT** for a smaller, fresh-source assisted comparison. It records
the completed development choices without approving collection or replacing
this contract's safeguards. Earlier scale/comparison placeholders remain
historical proposals; if Mark approves A1, its explicit study-specific choices
take precedence over conflicting earlier proposals.

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
Final-study reviewer availability and disagreement sampling remain pending;
do not treat one person's repeated labels as independent reviewers.
For the initial 001B development pilot, the owner is the one actual reviewer.
Uncertainty remains explicit; repeated passes can inform within-reviewer
consistency only. Independent review/adjudication for the final study remains
pending, rather than being claimed for this single-reviewer pilot.

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

## Proposed comparisons and development implementation

001C implements category-only and paired full-image/crop retrieval under its
separate recorded development protocol. The assisted rule comparison requires
independent human attributes. Hybrids and final-study designs below remain proposals.

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
No checkpoint was selected, downloaded, wrapped or run in 001A. See the separate
[001C candidate decision](001c-candidate.md) for the first authorized local encoder.

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
are **PENDING intended-machine measurements and agreement**, with no invented limits.
The owner confirmed the inventoried laptop as the initial target in 001B; no model
measurements have occurred. Record exact device/software, warm versus cold runs,
batch size, repetitions, timing method,
peak-memory method and missing measurements. No engineering fixture can pass a
model RAM or latency budget. Failed runs need reasons and remain unscored;
missing resource values remain null with reasons. Define the final repeated-run
and group-aware uncertainty analysis before test sealing.

## 001E amendment A1 — owner review DRAFT

**17 November 2026, Africa/Nairobi. DRAFT / UNAPPROVED / NOT FROZEN.** Objective:
on fresh inspiration sources, does human-confirmed tagging improve the first
suggested garment enough to justify its effort versus MobileNetV2 crop retrieval?
Machine-readable proposals: [001e-heldout-draft.json](../configs/001e-heldout-draft.json).
No held-out collection, inference or scoring is authorized by this preparation.
Stage advancement belongs to the master roadmap.

**Choose one design; recommend A first.** Both use 24 independent source/looks,
one image per source, with an **estimated** 48 supported components: 24 tops,
18 bottoms, 6 outerwear (not quotas). Each source may supply one component per
category, hence 24–72 tasks. A source means an original look/shoot cluster, not
a website/domain or URL: related shots, edits and reposts count together. Human
relationship/near-duplicate review is necessary; hashes cannot prove independence.

| Collection option | Garments / category pools | New work | Estimated exhaustive grades |
| --- | --- | --- | --- |
| A: known wardrobe, entirely fresh sources | Existing 15: 6 tops / 6 bottoms / 3 outerwear; exact locked photos/tags | 24 looks, ~48 crops and query tag sets; no new wardrobe tags | 24×6 + 18×6 + 6×3 = **270** |
| B: independently owned second wardrobe, fresh sources | Proposed 18: 8 tops / 6 bottoms / 4 outerwear | Same look/query work, plus permission, 18 garment captures/preparations and tag sets | 24×8 + 18×6 + 6×4 = **324** |

Counts assume the category mix above. Actual grades are `sum(category pool size
for every retained task)`; if all three categories occur on every look, totals
are 360 (A) or 432 (B). At 2 min/accepted-source selection, 20 s/crop, 20 s/query
tag set, 15 s/candidate grade, and 20% repeat-review/administrative allowance,
planning effort is **~3.0 h A** and **~4.1 h B**. B additionally assumes 2 min/new
garment capture/preparation and 30 s/garment tagging. These are estimates, not
measurements; difficult cases, screened exclusions, recruitment and permission
work can add unbounded time and must be logged. A's original wardrobe-tagging
time remains **unknown**, never estimated retrospectively. B setup is timed.
A supports only new looks for this known wardrobe. B requires a different
actual owner/person and wardrobe, explicit photo/use permission and no shared
garments/captures; one additional owner does not establish population performance.

**Split implementation.** Current `validate_dataset` assigns a wardrobe one
partition and rejects cross-partition SHA-256/capture/source overlap, including
unused images. It cannot represent A as one mixed development/test manifest.
Keep that validator unchanged. Use separate immutable development and test-view
manifests; A's test view copies the locked wardrobe records/images with partition
`test`, preserving IDs, categories, image metadata and exact photo/tag bytes.
Never repartition the accepted development files. A canonical neutral-ID garment
tag registry is projected from the accepted human reference, validated and hashed
before collection; both views bind to that same registry. B registers new owner,
wardrobe, garment and image identities. `audit_holdout_split` in
[`stylematch/holdout.py`](../stylematch/holdout.py) validates both manifests and
rejects all cross-manifest overlap except A's explicitly identical registered
garment images/tags. Inspiration/crop hashes, groups and IDs must be fresh against
*all* development images; a group shared with an inspiration can never be waived.
The audit distinguishes intentional person/wardrobe/garment overlap from leakage.
It must run before future inference, in addition to normal file/hash checks.
Ownership, permission and near-duplicate review remain manual recorded checks.

**Frozen methods.** Pin delivered part 1 commit
`4e49796614541c2a808caecfb3d2811976a8c82a`, its
[`001e-development.json`](../configs/001e-development.json), vocabulary/guide and
[`001c-encoder.json`](../configs/001c-encoder.json). Primary: **human-assisted
attribute-only versus MobileNetV2 human crop**, identical category-eligible pools,
no abstention. Retain category `Random("104729:"+query_id)` permutation of sorted
compound IDs. Attribute score = exact known type/color/pattern agreements / 3;
missing/unknown (including unknown/unknown) gives zero; keep all three fields,
denominator and compound-ID ties, with all-zero scores falling back to ID order.
No relevance, source names, notes or SmolVLM text enters ranking. CPU FP32
MobileNetV2-12 revision `23a2a25eaaa6fcd61865414c8a1acf13dda66b7a`, checkpoint
SHA-256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`;
RGB bilinear short side 256, centered 224, existing ImageNet normalization,
1280-D final pooled/L2-normalized features, same multi-image pooling, batch 1,
2 intra-op/1 inter-op threads. No model/rule changes, hybrid arm or field selection.
Separately apply **only original crop cosine >=0.60**. Also rerank the same
accepted pools with human attributes, labelled **ordering only**; FA/FR/coverage
are necessarily shared. Do not threshold attribute scores. This assisted
abstention variant still incurs embedding cost. Threshold is development-tuned,
not held-out calibrated; no tuning on test outcomes.

**Collection passes, rankings hidden.** Mark freezes a dated ordered queue of up
to 36 permitted fresh source clusters in ordinary selection order, without
searching for wardrobe matches or negatives. Keep source/permission and related
look audit locally. Pass 1 takes the first 24 eligible independent sources:
identify every supported visible component, crop once per category, record
occlusion/uncertainty and exclusion reasons before relevance grading. Retain
partially occluded identifiable components and tag unknown fields; exclude only
unreadable/out-of-scope/undistinguishable targets by the pre-recorded rule. Do not
drop difficult tasks after model outputs. Stop at 24 eligible sources, 36 screened
sources, or 14 calendar days after approval, whichever comes first. Record every
screened exclusion. Never extend collection to reach favorable outcomes/negatives.
Pass 2 tags isolated wardrobe images (B) and cropped query components; all three
fields use the existing guide. Lock tags before grading. Measure crop and query
tag active time separately, including corrections, navigation and explicit
unknowns; pause timers on interruptions, log missing timers as unknown. Record
source-selection, garment capture/preparation, garment tagging and grading time
separately. Use a per-task stopwatch/sidecar ledger (`subject_id`, `stage`, active
seconds, corrections, missing reason); the old aggregate review timer alone
cannot establish per-query percentiles. For B the second owner confirms permission/garment identity/tags;
record that confirmation effort too.

Pass 3, at least 24 h after query tagging, has Mark grade **every** eligible
candidate 0/1/2/3 using the existing rubric, with candidate order seeded/randomized,
tag values, method identities, scores and rankings hidden. Multiple grades 2/3
are retained; no-match means zero 2/3 grades, never a quota. Recheck a seeded
20% of source clusters (round up: 5 of 24) in a separate hidden-order pass;
preserve original/revised labels and reasons. Resolve uncertainty before sealing;
still-unresolved tasks remain explicit, unscored and count against evidence
floors. Preserve them in the collection/exclusion registry; before any predictions,
the custodian freezes a scorable manifest of resolved tasks only for both methods.
Do not pass unresolved labels to the strict evaluator or replace them with negatives.
Mark is the proposed sole canonical reviewer for either design; repeated
passes do not establish independent review, and memory/subjectivity remain limits.
Presentation uses `Random` shuffles of sorted neutral IDs with the exact stage
seeds in `presentation_randomization` in the draft config; recheck selection is
the first `ceil(0.20*N)` shuffled eligible sources. Assign IDs before these passes,
preserve the presented orders, and never reshuffle based on grades.

**Outcomes and uncertainty.** Primary is paired task-weighted matchable
`Delta Hit@1 = (attribute gains - losses) / matchable task count`, without
abstention. Print each method's usable-first count, gains/losses/ties and
denominators; preserve multiple acceptable items. Secondary Hit@3, Recall@3 and
graded nDCG@5 use existing evaluator semantics (no-match metrics null); report
category, pool size and occlusion, flag pools <=3. Report no-match FA, matchable
FR and coverage separately with task *and source* denominators. Raw and validated
errors remain visible; zero surfaced invalid/foreign IDs and category violations
are mandatory, and any raw violation blocks a successful conclusion pending an
audited fix/fresh-run decision, never silent filtering.

For primary 95% uncertainty, resample whole matchable-containing source clusters
with replacement (10,000 draws, seed 20261117), carry all their components and
compute the task-weighted ratio each draw; percentile indices
`floor(p*(9999))`, p=0.025/0.975. Never bootstrap components independently.
Report source-balanced mean delta and leave-one-source-out sensitivity; a sign
change signals concentration. Secondary paired ranking metrics use the same
cluster draws. Conditional FA/FR intervals resample whole sources containing
the applicable task type; coverage resamples all sources. Task-level Wilson
intervals from the old evaluator are descriptive only, not the decision interval.
Within-source dependence is retained; shared owner/wardrobe limits generalization.

**Proposed decisions, all awaiting Mark's approval.** Require >=30 resolved
matchable tasks from >=20 sources, paired Hit@1 improvement **>=10 percentage
points**, cluster-95% lower bound **>0**, gains on >=5 sources and positive delta
after dropping any one source. This means at least one extra usable first choice
per ten matchable requests, supported beyond a single look; it is a feasibility
criterion, not a powered/population claim. Interval spanning zero means
inconclusive; nonpositive point effect means no observed benefit, not equivalence.
For abstention require >=10 no-match tasks across >=8 sources even for a limited
observed-rate conclusion; propose observed FA<=10% and FR<=20%. With these small
counts even zero errors gives a wide upper bound: do not claim a proven <=10%
population risk. Insufficient type/source counts mean that arm is inconclusive;
insufficient ranking counts mean the primary conclusion is inconclusive. Report
what was collected, do not top up using outcomes; a later cohort needs a fresh
approved protocol and cannot silently rescue this test.

Propose query-tag median **<=20 s**, p90 **<=40 s** (less than half a minute for
typical incremental tagging); measure crop median **<=30 s**, p90 **<=60 s**
separately as shared interaction overhead. Percentiles use nearest-rank
`ceil(p*n)` on active per-task totals; missing measurements prevent an effort
pass. B: garment tagging **<=15 min total**, new wardrobe setup including capture
and preparation **<=60 min total**, a one-off setup burden; report amortization
only with an explicit assumed number of future queries. A's sunk tagging cost is
unknown; only prospective query effort can pass. Report ranking/effort/resource
decisions separately: beneficial but slow tagging is a mixed result, not success.

On the confirmed laptop propose CPU worker peak working set **<=1 GiB**, cold
query in a fresh worker using a prebuilt wardrobe-vector cache, including
imports/load/cache read, **<=5 s**, warm decode/preprocess/embed/rank p95
**<=1 s** with wardrobe cache reused, and one-time wardrobe-cache creation
**<=10 s**. These are proposed interaction/headroom limits, not observed results.
Use one fresh worker, `perf_counter_ns`, Windows process peak working set, one
primary quality pass, then three warm timing repeats/task (no score-driven retries).
Report parent-process memory separately, versions, background load, all samples
and failures; OS cache is uncontrolled, VRAM unused. Attribute-only timing includes
lookup/scoring; masked ordering includes encoding. Missing resource measurements
mean unknown, never a pass. Zero spend, no hosted inference or new model download.

**Custody, seals and release.** Propose Mark as named label custodian and sole
reviewer; he necessarily sees labels while making them. If separate custody is
required, nominate someone *before approval*; do not claim independent custody
for Mark's self-review. Locally separate label-free input/pixel/tag manifests
from relevance files, uncertainty/review notes and label keys, all Git-ignored.
Freeze approval ID/date, design/claim, exact protocol text/config hashes, source
registry/order/exclusions, owner/permission audit, split/intentional-overlap audit,
manifest/image/crop hashes and boxes, canonical tag/reference/label hashes,
timing/review history hashes, candidate/code commit, dependency lock, encoder and
derived-graph hashes/revisions, preprocessing/seeds/threshold and device plan.
Original development snapshots stay immutable. Test labels stay in a local
custodian-controlled encrypted archive or verified restricted directory outside
the worker input root; record who can access what and each unlock. Hashes are
tamper evidence, not access control. Without verified controls call this a
procedural seal and disclose the limitation.

Before the first real inference, Mark must approve the exact choices and freeze
all records; the input-only runner verifies seals/audits without reading test
relevance. Freeze complete predictions for **all** methods, failures and resource
logs with hashes/timestamp before custodian releases labels. No score/rank views
until that freeze; first quality scores only after canonical label release.
No reruns/tuning after inspection; a material error needs a logged decision about
a fresh holdout. This preparation supplies pure cross-manifest and primary
source-bootstrap helpers plus synthetic checks, **not** an approved collection
or held-out inference runner. The existing comparison CLI remains development-only.

**Owner decisions still open:** A or B/claim; accept or amend collection caps and
category workload; approve numerical benefit/effort/resource/evidence criteria;
confirm Mark or name reviewer/custodian and access controls; for B confirm an
independent consenting owner; then approve an exact protocol/freeze identifier.
Changing a proposal must happen before collection; no real holdout is created here.

Reproduce draft checks with `.venv/Scripts/python.exe -m pytest tests/test_holdout.py -q`
or run the full suite. Fixtures exercise locked reuse, forbidden source overlap,
independent ownership, label-free input audit followed by exhaustive label checks,
multiple acceptable items/no-match, and source-level uncertainty. No photos or
real held-out labels are needed.
