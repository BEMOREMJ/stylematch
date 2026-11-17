"""Draft held-out protocol helpers, exercised on synthetic data only in 001E-2.

No collection, inference, filesystem access or implicit approval is provided.
Existing single-manifest leakage checks remain mandatory and unchanged.
"""
from collections import defaultdict
from hashlib import sha256
import random

from .validation import require, unique, validate_dataset


def audit_holdout_split(development, heldout, *, design, locked_tags=None,
                        heldout_tags=None, require_judgments=False):
    """Audit two separate manifests; permit only explicitly locked garment reuse.

    Tag arguments are exact bytes of a separately validated, canonical garment
    tag registry, not query tags or relevance labels. Actual file verification,
    permission review and approval/sealing are separate custodian duties.
    """
    require(design in ("known-wardrobe", "new-owner"), "unknown holdout design")
    require(development.dataset_id != heldout.dataset_id, "heldout dataset ID must be fresh")
    for dataset, partition in ((development, "development"), (heldout, "test")):
        validate_dataset(dataset, require_judgments=require_judgments)
        require(all(w.partition == partition for w in dataset.wardrobes)
                and all(i.partition == partition for i in dataset.images)
                and all(q.partition == partition for q in dataset.queries),
                "cross-manifest audit requires separate development/test manifests")
    require(development.synthetic == heldout.synthetic, "synthetic/real manifest mismatch")
    require(all(q.crop_image_id is not None for q in heldout.queries), "heldout human crops required")
    require({q.query_id for q in development.queries}.isdisjoint(q.query_id for q in heldout.queries),
            "heldout query IDs must be fresh")
    dev_wardrobes = {w.wardrobe_id: w.model_dump(exclude={"partition"}) for w in development.wardrobes}
    test_wardrobes = {w.wardrobe_id: w.model_dump(exclude={"partition"}) for w in heldout.wardrobes}
    dev_items = {g.ref.key: g.model_dump() for g in development.garments}
    test_items = {g.ref.key: g.model_dump() for g in heldout.garments}
    dev_registered = {i for g in development.garments for i in g.image_ids}
    test_registered = {i for g in heldout.garments for i in g.image_ids}
    people_overlap = sorted({w.person_id for w in development.wardrobes}
                            & {w.person_id for w in heldout.wardrobes})
    tag_hash = None
    if design == "known-wardrobe":
        require(dev_wardrobes == test_wardrobes and dev_items == test_items,
                "known wardrobe membership/owner/category/image references changed")
        require(type(locked_tags) is bytes and type(heldout_tags) is bytes and bool(locked_tags)
                and heldout_tags == locked_tags, "locked garment tag bytes changed or missing")
        tag_hash = sha256(locked_tags).hexdigest()
        dev_images = {i.image_id: i.model_dump(exclude={"partition"}) for i in development.images
                      if i.image_id in dev_registered}
        test_images = {i.image_id: i.model_dump(exclude={"partition"}) for i in heldout.images
                       if i.image_id in test_registered}
        require(dev_images == test_images, "locked garment image metadata changed")
    else:
        require(not people_overlap and dev_wardrobes.keys().isdisjoint(test_wardrobes)
                and dev_items.keys().isdisjoint(test_items), "new-owner design requires owner/wardrobe independence")
    allowed_image_ids = dev_registered if design == "known-wardrobe" else set()
    require(({i.image_id for i in development.images} & {i.image_id for i in heldout.images})
            <= allowed_image_ids, "non-wardrobe image IDs must be fresh")
    intentional = {}
    for field in ("sha256", "capture_group", "source_group"):
        old, new = defaultdict(list), defaultdict(list)
        for image in development.images:
            old[getattr(image, field)].append(image)
        for image in heldout.images:
            new[getattr(image, field)].append(image)
        overlap = sorted(old.keys() & new.keys())
        for value in overlap:
            require(design == "known-wardrobe"
                    and all(i.kind == "garment" and i.image_id in dev_registered for i in old[value])
                    and all(i.kind == "garment" and i.image_id in test_registered for i in new[value]),
                    f"unapproved cross-manifest {field} leakage")
        intentional[field] = overlap
    return {"design": design, "intentional_wardrobe_ids": sorted(dev_wardrobes.keys() & test_wardrobes),
            "intentional_person_overlap": people_overlap,
            "intentional_garment_image_ids": sorted(allowed_image_ids),
            "intentional_garment_overlap": intentional,
            "locked_tags_sha256": tag_hash, "unexpected_overlap": [],
            "within_manifest_leakage_checks": "unchanged: sha256, capture_group, source_group",
            "claim": "new looks for the locked known wardrobe" if design == "known-wardrobe"
                     else "fresh sources for one independent owner's wardrobe; not population generalization",
            "manual_review_required": "permissions, ownership, related-source/near-duplicate audit; hashes cannot prove independence"}


def paired_source_hit1(rows, *, repetitions=10000, seed=20261117):
    """Task-weighted paired effect with source-cluster percentile bootstrap.

    Called only after sealed predictions are frozen and labels are released in
    a future approved run. Here it supports synthetic protocol checks only.
    No-match-only clusters are outside the ranking estimand. Resampling retains
    every matchable component of each sampled source, including multiplicity.
    """
    require(type(repetitions) is int and repetitions >= 100, "too few bootstrap repetitions")
    unique((r["query_id"] for r in rows), "paired query IDs")
    groups = defaultdict(list)
    for row in rows:
        require(type(row["source_group"]) is str and bool(row["source_group"]), "source group required")
        require(type(row["no_match"]) is bool, "no_match must be boolean")
        require(all(type(row[f]) is int and row[f] in (0, 1) for f in ("crop_hit1", "attributes_hit1")),
                "paired hits must be integer 0/1")
        if not row["no_match"]:
            groups[row["source_group"]].append(row)
    sources = sorted(groups)
    selected = [row for source in sources for row in groups[source]]
    gains = [r["query_id"] for r in selected if r["attributes_hit1"] > r["crop_hit1"]]
    losses = [r["query_id"] for r in selected if r["attributes_hit1"] < r["crop_hit1"]]
    n = len(selected)
    effect = (len(gains) - len(losses)) / n if n else None
    totals = {s: (sum(r["attributes_hit1"] - r["crop_hit1"] for r in groups[s]), len(groups[s])) for s in sources}
    rng, samples = random.Random(seed), []
    if len(sources) >= 2:
        for _ in range(repetitions):
            drawn = [totals[rng.choice(sources)] for _ in sources]
            samples.append(sum(v[0] for v in drawn) / sum(v[1] for v in drawn))
        samples.sort()
    interval = [samples[int(0.025 * (repetitions - 1))], samples[int(0.975 * (repetitions - 1))]] if samples else None
    leave_one = {s: (sum(v[0] for k, v in totals.items() if k != s)
                     / sum(v[1] for k, v in totals.items() if k != s)) for s in sources} if len(sources) >= 2 else {}
    return {"matchable_tasks": n, "matchable_sources": len(sources), "gains": gains, "losses": losses,
            "ties": n - len(gains) - len(losses), "delta_hit1": effect,
            "source_balanced_delta": sum(v[0] / v[1] for v in totals.values()) / len(sources) if sources else None,
            "source_cluster_percentile95": interval, "leave_one_source_out_delta": leave_one,
            "gain_sources": sum(any(r["attributes_hit1"] > r["crop_hit1"] for r in groups[s]) for s in sources),
            "bootstrap_seed": seed, "bootstrap_repetitions": repetitions,
            "ranking_evidence_floor_met": n >= 30 and len(sources) >= 20,
            "caution": "One wardrobe/owner; source clusters, not components, are resampled. Small counts remain descriptive; no power or population claim."}
