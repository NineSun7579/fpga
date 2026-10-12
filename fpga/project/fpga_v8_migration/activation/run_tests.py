"""Run isolated NumPy and ModelSim regression; all outputs stay in activation."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path,
                        default=Path("C:/modeltech64_10.6e/win64"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    evidence = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "modelsim_bin": str(args.modelsim_bin.resolve()),
        "scope": "isolated activation only; no PDS, board, NPU integration, or calibration",
        "commands": [],
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(root.iterdir())
                          if path.is_file() and path.suffix in (".v", ".py")},
    }
    report_path = artifacts / "test_results.json"

    def run(label, command, cwd=artifacts):
        command = [str(part) for part in command]
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, errors="replace", timeout=90)
        output = result.stdout + result.stderr
        (artifacts / (label + ".log")).write_text(output, encoding="ascii", errors="backslashreplace")
        evidence["commands"].append({"label": label, "argv": command,
                                     "cwd": str(cwd), "returncode": result.returncode,
                                     "log": label + ".log"})
        print("COMMAND " + label + " returncode=" + str(result.returncode))
        print(output.rstrip())
        if result.returncode:
            raise RuntimeError(label + " failed with exit code " + str(result.returncode))
        return output

    try:
        for tool in ("vlib.exe", "vlog.exe", "vsim.exe"):
            if not (args.modelsim_bin / tool).is_file():
                raise RuntimeError("Missing ModelSim binary: " + tool)
        run("generator_tests", [sys.executable, "-m", "unittest", "-v", "test_generate_silu_lut"], root)
        cases = (("a", "0.0625", "128", "0.03125", "16"),
                 ("b", "0.125", "80", "0.05", "120"))
        tables = []
        manifests = []
        for name, in_scale, in_zp, out_scale, out_zp in cases:
            run("generate_" + name, [sys.executable, root / "generate_silu_lut.py",
                                     "--input-scale", in_scale, "--input-zero-point", in_zp,
                                     "--output-scale", out_scale, "--output-zero-point", out_zp,
                                     "--hex", artifacts / ("table_" + name + ".hex"),
                                     "--manifest", artifacts / ("table_" + name + ".json")])
            tables.append(bytes(int(line, 16) for line in
                                (artifacts / ("table_" + name + ".hex")).read_text().splitlines()))
            manifests.append(json.loads((artifacts / ("table_" + name + ".json")).read_text()))
        difference = sum(a != b for a, b in zip(*tables))
        if difference < 200:
            raise RuntimeError("Test tables are insufficiently different")
        evidence["table_differing_entries"] = difference
        evidence["tables"] = manifests
        print("TABLE_DIFFERENCE differing_entries=" + str(difference) + "/256")
        if not (artifacts / "work").exists():
            run("vlib", [args.modelsim_bin / "vlib.exe", "work"])
        run("vlog", [args.modelsim_bin / "vlog.exe", "-work", "work",
                     root / "fpga_v8_activation_lut.v", root / "tb_fpga_v8_activation_lut.v"])
        runs = []
        for lanes, seed in ((1, 20260929), (3, 17320508), (16, 31415926), (16, 27182818)):
            label = "vsim_lanes_%d_seed_%d" % (lanes, seed)
            output = run(label, [args.modelsim_bin / "vsim.exe", "-c", "-onfinish", "stop",
                                 "-gLANES=" + str(lanes), "work.tb_fpga_v8_activation_lut",
                                 "+seed=" + str(seed), "-do", "run -all; quit -f"])
            expected = "PASS fpga_v8_activation_lut LANES=%d seed=%d" % (lanes, seed)
            if expected not in output or re.search(r"\bFAIL\b|\*\*\s+(Error|Fatal):", output):
                raise RuntimeError(label + " did not pass the scoreboard")
            summary = [line.removeprefix("# ") for line in output.splitlines()
                       if any(token in line for token in ("COVERAGE ", "COUNTERS ", "PASS "))]
            runs.append({"lanes": lanes, "seed": seed, "summary": summary, "log": label + ".log"})
        evidence["simulations"] = runs
        evidence["status"] = "PASS"
        print("PASS isolated regression: 4 generator tests, 4 ModelSim simulations")
    except Exception as exc:
        evidence["status"] = "FAIL"
        evidence["error"] = str(exc)
        print("FAIL isolated regression: " + str(exc), file=sys.stderr)
        raise
    finally:
        report_path.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="ascii")
        print("EVIDENCE " + str(report_path))


if __name__ == "__main__":
    main()
