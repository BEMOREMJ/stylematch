"""001E: fixed human-assisted rules over verified, saved development scores.

No image encoder or VLM is invoked. Ranking functions receive only opaque IDs,
human fields and original crop cosines; evaluation labels stay in the caller.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import statistics
import subprocess
from time import perf_counter_ns

from .benchmark import (apply_threshold, category_rankings, eligible, rank_vectors,
                        retrieval_inputs)
from .contracts import Run
from .evaluation import evaluate
from .interpretation import VOCAB, inputs as reference_views
from .preparation import load_pilot, new_json, private_path
from .validation import require

FIELDS = ("garment_type", "color", "pattern")
PARENTS = ("e3ec9c5cc75e4cd9ec1ff59390ff8aa29b837640",
           "3b165c5eb8b8d7a84e6c7c1472542e1e1f101253")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def snapshot(roots):
    return {str(p): digest(p) for root in roots for p in root.rglob("*") if p.is_file()}


def verify_ledger(files):
    for name, expected in files.items():
        require(digest(Path(name)) == expected, f"Preserved input changed: {name}")


def validate_reference(dataset, dataset_hash, reviewer, reference, mapping, source,
                       mapping_hash, source_hash):
    """Validate provenance and bijection before projecting only the three fields."""
    require(reference["mapping"] == mapping, "reference mapping mismatch")
    require(reference["bundle"] == reference["mapping_sha256"] == mapping_hash
            and source["bundle"] == mapping_hash, "reference bundle mismatch")
    require(reference["source_sha256"] == source_hash, "reference source mismatch")
    require(source["completed_by"] == reference["completed_by"] == "Mark",
            "owner completion required")
    require(source["labels"] == reference["labels"], "source labels changed")
    require(mapping["dataset_sha256"] == dataset_hash and mapping["reviewer_id"] == reviewer
            and mapping["vocabulary"] == VOCAB, "reference dataset/reviewer/vocabulary mismatch")
    expected = {}
    for row in reference_views(dataset):
        key = (row["kind"], tuple(row["entity"]) if row["kind"] == "wardrobe" else row["entity"])
        expected[key] = (row["image"]["path"], row["image"]["sha256"])
    labels = reference["labels"]
    rows = mapping["items"]
    require([r["id"] for r in rows] == [r["id"] for r in labels]
            and len({r["id"] for r in rows}) == len(rows), "reference ID membership/order mismatch")
    actual, projected = {}, {"wardrobe": {}, "crop": {}}
    for row, label in zip(rows, labels, strict=True):
        require(set(label) == {"id", *FIELDS}
                and all(label[f] in VOCAB[f] for f in FIELDS), "invalid human attribute")
        require(row["kind"] in projected, "invalid reference kind")
        entity = tuple(row["entity"]) if row["kind"] == "wardrobe" else row["entity"]
        key = row["kind"], entity
        require(key not in actual, "duplicate mapped entity")
        actual[key] = row["image_path"], row["sha256"]
        projected[row["kind"]][entity] = {f: label[f] for f in FIELDS}
    require(actual == expected, "reference entity/image mapping mismatch")
    return projected


def verify_pools(inputs, rankings):
    require(len(rankings) == len(inputs["queries"]), "saved task count mismatch")
    by_query = {r["query_id"]: r for r in rankings}
    require(set(by_query) == {q["query_id"] for q in inputs["queries"]}, "saved task IDs mismatch")
    for query in inputs["queries"]:
        keys = [(p["ref"]["wardrobe_id"], p["ref"]["item_id"])
                for p in by_query[query["query_id"]]["predictions"]]
        pool = [(g["ref"]["wardrobe_id"], g["ref"]["item_id"]) for g in eligible(inputs, query)]
        require(sorted(keys) == sorted(pool), "saved candidate pool mismatch")


def scoring_inputs(dataset, attributes, crop_rankings):
    """Explicit projection: no image path, grades, no-match flags or review notes."""
    by_query = {r["query_id"]: r for r in crop_rankings}
    return [{"query_id": q.query_id, "attributes": attributes["crop"][q.query_id],
             "candidates": [{"ref": p["ref"], "cosine": p["score"],
                             "attributes": attributes["wardrobe"][(p["ref"]["wardrobe_id"], p["ref"]["item_id"]) ]}
                            for p in by_query[q.query_id]["predictions"]]}
            for q in dataset.queries]


def agreement(query, candidate, omitted=None):
    return {f: int(f != omitted and query.get(f) not in (None, "", "unknown")
                   and candidate.get(f) not in (None, "", "unknown")
                   and query.get(f) == candidate.get(f)) for f in FIELDS}


def rank_assisted(tasks, *, hybrid=False, omitted=None):
    require(omitted is None or omitted in FIELDS, "unknown ablation field")
    rankings, contributions = [], []
    for task in tasks:
        predictions, evidence = [], []
        for candidate in task["candidates"]:
            c = candidate["cosine"]
            require(type(c) in (int, float) and isfinite(c) and -1 <= c <= 1,
                    "missing/invalid original embedding score")
            fields = agreement(task["attributes"], candidate["attributes"], omitted)
            a = sum(fields.values()) / 3
            e = (c + 1) / 2
            score = 0.5 * e + 0.5 * a if hybrid else a
            predictions.append({"ref": candidate["ref"], "score": score})
            evidence.append({"ref": candidate["ref"], "cosine": c,
                             "known_agreement": fields, "attribute_score": a,
                             "embedding_contribution": 0.5 * e if hybrid else 0,
                             "field_contributions": {f: v / (6 if hybrid else 3) for f, v in fields.items()},
                             "score": score})
        predictions.sort(key=lambda p: (-p["score"], p["ref"]["wardrobe_id"], p["ref"]["item_id"]))
        rankings.append({"query_id": task["query_id"], "predictions": predictions})
        contributions.append({"query_id": task["query_id"], "candidates": evidence})
    return rankings, contributions


def ordering_only(crop_rankings, reranked, threshold=0.60):
    accepted = {r["query_id"]: bool(r["predictions"]) for r in apply_threshold(crop_rankings, threshold)}
    require(set(accepted) == {r["query_id"] for r in reranked}, "accept mask task mismatch")
    return [{"query_id": r["query_id"], "predictions": r["predictions"] if accepted[r["query_id"]] else []}
            for r in reranked]


def paired(before, after):
    a = {r["query_id"]: r for r in before["per_query"]}
    details = []
    for row in after["per_query"]:
        old, new = a[row["query_id"]]["validated_metrics"], row["validated_metrics"]
        details.append({"query_id": row["query_id"], "category": new["category"],
                        "no_match": new["no_match"],
                        "ranking_changed": a[row["query_id"]]["validated"] != row["validated"],
                        "hit1_delta": new["hit"][1] - old["hit"][1] if not new["no_match"] else None,
                        "hit3_delta": new["hit"][3] - old["hit"][3] if not new["no_match"] else None,
                        "recall3_delta": new["recall"][3] - old["recall"][3] if not new["no_match"] else None,
                        "ndcg5_delta": new["ndcg"][5] - old["ndcg"][5] if not new["no_match"] else None})
    counts = {metric: {direction: [r["query_id"] for r in details if r[metric] is not None and
                                  (r[metric] > 1e-12 if direction == "gains" else r[metric] < -1e-12)]
                       for direction in ("gains", "losses")}
              for metric in ("hit1_delta", "hit3_delta", "recall3_delta", "ndcg5_delta")}
    return {"counts": counts, "tasks": details}


def timing(call, repetitions):
    samples = []
    for _ in range(repetitions):
        start = perf_counter_ns()
        call()
        samples.append((perf_counter_ns() - start) / 1e6)
    ordered = sorted(samples)
    return {"repetitions": repetitions, "scope": "all 13 tasks; in-memory score, sort and contribution construction only",
            "median_ms": statistics.median(samples), "p95_ms": ordered[(95 * len(ordered) + 99) // 100 - 1],
            "samples_ms": samples}


def verify_saved(dataset, pilot, saved):
    """Bind saved scores to accepted pixels, registered encoder and cached vectors."""
    import numpy as np  # local cache reading only; never imports an inference worker
    dataset_hash = digest(pilot / "dataset-labeled-01.json")
    registration = read(saved / "registration.json")
    require(registration["dataset_sha256"] == dataset_hash, "001C dataset binding mismatch")
    require(registration["protocol_sha256"] == digest(Path("configs/001c-development.json")), "001C protocol mismatch")
    require(registration["dependency_lock_sha256"] == digest(Path("uv.lock")), "001C lock mismatch")
    require(read(saved / "code-provenance.json")["commit"] == PARENTS[1], "001C delivery provenance mismatch")
    for name, expected in registration["source_sha256"].items():
        content = subprocess.check_output(["git", "show", f"{PARENTS[1]}:{name}"])
        lf = content.replace(b"\r\n", b"\n")
        require(expected in {sha256(content).hexdigest(), sha256(lf).hexdigest(),
                             sha256(lf.replace(b"\n", b"\r\n")).hexdigest()}, "001C committed source mismatch")
    inputs = retrieval_inputs(dataset)
    spec = read(saved / "encoder/inputs.json")
    require(spec["inputs"] == inputs and spec["protocol"] == registration["protocol"], "001C image/protocol binding mismatch")
    config = read(Path("configs/001c-encoder.json"))
    measured = read(saved / "encoder/measurements.json")
    require(spec["encoder"] == config and measured["weight_sha256"] == config["weight_sha256"], "001C encoder mismatch")
    with np.load(saved / "encoder/image-embeddings.npz", allow_pickle=False) as archive:
        require(set(archive.files) == set(inputs["images"]), "cached vector membership mismatch")
        features = {key: archive[key].tolist() for key in archive.files}
    require(all(len(v) == config["feature_dimension"] for v in features.values()), "cached vector dimension mismatch")
    runs = {name: Run.model_validate_json((saved / f"{name}.run.json").read_bytes())
            for name in ("category", "full-always", "crop-always")}
    worker_rankings = read(saved / "encoder/rankings.json")
    for name, run in runs.items():
        require(run.dataset_sha256 == dataset_hash and run.status == "complete" and run.threshold is None,
                "saved run binding/status mismatch")
        rankings = [r.model_dump() for r in run.rankings]
        verify_pools(inputs, rankings)
        if name == "category":
            require(rankings == category_rankings(inputs, 104729), "category baseline changed")
        else:
            view = name.split("-")[0]
            require(rankings == worker_rankings[view], "saved worker/run scores differ")
            recomputed = rank_vectors(inputs, features, view)
            for old, new in zip(rankings, recomputed, strict=True):
                require(old["query_id"] == new["query_id"], "cached task order mismatch")
                for a, b in zip(old["predictions"], new["predictions"], strict=True):
                    require(a["ref"] == b["ref"] and abs(a["score"] - b["score"]) <= 1e-6,
                            "cached vectors do not reproduce saved ranking/score")
    require(read(saved / "development-threshold.json")["chosen"]["threshold"] == 0.60, "001C threshold changed")
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=Path("data/pilot-02"))
    parser.add_argument("--saved", type=Path, default=Path("data/benchmarks-001c-01/comparison-01"))
    parser.add_argument("--reference-root", type=Path, default=Path("data/interpretation-001d-01"))
    parser.add_argument("--protocol", type=Path, default=Path("configs/001e-development.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter_ns()
    for parent in PARENTS:
        subprocess.run(["git", "merge-base", "--is-ancestor", parent, "HEAD"], check=True)
    protocol = read(args.protocol)
    require(protocol["fields"] == list(FIELDS) and protocol["attribute_denominator"] == 3
            and protocol["embedding_weight"] == protocol["attribute_weight"] == 0.5
            and protocol["embedding_threshold"] == 0.60 and protocol["ks"] == [1, 3, 5]
            and protocol["category_seed"] == 104729 and protocol["runtime_repetitions"] == 100,
            "unsupported protocol change: record a separate experiment")
    pilot, saved, refroot = (private_path(p) for p in (args.pilot, args.saved, args.reference_root))
    # Snapshot only the three required private input trees; never open final-test paths.
    preservation = snapshot([pilot, saved, refroot])
    verify_ledger(read(refroot / "preservation-before.json")["files"])
    dataset, audit = load_pilot(pilot, "dataset-labeled-01.json", require_labels=True)
    dataset_hash = digest(pilot / "dataset-labeled-01.json")
    require((len(dataset.garments), len(dataset.queries), sum(len(j.grades) for j in dataset.judgments),
             sum(j.no_match for j in dataset.judgments)) == (15, 13, 69, 3), "accepted pilot counts changed")
    require(all(sum(g.relevance >= 2 for g in j.grades) == (0 if j.no_match else 1)
                for j in dataset.judgments), "acceptable-item count changed")
    reference = read(refroot / "reference-01.json")
    mapping_path = refroot / "review-01/mapping.json"
    source_path = refroot / "review-01/001d-attribute-labels.json"
    attributes = validate_reference(dataset, dataset_hash, audit["plan"]["reviewer_id"], reference,
                                    read(mapping_path), read(source_path), digest(mapping_path), digest(source_path))
    runs = verify_saved(dataset, pilot, saved)
    output = private_path(args.output)
    require(all(not output.is_relative_to(root) and not root.is_relative_to(output)
                for root in (pilot, saved, refroot)), "output must be separate from preserved input trees")
    output.mkdir(parents=True, exist_ok=False)
    new_json(output / "preservation-before.json", {"files": preservation})
    new_json(output / "registration.json", {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scoring_started": False, "protocol": protocol, "protocol_sha256": digest(args.protocol),
        "dataset_sha256": dataset_hash, "reference_sha256": digest(refroot / "reference-01.json"),
        "source_sha256": {str(p): digest(p) for root in (Path("stylematch"), Path("configs"))
                          for p in root.rglob("*") if p.suffix in (".py", ".json")},
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "lock_sha256": digest(Path("uv.lock")), "verified_saved_vectors_scores": True,
        "preserved_files": len(preservation), "ancestry": list(PARENTS)})
    reports, ranked = {}, {}
    template = runs["crop-always"].model_dump()

    def emit(name, rankings):
        base = runs["full-always"].model_dump() if name == "full-cosine-060" else template
        metadata = {**base["model"], "name": name}
        if "assisted" in name:
            metadata["notes"] = protocol["assistance"] + " " + protocol["rule"] + " " + protocol["abstention"]
            if name == "attributes-assisted":
                metadata.update(checkpoint="none", revision="001e-rule-v1",
                                preprocessing="Human-confirmed type, main color and pattern; exact known agreement only")
                metadata["notes"] += " Attribute-only scores do not use cosine similarity."
        else:
            metadata["notes"] += " Original cosine >=0.60 mask; saved scores reused."
        payload = {**template, "run_id": name, "rankings": rankings, "threshold": None,
                   "resources": {"device": "Local CPU; saved scores reused", "wall_time_ms": None,
                       "peak_ram_bytes": None, "peak_vram_bytes": None, "missing_reasons": {
                           "wall_time_ms": "See separate repeated incremental timing; cached inference not rerun",
                           "peak_ram_bytes": "Incremental ranking memory not measured",
                           "peak_vram_bytes": "No GPU execution"}}, "model": metadata}
        if name in ("full-cosine-060", "crop-cosine-060"):
            payload["threshold"] = 0.60
        run = Run.model_validate(payload)
        report = evaluate(dataset, run, (1, 3, 5), dataset_sha256=dataset_hash)
        new_json(output / f"{name}.run.json", run.model_dump())
        new_json(output / f"{name}.report.json", report)
        reports[name], ranked[name] = report, rankings

    for name, run in runs.items():
        # Preserve original metadata on cached comparisons.
        report = evaluate(dataset, run, (1, 3, 5), dataset_sha256=dataset_hash)
        new_json(output / f"{name}.report.json", report)
        reports[name] = report
        ranked[name] = [r.model_dump() for r in run.rankings]
    tasks = scoring_inputs(dataset, attributes, ranked["crop-always"])
    new_json(output / "ranking-inputs.json", {"tasks": tasks})
    for name, hybrid, omitted in [("attributes-assisted", False, None), ("hybrid-assisted", True, None)] + [
            (f"hybrid-assisted-without-{f}", True, f) for f in FIELDS]:
        rankings, contributions = rank_assisted(tasks, hybrid=hybrid, omitted=omitted)
        verify_pools(retrieval_inputs(dataset), rankings)
        emit(name, rankings)
        new_json(output / f"{name}.contributions.json", {"tasks": contributions})
    emit("full-cosine-060", apply_threshold(ranked["full-always"], 0.60))
    emit("crop-cosine-060", apply_threshold(ranked["crop-always"], 0.60))
    emit("hybrid-assisted-crop-mask-ordering-only", ordering_only(ranked["crop-always"], ranked["hybrid-assisted"]))
    pairs = {f"{name}-vs-crop": paired(reports["crop-always"], report)
             for name, report in reports.items() if name != "crop-always"}
    pairs.update({f"hybrid-vs-without-{f}": paired(reports[f"hybrid-assisted-without-{f}"], reports["hybrid-assisted"])
                  for f in FIELDS})
    pairs["hybrid-ordering-only-vs-crop-060"] = paired(reports["crop-cosine-060"], reports["hybrid-assisted-crop-mask-ordering-only"])
    pairs["hybrid-vs-attributes"] = paired(reports["attributes-assisted"], reports["hybrid-assisted"])
    pairs["crop-vs-full"] = paired(reports["full-always"], reports["crop-always"])
    new_json(output / "paired-comparisons.json", pairs)
    flags = read(pilot / "task-flags.json")["flags_by_query"]
    pool_inputs = retrieval_inputs(dataset)
    subgroups = [{"query_id": q.query_id, "category": q.component_category,
                  "pool_size": len(eligible(pool_inputs, q.model_dump())), "occluded": q.query_id in flags,
                  "runs": {name: next(r["validated_metrics"] for r in report["per_query"] if r["query_id"] == q.query_id)
                           for name, report in reports.items()}}
                 for q in dataset.queries]
    new_json(output / "subgroups.json", {"tasks": subgroups})
    runtime = {name: timing(lambda h=hybrid: rank_assisted(tasks, hybrid=h), protocol["runtime_repetitions"])
               for name, hybrid in (("attributes-assisted", False), ("hybrid-assisted", True))}
    runtime["missing"] = {"human_annotation_effort": "Unknown; no measured annotation duration",
        "incremental_peak_ram": "Not measured", "end_to_end_latency": "Not measured; saved embeddings reused",
        "deployment_cost": "Unknown", "new_inference": "None; no model loaded or downloaded"}
    new_json(output / "runtime.json", runtime)
    new_json(output / "category-summaries.json", {name: report["validated"]["categories"]
                                                 for name, report in reports.items()})
    summary = {"assistance": protocol["assistance"], "ranking_metrics_denominator": 10,
               "runs": {name: {mode: report[mode]["overall"] for mode in ("raw", "validated")}
                        for name, report in reports.items()}, "limits": protocol["limits"],
               "human_annotation_seconds": None, "unknown_fields": {kind: {f: sum(v[f] == "unknown" for v in rows.values())
                   for f in FIELDS} for kind, rows in attributes.items()}}
    new_json(output / "comparison-summary.json", summary)
    verify_ledger(preservation)
    new_json(output / "preservation-after.json", {"unchanged": True, "files_checked": len(preservation),
        "orchestration_wall_ms": (perf_counter_ns() - started) / 1e6,
        "scope": "validation, vector verification, ranking, evaluation and private I/O; excludes process startup"})
    print(json.dumps({"status": "complete", "output": str(output), "preserved_files": len(preservation)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
