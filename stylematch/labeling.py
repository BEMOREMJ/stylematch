"""Reproducible local CSV review, exhaustive labels and a private import audit."""

import csv
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import random

from .contracts import Dataset, Grade, ItemRef, Judgment
from .preparation import contained, load_pilot, new_json, private_path
from .validation import require, validate_dataset

PAIR_FIELDS = ["query_id", "wardrobe_id", "item_id", "query_image", "crop_image", "candidate_images",
               "reviewer_id", "grade", "uncertain", "notes"]
QUERY_FIELDS = ["query_id", "query_image", "crop_image", "category", "eligible_candidates",
                "reviewer_id", "no_match", "uncertain", "notes"]
ATTRIBUTE_FIELDS = ["entity_kind", "entity_id", "category", "reviewer_id", "color", "pattern",
                    "garment_type", "silhouette", "texture", "notes"]
EFFORT_FIELDS = ["activity", "reviewer_id", "status", "seconds", "notes"]

INSTRUCTIONS = """PRIVATE DEVELOPMENT REVIEW ONLY. No model predictions or scores.
Keep IDs, paths, reviewer IDs, rows and columns unchanged. Candidate order was
shuffled with the seed in template.json. View prepared images locally; never
upload these sheets or images. candidate_images separates multiple paths with |.

labels.csv: grade every eligible candidate: 0 unacceptable; 1 partial resemblance
insufficient to recommend; 2 acceptable; 3 strong recreation. Multiple 2/3 matches
are allowed. Set uncertain to true or false. unknown/blank is unresolved, not 0.
queries.csv: set no_match true exactly when exhaustive labels contain no 2/3;
use true/false for uncertain. Empty pools still need an explicit query decision.
If unresolved, keep unknown/true and add notes. Import will refuse scoring until
all candidate and query labels are resolved. Do not invent labels to meet quotas.

attributes.csv: optional observable human attribute candidates, initially unknown.
Keep unknown when unobservable; do not leave blanks. No sensitive traits or body
fit judgments. These fields have no reliability gates or predictive-accuracy claim.
effort.csv: record actual total human seconds for capture, cropping and annotation;
status measured requires a nonnegative finite value. Otherwise keep unknown,
seconds blank, and explain the missing measurement in notes. Do not report tool
execution time as human effort. The same reviewer doing another pass is not an
independent reviewer. Keep prior templates/reviews for within-reviewer comparison.
Never enter formulas. Preserve this instruction file with the CSVs.
"""


def template_rows(dataset: Dataset, reviewer: str, seed: int) -> dict:
    images = {image.image_id: image.path for image in dataset.images}
    pairs, queries, attributes = [], [], []
    for query in dataset.queries:
        candidates = sorted(
            (g for g in dataset.garments if g.ref.wardrobe_id == query.active_wardrobe_id
             and g.category == query.component_category), key=lambda g: g.ref.key,
        )
        random.Random(f"{seed}:{query.query_id}").shuffle(candidates)
        context = {"query_id": query.query_id, "query_image": images[query.image_id],
                   "crop_image": images[query.crop_image_id] if query.crop_image_id else "",
                   "reviewer_id": reviewer}
        queries.append({**context, "category": query.component_category, "eligible_candidates": str(len(candidates)),
                        "no_match": "unknown", "uncertain": "unknown", "notes": ""})
        for garment in candidates:
            pairs.append({**context, "wardrobe_id": garment.ref.wardrobe_id, "item_id": garment.ref.item_id,
                          "candidate_images": "|".join(images[i] for i in garment.image_ids),
                          "grade": "unknown", "uncertain": "unknown", "notes": ""})
        attributes.append({"entity_kind": "component", "entity_id": query.query_id,
                           "category": query.component_category, "reviewer_id": reviewer})
    for garment in dataset.garments:
        attributes.append({"entity_kind": "garment", "entity_id": "/".join(garment.ref.key),
                           "category": garment.category, "reviewer_id": reviewer})
    for attribute in attributes:
        attribute.update({field: "unknown" for field in ("color", "pattern", "garment_type", "silhouette", "texture")})
        attribute["notes"] = ""
    effort = [{"activity": activity, "reviewer_id": reviewer, "status": "unknown", "seconds": "",
               "notes": "not recorded yet"} for activity in ("capture", "cropping", "annotation")]
    return {"labels.csv": (PAIR_FIELDS, pairs), "queries.csv": (QUERY_FIELDS, queries),
            "attributes.csv": (ATTRIBUTE_FIELDS, attributes), "effort.csv": (EFFORT_FIELDS, effort)}


def export_template(root: Path, output: Path, seed: int) -> dict:
    require(type(seed) is int and seed >= 0, "label seed must be a nonnegative integer")
    dataset, preparation = load_pilot(root)
    output = private_path(output)
    output.mkdir(parents=True, exist_ok=False)
    reviewer = preparation["plan"]["reviewer_id"]
    rows = template_rows(dataset, reviewer, seed)
    for filename, (fields, values) in rows.items():
        with (output / filename).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(values)
    (output / "INSTRUCTIONS.txt").write_text(INSTRUCTIONS, encoding="utf-8", newline="\n")
    metadata = {"schema_version": 1, "dataset_sha256": preparation["dataset_sha256"],
                "reviewer_id": reviewer, "seed": seed, "randomization": "python-3.12 Random(str(seed)+':'+query_id)",
                "candidate_rows": len(rows["labels.csv"][1]), "query_rows": len(rows["queries.csv"][1])}
    new_json(output / "template.json", metadata)
    return metadata


def read_sheet(root: Path, name: str, fields: list[str]) -> tuple[list[dict], str]:
    path = contained(root, name)
    content = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == fields, f"{name}: columns changed or duplicated")
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            f"{name}: malformed or incomplete CSV row")
    return rows, sha256(content).hexdigest()


def unchanged(rows: list[dict], expected: list[dict], editable: set[str], name: str) -> None:
    require(len(rows) == len(expected), f"{name}: missing/extra rows; exhaustive review required")
    for row, reference in zip(rows, expected, strict=True):
        require(all(row[field] == value for field, value in reference.items() if field not in editable),
                f"{name}: identity, membership, order or context changed")


def resolved_bool(value: str, field: str) -> bool:
    require(value in ("true", "false"), f"{field}: unresolved/invalid; enter true or false")
    return value == "true"


def import_labels(root: Path, labels: Path, output_name: str) -> Dataset:
    dataset, preparation = load_pilot(root)
    labels = private_path(labels)
    metadata = json.loads(contained(labels, "template.json").read_bytes())
    require(isinstance(metadata, dict) and metadata.get("schema_version") == 1, "unsupported label-template version")
    require(metadata.get("dataset_sha256") == preparation["dataset_sha256"], "label template dataset binding mismatch")
    reviewer = preparation["plan"]["reviewer_id"]
    require(metadata.get("reviewer_id") == reviewer, "one actual reviewer identity required")
    seed = metadata.get("seed")
    require(type(seed) is int and seed >= 0, "invalid recorded randomization seed")
    expected = template_rows(dataset, reviewer, seed)
    require(metadata.get("candidate_rows") == len(expected["labels.csv"][1])
            and metadata.get("query_rows") == len(expected["queries.csv"][1]), "template row-count mismatch")
    sheets, hashes = {}, {}
    editable = {
        "labels.csv": {"grade", "uncertain", "notes"},
        "queries.csv": {"no_match", "uncertain", "notes"},
        "attributes.csv": {"color", "pattern", "garment_type", "silhouette", "texture", "notes"},
        "effort.csv": {"status", "seconds", "notes"},
    }
    for name, (fields, reference) in expected.items():
        values, digest = read_sheet(labels, name, fields)
        unchanged(values, reference, editable[name], name)
        sheets[name], hashes[name] = values, digest
    grades = {q.query_id: [] for q in dataset.queries}
    for row in sheets["labels.csv"]:
        require(row["grade"] in ("0", "1", "2", "3"), "grade unresolved/invalid; blank or unknown is not grade 0")
        require(not resolved_bool(row["uncertain"], "candidate uncertainty"), "unresolved uncertain candidate label")
        grades[row["query_id"]].append(Grade(
            ref=ItemRef(wardrobe_id=row["wardrobe_id"], item_id=row["item_id"]), relevance=int(row["grade"]),
        ))
    judgments = []
    for row in sheets["queries.csv"]:
        judgments.append(Judgment(
            query_id=row["query_id"], reviewer_id=reviewer,
            no_match=resolved_bool(row["no_match"], "no_match"),
            uncertain=resolved_bool(row["uncertain"], "query uncertainty"), notes=row["notes"],
            grades=grades[row["query_id"]],
        ))
    # Round-trip through strict existing contracts; semantic checks remain fail closed.
    labeled = Dataset.model_validate({**dataset.model_dump(), "judgments": [j.model_dump() for j in judgments]})
    validate_dataset(labeled)
    for row in sheets["attributes.csv"]:
        for field in editable["attributes.csv"] - {"notes"}:
            require(bool(row[field].strip()), "attribute blanks must be recorded as explicit unknown")
    effort = []
    for row in sheets["effort.csv"]:
        require(row["status"] in ("measured", "unknown"), "effort status must be measured or unknown")
        seconds = None
        if row["status"] == "measured":
            try:
                seconds = float(row["seconds"])
            except ValueError as exc:
                raise ValueError("measured human effort needs actual numeric seconds") from exc
            require(isfinite(seconds) and seconds >= 0, "human seconds must be finite and nonnegative")
        else:
            require(not row["seconds"] and bool(row["notes"].strip()), "unknown effort requires blank seconds and a reason")
        effort.append({**row, "seconds": seconds})
    require(output_name.endswith(".json") and "/" not in output_name and "\\" not in output_name,
            "output must be a new JSON filename in the pilot directory")
    target = private_path(contained(root, output_name, exists=False))
    audit_path = target.with_suffix(".label-audit.json")
    require(not target.exists() and not audit_path.exists(), "label import cannot overwrite previous files")
    require(contained(labels, "INSTRUCTIONS.txt").read_text(encoding="utf-8") == INSTRUCTIONS,
            "label editing instructions must be preserved")
    new_json(audit_path, {
        "schema_version": 1, "template": metadata, "csv_sha256": hashes,
        "reviewer_id": reviewer, "independent_reviewers": False,
        "human_effort": effort, "attributes": sheets["attributes.csv"],
        "candidate_review_notes": [
            {k: row[k] for k in ("query_id", "wardrobe_id", "item_id", "notes")}
            for row in sheets["labels.csv"]
        ],
        "dataset_sha256": sha256((json.dumps(labeled.model_dump(), indent=2) + "\n").encode()).hexdigest(),
    })
    new_json(target, labeled.model_dump())
    return labeled
