"""Regenerate text stand-ins and manifests. No photographs or model inference."""

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).parent


def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def ref(wardrobe, item):
    return {"wardrobe_id": wardrobe, "item_id": item}


def build():
    images, garments = [], []

    def image(name, partition, kind, parent=None):
        text = f"SYNTHETIC ENGINEERING STAND-IN: {name}. Not a photograph or model input.\n"
        (ROOT / "standins").mkdir(exist_ok=True)
        path = f"standins/{name}.txt"
        (ROOT / path).write_text(text, encoding="utf-8", newline="\n")
        group = parent or name
        images.append({
            "image_id": name, "path": path, "sha256": sha256(text.encode()).hexdigest(),
            "kind": kind, "partition": partition, "provenance": "authored synthetic text stand-in",
            "permission_reference": "synthetic engineering fixture authored for this repository",
            "permitted_use": "synthetic-engineering", "capture_group": group,
            "source_group": group, "parent_image_id": parent,
        })
        return name

    for wardrobe, partition, item, category in (
        ("dev", "development", "top-a", "tops"),
        ("dev", "development", "top-b", "tops"),
        ("dev", "development", "jeans", "bottoms"),
        ("dev", "development", "coat", "outerwear"),
        ("test", "test", "top-a", "tops"),
        ("test", "test", "coat", "outerwear"),
    ):
        image_id = image(f"{wardrobe}-{item}", partition, "garment")
        garments.append({"ref": ref(wardrobe, item), "category": category, "image_ids": [image_id]})
    image("dev-inspiration", "development", "inspiration")
    image("test-inspiration", "test", "inspiration")
    image("dev-crop", "development", "crop", "dev-inspiration")
    queries, judgments, rankings = [], [], []
    tasks = (
        ("dev-top", "dev", "tops", {"top-a": 3, "top-b": 2}, False,
         [("dev", "unknown"), ("test", "top-a"), ("dev", "jeans"),
          ("dev", "top-a"), ("dev", "top-a"), ("dev", "top-b")]),
        ("dev-none", "dev", "outerwear", {"coat": 0}, True, [("dev", "coat")]),
        ("test-top", "test", "tops", {"top-a": 2}, False, []),
        ("test-empty", "test", "bottoms", {}, True, [("dev", "jeans")]),
        ("test-partial", "test", "outerwear", {"coat": 1}, True, []),
        ("test-coat", "test", "outerwear", {"coat": 3}, False, [("test", "coat")]),
    )
    for name, wardrobe, category, grades, no_match, predictions in tasks:
        partition = "development" if wardrobe == "dev" else "test"
        queries.append({
            "query_id": name, "active_wardrobe_id": wardrobe,
            "image_id": f"{wardrobe}-inspiration", "component_category": category,
            "partition": partition, "crop_image_id": "dev-crop" if name == "dev-top" else None,
        })
        judgments.append({
            "query_id": name, "reviewer_id": "synthetic-author", "no_match": no_match,
            "uncertain": False, "notes": "Synthetic engineering labels; not human feasibility evidence.",
            "grades": [{"ref": ref(wardrobe, item), "relevance": grade} for item, grade in grades.items()],
        })
        rankings.append({"query_id": name, "predictions": [
            {"ref": ref(w, item), "score": None} for w, item in predictions
        ]})
    dataset = {
        "schema_version": 1, "dataset_id": "synthetic-v1", "synthetic": True,
        "wardrobes": [
            {"wardrobe_id": "dev", "person_id": "synthetic-person", "partition": "development"},
            {"wardrobe_id": "test", "person_id": "synthetic-person", "partition": "test"},
        ],
        "images": images, "garments": garments, "queries": queries, "judgments": judgments,
    }
    write_json("dataset.json", dataset)
    write_json("run.json", {
        "schema_version": 1, "run_id": "synthetic-hand-ranked-v1", "dataset_id": dataset["dataset_id"],
        "dataset_sha256": sha256((ROOT / "dataset.json").read_bytes()).hexdigest(),
        "status": "complete", "failures": [],
        "model": {
            "name": "synthetic-hand-ranking", "checkpoint": "none-no-model", "revision": "fixture-v1",
            "preprocessing": "none-text-standins", "dependency_lock_sha256": None,
            "notes": "No model executed. Rankings authored by fixture generator; no model dependency lock.",
        },
        "threshold": None, "threshold_selection_partition": "development",
        "resources": {
            "device": "none-no-model-execution", "wall_time_ms": None,
            "peak_ram_bytes": None, "peak_vram_bytes": None,
            "missing_reasons": {
                name: "No model executed; engineering fixture only."
                for name in ("wall_time_ms", "peak_ram_bytes", "peak_vram_bytes")
            },
        },
        "rankings": rankings,
    })


if __name__ == "__main__":
    build()
