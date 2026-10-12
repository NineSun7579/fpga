"""Check static specialization parity and save named CPU reference tensors."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

from raw_dfl import decode


def image_input(path):
    image = Image.open(path).convert("RGB")
    width, height = image.size
    ratio = min(640 / width, 640 / height)
    resized = image.resize((round(width * ratio), round(height * ratio)), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (640, 640), (114, 114, 114))
    pad = ((640 - resized.width) // 2, (640 - resized.height) // 2)
    canvas.paste(resized, pad)
    pixels = np.asarray(canvas, dtype=np.uint8)
    tensor = pixels.astype(np.float32).transpose(2, 0, 1)[None] / np.float32(255)
    return tensor, {"source": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source_size": [width, height], "ratio": ratio, "pad": list(pad)}


def verify(original, specialized, output_dir, images):
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.intra_op_num_threads = 4
    options.log_severity_level = 3
    original_session = ort.InferenceSession(str(original), options, providers=["CPUExecutionProvider"])
    specialized_session = ort.InferenceSession(str(specialized), options, providers=["CPUExecutionProvider"])
    expected = [(v.name, v.shape, v.type) for v in original_session.get_outputs()]
    if expected != [(v.name, v.shape, v.type) for v in specialized_session.get_outputs()]:
        raise ValueError("Specialization changed the output contract")
    names = [x[0] for x in expected]
    ramp = np.linspace(0, 1, 640, dtype=np.float32)[None, None, None, :]
    cases = [("zero", np.zeros((1, 3, 640, 640), np.float32), {"kind": "synthetic_zero"}),
             ("ramp", np.broadcast_to(ramp, (1, 3, 640, 640)).copy(), {"kind": "synthetic_ramp"})]
    for index, path in enumerate(images):
        tensor, metadata = image_input(path)
        cases.append((f"image_{index:02d}", tensor, metadata))
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"scope": "CPU float ONNX parity only; no FPGA or INT8 accuracy claim",
              "original_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
              "specialized_sha256": hashlib.sha256(specialized.read_bytes()).hexdigest(),
              "preprocessing": "RGB; bilinear letterbox to 640; fill 114; NCHW float32 /255",
              "cases": []}
    for label, tensor, metadata in cases:
        left = original_session.run(names, {"images": tensor})
        right = specialized_session.run(names, {"images": tensor})
        errors = {}
        for name, reference, candidate in zip(names, left, right):
            if not np.isfinite(reference).all() or not np.isfinite(candidate).all():
                raise ValueError(f"Nonfinite output: {label}/{name}")
            np.testing.assert_allclose(candidate, reference, rtol=1e-6, atol=1e-6,
                                       err_msg=f"Specialization mismatch: {label}/{name}")
            errors[name] = float(np.max(np.abs(candidate - reference)))
        tensors = dict(zip(names, left))
        detections = decode(tensors)
        np.savez_compressed(output_dir / f"{label}.npz", images=tensor, **tensors)
        row = {"case": label, "input": metadata, "max_absolute_error": errors,
               "detection_count": len(detections), "detections": detections.tolist()}
        report["cases"].append(row)
        print(label, "PARITY_PASS", "max_abs", max(errors.values()), "detections", len(detections))
    (output_dir / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("specialized", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", type=Path, action="append", default=[])
    args = parser.parse_args()
    verify(args.model, args.specialized, args.out, args.image)
