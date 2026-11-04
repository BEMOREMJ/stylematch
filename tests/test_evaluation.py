from math import log2

import pytest

from stylematch.contracts import Dataset, Run
from stylematch.evaluation import dcg, evaluate


def test_hand_computed_dcg():
    assert dcg([3, 2, 1]) == pytest.approx(7 + 3 / log2(3) + 1 / 2)
    assert dcg([]) == 0


def test_multiple_matches_hand_computed_metrics(dataset, run):
    report = evaluate(dataset, run, (1, 3, 5))
    query = report["per_query"][0]
    raw, clean = query["raw_metrics"], query["validated_metrics"]
    assert raw["hit"][3] == 0
    assert raw["recall"][5] == 0.5
    assert raw["ndcg"][5] == pytest.approx((7 / log2(5)) / (7 + 3 / log2(3)))
    assert clean["hit"][1] == 1
    assert clean["recall"][1] == 0.5
    assert clean["recall"][3] == 1
    assert clean["ndcg"][3] == 1
    assert report["validated"]["overall"]["hit_at_k"]["3"]["value"] == pytest.approx(2 / 3)
    assert report["validated"]["overall"]["recall_at_k"]["3"]["value"] == pytest.approx(2 / 3)
    assert report["validated"]["overall"]["ndcg_at_k"]["5"]["value"] == pytest.approx(2 / 3)


def test_no_match_abstention_zero_relevant_and_coverage(dataset, run):
    report = evaluate(dataset, run)
    raw, clean = report["raw"]["overall"], report["validated"]["overall"]
    assert clean["matchable_count"] == clean["no_match_count"] == 3
    assert raw["no_match_false_acceptance"]["value"] == pytest.approx(2 / 3)
    assert clean["no_match_false_acceptance"]["value"] == pytest.approx(1 / 3)
    assert clean["matchable_false_rejection"]["value"] == pytest.approx(1 / 3)
    assert clean["recommendation_coverage"]["value"] == 0.5
    empty = next(r for r in report["per_query"] if r["query_id"] == "test-empty")
    assert empty["validated"] == []
    assert empty["validated_metrics"]["ndcg"][3] is None
    assert empty["validated_metrics"]["recall"][3] is None
    assert report["validated"]["categories"]["bottoms"]["hit_at_k"]["3"]["value"] is None


def test_errors_before_and_after_filtering(dataset, run):
    report = evaluate(dataset, run)
    raw, clean = report["raw"]["overall"], report["validated"]["overall"]
    assert raw["prediction_slots"] == 9
    assert raw["invalid_id_rate"]["numerator"] == 3
    assert raw["invalid_id_rate"]["value"] == pytest.approx(3 / 9)
    assert raw["category_violation_rate"]["numerator"] == 1
    assert raw["duplicate_prediction_rate"]["numerator"] == 1
    assert clean["prediction_slots"] == 4
    for metric in ("invalid_id_rate", "category_violation_rate", "duplicate_prediction_rate"):
        assert clean[metric]["numerator"] == 0
        assert clean[metric]["value"] == 0
    wardrobes = {q.query_id: q.active_wardrobe_id for q in dataset.queries}
    for row in report["per_query"]:
        for wardrobe, item in row["validated"]:
            assert wardrobe == wardrobes[row["query_id"]]


def test_duplicate_never_inflates_recall_or_dcg(dataset, run_data):
    run_data["rankings"][0]["predictions"] = [
        {"ref": {"wardrobe_id": "dev", "item_id": "top-a"}, "score": None}
    ] * 3
    report = evaluate(dataset, Run.model_validate(run_data), (3,))
    raw = report["per_query"][0]["raw_metrics"]
    assert raw["recall"][3] == 0.5
    assert raw["ndcg"][3] == pytest.approx(7 / (7 + 3 / log2(3)))
    assert raw["duplicates"] == 2


def test_all_empty_rankings(dataset, run_data):
    for ranking in run_data["rankings"]:
        ranking["predictions"] = []
    summary = evaluate(dataset, Run.model_validate(run_data))["validated"]["overall"]
    assert summary["hit_at_k"]["3"]["value"] == 0
    assert summary["ndcg_at_k"]["5"]["value"] == 0
    assert summary["no_match_false_acceptance"]["value"] == 0
    assert summary["matchable_false_rejection"]["value"] == 1
    assert summary["recommendation_coverage"]["value"] == 0
    assert summary["invalid_id_rate"]["value"] is None


def test_only_no_match_queries_have_undefined_retrieval_metrics(data, run_data):
    keep = {"dev-none", "test-empty", "test-partial"}
    data["queries"] = [q for q in data["queries"] if q["query_id"] in keep]
    data["judgments"] = [j for j in data["judgments"] if j["query_id"] in keep]
    run_data["rankings"] = [r for r in run_data["rankings"] if r["query_id"] in keep]
    summary = evaluate(Dataset.model_validate(data), Run.model_validate(run_data))["validated"]["overall"]
    assert summary["matchable_count"] == 0
    assert summary["hit_at_k"]["3"]["value"] is None
    assert summary["recall_at_k"]["3"]["value"] is None
    assert summary["ndcg_at_k"]["5"]["value"] is None
    assert summary["matchable_false_rejection"]["value"] is None


def test_partial_grade_receives_graded_gain_but_is_not_relevant(data, run_data):
    # Reclassify the stand-in to make a third eligible, partial-only candidate.
    data["garments"][2]["category"] = "tops"
    data["judgments"][0]["grades"].append({"ref": {"wardrobe_id": "dev", "item_id": "jeans"}, "relevance": 1})
    run_data["rankings"][0]["predictions"] = [{"ref": {"wardrobe_id": "dev", "item_id": "jeans"}}]
    row = evaluate(Dataset.model_validate(data), Run.model_validate(run_data), (1,))["per_query"][0]["raw_metrics"]
    assert row["hit"][1] == 0
    assert row["recall"][1] == 0
    assert row["ndcg"][1] == pytest.approx(1 / 7)


def test_failed_run_is_not_a_scored_success(dataset, run_data):
    run_data.update(status="failed", failures=["execution failed before rankings"], rankings=[])
    result = evaluate(dataset, Run.model_validate(run_data))
    assert result["status"] == "failed"
    assert result["raw"] is result["validated"] is None


@pytest.mark.parametrize("ks", [(), (0,), (-1,), (3, 3), (True,), (1.5,)])
def test_invalid_k_rejected(dataset, run, ks):
    with pytest.raises(ValueError, match="positive integers"):
        evaluate(dataset, run, ks)


def test_repeated_evaluation_is_identical_and_does_not_mutate(dataset, run):
    before = run.model_dump_json()
    assert evaluate(dataset, run) == evaluate(dataset, run)
    assert before == run.model_dump_json()
