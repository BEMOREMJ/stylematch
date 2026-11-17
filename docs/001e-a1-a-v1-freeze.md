# STYLEMATCH-001E-A1-A-v1 — approved Option A freeze

Owner decision: **Mark, 17 November 2026, Africa/Nairobi**. Mark explicitly
approved amendment A1 from draft commit
`2e72357459ff720f88369615ed0d4cbc32bccbb5`, Option A, its collection caps,
fixed comparisons and numerical decision criteria, and himself as sole reviewer
and label custodian. Freeze ID: **STYLEMATCH-001E-A1-A-v1**.

The exact historical contract, draft, part 1 scoring/vocabulary/encoder,
validation, split-audit and dependency sources are pinned by commit and public
SHA-256 in [the frozen configuration](../configs/001e-a1-a-v1.json). The draft
and development evidence remain unchanged. The active design is A only; B's
wardrobe setup proposals are inactive. All A1 numerical criteria and all three
attribute fields are unchanged. There is no hybrid arm or new threshold.
The claim is new looks for the existing known 15-garment wardrobe, not a new-owner
or population claim. Stage advancement remains a master-roadmap decision.

## Window and caps

Collection may begin after this freeze is committed, pushed and the remote SHA
verified. Local approval date 17 November + 14 calendar days gives the **exclusive
cutoff 1 December 2026 at 00:00:00 +03:00**. Thus 30 November is the last permitted
collection date. This date-based convention does not invent an approval time or
start a rolling 336-hour clock. Stop at the first of 24 eligible independent
sources, 36 screened sources (including exclusions), or this cutoff. Neither
observed matchability nor outcome counts may extend the window or queue.

## Verification and custody

Before collection, locally validate the accepted pilot/reference and map all 15
garments to their owner-confirmed fields. Preserve their exact photos/categories
and the canonical garment-tag bytes. Verify the local encoder size/SHA-256 and
revision, fixed scoring/preprocessing, category seed 104729, presentation seeds,
repeat-review seed and cluster bootstrap seed 20261117. Real input/tag/image
fingerprints and the immutable development snapshot belong only in the private
binding receipt. Original wardrobe-tagging time remains unknown.

Keep the existing strict validator unchanged. The pinned cross-manifest audit
allows only the deliberate identical registered wardrobe reuse. Fresh-source
checks reject development/prior-source byte/pixel duplicates and group overlap;
Mark additionally reviews related shoots, edits/reposts and permissions. This
checkpoint verifies audit code with synthetic fixtures; a real fresh-source audit
cannot be declared complete before any sources exist.

Mark controls local labels and necessarily knows them as their author. Intake
separates source identities, annotation, relevance and predictions from the
allowlisted ranking projection. The Python child-process file guard rejects
reads of the private custody tree outside `inputs`; it is **not an OS security
or independent-custody guarantee**. No encryption or separate account has been
silently configured. Preserve this procedural-custody limitation in reporting.

## Intake and later release sequence

After verified push, initialize a fresh private folder **outside the repository**:
`C:\Users\Mark\Desktop\stylematch-private\STYLEMATCH-001E-A1-A-v1`.
No real new source is registered by initialization. It creates `originals`, an
ordered `source-queue.csv`, `source-screening.csv` and immutable chained screening
records, blank component/tag/effort sheets, separate custodian relevance and
repeat-review sheets, and a pending review schedule. Only already accepted
wardrobe images/tags are copied. No predictions are generated.

1. Mark lists prospective permitted source clusters in order (up to 36), including
   source/permission references. Lock this queue **before screening**. Related
   shots/reposts belong to one source group. No outcome-driven additions or
   reordering. Queue exhaustion is not permission to top up; retain the fixed cap.
2. For the next queued source, save an original JPEG/PNG under `originals` and
   record include/exclude, supported visible components and occlusion before
   relevance judgment. Every exclusion gets a reason and consumes a screen.
   Intake logs automatic duplicate/permission/unreadable exclusions too.
3. Crop and tag using the fixed guide, with predictions hidden. Record **separate
   crop and query-tag active seconds** per task in `annotation/effort.csv`, including
   corrections; explicit unknown-time reasons remain unknown, never zero. Keep
   partially occluded identifiable components and unknown attribute values.
4. Close collection at the first cap. Lock all query tags before grading; freeze
   the seeded presentation order. Grading begins at least 24 hours after the
   tag seal. Mark grades every candidate, preserving multiple acceptable items,
   true no-match cases and unresolved cases in their audit registry. Complete
   the seeded repeat review of `ceil(0.20*N)` eligible source clusters with prior
   labels/rankings hidden; 24 eligible sources imply five repeat sources.
5. Freeze resolved scoring tasks and required input/photo/crop/tag, source/audit,
   timing and canonical/repeat-label hashes separately. Export only neutral image
   IDs, pixels, eligible references/categories and the three fields to `inputs`.
   No relevance/no-match flags, notes or original names enter ranking inputs.
6. A future authorized ranking child verifies input seals, installs the file guard,
   and keeps all predictions hidden. Validate complete/grounded results, then lock
   category, crop and human-assisted attribute predictions together with their
   hashes and resource/failure logs. Mark releases labels for scoring only after
   that lock and after verifying unchanged input, label and prediction hashes.

Data and label seals are **pending**, not fabricated from empty intake folders.
The existing development comparison command remains development-only. This
checkpoint provides intake and custody helper checks, not permission to skip
annotation/repeat review, run inference now, or score before collection/sealing.

## Reproduction

```powershell
.venv/Scripts/python.exe -m pytest -q
node tests/check_attribute_review.cjs
.venv/Scripts/python.exe -m compileall -q stylematch tests
git diff --check
.venv/Scripts/python.exe -m scripts.verify_001e_freeze --output private/fresh-freeze-verification
```

Intake CLI: `python -m stylematch.intake init`, `lock-queue`, `screen`, `status`.
The initializer requires the locally verified binding receipt and the full
verified freeze commit. It refuses overwrites and a root inside the repository.
`scripts.verify_001e_freeze` reproduces private wardrobe/reference/checkpoint
bindings from the accepted inputs without any held-out data or inference.
Exact local commands and first-look instructions are also saved in the private
intake folder after its creation. Photos, tags, label sheets, identities and
per-source receipts are never committed or pushed.
