"""Synthetic private intake/cap/seal checks; never uses actual held-out images."""
from copy import deepcopy
import csv
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from stylematch import intake
from stylematch.comparison import FIELDS


@pytest.fixture
def store(tmp_path, monkeypatch):
    repo = tmp_path / "repository"
    repo.mkdir()
    monkeypatch.setattr(intake, "REPOSITORY", repo)
    (repo / "dummy.py").write_bytes(b"# synthetic code\n")
    public = {"dummy.py": sha256((repo / "dummy.py").read_bytes()).hexdigest()}
    config = json.loads(Path("configs/001e-a1-a-v1.json").read_bytes())
    config["public_bindings"] = public
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    image_path = repo / "pilot/prepared/g.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (4, 4), (1, 2, 3)).save(image_path)
    tags = repo / "tags.json"
    tags.write_bytes(b'{"synthetic":true}\n')
    pixels = Image.open(image_path).convert("RGB")
    bindings = {"freeze_id": intake.FREEZE_ID, "public_bindings": public, "pilot_root": "pilot",
        "garment_images": [{"path": "prepared/g.png", "sha256": intake.digest(image_path)}],
        "canonical_tags_path": "tags.json", "canonical_tags_sha256": intake.digest(tags),
        "development_overlap": [{"sha256": intake.digest(image_path), "pixel_sha256": sha256(b"4x4:" + pixels.tobytes()).hexdigest(),
                                  "source_group": "development-look", "capture_group": "development-capture"}]}
    binding_path = tmp_path / "bindings.json"
    binding_path.write_text(json.dumps(bindings))
    root = tmp_path / "outside" / intake.FREEZE_ID
    intake.initialize(root, config_file, binding_path, "a" * 40)
    return root


def queue(root, n):
    with (root / "source-queue.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, intake.QUEUE_COLUMNS)
        writer.writeheader()
        for i in range(1, n + 1):
            writer.writerow({"position": i, "source_id": f"look-{i:03d}", "source_group": f"fresh-{i}",
                "original_file": f"look-{i:03d}.png", "source_reference": f"synthetic generated look {i}",
                "permission_basis": "owner-created", "permission_reference": "test author generated pixels"})
            Image.new("RGB", (4, 4), (100 + i, 30, 60)).save(root / f"originals/look-{i:03d}.png")
    intake.lock_queue(root, datetime(2026, 11, 17, 12, tzinfo=intake.LOCAL))


WHEN = datetime(2026, 11, 17, 12, tzinfo=intake.LOCAL)


def test_frozen_choice_and_exact_approved_values():
    draft = json.loads(Path("configs/001e-heldout-draft.json").read_bytes())
    frozen = json.loads(Path("configs/001e-a1-a-v1.json").read_bytes())
    assert draft["status"] == "DRAFT" and draft["owner_approval"] is None
    assert frozen["status"] == "FROZEN" and frozen["selected_design"] == "A"
    assert frozen["label_custodian"] == frozen["canonical_reviewer"] == "Mark"
    assert frozen["owner_approval"]["decision_date"] == "2026-11-17"
    for key in draft.keys() - {"status", "owner_approval", "selected_design", "label_custodian", "canonical_reviewer", "options", "boundary"}:
        assert frozen[key] == draft[key], key
    assert frozen["options"] == {"A": draft["options"]["A"]}
    assert datetime.fromisoformat(frozen["collection_window"]["cutoff_exclusive"]) == WHEN.replace(hour=0) + timedelta(days=14)


def test_initialized_store_is_empty_label_free_and_refuses_overwrite(store):
    _, config, receipt = intake.load_store(store)
    assert receipt["heldout_label_seal"] is receipt["heldout_data_seal"] is None
    assert receipt["predictions_locked"] is False
    assert intake.records(store) == []
    assert not list((store / "originals").iterdir())
    assert not list((store / "custodian/predictions").iterdir())
    assert "crop and query_tag" in (store / "FIRST-LOOK.txt").read_text()
    header = (store / "annotation/effort.csv").read_text()
    assert "active_seconds" in header and "stage" in header and "missing_reason" in header
    with pytest.raises(FileExistsError):
        intake.write_json(store / "freeze-receipt.json", {})


def test_screening_preserves_order_and_exclusions(store):
    queue(store, 3)
    with pytest.raises(ValueError, match="next queued"):
        intake.screen(store, "look-002", "exclude", "synthetic exclusion", now=WHEN)
    first = intake.screen(store, "look-001", "exclude", "no supported target", now=WHEN)
    assert first["screened"] == 1 and first["eligible"] == 0
    with pytest.raises(ValueError, match="manual related"):
        intake.screen(store, "look-002", "include", components=["tops"], now=WHEN)
    second = intake.screen(store, "look-002", "include", components=["tops"], related_checked=True, now=WHEN)
    assert second["screened"] == 2 and second["eligible"] == 1
    assert len(intake.records(store)) == 2
    # Changing a previously logged record cannot quietly erase an exclusion.
    record = store / "screening/records/0002.json"
    payload = intake.read(record)
    payload["reason"] = "changed"
    record.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="log/record"):
        intake.records(store)


def test_queue_cannot_be_changed_after_lock(store):
    queue(store, 1)
    with (store / "source-queue.csv").open("a") as stream:
        stream.write("changed\n")
    with pytest.raises(ValueError, match="queue changed"):
        intake.screen(store, "look-001", "exclude", "reason", now=WHEN)


def test_duplicate_pixels_are_logged_as_exclusion(store):
    queue(store, 2)
    Image.new("RGB", (4, 4), (1, 2, 3)).save(store / "originals/look-001.png")
    result = intake.screen(store, "look-001", "include", components=["tops"], related_checked=True, now=WHEN)
    assert result["decision"] == "exclude" and "overlap" in result["reason"]
    assert result["screened"] == 1
    assert not (store / "annotation/looks/look-001.png").exists()


@pytest.mark.parametrize("cap", ["eligible", "screened", "time"])
def test_caps_ignore_outcome_mix_and_block_next_screen(store, cap):
    queue(store, 36)
    if cap == "time":
        with pytest.raises(ValueError, match="calendar cutoff"):
            intake.screen(store, "look-001", "exclude", "reason", now=datetime(2026, 12, 1, tzinfo=intake.LOCAL))
        return
    maximum = 24 if cap == "eligible" else 36
    for i in range(1, maximum + 1):
        result = intake.screen(store, f"look-{i:03d}", "include" if cap == "eligible" else "exclude",
                               "screened exclusion" if cap == "screened" else "", ["tops"], True, now=WHEN)
    assert result["stop"]
    with pytest.raises(ValueError, match="collection stopped"):
        intake.screen(store, f"look-{maximum+1:03d}", "exclude", "reason", now=WHEN)


def test_repeat_schedule_and_lock_before_release():
    sources = [f"source-{n:03d}" for n in range(24)]
    schedule = intake.review_schedule(sources, WHEN)
    assert len(schedule["repeat_sources"]) == 5
    assert datetime.fromisoformat(schedule["grade_not_before"]) == WHEN + timedelta(hours=24)
    review = {"canonical_labels_complete": True, "repeat_review_complete": True, "eligible_sources": sources,
              "tag_sealed_at": WHEN.isoformat(), "grade_started_at": (WHEN + timedelta(hours=24)).isoformat(),
              "first_grade_sealed_at": (WHEN + timedelta(hours=25)).isoformat(),
              "repeat_started_at": (WHEN + timedelta(hours=26)).isoformat(),
              "repeat_completed_at": (WHEN + timedelta(hours=27)).isoformat(),
              "repeat_completed_sources": schedule["repeat_sources"]}
    predictions = {method: {"predictions.json": "c" * 64} for method in intake.METHODS}
    with pytest.raises(ValueError, match="repeat review"):
        intake.lock_prediction_receipt({"inputs": "a"}, {"labels": "b"}, {**review, "repeat_review_complete": False}, predictions, WHEN)
    with pytest.raises(ValueError, match="24-hour"):
        intake.lock_prediction_receipt({"inputs": "a"}, {"labels": "b"}, {**review, "grade_started_at": WHEN.isoformat()}, predictions, WHEN)
    receipt = intake.lock_prediction_receipt({"inputs": "a"}, {"labels": "b"}, review, predictions, WHEN + timedelta(days=2))
    assert intake.release_allowed(receipt, {"inputs": "a"}, {"labels": "b"}, predictions)
    with pytest.raises(ValueError, match="artifacts changed"):
        intake.release_allowed(receipt, {"inputs": "a"}, {"labels": "changed"}, predictions)


def test_ranking_projection_excludes_labels_names_and_notes(dataset):
    attributes = {"wardrobe": {g.ref.key: {f: "unknown" for f in FIELDS} for g in dataset.garments},
                  "crop": {q.query_id: {f: "unknown" for f in FIELDS} for q in dataset.queries}}
    # Engineering fixture needs a crop on every task; no image is decoded here.
    payload = dataset.model_dump()
    for q in payload["queries"]:
        q["crop_image_id"] = "dev-crop"
    from stylematch.contracts import Dataset
    fixture = Dataset.model_validate(payload)
    before = intake.ranking_projection(fixture, attributes)
    for j in payload["judgments"]:
        j["notes"] = "untrusted revealing text"
        for g in j["grades"]:
            g["relevance"] = 0
    for image in payload["images"]:
        image["path"] = "revealing-file-name.png"
    assert intake.ranking_projection(Dataset.model_validate(payload), attributes) == before
    assert "revealing" not in json.dumps(before) and "no_match" not in json.dumps(before)


def test_future_ranking_guard_blocks_custodian_reads(store):
    (store / "inputs/safe.json").write_text("{}")
    (store / "custodian/labels/private.json").write_text("{}")
    script = """import sys
from pathlib import Path
from stylematch.intake import guard_ranking_files
r=Path(sys.argv[1]); guard_ranking_files(r)
assert (r/'inputs/safe.json').read_text()=='{}'
try:
    (r/'custodian/labels/private.json').read_text()
except PermissionError:
    print('blocked')
else:
    raise AssertionError('labels accessible')
"""
    result = subprocess.run([sys.executable, "-c", script, str(store)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "blocked"
