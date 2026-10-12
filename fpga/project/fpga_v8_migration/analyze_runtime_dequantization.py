"""Audit observed same-run conversion bits against two explicit formulas.

Missing codes are reported as unobserved; this is not generic RKNN API behavior.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import struct

import numpy as np


def bits(value):
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def analyze(directory):
    mapping_path = directory / "pipeline_mapping.csv"
    metadata_path = directory / "pipeline_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata["raw_changed_after_float_get"] or metadata["codes_with_multiple_float_values"]:
        raise ValueError("Same-run conversion is not a deterministic code mapping")
    rows = list(csv.DictReader(mapping_path.open(encoding="utf-8", newline="")))
    heads = []
    total_mismatches, total_count = 0, 0
    for name in ("box_p3", "box_p4", "box_p5", "cls_p3", "cls_p4", "cls_p5"):
        subset = [row for row in rows if row["head"] == name]
        if not subset:
            raise ValueError("Missing head " + name)
        scale, zp = np.float32(subset[0]["scale"]), int(subset[0]["zp"])
        offset = np.float32(-np.float32(zp) * scale)
        observed = set()
        mismatches = []
        for row in subset:
            q = int(row["code"])
            if q != (int(row["byte"]) if int(row["byte"]) < 128 else int(row["byte"]) - 256):
                raise ValueError("Signed byte/code mismatch")
            if name.endswith("p5"):
                # Integer q has at most 8 bits; float32 scale/offset at most 24.
                # Their exact product/sum fits float64 here, followed by one f32 rounding.
                expected = np.float32(float(q) * float(scale) + float(offset))
            else:
                expected = np.float32(q - zp) * np.float32(np.float16(scale))
            if bits(expected) != int(row["runtime_bits"]):
                mismatches.append({"byte": int(row["byte"]), "expected_bits": bits(expected),
                                   "runtime_bits": int(row["runtime_bits"])})
            observed.add(int(row["byte"]))
            total_count += int(row["count"])
        total_mismatches += len(mismatches)
        heads.append({"name": name, "type": "int8", "zp": zp, "queried_scale_bits": bits(scale),
                      "rounded_fp16_scale_bits": bits(np.float32(np.float16(scale))),
                      "formula": "fma(float(q),scale,round_float32(-zp*scale))" if name.endswith("p5")
                                 else "float(q-zp)*float(round_float16_RNE(scale))",
                      "observed_codes": len(observed), "unobserved_bytes": sorted(set(range(256)) - observed),
                      "mismatches": mismatches})
    if total_count != metadata["elements"]:
        raise ValueError("Mapping counts do not equal captured full output count")
    result = {"status": "PASS" if total_mismatches == 0 else "FAIL",
              "model_sha256": metadata["model_sha256"], "runtime_library": metadata["runtime_library"],
              "session": metadata["session"], "same_completed_run": metadata["same_completed_run"],
              "mapping_sha256": hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
              "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
              "elements": total_count, "heads": heads, "mismatched_observed_code_pairs": total_mismatches,
              "limits": ["Only this pinned model and runtime build were observed",
                         "Unobserved codes are explicit; formulas are derived and need decoder/full-frame parity",
                         "Mathematical affine quantization remains the default decoder contract",
                         "No FPGA arithmetic or generic RKNN conversion assertion"]}
    (directory / "conversion_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("RUNTIME_CONVERSION_AUDIT", result["status"], "elements", total_count,
          "observed_code_pairs", sum(head["observed_codes"] for head in heads), "mismatches", total_mismatches)
    if total_mismatches:
        raise ValueError("Runtime formula mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    analyze(args.directory)
