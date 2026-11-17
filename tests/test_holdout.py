"""Proposed known-wardrobe/new-owner splits and clustered inference, synthetic only."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from stylematch.contracts import Dataset, Run
from stylematch.evaluation import evaluate
from stylematch.holdout import audit_holdout_split, paired_source_hit1
from stylematch.validation import validate_dataset


def partition(data, name):
    result = deepcopy(data)
    result["dataset_id"] += "-" + name
    result["wardrobes"] = [w for w in result["wardrobes"] if w["partition"] == name]
    result["images"] = [i for i in result["images"] if i["partition"] == name]
    result["garments"] = [g for g in result["garments"] if g["ref"]["wardrobe_id"] in {w["wardrobe_id"] for w in result["wardrobes"]}]
    result["queries"] = [q for q in result["queries"] if q["partition"] == name]
    result["judgments"] = [j for j in result["judgments"] if j["query_id"] in {q["query_id"] for q in result["queries"]}]
    return result


@pytest.fixture
def holdout_manifests(data):
    dev = partition(data, "development")
    test_a = deepcopy(dev)
    test_a["dataset_id"] = "synthetic-heldout-a"
    renamed = {i["image_id"]: "fresh-" + i["image_id"] for i in test_a["images"] if i["kind"] != "garment"}
    for w in test_a["wardrobes"]:
        w["partition"] = "test"
    for image in test_a["images"]:
        image["partition"] = "test"
        if image["image_id"] in renamed:
            image["image_id"] = renamed[image["image_id"]]
            image["path"] = f"standins/{image['image_id']}.txt"
            image["sha256"] = sha256(image["image_id"].encode()).hexdigest()
            image["source_group"] = "fresh-" + image["source_group"]
            image["capture_group"] = "fresh-" + image["capture_group"]
            if image["parent_image_id"]:
                image["parent_image_id"] = renamed[image["parent_image_id"]]
    for q in test_a["queries"]:
        q.update(query_id="fresh-" + q["query_id"], partition="test", image_id=renamed[q["image_id"]],
                 crop_image_id="fresh-dev-crop")
    for j in test_a["judgments"]:
        j["query_id"] = "fresh-" + j["query_id"]
    test_b = partition(data, "test")
    test_b["wardrobes"][0]["person_id"] = "independent-owner"
    crop = deepcopy(next(i for i in test_b["images"] if i["kind"] == "inspiration"))
    crop.update(image_id="test-crop", path="standins/test-crop.txt", kind="crop", parent_image_id="test-inspiration",
                sha256=sha256(b"synthetic fresh crop").hexdigest())
    test_b["images"].append(crop)
    for q in test_b["queries"]:
        q["crop_image_id"] = "test-crop"
    return dev, test_a, test_b


def audit_a(dev, heldout, **kwargs):
    return audit_holdout_split(Dataset.model_validate(dev), Dataset.model_validate(heldout),
                               design="known-wardrobe", locked_tags=b"synthetic locked registry",
                               heldout_tags=b"synthetic locked registry", **kwargs)


def test_known_wardrobe_is_explicitly_audited_without_changing_existing_manifest(holdout_manifests):
    dev, test_a, _ = holdout_manifests
    before = deepcopy(holdout_manifests)
    for payload in (dev, test_a):
        validate_dataset(Dataset.model_validate(payload))
    audit = audit_a(dev, test_a, require_judgments=True)
    assert audit["intentional_wardrobe_ids"] == ["dev"]
    assert audit["intentional_person_overlap"] == ["synthetic-person"]
    assert len(audit["intentional_garment_image_ids"]) == 4
    assert len(audit["intentional_garment_overlap"]["sha256"]) == 4
    assert audit["unexpected_overlap"] == []
    assert holdout_manifests == before
    # Relabeling a query inside the original manifest still fails the strict core.
    invalid = deepcopy(dev)
    invalid["queries"][0]["partition"] = "test"
    with pytest.raises(ValueError, match="wardrobe partition"):
        validate_dataset(Dataset.model_validate(invalid))


@pytest.mark.parametrize("field", ["sha256", "capture_group", "source_group"])
@pytest.mark.parametrize("kind", ["inspiration", "crop", "unused"])
def test_reuse_never_waives_fresh_input_leakage(holdout_manifests, field, kind):
    dev, test_a, _ = holdout_manifests
    value = next(i[field] for i in dev["images"] if i["kind"] == "garment")
    if kind == "unused":
        unused = deepcopy(next(i for i in test_a["images"] if i["kind"] == "inspiration"))
        unused.update(image_id="unused", path="standins/unused.txt", sha256=sha256(b"unused").hexdigest(),
                      source_group="unused", capture_group="unused")
        unused[field] = value
        test_a["images"].append(unused)
    else:
        for image in test_a["images"]:
            if image["kind"] == kind or (field != "sha256" and image["kind"] != "garment"):
                image[field] = value
    with pytest.raises(ValueError, match="cross-manifest.*leakage"):
        audit_a(dev, test_a)


def test_garment_source_group_cannot_hide_development_inspiration(holdout_manifests):
    dev, test_a, _ = holdout_manifests
    group = next(i["source_group"] for i in dev["images"] if i["kind"] == "inspiration")
    for payload in (dev, test_a):
        next(i for i in payload["images"] if i["kind"] == "garment")["source_group"] = group
    with pytest.raises(ValueError, match="cross-manifest source_group"):
        audit_a(dev, test_a)


def test_locked_registry_membership_and_images_cannot_change(holdout_manifests):
    dev, test_a, _ = holdout_manifests
    for tags in (None, b"changed"):
        with pytest.raises(ValueError, match="tag bytes"):
            audit_holdout_split(Dataset.model_validate(dev), Dataset.model_validate(test_a),
                                design="known-wardrobe", locked_tags=b"locked", heldout_tags=tags)
    changed = deepcopy(test_a)
    changed["judgments"] = []
    changed["garments"][0]["category"] = "bottoms"
    with pytest.raises(ValueError, match="membership"):
        audit_a(dev, changed)
    changed = deepcopy(test_a)
    next(i for i in changed["images"] if i["kind"] == "garment")["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="metadata"):
        audit_a(dev, changed)


def test_independent_owner_design_rejects_people_and_image_overlap(holdout_manifests):
    dev, _, test_b = holdout_manifests
    def check(payload):
        return audit_holdout_split(Dataset.model_validate(dev), Dataset.model_validate(payload), design="new-owner")
    audit = check(test_b)
    assert audit["intentional_person_overlap"] == audit["intentional_wardrobe_ids"] == []
    assert audit["intentional_garment_overlap"]["sha256"] == []
    changed = deepcopy(test_b)
    changed["wardrobes"][0]["person_id"] = dev["wardrobes"][0]["person_id"]
    with pytest.raises(ValueError, match="independence"):
        check(changed)
    changed = deepcopy(test_b)
    changed["images"][0]["sha256"] = dev["images"][0]["sha256"]
    with pytest.raises(ValueError, match="leakage"):
        check(changed)


def test_label_free_audit_then_exhaustive_labels_preserve_multiple_matches_and_no_match(holdout_manifests, run_data):
    dev, test_a, _ = holdout_manifests
    label_free = deepcopy(test_a)
    label_free["judgments"] = []
    audit_a(dev, label_free)
    with pytest.raises(ValueError, match="query judgments"):
        audit_a(dev, label_free, require_judgments=True)
    audit_a(dev, test_a, require_judgments=True)
    assert sorted(g["relevance"] for g in test_a["judgments"][0]["grades"]) == [2, 3]
    assert test_a["judgments"][1]["no_match"]
    run_data.update(dataset_id=test_a["dataset_id"], rankings=[
        {"query_id": q["query_id"], "predictions": [{"ref": g["ref"], "score": None}
            for g in test_a["garments"] if g["category"] == q["component_category"]]}
        for q in test_a["queries"]])
    # Hand-authored synthetic ordering only; no encoder/model is invoked.
    report = evaluate(Dataset.model_validate(test_a), Run.model_validate(run_data), (1, 3, 5))
    assert report["validated"]["overall"]["recall_at_k"]["3"]["value"] == 1
    assert report["validated"]["overall"]["no_match_false_acceptance"]["numerator"] == 1
    for mode in ("raw", "validated"):
        assert report[mode]["overall"]["invalid_id_rate"]["numerator"] == 0
    incomplete = deepcopy(test_a)
    incomplete["judgments"][0]["grades"].pop()
    with pytest.raises(ValueError, match="incomplete judgments"):
        audit_a(dev, incomplete, require_judgments=True)


def row(name, source, crop, assisted, no_match=False):
    return {"query_id": name, "source_group": source, "crop_hit1": crop,
            "attributes_hit1": assisted, "no_match": no_match}


def test_cluster_bootstrap_preserves_dependence_and_exposes_concentration():
    rows = [row(str(i), "one-look", 0, 1) for i in range(4)] + [row("loss", "second-look", 1, 0)]
    result = paired_source_hit1(rows)
    assert result["delta_hit1"] == pytest.approx(0.6)
    assert result["source_balanced_delta"] == 0
    assert result["source_cluster_percentile95"] == [-1, 1]
    assert result["leave_one_source_out_delta"] == {"one-look": -1, "second-look": 1}
    assert result["ranking_evidence_floor_met"] is False
    assert paired_source_hit1(rows) == result
    assert paired_source_hit1(rows + [row("none", "third-look", 0, 0, True)]) == result


def test_many_components_from_one_source_do_not_meet_independence_floor():
    result = paired_source_hit1([row(str(i), "single-source", 0, 1) for i in range(100)])
    assert result["matchable_tasks"] == 100 and result["matchable_sources"] == 1
    assert result["source_cluster_percentile95"] is None
    assert result["ranking_evidence_floor_met"] is False
    empty = paired_source_hit1([])
    assert empty["delta_hit1"] is empty["source_cluster_percentile95"] is None
    assert empty["gains"] == empty["losses"] == []


def test_draft_estimate_arithmetic_and_status():
    proposal = json.loads(Path("configs/001e-heldout-draft.json").read_bytes())
    assert proposal["status"] == "DRAFT" and proposal["owner_approval"] is None
    assert proposal["selected_design"] is proposal["label_custodian"] is None
    tasks = proposal["collection"]["expected_tasks_by_category"]
    for option in proposal["options"].values():
        assert sum(tasks.values()) == option["expected_tasks"]
        assert sum(tasks[c] * n for c, n in option["garments_by_category"].items()) == option["expected_candidate_judgments"]
