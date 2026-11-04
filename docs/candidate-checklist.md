# Candidate verification checklist

No model is selected, downloaded or executed. All properties below are **PENDING
verification**, not claims about compatibility, licenses or performance. This
checklist is for later authorized evaluation. A family name is not an exact
checkpoint or an approval to use one.

| Candidate family | Exact checkpoint/revision | Verification status |
| --- | --- | --- |
| FashionCLIP | Unselected | PENDING |
| SigLIP2 | Unselected | PENDING |
| Lightweight VLM | Family/checkpoint unselected | PENDING |

Complete a separate copy for each concrete candidate:

- [ ] Exact publisher, checkpoint ID and immutable revision/weight hash.
- [ ] Official model card, repository and paper URLs, access date, and evidence
  excerpts for each asserted property; distinguish official facts from inference.
- [ ] Intended uses, training-domain limits, unsupported inputs, evaluation
  limitations and any restrictions relevant to personal clothing images.
- [ ] Exact model/weight license and notices, redistribution conditions and any
  separate code, tokenizer, dependency or dataset-derived restrictions.
- [ ] Preprocessing: decoder, orientation, color space, resizing/interpolation,
  crop/padding, normalization, prompts/tokenization and any pooling/normalization.
- [ ] Embedding dimensions, similarity definition and handling of full image
  versus human crop. For a VLM, specify structured attributes/prompts, output
  validation, nondeterminism and whether embeddings are applicable.
- [ ] Python 3.12, OS, CPU/GPU and library compatibility; pinned dependencies,
  conflicts with the project lock, supported device/dtype and local verification.
- [ ] Documented expected download/storage, RAM/VRAM, compute and latency needs;
  mark undocumented properties unknown. No inferred budget pass.
- [ ] Intended-machine measurements under the approved protocol: loading time,
  warm/cold inference, peak memory, batch/thread settings, sample counts,
  repetitions and failure/missing-measurement reasons.
- [ ] Offline/local execution and telemetry/network behavior verified before
  processing personal data; no external personal-photo inference without approval.
- [ ] Evidence table for every property with `documented`, `locally measured`,
  `inferred` or `unknown`, including source/revision/date and measurement method.
- [ ] Development-only comparison decision recorded with tradeoffs, resource
  evidence and licenses reviewed before any final-test use.

Do not treat the checklist as completed because a model imports successfully.
Do not add a model-specific wrapper before candidate selection is authorized.
