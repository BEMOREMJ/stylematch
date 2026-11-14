"""Offline CPU feature extraction. Receives pixels/identities, never judgments."""
import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import sys
from time import perf_counter_ns


def deny_network():
    """Reject Python network I/O and child programs except read-only local Git."""
    # Windows' stdlib platform probe may use `cmd /c ver`. Resolve that local
    # OS identity before the strict child-process hook; ORT later reuses it.
    import platform
    platform.uname()
    os.environ.update(HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    def audit(event, arguments):
        if event == "subprocess.Popen":
            command = arguments[1]
            if isinstance(command, str):
                import shlex
                command = shlex.split(command, posix=False)
            if (isinstance(command, (list, tuple)) and len(command) > 1
                    and Path(str(command[0]).strip('"')).name.lower() in ("git", "git.exe")
                    and command[1] in ("check-ignore", "ls-files")):
                return
        if event in ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"):
            raise RuntimeError(f"Offline encoder forbids {event}")
    sys.addaudithook(audit)


def load_encoder(config, weights, protocol):
    started = perf_counter_ns()
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnx.utils import Extractor
    from PIL import Image
    versions = {name: importlib.metadata.version(name) for name in config["dependencies"]}
    if versions != config["dependencies"]:
        raise ValueError(f"Installed dependencies do not match adoption config: {versions}")
    ort.disable_telemetry_events()
    weight_content = weights.read_bytes()
    if len(weight_content) != config["weight_bytes"] or sha256(weight_content).hexdigest() != config["weight_sha256"]:
        raise ValueError("Local weight size/hash mismatch")
    original = onnx.load_model_from_string(weight_content)
    if any(tensor.data_location == onnx.TensorProto.EXTERNAL for tensor in original.graph.initializer):
        raise ValueError("External ONNX tensor files are not authorized by this checkpoint")
    onnx.checker.check_model(original)
    inferred = onnx.shape_inference.infer_shapes(original)
    pools = [node for node in inferred.graph.node if node.op_type == "GlobalAveragePool"]
    if len(pools) != 1:
        raise ValueError("Expected one final GlobalAveragePool for this verified architecture")
    feature_name = pools[0].output[0]
    input_name = inferred.graph.input[0].name
    extracted = Extractor(inferred).extract_model([input_name], [feature_name])
    onnx.checker.check_model(extracted)
    graph_bytes = extracted.SerializeToString()
    options = ort.SessionOptions()
    options.intra_op_num_threads = protocol["torch_threads"]
    options.inter_op_num_threads = protocol["torch_interop_threads"]
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.use_deterministic_compute = True
    session = ort.InferenceSession(graph_bytes, sess_options=options, providers=["CPUExecutionProvider"])
    if session.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("Unexpected execution provider")
    def transform(image):
        width, height = image.size
        ratio = 256.0 / min(width, height)
        size = (int(round(ratio * width)), 256) if width > height else (256, int(round(ratio * height)))
        resized = image.convert("RGB").resize(size, Image.Resampling.BILINEAR)
        left, top = size[0] // 2 - 112, size[1] // 2 - 112
        pixels = np.asarray(resized.crop((left, top, left + 224, top + 224)), dtype=np.float32).transpose(2, 0, 1)
        mean = np.asarray(config["mean"])[:, None, None]
        std = np.asarray(config["std"])[:, None, None]
        return np.ascontiguousarray(((pixels / 255.0 - mean) / std).astype(np.float32)[None])
    def model(tensor):
        return session.run([feature_name], {input_name: tensor})[0].reshape(1, -1)
    equivalence = None
    if protocol.get("verify_extraction_synthetic"):
        from copy import deepcopy
        augmented = deepcopy(original)
        augmented.graph.output.append(extracted.graph.output[0])
        reference = ort.InferenceSession(augmented.SerializeToString(), sess_options=options, providers=["CPUExecutionProvider"])
        tensor = transform(Image.new("RGB", (256, 256), (128, 96, 64)))
        expected = reference.run([feature_name], {input_name: tensor})[0].reshape(1, -1)
        actual = model(tensor)
        if not np.allclose(expected, actual, atol=1e-6, rtol=1e-6):
            raise ValueError("Extracted feature graph differs from original pooled output")
        equivalence = {"passed": True, "max_absolute_difference": float(np.max(np.abs(expected - actual)))}
    return np, model, transform, {"imports_and_model_load_ms": (perf_counter_ns() - started) / 1e6,
        "versions": versions, "preprocessing_repr": "Publisher PIL bilinear shorter-side 256 (round aspect), centered 224 crop; RGB [0,1]; ImageNet channel normalization; float32 NCHW",
        "feature_tensor": feature_name, "extracted_graph_sha256": sha256(graph_bytes).hexdigest(),
        "synthetic_original_pool_equivalence": equivalence,
        "extracted_graph_bytes": len(graph_bytes), "providers": session.get_providers(),
        "onnxruntime_telemetry_disabled": True,
        "device": "cpu", "dtype": "float32", "batch_size": 1, "intraop_threads": options.intra_op_num_threads,
        "interop_threads": options.inter_op_num_threads, "weight_bytes": len(weight_content),
        "weight_sha256": config["weight_sha256"], "network": "Python outbound socket/DNS events forbidden; child launch restricted to local read-only Git path checks. No hub loaders or remote code used."}


def timing_summary(values):
    return {"count": len(values), "mean_ms": statistics.mean(values), "median_ms": statistics.median(values),
            "p95_ms": sorted(values)[max(0, __import__('math').ceil(0.95 * len(values)) - 1)],
            "min_ms": min(values), "max_ms": max(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--encoder-config", type=Path, default=Path("configs/001c-encoder.json"))
    parser.add_argument("--weights", type=Path)
    args = parser.parse_args()
    if args.smoke:
        config = json.loads(args.encoder_config.read_bytes())
        protocol = json.loads(Path("configs/001c-development.json").read_bytes())
        protocol["verify_extraction_synthetic"] = True
        weights = args.weights.resolve(strict=True)
    else:
        spec = json.loads(args.spec.read_bytes())
        config, protocol, weights = spec["encoder"], spec["protocol"], Path(spec["weights"])
    deny_network()
    np, model, transform, measurement = load_encoder(config, weights, protocol)
    from PIL import Image
    from .benchmark import garment_vectors, process_peak_ram, rank_query, rank_vectors
    from .preparation import contained, new_json, private_path
    output = private_path(args.output)
    if args.smoke:
        features = model(transform(Image.new("RGB", (256, 256), (128, 96, 64))))
        if tuple(features.shape) != (1, config["feature_dimension"]) or not np.isfinite(features).all():
            raise ValueError("Synthetic CPU feature compatibility check failed")
        measurement["synthetic_feature_shape"] = list(features.shape)
        measurement["peak_ram_bytes"], measurement["peak_ram_missing_reason"] = process_peak_ram()
        output.mkdir(parents=True, exist_ok=False)
        new_json(output / "smoke.json", measurement)
        print(json.dumps(measurement, indent=2))
        return 0

    inputs = spec["inputs"]
    image_root = Path(spec["image_root"])
    features, timings = {}, []
    image_order = list(dict.fromkeys([image for garment in inputs["garments"] for image in garment["image_ids"]]
                                   + [image for query in inputs["queries"] for image in (query["image_id"], query["crop_image_id"])]))
    if any(image is None for image in image_order):
        raise ValueError("Missing confirmed crop")

    def encode(image_id):
        image_record = inputs["images"][image_id]
        path = contained(image_root, image_record["path"])
        started = perf_counter_ns()
        with Image.open(path) as image:
            tensor = transform(image.convert("RGB"))
        vector = model(tensor)
        vector = vector / np.linalg.norm(vector, axis=-1, keepdims=True)
        if tuple(vector.shape) != (1, config["feature_dimension"]) or not np.isfinite(vector).all():
            raise ValueError("Unexpected/nonfinite encoder features")
        result = vector[0].tolist()
        return result, (perf_counter_ns() - started) / 1e6

    # Hash verification is outside transform/encode timings and before inference.
    for image in image_order:
        record = inputs["images"][image]
        if sha256(contained(image_root, record["path"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Prepared image changed before embedding")
    wardrobe_ids = {image for garment in inputs["garments"] for image in garment["image_ids"]}
    cache_started = perf_counter_ns()
    for index, image in enumerate(image_order):
        features[image], milliseconds = encode(image)
        timings.append({"image_id": image, "cold": index == 0, "wardrobe": image in wardrobe_ids, "ms": milliseconds})
        if index + 1 == len(wardrobe_ids):
            measurement["wardrobe_image_cache_wall_ms"] = (perf_counter_ns() - cache_started) / 1e6
    measurement["unique_embedding_cache_wall_ms"] = (perf_counter_ns() - cache_started) / 1e6
    measurement["cold_first_image_ms"] = timings[0]["ms"]
    measurement["cold_note"] = "First inference in this fresh process; OS filesystem cache not controlled. Input hashes were checked before timing; not a disk-cold claim."
    measurement["unique_image_count"] = len(image_order)
    measurement["wardrobe_image_count"] = len(wardrobe_ids)
    measurement["image_embedding_timings"] = timings
    wardrobe = garment_vectors(inputs, features)
    ranking_started = perf_counter_ns()
    rankings = {view: rank_vectors(inputs, features, view) for view in ("full", "crop")}
    measurement["cached_pair_ranking_ms"] = (perf_counter_ns() - ranking_started) / 1e6
    np.savez(output / "image-embeddings.npz", **{key: np.asarray(value, dtype=np.float32) for key, value in features.items()})
    np.save(output / "wardrobe-embeddings.npy", np.asarray(list(wardrobe.values()), dtype=np.float32))
    new_json(output / "wardrobe-embedding-keys.json", {"keys": list(wardrobe)})
    new_json(output / "rankings.json", rankings)
    warm = []
    for repeat in range(protocol["warm_repetitions"]):
        for query in inputs["queries"]:
            for view in ("full", "crop"):
                image = query["image_id"] if view == "full" else query["crop_image_id"]
                started = perf_counter_ns()
                vector, embedding_ms = encode(image)
                rank_query(inputs, query, vector, wardrobe)
                elapsed = (perf_counter_ns() - started) / 1e6
                # Repeated extraction must reproduce the cached feature vector.
                if not np.allclose(vector, features[image], atol=1e-6, rtol=1e-6):
                    raise ValueError("Repeated CPU embeddings changed beyond 1e-6 tolerance")
                warm.append({"query_id": query["query_id"], "view": view, "repeat": repeat + 1,
                             "transform_encode_ms": embedding_ms, "decode_transform_encode_score_ms": elapsed})
    measurement["warm_timings"] = warm
    measurement["warm_by_view"] = {view: timing_summary([row["decode_transform_encode_score_ms"] for row in warm if row["view"] == view]) for view in ("full", "crop")}
    measurement["peak_ram_bytes"], measurement["peak_ram_missing_reason"] = process_peak_ram()
    measurement["peak_ram_method"] = "Windows GetProcessMemoryInfo PeakWorkingSetSize: lifetime process peak resident bytes, including imports/model/cache/warm runs. Not incremental model RAM."
    measurement["peak_vram_bytes"] = None
    measurement["peak_vram_missing_reason"] = "CPU-only execution; dedicated VRAM not measured"
    measurement["embedding_storage_bytes"] = sum(path.stat().st_size for path in output.glob('*embeddings.np*'))
    new_json(output / "measurements.json", measurement)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
