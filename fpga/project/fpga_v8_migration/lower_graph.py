"""Lower the checked fixed-shape V8 graph into explicit migration tasks.

This IR is intentionally not called FPGA instruction data: the runtime ABI,
affine quantization, and integration must be verified before binary emission.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper, shape_inference


def attrs_of(node):
    return {a.name: helper.get_attribute_value(a) for a in node.attribute}


def shape_of(value):
    dims = value.type.tensor_type.shape.dim
    if not all(d.HasField("dim_value") for d in dims):
        raise ValueError(f"Symbolic tensor remains: {value.name}")
    return [d.dim_value for d in dims]


def lower(path):
    model = shape_inference.infer_shapes(onnx.load(str(path)), strict_mode=True, data_prop=True)
    onnx.checker.check_model(model, full_check=True)
    graph = model.graph
    values = {t.name: numpy_helper.to_array(t) for t in graph.initializer}
    shapes = {}
    for value in (*graph.input, *graph.value_info, *graph.output):
        try:
            shapes[value.name] = shape_of(value)
        except ValueError:
            # Only live feature shapes are mandatory; dead shape chains are ignored.
            pass
    nodes = list(graph.node)
    consumers = {}
    producers = {}
    for node in nodes:
        for name in node.input:
            consumers.setdefault(name, []).append(node)
        for name in node.output:
            producers[name] = node
        if node.op_type == "Constant":
            attrs = attrs_of(node)
            if "value" in attrs:
                values[node.output[0]] = numpy_helper.to_array(attrs["value"])
    live = set()

    def visit(name):
        if name in values or name in live:
            return
        live.add(name)
        node = producers.get(name)
        if node:
            for input_name in node.input:
                if input_name:
                    visit(input_name)

    for output in graph.output:
        visit(output.name)
    skipped = set()
    tasks = []
    for node in nodes:
        if not any(name in live for name in node.output) or node.name in skipped:
            continue
        attrs = attrs_of(node)
        task = {"id": len(tasks), "name": node.name, "op": node.op_type,
                "inputs": [x for x in node.input if x and x not in values],
                "output": node.output[0]}
        if len(node.output) != 1:
            raise ValueError(f"Multiple outputs need an explicit lowering rule: {node.name}")
        if node.op_type == "Conv":
            weights = values[node.input[1]]
            kernels = list(weights.shape[2:])
            stride = list(attrs.get("strides", [1, 1]))
            pads = list(attrs.get("pads", [0, 0, 0, 0]))
            if (kernels not in ([1, 1], [3, 3]) or stride not in ([1, 1], [2, 2])
                    or attrs.get("group", 1) != 1 or attrs.get("dilations", [1, 1]) != [1, 1]
                    or attrs.get("auto_pad", b"NOTSET") != b"NOTSET"):
                raise ValueError(f"Unsupported convolution contract: {node.name}")
            task.update({"weight": node.input[1], "bias": node.input[2] if len(node.input) > 2 else None,
                         "weight_shape": list(weights.shape), "kernel": kernels, "strides": stride,
                         "pads": pads, "activation": "linear", "preactivation": node.output[0]})
            peers = consumers.get(node.output[0], [])
            sigmoid = next((n for n in peers if n.op_type == "Sigmoid"), None)
            mul = next((n for n in peers if n.op_type == "Mul" and sigmoid
                        and sigmoid.output[0] in n.input), None)
            if sigmoid and mul and len(peers) == 2 and consumers.get(sigmoid.output[0]) == [mul]:
                task.update({"activation": "silu", "output": mul.output[0]})
                skipped.update((sigmoid.name, mul.name))
            elif len(peers) == 1 and peers[0].op_type == "Clip":
                clip = peers[0]
                lower_bound = float(values[clip.input[1]].item())
                upper_bound = float(values[clip.input[2]].item())
                task.update({"activation": "clip", "clip": [lower_bound, upper_bound],
                             "output": clip.output[0]})
                skipped.add(clip.name)
        elif node.op_type == "Slice":
            source = shapes[node.input[0]]
            starts, ends, axes = [values[name].reshape(-1).tolist() for name in node.input[1:4]]
            steps = values[node.input[4]].reshape(-1).tolist() if len(node.input) > 4 else [1] * len(axes)
            if axes != [1] or steps != [1] or len(starts) != 1 or len(ends) != 1:
                raise ValueError(f"Expected static contiguous channel slice: {node.name}")
            start, stop, step = slice(starts[0], ends[0], 1).indices(source[1])
            if start % 16 or (stop - start) % 16:
                raise ValueError(f"Slice crosses 16-channel packing: {node.name}")
            task.update({"op": "ChannelView", "channel_start": start, "channel_count": stop - start})
        elif node.op_type == "Concat":
            if attrs.get("axis") != 1:
                raise ValueError(f"Only channel concatenation is covered: {node.name}")
            task.update({"axis": 1, "requantization_required": True})
        elif node.op_type == "Add":
            if len(task["inputs"]) != 2 or shapes[task["inputs"][0]] != shapes[task["inputs"][1]]:
                raise ValueError(f"Broadcast or scalar Add needs a separate rule: {node.name}")
            task["requantization_required"] = True
        elif node.op_type == "MaxPool":
            if (attrs.get("kernel_shape") != [5, 5] or attrs.get("strides") != [1, 1]
                    or attrs.get("pads") != [2, 2, 2, 2] or attrs.get("ceil_mode", 0) != 0
                    or attrs.get("dilations", [1, 1]) != [1, 1]):
                raise ValueError(f"Expected SPPF 5x5 stride-1: {node.name}")
            task.update({"kernel": [5, 5], "strides": [1, 1], "pads": [2, 2, 2, 2],
                         "padding_semantics": "negative_infinity_not_affine_zero"})
        elif node.op_type == "Resize":
            scales = values[node.input[2]].tolist()
            if (scales != [1, 1, 2, 2] or attrs.get("mode") != b"nearest"
                    or attrs.get("coordinate_transformation_mode") != b"asymmetric"
                    or attrs.get("nearest_mode") != b"floor"):
                raise ValueError(f"Only exact nearest 2x is covered: {node.name}")
            task.update({"op": "Upsample2x", "scales": scales})
        else:
            raise ValueError(f"Live operator lacks a lowering rule: {node.name} ({node.op_type})")
        names = task["inputs"] + [task["output"]]
        if any(name not in shapes or len(shapes[name]) != 4 or shapes[name][0] != 1 for name in names):
            raise ValueError(f"Nonconcrete NCHW feature contract: {node.name}")
        task.update({"input_shapes": [shapes[name] for name in task["inputs"]],
                     "output_shape": shapes[task["output"]]})
        tasks.append(task)
    outputs = [v.name for v in graph.output]
    for name in outputs:
        if name not in {task["output"] for task in tasks}:
            raise ValueError(f"Graph output was not lowered: {name}")
    tensor_names = {v.name for v in graph.input}
    tensor_names.update(task["output"] for task in tasks)
    tensors = {}
    for name in sorted(tensor_names):
        shape = shapes[name]
        if len(shape) != 4:
            raise ValueError(f"Unexpected feature tensor: {name}")
        padded_channels = ((shape[1] + 15) // 16) * 16
        tensors[name] = {"shape": shape, "padded_channels": padded_channels,
                         "bytes_u8_padded": padded_channels * shape[2] * shape[3]}
    return {"source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "status": "semantic_ir_only_not_hardware_instructions",
            "task_counts": dict(Counter(task["op"] for task in tasks)),
            "tasks": tasks, "tensors": tensors, "outputs": outputs,
            "pending": ["calibrated affine quantization and fixed-point accuracy",
                        "SiLU LUT integration and signed activation preservation",
                        "SPPF boundary semantics with negative SiLU features",
                        "verified packed feature layout and instruction emission",
                        "DDR arbitration, camera raw input conversion, and host runtime",
                        "PDS timing/resource verification and measured board speedup"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = lower(args.model)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "task_counts": result["task_counts"],
                      "tensor_count": len(result["tensors"])}, indent=2))
