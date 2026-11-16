"""Private development attribute review and interpretation evaluation (001D)."""
import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import random
import sys

from .preparation import contained, load_pilot, new_json, private_path
from .validation import require

VOCAB = {
    "garment_type": ["tshirt", "shirt", "sweater", "sweatshirt", "vest", "jacket", "coat",
                     "trousers", "jeans", "shorts", "skirt", "dress", "other", "unknown"],
    "color": ["black", "white", "gray", "beige", "brown", "red", "orange", "yellow", "green",
              "blue", "purple", "pink", "multicolor", "unknown"],
    "pattern": ["solid", "striped", "checked", "dotted", "graphic", "floral", "other", "unknown"],
}
GUIDE = """Label only visible evidence in the garment or selected component crop.
Type: tshirt = tee/polo; shirt = button-front shirt/blouse; sweater = knitted pullover/cardigan;
sweatshirt = sweatshirt/hoodie; vest = sleeveless outer layer; jacket = short outer layer;
coat = longer outer layer; trousers = non-denim long bottoms; jeans = visibly denim long bottoms;
shorts = short bottoms (including denim); skirt; dress; other = visibly a garment outside this list.
If construction or the intended component cannot be distinguished, choose unknown.
Color: main visible garment area, ignoring background, skin, shadow and small trim/logos.
Navy/light blue -> blue; cream/tan -> beige; silver -> gray; burgundy -> red.
Choose multicolor when two or more clearly visible colors have no dominant color (roughly half
or less of the visible garment area for the largest). Choose unknown if lighting/occlusion
prevents a defensible color judgment. Never infer concealed regions.
Pattern: solid = no visible repeated motif/graphic (texture, seams and small logos do not count);
striped = repeated lines; checked = plaid/grid; dotted = spots; graphic = prominent lettering,
logo or illustration; floral = flowers/leaves; other = another clear pattern or mixed patterns.
Unknown = insufficient detail, conflicting interpretations, or multiple garments without a
distinguishable target. Label each field independently. Unknown is an explicit completed label;
an empty selection means unfinished. Do not infer material, brand, fit or hidden features.
Example (hypothetical, not a pilot answer): a clearly visible blue denim pair of short bottoms
without a print is shorts / blue / solid. If only a tiny blue patch is visible, type and pattern
may be unknown while color can still be blue. Mark supplies every actual label.
"""


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def inputs(dataset):
    """Pixel references only; no grades, human attributes, category or original names."""
    images = {i.image_id: i for i in dataset.images}
    rows = []
    for garment in dataset.garments:
        require(len(garment.image_ids) == 1, "001D requires one registered photo per garment")
        rows.append({"kind": "wardrobe", "entity": list(garment.ref.key),
                     "image": images[garment.image_ids[0]].model_dump()})
    for query in dataset.queries:
        require(query.crop_image_id is not None, "human-selected component crop required")
        rows.append({"kind": "crop", "entity": query.query_id,
                     "image": images[query.crop_image_id].model_dump()})
    return rows


def export_review(pilot, output, seed=130363, dataset_name="dataset-labeled-01.json"):
    dataset, audit = load_pilot(pilot, dataset_name, require_labels=True)
    rows = inputs(dataset)
    random.Random(seed).shuffle(rows)
    output = private_path(output)
    output.mkdir(parents=True, exist_ok=False)
    mapping, display = [], []
    for index, row in enumerate(rows, 1):
        item_id = f"view-{index:03d}"
        image = row.pop("image")
        source = contained(pilot, image["path"])
        require(digest(source) == image["sha256"], "input image hash mismatch")
        mapping.append({"id": item_id, **row, "image_path": image["path"], "sha256": image["sha256"]})
        display.append({"id": item_id, "src": "data:image/png;base64," + base64.b64encode(source.read_bytes()).decode()})
    binding = {"schema_version": 1, "seed": seed, "dataset_sha256": digest(pilot / dataset_name),
               "reviewer_id": audit["plan"]["reviewer_id"], "vocabulary": VOCAB, "items": mapping}
    new_json(output / "mapping.json", binding)
    bundle = digest(output / "mapping.json")
    html = Path(__file__).with_name("attribute_review.html").read_text(encoding="utf-8")
    payload = {"bundle": bundle, "vocabulary": VOCAB, "guide": GUIDE, "items": display}
    html = html.replace("/*PAYLOAD*/null", json.dumps(payload).replace("<", "\\u003c"))
    (output / "review.html").write_text(html, encoding="utf-8")
    (output / "INSTRUCTIONS.txt").write_text(GUIDE, encoding="utf-8")
    return {"items": len(mapping), "review": str(output / "review.html"), "bundle": bundle}


def import_reference(review, labels, output):
    review, labels = private_path(review), private_path(labels)
    mapping = json.loads((review / "mapping.json").read_bytes())
    document = json.loads(labels.read_bytes())
    require(document.get("bundle") == digest(review / "mapping.json"), "review bundle mismatch")
    require(document.get("completed_by") == "Mark", "owner completion declaration required")
    rows = document.get("labels")
    require(isinstance(rows, list), "labels must be a list")
    require([r.get("id") for r in rows] == [r["id"] for r in mapping["items"]], "review membership/order mismatch")
    for row in rows:
        require(set(row) == {"id", *VOCAB}, "unexpected label fields")
        for field, choices in VOCAB.items():
            require(row[field] in choices, f"unfinished/invalid {field}")
    effort = document.get("annotation_seconds")
    require(effort is None or (type(effort) in (int, float) and isfinite(effort) and effort >= 0), "invalid measured effort")
    new_json(output, {"schema_version": 1, "preserved_at_utc": datetime.now(timezone.utc).isoformat(),
                      "bundle": document["bundle"], "source_sha256": digest(labels),
                      "mapping_sha256": digest(review / "mapping.json"), "mapping": mapping,
                      "completed_by": "Mark", "labels": rows, "annotation_seconds": effort,
                      "effort_method": document.get("effort_method", "unknown")})
    return {"reference_items": len(rows), "annotation_seconds": effort, "reference": str(output)}


def parse_prediction(raw):
    """Strict JSON only. No guessing, repair, synonym mapping or fence removal."""
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, "duplicate JSON key")
                result[key] = value
            return result
        value = json.loads(raw, object_pairs_hook=unique)
        require(type(value) is dict and set(value) == {*VOCAB, "description"}, "wrong schema keys")
        for field, choices in VOCAB.items():
            require(type(value[field]) is str and value[field] in choices, f"invalid {field}")
        require(type(value["description"]) is str and 0 < len(value["description"].strip()) <= 240,
                "description must contain 1..240 characters")
        return value, None
    except (ValueError, TypeError) as exc:
        return None, str(exc)


def fraction(n, d):
    return {"count": n, "total": d, "percent": 100 * n / d if d else None}


def score(reference, predictions):
    ids = [r["id"] for r in reference["labels"]]
    require([p["id"] for p in predictions] == ids, "prediction membership/order mismatch")
    parsed = {p["id"]: parse_prediction(p["raw"])[0] for p in predictions}
    kinds = {r["id"]: r["kind"] for r in reference["mapping"]["items"]}
    groups = {"all": ids, "wardrobe": [i for i in ids if kinds[i] == "wardrobe"],
              "crop": [i for i in ids if kinds[i] == "crop"],
              "occluded_components": [r["id"] for r in reference["mapping"]["items"]
                                       if r["kind"] == "crop" and r["entity"] in ("task-009", "task-010")]}
    labels = {r["id"]: r for r in reference["labels"]}
    report = {}
    for group, members in groups.items():
        fields = {}
        for field in VOCAB:
            known = [i for i in members if labels[i][field] != "unknown"]
            unknown = [i for i in members if labels[i][field] == "unknown"]
            answered = [i for i in members if parsed[i] and parsed[i][field] != "unknown"]
            known_answered = [i for i in known if i in answered]
            correct = sum(parsed[i][field] == labels[i][field] for i in known_answered)
            fields[field] = {"correct_on_human_known": fraction(correct, len(known)),
                             "answered_on_human_known": fraction(len(known_answered), len(known)),
                             "accuracy_among_answered_known": fraction(correct, len(known_answered)),
                             "answered_all": fraction(len(answered), len(members)),
                             "asserted_on_human_unknown": fraction(sum(i in answered for i in unknown), len(unknown))}
        report[group] = {"items": len(members), "schema_valid": fraction(sum(parsed[i] is not None for i in members), len(members)),
                         "fields": fields}
    report["failures"] = [{"id": p["id"], "error": parse_prediction(p["raw"])[1]} for p in predictions if parsed[p["id"]] is None]
    return report


def import_descriptions(run, labels, output):
    run, labels = private_path(run), private_path(labels)
    expected = json.loads((run / "description-review.json").read_bytes())
    document = json.loads(labels.read_bytes())
    require(document.get("completed_by") == "Mark", "Mark description spot-check pending")
    require(document.get("binding") == digest(run / "description-review.json"), "description review binding mismatch")
    rows = document.get("items", [])
    require([r.get("id") for r in rows] == [r["id"] for r in expected["items"]], "description membership mismatch")
    for row, item in zip(rows, expected["items"], strict=True):
        require(set(row) == {"id", "unsupported", "notes"}, "invalid description review schema")
        require(row["unsupported"] in ("true", "false", "unknown", "missing"), "unresolved description check")
        require(type(row["notes"]) is str, "invalid description notes")
        require(row["unsupported"] not in ("true", "unknown") or bool(row["notes"].strip()), "unsupported/uncertain detail needs notes")
        require(bool(item["description"]) == (row["unsupported"] != "missing"), "missing-description status contradicts output")
    counts = {key: sum(r["unsupported"] == key for r in rows) for key in ("true", "false", "unknown", "missing")}
    new_json(output, {"completed_by": "Mark", "source_sha256": digest(labels), "binding": document["binding"],
                      "context": expected.get("context", "schema-valid descriptions"),
                      "items": rows, "counts": counts,
                      "unsupported_among_decidable": fraction(counts["true"], counts["true"] + counts["false"])})
    return {"description_checks": len(rows), "counts": counts}


def export_raw_review(run, reference_path, output):
    """Show raw visible claims for owner review, without repairing schema failures."""
    run, reference_path, output = private_path(run), private_path(reference_path), private_path(output)
    reference = json.loads(reference_path.read_bytes())
    binding = json.loads((run / "reference-binding.json").read_bytes())
    require(binding["reference_sha256"] == digest(reference_path), "run reference mismatch")
    predictions = json.loads((run / "predictions.json").read_bytes())["predictions"]
    payloads = json.loads((run / "input-payloads.json").read_bytes())["items"]
    ids = [r["id"] for r in reference["labels"]]
    require([p["id"] for p in payloads] == ids, "run input membership mismatch")
    by_id = {p["id"]: p for p in predictions}
    require(len(by_id) == len(predictions) and set(by_id).issubset(ids), "unexpected/duplicate predictions")
    occluded = {r["id"] for r in reference["mapping"]["items"]
                if r["kind"] == "crop" and r["entity"] in ("task-009", "task-010")}
    output.mkdir(parents=True, exist_ok=False)
    context = ("Owner factuality check of raw model responses, including invalid or truncated JSON. "
               "This does not repair predictions or change attribute/schema scores. "
               "Flag unsupported visible claims; use Cannot decide if the text cannot be judged.")
    items, display = [], []
    for payload in payloads:
        prediction = by_id.get(payload["id"], {})
        raw = prediction.get("raw", "")
        require(type(raw) is str, "raw model output must be text")
        valid = parse_prediction(raw)[1] is None
        reason = prediction.get("finish_reason", "missing")
        items.append({"id": payload["id"], "description": raw or None, "schema_valid": valid,
                      "finish_reason": reason, "text_source": "unmodified raw model response"})
        display.append({"id": payload["id"], "pixels": payload["pixels"], "description": raw or None,
                        "occluded": payload["id"] in occluded,
                        "source_note": f"Raw response; schema {'valid' if valid else 'invalid'}; finish reason: {reason}."})
    new_json(output / "description-review.json", {"context": context,
                                                  "run_predictions_sha256": digest(run / "predictions.json"),
                                                  "items": items})
    data = {"binding": digest(output / "description-review.json"), "context": context, "items": display}
    html = Path(__file__).with_name("description_review.html").read_text(encoding="utf-8")
    (output / "description-review.html").write_text(
        html.replace("/*PAYLOAD*/null", json.dumps(data).replace("<", "\\u003c")), encoding="utf-8")
    return {"items": len(items), "review": str(output / "description-review.html"), "context": context}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("review")
    review.add_argument("--pilot", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    importer = commands.add_parser("import-reference")
    importer.add_argument("--review", type=Path, required=True)
    importer.add_argument("--labels", type=Path, required=True)
    importer.add_argument("--output", type=Path, required=True)
    description = commands.add_parser("import-descriptions")
    description.add_argument("--run", type=Path, required=True)
    description.add_argument("--labels", type=Path, required=True)
    description.add_argument("--output", type=Path, required=True)
    raw = commands.add_parser("raw-output-review")
    raw.add_argument("--run", type=Path, required=True)
    raw.add_argument("--reference", type=Path, required=True)
    raw.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "review":
            result = export_review(args.pilot, args.output)
        elif args.command == "import-reference":
            result = import_reference(args.review, args.labels, args.output)
        elif args.command == "import-descriptions":
            result = import_descriptions(args.run, args.labels, args.output)
        else:
            result = export_raw_review(args.run, args.reference, args.output)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"interpretation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
