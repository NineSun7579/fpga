"""Prepare verified HWC16 assets without issuing incomplete legacy instructions."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from hwc16_layout import pack_biases, pack_weights
from plan_buffers import plan


def prepare(tasks_path, numeric_path, output_dir):
    ir = json.loads(tasks_path.read_text(encoding="utf-8"))
    numeric = json.loads(numeric_path.read_text(encoding="utf-8"))
    if numeric["tasks_sha256"] != hashlib.sha256(tasks_path.read_bytes()).hexdigest():
        raise ValueError("IR and numerical assets must agree")
    if numeric["summary"]["legacy_shared_scale_incompatible"] or numeric["summary"]["legacy_bias_incompatible"]:
        raise ValueError("Numerical assets cannot use the shared-scale/bias register contract")
    materialized = deepcopy(ir)
    for task in materialized["tasks"]:
        if task["op"] == "ChannelView":
            task["op"] = "ChannelCopy"
            shape = task["input_shapes"][0]
            task["command"] = {"total_pixels": shape[2] * shape[3],
                               "groups_per_pixel": (shape[1] + 15) // 16,
                               "first_group": task["channel_start"] // 16,
                               "group_count": task["channel_count"] // 16}
    buffers = plan(materialized)
    buffers["layout"] = "uint8 HWC16 [row,column,channel_group,lane]; lane0 at lowest address"
    buffers["status"] = "relative_HWC16_materialized_copy_plan_no_board_ddr_assignment"
    buffers["limits"] = ["sequential tasks only", "no camera/ring/reserved DDR assignment",
                         "actual loader endian and AXI DMA contract still require simulation"]
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    conv_tasks = {task["id"]: task for task in ir["tasks"] if task["op"] == "Conv"}
    assets = []
    for operation in numeric["operations"]:
        if operation["op"] != "Conv":
            continue
        task = conv_tasks[operation["task_id"]]
        with np.load(numeric_path.parent / operation["asset"], allow_pickle=False) as asset:
            weight = pack_weights(asset["weight"])
            co = (task["weight_shape"][0] + 15) // 16 * 16
            bias = pack_biases(asset["folded_bias_q16"], co)
            lut = asset["activation_lut"].tobytes()
        stem = f"task_{task['id']:03d}"
        files = {}
        for kind, data in [("weight", weight), ("bias", bias), ("lut", lut)]:
            path = assets_dir / (stem + "_" + kind + ".bin")
            path.write_bytes(data)
            files[kind] = {"path": path.relative_to(output_dir).as_posix(), "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
        assets.append({"task_id": task["id"], "files": files,
                       "shared_scale_q16": operation["multiplier_q16"][0],
                       "preactivation_zero_point": operation["preactivation_quantization"]["zero_point"],
                       "input_zero_point": numeric["quantization"][task["inputs"][0]]["zero_point"]})
    (output_dir / "buffers.json").write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
    (output_dir / "materialized_tasks.json").write_text(json.dumps(materialized, indent=2) + "\n", encoding="utf-8")
    result = {"status": "HWC16_preparation_assets_not_an_executable_instruction_image",
              "source_ir_sha256": hashlib.sha256(tasks_path.read_bytes()).hexdigest(),
              "numeric_sha256": hashlib.sha256(numeric_path.read_bytes()).hexdigest(),
              "feature_arena_bytes": buffers["feature_arena_bytes"], "convolutions": assets,
              "channel_copy_count": sum(task["op"] == "ChannelCopy" for task in materialized["tasks"]),
              "mandatory_before_instructions": ["640x640 first layer engine geometry and buffers",
                                               "SiLU/Clip finish and signed Add/Concat integration",
                                               "ChannelCopy engine and DMA route",
                                               "live instruction capacity and scheduling/engine completion",
                                               "DDR crossbar port ownership and host raw-frame contract",
                                               "RTL per-layer parity and full candidate timing/resources"],
              "performance": "Current engine full-network compute bound cannot improve retained RKNN latency."}
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("HWC16_ASSETS_PREPARED", len(assets), "convolutions", result["channel_copy_count"],
          "channel_copies", "arena_bytes", result["feature_arena_bytes"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("numeric", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.tasks, args.numeric, args.out)
