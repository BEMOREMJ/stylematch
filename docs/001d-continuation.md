# STYLEMATCH-001D continuation — 16 November 2026

The owner completed the 28-image attribute review and provided its Downloads
path. A byte-identical copy was preserved in the ignored review folder, validated
for bundle binding, complete membership and vocabulary, and imported as the
private `reference-01.json` before predictions were shown. No owner labels were
filled or changed by tooling. Annotation time was not measured and remains null.

The same pinned SmolVLM-256M Q8_0 candidate, prompt, input views, decoding and
scoring protocol were retained. Resuming runtime ZIPs now uses the same bounded,
verified range mechanism as model files. Complete sizes and SHA-256 matched for
both model files and the Windows CPU runtime. Thus the earlier transfer blocker
was resolved without choosing another candidate. No hosted inference was used.

The synthetic CPU smoke test completed without execution/resource failures:
loading 0.771 s, process-cold request 15.336 s, warm request 15.022 s, peak native
working set 382,423,040 bytes (364.71 MiB). Both responses failed the strict
schema. This was compatibility/resource evidence, not garment-quality evidence.

All 28 pilot images completed, plus an unscored warm repeat. Actual pilot
measurements: loading 0.747 s; process-cold request 14.303 s; warm request
14.584 s; primary-image median 14.946 s; peak native working set 405,635,072
bytes (386.84 MiB); native session 452.794 s. There were no execution or resource
guard failures. RAM/latency estimates from the earlier checkpoint are superseded
by these measurements for this configuration. Python orchestration RAM is
excluded; OS file cache and normal background apps were uncontrolled. Brief
focused engineering checks overlapped a portion of the pilot run. Timings are
practical observations, not an isolated microbenchmark or final acceptance gate.

Strict schema validity was **0/28 (0%)**: wardrobe 0/15, crops 0/13, retained
occluded pair 0/2. Every primary output reached the 160-token ceiling and failed
JSON parsing. Under the prespecified whole-schema failure rule, there are no
valid field answers; correct-on-known counts are zero and accuracy among
answered known cases is undefined (0/0). Detailed per-field known/unknown
denominators, subgroup counts and resource logs remain in the private report:
`data/interpretation-001d-01/evaluation-final-2026-11-16.md`.

This establishes local execution at a small measured RAM footprint, while the
fixed structured-output configuration was unsuccessful. It does not establish
garment-attribute competence from malformed prose, independently verified description factuality,
production suitability or final-study feasibility. No prompt/decoding changes,
heuristic JSON repair, score-driven retries or reranking were performed.

Because the outputs are malformed prose, an additional owner review presents
the **unmodified raw responses**, identifies schema/token-limit status, and
pairs them with the actual resized model views. Both occluded components are
flagged. This operational review does not alter structured scoring or promote
raw claims to normalized attributes. No factuality labels are prefilled.

```powershell
.venv/Scripts/python.exe -m stylematch.interpretation raw-output-review --run data/interpretation-001d-01/run-2026-11-16-01 --reference data/interpretation-001d-01/reference-01.json --output data/interpretation-001d-01/raw-output-review-01
```

The generated local `raw-output-review-01/description-review.html` asks Mark to
flag unsupported details and uncertainty. Save its JSON and preserve it using:

```powershell
.venv/Scripts/python.exe -m stylematch.interpretation import-descriptions --run data/interpretation-001d-01/raw-output-review-01 --labels data/interpretation-001d-01/raw-output-review-01/001d-description-checks.json --output data/interpretation-001d-01/raw-factuality-reference-01.json
```

## Completed owner factuality review

The owner supplied the completed 28-item raw-text review. The original Downloads
file and a byte-identical private review copy were preserved; import validated
the bundle, item membership, decisions and required notes. The private
`raw-factuality-reference-01.json` preserves every decision and note unchanged.

| Views | Flagged | No unsupported detail found | Uncertain | No valid description |
| --- | --- | --- | --- | --- |
| All | 16/28 (57.1%) | 10/28 (35.7%) | 1/28 (3.6%) | 1/28 (3.6%) |
| Wardrobe | 3/15 (20.0%) | 10/15 (66.7%) | 1/15 (6.7%) | 1/15 (6.7%) |
| Crops | 13/13 (100%) | 0/13 (0%) | 0/13 (0%) | 0/13 (0%) |
| Occluded pair (subset of crops) | 2/2 (100%) | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) |

The owner's flags include descriptions of context beyond the component crop
and unnecessary description. These are single-owner flags on truncated raw
responses, not independently established factual-error counts. The 10 unflagged
responses still fail the structured schema; no prediction is repaired or given
attribute credit. Both retained occluded components were explicitly flagged for
describing the whole image rather than the component view.

The owner used the page's "No valid description" option once despite nonempty
raw text. The importer was corrected to accept that explicitly offered raw-review
judgment. It is preserved as an owner judgment of the response, distinct from an
absent model execution response. Structured-description imports retain their
existing absence consistency check. A synthetic regression test covers this
case; no reference decisions or scoring rules changed.

**001D interpretation evaluation is complete.** This configuration ran within
the measured resource limits but failed to produce usable structured predictions
and received flags on every component crop. Stop here; no further model runs,
prompt tuning or 001E work followed the review.

Raw responses, source labels,
normalized failures, scores, photo payloads, binaries and weights remain ignored
and untracked. All 107 original pilot/001C benchmark files still matched their
preservation hashes. The final contract remains open, final test unchanged and
001E deferred.

Final validation: 158 Python tests passed, including the raw-review import
regression; Python compilation and Git whitespace checks passed. The source
review JSON and all private references remain outside Git.
