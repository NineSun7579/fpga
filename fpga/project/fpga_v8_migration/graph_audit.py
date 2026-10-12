"""Inspect the exact FPGA migration source graph without changing its semantics.

The inventory and float weights are preparation artifacts, not an executable
FPGA program. No quantization, activation replacement, or inference claim is
implicit in their generation.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper, shape_inference

from specialize_graph import specialize


def shape_of(value):
    result = []
    for dim in value.type.tensor_type.shape.dim:
        result.append(dim.dim_value if dim.HasField("dim_value") else dim.dim_param)
    return result


def attributes(node):
    result = {}
    for attr in node.attribute:
        value = helper.get_attribute_value(attr)
        if isinstance(value, onnx.TensorProto):
            array = numpy_helper.to_array(value)
            value = {"shape": list(array.shape), "values": array.tolist()}
        elif isinstance(value, bytes):
            value = value.decode("utf-8")
        elif isinstance(value, tuple):
            value = list(value)
        result[attr.name] = value
    return result


def audit(model_path, output_dir, export_weights=False):
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    model = onnx.load(str(model_path))
    onnx.checker.check_model(model, full_check=True)
    model = shape_inference.infer_shapes(model, strict_mode=True, data_prop=True)
    graph = model.graph
    specialized, folds = specialize(model)
    shapes = {v.name: shape_of(v) for v in
              (*specialized.graph.input, *specialized.graph.value_info, *specialized.graph.output)}
    constants = {t.name: numpy_helper.to_array(t) for t in graph.initializer}
    for node in graph.node:
        if node.op_type == "Constant":
            attr = next((a for a in node.attribute if a.name == "value"), None)
            if attr:
                constants[node.output[0]] = numpy_helper.to_array(attr.t)
    consumers = {}
    for node in graph.node:
        for value in node.input:
            consumers.setdefault(value, []).append(node)

    nodes = []
    convs = []
    for index, node in enumerate(graph.node):
        attrs = attributes(node)
        record = {
            "index": index,
            "name": node.name,
            "op": node.op_type,
            "inputs": list(node.input),
            "outputs": list(node.output),
            "input_shapes": [shapes.get(x, list(constants[x].shape) if x in constants else None)
                             for x in node.input],
            "output_shapes": [shapes.get(x) for x in node.output],
            "attributes": attrs,
        }
        nodes.append(record)
        if node.op_type != "Conv":
            continue
        if len(node.input) < 2 or node.input[1] not in constants:
            raise ValueError(f"Nonconstant convolution weights: {node.name}")
        weights = constants[node.input[1]]
        bias = constants[node.input[2]] if len(node.input) > 2 else np.zeros(weights.shape[0], np.float32)
        out = shapes.get(node.output[0])
        activation = "linear"
        peers = consumers.get(node.output[0], [])
        sigmoid = next((n for n in peers if n.op_type == "Sigmoid"), None)
        if sigmoid:
            mul = next((n for n in peers if n.op_type == "Mul" and sigmoid.output[0] in n.input), None)
            if mul and len(peers) == 2 and len(consumers.get(sigmoid.output[0], [])) == 1:
                activation = "silu"
        entry = {
            "index": len(convs), "node_index": index, "name": node.name,
            "input": node.input[0], "output": node.output[0],
            "input_shape": shapes.get(node.input[0]), "output_shape": out,
            "weight_shape": list(weights.shape), "bias_shape": list(bias.shape),
            "kernel": list(weights.shape[2:]), "strides": attrs.get("strides", [1, 1]),
            "pads": attrs.get("pads", [0, 0, 0, 0]), "groups": attrs.get("group", 1),
            "activation": activation,
            "weight_bytes_fp32": int(weights.size * 4),
            "weight_values": int(weights.size),
            "macs": int(np.prod(out, dtype=np.int64) * np.prod(weights.shape[1:], dtype=np.int64))
                    if out and all(isinstance(d, int) for d in out) else None,
        }
        if export_weights:
            weight_dir = output_dir / "float_weights"
            weight_dir.mkdir(parents=True, exist_ok=True)
            stem = f"conv_{entry['index']:03d}"
            np.save(weight_dir / f"{stem}_weight.npy", weights, allow_pickle=False)
            np.save(weight_dir / f"{stem}_bias.npy", bias, allow_pickle=False)
            entry["weight_file"] = f"float_weights/{stem}_weight.npy"
            entry["bias_file"] = f"float_weights/{stem}_bias.npy"
        convs.append(entry)

    output_dir.mkdir(parents=True, exist_ok=True)
    onnx.save(specialized, str(output_dir / "specialized.onnx"))
    result = {
        "model": model_path.name, "sha256": digest, "ir_version": model.ir_version,
        "opset": [{"domain": x.domain, "version": x.version} for x in model.opset_import],
        "inputs": [{"name": v.name, "shape": shape_of(v), "dtype": v.type.tensor_type.elem_type}
                   for v in graph.input],
        "outputs": [{"name": v.name, "shape": shape_of(v), "dtype": v.type.tensor_type.elem_type}
                    for v in graph.output],
        "operator_counts": dict(sorted(Counter(n.op_type for n in graph.node).items())),
        "conv_count": len(convs), "conv_activation_counts": dict(Counter(c["activation"] for c in convs)),
        "weight_values": sum(c["weight_values"] for c in convs),
        "macs": sum(c["macs"] or 0 for c in convs),
        "nodes": nodes, "convolutions": convs,
        "static_shape_folds": folds,
        "constants": {k: {"shape": list(v.shape), "values": v.tolist()}
                      for k, v in constants.items() if v.size <= 32},
        "status": "graph_checked_float_assets_only",
    }
    (output_dir / "graph.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [f"# {model_path.name}", "", f"SHA-256: `{digest}`", "",
             "ONNX checker and strict shape inference passed.", "",
             f"Static shape operations folded: {len(folds)}. Feature-map math is unchanged.", "",
             "These are graph/float-weight preparation assets, not FPGA instructions.", "",
             "| Operator | Count |", "| --- | --- |"]
    lines += [f"| {op} | {count} |" for op, count in result["operator_counts"].items()]
    lines += ["", f"Convolutions: {len(convs)}; activations: {result['conv_activation_counts']}",
              f"Weight values: {result['weight_values']}; convolution MACs: {result['macs']}", "",
              "| Output | Shape |", "| --- | --- |"]
    lines += [f"| {v['name']} | {v['shape']} |" for v in result["outputs"]]
    lines += ["", "| Conv | Name | Weight | Input | Output | Activation |",
              "| --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {c['index']} | {c['name']} | {c['weight_shape']} | {c['input_shape']} | "
              f"{c['output_shape']} | {c['activation']} |" for c in convs]
    (output_dir / "graph.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-float-weights", action="store_true")
    args = parser.parse_args()
    result = audit(args.model, args.out, args.export_float_weights)
    print(json.dumps({k: result[k] for k in ("sha256", "operator_counts", "conv_count",
                                           "conv_activation_counts", "weight_values", "macs", "outputs")}, indent=2))


if __name__ == "__main__":
    main()
