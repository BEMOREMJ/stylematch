"""Fail closed on ambiguous labels, references, membership and split leakage."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from .contracts import Dataset, Run


def unique(values, label: str) -> set:
    values = list(values)
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")
    return set(values)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_dataset(dataset: Dataset) -> dict:
    wardrobes = {w.wardrobe_id: w for w in dataset.wardrobes}
    unique((w.wardrobe_id for w in dataset.wardrobes), "wardrobe IDs")
    images = {i.image_id: i for i in dataset.images}
    unique((i.image_id for i in dataset.images), "image IDs")
    unique((i.path for i in dataset.images), "image paths")
    items = {g.ref.key: g for g in dataset.garments}
    unique((g.ref.key for g in dataset.garments), "compound item IDs")
    queries = {q.query_id: q for q in dataset.queries}
    unique((q.query_id for q in dataset.queries), "query IDs")
    unique((j.query_id for j in dataset.judgments), "canonical judgment query IDs")
    require({j.query_id for j in dataset.judgments} == set(queries), "incomplete/unknown query judgments")

    for field in ("sha256", "capture_group", "source_group"):
        partitions = defaultdict(set)
        for image in dataset.images:
            partitions[getattr(image, field)].add(image.partition)
        require(all(len(p) == 1 for p in partitions.values()), f"cross-partition {field} leakage")
    for image in dataset.images:
        require(
            (image.permitted_use == "synthetic-engineering") == dataset.synthetic,
            "synthetic/provenance use mismatch",
        )
        if image.kind == "crop":
            parent = images.get(image.parent_image_id)
            require(parent is not None and parent.kind == "inspiration", "crop needs inspiration parent")
            require(parent.partition == image.partition, "crop parent partition mismatch")
            require(parent.source_group == image.source_group, "crop must retain source group")
            require(parent.capture_group == image.capture_group, "crop must retain capture group")
        else:
            require(image.parent_image_id is None, "only crops may declare a parent")
    image_owners = {}
    for item in dataset.garments:
        wardrobe = wardrobes.get(item.ref.wardrobe_id)
        require(wardrobe is not None, "unknown garment wardrobe")
        unique(item.image_ids, "garment image references")
        for image_id in item.image_ids:
            image = images.get(image_id)
            require(image is not None and image.kind == "garment", "unknown/non-garment item image")
            require(image.partition == wardrobe.partition, "garment image partition mismatch")
            require(image_id not in image_owners, "garment image assigned to multiple items")
            image_owners[image_id] = item.ref.key
    for query in dataset.queries:
        wardrobe = wardrobes.get(query.active_wardrobe_id)
        require(wardrobe is not None, "unknown active wardrobe")
        require(wardrobe.partition == query.partition, "query wardrobe partition mismatch")
        image = images.get(query.image_id)
        require(image is not None and image.kind == "inspiration", "unknown/non-inspiration query image")
        require(image.partition == query.partition, "query image partition mismatch")
        if query.crop_image_id is not None:
            crop = images.get(query.crop_image_id)
            require(crop is not None and crop.kind == "crop", "unknown/non-crop reference")
            require(crop.parent_image_id == query.image_id, "crop/query parent mismatch")
    for judgment in dataset.judgments:
        query = queries[judgment.query_id]
        keys = unique((grade.ref.key for grade in judgment.grades), "judgment item IDs")
        eligible = {
            key for key, item in items.items()
            if key[0] == query.active_wardrobe_id and item.category == query.component_category
        }
        require(keys == eligible, "incomplete judgments or invalid wardrobe/category label")
        relevant = any(grade.relevance >= 2 for grade in judgment.grades)
        require(judgment.no_match == (not relevant), "contradictory no-match label")
        require(not judgment.uncertain, "unresolved uncertain judgment cannot be evaluated")

    people = defaultdict(set)
    for wardrobe in dataset.wardrobes:
        people[wardrobe.person_id].add(wardrobe.partition)
    return {
        "person_partition_overlap": sorted(p for p, splits in people.items() if len(splits) > 1),
        "wardrobes": len(wardrobes), "garments": len(items), "images": len(images),
        "queries": len(queries), "no_match_queries": sum(j.no_match for j in dataset.judgments),
        "leakage_checks": ["sha256", "capture_group", "source_group"],
        "near_duplicate_detection": "not performed; hashes detect exact bytes only",
    }


def verify_image_files(dataset: Dataset, root: Path) -> None:
    """Optional local file/hash verification, also preventing symlink escape."""
    root = root.resolve(strict=True)
    for image in dataset.images:
        path = (root / image.path).resolve(strict=True)
        require(path.is_relative_to(root), "image path escapes root")
        require(path.is_file(), "image path is not a file")
        require(sha256(path.read_bytes()).hexdigest() == image.sha256, "image hash mismatch")


def validate_run(dataset: Dataset, run: Run, dataset_sha256: str | None = None) -> None:
    require(run.dataset_id == dataset.dataset_id, "run dataset ID mismatch")
    if dataset_sha256 is not None:
        require(run.dataset_sha256 == dataset_sha256, "run dataset hash mismatch")
    ids = unique((r.query_id for r in run.rankings), "ranking query IDs")
    expected = {q.query_id for q in dataset.queries}
    require(ids <= expected, "unknown ranking query ID")
    if run.status == "complete":
        require(ids == expected, "complete run must explicitly rank or abstain on every query")
