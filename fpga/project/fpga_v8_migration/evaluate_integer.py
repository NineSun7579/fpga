"""Compare candidate Q16 outputs on a hash-disjoint, unlabelled retained set."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from integer_reference import run


def evaluate(tasks, numeric, model, frames, output):
    manifest_path = frames / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["calibration_hash_overlap_count"]:
        raise ValueError("Evaluation frames overlap development calibration by file hash")
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    matches = []
    float_total, integer_total, missing, additional = 0, 0, 0, 0
    per_class = {name: {"float_boxes": 0, "integer_boxes": 0, "matched": 0,
                        "unmatched_float": 0, "unmatched_integer": 0}
                 for name in ("zebra", "vehicle", "person")}
    class_names = list(per_class)
    for index, row in enumerate(manifest["images"]):
        path = frames / row["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Evaluation frame changed since capture")
        report = run(tasks, numeric, path, output / f"frame_{index:03d}", model, quiet=True)
        comparison = report["detection_comparison"]
        matches.extend(comparison["matches"])
        float_total += len(report["float_detections"])
        integer_total += len(report["integer_detections"])
        missing += len(comparison["unmatched_float"])
        additional += len(comparison["unmatched_integer"])
        reference, candidate = report["float_detections"], report["integer_detections"]
        for box in reference:
            per_class[class_names[int(box[5])]]["float_boxes"] += 1
        for box in candidate:
            per_class[class_names[int(box[5])]]["integer_boxes"] += 1
        for match in comparison["matches"]:
            per_class[class_names[int(reference[match["float_index"]][5])]]["matched"] += 1
        for box_index in comparison["unmatched_float"]:
            per_class[class_names[int(reference[box_index][5])]]["unmatched_float"] += 1
        for box_index in comparison["unmatched_integer"]:
            per_class[class_names[int(candidate[box_index][5])]]["unmatched_integer"] += 1
        reports.append({"image": row["path"], "sha256": row["sha256"],
                        "float_boxes": len(report["float_detections"]),
                        "integer_boxes": len(report["integer_detections"]),
                        "comparison": comparison,
                        "report": f"frame_{index:03d}/report.json"})
        print("EVALUATION_FRAME", index, row["path"], "unmatched", len(comparison["unmatched_float"]),
              len(comparison["unmatched_integer"]), flush=True)
    ious = [match["iou"] for match in matches]
    coordinate_errors = [match["max_coordinate_error"] for match in matches]
    result = {"status": "unlabelled_float_parity_diagnostic_not_mAP_or_FPGA_acceptance",
              "frames": reports, "frame_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "per_class": per_class,
              "summary": {"frames": len(reports), "float_boxes": float_total, "integer_boxes": integer_total,
                          "matched_at_iou_0_5": len(matches), "unmatched_float": missing,
                          "unmatched_integer": additional, "minimum_matched_iou": min(ious) if ious else None,
                          "mean_matched_iou": float(np.mean(ious)) if ious else None,
                          "max_matched_coordinate_error": max(coordinate_errors) if coordinate_errors else None},
              "limits": ["file-hash independence does not establish scene independence",
                         "class-aware float ONNX decoder used consistently for both outputs",
                         "not a comparison against RKNN quantization or production NMS semantics",
                         "no labels, per-class mAP or FPGA hardware execution"]}
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("INTEGER_EVALUATION_COMPLETE", json.dumps(result["summary"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("numeric", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evaluate(args.tasks, args.numeric, args.model, args.frames, args.out)
