# STYLEMATCH-001A decision log

This file preserves historical stage decisions. Current 001C authorization and
methodology are recorded in [development-benchmarks.md](development-benchmarks.md).

Date: 2026-11-04. Scope: experiment foundation and evaluation contract only.

| Decision | Evidence / reason |
| --- | --- |
| Use the existing clone and main | Origin verified as `https://github.com/BEMOREMJ/stylematch`; clean main at initial `365a372`; no applicable AGENTS.md or conflicting conventions found |
| Require Python 3.12 and uv.lock | Brief requirement; managed project-local 3.12.14 installed normally with network access; exact dependencies locked |
| Use one small package with Pydantic and pytest | Strict versioned JSON contracts and meaningful tests without an application framework or model dependencies |
| Compound wardrobe/item references | Item IDs alone cannot establish wardrobe grounding; synthetic fixture repeats top-a across wardrobes |
| Exhaustive resolved canonical labels | Missing/uncertain labels must fail, not become grade 0; reviewer history remains private |
| Keep raw and validated rankings together | Invalid IDs, wrong categories and duplicates must remain visible even when filtered output is safe |
| Explicit abstention, no automatic score interpretation | Ranking lists are accepted recommendations; threshold provenance is recorded and development-only; evaluator cannot establish calibration |
| Split wardrobes and source/capture groups, report people overlap | Prevent deterministic leakage without requiring entirely different people; hashes detect exact bytes only |
| Text stand-ins with real file hashes | Reproducible manifest/file validation without personal photos, model inputs or invented feasibility evidence |
| No checkpoint selection or wrappers | Candidate properties remain pending; no weights downloaded or models run |
| Draft remains unfrozen | Scope does not approve numeric targets, data collection, resource budgets, 001B or STYLEMATCH-002 |
| Preserve all initial unrelated work | Initial tree clean; only slice-related files added/modified; no repository initialization or history rewrite |

The implementation does not establish product feasibility. No comparative study,
real human labeling, private data preparation, resource benchmark or contract
freeze occurred. Remaining inputs are in [001b-handoff.md](001b-handoff.md).

## 001B development preparation decisions

- Owner confirmed the inventoried Windows laptop as the initial inference target,
  authorized local study use of their own garment photos, and will be the sole
  initial reviewer. The workflow enforces one wardrobe and reviewer, without
  independent-annotation or unseen-person claims.
- Reuse version 1 contracts with optional dimensions/crop boxes. Unlabeled
  preparation is explicit; default validation/evaluation still requires full labels.
- Add Pillow as the only image dependency; use new ignored folders, exclusive
  file creation, oriented metadata-free PNGs, and source hashes. No original moves,
  overwrites, deletion, photo uploads or inference.
- Use reproducibly shuffled CSVs with explicit unknown/uncertain states, exhaustive
  human labels, observable attribute candidates and measured/missing human effort.
- The owner has not photographed the clothes yet. Original location, handling
  approval and inspiration permissions remain pending; only preparation engineering
  is delivered. No contract freeze, model experiments or later stage is authorized.

## 001C development comparison decisions — 2026-11-14

- Subsequent owner handling/permission decisions, private preparation, confirmed
  human crops and accepted exhaustive labels supersede the pending owner-input
  status above. Keep those records and all personal data outside Git.
- The owner authorized development retrieval baselines and one officially
  verified encoder on the confirmed laptop. Record the protocol before scoring,
  preserve the existing evaluator, and keep final-study targets open.
- Add a category-only uniform-order comparison with exact chance expectations;
  require independent observed human attributes for the assisted rule baseline.
- Select one small pinned general ImageNet encoder for initial CPU feasibility;
  compare full inspirations with confirmed crops using the same cached wardrobe
  embeddings. Keep labels and no-match flags outside ranking inputs.
- Primary comparison has no abstention. A separate shared full/crop threshold is
  explicitly development-tuned, with false acceptances/rejections and coverage.
- Keep correlated-task/single-reviewer limitations and retained occlusion visible.
  Resource findings and all real per-task outputs remain private. No later-stage
  final-test inference, outfit generation or contract freeze is authorized.
