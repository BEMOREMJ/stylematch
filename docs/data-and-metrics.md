# Data and metric contract, version 1

The executable definitions are in `stylematch/contracts.py`. Unknown fields and
type coercions are rejected. Dataset and run documents require `schema_version: 1`;
reports use `report_schema_version: 1`. Future incompatible changes need a new
version and reviewed migration. The checked-in synthetic JSON is a complete
example, not a real dataset. JSON schemas can be obtained from
`Dataset.model_json_schema()` and `Run.model_json_schema()` when needed.

## Identities and manifests

| Entity | Required information |
| --- | --- |
| Wardrobe | Unique wardrobe ID, pseudonymous person ID, development/test partition |
| Garment | Compound `{wardrobe_id, item_id}` reference, category, image IDs |
| Image | Unique image ID and relative path, lowercase SHA-256, kind, partition, provenance, permission reference, permitted use, capture/source groups, crop parent if applicable |
| Query | Unique task ID, active wardrobe, inspiration image, component category, partition, optional human crop |
| Canonical judgment | Query, reviewer ID, no-match flag, uncertainty flag, notes, exhaustive candidate grades |
| Ranking | Query ID and ordered predictions, each with compound item reference and optional finite score |
| Run | Run/dataset IDs, exact dataset-file SHA-256, completion/failure status and reasons, model/checkpoint/revision/preprocessing/lock metadata, threshold and development-only selection declaration, resources, rankings |

Item IDs may repeat in different wardrobes. Membership is always resolved by the
compound reference. Wardrobe, image, query, compound item and canonical judgment
IDs are unique. Item images must exist, have garment kind and share the wardrobe
partition; an image cannot be assigned to multiple items. Query/crop images must
exist, have the appropriate kind, and match their partition and parent. Crops
inherit capture/source groups. Image paths are normalized relative POSIX paths;
absolute, drive, UNC and traversal paths are rejected. Optional file verification
rejects symlink escapes and verifies the SHA-256 of exact bytes.

Every image requires both capture and source groups. Related captures, edits and
crops must use the same groups. A SHA-256, capture group or source group appearing
across development/test is an error, including for unused manifest images. Each
wardrobe has one partition. Person overlap is allowed and reported as the actual
list of pseudonymous IDs shared between partitions. Shared people are not
independence evidence. Hashes do not detect all near-duplicates; human auditing of
unrecorded relationships remains necessary.

Each query has exactly one canonical, resolved human judgment. Grades must cover
**every** item in the active wardrobe's requested category, with no other items.
An empty eligible pool has an empty grade list and must be labeled no-match.
Missing labels fail evaluation; they never become negatives. Provisional or
disputed labels may be recorded with `uncertain: true`, but cannot be scored.
Independent reviewer records and adjudication history stay in private labeling
records; the evaluator consumes their final canonical judgment.

| Grade | Meaning | Relevant for Hit/Recall? |
| --- | --- | --- |
| 0 | Unacceptable | No |
| 1 | Partial resemblance, insufficient to recommend | No |
| 2 | Acceptable | Yes |
| 3 | Strong recreation | Yes |

`no_match` is true exactly when no eligible candidate has grade 2 or 3. Grade 1
can occur in a no-match task. A conflicting flag or unresolved uncertainty fails
evaluation. All complete runs explicitly return one ranking per query, including
an empty list for abstention. Missing, duplicate or unknown ranking query IDs are
errors. Failed runs can have partial rankings but are reported as unscored, with
failure reasons; they are never averaged into successful runs.

## Raw and validated output

The ordered prediction list is the run's **already accepted** recommendation
output after its declared threshold decision. The evaluator does not infer score
calibration or apply the threshold again. Empty lists are abstentions. Scores are
optional finite diagnostics; ordering in the list is authoritative, including
ties. Model runs must separately preserve pre-threshold scores privately so
development threshold decisions can be audited.

The raw report counts every prediction slot before filtering. An unknown compound
ID or an ID outside the active wardrobe is invalid. A globally known item with
the wrong category is a category violation, even when also cross-wardrobe. These
error counts can overlap. A duplicate is each occurrence after the first of the
same compound ID. Duplicate entries are not fatal to an entire raw run: they
occupy rank positions, contribute no repeated gain and are reported explicitly.

Deterministic validation removes unknown IDs, cross-wardrobe IDs, wrong categories
and repeated IDs, preserving the order of remaining first occurrences. Validated
lists are the only surfaceable recommendations. They can become empty. Raw and
validated metrics, prediction counts, violation rates and per-query rankings are
always retained together. Never report only the improved filtered metric. Zero
surfaced invalid/cross-wardrobe IDs is a mandatory grounding rule; zero surfaced
category violations is also required. These are invariants, regardless of
provisional performance thresholds.

## Metric definitions

For a query, let `R` be the set of eligible items graded 2 or 3; let `L[:k]` be
the first k prediction slots. Invalid, wrong-category and repeated slots have zero
gain. They still occupy their original positions in the raw metric.

- **Hit@k** = 1 if `set(L[:k])` intersects `R`, else 0. Report the mean over
  matchable queries only.
- **Recall@k** = `|set(L[:k]) intersect R| / |R|`. Report the macro mean over
  matchable queries, giving each task equal weight.
- **Graded nDCG@k**: `gain(g) = 2^g - 1`; rank `r` starts at 1 and has discount
  `1 / log2(r + 1)`. `DCG@k = sum(gain(g_r) / log2(r + 1))`. `IDCG@k` uses all
  eligible labeled candidates sorted by grade descending, truncated to k.
  `nDCG@k = DCG@k / IDCG@k`; report the macro mean over matchable tasks. Grade 1
  receives gain 1 despite being insufficient to recommend. This distinction is
  deliberate. No-match tasks, including those with grade-1 items, are excluded.
- **No-match false acceptance** = no-match tasks with a nonempty recommendation
  list / all no-match tasks.
- **Matchable false rejection** = matchable tasks with an empty recommendation
  list / all matchable tasks. Recommending an unacceptable item is an acceptance
  error reflected in retrieval metrics, rather than an abstention.
- **Recommendation coverage** = tasks with a nonempty list / all evaluated tasks.
- **Invalid-ID rate** = invalid slots / all prediction slots, before or after
  validation respectively. Category and duplicate rates use the same slot
  denominator and their corresponding violation counts.

All k values must be distinct positive integers. A short list uses its available
slots; no padding or invented predictions. Empty lists score zero on matchable
Hit/Recall/nDCG and count as false rejection. Queries with `|R| = 0` must be
no-match; their retrieval metrics are null and their count is reported separately.
Any metric with an empty denominator is null, with denominator 0, never a perfect
score or a NaN. No-match rates and coverage do not depend on k; they inspect the
whole accepted recommendation list supplied by the run.

Reports include overall, partition, category, and partition-by-category values,
sample counts and per-query details. Proportions have Wilson 95% intervals using
`z = 1.959963984540054`. These intervals assume independent Bernoulli trials;
shared people, inspirations and captures can violate that assumption. They are
descriptive, not proof of population performance. Recall/nDCG means have counts
but no estimated interval in this slice. A later analysis plan must choose a
group-aware uncertainty method before final-test inspection.

## Run and resource reporting

Record exact model checkpoint/revision, preprocessing, dependency lock hash,
threshold and development-only selection provenance. Fixture metadata says
explicitly that no model exists or ran, and its lock hash is null. The run's
dataset SHA-256 binds the exact manifest bytes; the CLI verifies it. The Python
API allows this external-byte check through its `dataset_sha256` argument.

Wall time in milliseconds, peak RAM and peak VRAM in bytes are nonnegative or
null. Each null needs a specific `missing_reasons` entry; measured fields cannot
have a missing reason. Unknown is distinct from measured zero. Device identity is
required. The future run protocol must record warm/cold timing, model loading,
batch size, thread settings, repetitions, seeds, code commit and measurement
method alongside the run. No limits or model performance are established by
these fixtures. Execution failures, missing measurements and invalid manifests
must appear in the study ledger; repeated successful runs cannot erase them.
