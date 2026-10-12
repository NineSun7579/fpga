"""Build a CPU Q/DQ reference for exploratory FPGA affine quantization.

This exercises signed float features encoded as affine uint8, per-channel
signed INT8 weights, and quantized SiLU inputs/outputs. It does not emulate
the legacy FPGA accumulator packing, Q16 scaling, or timing.
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

from raw_dfl import decode
from verify_reference import image_input
from activation.generate_silu_lut import build_silu_lut


def build(model_path, calibration_path, output_path, activation_luts=False):
    manifest = json.loads(calibration_path.read_text(encoding="utf-8"))
    if manifest["model_sha256"] != hashlib.sha256(model_path.read_bytes()).hexdigest():
        raise ValueError("Calibration belongs to another graph")
    model = onnx.load(str(model_path))
    result = deepcopy(model)
    nodes = []
    quantization = manifest["quantization"]
    replacement_weights = {}
    lut_muls = {}
    lut_sigmoids = set()
    if activation_luts:
        for conv in manifest["convolutions"]:
            if conv["activation"] != "silu":
                continue
            node = next(n for n in model.graph.node if n.name == conv["name"])
            preactivation = node.output[0]
            sigmoid = next(n for n in model.graph.node if n.op_type == "Sigmoid" and n.input[0] == preactivation)
            mul = next(n for n in model.graph.node if n.op_type == "Mul"
                       and preactivation in n.input and sigmoid.output[0] in n.input)
            lut_sigmoids.add(sigmoid.name)
            lut_muls[mul.name] = (preactivation, mul.output[0], conv)
    for conv in manifest["convolutions"]:
        weight_file = calibration_path.parent / conv["weights"]
        with np.load(weight_file, allow_pickle=False) as data:
            codes, scales = data["weight"].copy(), data["weight_scale"].astype(np.float32)
        original_node = next(n for n in model.graph.node if n.name == conv["name"])
        weight_name = original_node.input[1]
        prefix = f"migration_weight_{conv['task_id']:03d}"
        replacement_weights[weight_name] = prefix + "_float"
        result.graph.initializer.extend([
            numpy_helper.from_array(codes, prefix + "_i8"),
            numpy_helper.from_array(scales, prefix + "_scale"),
            numpy_helper.from_array(np.zeros(len(scales), np.int8), prefix + "_zp")])
        nodes.append(helper.make_node("DequantizeLinear",
                     [prefix + "_i8", prefix + "_scale", prefix + "_zp"],
                     [prefix + "_float"], name=prefix + "_dq", axis=0))

    u8_outputs = {}

    def quantize_node(name, source):
        q = quantization[name]
        prefix = f"migration_tensor_{len(nodes):04d}"
        result.graph.initializer.extend([
            numpy_helper.from_array(np.asarray(q["scale"], np.float32), prefix + "_scale"),
            numpy_helper.from_array(np.asarray(q["zero_point"], np.uint8), prefix + "_zp")])
        nodes.append(helper.make_node("QuantizeLinear", [source, prefix + "_scale", prefix + "_zp"],
                                      [prefix + "_u8"], name=prefix + "_q"))
        u8_outputs[name] = prefix + "_u8"
        destination = name if source != name else name + "__migration_input_dq"
        nodes.append(helper.make_node("DequantizeLinear",
                                      [prefix + "_u8", prefix + "_scale", prefix + "_zp"],
                                      [destination], name=prefix + "_dq"))
        return destination

    input_name = model.graph.input[0].name
    input_dequantized = quantize_node(input_name, input_name)
    for original in model.graph.node:
        if original.name in lut_sigmoids:
            continue
        if original.name in lut_muls:
            preactivation, output, conv = lut_muls[original.name]
            input_q, output_q = conv["preactivation_quantization"], conv["output_quantization"]
            table, _ = build_silu_lut(input_q["scale"], input_q["zero_point"],
                                      output_q["scale"], output_q["zero_point"])
            prefix = f"migration_lut_{conv['task_id']:03d}"
            result.graph.initializer.extend([
                numpy_helper.from_array(table, prefix + "_table"),
                numpy_helper.from_array(np.asarray(output_q["scale"], np.float32), prefix + "_scale"),
                numpy_helper.from_array(np.asarray(output_q["zero_point"], np.uint8), prefix + "_zp")])
            nodes.append(helper.make_node("Cast", [u8_outputs[preactivation]], [prefix + "_index"],
                                          name=prefix + "_cast", to=onnx.TensorProto.INT64))
            nodes.append(helper.make_node("Gather", [prefix + "_table", prefix + "_index"],
                                          [prefix + "_u8"], name=prefix + "_gather", axis=0))
            nodes.append(helper.make_node("DequantizeLinear",
                                          [prefix + "_u8", prefix + "_scale", prefix + "_zp"],
                                          [output], name=prefix + "_dq"))
            u8_outputs[output] = prefix + "_u8"
            continue
        node = deepcopy(original)
        for index, name in enumerate(node.input):
            if name in replacement_weights:
                node.input[index] = replacement_weights[name]
            elif name == input_name:
                node.input[index] = input_dequantized
        targeted = [name for name in node.output if name in quantization]
        for index, name in enumerate(node.output):
            if name in quantization:
                node.output[index] = name + "__migration_float"
        nodes.append(node)
        for name in targeted:
            quantize_node(name, name + "__migration_float")
    del result.graph.node[:]
    result.graph.node.extend(nodes)
    # Original weights are no longer referenced, and keeping them obscures sizing.
    initializers = [value for value in result.graph.initializer if value.name not in replacement_weights]
    del result.graph.initializer[:]
    result.graph.initializer.extend(initializers)
    result = onnx.shape_inference.infer_shapes(result, strict_mode=True, data_prop=True)
    onnx.checker.check_model(result, full_check=True)
    onnx.save(result, str(output_path))
    return result


def evaluate(float_path, quantized_path, images, output_path):
    options = ort.SessionOptions()
    options.log_severity_level = 3
    options.intra_op_num_threads = 4
    sessions = [ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
                for path in (float_path, quantized_path)]
    names = [value.name for value in sessions[0].get_outputs()]
    report = {"scope": "CPU affine Q/DQ smoke comparison; not RTL bit accuracy or validation mAP",
              "float_sha256": hashlib.sha256(float_path.read_bytes()).hexdigest(),
              "qdq_sha256": hashlib.sha256(quantized_path.read_bytes()).hexdigest(), "images": []}
    for image in images:
        tensor, metadata = image_input(image)
        reference, candidate = [session.run(names, {"images": tensor}) for session in sessions]
        errors = {}
        for name, left, right in zip(names, reference, candidate):
            if not np.isfinite(right).all():
                raise ValueError(f"Nonfinite quantized output: {image}/{name}")
            delta = left.astype(np.float64) - right
            denom = max(float(np.linalg.norm(left.ravel()) * np.linalg.norm(right.ravel())), 1e-12)
            errors[name] = {"max_abs": float(np.abs(delta).max()),
                            "mean_abs": float(np.abs(delta).mean()),
                            "rmse": float(np.sqrt(np.mean(delta * delta))),
                            "cosine": float(np.dot(left.ravel(), right.ravel()) / denom)}
        float_detections = decode(dict(zip(names, reference)))
        quantized_detections = decode(dict(zip(names, candidate)))
        report["images"].append({"image": metadata, "outputs": errors,
                                 "float_detections": float_detections.tolist(),
                                 "qdq_detections": quantized_detections.tolist()})
        print(image.name, "float_boxes", len(float_detections), "qdq_boxes", len(quantized_detections))
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image", type=Path, action="append", default=[])
    parser.add_argument("--activation-luts", action="store_true")
    args = parser.parse_args()
    build(args.model, args.calibration, args.out, args.activation_luts)
    print("QDQ_MODEL_CHECK_PASS", args.out)
    if args.image:
        evaluate(args.model, args.out, args.image, args.out.with_suffix(".comparison.json"))
