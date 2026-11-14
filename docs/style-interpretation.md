# STYLEMATCH-001D development interpretation

001D uses the accepted pilot-02 development data only. The final contract remains
open and the final test untouched. Hybrid reranking is deferred to 001E.

Before creating `codex/stylematch-001d`, `git merge-base --is-ancestor
3b165c5eb8b8d7a84e6c7c1472542e1e1f101253 HEAD` succeeded; HEAD was exactly that
delivered 001C commit. The initial working tree was clean. Existing accepted
import, review and benchmark files are read-only to this workflow. A private
SHA-256 preservation ledger covers them before and after work.

## Reference review

```powershell
.venv/Scripts/python.exe -m stylematch.interpretation review --pilot data/pilot-02 --output data/interpretation-001d-01/review-01
```

Output directories must be fresh, ignored and untracked. `review.html` is a
self-contained offline image-by-image workflow. It embeds only neutral IDs,
sanitized pixels, definitions and empty fields. The private `mapping.json`
retains source binding outside the display. There are no old human attributes,
grades, model outputs, category hints, identifying names or retrieval scores.
The vocabulary and hypothetical worked example are defined in
`stylematch/interpretation.py`; unknown is a completed answer, blank unfinished.
Color follows the dominant visible area; use multicolor when no color occupies
more than roughly half. Infer nothing hidden. Label each field independently.
If multiple components cannot be separated, ambiguous fields stay unknown.

Mark alone supplies actual labels. The timer is optional: it accumulates only
while started and the page is visible; pause for breaks. It does not measure
off-page annotation or guarantee attentive time. Saving exports a JSON backup;
resume accepts only the same bundle. Keep its actual measurement method with
the reference; absent measurement is null, never estimated or zero-filled.

Move the downloaded `001d-attribute-labels.json` into the private review folder.
Before revealing any predictions, validate completion, vocabulary and membership
and preserve a new immutable-by-convention reference snapshot:

```powershell
.venv/Scripts/python.exe -m stylematch.interpretation import-reference --review data/interpretation-001d-01/review-01 --labels data/interpretation-001d-01/review-01/001d-attribute-labels.json --output data/interpretation-001d-01/reference-01.json
```

No overwrites, inferred labels or unresolved blank values are accepted. A single
owner's repeat review is not independent reviewer evidence.

## Prespecified experiment

Commit-controlled [protocol](../configs/001d-protocol.json) records the exact
prompt, views, deterministic settings, scoring and resource procedure before
pilot inference. Vocabulary matches the human guide. One fixed candidate and
prompt; no score-driven retries or substitutions. Reference labels are never
model inputs. The supervisor prepares neutral, resized image payloads; the native
runtime receives only inline pixels and the fixed prompt. All photo decoding and
inference stay on this laptop. Download tooling reads no pilot images.

For each field report correct / human-known total, model answered / human-known
total, correct / answered human-known, answered / all, and assertions / human-
unknown total. All ratios include counts and percentages; empty denominators
have null percentages. Strict invalid JSON/schema outputs are retained as
failures and count as unanswered and incorrect on known cases. An asserted
value on a human-unknown case is a caution count, not proven model error.
Report separately all 28 images, 15 wardrobe images, 13 crops, and retained
occluded task-009/task-010. Inspect those two individually after reference lock.
Raw responses, parse errors, normalized predictions and descriptions remain
ignored and private. Description factuality requires Mark's spot-check and is
reported separately; attribute scores do not establish description grounding.

Loading is startup through healthy server (both weights supplied). Cold means
first request after process start, not a flushed OS file cache. Warm repeats the
same first input with prompt caching disabled. End-to-end request timings,
native server peak working set, memory headroom, failures and guard stops are
measured; estimates stay explicitly separate. Limits are development resource
guards, not final acceptance gates. No unmeasured cost or feasibility claim.

## Candidate evidence

Only SmolVLM-256M-Instruct Q8_0 is selected for a local smoke test.
[Pinned config](../configs/001d-model.json) lists exact publisher revisions,
sizes and SHA-256. Official [upstream model card](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/blob/d039ab0d4b9311b617e8ffec1d06c8464364aeb3/README.md)
and [ggml-org conversion](https://huggingface.co/ggml-org/SmolVLM-256M-Instruct-GGUF/tree/b9e4379657e1450d04d02eec8e345667265b0a00)
declare Apache-2.0; ggml-org links this upstream but does not publish the exact
upstream conversion commit, so upstream revision is a documentation snapshot,
not a claim of conversion provenance. Local files are never redistributed.

The two Q8_0 files are 175,054,528 + 103,769,856 = 278,824,384 bytes; both are
needed. Runtime is official [llama.cpp b7350 Windows CPU x64](https://github.com/ggml-org/llama.cpp/releases/tag/b7350),
commit `4dff236a522bd0ed949331d6cb1ee2a1b3615c35`, MIT, archive 18,612,597 bytes.
Total download 297,436,981 bytes, excluding small documentation. Publisher API
LFS metadata and GitHub asset digest are preserved privately. The downloader
verifies every size/hash and preserves failed partial downloads and ledgers.
No PyTorch, model-hub inference or remote model code is used.

The pinned [runtime documentation](https://github.com/ggml-org/llama.cpp/blob/b7350/docs/multimodal.md)
lists SmolVLM-256M, local `-m`/`--mmproj` loading and CPU projector support.
Windows x64 CPU release exists; successful synthetic local loading must establish
actual DLL/CPU compatibility. CPU backend, two threads, no GPU layers and no
projector offload are required. Native runtime serves loopback only; it is not
an OS network sandbox. No URLs, tools or download switches enter inference.
No claim of firewall-level isolation is made.

Estimated process RAM is roughly 1–2 GiB for this small quantized model,
2048-token context and 512-pixel input, inferred from 266 MiB weight storage
plus runtime/KV/vision buffers, not a publisher Windows measurement or guarantee.
At preparation, the owner-confirmed i7-6600U host had 15.88 GiB total RAM and
about 2.78 GiB available; available memory changes with other apps. A 1.5 GiB
peak-process guard and 750 MiB available-memory floor constrain this pilot.
The actual smoke test determines feasibility; no prediction of speed on this
CPU is asserted. The small model may hallucinate, fail JSON, confuse garment
construction or lose tiny patterns in resizing. Even a successful run establishes
only development evidence for this owner's photos and confirmed crops.

## Execution and description check

```powershell
.venv/Scripts/python.exe scripts/download_vlm.py --ranged
.venv/Scripts/python.exe -m stylematch.vlm_worker --smoke --output data/interpretation-001d-01/smoke-01
# After Mark's reference is imported:
.venv/Scripts/python.exe -m stylematch.vlm_worker --pilot data/pilot-02 --review data/interpretation-001d-01/review-01 --reference data/interpretation-001d-01/reference-01.json --output data/interpretation-001d-01/run-01
```

Use a fresh output path on every attempt. Only small public publisher requests
occur in the downloader. Ranges are one MiB with eight workers and three attempts;
the per-artifact transfer ceiling is ten minutes. Complete prefix chunks from a
failed full response may be reused, but overlap and final size/SHA-256 must agree.
Partial downloads and failed attempt ledgers remain local. `--runtime-only` can
prepare the same official runtime independently while weights are pending.

After pilot inference open `run-01/description-review.html`. Mark saves the
separate description review and supplies its local path. Then preserve it:

```powershell
.venv/Scripts/python.exe -m stylematch.interpretation import-descriptions --run data/interpretation-001d-01/run-01 --labels data/interpretation-001d-01/run-01/001d-description-checks.json --output data/interpretation-001d-01/description-reference-01.json
```

The scorer retains partial/unattempted inference cases in the full denominators
as execution/schema failures. A resource stop does not justify removing images.
If model installation or the smoke run hits a documented blocker, stop 001D
there, preserving the completed annotation workflow and any owner labels.
