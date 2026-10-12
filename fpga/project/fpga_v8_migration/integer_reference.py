"""Execute candidate Q16 task arithmetic using exact CPU integer matrix products.

This verifies numerical assets before modifying RTL. It deliberately has no
legacy DMA, RAM truncation, instruction execution or clock behavior model.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from onnx import TensorProto, helper

from feature_layout import pack_c16
from raw_dfl import decode
from verify_reference import image_input


def saturate_q16(value):
    value = np.asarray(value, dtype=np.int64)
    return np.clip((value + 32768) // 65536, 0, 255).astype(np.uint8)


def requantize(codes, source, destination, multiplier):
    centered = codes.astype(np.int64) - source["zero_point"]
    return saturate_q16(centered * multiplier + destination["zero_point"] * 65536)


def integer_matmul_session():
    graph = helper.make_graph([helper.make_node("MatMulInteger", ["a", "b"], ["y"])], "exact_integer_mac",
                               [helper.make_tensor_value_info("a", TensorProto.UINT8, [None, None]),
                                helper.make_tensor_value_info("b", TensorProto.INT8, [None, None])],
                               [helper.make_tensor_value_info("y", TensorProto.INT32, [None, None])])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.intra_op_num_threads = 4
    return ort.InferenceSession(model.SerializeToString(), options, providers=["CPUExecutionProvider"])


def convolution(codes, weights, strides, pads, zero_point, session):
    if codes.dtype != np.uint8 or weights.dtype != np.int8 or codes.ndim != 4 or codes.shape[0] != 1:
        raise ValueError("Expected batch-1 uint8 feature and signed int8 weight")
    if weights.shape[1] != codes.shape[1]:
        raise ValueError("Convolution input channels disagree")
    bound = 255 * np.abs(weights.astype(np.int64)).sum(axis=(1, 2, 3))
    if (bound > 2147483647).any():
        raise ValueError("MatMulInteger accumulator could overflow int32")
    padded = np.pad(codes[0], ((0, 0), (pads[0], pads[2]), (pads[1], pads[3])), constant_values=zero_point)
    kh, kw = weights.shape[2:]
    patches = np.lib.stride_tricks.sliding_window_view(padded, (kh, kw), axis=(1, 2))
    patches = patches[:, ::strides[0], ::strides[1]]
    height, width = patches.shape[1:3]
    matrix = patches.transpose(1, 2, 0, 3, 4).reshape(height * width, -1).copy()
    kernel = weights.reshape(weights.shape[0], -1).T.copy()
    result = session.run(["y"], {"a": matrix, "b": kernel})[0]
    return result.T.reshape(1, weights.shape[0], height, width).astype(np.int64)


def maxpool5(codes):
    padded = np.pad(codes, ((0, 0), (0, 0), (2, 2), (2, 2)), constant_values=0)
    patches = np.lib.stride_tricks.sliding_window_view(padded, (5, 5), axis=(2, 3))
    return patches.max(axis=(-2, -1))


def box_iou(left, right):
    intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0, min(left[3], right[3]) - max(left[1], right[1]))
    a = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    b = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    return intersection / max(a + b - intersection, 1e-12)


def detection_matches(reference, candidate, minimum_iou=0.5):
    if not 0 <= minimum_iou <= 1:
        raise ValueError("Match IoU threshold must be between 0 and 1")
    candidates = sorted(((box_iou(left, right), i, j) for i, left in enumerate(reference)
                         for j, right in enumerate(candidate) if int(left[5]) == int(right[5])), reverse=True)
    used_left, used_right, matches = set(), set(), []
    for iou, i, j in candidates:
        if iou < minimum_iou:
            continue
        if i in used_left or j in used_right:
            continue
        used_left.add(i)
        used_right.add(j)
        matches.append({"float_index": i, "integer_index": j, "iou": iou,
                        "max_coordinate_error": float(np.max(np.abs(reference[i, :4] - candidate[j, :4]))),
                        "confidence_error": float(abs(reference[i, 4] - candidate[j, 4]))})
    return {"minimum_match_iou": minimum_iou,
            "matches": matches, "unmatched_float": sorted(set(range(len(reference))) - used_left),
            "unmatched_integer": sorted(set(range(len(candidate))) - used_right)}


def run(tasks_path, numeric_path, image, output_dir, model_path=None, save_features=False, quiet=False):
    ir = json.loads(tasks_path.read_text(encoding="utf-8"))
    numeric = json.loads(numeric_path.read_text(encoding="utf-8"))
    if numeric["tasks_sha256"] != hashlib.sha256(tasks_path.read_bytes()).hexdigest():
        raise ValueError("Integer assets and task IR hashes disagree")
    if model_path and numeric["model_sha256"] != hashlib.sha256(model_path.read_bytes()).hexdigest():
        raise ValueError("Float reference and integer assets model hashes disagree")
    domains = numeric["quantization"]
    tensor, metadata = image_input(image)
    values = {"images": np.clip(np.floor(tensor.astype(np.float64) * 255 + 0.5), 0, 255).astype(np.uint8)}
    operations = {operation["task_id"]: operation for operation in numeric["operations"]}
    session = integer_matmul_session()
    trace = []
    output_dir.mkdir(parents=True, exist_ok=True)
    if save_features:
        (output_dir / "features").mkdir(exist_ok=True)
    for task in ir["tasks"]:
        operation = operations[task["id"]]
        args = [values[name] for name in task["inputs"]]
        output_q = domains[task["output"]]
        extra = {}
        if task["op"] == "Conv":
            with np.load(numeric_path.parent / operation["asset"], allow_pickle=False) as asset:
                weights = asset["weight"]
                accum = convolution(args[0], weights, task["strides"], task["pads"],
                                    domains[task["inputs"][0]]["zero_point"], session)
                raw_q16 = (accum * asset["multiplier_q16"][None, :, None, None]
                           + asset["folded_bias_q16"][None, :, None, None]
                           + operation["preactivation_quantization"]["zero_point"] * 65536)
                preactivation = saturate_q16(raw_q16)
                output = asset["activation_lut"][preactivation]
                extra = {"raw_accumulator_min": int(accum.min()), "raw_accumulator_max": int(accum.max()),
                         "preactivation_low_saturation_elements": int(np.count_nonzero(raw_q16 + 32768 < 0)),
                         "preactivation_high_saturation_elements": int(np.count_nonzero(raw_q16 + 32768 >= 256 * 65536))}
        elif task["op"] == "ChannelView":
            output = args[0][:, task["channel_start"]:task["channel_start"] + task["channel_count"]]
        elif task["op"] == "Upsample2x":
            output = np.repeat(np.repeat(args[0], 2, axis=2), 2, axis=3)
        elif task["op"] == "MaxPool":
            output = maxpool5(args[0])
        elif task["op"] == "Concat":
            converted = [requantize(codes, domains[name], output_q, multiplier)
                         for codes, name, multiplier in zip(args, task["inputs"], operation["input_to_output_multiplier_q16"])]
            output = np.concatenate(converted, axis=1)
        elif task["op"] == "Add":
            total = output_q["zero_point"] * 65536
            for codes, name, multiplier in zip(args, task["inputs"], operation["input_to_output_multiplier_q16"]):
                total = total + (codes.astype(np.int64) - domains[name]["zero_point"]) * multiplier
            output = saturate_q16(total)
        else:
            raise ValueError(f"No integer execution rule for {task['op']}")
        if list(output.shape) != task["output_shape"] or output.dtype != np.uint8:
            raise ValueError(f"Integer output contract failed: {task['name']}")
        values[task["output"]] = output
        trace.append({"task_id": task["id"], "name": task["name"], "op": task["op"],
                      "code_min": int(output.min()), "code_max": int(output.max()),
                      "sha256_nchw_u8": hashlib.sha256(output.tobytes()).hexdigest(), **extra})
        if save_features:
            (output_dir / "features" / f"task_{task['id']:03d}.c16.bin").write_bytes(pack_c16(output, output_q["zero_point"]))
        if not quiet:
            print("INTEGER_TASK", task["id"], task["op"], output.shape, flush=True)
    dequantized = {name: (values[name].astype(np.float32) - domains[name]["zero_point"]) * domains[name]["scale"]
                   for name in ir["outputs"]}
    np.savez(output_dir / "heads_u8.npz", **{name: values[name] for name in ir["outputs"]})
    np.savez(output_dir / "heads_float.npz", **dequantized)
    detections = decode(dequantized)
    report = {"scope": "candidate Q16 CPU arithmetic; not legacy RTL/board acceptance", "image": metadata,
              "weight_domain": numeric["weight_domain"], "numeric_sha256": hashlib.sha256(numeric_path.read_bytes()).hexdigest(),
              "trace": trace, "integer_detections": detections.tolist()}
    if model_path:
        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.intra_op_num_threads = 4
        float_session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        reference = dict(zip(ir["outputs"], float_session.run(ir["outputs"], {"images": tensor})))
        float_detections = decode(reference)
        report["float_detections"] = float_detections.tolist()
        report["detection_comparison"] = detection_matches(float_detections, detections)
        report["outputs"] = {}
        for name in ir["outputs"]:
            left, right = reference[name].astype(np.float64), dequantized[name].astype(np.float64)
            delta = left - right
            report["outputs"][name] = {"max_abs": float(np.abs(delta).max()), "mean_abs": float(np.abs(delta).mean()),
                                       "cosine": float(np.dot(left.ravel(), right.ravel()) / max(
                                           float(np.linalg.norm(left) * np.linalg.norm(right)), 1e-12))}
    (output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("INTEGER_REFERENCE_COMPLETE", image.name, "detections", len(detections))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("numeric", type=Path)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--float-model", type=Path)
    parser.add_argument("--save-features", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.tasks, args.numeric, args.image, args.out, args.float_model, args.save_features, args.quiet)
