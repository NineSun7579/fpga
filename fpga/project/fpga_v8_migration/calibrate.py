"""Collect float tensor ranges and export exploratory INT8 weights.

This is a development calibration tool. It does not emit FPGA instructions,
replace SiLU with ReLU, or establish model accuracy on a validation dataset.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper
import onnxruntime as ort

from verify_reference import image_input


def affine_u8(low, high):
    low, high = min(float(low), 0.0), max(float(high), 0.0)
    scale = max((high - low) / 255, 1e-12)
    zero_point = int(np.clip(np.rint(-low / scale), 0, 255))
    return {"scale": scale, "zero_point": zero_point,
            "min": low, "max": high, "dtype": "uint8_affine"}


def calibrate(model_path, tasks_path, image_paths, output_dir):
    if not image_paths:
        raise ValueError("Provide representative images; empty calibration is invalid")
    model = onnx.load(str(model_path))
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    if tasks["source_sha256"] != hashlib.sha256(model_path.read_bytes()).hexdigest():
        raise ValueError("Task IR and calibration graph do not match")
    names = set(tasks["tensors"])
    names.update(task["preactivation"] for task in tasks["tasks"] if task["op"] == "Conv")
    names.discard("images")
    values = {value.name: value for value in (*model.graph.value_info, *model.graph.output)}
    augmented = deepcopy(model)
    del augmented.graph.output[:]
    output_names = sorted(names)
    for name in output_names:
        if name not in values:
            raise ValueError(f"Missing inferred shape for {name}")
        augmented.graph.output.append(deepcopy(values[name]))
    onnx.checker.check_model(augmented, full_check=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.log_severity_level = 3
    session = ort.InferenceSession(augmented.SerializeToString(), options, providers=["CPUExecutionProvider"])
    ranges = {}

    def observe(name, tensor):
        if not np.isfinite(tensor).all():
            raise ValueError(f"Nonfinite calibration tensor: {name}")
        low, high = float(tensor.min()), float(tensor.max())
        if name in ranges:
            ranges[name][0] = min(ranges[name][0], low)
            ranges[name][1] = max(ranges[name][1], high)
        else:
            ranges[name] = [low, high]

    samples = []
    for index, image in enumerate(image_paths):
        tensor, metadata = image_input(image)
        observe("images", tensor)
        results = session.run(output_names, {"images": tensor})
        for name, output in zip(output_names, results):
            observe(name, output)
        del results
        samples.append(metadata)
        print(f"CALIBRATED {index + 1}/{len(image_paths)} {image.name}", flush=True)
    quantization = {name: affine_u8(*bounds) for name, bounds in ranges.items()}
    # Pixel input is defined by RGB byte /255, independent of sampled dynamic range.
    quantization["images"] = {"scale": 1 / 255, "zero_point": 0, "min": 0, "max": 1,
                              "dtype": "uint8_affine"}
    for task in tasks["tasks"]:
        if task["op"] in {"ChannelView", "Upsample2x", "MaxPool"}:
            # Views and value-preserving spatial operations share their input
            # domain. A slice-specific min/max would silently require a copy
            # and requantization, invalidating the ChannelView lowering.
            quantization[task["output"]] = dict(quantization[task["inputs"][0]])
    weights = {value.name: numpy_helper.to_array(value) for value in model.graph.initializer}
    output_dir.mkdir(parents=True, exist_ok=True)
    weight_dir = output_dir / "int8_weights"
    weight_dir.mkdir(exist_ok=True)
    convolutions = []
    for task in tasks["tasks"]:
        if task["op"] != "Conv":
            continue
        weight = weights[task["weight"]].astype(np.float64)
        scale = np.maximum(np.abs(weight).max(axis=(1, 2, 3)) / 127, 1e-12)
        codes = np.clip(np.rint(weight / scale[:, None, None, None]), -127, 127).astype(np.int8)
        bias = weights[task["bias"]].astype(np.float64) if task["bias"] else np.zeros(weight.shape[0])
        stem = f"task_{task['id']:03d}"
        np.savez(weight_dir / f"{stem}.npz", weight=codes, weight_scale=scale, bias_float=bias)
        input_q = quantization[task["inputs"][0]]
        pre_q = quantization[task["preactivation"]]
        output_q = quantization[task["output"]]
        # These real multipliers are specifications, not the legacy Q16 encoding.
        # New compiler must verify scale precision, bias range, wrap, and padding.
        multiplier = input_q["scale"] * scale / pre_q["scale"]
        folded_bias = bias / pre_q["scale"] - input_q["zero_point"] * codes.astype(np.int64).sum(axis=(1, 2, 3)) * multiplier
        convolutions.append({"task_id": task["id"], "name": task["name"],
                             "weights": f"int8_weights/{stem}.npz",
                             "weight_scale": scale.tolist(), "input_quantization": input_q,
                             "preactivation_quantization": pre_q, "output_quantization": output_q,
                             "accumulator_to_preactivation_multiplier": multiplier.tolist(),
                             "bias_after_input_zero_point_correction": folded_bias.tolist(),
                             "bias_correction_scope": "all kernel positions; padding must use input zero-point",
                             "activation": task["activation"],
                             "hardware_encoding_verified": False})
    result = {"status": "exploratory_calibration_not_accuracy_or_hardware_acceptance",
              "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
              "sample_count": len(samples), "samples": samples,
              "preprocessing": "RGB bilinear letterbox640 fill114 float32 /255",
              "observed_ranges": ranges,
              "quantization": quantization, "convolutions": convolutions,
              "pending": ["independent validation data and output/detection accuracy",
                          "Concat/Add shared domains or explicit affine requantization",
                          "SiLU affine LUT error and signed-value preservation",
                          "legacy arithmetic encoding and accumulator/bias range validation",
                          "channel packing and real instruction export"]}
    (output_dir / "quantization.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    image_paths = sorted(path for path in args.images.iterdir()
                         if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".ppm"})
    result = calibrate(args.model, args.tasks, image_paths, args.out)
    print("CALIBRATION_COMPLETE", result["sample_count"], "samples", len(result["convolutions"]), "convolutions")
