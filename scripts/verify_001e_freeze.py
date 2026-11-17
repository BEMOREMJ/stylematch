"""Verify accepted development locks without collecting or scoring fresh inputs."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from stylematch.comparison import validate_reference, verify_ledger
from stylematch.preparation import load_pilot, new_json, private_path, sanitized_pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pilot = Path("data/pilot-02")
    reference = Path("data/interpretation-001d-01")
    config_path = Path("configs/001e-a1-a-v1.json")
    config = json.loads(config_path.read_bytes())
    def read(path):
        return json.loads(path.read_bytes())
    def digest(path):
        return sha256(path.read_bytes()).hexdigest()
    subprocess.run(["git", "merge-base", "--is-ancestor", config["draft_commit"], "HEAD"], check=True)
    for name, expected in config["public_bindings"].items():
        committed = subprocess.check_output(["git", "show", f"{config['draft_commit']}:{name}"])
        if sha256(committed).hexdigest() != expected or committed.replace(b"\r\n", b"\n") != Path(name).read_bytes().replace(b"\r\n", b"\n"):
            raise ValueError(f"Frozen source changed: {name}")
    dataset, audit = load_pilot(pilot, "dataset-labeled-01.json", require_labels=True)
    if Counter(g.category for g in dataset.garments) != {"tops": 6, "bottoms": 6, "outerwear": 3}:
        raise ValueError("Locked wardrobe membership changed")
    attrs = validate_reference(dataset, digest(pilot / "dataset-labeled-01.json"), audit["plan"]["reviewer_id"],
        read(reference / "reference-01.json"), read(reference / "review-01/mapping.json"),
        read(reference / "review-01/001d-attribute-labels.json"), digest(reference / "review-01/mapping.json"),
        digest(reference / "review-01/001d-attribute-labels.json"))
    verify_ledger(read(reference / "preservation-before.json")["files"])
    encoder = read(Path("configs/001c-encoder.json"))
    weights = Path("models/mobilenetv2-onnx-001c/mobilenetv2-12.onnx")
    if weights.stat().st_size != encoder["weight_bytes"] or digest(weights) != encoder["weight_sha256"]:
        raise ValueError("Frozen checkpoint bytes changed")
    output = private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    tags = {"schema_version": 1, "items": [{"ref": {"wardrobe_id": key[0], "item_id": key[1]}, "attributes": value}
             for key, value in sorted(attrs["wardrobe"].items())]}
    tag_path = output / "canonical-garment-tags.json"
    with tag_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(tags, sort_keys=True, separators=(",", ":")) + "\n")
    overlap = []
    for image in dataset.images:
        pixels, _ = sanitized_pixels((pilot / image.path).read_bytes())
        overlap.append({"image_id": image.image_id, "kind": image.kind, "sha256": image.sha256,
            "pixel_sha256": sha256(f"{pixels.width}x{pixels.height}:".encode() + pixels.tobytes()).hexdigest(),
            "source_group": image.source_group, "capture_group": image.capture_group})
    new_json(output / "verified-bindings.json", {"freeze_id": config["freeze_id"], "draft_commit": config["draft_commit"],
        "public_bindings": config["public_bindings"], "pilot_root": str(pilot), "dataset_file": "dataset-labeled-01.json",
        "dataset_sha256": digest(pilot / "dataset-labeled-01.json"), "reference_sha256": digest(reference / "reference-01.json"),
        "canonical_tags_path": str(tag_path), "canonical_tags_sha256": digest(tag_path),
        "garments": [g.model_dump() for g in dataset.garments], "wardrobes": [w.model_dump() for w in dataset.wardrobes],
        "garment_images": [i.model_dump() for i in dataset.images if i.kind == "garment"],
        "development_overlap": overlap, "weights_verified": True, "model_revision": encoder["revision"],
        "weight_sha256": encoder["weight_sha256"], "original_wardrobe_tagging_seconds": None,
        "fresh_source_overlap_audit": "pending actual fresh sources; code bound and checked synthetically"})
    print(json.dumps({"verified_garments": len(dataset.garments), "verified_tag_sets": len(attrs["wardrobe"]),
                      "model_verified": True, "private_output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
