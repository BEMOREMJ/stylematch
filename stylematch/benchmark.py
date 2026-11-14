"""Private development comparisons using the unchanged STYLEMATCH evaluator."""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import comb, isfinite, log2, sqrt
from pathlib import Path
import platform
import random
import subprocess
import sys
from time import perf_counter_ns

from .contracts import ModelMetadata, Resources, Run
from .evaluation import evaluate
from .preparation import load_pilot, new_json, private_path
from .validation import require


def retrieval_inputs(dataset):
    """Deliberately exclude judgments, provenance, notes and source filenames."""
    used = {image for garment in dataset.garments for image in garment.image_ids}
    used.update(q.image_id for q in dataset.queries)
    used.update(q.crop_image_id for q in dataset.queries if q.crop_image_id)
    return {
        "images": {i.image_id: {"path": i.path, "sha256": i.sha256} for i in dataset.images if i.image_id in used},
        "garments": [g.model_dump() for g in dataset.garments],
        "queries": [q.model_dump() for q in dataset.queries],
    }


def eligible(inputs, query):
    return sorted((g for g in inputs["garments"] if g["ref"]["wardrobe_id"] == query["active_wardrobe_id"]
                   and g["category"] == query["component_category"]),
                  key=lambda g: (g["ref"]["wardrobe_id"], g["ref"]["item_id"]))


def category_rankings(inputs, seed):
    rankings = []
    for query in inputs["queries"]:
        candidates = eligible(inputs, query)
        random.Random(f"{seed}:{query['query_id']}").shuffle(candidates)
        rankings.append({"query_id": query["query_id"], "predictions": [{"ref": g["ref"], "score": None} for g in candidates]})
    return rankings


def normalized(vector):
    require(bool(vector) and all(isfinite(v) for v in vector), "invalid feature vector")
    norm = sqrt(sum(v * v for v in vector))
    require(norm > 0, "zero feature norm")
    return [v / norm for v in vector]


def garment_vectors(inputs, features):
    result = {}
    for garment in inputs["garments"]:
        vectors = [normalized(features[image]) for image in garment["image_ids"]]
        require(len({len(v) for v in vectors}) == 1, "feature dimension mismatch")
        average = [sum(values) / len(vectors) for values in zip(*vectors, strict=True)]
        result[(garment["ref"]["wardrobe_id"], garment["ref"]["item_id"])] = normalized(average)
    return result


def rank_query(inputs, query, feature, wardrobe_features):
    vector = normalized(feature)
    predictions = []
    for garment in eligible(inputs, query):
        ref = garment["ref"]
        candidate = wardrobe_features[(ref["wardrobe_id"], ref["item_id"])]
        require(len(vector) == len(candidate), "query/candidate feature dimension mismatch")
        score = sum(a * b for a, b in zip(vector, candidate, strict=True))
        predictions.append({"ref": ref, "score": score})
    predictions.sort(key=lambda p: (-p["score"], p["ref"]["wardrobe_id"], p["ref"]["item_id"]))
    return {"query_id": query["query_id"], "predictions": predictions}


def rank_vectors(inputs, features, view):
    require(view in ("full", "crop"), "unknown view")
    wardrobe = garment_vectors(inputs, features)
    rankings = []
    for query in inputs["queries"]:
        image = query["image_id"] if view == "full" else query["crop_image_id"]
        require(image is not None, "paired comparison requires a confirmed crop for every task")
        rankings.append(rank_query(inputs, query, features[image], wardrobe))
    return rankings


def expected_category(dataset):
    inputs = retrieval_inputs(dataset)
    labels = {j.query_id: j for j in dataset.judgments}
    rows = []
    for query in inputs["queries"]:
        judgment = labels[query["query_id"]]
        grades = [grade.relevance for grade in judgment.grades]
        n, r = len(eligible(inputs, query)), sum(grade >= 2 for grade in grades)
        k = min(3, n)
        miss = comb(n - r, k) / comb(n, k) if n and n - r >= k else 0.0
        ideal = sum((2**grade - 1) / log2(rank + 2) for rank, grade in enumerate(sorted(grades, reverse=True)[:5]))
        gain_mean = sum(2**grade - 1 for grade in grades) / n if n else 0
        expected_dcg = gain_mean * sum(1 / log2(rank + 2) for rank in range(min(5, n)))
        rows.append({"query_id": query["query_id"], "category": query["component_category"],
                     "eligible": n, "acceptable": r, "no_match": judgment.no_match,
                     "expected_hit3": 1 - miss if r else None,
                     "acceptable_hit_probability": 1 - miss if r else 0.0,
                     "expected_recall3": k / n if r else None,
                     "expected_ndcg5": expected_dcg / ideal if r else None,
                     "hit3_uninformative_small_pool": n <= 3,
                     "eligible_refs": [g["ref"] for g in eligible(inputs, query)],
                     "acceptable_refs": [g.ref.model_dump() for g in judgment.grades if g.relevance >= 2]})
    means = {key: sum(row[key] for row in rows if row[key] is not None) / sum(row[key] is not None for row in rows)
             if any(row[key] is not None for row in rows) else None
             for key in ("expected_hit3", "expected_recall3", "expected_ndcg5")}
    return {"per_task": rows, "matchable_mean": means, "note": "Exact expectation over uniform within-category permutations, not a fitted ranking or model score."}


def apply_threshold(rankings, threshold):
    return [{"query_id": row["query_id"], "predictions": row["predictions"]
             if row["predictions"] and row["predictions"][0]["score"] >= threshold else []} for row in rankings]


def tune_shared_threshold(dataset, views, grid):
    labels = {j.query_id: j for j in dataset.judgments}
    no_match = sum(j.no_match for j in labels.values())
    matchable = len(labels) - no_match
    require(no_match > 0 and matchable > 0, "balanced abstention tuning needs both task types")
    curve = []
    for threshold in grid:
        details = {}
        for view, rankings in views.items():
            accepted = {row["query_id"]: bool(row["predictions"]) for row in apply_threshold(rankings, threshold)}
            require(set(accepted) == set(labels), "threshold inputs must cover all tasks")
            fa = sum(accepted[q] for q, j in labels.items() if j.no_match)
            fr = sum(not accepted[q] for q, j in labels.items() if not j.no_match)
            details[view] = {"false_acceptances": fa, "no_match_denominator": no_match,
                             "false_rejections": fr, "matchable_denominator": matchable,
                             "coverage": sum(accepted.values()) / len(labels),
                             "balanced_error": 0.5 * (fa / no_match + fr / matchable)}
        curve.append({"threshold": threshold, "views": details,
                      "mean_balanced_error": sum(v["balanced_error"] for v in details.values()) / len(details),
                      "mean_coverage": sum(v["coverage"] for v in details.values()) / len(details)})
    chosen = min(curve, key=lambda row: (row["mean_balanced_error"], -row["mean_coverage"], row["threshold"]))
    return {"chosen": chosen, "curve": curve, "selection_partition": "development",
            "warning": "Development-tuned on these same labels for both views; not held-out calibration."}


def process_peak_ram():
    if sys.platform != "win32":
        return None, "Windows peak working-set method unavailable on this platform"
    try:
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                                                    "PagefileUsage", "PeakPagefileUsage")]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize, None
    except (OSError, AttributeError) as exc:
        return None, f"PeakWorkingSetSize measurement failed: {exc}"


def resources(wall_ms, peak=None, peak_reason=None):
    reasons = {"peak_vram_bytes": "CPU-only run; dedicated VRAM not measured"}
    if peak is None:
        reasons["peak_ram_bytes"] = peak_reason or "Process peak working set not available"
    return Resources(device=f"{platform.platform()}; {platform.processor()}; CPU", wall_time_ms=wall_ms,
                     peak_ram_bytes=peak, peak_vram_bytes=None, missing_reasons=reasons)


def metric_summary(report):
    if report["status"] != "complete":
        return {"status": "failed", "failures": report["failures"]}
    return {mode: {"hit3": report[mode]["overall"]["hit_at_k"]["3"],
                   "recall3": report[mode]["overall"]["recall_at_k"]["3"],
                   "ndcg5": report[mode]["overall"]["ndcg_at_k"]["5"],
                   **{key: report[mode]["overall"][key] for key in ("no_match_false_acceptance", "matchable_false_rejection", "recommendation_coverage", "prediction_slots", "invalid_id_rate", "category_violation_rate", "duplicate_prediction_rate")}}
            for mode in ("raw", "validated")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--dataset", default="dataset-labeled-01.json")
    parser.add_argument("--protocol", type=Path, default=Path("configs/001c-development.json"))
    parser.add_argument("--encoder-config", type=Path, default=Path("configs/001c-encoder.json"))
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol_bytes = args.protocol.read_bytes()
    protocol = json.loads(protocol_bytes)
    dataset, audit = load_pilot(args.pilot, args.dataset, require_labels=True)
    require(all(q.partition == "development" for q in dataset.queries)
            and all(w.partition == "development" for w in dataset.wardrobes)
            and all(i.partition == "development" for i in dataset.images), "001C must not access final-test data")
    content = (args.pilot / args.dataset).read_bytes()
    digest = sha256(content).hexdigest()
    output = private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    lock = Path("uv.lock")
    lock_hash = sha256(lock.read_bytes()).hexdigest()
    inputs = retrieval_inputs(dataset)
    source_hashes = {p.as_posix(): sha256(p.read_bytes()).hexdigest() for base in ("stylematch", "configs")
                     for p in Path(base).rglob('*') if p.is_file() and p.suffix in (".py", ".json")}
    new_json(output / "registration.json", {"recorded_at": datetime.now(timezone(timedelta(hours=3))).isoformat(),
        "dataset_sha256": digest, "protocol_sha256": sha256(protocol_bytes).hexdigest(), "protocol": protocol,
        "dependency_lock_sha256": lock_hash, "source_sha256": source_hashes,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "scoring_started": False, "notes": "Source hashes bind any implementation not yet committed."})
    reports = {}

    def emit(name, rankings, metadata, resource, threshold=None, failures=None):
        run = Run(schema_version=1, run_id=name, dataset_id=dataset.dataset_id, dataset_sha256=digest,
                  status="failed" if failures else "complete", failures=failures or [], model=metadata,
                  threshold=threshold, threshold_selection_partition="development", resources=resource, rankings=rankings)
        new_json(output / f"{name}.run.json", run.model_dump())
        report = evaluate(dataset, run, tuple(protocol["ks"]), dataset_sha256=digest)
        new_json(output / f"{name}.report.json", report)
        reports[name] = report

    t0 = perf_counter_ns()
    category = category_rankings(inputs, protocol["seed"])
    elapsed = (perf_counter_ns() - t0) / 1e6
    peak, reason = process_peak_ram()
    baseline_meta = ModelMetadata(name="Category-only seeded uniform order", checkpoint="none",
        revision=f"seed-{protocol['seed']}", preprocessing="Category membership only; no image or label features",
        dependency_lock_sha256=lock_hash, notes="One reproducible uniform ordering; separate exact uniform-order expectation reported. Parent-process memory includes validation; timing covers ranking only.")
    emit("category", category, baseline_meta, resources(elapsed, peak, reason))
    chance = expected_category(dataset)
    new_json(output / "category-expectation.json", chance)
    attributes = audit["labeling"]["attributes"]
    fields = ("color", "pattern", "garment_type", "silhouette", "texture")
    observed = sum(row[field] not in ("unknown", "") for row in attributes for field in fields)
    assisted = {"status": "skipped", "observed_fields": observed, "reason": "No independent human attribute annotations exist; all 140 observable fields are unknown." if observed == 0 else "Observed fields require independently documented provenance and a pre-recorded attribute rule; no relevance-derived attributes are synthesized."}
    new_json(output / "assisted-rule-status.json", assisted)
    print("Category baseline recorded; starting encoder worker if a local checkpoint was supplied.", flush=True)
    encoder_failure = None
    measurement = None
    if args.weights:
        config = json.loads(args.encoder_config.read_bytes())
        model_meta = ModelMetadata(name=config["architecture"], checkpoint=config["checkpoint"], revision=config["revision"],
            preprocessing=json.dumps({key: config[key] for key in ("input_size", "interpolation", "crop_pct", "crop_mode", "mean", "std", "pooling")}, sort_keys=True),
            dependency_lock_sha256=lock_hash, notes="Local float32 CPU image features only; no filename/grade/no-match/note inputs. Wardrobe embeddings reused for both views.")
        worker = private_path(output / "encoder")
        worker.mkdir()
        new_json(worker / "inputs.json", {"image_root": str(args.pilot.resolve()), "inputs": inputs,
                 "protocol": protocol, "encoder": config, "weights": str(args.weights.resolve())})
        started = perf_counter_ns()
        result = subprocess.run([sys.executable, "-m", "stylematch.encoder_worker", "--spec", str(worker / "inputs.json"), "--output", str(worker)], text=True, capture_output=True)
        process_ms = (perf_counter_ns() - started) / 1e6
        (worker / "stdout.txt").write_text(result.stdout, encoding="utf-8")
        (worker / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            encoder_failure = {"returncode": result.returncode, "reason": result.stderr[-3000:], "fresh_process_wall_ms": process_ms}
            new_json(output / "encoder-failure.json", encoder_failure)
            emit("encoder-failed", [], model_meta, resources(process_ms), failures=["Encoder worker failed; inspect private encoder-failure.json and worker logs. No model metrics computed."])
        else:
            measurement = json.loads((worker / "measurements.json").read_bytes())
            measurement["fresh_process_wall_ms"] = process_ms
            new_json(output / "encoder-resource-summary.json", measurement)
            views = json.loads((worker / "rankings.json").read_bytes())
            resource = resources(process_ms, measurement["peak_ram_bytes"], measurement["peak_ram_missing_reason"])
            for view, rankings in views.items():
                emit(f"{view}-always", rankings, model_meta, resource)
            grid_settings = protocol["threshold_grid"]
            start, stop, step = (grid_settings[key] for key in ("start", "stop", "step"))
            grid = [round(start + i * step, 10) for i in range(round((stop - start) / step) + 1)]
            tuning = tune_shared_threshold(dataset, views, grid)
            new_json(output / "development-threshold.json", tuning)
            threshold = tuning["chosen"]["threshold"]
            for view, rankings in views.items():
                emit(f"{view}-tuned", apply_threshold(rankings, threshold), model_meta, resource, threshold)
            paired = []
            flags_path = args.pilot / "task-flags.json"
            flags = json.loads(flags_path.read_bytes()).get("flags_by_query", {}) if flags_path.exists() else {}
            for q in dataset.queries:
                row = {"query_id": q.query_id, "category": q.component_category,
                       "occlusion_note": flags.get(q.query_id), "runs": {}}
                for name, report in reports.items():
                    if report["status"] == "complete":
                        row["runs"][name] = next(r for r in report["per_query"] if r["query_id"] == q.query_id)
                paired.append(row)
            new_json(output / "paired-per-task.json", {"tasks": paired})
    summary = {"status": "baseline-only" if not args.weights or encoder_failure else "complete",
               "dataset_sha256": digest, "category_uniform_expectation": chance["matchable_mean"],
               "assisted_rule": assisted, "runs": {name: metric_summary(report) for name, report in reports.items()},
               "encoder_failure": encoder_failure, "resource_summary": measurement,
               "limitations": protocol["limits"], "human_effort": audit["labeling"]["human_effort"]}
    new_json(output / "comparison-summary.json", summary)
    require(sha256((args.pilot / args.dataset).read_bytes()).hexdigest() == digest, "Input dataset changed during comparison")
    print(json.dumps({"status": summary["status"], "private_output": str(output), "runs": list(reports)}, indent=2), flush=True)
    return 0 if not encoder_failure else 2


if __name__ == "__main__":
    raise SystemExit(main())
