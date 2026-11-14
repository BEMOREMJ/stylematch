"""Synthetic retrieval/abstention checks; no model download or personal data."""
from copy import deepcopy
from itertools import permutations
import json
import subprocess
import sys

import pytest

from stylematch.benchmark import (apply_threshold, category_rankings, expected_category,
                                 garment_vectors, normalized, rank_vectors,
                                 retrieval_inputs, tune_shared_threshold)
from stylematch.contracts import Dataset
from stylematch.evaluation import dcg
from stylematch.validation import validate_dataset


@pytest.fixture
def retrieval_dataset():
    def image(name, kind, parent=None):
        return {"image_id": name, "path": f"synthetic/{name}.png", "sha256": "a" * 64,
                "kind": kind, "partition": "development", "provenance": "synthetic test only",
                "permission_reference": "authored synthetic fixture", "permitted_use": "synthetic-engineering",
                "capture_group": "synthetic-group", "source_group": "synthetic-group",
                "parent_image_id": parent, "width_px": 2 if parent else 4,
                "height_px": 2 if parent else 4, "crop_box": [0, 0, 2, 2] if parent else None}
    garments = [{"ref": {"wardrobe_id": "synthetic", "item_id": f"item-{i}"}, "category": "tops", "image_ids": [f"g-{i}"]} for i in range(6)]
    queries = [{"query_id": q, "active_wardrobe_id": "synthetic", "image_id": q,
                "component_category": "tops", "partition": "development", "crop_image_id": q + "-crop"} for q in ("matchable", "no-match")]
    judgments = [{"query_id": q, "reviewer_id": "synthetic-reviewer", "uncertain": False,
                  "no_match": q == "no-match", "notes": "synthetic", "grades": [
                      {"ref": g["ref"], "relevance": ([3, 2, 1, 0, 0, 0][i] if q == "matchable" else 1)} for i, g in enumerate(garments)]}
                 for q in ("matchable", "no-match")]
    dataset = Dataset.model_validate({"schema_version": 1, "dataset_id": "synthetic-benchmark", "synthetic": True,
        "wardrobes": [{"wardrobe_id": "synthetic", "person_id": "synthetic-person", "partition": "development"}],
        "garments": garments, "queries": queries, "judgments": judgments,
        "images": [image(f"g-{i}", "garment") for i in range(6)] + [image(q, "inspiration") for q in ("matchable", "no-match")]
                  + [image(q + "-crop", "crop", q) for q in ("matchable", "no-match")]})
    validate_dataset(dataset)
    return dataset


def test_chance_matches_exhaustive_permutations(retrieval_dataset):
    expected = expected_category(retrieval_dataset)
    row = expected["per_task"][0]
    assert (row["eligible"], row["acceptable"], row["expected_hit3"]) == (6, 2, 0.8)
    assert row["hit3_uninformative_small_pool"] is False
    orders = list(permutations([3, 2, 1, 0, 0, 0]))
    assert row["expected_hit3"] == pytest.approx(sum(any(g >= 2 for g in order[:3]) for order in orders) / len(orders))
    assert row["expected_recall3"] == pytest.approx(sum(sum(g >= 2 for g in order[:3]) / 2 for order in orders) / len(orders))
    assert row["expected_ndcg5"] == pytest.approx(sum(dcg(list(order[:5])) / dcg([3, 2, 1, 0, 0]) for order in orders) / len(orders))
    no_match = expected["per_task"][1]
    assert no_match["expected_hit3"] is no_match["expected_ndcg5"] is None
    assert no_match["acceptable_hit_probability"] == 0


def test_small_pool_hit_is_trivial(retrieval_dataset):
    payload = retrieval_dataset.model_dump()
    payload["garments"] = payload["garments"][:3]
    for judgment in payload["judgments"]:
        judgment["grades"] = judgment["grades"][:3]
    dataset = Dataset.model_validate(payload)
    validate_dataset(dataset)
    row = expected_category(dataset)["per_task"][0]
    assert row["hit3_uninformative_small_pool"] is True
    assert row["expected_hit3"] == row["expected_recall3"] == 1


def test_grades_notes_and_names_do_not_rank(retrieval_dataset):
    inputs = retrieval_inputs(retrieval_dataset)
    payload = retrieval_dataset.model_dump()
    payload["judgments"][0]["grades"][0]["relevance"] = 0
    payload["judgments"][0]["notes"] = "private irrelevant note"
    assert retrieval_inputs(Dataset.model_validate(payload)) == inputs
    features = {key: [1.0, 0.0] for key in inputs["images"]}
    features["g-0"] = [0.0, 1.0]
    features["matchable-crop"] = [0.0, 1.0]
    before = rank_vectors(inputs, features, "full")
    changed = deepcopy(inputs)
    for image in changed["images"].values():
        image["path"] = "arbitrary-path-ignored-by-ranking.png"
    assert rank_vectors(changed, features, "full") == before
    assert rank_vectors(inputs, features, "crop")[0]["predictions"][0]["ref"]["item_id"] == "item-0"
    assert before[0]["predictions"][0]["ref"]["item_id"] == "item-1"
    category = category_rankings(inputs, 104729)
    assert category == category_rankings(inputs, 104729)
    assert all(len(row["predictions"]) == 6 for row in category)


def test_multi_image_normalization_and_bad_vectors(retrieval_dataset):
    inputs = retrieval_inputs(retrieval_dataset)
    inputs["garments"][0]["image_ids"] = ["g-0", "g-1"]
    features = {key: [3.0, 0.0] for key in inputs["images"]}
    features["g-1"] = [0.0, 5.0]
    assert garment_vectors(inputs, features)[("synthetic", "item-0")] == pytest.approx([2**-0.5, 2**-0.5])
    for bad in ([0.0, 0.0], [float("nan"), 1], []):
        with pytest.raises(ValueError):
            normalized(bad)


def test_threshold_inclusive_and_shared_tie_break(retrieval_dataset):
    def rows(matchable, no_match):
        return [{"query_id": key, "predictions": [{"ref": {"wardrobe_id": "synthetic", "item_id": "item-0"}, "score": score}]}
                for key, score in (("matchable", matchable), ("no-match", no_match))]
    full, crop = rows(0.9, 0.8), rows(0.7, 0.6)
    assert apply_threshold(crop, 0.7)[0]["predictions"]
    assert not apply_threshold(crop, 0.7)[1]["predictions"]
    assert all(not row["predictions"] for row in apply_threshold(full, 1.01))
    tuned = tune_shared_threshold(retrieval_dataset, {"full": full, "crop": crop}, [0.65, 0.85])
    assert tuned["chosen"]["threshold"] == 0.65
    assert tuned["chosen"]["mean_coverage"] == 0.75
    assert tuned["selection_partition"] == "development"


def test_worker_rejects_outbound_network_before_connection():
    script = "from stylematch.encoder_worker import deny_network; deny_network(); import socket; socket.create_connection(('example.invalid',443))"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Offline encoder forbids socket.getaddrinfo" in result.stderr


def test_worker_allows_only_local_private_path_git_checks():
    script = "from stylematch.encoder_worker import deny_network; deny_network(); from stylematch.preparation import private_path; from pathlib import Path; private_path(Path('data/offline-path-check')); print('allowed')"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "allowed"
    forbidden = "from stylematch.encoder_worker import deny_network; deny_network(); import subprocess; subprocess.run(['git','push'])"
    result = subprocess.run([sys.executable, "-c", forbidden], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Offline encoder forbids subprocess.Popen" in result.stderr


def test_synthetic_onnx_pool_extraction_and_preprocessing(tmp_path):
    np = pytest.importorskip("numpy")
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    import importlib.metadata
    from hashlib import sha256
    from PIL import Image
    from stylematch.encoder_worker import load_encoder
    # Synthetic classifier: global RGB means followed by a two-class linear
    # layer. Retrieval must expose the three pooled channels, not class logits.
    h = onnx.helper
    graph = h.make_graph([
        h.make_node("GlobalAveragePool", ["input"], ["pool"]),
        h.make_node("Flatten", ["pool"], ["flat"], axis=1),
        h.make_node("MatMul", ["flat", "weights"], ["logits"]),
    ], "synthetic-pool", [h.make_tensor_value_info("input", onnx.TensorProto.FLOAT, [1, 3, 224, 224])],
        [h.make_tensor_value_info("logits", onnx.TensorProto.FLOAT, [1, 2])],
        [onnx.numpy_helper.from_array(np.ones((3, 2), dtype=np.float32), "weights")])
    model = h.make_model(graph, opset_imports=[h.make_opsetid("", 12)], ir_version=10)
    content = model.SerializeToString()
    path = tmp_path / "synthetic.onnx"
    path.write_bytes(content)
    config = {"dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "onnx", "onnxruntime")},
              "weight_bytes": len(content), "weight_sha256": sha256(content).hexdigest(),
              "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
    _, encode, transform, measured = load_encoder(config, path, {"torch_threads": 1, "torch_interop_threads": 1, "verify_extraction_synthetic": True})
    tensor = transform(Image.new("RGB", (310, 500), (128, 96, 64)))
    assert tensor.shape == (1, 3, 224, 224) and tensor.dtype == np.float32
    expected = (np.array([128, 96, 64]) / 255 - np.array(config["mean"])) / np.array(config["std"])
    assert encode(tensor).shape == (1, 3)
    assert encode(tensor)[0] == pytest.approx(expected, abs=1e-4)
    assert measured["synthetic_original_pool_equivalence"]["passed"] is True
    assert measured["providers"] == ["CPUExecutionProvider"]
    assert measured["onnxruntime_telemetry_disabled"] is True
