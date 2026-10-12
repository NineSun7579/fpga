"""Export explicit integer arithmetic assets for a candidate V8 implementation.

These files specify arithmetic, not the legacy instruction/DMA ABI. Shared
layer weight scales can be evaluated alongside per-channel scales. A folded
input-zero-point bias uses the *encoded* multiplier, preventing systematic
zero-input error when its Q16 coefficient is rounded.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper

from activation.generate_silu_lut import build_silu_lut


def q16(value):
    value = np.asarray(value, np.float64)
    if not np.isfinite(value).all() or (value < 0).any():
        raise ValueError("Expected finite nonnegative multiplier")
    result = np.floor(value * 65536 + 0.5)
    if (result > 0xffffffff).any():
        raise ValueError("Multiplier exceeds unsigned 32-bit Q16")
    return result.astype(np.int64)


def export(model_path, tasks_path, calibration_path, output_dir, weight_domain, fuse_clipped_heads=False):
    source_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    ir = json.loads(tasks_path.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    if ir["source_sha256"] != source_hash or calibration["model_sha256"] != source_hash:
        raise ValueError("Model, task IR and calibration hashes must agree")
    weights = {t.name: numpy_helper.to_array(t) for t in onnx.load(str(model_path)).graph.initializer}
    domains = calibration["quantization"]
    output_dir.mkdir(parents=True, exist_ok=True)
    operations = []
    for task in ir["tasks"]:
        operation = {"task_id": task["id"], "op": task["op"]}
        output_q = domains[task["output"]]
        input_q = [domains[name] for name in task["inputs"]]
        stem = f"task_{task['id']:03d}"
        if task["op"] == "Conv":
            weight = weights[task["weight"]].astype(np.float64)
            if weight_domain == "per-layer":
                weight_scale = np.full(weight.shape[0], max(float(np.abs(weight).max()) / 127, 1e-12))
            else:
                weight_scale = np.maximum(np.abs(weight).max(axis=(1, 2, 3)) / 127, 1e-12)
            codes = np.clip(np.rint(weight / weight_scale[:, None, None, None]), -127, 127).astype(np.int8)
            # A head without SiLU can accumulate directly into its clipped
            # output domain. This avoids the coarser pre-Clip domain followed
            # by a second quantization. The LUT still defines Clip endpoints.
            pre_q = output_q if fuse_clipped_heads and task["activation"] == "clip" else domains[task["preactivation"]]
            multiplier_real = input_q[0]["scale"] * weight_scale / pre_q["scale"]
            multiplier = q16(multiplier_real)
            bias = weights[task["bias"]].astype(np.float64) if task["bias"] else np.zeros(weight.shape[0])
            # Keep integer rounding separate from exact offset correction.
            bias_q16 = np.floor(bias / pre_q["scale"] * 65536 + 0.5).astype(np.int64)
            weight_sum = codes.astype(np.int64).sum(axis=(1, 2, 3))
            folded_bias_q16 = bias_q16 - input_q[0]["zero_point"] * weight_sum * multiplier
            lut = np.arange(256, dtype=np.uint8)
            if task["activation"] == "silu":
                lut, _ = build_silu_lut(pre_q["scale"], pre_q["zero_point"],
                                        output_q["scale"], output_q["zero_point"])
            elif task["activation"] == "clip":
                values = (np.arange(256, dtype=np.float64) - pre_q["zero_point"]) * pre_q["scale"]
                values = np.clip(values, *task["clip"])
                lut = np.clip(np.rint(values / output_q["scale"]) + output_q["zero_point"], 0, 255).astype(np.uint8)
            elif pre_q != output_q:
                raise ValueError("Linear activation unexpectedly changes quantization domain")
            asset_name = stem + ".npz"
            np.savez(output_dir / asset_name, weight=codes, multiplier_q16=multiplier,
                     folded_bias_q16=folded_bias_q16, bias_q16=bias_q16, activation_lut=lut)
            bound_raw = 255 * np.abs(codes.astype(np.int64)).sum(axis=(1, 2, 3))
            bound_q16 = bound_raw * multiplier + np.abs(folded_bias_q16) + pre_q["zero_point"] * 65536
            operation.update({"asset": asset_name, "activation": task["activation"],
                              "preactivation_quantization": pre_q,
                              "weight_scale": weight_scale.tolist(),
                              "multiplier_q16": multiplier.tolist(),
                              "multiplier_relative_error_max": float(np.max(np.abs(
                                  multiplier / 65536 - multiplier_real) / np.maximum(multiplier_real, 1e-30))),
                              "coefficient_underflow_channels": int(np.count_nonzero(multiplier == 0)),
                              "raw_accumulator_abs_bound_max": int(bound_raw.max()),
                              "postscale_q16_abs_bound_max": int(bound_q16.max()),
                              "legacy_shared_scale_u16": bool(np.all(multiplier == multiplier[0]) and multiplier.max() <= 65535),
                              "legacy_bias_i32": bool(np.all(folded_bias_q16 >= -2147483648)
                                                      and np.all(folded_bias_q16 <= 2147483647)),
                              "asset_sha256": hashlib.sha256((output_dir / asset_name).read_bytes()).hexdigest()})
        elif task["op"] in {"Add", "Concat"}:
            operation["input_to_output_multiplier_q16"] = [int(q16(q["scale"] / output_q["scale"])) for q in input_q]
        elif task["op"] in {"ChannelView", "MaxPool", "Upsample2x"}:
            if input_q[0] != output_q:
                raise ValueError("Value-preserving operation must retain its source quantization")
        else:
            raise ValueError(f"Unknown operation {task['op']}")
        operations.append(operation)
    convolutions = [op for op in operations if op["op"] == "Conv"]
    result = {"status": "candidate_integer_arithmetic_assets_no_legacy_instruction_image",
              "model_sha256": source_hash, "tasks_sha256": hashlib.sha256(tasks_path.read_bytes()).hexdigest(),
              "calibration_sha256": hashlib.sha256(calibration_path.read_bytes()).hexdigest(),
              "weight_domain": weight_domain,
              "clipped_head_domain": "output_domain_then_Clip_LUT" if fuse_clipped_heads else "preactivation_domain_then_Clip_requantization_LUT",
              "rounding": "arithmetic floor((q16+32768)/65536), saturate u8",
              "activation_table_rounding": "numpy ties-to-even; table bytes define lookup exactly",
              "conv_padding": "input affine zero-point, including every kernel position",
              "maxpool_padding": "minimum code 0, preserving input domain",
              "quantization": domains, "operations": operations,
              "summary": {"convolutions": len(convolutions),
                          "legacy_shared_scale_incompatible": sum(not c["legacy_shared_scale_u16"] for c in convolutions),
                          "legacy_bias_incompatible": sum(not c["legacy_bias_i32"] for c in convolutions),
                          "coefficient_underflow_channels": sum(c["coefficient_underflow_channels"] for c in convolutions)},
              "limits": ["development smoke calibration; independent accuracy not accepted",
                         "no RTL packing, DMA, overflow-wrap, or instruction scheduling emulation",
                         "verified DMA layout, signed Add/Concat and LUT integration required",
                         "legacy convolution accumulator width must be verified separately"]}
    (output_dir / "numeric.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("NUMERIC_ASSETS_EXPORT_PASS", weight_domain, json.dumps(result["summary"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--weight-domain", choices=["per-layer", "per-channel"], default="per-layer")
    parser.add_argument("--fuse-clipped-heads", action="store_true")
    args = parser.parse_args()
    export(args.model, args.tasks, args.calibration, args.out, args.weight_domain, args.fuse_clipped_heads)
