"""Check the migration's compute ceiling before claiming an RK3568 speedup.

This is an optimistic throughput bound, not a cycle-accurate simulator. It
reads the current RTL as bytes and verifies both instantiated engines use
the live shared macros. Dependencies, DDR and line-buffer overhead can
only make the reported full-network bound slower.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


def preflight(ir_path, source_dir, baseline_csv, clock_mhz):
    config_path = source_dir / "npu_top/config.v"
    top_path = source_dir / "npu_top/npu_top.v"
    config = config_path.read_bytes()
    top = top_path.read_bytes()
    macros = {name.decode("ascii"): int(value) for name, value in re.findall(
        rb"(?m)^\s*`define\s+(\w+)\s+(\d+)\b", config)}
    parallel = re.search(rb"conv11_para_top\s*#\((.*?)\)\s*conv_para_top_inst", top, re.S)
    main = re.search(rb"conv_top\s*#\((.*?)\)\s*conv_top_inst", top, re.S)
    if not parallel or not main:
        raise ValueError("Cannot verify current convolution engine instantiations")
    engines = []
    for name, match in [("conv_para_top_inst", parallel), ("conv_top_inst", main)]:
        parameter_bytes = match.group(1)
        in_macro = re.search(rb"\.CHA_PAR_IN\s*\(\s*`(\w+)\s*\)", parameter_bytes)
        out_macro = re.search(rb"\.CHA_PAR_OUT\s*\(\s*`(\w+)\s*\)", parameter_bytes)
        if not in_macro or not out_macro:
            raise ValueError("Engine parallelism is not specified by recognized macros")
        input_lanes = macros[in_macro.group(1).decode("ascii")]
        output_lanes = macros[out_macro.group(1).decode("ascii")]
        engines.append({"instance": name, "input_lanes": input_lanes, "output_lanes": output_lanes,
                        "macs_per_cycle_3x3": input_lanes * output_lanes * 9,
                        "macs_per_cycle_1x1": input_lanes * output_lanes})
    ir = json.loads(ir_path.read_text(encoding="utf-8"))
    macs = {"1x1": 0, "3x3": 0}
    for task in ir["tasks"]:
        if task["op"] != "Conv":
            continue
        co, ci, kh, kw = task["weight_shape"]
        _, _, height, width = task["output_shape"]
        macs[f"{kh}x{kw}"] += co * ci * kh * kw * height * width
    capacities = {kernel: sum(engine[f"macs_per_cycle_{kernel}"] for engine in engines) for kernel in macs}
    # The 3x3-only bound remains decisive even if an entirely different 1x1
    # acceleration path is added: it excludes ALL 1x1 work and all overhead.
    bounds = {kernel: macs[kernel] / capacities[kernel] / (clock_mhz * 1000) for kernel in macs}
    rows = {row["stage"]: row for row in csv.DictReader(baseline_csv.read_text(encoding="utf-8").splitlines())}
    baseline = {stage: float(row["mean_ms"]) for stage, row in rows.items()}
    run_ms = baseline["run_only"]
    return {"status": "analytic_lower_bound_not_measured_FPGA_fps", "npu_clock_mhz_assumed": clock_mhz,
            "rtl": {"config_sha256": hashlib.sha256(config).hexdigest(),
                    "top_sha256": hashlib.sha256(top).hexdigest(), "engines": engines},
            "model_macs": macs, "ideal_kernel_time_ms": bounds,
            "conv_only_ideal_ms": sum(bounds.values()),
            "conv_only_ideal_fps_upper_bound": 1000 / sum(bounds.values()),
            "3x3_only_ideal_fps_upper_bound": 1000 / bounds["3x3"],
            "rknn_historical_mean_ms": baseline,
            "3x3_only_bound_exceeds_rknn_run": bounds["3x3"] > run_ms,
            "required_3x3_macs_per_cycle_for_rknn_run": macs["3x3"] / (run_ms * clock_mhz * 1000),
            "limits": ["clock is a stated assumption, not timing acceptance of a V8 candidate",
                       "assumes both existing engines have continuous useful MAC occupancy",
                       "excludes channel padding, frame dependencies, memory and every non-Conv operation",
                       "RKNN data are retained historical measurements, not simultaneous new trials"],
            "decision": "Current convolution engine migration alone cannot establish RK3568 latency/FPS improvement; keep RKNN execution and evaluate FPGA preprocessing/transfer overlap, or redesign compute architecture."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ir", type=Path)
    parser.add_argument("--rtl", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--clock-mhz", type=float, default=150)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.clock_mhz <= 0:
        raise ValueError("Clock frequency must be positive")
    result = preflight(args.ir, args.rtl, args.baseline, args.clock_mhz)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PERFORMANCE_PREFLIGHT", json.dumps({"conv_only_ideal_ms": result["conv_only_ideal_ms"],
          "3x3_only_ideal_ms": result["ideal_kernel_time_ms"]["3x3"],
          "rknn_historical_run_ms": result["rknn_historical_mean_ms"]["run_only"],
          "3x3_only_bound_exceeds_rknn_run": result["3x3_only_bound_exceeds_rknn_run"]}))
