"""Add class coverage to retained reports without rerunning unchanged inference."""

import argparse
import json
from pathlib import Path


def update(directory):
    path = directory / "summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    names = ("zebra", "vehicle", "person")
    counts = {name: {"float_boxes": 0, "integer_boxes": 0, "matched": 0,
                     "unmatched_float": 0, "unmatched_integer": 0} for name in names}
    for row in summary["frames"]:
        report = json.loads((directory / row["report"]).read_text(encoding="utf-8"))
        reference, candidate = report["float_detections"], report["integer_detections"]
        comparison = report["detection_comparison"]
        for box in reference:
            counts[names[int(box[5])]]["float_boxes"] += 1
        for box in candidate:
            counts[names[int(box[5])]]["integer_boxes"] += 1
        for match in comparison["matches"]:
            counts[names[int(reference[match["float_index"]][5])]]["matched"] += 1
        for index in comparison["unmatched_float"]:
            counts[names[int(reference[index][5])]]["unmatched_float"] += 1
        for index in comparison["unmatched_integer"]:
            counts[names[int(candidate[index][5])]]["unmatched_integer"] += 1
    for field in ("float_boxes", "integer_boxes", "unmatched_float", "unmatched_integer"):
        if sum(value[field] for value in counts.values()) != summary["summary"][field]:
            raise ValueError("Retained reports disagree with aggregate counts")
    summary["per_class"] = counts
    summary["limits"].append("Class coverage is predicted-box coverage; this set has no annotated ground truth")
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("EVALUATION_CLASS_COVERAGE", directory.name, json.dumps(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    update(args.directory)
