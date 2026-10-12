"""Generate an affine u8 SiLU table from explicit, uncalibrated parameters."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def build_silu_lut(input_scale, input_zero_point, output_scale, output_zero_point):
    for name, value in (("input_scale", input_scale), ("output_scale", output_scale)):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(name + " must be finite and positive")
    for name, value in (("input_zero_point", input_zero_point),
                        ("output_zero_point", output_zero_point)):
        if not isinstance(value, (int, np.integer)) or not 0 <= value <= 255:
            raise ValueError(name + " must be an integer in [0, 255]")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        x = (np.arange(256, dtype=np.float64) - input_zero_point) * input_scale
    if not np.all(np.isfinite(x)):
        raise ValueError("input affine domain overflows float64")
    sigmoid = np.empty_like(x)
    positive = x >= 0
    sigmoid[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    exp_x = np.exp(x[~positive])
    sigmoid[~positive] = exp_x / (1.0 + exp_x)
    y = x * sigmoid
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        output_codes = y / output_scale + output_zero_point
    if not np.all(np.isfinite(output_codes)):
        raise ValueError("output affine codes overflow float64")
    rounded = np.rint(output_codes)
    table = np.clip(rounded, 0, 255).astype(np.uint8)
    reconstructed = (table.astype(np.float64) - output_zero_point) * output_scale
    error = reconstructed - y
    unclipped = (rounded >= 0) & (rounded <= 255)
    # hypot avoids overflow when computing an RMS for large finite errors.
    def metrics(values):
        if values.size == 0:
            return None
        magnitude = np.abs(values)
        return {
            "max_abs": float(np.max(magnitude)),
            "mean_abs": float(np.mean(magnitude / values.size) * values.size),
            "rmse": float(np.hypot.reduce(values / np.sqrt(values.size))),
        }
    manifest = {
        "format": "fpga_v8_activation_lut_affine_u8_v1",
        "activation": "SiLU: x / (1 + exp(-x))",
        "calibration_status": "not_calibrated; parameters supplied by caller",
        "entries": 256,
        "input_scale": float(input_scale),
        "input_zero_point": int(input_zero_point),
        "output_scale": float(output_scale),
        "output_zero_point": int(output_zero_point),
        "rounding": "nearest, ties to even (numpy.rint)",
        "clipping": "saturate rounded output code to [0, 255]",
        "lane_byte_order": "lane i occupies bits [8*i +: 8]",
        "table_sha256": hashlib.sha256(table.tobytes()).hexdigest(),
        "input_float_range": [float(x.min()), float(x.max())],
        "silu_float_range": [float(y.min()), float(y.max())],
        "negative_input_count": int(np.count_nonzero(x < 0)),
        "negative_silu_count": int(np.count_nonzero(y < 0)),
        "clipped_low_count": int(np.count_nonzero(rounded < 0)),
        "clipped_high_count": int(np.count_nonzero(rounded > 255)),
        "unclipped_count": int(np.count_nonzero(unclipped)),
        "error_units": "output float units; reconstructed u8 minus float64 SiLU",
        "all_codes_error": metrics(error),
        "unclipped_codes_error": metrics(error[unclipped]),
    }
    return table, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-scale", required=True, type=float)
    parser.add_argument("--input-zero-point", required=True, type=int)
    parser.add_argument("--output-scale", required=True, type=float)
    parser.add_argument("--output-zero-point", required=True, type=int)
    parser.add_argument("--hex", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        table, manifest = build_silu_lut(
            args.input_scale, args.input_zero_point,
            args.output_scale, args.output_zero_point)
    except ValueError as exc:
        parser.error(str(exc))
    args.hex.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.hex.write_text("".join("%02x\n" % int(value) for value in table), encoding="ascii")
    args.manifest.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n",
                             encoding="ascii")
    print("GENERATED entries=256 sha256=" + manifest["table_sha256"])
    print("UNCALIBRATED all_codes_error=" + json.dumps(manifest["all_codes_error"]))


if __name__ == "__main__":
    main()
