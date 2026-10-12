"""Generate model-specific LUT preparation assets from smoke calibration."""

import argparse
import hashlib
import json
from pathlib import Path

from activation.generate_silu_lut import build_silu_lut


def export(calibration, output_dir):
    manifest = json.loads(calibration.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = []
    for conv in manifest["convolutions"]:
        if conv["activation"] != "silu":
            continue
        input_q, output_q = conv["preactivation_quantization"], conv["output_quantization"]
        table, details = build_silu_lut(input_q["scale"], input_q["zero_point"],
                                        output_q["scale"], output_q["zero_point"])
        stem = f"task_{conv['task_id']:03d}_silu"
        (output_dir / (stem + ".bin")).write_bytes(table.tobytes())
        (output_dir / (stem + ".hex")).write_text("".join(f"{code:02x}\n" for code in table), encoding="ascii")
        details.update({"task_id": conv["task_id"], "node": conv["name"],
                        "calibration_status": "16-road-frame development smoke calibration; not accuracy acceptance",
                        "source_model_sha256": manifest["model_sha256"],
                        "calibration_sha256": hashlib.sha256(calibration.read_bytes()).hexdigest()})
        (output_dir / (stem + ".json")).write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
        tables.append({"task_id": conv["task_id"], "node": conv["name"], "binary": stem + ".bin",
                       "sha256": details["table_sha256"], "negative_silu_count": details["negative_silu_count"],
                       "clipped_high_count": details["clipped_high_count"],
                       "max_error": details["all_codes_error"]["max_abs"]})
    result = {"status": "model_specific_smoke_LUT_assets_not_connected_to_NPU",
              "table_count": len(tables), "total_table_bytes": len(tables) * 256, "tables": tables}
    (output_dir / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("SILU_TABLE_EXPORT_PASS", len(tables), "tables", result["total_table_bytes"], "bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("calibration", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    export(args.calibration, args.out)
