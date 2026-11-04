# STYLEMATCH-001A engineering validation

Executed locally on 2026-11-04 using uv-managed CPython 3.12.14, Pydantic
2.14.2 and pytest 9.2.0. These are engineering checks, not model experiments.

Project-local uv setup used:

```powershell
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'
uv python install 3.12 --no-bin
uv sync --python 3.12
```

Interpreter and dependency setup succeeded using permitted network access after
the initial sandboxed download failure. Exact dependency hashes are in `uv.lock`.

| Actual command | Result |
| --- | --- |
| `uv sync --locked --offline` | Passed; lock resolved locally and 11 installed dependencies checked |
| `uv run --locked pytest` | 71 passed; includes CLI success/failure paths |
| `uv run --locked python -m compileall -q stylematch scripts tests` | Passed |
| `uv run --locked python -m stylematch tests/fixtures/synthetic/dataset.json tests/fixtures/synthetic/run.json --image-root tests/fixtures/synthetic` | Exit 0; complete synthetic raw/validated JSON report; all stand-in files/hashes verified |
| `uv run --locked python scripts/inventory.py` | OS, CPU, memory, disk, graphics-name and runtime inventory; VRAM explicitly unknown |
| `git diff --check` | Passed |

The first pytest run had 68 passes and two temp-directory setup errors. Moving
pytest's base temp directory into ignored `.pytest_cache/tmp` resolved these;
no tests were skipped or disabled.

Coverage includes hand-computed Hit/Recall/graded nDCG with multiple acceptable
items and partial grades; no-match, abstention, empty outputs, empty candidate
pools and all-no-match datasets; missing/contradictory/uncertain labels; duplicate
prediction/query IDs; unknown/cross-wardrobe IDs; categories; raw/validated error
accounting; exact hash, capture/source group leakage; actual person overlap;
safe paths, file hash changes; missing resources and failed runs.

Fixture counts: two wardrobes, one shared synthetic person, six garments, nine
text stand-ins, six component queries and six canonical synthetic judgments.
Three tasks are matchable, three no-match. These intentionally small counts do
not implement the proposed real-data scale.

| Engineering fixture output, overall | Raw | Validated |
| --- | --- | --- |
| Prediction slots | 9 | 4 |
| Invalid/cross-wardrobe slots | 3 / 9 | 0 / 4 |
| Category violations | 1 / 9 | 0 / 4 |
| Duplicate slots | 1 / 9 | 0 / 4 |
| Hit@3 | 1 / 3 | 2 / 3 |
| Recall@3, macro | 0.333333 | 0.666667 |
| nDCG@5, macro | 0.446336 | 0.666667 |
| No-match false acceptance | 2 / 3 | 1 / 3 |
| Matchable false rejection | 1 / 3 | 1 / 3 |
| Recommendation coverage | 4 / 6 | 3 / 6 |

These values verify authored arithmetic and error handling. They are **not
feasibility evidence**, estimates of model quality, or passes/failures against
provisional real-data targets. No real-data model experiments were run. No model
weights or real datasets were downloaded. All fixture model resource values
are null with explicit no-execution reasons; no RAM/latency budget passed.

Repository delivery records (branch, exact commit and actual push result) are
reported in the conversation after the commit/push. A document inside its own
commit cannot reliably record its final commit SHA.
