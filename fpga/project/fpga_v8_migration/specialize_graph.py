"""Fold only static shape arithmetic for the fixed ONNX input contract."""

from copy import deepcopy

import numpy as np
import onnx
from onnx import helper, numpy_helper, shape_inference
from onnx.reference import ReferenceEvaluator


def concrete_shape(value):
    dims = value.type.tensor_type.shape.dim
    if all(d.HasField("dim_value") for d in dims):
        return [d.dim_value for d in dims]
    return None


def specialize(model):
    """Preserve tensor names and floating point operators; resolve shape chains.

    Folding is allowed only with concrete dimensions or exclusively constant
    operands. Feature-map operations and activation formulas are never changed.
    """
    result = deepcopy(model)
    folds = []
    for _ in range(len(model.graph.node) + 1):
        inferred = shape_inference.infer_shapes(result, strict_mode=True, data_prop=True)
        shapes = {v.name: concrete_shape(v) for v in
                  (*inferred.graph.input, *inferred.graph.value_info, *inferred.graph.output)}
        values = {t.name: numpy_helper.to_array(t) for t in inferred.graph.initializer}
        new_nodes = []
        changed = False
        for node in inferred.graph.node:
            outputs = None
            if node.op_type == "Constant":
                attr = next((a for a in node.attribute if a.name == "value"), None)
                if attr:
                    values[node.output[0]] = numpy_helper.to_array(attr.t)
            elif node.op_type == "Shape" and shapes.get(node.input[0]) is not None:
                dims = shapes[node.input[0]]
                attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
                outputs = [np.asarray(dims[attrs.get("start", 0):attrs.get("end", len(dims))], np.int64)]
            elif node.op_type in {"Gather", "Add", "Sub", "Mul", "Div", "Unsqueeze", "Concat"}:
                if all(name in values for name in node.input):
                    outputs = ReferenceEvaluator(node).run(None, {name: values[name] for name in node.input})
            if outputs is not None:
                if len(outputs) != len(node.output):
                    raise ValueError(f"Constant output count mismatch: {node.name}")
                for name, output in zip(node.output, outputs):
                    values[name] = output
                    new_nodes.append(helper.make_node("Constant", [], [name],
                                     name=node.name + "/static", value=numpy_helper.from_array(output)))
                folds.append({"name": node.name, "op": node.op_type, "outputs": list(node.output)})
                changed = True
            else:
                new_nodes.append(node)
        if not changed:
            onnx.checker.check_model(inferred, full_check=True)
            return inferred, folds
        result = inferred
        del result.graph.node[:]
        result.graph.node.extend(new_nodes)
        # Avoid stale symbolic intermediate shapes hiding resolved Slice sizes.
        del result.graph.value_info[:]
    raise RuntimeError("Static specialization failed to reach a fixed point")
