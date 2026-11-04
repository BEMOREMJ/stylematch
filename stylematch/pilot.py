"""Local preparation/CSV review commands. No model or metric execution."""

import argparse
import json
from pathlib import Path
import sys

from .labeling import export_template, import_labels
from .preparation import PilotPlan, load_pilot, new_json, prepare, private_path, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="write a private, unapproved empty registration plan")
    init.add_argument("--output", type=Path, required=True)
    preparation = commands.add_parser("prepare", help="create a new ignored pilot directory from registered originals")
    preparation.add_argument("--plan", type=Path, required=True)
    preparation.add_argument("--originals", type=Path, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    template = commands.add_parser("label-template", help="create a new private CSV bundle")
    template.add_argument("--pilot", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)
    template.add_argument("--seed", type=int, required=True)
    importer = commands.add_parser("import-labels", help="import resolved exhaustive human labels")
    importer.add_argument("--pilot", type=Path, required=True)
    importer.add_argument("--labels", type=Path, required=True)
    importer.add_argument("--output", required=True, help="new JSON filename inside pilot directory")
    check = commands.add_parser("check", help="verify manifests, PNG decoding, dimensions, hashes and human labels")
    check.add_argument("--pilot", type=Path, required=True)
    check.add_argument("--dataset", default="dataset.json")
    check.add_argument("--allow-unlabeled", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            new_json(args.output, {
                "schema_version": 1, "dataset_id": "development-pilot-01", "synthetic": False,
                "wardrobe": {"wardrobe_id": "wardrobe-01", "person_id": "owner-01", "partition": "development"},
                "reviewer_id": "reviewer-01",
                "handling": {"approved": False, "decision_reference": None, "amendment": ""},
                "sources": [], "garments": [], "crops": [], "queries": [], "exclusions": [],
            })
            result = {"status": "empty plan created; handling, provenance, registrations and real data pending"}
        elif args.command == "prepare":
            plan = PilotPlan.model_validate_json(private_path(args.plan).read_bytes())
            dataset = prepare(plan, args.originals, args.output)
            result = summary(dataset, [e.model_dump() for e in plan.exclusions])
        elif args.command == "label-template":
            result = export_template(args.pilot, args.output, args.seed)
        elif args.command == "import-labels":
            dataset = import_labels(args.pilot, args.labels, args.output)
            _, audit = load_pilot(args.pilot, args.output, require_labels=True)
            result = summary(dataset, audit["plan"]["exclusions"])
        else:
            dataset, audit = load_pilot(args.pilot, args.dataset, require_labels=not args.allow_unlabeled)
            result = summary(dataset, audit["plan"]["exclusions"])
        if args.command in ("import-labels", "check") and "labeling" in audit:
            result["human_effort"] = audit["labeling"]["human_effort"]
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError) as exc:
        print(f"pilot command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
