"""Download only the pinned public 001D weights/runtime. Never reads photos."""
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from time import monotonic
import urllib.request
import zipfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stylematch.preparation import new_json, private_path


def ranged_download(url, path, artifact):
    """Bounded publisher range requests for gateways that stall large responses."""
    parts = path.with_suffix(path.suffix + ".parts")
    parts.mkdir(exist_ok=True)
    chunk_size = 1024 * 1024
    jobs = list(range(0, artifact["bytes"], chunk_size))
    # A prior interrupted full response is a contiguous prefix. Reuse only
    # complete chunks, verify overlap with range parts, then hash the whole file.
    prefix = path.with_suffix(path.suffix + ".partial")
    if prefix.exists():
        with prefix.open("rb") as stream:
            for start in jobs:
                content = stream.read(chunk_size)
                if len(content) != chunk_size:
                    break
                part = parts / f"{start:012d}"
                if part.exists():
                    if part.read_bytes() != content:
                        raise ValueError("prior response prefix differs from publisher range")
                else:
                    with part.open("xb") as target:
                        target.write(content)
    started = monotonic()
    failed = threading.Event()

    def fetch(start):
        if failed.is_set():
            raise TimeoutError("earlier range failed; preserving completed parts")
        end = min(start + chunk_size, artifact["bytes"]) - 1
        part = parts / f"{start:012d}"
        if part.exists() and part.stat().st_size == end - start + 1:
            return
        for attempt in range(3):
            try:
                if monotonic() - started > 600 or failed.is_set():
                    raise TimeoutError("600-second ranged artifact transfer ceiling")
                # Distinct cache key prevents a cached range being reused for other bytes.
                request_url = url + f"?download=true&range={start}-{end}"
                request = urllib.request.Request(request_url, headers={"Range": f"bytes={start}-{end}",
                                                                      "Accept-Encoding": "identity"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{artifact['bytes']}":
                        raise ValueError("publisher did not honor exact range")
                    content = response.read(end - start + 2)
                if len(content) != end - start + 1:
                    raise ValueError("incomplete range")
                with part.open("xb") as stream:
                    stream.write(content)
                return
            except Exception:
                if attempt == 2:
                    failed.set()
                    raise
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, _ in enumerate(pool.map(fetch, jobs), 1):
            if index % 20 == 0 or index == len(jobs):
                print(f"{path.name}: verified range lengths {index}/{len(jobs)}", flush=True)
    assembled = path.with_suffix(path.suffix + ".assembled.partial")
    with assembled.open("xb") as stream:
        for start in jobs:
            stream.write((parts / f"{start:012d}").read_bytes())
    require_artifact(assembled, artifact)
    assembled.rename(path)


def main():
    config = json.loads((ROOT / "configs/001d-model.json").read_bytes())
    output = private_path(ROOT / "models/001d-smolvlm")
    output.mkdir(parents=True, exist_ok=True)
    runtime = config["runtime"]
    artifacts = [(f, f"https://huggingface.co/{config['repository']}/resolve/{config['revision']}/{f['name']}")
                 for f in config["files"]]
    artifacts.append(({**runtime, "name": runtime["archive"]},
                      f"https://github.com/{runtime['repository']}/releases/download/{runtime['tag']}/{runtime['archive']}"))
    if "--runtime-only" in sys.argv:
        artifacts = artifacts[-1:]
    attempt = output / f"download-{__import__('time').time_ns()}.json"
    ledger = {"config_sha256": sha256((ROOT / "configs/001d-model.json").read_bytes()).hexdigest(), "artifacts": []}
    try:
        for artifact, url in artifacts:
            path = output / artifact["name"]
            start = monotonic()
            entry = {"name": path.name, "url": url}
            ledger["artifacts"].append(entry)
            if not path.exists():
                if "--ranged" in sys.argv:
                    ranged_download(url, path, artifact)
                    entry["transfer"] = "1 MiB ranges, eight workers, three attempts, 20-second socket timeout, 600-second artifact ceiling"
                else:
                    partial = path.with_suffix(path.suffix + ".partial")
                    # Preserve failed partial downloads; never silently overwrite them.
                    with urllib.request.urlopen(url, timeout=45) as response, partial.open("xb") as stream:
                        while chunk := response.read(1024 * 1024):
                            stream.write(chunk)
                            if monotonic() - start > 600:
                                raise TimeoutError("600-second per-artifact download ceiling")
                    require_artifact(partial, artifact)
                    partial.rename(path)
            require_artifact(path, artifact)
            entry.update({"verified": True, "seconds": monotonic() - start, "bytes": path.stat().st_size})
            print(f"Verified {path.name}: {path.stat().st_size} bytes", flush=True)
        destination = output / "runtime"
        if not destination.exists():
            destination.mkdir()
            with zipfile.ZipFile(output / runtime["archive"]) as archive:
                for member in archive.infolist():
                    target = (destination / member.filename).resolve()
                    if not target.is_relative_to(destination.resolve()):
                        raise ValueError("unsafe runtime archive path")
                archive.extractall(destination)
        ledger["status"] = "verified"
    except (Exception, KeyboardInterrupt) as exc:
        if ledger["artifacts"]:
            ledger["artifacts"][-1].update(seconds=monotonic() - start,
                                          partial_bytes=sum(p.stat().st_size for p in output.rglob("*") if p.is_file()))
        ledger.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        print(ledger["error"], file=sys.stderr)
    finally:
        new_json(attempt, ledger)
    return 0 if ledger["status"] == "verified" else 2


def require_artifact(path, metadata):
    if path.stat().st_size != metadata["bytes"]:
        raise ValueError(f"size mismatch: {path.name}")
    with path.open("rb") as stream:
        value = __import__('hashlib').file_digest(stream, "sha256").hexdigest()
    if value != metadata["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}")


if __name__ == "__main__":
    raise SystemExit(main())
