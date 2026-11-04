# Proposed private data handling

No real images are supplied, collected, transformed, deleted or uploaded in 001A.
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

These are proposals, not an approved retention policy. Exact duration, storage
owner, backup locations, access list and withdrawal contact remain 001B inputs.
Do not silently choose an indefinite retention period. Before private collection,
record the owner's permission, permitted uses, retention decision and deletion
authority. Prepared copies must remain separate from originals. Metadata
stripping has not been implemented or performed by this foundation.

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
