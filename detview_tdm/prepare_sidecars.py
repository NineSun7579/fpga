"""Generate portable sidecars from the actual delivery, without modifying it."""
import argparse
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "sidecars")
    args = parser.parse_args()
    expected = ["person", "vehicle", "zebra", "traffic_light", "traffic_sign"]
    args.output.mkdir(parents=True, exist_ok=True)
    for folder, model in [("MVP_INT8", "MVP_rk3568_int8.rknn"),
                          ("MVP_plus_shared_FP16", "MVP_plus_shared_rk3568_fp16.rknn")]:
        names = json.loads((args.package / folder / "names.json").read_text(encoding="utf-8-sig"))
        if names != expected:
            raise ValueError(f"Unexpected class IDs in {folder}: {names}")
        (args.output / (model + ".names.json")).write_text(json.dumps(names, indent=2) + "\n", encoding="utf-8")
    for folder, metadata, model in [
        ("MVP_plus_shared_FP16", "pipeline.json", "MVP_plus_shared_rk3568_fp16.rknn"),
        ("UFLDv2_independent_FP16", "dataset_summary.json", "lane_ufldv2_480x640_rk3568_fp16.rknn")]:
        data = json.loads((args.package / folder / metadata).read_text(encoding="utf-8-sig"))
        contract = dict(input_hw=[480,640], decode="argmax_endpoint", grid_row=64, grid_col=48,
                        num_lanes=8, row_anchors=data["row_anchors"], col_anchors=data["col_anchors"],
                        source=f"{folder}/{metadata}")
        if len(contract["row_anchors"]) != 24 or len(contract["col_anchors"]) != 32:
            raise ValueError("Unexpected anchor counts")
        (args.output / (model + ".lane.json")).write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared four sidecars in {args.output}")

if __name__ == "__main__":
    main()
