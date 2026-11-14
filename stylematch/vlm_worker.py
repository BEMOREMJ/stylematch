"""Native Windows CPU VLM measurement; loopback only, no hub downloads."""
import argparse
import base64
import ctypes
from ctypes import wintypes
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import threading
from time import perf_counter, sleep
import urllib.error
import urllib.request
import zipfile

from PIL import Image

from .interpretation import digest, parse_prediction, score
from .preparation import contained, load_pilot, new_json, private_path
from .validation import require

ROOT = Path(__file__).resolve().parents[1]


class ProcessMemory(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
        "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in ("total", "available", "total_page",
        "available_page", "total_virtual", "available_virtual", "extended")]


def available_memory():
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("GlobalMemoryStatusEx failed")
    return memory.available


def process_memory(process):
    memory = ProcessMemory()
    memory.cb = ctypes.sizeof(memory)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(wintypes.HANDLE(int(process._handle)), ctypes.byref(memory), memory.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return memory.PeakWorkingSetSize


def png_payload(image, maximum):
    image = image.convert("RGB")
    image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def measure(payloads, output, protocol):
    require(sys.platform == "win32", "measurement implemented for Windows laptop only")
    config = json.loads((ROOT / "configs/001d-model.json").read_bytes())
    models = private_path(ROOT / "models/001d-smolvlm")
    from scripts.download_vlm import require_artifact
    for artifact in config["files"]:
        require_artifact(models / artifact["name"], artifact)
    runtime = config["runtime"]
    archive_path = models / runtime["archive"]
    require_artifact(archive_path, runtime)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if not member.is_dir():
                extracted = contained(models / "runtime", member.filename)
                require(sha256(extracted.read_bytes()).digest() == sha256(archive.read(member)).digest(),
                        "extracted runtime differs from pinned archive")
    executables = list((models / "runtime").rglob("llama-server.exe"))
    require(len(executables) == 1, "expected one extracted official server")
    # Choose a free loopback port; native bind failures remain in the server log.
    import socket
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    command = [str(executables[0]), "-m", str(models / config["files"][0]["name"]),
               "--mmproj", str(models / config["files"][1]["name"]), "--no-mmproj-offload",
               "-ngl", "0", "-t", str(protocol["threads"]), "-tb", str(protocol["threads"]),
               "-c", str(protocol["context_tokens"]), "--parallel", "1", "--host", "127.0.0.1",
               "--port", str(port), "--no-webui"]
    report = {"schema_version": 1, "measured": True, "process": "native llama-server only; Python excluded",
              "command": command, "available_before_bytes": available_memory(), "requests": [],
              "peak_working_set_bytes": 0, "failures": [], "disk_cache": "uncontrolled"}
    if report["available_before_bytes"] < protocol["minimum_available_memory_bytes"]:
        report["measured"] = False
        report["peak_working_set_bytes"] = None
        report["failures"].append("insufficient available RAM before load")
        new_json(output / "resources.json", report)
        return []
    stop = threading.Event()
    guard = []
    started = perf_counter()
    with (output / "server.log").open("xb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)

        def monitor():
            while not stop.is_set():
                if process.poll() is not None:
                    break
                try:
                    report["peak_working_set_bytes"] = max(report["peak_working_set_bytes"], process_memory(process))
                    free = available_memory()
                    report["minimum_available_bytes"] = min(report.get("minimum_available_bytes", free), free)
                    if report["peak_working_set_bytes"] > protocol["maximum_peak_working_set_bytes"]:
                        guard.append("peak working set exceeded development guard")
                    elif free < protocol["minimum_available_memory_bytes"]:
                        guard.append("available RAM fell below development floor")
                    if guard:
                        process.terminate()
                        break
                except OSError as exc:
                    guard.append(f"resource measurement failed: {exc}")
                    process.terminate()
                    break
                stop.wait(.02)

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        predictions = []
        try:
            while True:
                require(process.poll() is None, "server exited before ready")
                require(perf_counter() - started <= protocol["load_timeout_seconds"], "server load timeout")
                try:
                    with opener.open(endpoint + "/health", timeout=1) as response:
                        health = json.load(response)
                    if health.get("status") == "ok":
                        break
                except (OSError, ValueError):
                    pass
                sleep(.05)
            report["loading_seconds"] = perf_counter() - started
            sequence = [("cold", payloads[0]), ("warm", payloads[0])] + [("subsequent", p) for p in payloads[1:]]
            for index, (condition, payload) in enumerate(sequence):
                before = perf_counter()
                body = {"messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": payload["pixels"]}},
                    {"type": "text", "text": protocol["prompt"]}]}],
                    "temperature": protocol["temperature"], "seed": protocol["seed"],
                    "max_tokens": protocol["maximum_output_tokens"], "cache_prompt": False}
                request = urllib.request.Request(endpoint + "/v1/chat/completions", data=json.dumps(body).encode(),
                                                 headers={"Content-Type": "application/json"})
                try:
                    with opener.open(request, timeout=protocol["request_timeout_seconds"]) as response:
                        response_bytes = response.read()
                    (output / f"response-{index:03d}.json").write_bytes(response_bytes)
                    result = json.loads(response_bytes)
                    raw = result["choices"][0]["message"]["content"]
                    require(type(raw) is str, "no textual model response")
                    normalized, error = parse_prediction(raw)
                    record = {"id": payload["id"], "condition": condition, "raw": raw,
                              "normalized": normalized, "parse_error": error,
                              "finish_reason": result["choices"][0].get("finish_reason")}
                    new_json(output / f"prediction-{index:03d}.json", record)
                    report["requests"].append({"id": payload["id"], "condition": condition,
                                               "seconds": perf_counter() - before, "schema_valid": error is None})
                    if condition != "warm":
                        predictions.append(record)
                except Exception as exc:
                    if isinstance(exc, urllib.error.HTTPError):
                        (output / f"error-response-{index:03d}.bin").write_bytes(exc.read())
                    report["requests"].append({"id": payload["id"], "condition": condition,
                                               "seconds": perf_counter() - before, "failure": str(exc)})
                    raise
        except Exception as exc:
            report["failures"].append(f"{type(exc).__name__}: {exc}")
        finally:
            if process.poll() is None:
                try:
                    report["peak_working_set_bytes"] = max(report["peak_working_set_bytes"], process_memory(process))
                except OSError:
                    pass
                process.terminate()
            process.wait(timeout=10)
            stop.set()
            monitor_thread.join(timeout=2)
            report["failures"].extend(guard)
            report["exit_code"] = process.returncode
            report["terminated_by_supervisor"] = True
            report["total_seconds"] = perf_counter() - started
            new_json(output / "resources.json", report)
    return predictions


def run(pilot, review, reference_path, output, smoke=False):
    output = private_path(output)
    output.mkdir(parents=True, exist_ok=False)
    protocol_path = ROOT / "configs/001d-protocol.json"
    protocol = json.loads(protocol_path.read_bytes())
    new_json(output / "protocol.json", protocol)
    new_json(output / "binding.json", {"protocol_sha256": digest(protocol_path),
                                      "model_config_sha256": digest(ROOT / "configs/001d-model.json"),
                                      "mode": "synthetic-smoke" if smoke else "pilot"})
    preparation_started = perf_counter()
    if smoke:
        # Engineering compatibility image only; no real photos, labels or quality claims.
        pixels = Image.new("RGB", (256, 256), (40, 90, 170))
        payloads = [{"id": "synthetic-001", "pixels": png_payload(pixels, protocol["input_longest_edge"])}]
        reference = None
    else:
        require(pilot and review and reference_path, "preserved owner reference required before pilot inference")
        reference_path = private_path(reference_path)
        reference = json.loads(reference_path.read_bytes())
        require(reference["completed_by"] == "Mark", "owner reference not completed")
        require(reference["mapping_sha256"] == digest(review / "mapping.json"), "reference mapping changed")
        dataset, _ = load_pilot(pilot, "dataset-labeled-01.json", require_labels=True)
        require(reference["mapping"]["dataset_sha256"] == digest(pilot / "dataset-labeled-01.json"), "dataset changed")
        payloads = []
        for row in reference["mapping"]["items"]:
            path = contained(pilot, row["image_path"])
            require(digest(path) == row["sha256"], "pilot pixels changed")
            with Image.open(path) as image:
                payloads.append({"id": row["id"], "pixels": png_payload(image, protocol["input_longest_edge"])})
        # No reference values or source names cross the model request boundary.
        new_json(output / "reference-binding.json", {"reference_sha256": digest(reference_path)})
    new_json(output / "input-payloads.json", {"items": payloads})
    new_json(output / "input-preparation.json", {"measured_seconds": perf_counter() - preparation_started,
                                                "includes": "validation, RGB resize, PNG/base64 encoding and private payload persistence"})
    predictions = measure(payloads, output, protocol)
    new_json(output / "predictions.json", {"predictions": predictions})
    if reference:
        # Failed/unattempted cases remain in denominators as schema failures.
        by_id = {p["id"]: p for p in predictions}
        exhaustive = [by_id.get(r["id"], {"id": r["id"], "raw": "", "execution_failure": "no completed response"})
                      for r in reference["labels"]]
        new_json(output / "scores.json", score(reference, exhaustive))
        new_json(output / "description-review.json", {"status": "Mark spot-check pending", "items": [
            {"id": p["id"], "description": (p.get("normalized") or {}).get("description"),
             "unsupported_details": None, "reviewed_by": None} for p in exhaustive]})
        occluded = {r["id"] for r in reference["mapping"]["items"]
                    if r["kind"] == "crop" and r["entity"] in ("task-009", "task-010")}
        display = {"binding": digest(output / "description-review.json"), "items": [
            {"id": p["id"], "pixels": payload["pixels"], "occluded": p["id"] in occluded,
             "description": (p.get("normalized") or {}).get("description")}
            for p, payload in zip(exhaustive, payloads, strict=True)]}
        html = Path(__file__).with_name("description_review.html").read_text(encoding="utf-8")
        (output / "description-review.html").write_text(
            html.replace("/*PAYLOAD*/null", json.dumps(display).replace("<", "\\u003c")), encoding="utf-8")
    resources = json.loads((output / "resources.json").read_bytes())
    print(json.dumps({"output": str(output), "completed_responses": len(predictions),
                      "failures": resources["failures"], "loading_seconds": resources.get("loading_seconds"),
                      "peak_working_set_bytes": resources["peak_working_set_bytes"]}, indent=2))
    return 2 if resources["failures"] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--pilot", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args.pilot, args.review, args.reference, args.output, args.smoke)
    except (OSError, ValueError) as exc:
        if args.output.exists() and not (args.output / "blocker.json").exists():
            new_json(args.output / "blocker.json", {"error": f"{type(exc).__name__}: {exc}",
                                                   "measured_model_resources": False})
        print(f"VLM run failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
