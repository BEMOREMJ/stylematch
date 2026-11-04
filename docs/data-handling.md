# Proposed private data handling

No real images are supplied, collected, transformed, deleted or uploaded in 001A.
For 001B, the owner authorized local use of their garment photographs, but has
not yet taken/supplied them. Handling approval and inspiration permissions remain
pending; no real files have been processed.
Do not upload photos or run external personal-photo inference without explicit
authorization. No paid processing, scraping or inferred sensitive traits/physical
body fit is authorized. Git ignore rules do not remove already tracked files;
inspect every staged path and diff before committing.

| Material | Proposed private location and handling | Retention/deletion proposal |
| --- | --- | --- |
| Originals | Outside public Git, preferably a separate access-controlled local store; preserve unchanged only when authorized | Owner-approved retention date required before capture; never delete source images without explicit permission |
| Sanitized copies | Ignored `data/prepared/`; local preparation strips unnecessary EXIF, GPS and other metadata, assigns pseudonymous names, checks output visually, records hashes and source links | Retain through agreed study/review window only; delete on authorized withdrawal or scheduled cleanup after owner approval |
| Human crops | Ignored `data/crops/`; link source, crop instructions and groups; no sensitive surroundings | Same or shorter lifetime than prepared sources; cascade authorized derivative deletion |
| Labels/manifests | Ignored `private/` or `data/`; permissions references without personal details, pseudonymous reviewer/person IDs; identity key stored separately | Retain the minimum authorized audit record; remove personal links on authorized withdrawal |
| Embeddings | Ignored `embeddings/` or `data/embeddings/`; potentially sensitive derived data, local access controls, source/model/revision mapping | Delete/rebuild when sources, authorization or models change; include them in withdrawal and end-of-study cleanup |
| Caches and outputs | Ignored `cache/`, `outputs/`, `runs/`; no public raw personal manifests, vectors or rankings | Disposable; clear under an agreed schedule and after authorized source withdrawal |
| Weights/dependencies | Ignored `models/`, `weights/`, `.tools/`, `.uv-cache/`, `.venv/`; future downloads require candidate/license checks | Rebuildable; delete when no longer needed, honoring licenses and available disk |

The 001B proposal is: originals in a private folder outside this working tree;
prepared copies, crops, manifests and labels in ignored local directories; access
limited to the owner and explicitly authorized local tools; no application-created
external backup or upload; retention through the study, then owner review within
30 days of the stage decision; no automatic original deletion; derivative cleanup
only under an agreed owner instruction. This proposal is **not approved**.

Exact source location, approval/amendments, inspiration permissions, storage
owner, backup locations, access list and withdrawal contact remain owner inputs.
Do not silently choose an indefinite retention period. Before private collection,
record the owner's permission, permitted uses, retention decision and deletion
authority. Prepared copies must remain separate from originals. Metadata
stripping is implemented for authorized copies in 001B, but has been exercised
only on synthetic engineering images. The workflow requires an approval reference
before reading real originals; file access does not imply permission.

Authorized derivative cleanup must enumerate copies, crops, embeddings, caches,
outputs and backups using recorded source links; verify what was removed and
report any retained backups or deletion limits. Never promise secure physical
erasure from normal filesystem deletion. Public reports should contain reviewed
aggregates only, with image/reidentification risk checked before release.

The repository's `.gitignore` covers private roots, common image/weight/vector
extensions, credentials and caches. Text fixtures are explicitly synthetic.
Ignore patterns cannot cover every filename or prevent forced additions. Do not
stage private JSON/CSV manifests or credentials merely because their extension
is allowed. Do not publish a source image as a synthetic fixture.
