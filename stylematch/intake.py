"""Private Option A intake. No model loading, ranking, score display or tuning.

Custody is procedural for Mark's account. A separate ranking process can install
the Python file-access guard below; it is not an OS account security boundary.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import random
import shutil
import sys

from .contracts import Image
from .interpretation import VOCAB
from .preparation import REPOSITORY, sanitized_pixels
from .validation import require

FREEZE_ID = "STYLEMATCH-001E-A1-A-v1"
LOCAL = timezone(timedelta(hours=3), "Africa/Nairobi")
QUEUE_COLUMNS = ("position", "source_id", "source_group", "original_file", "source_reference",
                 "permission_basis", "permission_reference")
METHODS = {"category", "crop", "attributes-assisted"}


def now_local():
    return datetime.now(LOCAL)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def inside(root, relative):
    Image.relative_path(relative)
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), "path escapes private root")
    return path


def load_store(root):
    root = root.resolve()
    receipt = read(root / "freeze-receipt.json")
    config = read(root / "protocol/frozen-config.json")
    require(receipt["freeze_id"] == config["freeze_id"] == FREEZE_ID, "wrong freeze")
    require(digest(root / "protocol/frozen-config.json") == receipt["config_sha256"], "frozen config changed")
    require(digest(root / "locked/bindings.json") == receipt["bindings_sha256"], "locked binding changed")
    require(digest(root / "locked/garment-tags.json") == receipt["garment_tags_sha256"], "locked tags changed")
    for image in read(root / "locked/bindings.json")["garment_images"]:
        require(digest(inside(root / "locked", image["path"])) == image["sha256"], "locked garment pixels changed")
    return root, config, receipt


def records(root):
    result, previous = [], None
    for n, path in enumerate(sorted((root / "screening/records").glob("*.json")), 1):
        record = read(path)
        require(path.name == f"{n:04d}.json" and record["ordinal"] == n
                and record["previous_sha256"] == previous, "screening chain changed")
        result.append(record)
        previous = digest(path)
    with (root / "source-screening.csv").open(encoding="utf-8", newline="") as stream:
        mirror = list(csv.DictReader(stream))
    require(len(mirror) == len(result) and all(
        (row["ordinal"], row["source_id"], row["decision"], row["reason"], row["recorded_at"], row["record_sha256"])
        == (str(n), record["source"]["source_id"], record["decision"], record["reason"], record["recorded_at"],
            digest(root / f"screening/records/{n:04d}.json"))
        for n, (row, record) in enumerate(zip(mirror, result, strict=True), 1)), "screening log/record mismatch")
    return result


def cap_reason(config, screened, now):
    require(now.tzinfo is not None, "timezone-aware clock required")
    if len(screened) >= config["collection"]["screened_sources_cap"]:
        return "36 screened sources"
    if sum(r["decision"] == "include" for r in screened) >= config["collection"]["independent_sources_target"]:
        return "24 eligible independent sources"
    if now >= datetime.fromisoformat(config["collection_window"]["cutoff_exclusive"]):
        return "local calendar cutoff"
    return None


def initialize(root, config_path, binding_path, commit):
    """Called only after the freeze commit has been pushed and verified."""
    root = root.resolve()
    require(not root.is_relative_to(REPOSITORY) and root.name == FREEZE_ID,
            "use a new private freeze folder outside the repository")
    config, bindings = read(config_path), read(binding_path)
    require(config["status"] == "FROZEN" and config["selected_design"] == "A"
            and config["freeze_id"] == bindings["freeze_id"] == FREEZE_ID, "approved Option A required")
    require(config["canonical_reviewer"] == config["label_custodian"] == "Mark", "owner decision mismatch")
    require(bindings["public_bindings"] == config["public_bindings"], "source binding mismatch")
    for name, expected in config["public_bindings"].items():
        content = inside(REPOSITORY, name).read_bytes().replace(b"\r\n", b"\n")
        require(sha256(content).hexdigest() == expected, f"pinned public source changed: {name}")
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "full verified commit required")
    root.mkdir(parents=True, exist_ok=False)
    for relative in ("originals", "screening/records", "annotation/looks", "annotation/crops",
                     "custodian/labels", "custodian/predictions", "inputs", "seals"):
        (root / relative).mkdir(parents=True)
    # These are already accepted development images, not newly collected looks.
    pilot = REPOSITORY / bindings["pilot_root"]
    for image in bindings["garment_images"]:
        source = inside(pilot, image["path"])
        require(digest(source) == image["sha256"], "locked garment image changed")
        target = inside(root / "locked", image["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(source.read_bytes())
    tags = REPOSITORY / bindings["canonical_tags_path"]
    require(digest(tags) == bindings["canonical_tags_sha256"], "canonical tags changed")
    shutil.copyfile(tags, root / "locked/garment-tags.json")
    write_json(root / "locked/bindings.json", bindings)
    (root / "protocol").mkdir()
    shutil.copyfile(config_path, root / "protocol/frozen-config.json")
    write_json(root / "freeze-receipt.json", {"freeze_id": FREEZE_ID, "freeze_commit": commit,
        "config_sha256": digest(config_path), "bindings_sha256": digest(root / "locked/bindings.json"),
        "garment_tags_sha256": digest(tags), "created_at": now_local().isoformat(),
        "custody": "Mark; procedural separation, not an independent OS identity",
        "heldout_data_seal": None, "heldout_label_seal": None, "predictions_locked": False})
    with (root / "source-queue.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, QUEUE_COLUMNS)
        writer.writeheader()
        writer.writerow({"position": 1, "source_id": "look-001", "source_group": "a1a-look-001",
                         "original_file": "look-001.jpg"})
    with (root / "source-screening.csv").open("x", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow(("ordinal", "source_id", "decision", "reason", "recorded_at", "record_sha256"))
    for filename, columns in {
        "annotation/components.csv": ("source_id", "category", "occlusion", "include", "exclusion_reason", "crop_box"),
        "annotation/query-tags.csv": ("query_id", "garment_type", "color", "pattern"),
        "annotation/effort.csv": ("subject_id", "stage", "active_seconds", "correction_notes", "missing_reason"),
        "custodian/labels/relevance.csv": ("query_id", "wardrobe_id", "item_id", "grade", "uncertain", "notes"),
        "custodian/labels/repeat-review.csv": ("query_id", "wardrobe_id", "item_id", "grade", "uncertain", "notes"),
    }.items():
        with (root / filename).open("x", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(columns)
    write_json(root / "custodian/review-schedule.json", {"status": "pending collection and tag seal",
        "grade_not_before": None, "repeat_sources": None, "rankings_hidden": True})
    (root / "FIRST-LOOK.txt").write_text(
        f"Freeze: {FREEZE_ID}\nVerified commit: {commit}\n"
        f"Cutoff (exclusive): {config['collection_window']['cutoff_exclusive']}\n\n"
        f"Run commands from {REPOSITORY}.\n"
        f"1. Save the first permitted fresh JPEG/PNG in {root / 'originals'}.\n"
        "2. Fill source-queue.csv with the prospective sources in order (up to 36). "
        "Row 1 is only a template, not a registered source. Supply actual source and permission references. "
        "Related shots/reposts share a source group. Finish and lock the queue before screening; do not reorder or top up later.\n"
        f"3. .venv/Scripts/python.exe -m stylematch.intake lock-queue --root '{root}'\n"
        f"4. .venv/Scripts/python.exe -m stylematch.intake screen --root '{root}' "
        "--source-id look-001 --decision include --components <visible supported categories> "
        "--related-sources-checked --occlusion '<actual note or none>'\n"
        "Replace angle-bracket placeholders; categories are tops bottoms outerwear. "
        "Confirm permission and compare manually against development sources before inclusion.\n"
        "To exclude: use --decision exclude --reason '<actual reason>' instead. "
        "Every exclusion consumes a screen and stays in source-screening.csv plus chained JSON receipts.\n"
        "5. Cropping/tagging come next with predictions hidden. Record crop and query_tag "
        "active seconds separately in annotation/effort.csv, including corrections; missing time is unknown. "
        "Do not write relevance or no-match decisions into intake or query-tag files.\n\n"
        "Stop at the first cap: 24 eligible, 36 screened, or cutoff. Queue exhaustion does not allow additions. "
        "No inference, predictions or scoring have been run. The data/label seals are pending. "
        "Close collection, seal tags, wait >=24h before grading, complete seeded repeat review, "
        "seal inputs and labels separately, then lock all fixed predictions before any label release/scoring.\n"
        "Mark is sole custodian; local separation/Python guard is procedural, not independent OS custody.\n",
        encoding="utf-8")


def lock_queue(root, now=None):
    root, config, _ = load_store(root)
    require(cap_reason(config, records(root), now or now_local()) is None, "collection cap reached")
    with (root / "source-queue.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(tuple(reader.fieldnames or ()) == QUEUE_COLUMNS, "unexpected queue fields")
        queue = list(reader)
    require(1 <= len(queue) <= 36, "queue must contain 1..36 ordered prospective sources")
    for n, row in enumerate(queue, 1):
        require(row["position"] == str(n) and row["source_id"] == f"look-{n:03d}", "queue order/IDs invalid")
        require(bool(row["source_group"].strip()) and bool(row["source_reference"].strip()), "record actual source/group")
        if row["original_file"]:
            inside(root / "originals", row["original_file"])
    write_json(root / "screening/queue-lock.json", {"queue_sha256": digest(root / "source-queue.csv"),
        "locked_at": (now or now_local()).isoformat(), "sources": queue})


def screen(root, source_id, decision, reason="", components=(), related_checked=False, occlusion="", now=None):
    root, config, _ = load_store(root)
    now = now or now_local()
    screened = records(root)
    stop = cap_reason(config, screened, now)
    require(stop is None, f"collection stopped: {stop}")
    queue_lock = read(root / "screening/queue-lock.json")
    require(digest(root / "source-queue.csv") == queue_lock["queue_sha256"], "ordered queue changed")
    queue = queue_lock["sources"]
    require(len(screened) < len(queue), "frozen queue exhausted; no outcome-driven additions")
    entry = queue[len(screened)]
    require(source_id == entry["source_id"], "screen the next queued source, including exclusions")
    require(decision in ("include", "exclude"), "invalid decision")
    require(set(components) <= {"tops", "bottoms", "outerwear"} and len(components) == len(set(components)), "invalid components")
    if decision == "include":
        require(related_checked, "manual related-source/near-duplicate review required")
        require(bool(components), "identify supported components before relevance grading")
    else:
        require(bool(reason.strip()), "record exclusion reason")
    bindings = read(root / "locked/bindings.json")
    old = bindings["development_overlap"]
    rejection, raw_hash, pixel_hash, prepared_hash, pixels = None, None, None, None, None
    if decision == "include":
        groups = {i["source_group"] for i in old} | {i["capture_group"] for i in old}
        groups |= {r["source"]["source_group"] for r in screened}
        if entry["source_group"] in groups:
            rejection = "related/duplicate source group"
        elif entry["permission_basis"] not in ("owner-created", "explicit-permission") or not entry["permission_reference"].strip():
            rejection = "permission not established"
        elif not entry["original_file"]:
            rejection = "original unavailable"
        else:
            try:
                original = inside(root / "originals", entry["original_file"])
                raw = original.read_bytes()
                raw_hash = sha256(raw).hexdigest()
                pixels, _ = sanitized_pixels(raw)
                pixel_hash = sha256(f"{pixels.width}x{pixels.height}:".encode() + pixels.tobytes()).hexdigest()
                encoded = BytesIO()
                pixels.save(encoded, format="PNG")
                prepared_hash = sha256(encoded.getvalue()).hexdigest()
                hashes = {i["sha256"] for i in old} | {r.get("original_sha256") for r in screened} | {r.get("prepared_sha256") for r in screened}
                pixel_hashes = {i["pixel_sha256"] for i in old} | {r.get("pixel_sha256") for r in screened}
                if raw_hash in hashes or prepared_hash in hashes or pixel_hash in pixel_hashes:
                    rejection = "exact bytes or decoded pixels overlap development/prior source"
            except (OSError, ValueError) as error:
                rejection = f"unreadable/unsafe/unsupported original: {error}"
    final = "exclude" if rejection else decision
    n = len(screened) + 1
    record = {"ordinal": n, "source": entry, "decision": final, "requested_decision": decision,
        "reason": rejection or reason, "supported_components": list(components), "occlusion": occlusion,
        "related_sources_checked": related_checked, "recorded_at": now.isoformat(),
        "original_sha256": raw_hash, "pixel_sha256": pixel_hash, "prepared_sha256": prepared_hash,
        "previous_sha256": digest(root / f"screening/records/{n-1:04d}.json") if n > 1 else None}
    if final == "include":
        with (root / f"annotation/looks/{source_id}.png").open("xb") as stream:
            pixels.save(stream, format="PNG")
    destination = root / f"screening/records/{n:04d}.json"
    write_json(destination, record)
    with (root / "source-screening.csv").open("a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerow((n, source_id, final, record["reason"], record["recorded_at"], digest(destination)))
    return {"source_id": source_id, "decision": final, "reason": record["reason"],
            "screened": n, "eligible": sum(r["decision"] == "include" for r in screened) + (final == "include"),
            "stop": cap_reason(config, screened + [record], now)}


def review_schedule(source_ids, tag_sealed_at):
    ordered = sorted(source_ids)
    require(ordered and len(ordered) == len(set(ordered)), "unique eligible sources required")
    random.Random("20261117:recheck-sources").shuffle(ordered)
    require(tag_sealed_at.tzinfo is not None, "tag seal needs timezone")
    return {"grade_not_before": (tag_sealed_at + timedelta(hours=24)).isoformat(),
            "repeat_sources": ordered[:(len(ordered) + 4) // 5], "rankings_hidden": True}


def ranking_projection(dataset, attributes):
    """Custodian projection only; no labels, provenance, source names or notes."""
    images = {i.image_id: i for i in dataset.images}
    queries, garments, used = [], [], set()
    for g in dataset.garments:
        fields = attributes["wardrobe"][g.ref.key]
        require(set(fields) == set(VOCAB) and all(fields[f] in VOCAB[f] for f in VOCAB), "invalid wardrobe fields")
        garments.append({"ref": g.ref.model_dump(), "category": g.category, "image_ids": g.image_ids, "attributes": fields})
        used.update(g.image_ids)
    for q in dataset.queries:
        fields = attributes["crop"][q.query_id]
        require(q.crop_image_id and set(fields) == set(VOCAB) and all(fields[f] in VOCAB[f] for f in VOCAB), "invalid crop fields")
        queries.append({"query_id": q.query_id, "active_wardrobe_id": q.active_wardrobe_id,
                        "component_category": q.component_category, "crop_image_id": q.crop_image_id, "attributes": fields})
        used.add(q.crop_image_id)
    return {"freeze_id": FREEZE_ID, "garments": garments, "queries": queries,
            "images": [{"image_id": key, "path": f"images/{key}.png", "sha256": images[key].sha256} for key in sorted(used)]}


def file_seal(root, relative_files):
    require(bool(relative_files), "cannot seal an empty bundle")
    require(len(relative_files) == len(set(relative_files)), "duplicate seal path")
    return {name: digest(inside(root, name)) for name in sorted(relative_files)}


def lock_prediction_receipt(input_seal, label_seal, completed_review, prediction_files, now):
    """Bookkeeping only; actual complete/grounded run validation precedes this."""
    require(bool(input_seal) and bool(label_seal), "input and label seals required")
    require(completed_review.get("canonical_labels_complete") is True
            and completed_review.get("repeat_review_complete") is True, "finish grading and scheduled repeat review first")
    schedule = review_schedule(completed_review["eligible_sources"],
                               datetime.fromisoformat(completed_review["tag_sealed_at"]))
    require(datetime.fromisoformat(completed_review["grade_started_at"]) >= datetime.fromisoformat(schedule["grade_not_before"]),
            "grading started before the 24-hour separation")
    require(set(completed_review["repeat_completed_sources"]) == set(schedule["repeat_sources"]), "scheduled repeat sources incomplete")
    require(now.tzinfo is not None, "prediction lock needs timezone")
    require(now >= datetime.fromisoformat(completed_review["repeat_completed_at"])
            >= datetime.fromisoformat(completed_review["repeat_started_at"])
            >= datetime.fromisoformat(completed_review["first_grade_sealed_at"])
            >= datetime.fromisoformat(completed_review["grade_started_at"]), "review/lock timestamps out of order")
    require(set(prediction_files) == METHODS and all(prediction_files.values()), "all fixed methods must be locked together")
    return {"freeze_id": FREEZE_ID, "inputs": input_seal, "labels": label_seal,
            "predictions": prediction_files, "locked_at": now.isoformat(), "labels_released": False}


def release_allowed(receipt, current_inputs, current_labels, current_predictions):
    require(receipt["freeze_id"] == FREEZE_ID and receipt["locked_at"] and receipt["labels_released"] is False,
            "valid unreleased prediction lock required")
    require(receipt["inputs"] == current_inputs and receipt["labels"] == current_labels
            and receipt["predictions"] == current_predictions, "sealed artifacts changed; do not release labels")
    require(set(current_predictions) == METHODS, "incomplete prediction lock")
    return True


def guard_ranking_files(private_root):
    """Install inside a future ranking child after imports; no native/OS claim."""
    private_root = private_root.resolve()
    allowed = private_root / "inputs"
    def audit(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0]).resolve()
            if path.is_relative_to(private_root) and not path.is_relative_to(allowed):
                raise PermissionError("Ranking worker cannot open custodian/intake files")
    sys.addaudithook(audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--config", type=Path, default=Path("configs/001e-a1-a-v1.json"))
    init.add_argument("--bindings", type=Path, required=True)
    init.add_argument("--freeze-commit", required=True)
    for name in ("lock-queue", "status"):
        commands.add_parser(name)
    entry = commands.add_parser("screen")
    entry.add_argument("--source-id", required=True)
    entry.add_argument("--decision", choices=("include", "exclude"), required=True)
    entry.add_argument("--reason", default="")
    entry.add_argument("--components", nargs="*", default=[])
    entry.add_argument("--occlusion", default="")
    entry.add_argument("--related-sources-checked", action="store_true")
    for sub in commands.choices.values():
        sub.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.root, args.config, args.bindings, args.freeze_commit)
        print(json.dumps({"initialized": str(args.root), "freeze_id": FREEZE_ID, "predictions": "none"}))
    elif args.command == "lock-queue":
        lock_queue(args.root)
        print("Ordered source queue locked; no rankings or labels read.")
    elif args.command == "screen":
        print(json.dumps(screen(args.root, args.source_id, args.decision, args.reason, args.components,
                                args.related_sources_checked, args.occlusion), indent=2))
    else:
        root, config, _ = load_store(args.root)
        rows = records(root)
        print(json.dumps({"freeze_id": FREEZE_ID, "screened": len(rows),
            "eligible": sum(r["decision"] == "include" for r in rows),
            "cutoff_exclusive": config["collection_window"]["cutoff_exclusive"],
            "stop": cap_reason(config, rows, now_local()), "predictions": "not generated by intake"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
