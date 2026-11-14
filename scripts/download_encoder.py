"""Download only the public pinned encoder; never reads pilot images/labels."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stylematch.preparation import private_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/001c-encoder.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_bytes())
    output = private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    base = f"https://huggingface.co/{config['checkpoint']}/resolve/{config['revision']}/"
    for name in config["publisher_files"]:
        with urlopen(base + name, timeout=120) as response:
            content = response.read()
        if name == config["filename"]:
            if len(content) != config["weight_bytes"] or sha256(content).hexdigest() != config["weight_sha256"]:
                raise ValueError("Pinned weight size/hash mismatch; not adopted")
        with (output / name).open("xb") as stream:
            stream.write(content)
        print(f"Downloaded verified public file {name}: {len(content)} bytes", flush=True)
    (output / "verified.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
