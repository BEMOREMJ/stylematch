# Local development pilot workflow

This workflow registers originals, prepares private copies/crops and imports
exhaustive human labels. No model downloads, inference, quality experiments,
final-test collection or contract freeze occur. Preparation tooling is ready;
**the real-data pilot is incomplete**. The owner has not yet taken the photos.

The owner confirmed the inventoried Windows laptop as the initial inference
machine, authorized local study use of their own garment photos, and is the sole
initial reviewer. Use pseudonyms `owner-01`, `wardrobe-01`, `reviewer-01`; keep the
identity mapping private. One owner's clothing is one wardrobe, not independent
subsets. A repeat review is not an independent reviewer or unseen-person evidence.

## Capture and handling

Working allocation: one wardrobe, approximately 15 garments (six tops, six
bottoms, three outerwear), six authorized outfit inspirations and approximately
12–18 human-selected component tasks. These are flexible development allocations,
not approved final-study sizes or gates. Record actual counts; use available
outerwear only, without purchases or invented items.

Photograph one unworn garment per image, entirely visible, against a simple
background with consistent adequate light. Avoid filters, deliberate color
changes, unnecessary faces and identifying surroundings. Each inspiration needs
a distinguishable supported component and must be owned or explicitly permitted
for local study use. Website availability is not permission. Related shots/edits
retain source/capture groups. Record unsupported/occluded components and exclusion
reasons before experiments; never drop difficult cases after seeing model results.

Use still JPEG/PNG. HEIC/HEIF, RAW, GIF, WebP and animation are unsupported; export
an unfiltered JPEG/PNG locally, retaining the original. Do not download converters
or silently replace sources. Check orientation and color visually after preparation.

Before real processing, supply the actual private originals folder outside Git,
approve/amend [the handling proposal](data-handling.md), and record permission
for each inspiration. This is still pending. Tools read registered files only;
they do not search personal folders. Use private local storage without cloud sync.

## Register originals and tasks

After [setup](../README.md), create an ignored, empty, unapproved plan:

```powershell
uv run --locked python -m stylematch.pilot init --output private/pilot-plan.json
```

This refuses to overwrite an existing plan; edit the existing file on later visits.
`PilotPlan` in `stylematch/preparation.py` is the strict versioned schema; its
`model_json_schema()` can assist an editor. Keep `synthetic` false for real files.
Only development data and one actual wardrobe are allowed. `handling.approved`
may be set true only after the actual owner decision: record its date/reference
in `decision_reference` and amendments in `amendment`. A boolean is not permission.

Populate `sources` with entries like this, replacing evidence with actual facts:

```json
{
  "image_id": "garment-image-001",
  "path": "garments/photo-001.jpg",
  "kind": "garment",
  "provenance": "owner-created garment photograph",
  "permission_basis": "owner-created",
  "permission_reference": "actual owner decision reference goes here",
  "capture_group": "capture-001",
  "source_group": "source-001"
}
```

Every source, including each `kind: "inspiration"`, needs `owner-created` or
`explicit-permission` with real evidence. Paths are relative to the originals
root passed at runtime. Its absolute path is not stored in the manifest/audit.
Do not copy a permission assertion without checking it.

Populate `garments` and `queries` using existing structures, for example:

```json
{"ref":{"wardrobe_id":"wardrobe-01","item_id":"garment-001"},"category":"tops","image_ids":["garment-image-001"]}
```

```json
{"query_id":"task-001","active_wardrobe_id":"wardrobe-01","image_id":"inspiration-001","component_category":"tops","partition":"development","crop_image_id":null}
```

All eligible candidates enter labeling automatically. Include visually similar
distractors and multiple acceptable matches where present; do not manufacture
no-match labels. Missing-category tasks are allowed and still need a human decision.
The categories/rubric remain those in [the draft contract](evaluation-contract.md).

`exclusions` entries have `image_id`, `component_category` (an unsupported category
name is allowed, or null for an entire image), and nonempty `reason`. An unused
source must have an exclusion. Such sources are hash-registered without decoding
or copies, so unsupported originals
can be explicitly excluded. Partially occluded sources with usable tasks are
still prepared; record excluded components separately. Included files must decode
correctly; errors never silently remove them.

## Prepare sanitized copies and human crops

After handling approval and registration, replace the placeholder with the actual
authorized folder; use a fresh output directory per preparation revision:

```powershell
$PilotOriginals = 'D:\YOUR_PRIVATE_ORIGINALS'
uv run --locked python -m stylematch.pilot prepare --plan private/pilot-plan.json --originals $PilotOriginals --output data/pilot-01
uv run --locked python -m stylematch.pilot check --pilot data/pilot-01 --allow-unlabeled
```

Preparation hashes originals, corrects EXIF orientation, converts valid tagged
ICC color to sRGB (assumes sRGB when untagged), flattens alpha on white, and writes
RGB PNG without EXIF/GPS/XMP/text/profile metadata. No resizing, filters or
enhancement occur. Untagged CMYK and invalid profiles fail explicitly. Source
bytes are rechecked before a ready manifest is written; sources are never moved,
overwritten or deleted. Decompression-bomb warnings/errors are rejected.

Private output: `prepared/`, `crops/`, unlabeled `dataset.json`, and
`preparation.json` with source registration, original hashes/dimensions/orientation,
permissions, exclusions, protocol and Pillow version. Outputs must be ignored and
untracked. Paths, audit metadata and labels remain private. Existing paths and
symlink escapes are rejected. A failed partial directory is preserved without a
ready dataset manifest; correct the cause and use a fresh directory. There is no
force, overwrite or automatic cleanup option.

To choose crops, first inspect a prepared inspiration with an offline image
editor. Record human-selected boxes in **oriented prepared-image pixels**. Add a
`crops` entry and set its query's `crop_image_id`:

```json
{"image_id":"crop-001","parent_image_id":"inspiration-001","box":[20,30,220,330]}
```

Bounds are `[left, top, right, bottom]`, right/bottom exclusive, positive area and
inside the parent. Coordinates, source link and inherited capture/source groups
and permissions are recorded. Reprepare the same originals into `data/pilot-02`;
no resizing means coordinates remain reproducible. Generate review sheets against
the chosen revision only. All earlier revisions remain development data too.
No automatic garment extraction or annotation platform is implemented.

## Human review and import

Substitute the chosen pilot revision in these commands:

```powershell
uv run --locked python -m stylematch.pilot label-template --pilot data/pilot-01 --output data/pilot-01/review-01 --seed 104729
```

Keep `INSTRUCTIONS.txt`, `template.json` and all four CSVs. The recorded seed
reproducibly shuffles sorted eligible candidates per task under Python 3.12.
No model predictions/scores are shown. Use a local CSV editor and view image paths
relative to the pilot folder. Do not change IDs, paths, headers, row order or
reviewer identity. Never enter spreadsheet formulas or upload private sheets.

- `labels.csv`: grade every candidate. 0 unacceptable; 1 partial, insufficient
  to recommend; 2 acceptable; 3 strong recreation. Multiple 2/3 matches are allowed.
  Set `uncertain` true/false and record rationale where useful.
- `queries.csv`: `no_match` is true exactly when no candidate has grade 2/3.
  Missing-category tasks have no candidate rows but need explicit query decisions.
  Set `uncertain` true/false and add notes.
- `attributes.csv`: optional human observations of color, pattern, garment type,
  silhouette and texture. Unobservable fields stay `unknown`, not blank. No
  sensitive-characteristic/body-fit judgments, reliability gates or accuracy claims.
- `effort.csv`: actual human seconds for capture, cropping and annotation, with
  status `measured`; missing measurements stay `unknown`, seconds blank, reason
  in notes. Measure while working; do not invent precision later or substitute
  zero. Tool runtime is separate from human effort.

Blank/unknown grades or decisions are unresolved, never grade 0. Uncertainty can
be recorded, but import refuses unresolved labels. One actual reviewer performs
the pilot; keep new bundles per repeat pass for within-reviewer comparison, not
independent-review claims. Preserve all instructions and prior reviews privately.

```powershell
uv run --locked python -m stylematch.pilot import-labels --pilot data/pilot-01 --labels data/pilot-01/review-01 --output dataset-labeled-01.json
uv run --locked python -m stylematch.pilot check --pilot data/pilot-01 --dataset dataset-labeled-01.json
```

Import rejects missing/extra/reordered rows, changed membership/context, invalid
grades, uncertainty and contradictory no-match flags. It round-trips through the
existing strict contracts and writes a new private manifest plus
`.label-audit.json`: CSV hashes, seed, one reviewer, candidate notes, attributes,
human effort and exact output hash. `check` validates decoding, dimensions,
metadata, hashes, references, membership, grouping, exhaustive labels and audit
bindings. Its default requires labels; `--allow-unlabeled` is preparation-only.
Existing evaluation also continues to require complete labels. No ranking is
synthesized and no quality metrics are calculated for real images.

Summaries give actual included image/crop/task/category counts, exclusions,
missing-category cases and label/no-match status. Labeled checks include measured
and missing human effort. The source register distinguishes all originals from
included/prepared files; report excluded inputs separately from evaluated tasks.

No runtime/RAM budget is established by preparation. Final-study gates remain
pending. Candidate/license/resource verification belongs before 001C/001D adoption
and does not block preparation engineering. Generated test images and labels are
synthetic engineering fixtures only. Stop within 001B; the real pilot still needs
photos, approved handling/permissions and actual human labels.
