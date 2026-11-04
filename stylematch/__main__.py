"""Read-only evaluator; stdout is a JSON report, stderr carries failures."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from .contracts import Dataset, Run
from .evaluation import evaluate
from .validation import verify_image_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("--image-root", type=Path, help="also verify local file existence and SHA-256")
    parser.add_argument("--k", type=int, nargs="+", default=[3, 5])
    args = parser.parse_args()
    try:
        content = args.dataset.read_bytes()
        dataset = Dataset.model_validate_json(content)
        run = Run.model_validate_json(args.run.read_bytes())
        if args.image_root is not None:
            verify_image_files(dataset, args.image_root)
        report = evaluate(dataset, run, tuple(args.k), dataset_sha256=sha256(content).hexdigest())
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0 if run.status == "complete" else 2
    except (ValueError, OSError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
