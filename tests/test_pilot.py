"""Generated colored images and authored labels are engineering fixtures only."""

from copy import deepcopy
import csv
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image as PILImage, ImageCms, ImageOps, PngImagePlugin
from pydantic import ValidationError
import pytest

from stylematch.contracts import Dataset, Image
from stylematch.labeling import export_template, import_labels
from stylematch.preparation import (
    PilotPlan, contained, load_pilot, new_json, prepare, private_path, sanitized_pixels,
    summary, verify_prepared_images,
)
from stylematch.validation import validate_dataset


@pytest.fixture
def pilot_input(tmp_path):
    originals = tmp_path / "synthetic-originals"
    originals.mkdir()
    sources, garments = [], []
    for index, (name, kind, category) in enumerate((
        ("top-a", "garment", "tops"), ("top-b", "garment", "tops"),
        ("jeans", "garment", "bottoms"), ("inspiration", "inspiration", None),
        ("excluded", "inspiration", None),
    )):
        pixels = PILImage.new("RGB", (8, 6), (30 + index * 20, 80, 110))
        pixels.putpixel((0, 0), (255, 0, 0))
        exif = PILImage.Exif()
        exif[274] = 6
        exif[270] = "synthetic identifying metadata; strip me"
        pixels.save(originals / f"{name}.jpg", exif=exif)
        sources.append({
            "image_id": name, "path": f"{name}.jpg", "kind": kind,
            "provenance": "generated colored engineering image, not a real garment photo",
            "permission_basis": "synthetic-authored", "permission_reference": "test author",
            "source_group": name, "capture_group": name,
        })
        if category:
            garments.append({"ref": {"wardrobe_id": "wardrobe-01", "item_id": name},
                             "category": category, "image_ids": [name]})
    queries = [{"query_id": f"q-{category}", "active_wardrobe_id": "wardrobe-01",
                "image_id": "inspiration", "component_category": category,
                "partition": "development", "crop_image_id": "human-crop" if category == "tops" else None}
               for category in ("tops", "bottoms", "outerwear")]
    plan = {
        "schema_version": 1, "dataset_id": "synthetic-pilot", "synthetic": True,
        "wardrobe": {"wardrobe_id": "wardrobe-01", "person_id": "synthetic-owner", "partition": "development"},
        "reviewer_id": "synthetic-reviewer", "handling": {"approved": False},
        "sources": sources, "garments": garments, "queries": queries,
        "crops": [{"image_id": "human-crop", "parent_image_id": "inspiration", "box": [1, 1, 5, 7]}],
        "exclusions": [{"image_id": "excluded", "component_category": "tops", "reason": "synthetic occlusion example"}],
    }
    return plan, originals, tmp_path / "pilot"


@pytest.fixture
def ready_pilot(pilot_input):
    plan, originals, output = pilot_input
    prepare(PilotPlan.model_validate(plan), originals, output)
    return output


def edit_sheet(path, change):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    change(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def completed_review(ready_pilot):
    labels = ready_pilot / "review-01"
    export_template(ready_pilot, labels, 42)

    def grades(rows):
        for row in rows:
            row["grade"] = {"top-a": "3", "top-b": "2", "jeans": "1"}[row["item_id"]]
            row["uncertain"] = "false"
            row["notes"] = "Synthetic authored engineering label; not a real review."

    def decisions(rows):
        for row in rows:
            row["no_match"] = "false" if row["query_id"] == "q-tops" else "true"
            row["uncertain"] = "false"

    edit_sheet(labels / "labels.csv", grades)
    edit_sheet(labels / "queries.csv", decisions)
    return ready_pilot, labels


def test_orientation_metadata_pixels_and_original_bytes(pilot_input):
    plan, originals, output = pilot_input
    before = {path.name: path.read_bytes() for path in originals.iterdir()}
    dataset = prepare(PilotPlan.model_validate(plan), originals, output)
    assert before == {path.name: path.read_bytes() for path in originals.iterdir()}
    for image in dataset.images:
        with PILImage.open(output / image.path) as prepared:
            assert not prepared.info and not prepared.getexif()
            assert prepared.size == (image.width_px, image.height_px)
            if image.kind != "crop":
                assert prepared.size == (6, 8)
                with PILImage.open(originals / f"{image.image_id}.jpg") as original:
                    expected = ImageOps.exif_transpose(original).convert("RGB")
                    assert expected.tobytes() == prepared.tobytes()
    record = json.loads((output / "preparation.json").read_text())
    assert record["originals"][0]["exif_orientation"] == 6
    assert record["originals"][0]["sha256"] == sha256(before["top-a.jpg"]).hexdigest()
    assert not any(str(originals) in str(value) for value in record.values())


def test_png_metadata_alpha_and_tagged_color_removed():
    image = PILImage.new("RGBA", (3, 2), (100, 20, 30, 0))
    info = PngImagePlugin.PngInfo()
    info.add_text("Comment", "synthetic private metadata")
    buffer = BytesIO()
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    image.save(buffer, format="PNG", pnginfo=info, icc_profile=profile)
    pixels, _ = sanitized_pixels(buffer.getvalue())
    assert pixels.mode == "RGB" and not pixels.info
    assert pixels.getpixel((0, 0)) == (255, 255, 255)


def test_exif_rotation_against_hand_computed_pixel_positions():
    image = PILImage.new("RGB", (2, 3))
    colors = [(10, 0, 0), (20, 0, 0), (30, 0, 0), (40, 0, 0), (50, 0, 0), (60, 0, 0)]
    for position, color in enumerate(colors): image.putpixel((position % 2, position // 2), color)
    exif = PILImage.Exif()
    exif[274] = 6
    buffer = BytesIO()
    image.save(buffer, format="PNG", exif=exif)
    pixels, _ = sanitized_pixels(buffer.getvalue())
    assert pixels.size == (3, 2)
    assert [pixels.getpixel((x, y)) for y in range(2) for x in range(3)] == [
        colors[4], colors[2], colors[0], colors[5], colors[3], colors[1],
    ]


@pytest.mark.parametrize("case", ["corrupt", "gif", "animated-png", "bad-profile", "untagged-cmyk", "heic"])
def test_unsupported_and_corrupt_inputs(case):
    buffer = BytesIO()
    image = PILImage.new("RGB", (4, 5), "red")
    if case == "corrupt": content = b"not an image"
    elif case == "heic": content = b"\x00\x00\x00\x18ftypheic"
    elif case == "gif":
        image.save(buffer, format="GIF")
        content = buffer.getvalue()
    elif case == "animated-png":
        image.save(buffer, format="PNG", save_all=True, append_images=[PILImage.new("RGB", (4, 5), "blue")])
        content = buffer.getvalue()
    elif case == "bad-profile":
        image.save(buffer, format="PNG", icc_profile=b"invalid synthetic profile")
        content = buffer.getvalue()
    else:
        image.convert("CMYK").save(buffer, format="JPEG")
        content = buffer.getvalue()
    with pytest.raises(ValueError, match="unsupported|multiframe|profile"):
        sanitized_pixels(content)


def test_decompression_safety(monkeypatch):
    buffer = BytesIO()
    PILImage.new("RGB", (10, 10)).save(buffer, format="PNG")
    monkeypatch.setattr(PILImage, "MAX_IMAGE_PIXELS", 60)
    with pytest.raises(ValueError, match="unsupported"):
        sanitized_pixels(buffer.getvalue())


def test_crop_pixels_coordinates_and_inherited_provenance(ready_pilot):
    dataset, _ = load_pilot(ready_pilot)
    crop = next(i for i in dataset.images if i.kind == "crop")
    parent = next(i for i in dataset.images if i.image_id == crop.parent_image_id)
    assert crop.crop_box == [1, 1, 5, 7]
    assert (crop.width_px, crop.height_px) == (4, 6)
    assert crop.capture_group == parent.capture_group
    assert crop.source_group == parent.source_group
    assert crop.permission_reference == parent.permission_reference
    with PILImage.open(ready_pilot / parent.path) as image, PILImage.open(ready_pilot / crop.path) as cropped:
        assert image.crop(tuple(crop.crop_box)).tobytes() == cropped.tobytes()


@pytest.mark.parametrize("box", [[0, 0, 7, 8], [0, 0, 6, 9], [2, 2, 2, 4], [5, 1, 3, 2]])
def test_crop_bounds_and_no_false_ready_manifest(pilot_input, box):
    plan, originals, output = pilot_input
    plan["crops"][0]["box"] = box
    with pytest.raises(ValueError, match="crop bounds"):
        prepare(PilotPlan.model_validate(plan), originals, output)
    assert not (output / "dataset.json").exists()


def test_real_approval_required_before_any_source_read(pilot_input):
    plan, _, output = pilot_input
    plan["synthetic"] = False
    for source in plan["sources"]: source["permission_basis"] = "owner-created"
    with pytest.raises(ValueError, match="approval is pending"):
        prepare(PilotPlan.model_validate(plan), Path("nonexistent-not-inspected"), output)
    plan["handling"] = {"approved": True, "decision_reference": "synthetic test of approval only"}
    with pytest.raises(ValueError, match="outside the Git"):
        prepare(PilotPlan.model_validate(plan), output.parent, output)


@pytest.mark.parametrize("case,match", [
    ("partition", "development"), ("multiple-wardrobes", "one actual wardrobe"),
    ("query-wardrobe", "single pilot wardrobe"), ("permission", "permission"),
    ("unused", "exclusion"), ("crop-registration", "human-selected"),
    ("path-traversal", "relative"), ("approval-reference", "decision reference"),
])
def test_plan_guards(pilot_input, case, match):
    plan, originals, output = pilot_input
    if case == "partition": plan["queries"][0]["partition"] = "test"
    elif case == "multiple-wardrobes": plan["garments"][0]["ref"]["wardrobe_id"] = "subset-02"
    elif case == "query-wardrobe": plan["queries"][0]["active_wardrobe_id"] = "other"
    elif case == "permission": plan["sources"][0]["permission_reference"] = "   "
    elif case == "unused": plan["exclusions"] = []
    elif case == "crop-registration": plan["queries"][0]["crop_image_id"] = None
    elif case == "path-traversal": plan["sources"][0]["path"] = "../top-a.jpg"
    elif case == "approval-reference": plan["handling"] = {"approved": True}
    with pytest.raises(ValueError, match=match):
        prepare(PilotPlan.model_validate(plan), originals, output)


def test_no_accidental_overwrite_or_source_output_overlap(pilot_input):
    plan, originals, output = pilot_input
    plan = PilotPlan.model_validate(plan)
    with pytest.raises(ValueError, match="separate"):
        prepare(plan, originals, originals / "prepared")
    prepare(plan, originals, output)
    original_manifest = (output / "dataset.json").read_bytes()
    with pytest.raises(FileExistsError): prepare(plan, originals, output)
    assert original_manifest == (output / "dataset.json").read_bytes()


def test_private_paths_and_all_outputs_remain_ignored(ready_pilot):
    export_template(ready_pilot, ready_pilot / "review", 42)
    for path in ready_pilot.rglob("*"):
        if path.is_file(): assert private_path(path) == path.resolve()
    with pytest.raises(ValueError, match="not ignored"):
        private_path(Path("README.md"))
    with pytest.raises(ValueError, match="inside an ignored"):
        private_path(Path("C:/outside-repository/private.json"))


def test_reproducible_templates_and_seed(ready_pilot):
    first, second = ready_pilot / "review-a", ready_pilot / "review-b"
    a = export_template(ready_pilot, first, 1024)
    b = export_template(ready_pilot, second, 1024)
    assert a == b and a["candidate_rows"] == 3 and a["query_rows"] == 3
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}
    assert "unknown" in (first / "labels.csv").read_text()
    assert "model" not in (first / "labels.csv").read_text()
    with pytest.raises(FileExistsError): export_template(ready_pilot, first, 1024)


def test_exhaustive_round_trip_multiple_matches_nomatch_missing_category(completed_review):
    root, labels = completed_review
    edit_sheet(labels / "effort.csv", lambda rows: rows[0].update(status="measured", seconds="123.5", notes="synthetic time"))
    dataset = import_labels(root, labels, "labeled-01.json")
    assert validate_dataset(dataset)["labels_complete"]
    loaded, _ = load_pilot(root, "labeled-01.json", require_labels=True)
    assert loaded == dataset
    assert len(dataset.judgments[0].grades) == 2
    assert all(g.relevance >= 2 for g in dataset.judgments[0].grades)
    assert dataset.judgments[1].no_match and dataset.judgments[2].no_match
    assert dataset.judgments[2].grades == []
    audit = json.loads((root / "labeled-01.label-audit.json").read_text())
    assert audit["human_effort"][0]["seconds"] == 123.5
    assert audit["human_effort"][1]["seconds"] is None
    assert audit["independent_reviewers"] is False
    assert all(a["color"] == "unknown" for a in audit["attributes"])
    assert summary(dataset, [])["missing_category_tasks"] == 1
    with pytest.raises(ValueError, match="overwrite"):
        import_labels(root, labels, "labeled-01.json")


@pytest.mark.parametrize("case,match", [
    ("blank", "grade unresolved"), ("unknown", "grade unresolved"), ("invalid", "grade unresolved"),
    ("uncertain", "uncertain candidate"), ("unknown-uncertainty", "unresolved/invalid"),
    ("missing-row", "missing/extra rows"), ("duplicate-row", "missing/extra rows"),
    ("membership", "membership"), ("reviewer", "identity"),
    ("contradiction", "contradictory"), ("missing-no-match", "unresolved/invalid"),
    ("query-uncertain", "uncertain judgment"), ("attribute-blank", "explicit unknown"),
    ("negative-effort", "nonnegative"), ("missing-effort", "numeric seconds"),
    ("unknown-time-with-value", "unknown effort"), ("nan-effort", "finite"),
    ("query-context", "context changed"), ("reordered", "order"),
])
def test_label_import_rejects_invalid_reviews(completed_review, case, match):
    root, labels = completed_review
    name = "labels.csv"

    def change(rows):
        if case == "blank": rows[0]["grade"] = ""
        elif case == "unknown": rows[0]["grade"] = "unknown"
        elif case == "invalid": rows[0]["grade"] = "4"
        elif case == "uncertain": rows[0]["uncertain"] = "true"
        elif case == "unknown-uncertainty": rows[0]["uncertain"] = "unknown"
        elif case == "missing-row": rows.pop()
        elif case == "duplicate-row": rows.append(deepcopy(rows[0]))
        elif case == "membership": rows[0]["wardrobe_id"] = "other"
        elif case == "reviewer": rows[0]["reviewer_id"] = "another-human"
        elif case == "contradiction": rows[0]["no_match"] = "true"
        elif case == "missing-no-match": rows[0]["no_match"] = ""
        elif case == "query-uncertain": rows[0]["uncertain"] = "true"
        elif case == "attribute-blank": rows[0]["color"] = ""
        elif case == "negative-effort": rows[0].update(status="measured", seconds="-1")
        elif case == "missing-effort": rows[0].update(status="measured", seconds="")
        elif case == "unknown-time-with-value": rows[0]["seconds"] = "12"
        elif case == "nan-effort": rows[0].update(status="measured", seconds="nan")
        elif case == "query-context": rows[0]["query_image"] = "prepared/wrong.png"
        elif case == "reordered": rows.reverse()

    if case in ("contradiction", "missing-no-match", "query-uncertain", "query-context"): name = "queries.csv"
    if case == "attribute-blank": name = "attributes.csv"
    if "effort" in case or case == "unknown-time-with-value": name = "effort.csv"
    edit_sheet(labels / name, change)
    with pytest.raises(ValueError, match=match):
        import_labels(root, labels, "must-not-exist.json")
    assert not (root / "must-not-exist.json").exists()


def test_unedited_unknown_sheet_cannot_import(ready_pilot):
    labels = ready_pilot / "untouched"
    export_template(ready_pilot, labels, 1)
    with pytest.raises(ValueError, match="unresolved"):
        import_labels(ready_pilot, labels, "unresolved.json")


@pytest.mark.parametrize("case,match", [
    ("image-bytes", "hash mismatch"), ("dimensions", "dimensions mismatch"),
    ("capture-group", "retain capture group"), ("binding", "binding mismatch"),
    ("crop-dimensions", "crop dimensions"),
])
def test_preparation_integrity(ready_pilot, case, match):
    path = ready_pilot / "dataset.json"
    value = json.loads(path.read_text())
    if case == "image-bytes": (ready_pilot / value["images"][0]["path"]).write_bytes(b"changed")
    elif case == "dimensions": value["images"][0]["width_px"] += 1
    elif case == "capture-group": value["images"][-1]["capture_group"] = "wrong"
    elif case == "binding": value["dataset_id"] = "different"
    elif case == "crop-dimensions": value["images"][-1]["width_px"] += 1
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match=match): load_pilot(ready_pilot)


def test_legacy_evaluator_still_requires_human_labels(ready_pilot):
    dataset = Dataset.model_validate_json((ready_pilot / "dataset.json").read_bytes())
    assert not validate_dataset(dataset, require_judgments=False)["labels_complete"]
    with pytest.raises(ValueError, match="incomplete"):
        validate_dataset(dataset)


def test_cli_prepare_review_import_check_and_no_overwrite(pilot_input):
    plan, originals, root = pilot_input
    plan_path = originals.parent / "plan.json"
    new_json(plan_path, plan)
    base = [sys.executable, "-m", "stylematch.pilot"]

    def command(*args, expected=0):
        result = subprocess.run(base + list(map(str, args)), capture_output=True, text=True)
        assert result.returncode == expected, result.stderr
        return result

    result = command("prepare", "--plan", plan_path, "--originals", originals, "--output", root)
    assert json.loads(result.stdout)["status"] == "human labels pending"
    command("check", "--pilot", root, expected=2)
    command("check", "--pilot", root, "--allow-unlabeled")
    command("label-template", "--pilot", root, "--output", root / "review", "--seed", 42)
    command("import-labels", "--pilot", root, "--labels", root / "review", "--output", "pending.json", expected=2)
    init_path = originals.parent / "empty-plan.json"
    command("init", "--output", init_path)
    initialized = PilotPlan.model_validate_json(init_path.read_bytes())
    assert initialized.handling.approved is False and not initialized.sources
    command("init", "--output", init_path, expected=2)


def test_cli_successful_label_import_and_check(completed_review):
    root, labels = completed_review
    base = [sys.executable, "-m", "stylematch.pilot"]
    imported = subprocess.run(base + ["import-labels", "--pilot", str(root), "--labels", str(labels),
                                      "--output", "cli-labeled.json"], capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr
    checked = subprocess.run(base + ["check", "--pilot", str(root), "--dataset", "cli-labeled.json"],
                             capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    result = json.loads(checked.stdout)
    assert result["synthetic"] is True and result["component_tasks"] == 3
    assert result["no_match_tasks"] == 2 and result["reviewers"] == ["synthetic-reviewer"]
    assert len(result["human_effort"]) == 3
    assert all(row["seconds"] is None for row in result["human_effort"])


def test_csv_header_and_template_binding_guards(completed_review):
    root, labels = completed_review
    metadata_path = labels / "template.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["dataset_sha256"] = "0" * 64
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="binding mismatch"):
        import_labels(root, labels, "never.json")


def test_explicitly_excluded_unsupported_source_is_registered_not_prepared(pilot_input):
    plan, originals, root = pilot_input
    plan["exclusions"][0]["component_category"] = "unsupported-footwear"
    (originals / "excluded.jpg").write_bytes(b"synthetic unsupported source excluded explicitly")
    dataset = prepare(PilotPlan.model_validate(plan), originals, root)
    assert "excluded" not in {i.image_id for i in dataset.images}
    audit = json.loads((root / "preparation.json").read_text())
    excluded = next(r for r in audit["originals"] if r["image_id"] == "excluded")
    assert excluded["prepared"] is False
    assert excluded["sha256"] == sha256((originals / "excluded.jpg").read_bytes()).hexdigest()
    assert audit["plan"]["exclusions"][0]["reason"]


def test_labeled_manifest_and_audit_are_bound(completed_review):
    root, labels = completed_review
    import_labels(root, labels, "labeled.json")
    path = root / "labeled.json"
    value = json.loads(path.read_text())
    value["judgments"][0]["notes"] = "changed after import"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="labeled manifest binding mismatch"):
        load_pilot(root, "labeled.json", require_labels=True)


def test_changed_csv_columns_and_preserved_instructions(completed_review):
    root, labels = completed_review
    sheet = labels / "labels.csv"
    original = sheet.read_bytes()
    sheet.write_bytes(original.replace(b"grade,uncertain", b"grade,grade", 1))
    with pytest.raises(ValueError, match="columns changed"):
        import_labels(root, labels, "never.json")
    sheet.write_bytes(original)
    (labels / "INSTRUCTIONS.txt").write_text("discarded", encoding="utf-8")
    with pytest.raises(ValueError, match="instructions must be preserved"):
        import_labels(root, labels, "never.json")


def test_relative_containment_and_image_dimension_contract(tmp_path):
    with pytest.raises(ValueError, match="relative"):
        contained(tmp_path, "../outside.txt", exists=False)
    payload = {"image_id": "x", "path": "prepared/x.png", "sha256": "0" * 64, "kind": "garment",
               "partition": "development", "provenance": "synthetic", "permission_reference": "synthetic",
               "permitted_use": "synthetic-engineering", "capture_group": "x", "source_group": "x", "width_px": 5}
    with pytest.raises(ValidationError, match="together"):
        Image.model_validate(payload)
