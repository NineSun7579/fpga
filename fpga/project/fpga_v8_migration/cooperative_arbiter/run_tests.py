"""Isolated, actual ModelSim regression and independent all-byte trace oracle."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
RTL = ROOT / "fpga_v8_ddr_write_arbiter.v"
TB = ROOT / "tb_fpga_v8_ddr_write_arbiter.sv"
LEGACY = ROOT.parents[1] / "source" / "axi_crossbar" / "ddr_w_arb.v"
CASES = [
    ("rr_seed_12345", 0, 12345),
    ("rr_seed_67891", 0, 67891),
    ("rr_seed_314159", 0, 314159),
    ("late_contender", 1, 90210),
    ("protocol_faults", 2, 20260929),
    ("common_reset", 3, 424242),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def burst_length(case: int, txn: int) -> int:
    if case in (2, 3):
        return 16
    return 256 if txn == 31 else (1, 2, 16)[txn % 3]


def descriptor(case: int, master: int, txn: int) -> list[int]:
    length = burst_length(case, txn)
    return [
        9 if txn < 16 else master + 1,
        0x100000 + master * 0x100000 + txn * 8192,
        length - 1,
        4,
        2 if length not in (1, 256) and (master + txn) % 2 else 1,
        (master + txn) % 2,
        (master + txn) & 15,
        (master ^ txn) & 7,
        (master * 3 + txn) & 15,
        (master * 5 + txn) & 15,
    ]


def golden_bytes(master: int, txn: int, beat: int) -> bytes:
    return bytes(
        ((master * 37 + txn * 19 + beat * 11 + lane * 7) ^ (0xA5 + lane)) & 255
        for lane in range(16)
    )


def golden_strobe(master: int, txn: int, beat: int) -> int:
    if (master + txn + beat) % 4 == 0:
        return 0xFFFF
    return (0xF3C5 ^ (master * 257 + txn * 17 + beat * 13)) & 0xFFFF


def golden_last(case: int, master: int, txn: int, beat: int) -> int:
    if case == 2:
        if master in (2, 5) and beat == 0:
            return 1
        if master in (3, 5) and beat == burst_length(case, txn) - 1:
            return 0
    return int(beat == burst_length(case, txn) - 1)


def check_trace(path: Path, case: int) -> dict:
    active = None
    sequence = [0] * 7
    order = []
    reset_orders = []
    resets = aborted = aw = beats = retired = strobed = 0
    compared = hashlib.sha256()
    with path.open(newline="", encoding="ascii") as handle:
        for row_number, row in enumerate(csv.reader(handle), 1):
            where = f"{path.name}:{row_number}"
            require(bool(row), f"{where}: empty trace row")
            kind = row[0]
            if kind == "R":
                require(len(row) == 2, f"{where}: malformed reset")
                int(row[1])
                if active is not None:
                    aborted += 1
                if resets:
                    reset_orders.append(order)
                order = []
                sequence = [0] * 7
                active = None
                resets += 1
                continue
            require(resets > 0, f"{where}: no initial reset")
            master, txn = map(int, row[1:3])
            require(0 <= master < 7, f"{where}: invalid master")
            require(txn == sequence[master], f"{where}: transaction skipped/repeated")
            if kind == "A":
                require(len(row) == 13 and active is None, f"{where}: overlapping/malformed AW")
                actual = [int(value, 16 if index == 1 else 10)
                          for index, value in enumerate(row[3:])]
                require(actual == descriptor(case, master, txn), f"{where}: full AW mismatch")
                active = [master, txn, 0]
                order.append(master)
                aw += 1
            elif kind == "W":
                require(len(row) == 7 and active is not None, f"{where}: W before AW")
                beat = int(row[3])
                require(active == [master, txn, beat], f"{where}: owner/beat order mismatch")
                require(beat < burst_length(case, txn), f"{where}: extra W accepted")
                # int(..., 16) rejects any X/Z. Compare all 16 lanes, including
                # unstrobed lanes, rather than suppressing unknown bytes.
                actual_bytes = int(row[4], 16).to_bytes(16, "little")
                expected_bytes = golden_bytes(master, txn, beat)
                require(actual_bytes == expected_bytes, f"{where}: 128-bit W bytes mismatch")
                strobe = int(row[5], 16)
                require(strobe == golden_strobe(master, txn, beat), f"{where}: WSTRB mismatch")
                require(int(row[6]) == golden_last(case, master, txn, beat), f"{where}: WLAST mismatch")
                strobed += strobe.bit_count()
                compared.update(actual_bytes)
                active[2] += 1
                beats += 1
            elif kind == "B":
                require(len(row) == 5 and active is not None, f"{where}: unexpected B")
                require(active == [master, txn, burst_length(case, txn)], f"{where}: early B retirement")
                bid = descriptor(case, master, txn)[0]
                resp = 0
                if case == 2:
                    if master in (0, 5):
                        bid ^= 15
                    resp = 2 if master == 1 else 3 if master == 5 else 0
                require([int(row[3]), int(row[4])] == [bid, resp], f"{where}: response rewritten")
                sequence[master] += 1
                retired += 1
                active = None
            else:
                raise AssertionError(f"{where}: unknown trace type {kind}")
    require(active is None, "unfinished transaction after final simulation pass")
    reset_orders.append(order)
    if case == 0:
        require(resets == 1 and order == list(range(7)) * 32, "repeated RR order mismatch")
        require(sequence == [32] * 7 and retired == 224, "not 32 transactions per writer")
        require(beats == 3129, "missing 1/2/16/256-beat burst coverage")
    elif case == 1:
        require(order == [6, 0] and retired == 2, "late contender stole latched AW")
    elif case == 2:
        require(order == list(range(7)) and retired == 7, "error draining/recovery order mismatch")
    elif case == 3:
        require(resets == 10 and retired == 35, "reset/restart count mismatch")
        require(aborted == 4, "expected four accepted transactions aborted by common reset")
        for phase, phase_order in enumerate(reset_orders):
            expected_order = ([] if phase == 0 else [0]) if phase % 2 == 0 else list(range(7))
            require(phase_order == expected_order, "reset-phase grant/restart mismatch")
    return {"aw": aw, "w": beats, "b": retired, "compared_bytes": beats * 16,
            "strobed_bytes": strobed, "resets": resets, "aborted_aw": aborted,
            "compared_byte_sha256": compared.hexdigest(), "trace_sha256": digest(path)}


def run(command: list[str], cwd: Path, log_name: str) -> dict:
    start = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=90)
    output = completed.stdout + completed.stderr
    (cwd / log_name).write_text(output, encoding="utf-8")
    require(completed.returncode == 0, f"{log_name}: exit {completed.returncode}\n{output[-4000:]}")
    require(not re.search(r"\*\*\s+(?:Error|Fatal):|\bFAIL\b", output),
            f"{log_name}: simulator error\n{output[-4000:]}")
    return {"command": command, "cwd": str(cwd), "log": str(cwd / log_name),
            "seconds": round(time.monotonic() - start, 3), "output": output}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[case[0] for case in CASES], action="append")
    args = parser.parse_args()
    selected = [case for case in CASES if not args.case or case[0] in args.case]
    binary_dir = Path(os.environ.get("MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))
    binaries = {name: binary_dir / f"{name}.exe" for name in ("vlib", "vlog", "vsim")}
    for name, binary in binaries.items():
        require(binary.is_file(), f"missing actual ModelSim {name}: {binary}")
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    input_hashes = {str(path): digest(path) for path in (RTL, TB, Path(__file__), LEGACY)}
    results = {"status": "running", "simulator": "ModelSim", "inputs_sha256": input_hashes,
               "scope": "cooperative_arbiter only; no PDS/board/cooperative_axi edits", "cases": []}
    output_path = artifacts / "results.json"
    try:
        for name, case, seed in selected:
            directory = artifacts / name
            directory.mkdir(exist_ok=True)
            (directory / "trace.csv").unlink(missing_ok=True)
            do_file = directory / "run.do"
            do_file.write_text(
                "onerror {quit -f -code 1}\n"
                f"vsim -onfinish stop -gCASE_ID={case} -gSEED={seed} "
                "work.tb_fpga_v8_ddr_write_arbiter +TRACE=trace.csv\n"
                "run -all\nquit -f -code 0\n", encoding="ascii")
            commands = []
            for command, log_name in [
                ([str(binaries["vlib"]), "work"], "vlib.log"),
                ([str(binaries["vlog"]), "-sv", "-work", "work", str(RTL), str(TB)], "vlog.log"),
                ([str(binaries["vsim"]), "-c", "-l", "transcript.log", "-do", "run.do"], "console.log"),
            ]:
                record = run(command, directory, log_name)
                console = record.pop("output")
                commands.append(record)
            marker = f"PASS fpga_v8_ddr_write_arbiter case={case} seed={seed}"
            require(marker in console, f"{name}: no explicit completion marker")
            metric_match = re.search(r"METRICS ([^\r\n]+)", console)
            require(metric_match is not None, f"{name}: missing scoreboard metrics")
            metrics = {key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", metric_match[1])}
            evidence = check_trace(directory / "trace.csv", case)
            require(all(metrics[key] == evidence[key] for key in ("aw", "w", "b")),
                    f"{name}: trace and simulation counters differ")
            require(metrics["bytes"] == evidence["compared_bytes"], f"{name}: byte counts differ")
            require(metrics["flags"] == (31 if case == 2 else 0), f"{name}: unexpected sticky errors")
            results["cases"].append({"name": name, "case_id": case, "seed": seed,
                                     "pass_marker": marker, "metrics": metrics,
                                     "python_oracle": evidence, "commands": commands})
            print(f"PASS {name}: {evidence['b']} retired, {evidence['compared_bytes']} bytes compared", flush=True)
        require(all(digest(Path(path)) == value for path, value in input_hashes.items()),
                "an input changed during simulation")
        results["status"] = "passed"
        results["total_retired"] = sum(case["metrics"]["b"] for case in results["cases"])
        results["total_compared_bytes"] = sum(case["python_oracle"]["compared_bytes"] for case in results["cases"])
    except Exception as exc:
        results["status"] = "failed"
        results["failure"] = str(exc)
        raise
    finally:
        output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
