"""Deterministic raw and grounded metrics; filtering never hides raw errors."""

from math import log2, sqrt

from .contracts import Dataset, Run
from .validation import validate_dataset, validate_run


def proportion(successes: int, count: int) -> dict:
    if not count:
        return {"value": None, "numerator": successes, "denominator": 0, "wilson95": None}
    value = successes / count
    z = 1.959963984540054
    scale = 1 + z * z / count
    center = (value + z * z / (2 * count)) / scale
    radius = z * sqrt(value * (1 - value) / count + z * z / (4 * count * count)) / scale
    return {
        "value": value, "numerator": successes, "denominator": count,
        "wilson95": [max(0.0, center - radius), min(1.0, center + radius)],
    }


def mean(values: list[float]) -> dict:
    return {"value": sum(values) / len(values) if values else None, "denominator": len(values)}


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / log2(rank + 2) for rank, grade in enumerate(grades))


def summarize(rows: list[dict], ks: tuple[int, ...]) -> dict:
    matchable = [row for row in rows if not row["no_match"]]
    no_match = [row for row in rows if row["no_match"]]
    slots = sum(row["slots"] for row in rows)
    return {
        "query_count": len(rows), "matchable_count": len(matchable), "no_match_count": len(no_match),
        "hit_at_k": {str(k): proportion(sum(r["hit"][k] for r in matchable), len(matchable)) for k in ks},
        "recall_at_k": {str(k): mean([r["recall"][k] for r in matchable]) for k in ks},
        "ndcg_at_k": {str(k): mean([r["ndcg"][k] for r in matchable]) for k in ks},
        "no_match_false_acceptance": proportion(sum(r["accepted"] for r in no_match), len(no_match)),
        "matchable_false_rejection": proportion(sum(not r["accepted"] for r in matchable), len(matchable)),
        "recommendation_coverage": proportion(sum(r["accepted"] for r in rows), len(rows)),
        "prediction_slots": slots,
        "invalid_id_rate": proportion(sum(r["invalid"] for r in rows), slots),
        "category_violation_rate": proportion(sum(r["category_errors"] for r in rows), slots),
        "duplicate_prediction_rate": proportion(sum(r["duplicates"] for r in rows), slots),
    }


def evaluate(dataset: Dataset, run: Run, ks: tuple[int, ...] = (3, 5), *, dataset_sha256=None) -> dict:
    if not ks or any(type(k) is not int or k <= 0 for k in ks) or len(set(ks)) != len(ks):
        raise ValueError("k values must be unique positive integers")
    inventory = validate_dataset(dataset)
    validate_run(dataset, run, dataset_sha256)
    report = {
        "report_schema_version": 1, "dataset_id": dataset.dataset_id, "run_id": run.run_id,
        "synthetic": dataset.synthetic, "status": run.status, "failures": run.failures,
        "inventory": inventory, "model": run.model.model_dump(),
        "threshold": run.threshold, "threshold_selection_partition": run.threshold_selection_partition,
        "resources": run.resources.model_dump(),
        "uncertainty_note": "Wilson 95% intervals for proportions only; tasks may be correlated. "
        "No population-level claim; no interval estimated for mean Recall/nDCG.",
    }
    if run.status == "failed":
        return {**report, "raw": None, "validated": None, "per_query": []}

    items = {g.ref.key: g for g in dataset.garments}
    labels = {j.query_id: j for j in dataset.judgments}
    rankings = {r.query_id: r for r in run.rankings}
    rows = {"raw": [], "validated": []}
    per_query = []
    for query in dataset.queries:
        judgment = labels[query.query_id]
        grades = {g.ref.key: g.relevance for g in judgment.grades}
        relevant = {key for key, grade in grades.items() if grade >= 2}
        raw = [prediction.ref.key for prediction in rankings[query.query_id].predictions]

        def errors(keys):
            # Unknown IDs and wrong-wardrobe IDs are invalid. Category errors are
            # independently counted for any globally known item, even if also invalid.
            invalid = sum(key not in items or key[0] != query.active_wardrobe_id for key in keys)
            category = sum(key in items and items[key].category != query.component_category for key in keys)
            return invalid, category, len(keys) - len(set(keys))

        clean, seen = [], set()
        for key in raw:
            if (key in items and key[0] == query.active_wardrobe_id
                    and items[key].category == query.component_category and key not in seen):
                clean.append(key)
                seen.add(key)
        detail = {"query_id": query.query_id, "raw": raw, "validated": clean}
        for mode, keys in (("raw", raw), ("validated", clean)):
            invalid, category, duplicates = errors(keys)
            row = {
                "query_id": query.query_id, "partition": query.partition,
                "category": query.component_category, "no_match": judgment.no_match,
                "accepted": bool(keys), "slots": len(keys), "invalid": invalid,
                "category_errors": category, "duplicates": duplicates,
                "hit": {}, "recall": {}, "ndcg": {},
            }
            seen = set()
            observed = []
            for key in keys:
                observed.append(grades.get(key, 0) if key not in seen else 0)
                seen.add(key)
            for k in ks:
                hits = len(set(keys[:k]) & relevant)
                row["hit"][k] = int(hits > 0)
                row["recall"][k] = hits / len(relevant) if relevant else None
                ideal = dcg(sorted(grades.values(), reverse=True)[:k])
                row["ndcg"][k] = dcg(observed[:k]) / ideal if relevant else None
            rows[mode].append(row)
            detail[f"{mode}_metrics"] = row
        per_query.append(detail)

    for mode in rows:
        selected = rows[mode]
        report[mode] = {
            "overall": summarize(selected, ks),
            "partitions": {
                p: summarize([r for r in selected if r["partition"] == p], ks)
                for p in ("development", "test")
            },
            "categories": {
                c: summarize([r for r in selected if r["category"] == c], ks)
                for c in ("tops", "bottoms", "outerwear")
            },
            "partition_categories": {
                f"{p}/{c}": summarize([
                    r for r in selected if r["partition"] == p and r["category"] == c
                ], ks)
                for p in ("development", "test") for c in ("tops", "bottoms", "outerwear")
            },
        }
    report["per_query"] = per_query
    return report
