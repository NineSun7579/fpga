"""Audit retained board counts/parity/provenance, without rerunning inference."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def audit(directory):
    source_path = directory / "pipeline_source.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    manifest = json.loads((directory / "experiment_manifest.json").read_text(encoding="utf-8"))
    samples = list(csv.DictReader((directory / "pipeline_block_samples.csv").open(encoding="utf-8", newline="")))
    parity = list(csv.DictReader((directory / "pipeline_parity.csv").open(encoding="utf-8", newline="")))
    if not manifest.get("completed") or manifest["benchmark_return_code"]:
        raise ValueError("Benchmark did not exit successfully")
    if source["model"]["verified_sha256"] != "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9":
        raise ValueError("Wrong RKNN model")
    if source["runtime_library"]["sha256"] != "73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885":
        raise ValueError("Wrong runtime library")
    totals = source["totals"]
    if not totals["semantic_compatibility_pass"] or not totals["exact_scalar_pass"] or totals["cleanup_errors"]:
        raise ValueError("Compatibility or cleanup failed")
    if not parity or any(row["pass"] != "1" or row["invalid_lhs"] != "0" or row["invalid_rhs"] != "0" for row in parity):
        raise ValueError("A retained parity row failed")
    for profile, key in (("baseline_runtime_float_production", "baseline"), ("native_quantized", "native")):
        actual = [row for row in samples if row["profile"] == profile]
        expected = totals[key]["timed_completions"]
        if len(actual) != expected:
            raise ValueError("Completion count differs from recorded samples")
        block_ids = set(row["block"] for row in actual)
        if len(block_ids) != totals[key]["blocks"]:
            raise ValueError("Missing profile block")
        for block_id in block_ids:
            rows = [row for row in actual if row["block"] == block_id]
            if sorted(int(row["completion"]) for row in rows) != list(range(len(rows))):
                raise ValueError("Completion sequence is incomplete or repeated")
        if len(set(row["input_sha256"] for row in actual)) != 30:
            raise ValueError("Expected 30 prepared inputs")
    if totals["baseline"]["timed_completions"] != totals["native"]["timed_completions"]:
        raise ValueError("Profiles have different completed workloads")
    pairs = [row for row in parity if row["scope"] == "timed"]
    if len(pairs) != totals["native"]["timed_completions"]:
        raise ValueError("Missing timed input/result pairs")
    for row in pairs:
        for profile in ("baseline_runtime_float_production", "native_quantized"):
            sample = [s for s in samples if s["profile"] == profile and s["round"] == row["round"]
                      and s["cycle"] == row["cycle"] and s["frame"] == row["frame"]]
            if len(sample) != 1 or sample[0]["input_sha256"] != row["input_sha256"]:
                raise ValueError("Pair refers to a different or missing input")
    files = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "evidence_audit.json":
            files.append({"name": path.name, "bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    result = {"status": "PASS", "model_sha256": source["model"]["verified_sha256"],
              "profile_timed_completions": totals["native"]["timed_completions"],
              "total_parity_rows": len(parity), "timed_pairs": len(pairs),
              "baseline_completed_fps": totals["baseline"]["completed_fps"],
              "native_completed_fps": totals["native"]["completed_fps"],
              "fps_ratio": totals["native_over_baseline_fps_ratio"], "files": files,
              "limits": ["Inputs were retained original images loaded before timing",
                         "Includes CPU preprocessing, RKNN input/run/get/decode/release and owned results",
                         "Excludes camera/PCIe acquisition, display and FPGA preprocessing",
                         "Viewer stayed running; NPU exclusivity was not assumed",
                         "Does not constitute deployment, model accuracy or FPGA acceleration acceptance"]}
    (directory / "evidence_audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PIPELINE_EVIDENCE_AUDIT_PASS", "timed_pairs", len(pairs), "fps_ratio", result["fps_ratio"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    audit(args.directory)
