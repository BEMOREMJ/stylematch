# STYLEMATCH-001C development retrieval protocol

Recorded 14 November 2026 (Africa/Nairobi), before computing benchmark scores.
The user authorized this stage on the confirmed local Windows laptop. The final
evaluation contract remains draft, unapproved and unfrozen. No final-test inputs,
outfit generation, training, external photo inference or paid processing enter
this comparison. The versioned settings are in
[`configs/001c-development.json`](../configs/001c-development.json).

Use the accepted 001B labeled manifest, its label audit and the confirmed prepared
images/crops. Re-run the documented labeled check and require 13 tasks, 13 crops,
69 exhaustive candidate grades, 10 matchable and 3 no-match tasks, including the
owner-confirmed task-004 correction. Preserve all pilot files. Store an exact
input-hash/protocol/lock/source snapshot privately before scoring.

## Comparisons recorded before results

1. Category-only: a fixed seeded uniform permutation of eligible item IDs per
   task. Also report each task's eligible N, acceptable R and exact expected
   uniform-order Hit@3: `1 - C(N-R,min(3,N))/C(N,min(3,N))`, with an impossible
   numerator combination treated as zero. No-match tasks have no retrieval
   metric; the chance of an acceptable hit is zero. Flag N <= 3, where returning
   the whole eligible pool makes matchable Hit@3 automatic. The random seed is
   fixed before scores, never selected for a favorable ordering.
2. Assisted rule baseline only with independent human attribute observations.
   Unknown attributes or filenames cannot be replaced with relevance-derived
   attributes. Report a skip if no such annotations exist.
3. One officially verified small pretrained image encoder, chosen before results.
   Use its documented image preprocessing, remove the classifier, normalize the
   feature vectors and sort category-eligible candidates by cosine similarity.
   Use the same garment embeddings for full inspirations and human crops.
   Source filenames, labels, no-match decisions and notes do not enter the
   encoder or scoring function. Item IDs only break exact score ties.

Primary comparisons have no abstention and return the full eligible ranking;
the evaluator truncates to each requested k. For secondary abstention, use one
shared cosine threshold for both views on the fixed -1.00 to 1.01 grid, step
0.01. Accept iff top similarity >= threshold; otherwise return no predictions.
Select the threshold minimizing mean balanced error
`0.5 * (false acceptances / 3 + false rejections / 10)` across both views; ties
prefer greater mean coverage, then the lower threshold. Clearly mark this as
**development-tuned using these same labels**, not calibrated or held-out evidence.
The primary paired crop comparison does not depend on this threshold choice.

## Metrics, resources and failures

Use the existing evaluator and its semantics unchanged: paired per-task and
aggregate Hit@3, Recall@3, nDCG@5; raw and validated grounding/category/duplicate
errors; coverage; false acceptances out of 3 and false rejections out of 10.
Keep both occluded blue-jorts tasks and their notes. No post-score exclusions.
Wilson intervals assume independence and are descriptive for this correlated
single-wardrobe pilot; no population or final-test performance claims follow.

CPU float32, batch 1, 2 intra-op and 1 inter-op threads, eval/inference mode.
Use one fresh worker process. Record imports/model-load time and the first
decoded/preprocessed/encoded image as process-cold inference, without claiming
an empty OS filesystem cache. Record wardrobe-cache and unique-query embedding
costs. Then measure three warm decode/preprocess/encode/score repetitions for
each task and view with the garment cache reused. Record individual timings,
mean, median and p95; count repeated full inspirations explicitly. Use
`perf_counter_ns` and Windows `GetProcessMemoryInfo.PeakWorkingSetSize` for process
peak resident RAM. RAM includes imports/model/cache and is not incremental model
memory. Do not report baseline-to-neural speedup from incomparable boundaries.
GPU execution is absent; peak VRAM is null with a reason. Record download and
installed/cache storage separately. Failed attempts stay in a private ledger;
failed model runs are unscored. Null resource measurements need explanations.
No latency/RAM budget or human annotation-time estimate is invented.

## Privacy and stage boundary

Committed artifacts contain reproducible code, configuration, synthetic tests
and methodology only. Keep photographs, crops, labels, model files, embeddings,
input fingerprints and per-task/aggregate private results in ignored paths.
Personal data must never enter download requests or model telemetry. Download
public dependencies/weights separately; inference loads a local verified weight
file with network disabled and no remote code. The handoff in chat may report
the requested development results. Stop after this comparison; the final study
requires its own approval, custodian, sealed inputs and uncertainty plan.

## Reproduction on the confirmed Windows laptop

From the clone root in PowerShell, with the accepted private pilot present:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'
uv sync --locked --extra benchmark
uv run --locked --extra benchmark python -m stylematch.pilot check --pilot data/pilot-02 --dataset dataset-labeled-01.json
uv run --locked --extra benchmark python scripts/download_encoder.py --output models/mobilenetv2-onnx-001c
uv run --locked --extra benchmark python -m stylematch.encoder_worker --smoke --weights models/mobilenetv2-onnx-001c/mobilenetv2-12.onnx --output data/001c-smoke-01
uv run --locked --extra benchmark python -m stylematch.benchmark --pilot data/pilot-02 --dataset dataset-labeled-01.json --weights models/mobilenetv2-onnx-001c/mobilenetv2-12.onnx --output data/001c-comparison-01
uv run --locked --extra benchmark pytest
```

The public download command is the only model-network step. Use fresh output
paths; downloads and comparisons refuse overwrites. Reuse a previously verified
weight directory by skipping its download, without deleting it. The worker
loads local ONNX graphs with CPUExecutionProvider and Python network audit blocking. Omit
`--weights` to produce baseline-only results if no encoder is feasible.
Dependencies are optional; ordinary evaluator/preparation use does not need
the benchmark extra. On unsupported non-Windows/non-CPU platforms, choose a
separate verified dependency plan rather than silently substituting hardware.

Private outputs include pre-score input/protocol/source/lock bindings, the
category expectation and per-task candidate counts, model input spec without
judgments, reusable embeddings and pre-threshold scores, raw/validated evaluator
reports for each view/abstention setting, a complete threshold curve, paired
task details with occlusion notes, process resource traces, failures and a
comparison summary. All randomization and threshold tie-breaks are explicit.
The worker smoke check is synthetic; it is not clothing-quality evidence.
