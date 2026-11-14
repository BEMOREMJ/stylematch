"""Synthetic interpretation checks; no owner labels or private photos."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from stylematch.interpretation import VOCAB, import_reference, parse_prediction, score
from stylematch.vlm_worker import png_payload
from PIL import Image


def prediction(**changes):
    return json.dumps({"garment_type": "shorts", "color": "blue", "pattern": "solid",
                       "description": "Blue short bottoms are visible.", **changes})


@pytest.mark.parametrize("raw", ["", "```json\n" + prediction() + "\n```", prediction(color="navy"),
                                prediction(extra="guess"), prediction(description=""),
                                prediction(description="a" * 241),
                                '{"color":"blue","color":"red"}', '[]', 'null'])
def test_strict_schema_does_not_repair(raw):
    value, error = parse_prediction(raw)
    assert value is None and error


def test_explicit_unknown_is_valid():
    value, error = parse_prediction(prediction(garment_type="unknown", color="unknown", pattern="unknown"))
    assert error is None and value["color"] == "unknown"


def test_denominators_unknowns_failures_and_occlusion():
    reference = {"labels": [
        {"id": "a", "garment_type": "shorts", "color": "blue", "pattern": "solid"},
        {"id": "b", "garment_type": "unknown", "color": "blue", "pattern": "unknown"},
        {"id": "c", "garment_type": "shorts", "color": "unknown", "pattern": "solid"},
    ], "mapping": {"items": [
        {"id": "a", "kind": "wardrobe", "entity": ["w", "a"]},
        {"id": "b", "kind": "crop", "entity": "task-009"},
        {"id": "c", "kind": "crop", "entity": "task-010"},
    ]}}
    predictions = [{"id": "a", "raw": prediction()}, {"id": "b", "raw": prediction(color="unknown")},
                   {"id": "c", "raw": "invalid"}]
    report = score(reference, predictions)
    color = report["all"]["fields"]["color"]
    assert color["correct_on_human_known"] == {"count": 1, "total": 2, "percent": 50}
    assert color["accuracy_among_answered_known"] == {"count": 1, "total": 1, "percent": 100}
    assert color["answered_all"]["total"] == 3
    assert report["all"]["fields"]["garment_type"]["asserted_on_human_unknown"]["count"] == 1
    assert report["crop"]["schema_valid"] == {"count": 1, "total": 2, "percent": 50}
    assert report["occluded_components"]["items"] == 2
    assert len(report["failures"]) == 1
    assert report["wardrobe"]["fields"]["color"]["asserted_on_human_unknown"]["percent"] is None
    with pytest.raises(ValueError, match="membership"):
        score(reference, predictions[:-1])


def test_reference_import_requires_owner_complete_and_preserves_snapshot(tmp_path, monkeypatch):
    # Test path policy separately in existing preparation tests.
    monkeypatch.setattr("stylematch.interpretation.private_path", lambda p: p)
    monkeypatch.setattr("stylematch.preparation.private_path", lambda p: p)
    review = tmp_path / "review"
    review.mkdir()
    mapping = {"items": [{"id": "view-001"}], "vocabulary": VOCAB}
    (review / "mapping.json").write_text(json.dumps(mapping))
    labels = tmp_path / "owner.json"
    document = {"bundle": sha256((review / "mapping.json").read_bytes()).hexdigest(),
                "completed_by": "Mark", "annotation_seconds": None,
                "labels": [{"id": "view-001", **{k: "unknown" for k in VOCAB}}]}
    labels.write_text(json.dumps(document))
    output = tmp_path / "reference.json"
    assert import_reference(review, labels, output)["reference_items"] == 1
    saved = output.read_bytes()
    assert json.loads(saved)["annotation_seconds"] is None
    with pytest.raises(FileExistsError):
        import_reference(review, labels, output)
    assert output.read_bytes() == saved
    for change in (lambda d: d.update(completed_by=None),
                   lambda d: d["labels"][0].update(color=""),
                   lambda d: d["labels"].append(d["labels"][0]),
                   lambda d: d.update(annotation_seconds=-1),
                   lambda d: d.update(bundle="wrong")):
        altered = deepcopy(document)
        change(altered)
        labels.write_text(json.dumps(altered))
        with pytest.raises(ValueError):
            import_reference(review, labels, tmp_path / "invalid.json")


def test_input_resizing_retains_whole_view_and_no_upscale():
    import base64
    from io import BytesIO
    for original, expected in [((1000, 500), (512, 256)), ((50, 100), (50, 100))]:
        image = Image.new("RGB", original, (23, 40, 80))
        value = png_payload(image, 512)
        with Image.open(BytesIO(base64.b64decode(value.split(",")[1]))) as decoded:
            assert decoded.size == expected and decoded.mode == "RGB" and not decoded.info
