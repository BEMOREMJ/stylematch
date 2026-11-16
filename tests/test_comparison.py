"""Synthetic safety and metric checks for the assisted comparison, no real data."""
from copy import deepcopy

import pytest

from test_benchmark import retrieval_dataset
from stylematch.benchmark import category_rankings, resources, retrieval_inputs
from stylematch.comparison import (agreement, ordering_only, paired, rank_assisted,
                                  scoring_inputs, validate_reference, verify_ledger, verify_pools)
from stylematch.contracts import Dataset, ModelMetadata, Run
from stylematch.evaluation import evaluate
from stylematch.interpretation import VOCAB, inputs as reference_views


def attrs(**changes):
    return {"garment_type": "shirt", "color": "blue", "pattern": "solid", **changes}


def candidate(name, cosine, **changes):
    return {"ref": {"wardrobe_id": "synthetic", "item_id": name}, "cosine": cosine,
            "attributes": attrs(**changes)}


def tasks():
    return [{"query_id": "q", "attributes": attrs(), "candidates": [
        candidate("a", 0.9, color="red", garment_type="tshirt"),
        candidate("b", 0.6)]}]


def test_unknown_never_agrees_or_renormalizes():
    assert sum(agreement(attrs(), attrs()).values()) == 3
    assert agreement(attrs(), attrs(color="unknown"))["color"] == 0
    assert agreement(attrs(color="unknown"), attrs(color="unknown"))["color"] == 0
    assert sum(agreement({}, {}).values()) == 0
    data = tasks()
    data[0]["attributes"] = attrs(garment_type="unknown", pattern="unknown")
    ranking, _ = rank_assisted(data)
    assert ranking[0]["predictions"][0]["score"] == pytest.approx(1 / 3)


def test_fixed_hybrid_weights_and_explanations():
    ranking, evidence = rank_assisted(tasks(), hybrid=True)
    assert [p["ref"]["item_id"] for p in ranking[0]["predictions"]] == ["b", "a"]
    assert ranking[0]["predictions"][0]["score"] == pytest.approx(0.9)
    for row in evidence[0]["candidates"]:
        assert row["score"] == pytest.approx(row["embedding_contribution"] + sum(row["field_contributions"].values()))
    omitted, without = rank_assisted(tasks(), hybrid=True, omitted="color")
    assert omitted[0]["predictions"][0]["score"] == pytest.approx(0.9 - 1 / 6)
    assert without[0]["candidates"][1]["field_contributions"]["garment_type"] == pytest.approx(1 / 6)


def test_attribute_only_order_is_independent_of_cosines():
    data = tasks()
    before, _ = rank_assisted(data)
    data[0]["candidates"][0]["cosine"] = -1.0
    data[0]["candidates"][1]["cosine"] = 1.0
    after, _ = rank_assisted(data)
    assert after == before


def test_ties_and_no_agreements_have_documented_fallback():
    data = tasks()
    data[0]["attributes"] = {}
    data[0]["candidates"].reverse()
    ranking, _ = rank_assisted(data)
    assert [p["ref"]["item_id"] for p in ranking[0]["predictions"]] == ["a", "b"]
    ranking, _ = rank_assisted(data, hybrid=True)
    assert [p["ref"]["item_id"] for p in ranking[0]["predictions"]] == ["a", "b"]
    data[0]["candidates"][0]["cosine"] = 0.9
    ranking, _ = rank_assisted(data, hybrid=True)
    assert ranking[0]["predictions"][0]["ref"]["item_id"] == "a"


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -1.01, 1.01, "0.8", True])
def test_bad_embedding_never_silently_substitutes(bad):
    data = tasks()
    data[0]["candidates"][0]["cosine"] = bad
    with pytest.raises(ValueError, match="embedding"):
        rank_assisted(data, hybrid=True)


def test_ordering_mask_uses_original_top_cosine_only():
    data = tasks()
    data.append({**deepcopy(data[0]), "query_id": "reject"})
    data[0]["candidates"][0]["cosine"] = 0.60
    data[0]["candidates"][1]["cosine"] = 0.59
    for c in data[1]["candidates"]:
        c["cosine"] = 0.59
    original = [{"query_id": t["query_id"], "predictions": [
        {"ref": c["ref"], "score": c["cosine"]} for c in t["candidates"]]} for t in data]
    hybrid, _ = rank_assisted(data, hybrid=True)
    assert hybrid[1]["predictions"][0]["score"] > 0.60
    masked = ordering_only(original, hybrid)
    assert masked[0]["predictions"][0]["ref"]["item_id"] == "b"
    assert masked[1]["predictions"] == []
    with pytest.raises(ValueError, match="mask"):
        ordering_only(original, hybrid[:-1])


def reference_bundle(dataset):
    rows = []
    for n, row in enumerate(reference_views(dataset)):
        rows.append({"id": f"view-{n}", "kind": row["kind"], "entity": row["entity"],
                     "image_path": row["image"]["path"], "sha256": row["image"]["sha256"]})
    mapping = {"dataset_sha256": "d" * 64, "reviewer_id": "synthetic-reviewer", "vocabulary": VOCAB, "items": rows}
    labels = [{"id": r["id"], **attrs()} for r in rows]
    source = {"bundle": "m" * 64, "completed_by": "Mark", "labels": labels}
    reference = {**deepcopy(source), "mapping": deepcopy(mapping), "mapping_sha256": "m" * 64, "source_sha256": "s" * 64}
    return reference, mapping, source


def validate_bundle(dataset, bundle):
    return validate_reference(dataset, "d" * 64, "synthetic-reviewer", *bundle, "m" * 64, "s" * 64)


def test_mapping_validates_complete_bijection_and_source(retrieval_dataset):
    bundle = reference_bundle(retrieval_dataset)
    attributes = validate_bundle(retrieval_dataset, bundle)
    assert len(attributes["wardrobe"]) == 6 and len(attributes["crop"]) == 2
    assert all(set(v) == set(VOCAB) for v in attributes["crop"].values())
    for mutate in (lambda r, m, s: r.update(source_sha256="bad"),
                   lambda r, m, s: s.update(completed_by="someone"),
                   lambda r, m, s: r["labels"][0].update(color="red"),
                   lambda r, m, s: m["items"][0].update(entity=["synthetic", "wrong"]),
                   lambda r, m, s: m["items"][0].update(sha256="0" * 64)):
        changed = deepcopy(bundle)
        mutate(*changed)
        with pytest.raises(ValueError):
            validate_bundle(retrieval_dataset, changed)
    # Even jointly modified mapping/reference must bind back to the accepted images.
    changed = deepcopy(bundle)
    changed[1]["items"][0]["image_path"] = "revealing-name.png"
    changed[0]["mapping"] = deepcopy(changed[1])
    with pytest.raises(ValueError, match="entity/image"):
        validate_bundle(retrieval_dataset, changed)
    changed = deepcopy(bundle)
    changed[1]["items"][1]["entity"] = changed[1]["items"][0]["entity"]
    changed[0]["mapping"] = deepcopy(changed[1])
    with pytest.raises(ValueError, match="duplicate"):
        validate_bundle(retrieval_dataset, changed)


def test_ranker_projection_excludes_grades_notes_paths_and_raw_text(retrieval_dataset):
    attributes = validate_bundle(retrieval_dataset, reference_bundle(retrieval_dataset))
    rankings = category_rankings(retrieval_inputs(retrieval_dataset), 104729)
    for row in rankings:
        for p in row["predictions"]:
            p["score"] = 0.5
    before = scoring_inputs(retrieval_dataset, attributes, rankings)
    payload = retrieval_dataset.model_dump()
    for j in payload["judgments"]:
        j["notes"] = "untrusted raw VLM prose"
        for g in j["grades"]:
            g["relevance"] = 0
    for image in payload["images"]:
        image["path"] = "revealing-unusable-name.png"
    after = scoring_inputs(Dataset.model_validate(payload), attributes, rankings)
    assert after == before
    assert rank_assisted(after, hybrid=True) == rank_assisted(before, hybrid=True)
    assert set(before[0]) == {"query_id", "attributes", "candidates"}
    assert set(before[0]["candidates"][0]) == {"ref", "cosine", "attributes"}


def test_same_pool_rejects_missing_duplicate_and_foreign_ids(retrieval_dataset):
    inputs = retrieval_inputs(retrieval_dataset)
    ranking = category_rankings(inputs, 104729)
    verify_pools(inputs, ranking)
    for mutate in (lambda r: r[0]["predictions"].pop(),
                   lambda r: r[0]["predictions"][0].update(ref=r[0]["predictions"][1]["ref"]),
                   lambda r: r[0]["predictions"][0]["ref"].update(wardrobe_id="foreign"),
                   lambda r: r.append(r[0])):
        changed = deepcopy(ranking)
        mutate(changed)
        with pytest.raises(ValueError):
            verify_pools(inputs, changed)


def test_preservation_detects_changed_bytes(tmp_path):
    from hashlib import sha256
    path = tmp_path / "private.json"
    path.write_bytes(b"preserved")
    ledger = {str(path): sha256(path.read_bytes()).hexdigest()}
    verify_ledger(ledger)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_ledger(ledger)


def test_metrics_keep_graded_changes_and_no_match_separate(retrieval_dataset):
    # Two acceptable items in this synthetic task; graded nDCG still sees grade 1.
    def report(order):
        rankings = [{"query_id": q.query_id, "predictions": [
            {"ref": retrieval_dataset.garments[i].ref.model_dump(), "score": None} for i in order]}
                    for q in retrieval_dataset.queries]
        run = Run(schema_version=1, run_id="synthetic", dataset_id=retrieval_dataset.dataset_id,
                  dataset_sha256="a" * 64, status="complete", failures=[],
                  model=ModelMetadata(name="synthetic", checkpoint="none", revision="test",
                      preprocessing="none", dependency_lock_sha256=None, notes="synthetic"),
                  threshold=None, threshold_selection_partition="development", resources=resources(0), rankings=rankings)
        return evaluate(retrieval_dataset, run, (1, 3, 5))
    old, new = report([1, 0, 3, 4, 2, 5]), report([0, 1, 2, 3, 4, 5])
    assert old["validated"]["overall"]["hit_at_k"]["1"]["denominator"] == 1
    delta = paired(old, new)
    assert delta["counts"]["hit1_delta"]["gains"] == []
    assert delta["counts"]["ndcg5_delta"]["gains"] == ["matchable"]
    assert delta["tasks"][1]["ndcg5_delta"] is None
    for mode in ("raw", "validated"):
        assert new[mode]["overall"]["invalid_id_rate"]["numerator"] == 0
