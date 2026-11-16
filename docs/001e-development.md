# STYLEMATCH-001E part 1 development comparison

Recorded 16 November 2026, Africa/Nairobi, before computing new comparison
results. Both required commits (`e3ec9c5` final 001D and `3b165c5` delivered
001C) were verified as ancestors of the clean starting HEAD. Before creating
`codex/stylematch-001e`, private availability checks validated the accepted
pilot-02 labels, completed 001D reference, image hashes, neutral view mapping,
source-label binding and saved 001C candidate pools. There are 15 garments,
28 reference images (15 wardrobe, 13 crops), 13 tasks, 69 judgments, 10 matchable
tasks with exactly one acceptable item each, and 3 no-match tasks. The prior
107-file preservation ledger passed; an additional private snapshot preserves
all 267 existing data/private files. Real measurements and task outputs stay
outside Git.

## Fixed rules before results

The configuration is [001e-development.json](../configs/001e-development.json).
Use the same category eligibility and all candidates, without attribute-based
filtering. Attribute-only is **human-assisted**: exact known agreement in garment
type, main color and pattern, each contributing 1/3. Unknown or missing on either
side, including unknown/unknown, contributes zero. The denominator stays three;
do not normalize by available fields. Score A is in [0,1].

The **human-assisted hybrid** uses the same attributes plus the saved crop
embedding cosine c: E=(c+1)/2 and H=0.5*E+0.5*A. E and H are in [0,1]; cosine
retains its original [-1,1] scale. These equal weights are a simple engineering
choice, not fitted or selected against the 13 tasks. Sort descending score,
then ascending compound wardrobe/item ID. With no agreements attribute-only
falls back to ID order; hybrid preserves embedding order. Missing or invalid
embeddings stop the comparison instead of silently substituting a model.

Leave one field out with its contribution set to zero; keep the denominator,
embedding weight and all remaining weights fixed. This explains changes and
does not select another rule. Attributes come only from the completed human
reference; query labels describe crops. SmolVLM raw responses and normalized
failures are never read by the ranker. Neither relevance labels nor revealing
filenames, image paths or reviewer notes enter scoring inputs.

## Evaluation and boundaries

Reuse and verify the saved category and MobileNetV2 full/crop scores, including
their image/vector/protocol bindings. Evaluate the existing seeded category
baseline, full images, crops, human attributes alone, and human-assisted hybrid
on identical pools without abstention first. Use the unchanged evaluator with
k=(1,3,5), reporting Hit@1/3, Recall@3 and graded nDCG@5 on the 10 matchable
tasks. Report paired task gains/losses, categories, both occluded components,
and three-candidate outerwear pools. Hit@1 measures a usable first suggestion
because each matchable task has one acceptable candidate. Hit@3 is automatic
for matchable pools of three. No-match ranking metrics remain undefined.

Separately retain the development-tuned 001C threshold 0.60 on original full
and crop cosine only. Apply the *crop* decision unchanged to the hybrid rankings
and label this **ordering only**. Never threshold an attribute/hybrid score at
0.60. Report FA/3, FR/10 and coverage/13. No new abstention rule is tested.

Report raw and validated invalid/foreign-wardrobe IDs, category errors and
duplicates. Measure incremental in-memory ranking time for all 13 tasks across
100 repetitions, separately from private input verification, evaluation and I/O;
report median/p95 and do not compare that to image encoding time. No new encoder
execution is needed. Human annotation effort and unmeasured incremental memory,
end-to-end interactive latency and deployment cost remain unknown. No speedup
or feasibility gate follows from ranking timings.

Use the simplest candidate supported by these descriptive development results;
report negative/mixed results and concentration. Final-test inputs are not read
or changed. The final contract remains open and stage advancement belongs to
the master roadmap. A fresh held-out evaluation needs explicit candidate,
annotation availability/effort, sealed split/custodian, relevance protocol,
abstention calibration, success/resource criteria and uncertainty decisions.

## Reproduction

Use the already installed locked environment and the preserved local inputs;
there is no download or inference step. The runner validates ancestry, private
paths, accepted labels/images, reference source and mapping, 001C registration
against its delivered commit, encoder identity, cached vector dimensions and
score/ranking reproduction (absolute score tolerance 1e-6 for float32 cache
serialization). It reuses the original saved scores, rather than replacing them
with recomputed rounded scores. It refuses existing outputs and outputs inside
any preserved input tree.

```powershell
.venv/Scripts/python.exe -m stylematch.comparison --output data/comparison-001e-02
.venv/Scripts/python.exe -m pytest -q
node tests/check_attribute_review.cjs
git diff --check
```

Optional CLI paths are `--pilot`, `--saved`, `--reference-root` and `--protocol`.
The accepted private filenames within those roots remain explicit and versioned
in the runner. It never searches for replacement labels or infers labels from
names. The benchmark extra (already installed for 001C) supplies NumPy to read
the saved cache with pickle disabled. Neither ONNX Runtime nor a VLM is loaded.

Every new run records source/configuration/dependency/input bindings before new
assisted scores, projected ranking inputs, full rankings and field contribution
breakdowns, unchanged-evaluator raw/validated reports, all paired deltas,
category/occlusion/small-pool details, repeated incremental timing samples and
a before/after preservation check. Cached comparison reports retain original
001C metadata and historical resource scope. New reports use null resource
fields with explanations; incremental timing is separate. Hybrid ordering-only
reports deliberately have no hybrid-score threshold; their metadata records the
original cosine mask.

The initial development execution and subsequent verification runs must use
fresh ignored folders. Findings and practical recommendations belong in the
private handoff and requested chat handoff, never in committed per-task outputs,
attribute labels or vectors. All existing pilot and interpretation runs remain
unchanged. These implementation checks do not approve or freeze the final
evaluation contract.
