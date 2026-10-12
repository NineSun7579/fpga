"""Rebuild ONNX from the task IR to test lowering independently of source nodes."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper


def rebuild(model_path, tasks_path, output_path):
    source = onnx.load(str(model_path))
    ir = json.loads(tasks_path.read_text(encoding="utf-8"))
    if ir["source_sha256"] != hashlib.sha256(model_path.read_bytes()).hexdigest():
        raise ValueError("IR and source graph hashes differ")
    nodes = []
    constants = list(deepcopy(source.graph.initializer))
    for task in ir["tasks"]:
        prefix = f"task_{task['id']:03d}"
        inputs, output = task["inputs"], task["output"]
        if task["op"] == "Conv":
            conv_output = output if task["activation"] == "linear" else prefix + "_pre"
            weights = [task["weight"]] + ([task["bias"]] if task["bias"] else [])
            nodes.append(helper.make_node("Conv", inputs + weights, [conv_output], name=prefix,
                         kernel_shape=task["kernel"], strides=task["strides"], pads=task["pads"], group=1))
            if task["activation"] == "silu":
                nodes.extend([helper.make_node("Sigmoid", [conv_output], [prefix + "_sigmoid"],
                                               name=prefix + "_sigmoid"),
                              helper.make_node("Mul", [conv_output, prefix + "_sigmoid"], [output],
                                               name=prefix + "_silu")])
            elif task["activation"] == "clip":
                bounds = []
                for index, value in enumerate(task["clip"]):
                    name = prefix + f"_bound_{index}"
                    constants.append(numpy_helper.from_array(np.asarray(value, np.float32), name))
                    bounds.append(name)
                nodes.append(helper.make_node("Clip", [conv_output] + bounds, [output], name=prefix + "_clip"))
            elif task["activation"] != "linear":
                raise ValueError(f"Unknown activation: {task['activation']}")
        elif task["op"] == "ChannelView":
            params = [[task["channel_start"]], [task["channel_start"] + task["channel_count"]], [1], [1]]
            names = []
            for index, values in enumerate(params):
                name = prefix + f"_slice_{index}"
                constants.append(numpy_helper.from_array(np.asarray(values, np.int64), name))
                names.append(name)
            nodes.append(helper.make_node("Slice", inputs + names, [output], name=prefix))
        elif task["op"] in {"Concat", "Add"}:
            options = {"axis": 1} if task["op"] == "Concat" else {}
            nodes.append(helper.make_node(task["op"], inputs, [output], name=prefix, **options))
        elif task["op"] == "MaxPool":
            nodes.append(helper.make_node("MaxPool", inputs, [output], name=prefix,
                         kernel_shape=task["kernel"], strides=task["strides"], pads=task["pads"], ceil_mode=0))
        elif task["op"] == "Upsample2x":
            name = prefix + "_scale"
            constants.append(numpy_helper.from_array(np.asarray(task["scales"], np.float32), name))
            nodes.append(helper.make_node("Resize", inputs + ["", name], [output], name=prefix,
                         mode="nearest", coordinate_transformation_mode="asymmetric", nearest_mode="floor"))
        else:
            raise ValueError(f"No IR reference rule: {task['op']}")
    graph = helper.make_graph(nodes, "fpga_v8_ir_reference", list(deepcopy(source.graph.input)),
                              list(deepcopy(source.graph.output)), initializer=constants)
    result = helper.make_model(graph, opset_imports=list(deepcopy(source.opset_import)),
                               ir_version=source.ir_version)
    result = onnx.shape_inference.infer_shapes(result, strict_mode=True, data_prop=True)
    onnx.checker.check_model(result, full_check=True)
    onnx.save(result, str(output_path))
    print("IR_REBUILD_CHECK_PASS", len(ir["tasks"]), "tasks", len(nodes), "feature operations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rebuild(args.model, args.tasks, args.out)
