# STYLEMATCH experiment foundation

STYLEMATCH helps recreate an inspiration look with clothing already owned.
**STYLEMATCH-001A is an engineering foundation, not evidence of feasibility.**
001B development preparation is authorized; its real-image pilot is incomplete.
The evaluation contract remains a draft, unapproved and unfrozen. No real data,
weights or model experiments are included in this public repository.

Use the [local development-pilot workflow](docs/development-pilot.md) to register
originals, prepare sanitized copies/crops and collect exhaustive human labels.
Photographs have not yet been supplied. Real processing awaits their location,
handling approval and per-inspiration permission records.

## Setup and checks

Use Python **3.12**, [uv](https://docs.astral.sh/uv/) and the committed `uv.lock`.
The commands below run from the repository root in PowerShell. On other shells,
set the equivalent environment variables if project-local tooling is desired.

```powershell
# Keep interpreter downloads and cache in ignored, project-local directories.
$env:UV_CACHE_DIR = Join-Path $PWD '.uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.tools\python'
uv python install 3.12 --no-bin
uv sync --locked
uv run --locked pytest
uv run --locked python -m stylematch tests/fixtures/synthetic/dataset.json tests/fixtures/synthetic/run.json --image-root tests/fixtures/synthetic
uv run --locked python scripts/inventory.py
git diff --check
```

Normal initial setup needs network access to download the interpreter and locked
dependencies. Subsequent execution is local. No service account or paid service is
needed. Pytest uses ignored `.pytest_cache/tmp` because this execution sandbox
cannot inspect the existing user-wide pytest temp directory.

The evaluation command prints JSON to stdout. Optionally redirect it into ignored
`outputs/` after creating that directory. Invalid manifests return exit code 2
with a stderr explanation. Failed runs return exit code 2 with an unscored JSON
report. A complete, valid run returns 0 even when its raw rankings contain errors;
inspect both raw and validated diagnostics. Report exit status does not assert
that provisional performance targets passed.

## Small project map

- `stylematch/contracts.py`: strict, versioned Pydantic data and run structures.
- `stylematch/validation.py`: membership, labels, split groups and file hashes.
- `stylematch/evaluation.py`: deterministic raw/validated metrics and counts.
- `stylematch/__main__.py`: read-only JSON evaluation command.
- `stylematch/pilot.py`, `preparation.py`, `labeling.py`: local registration,
  oriented metadata-free PNG copies, human crops, CSV review and validated import.
- `tests/`: hand-computed metric checks and deliberately invalid synthetic inputs.
- `scripts/inventory.py`: read-only environment discovery, with limitations.
- [Data and metric semantics](docs/data-and-metrics.md).
- [Draft evaluation contract](docs/evaluation-contract.md).
- [Private data handling](docs/data-handling.md).
- [Candidate verification checklist](docs/candidate-checklist.md).
- [Environment evidence](docs/environment.md), [decisions](docs/decisions.md)
  and [001B prerequisites](docs/001b-handoff.md).
- [Actual 001A validation results](docs/validation.md).

## Synthetic fixture

The fixture contains two wardrobes, six garments, nine **text stand-ins**, six
component tasks and six canonical synthetic judgments. Three tasks are matchable;
three have no acceptable match (including an empty candidate pool). The same
synthetic person owns both wardrobes to test accurate person-overlap reporting.
These stand-ins are not image/model inputs and establish no retrieval quality.

The raw run deliberately includes an unknown item, cross-wardrobe items, a wrong
category, a duplicate and abstentions. It uses no model or measured resources.
Regenerate deterministically with:

```powershell
uv run --locked python tests/fixtures/synthetic/build_fixture.py
```

`--image-root` verifies paths and file SHA-256, including these text stand-ins.
Without it, references and leakage are still checked against the manifest, but
file existence and bytes are not checked. Real-data evaluation must use it after
private, authorized preparation. The evaluation command does not decode images;
the pilot `check` command additionally checks decoding, dimensions and metadata.
Neither command detects all near-duplicates.
LF text normalization in `.gitattributes` preserves fixture hash reproducibility.

Personal images, labels containing personal details, embeddings, model weights,
caches and experiment outputs belong in ignored private directories. Check the
staged diff before every commit; ignore rules are not a confidentiality boundary.
