# STYLEMATCH-001A decision log

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
