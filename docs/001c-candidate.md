# 001C encoder verification and selection

Selected before any encoder quality scores on 14 November 2026: the official
ONNX Model Zoo `mobilenetv2-12` checkpoint. Exact revision, byte count, SHA-256,
preprocessing and dependency versions are in
[`configs/001c-encoder.json`](../configs/001c-encoder.json).

| Property | Evidence / decision |
| --- | --- |
| Publisher and identity | [ONNX Model Zoo card](https://huggingface.co/onnxmodelzoo/mobilenetv2-12/blob/23a2a25eaaa6fcd61865414c8a1acf13dda66b7a/README.md), immutable revision `23a2a25eaaa6fcd61865414c8a1acf13dda66b7a`. FP32 MobileNetV2, opset 12, originally trained using MXNet on ImageNet-1k (documented). |
| Checkpoint storage | Publisher LFS metadata: 13,964,571 bytes, SHA-256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`. Downloader checks size/hash before loading; card is another 6,879 bytes. No external tensor files permitted. |
| Model license | Publisher card and [Model Zoo license](https://github.com/onnx/models/blob/main/LICENSE): Apache-2.0. Preserve notices/card locally; do not redistribute weights. Training-dataset access/redistribution rights are separate. |
| Code/dependencies | [ONNX Runtime 1.23.2](https://github.com/microsoft/onnxruntime/blob/v1.23.2/LICENSE) is MIT; [ONNX 1.20.1](https://github.com/onnx/onnx/blob/v1.20.1/LICENSE) is Apache-2.0; NumPy 2.5.4 BSD-3-Clause. Exact transitive versions and wheel hashes are locked. Windows CPython 3.12 AMD64 wheels are published; CPU runtime wheel 13,470,528 bytes, ONNX wheel 16,389,207 bytes, plus NumPy/transitives. Visual C++ runtime is a documented Windows prerequisite; successful local loading must verify availability. |
| Image preprocessing | [Publisher preprocessing code](https://github.com/onnx/models/blob/main/validated/vision/classification/imagenet_preprocess.py): RGB, shorter side 256 using PIL bilinear and rounded aspect ratio; centered 224 crop; float32 NCHW, scale to [0,1], mean [0.485,0.456,0.406], std [0.229,0.224,0.225]. No prompts/tokenizer or text metadata. |
| Feature extraction | Expose the graph's unique final GlobalAveragePool before the classifier, flatten 1280 features, L2 normalize. Extract only its ancestors without changing weights; validate graph and record the derived graph digest/output tensor. Synthetic smoke compares this output with the same pooled tensor exposed in the original graph. This feature choice is an explicit development adaptation, not a publisher retrieval-quality claim. |
| CPU/local execution | CPUExecutionProvider only, float32, batch 1, deterministic sequential execution, 2 intra-op / 1 inter-op threads. Historical `torch_threads` protocol keys retain their numeric meaning for ORT. Load local serialized graphs; no remote code, hub inference, custom operators or downloads during image processing. Python socket/DNS calls and non-Git child programs are blocked by an audit hook; no OS packet-capture/firewall claim is made. |
| Domain and unknowns | Generic ImageNet classification features are not trained against wardrobe relevance. Background, occlusion, tiny images and center cropping can dominate similarity. Center cropping can omit boundaries even within a human-selected crop. Laptop RAM/latency and clothing retrieval quality are unknown until locally measured. No physical-fit, sensitive-trait or final-study approval follows. |

Feasibility amendment before encoder scores: the initial small timm MobileNetV3
candidate was not adopted because its large PyTorch dependency download failed
from both official CPU and PyPI sources. Failed requests, source changes and
partial caches remain in the private ledger. The smaller ONNX deployment above
was chosen for installation feasibility, without viewing any encoder quality
results. Comparison pairs, metrics, abstention rule, candidate pools, retained
occlusion and resource measurement boundaries remain those pre-recorded in the
001C protocol. The initial category-only results were already available; no model
results informed this backend choice.

All primary URLs were checked on the decision date. Synthetic CPU loading,
provider/shape/feature-equivalence checks precede any pilot inference. Private
logs distinguish documented properties, local measurements, engineering
inferences and unknowns. Resource findings and all real task outputs remain
ignored and local. No fashion-specific model family or VLM is adopted.

Local synthetic verification passed with the pinned Windows packages:
CPUExecutionProvider, float32, output shape (1, 1280), final pooled tensor `464`.
The extracted graph matches the original pooled output exactly on the synthetic
probe (maximum absolute difference 0); its SHA-256 is
`bfa8f7bdd68ff12b519fe81f420ba370904b33b6580b01fb907bd05a3b6959cc`.
ONNX Runtime telemetry is explicitly disabled. Windows' local stdlib OS-version
probe is primed before the strict child-process hook; no pilot input is involved.
These are compatibility/feature-extraction checks, not retrieval-quality evidence.
