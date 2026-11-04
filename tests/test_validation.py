from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from stylematch.contracts import Dataset, Run
from stylematch.validation import validate_dataset, validate_run, verify_image_files

ROOT = Path(__file__).parent / "fixtures" / "synthetic"


def test_valid_fixture_files_and_actual_person_overlap(dataset):
    inventory = validate_dataset(dataset)
    assert inventory["person_partition_overlap"] == ["synthetic-person"]
    assert inventory["queries"] == 6
    assert inventory["garments"] == 6
    assert inventory["images"] == 9
    verify_image_files(dataset, ROOT)


@pytest.mark.parametrize("field", ["sha256", "capture_group", "source_group"])
def test_split_group_leakage(data, field):
    data["images"][4][field] = data["images"][0][field]
    with pytest.raises(ValueError, match="leakage"):
        validate_dataset(Dataset.model_validate(data))


@pytest.mark.parametrize("path", ["/private/a.jpg", "C:/photos/a.jpg", "../a.jpg", "a/../b.jpg", "a\\b.jpg", "a//b", "./a", "a/"])
def test_unsafe_paths_rejected(data, path):
    data["images"][0]["path"] = path
    with pytest.raises(ValidationError, match="relative"):
        Dataset.model_validate(data)


@pytest.mark.parametrize("case,match", [
    ("missing-grade", "incomplete judgments"), ("missing-judgment", "query judgments"),
    ("duplicate-grade", "duplicate judgment"), ("no-match-with-relevant", "contradictory"),
    ("matchable-without-relevant", "contradictory"), ("uncertain", "uncertain"),
    ("cross-wardrobe-label", "invalid wardrobe"), ("category-label", "invalid wardrobe"),
    ("unknown-image", "item image"), ("unknown-wardrobe", "garment wardrobe"),
    ("query-split", "wardrobe partition"), ("crop-parent", "parent mismatch"),
    ("duplicate-item", "duplicate compound"), ("duplicate-query", "duplicate query"),
    ("duplicate-image", "duplicate image IDs"), ("duplicate-wardrobe", "duplicate wardrobe"),
    ("unknown-query-image", "query image"), ("unknown-active-wardrobe", "active wardrobe"),
    ("unknown-crop", "crop reference"), ("item-split", "image partition"),
    ("crop-group", "retain source group"), ("duplicate-judgment", "duplicate canonical"),
    ("provenance", "provenance use mismatch"),
])
def test_semantic_contract_rejections(data, case, match):
    if case == "missing-grade": data["judgments"][0]["grades"].pop()
    elif case == "missing-judgment": data["judgments"].pop()
    elif case == "duplicate-grade": data["judgments"][0]["grades"].append(deepcopy(data["judgments"][0]["grades"][0]))
    elif case == "no-match-with-relevant": data["judgments"][0]["no_match"] = True
    elif case == "matchable-without-relevant": data["judgments"][1]["no_match"] = False
    elif case == "uncertain": data["judgments"][0]["uncertain"] = True
    elif case == "cross-wardrobe-label": data["judgments"][0]["grades"][0]["ref"]["wardrobe_id"] = "test"
    elif case == "category-label": data["judgments"][0]["grades"][0]["ref"]["item_id"] = "jeans"
    elif case == "unknown-image": data["garments"][0]["image_ids"] = ["missing"]
    elif case == "unknown-wardrobe": data["garments"][0]["ref"]["wardrobe_id"] = "missing"
    elif case == "query-split": data["queries"][0]["partition"] = "test"
    elif case == "crop-parent": data["queries"][2]["crop_image_id"] = "dev-crop"
    elif case == "duplicate-item": data["garments"].append(deepcopy(data["garments"][0]))
    elif case == "duplicate-query": data["queries"].append(deepcopy(data["queries"][0]))
    elif case == "duplicate-image": data["images"].append(deepcopy(data["images"][0]))
    elif case == "duplicate-wardrobe": data["wardrobes"].append(deepcopy(data["wardrobes"][0]))
    elif case == "unknown-query-image": data["queries"][0]["image_id"] = "missing"
    elif case == "unknown-active-wardrobe": data["queries"][0]["active_wardrobe_id"] = "missing"
    elif case == "unknown-crop": data["queries"][0]["crop_image_id"] = "missing"
    elif case == "item-split": data["garments"][0]["image_ids"] = ["test-top-a"]
    elif case == "crop-group": data["images"][-1]["source_group"] = "other"
    elif case == "duplicate-judgment": data["judgments"].append(deepcopy(data["judgments"][0]))
    elif case == "provenance": data["images"][0]["permitted_use"] = "feasibility-evaluation"
    with pytest.raises(ValueError, match=match):
        validate_dataset(Dataset.model_validate(data))


@pytest.mark.parametrize("grade", [-1, 4, True, "2", 2.0])
def test_grade_range_and_type(data, grade):
    data["judgments"][0]["grades"][0]["relevance"] = grade
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


@pytest.mark.parametrize("case,match", [
    ("missing-ranking", "explicitly rank"), ("duplicate-ranking", "duplicate ranking"),
    ("unknown-ranking", "unknown ranking"), ("dataset-id", "dataset ID"),
])
def test_run_reference_integrity(dataset, run_data, case, match):
    if case == "missing-ranking": run_data["rankings"].pop()
    elif case == "duplicate-ranking": run_data["rankings"].append(deepcopy(run_data["rankings"][0]))
    elif case == "unknown-ranking": run_data["rankings"][0]["query_id"] = "unknown"
    elif case == "dataset-id": run_data["dataset_id"] = "other"
    with pytest.raises(ValueError, match=match):
        validate_run(dataset, Run.model_validate(run_data))


def test_dataset_hash_binding(dataset, run):
    validate_run(dataset, run, sha256((ROOT / "dataset.json").read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="dataset hash"):
        validate_run(dataset, run, "0" * 64)


def test_hash_verification_detects_changed_files(dataset, tmp_path):
    for image in dataset.images:
        path = tmp_path / image.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_image_files(dataset, tmp_path)


@pytest.mark.parametrize("case", ["unexplained", "negative", "nan", "failed-without-reason", "complete-with-failure", "test-tuned", "unknown-field", "version"])
def test_run_schema_guards(run_data, case):
    if case == "unexplained": run_data["resources"]["missing_reasons"] = {}
    elif case == "negative": run_data["resources"]["peak_ram_bytes"] = -1
    elif case == "nan": run_data["threshold"] = float("nan")
    elif case == "failed-without-reason": run_data["status"] = "failed"
    elif case == "complete-with-failure": run_data["failures"] = ["error"]
    elif case == "test-tuned": run_data["threshold_selection_partition"] = "test"
    elif case == "unknown-field": run_data["unexpected"] = "value"
    elif case == "version": run_data["schema_version"] = 2
    with pytest.raises(ValidationError):
        Run.model_validate(run_data)


def test_documented_cli_and_failure_exit(tmp_path):
    import json

    command = [sys.executable, "-m", "stylematch", str(ROOT / "dataset.json"), str(ROOT / "run.json"), "--image-root", str(ROOT)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["synthetic"] is True
    failure = subprocess.run(command + ["--k", "0"], capture_output=True, text=True)
    assert failure.returncode == 2
    assert "positive integers" in failure.stderr
    run_data = json.loads((ROOT / "run.json").read_text(encoding="utf-8"))
    run_data.update(status="failed", failures=["fixture simulated failure"], rankings=[])
    failed_run = tmp_path / "failed.json"
    failed_run.write_text(json.dumps(run_data), encoding="utf-8")
    command[4] = str(failed_run)
    failure = subprocess.run(command, capture_output=True, text=True)
    assert failure.returncode == 2
    assert json.loads(failure.stdout)["validated"] is None
