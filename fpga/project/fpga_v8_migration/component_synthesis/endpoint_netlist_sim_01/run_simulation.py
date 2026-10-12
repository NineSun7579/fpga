"""Read-only inputs; independent mapped/RTL wrapper runs with public traces.

Run once in this new evidence directory. No PDS commands or external access.
The existing regression module is imported without executing main or writing pyc.
"""
from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
MIGRATION = HERE.parent.parent
PROJECT = MIGRATION.parent
ORIGINAL = MIGRATION / "cooperative_endpoint"
SYNTH = HERE.parent / "endpoint_ctrl_01"
NETLIST = SYNTH / "synthesize/fpga_v8_endpoint_ctrl_synth_syn.vm"
WRAPPER = SYNTH / "fpga_v8_endpoint_ctrl_synth.v"
ENDPOINT = ORIGINAL / "fpga_v8_coop_axi128_endpoint.v"
CONTROL = MIGRATION / "cooperative_control/fpga_v8_coop_control_axil.v"
MODELS = Path(r"C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation")
SIM = Path(os.environ.get("MODELSIM_BIN", r"C:/modeltech64_10.6e/win64"))
BASE = 0x40010000
PUBLIC = {"AW", "W", "B", "AR", "R", "DESC", "CMD", "RELEASE", "STATE", "RESET"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def protected_paths():
    # Preserve existing component evidence, regression fixtures, and production RTL.
    roots = [ORIGINAL, MIGRATION / "cooperative_control", SYNTH,
             HERE.parent / "endpoint_mapping_audit_01", PROJECT / "source", PROJECT / "DOC"]
    suffixes = {".v", ".sv", ".vh", ".vm", ".md", ".py", ".json", ".txt",
                ".trace", ".csv", ".log", ".fdc", ".pds"}
    paths = {p for root in roots for p in root.rglob("*")
             if p.is_file() and p.suffix.lower() in suffixes and "__pycache__" not in p.parts}
    paths |= {p for p in HERE.parent.iterdir() if p.is_file()}
    return sorted(paths)


def manifest(paths):
    return {str(p.resolve()): sha(p) for p in paths}


def load_regression():
    spec = importlib.util.spec_from_file_location("frozen_endpoint_regression", ORIGINAL / "run_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_suite(regression):
    class WrapperSuite(regression.Suite):
        def partial_reset(self, kind):
            if kind not in (2, 3, 5):
                super().partial_reset(kind)

        def start(self, code, args, label):
            if code == 9:
                label = "80-cycle public B/R hold; no timeout"
            super().start(code, args, label)

        def desc(self, *args, **kwargs):
            super().desc(*args, **kwargs)
            self.ops[-1][1][8] = 13

        def done(self):
            super().done()
            self.ops[-1][1][0] = 17

    suite = WrapperSuite().build()
    reused_operations = len(suite.ops)
    # Byte boundaries, last legal aligned slot, and upper-address non-aliasing.
    suite.reset()
    probes = [BASE - 1, BASE - 16, BASE, BASE + 0xff0, BASE + 0xfff,
              BASE + 0x1000, BASE + 0x1010, 0, 0x40000000, 0x40020000,
              0x50010000, 0x80010000, 0xffff0000, 0xfffffff0, 0xffffffff]
    for address in probes:
        suite.read(0, addr=address, label=f"boundary/high read {address:08x}")
        suite.write(0, 0x5a5a1234, addr=address, label=f"boundary/high write {address:08x}")
    for misalignment in range(1, 16):
        suite.read(0, addr=BASE + misalignment, label=f"misalignment {misalignment} read")
        suite.write(0, 1, addr=BASE + 0x130 + misalignment,
                    label=f"misalignment {misalignment} ACK doorbell")
    # Size 6 supplements the original size 0,1,2,3,5,7 probes.
    suite.read(0, size=6, label="size 6 rejected read")
    suite.write(0x4c, 1, size=6, label="size 6 rejected ACK")
    # Invalid high addresses with meaningful low CLAIM/ACK bits and a live bank.
    suite.desc(0x01400000, 0xcafebabe, 0x89abcdef, 7, 1, 0xfedc0123456789ab)
    suite.done()
    for address in (0x400110c0, 0x400200c0, 0x500100c0, 0x800100c0, 0xffff00c0):
        suite.write(0, 0, addr=address, label=f"invalid high CLAIM {address:08x}")
        suite.read(4, label="invalid CLAIM preserves READY")
        suite.read(0x54, label="invalid CLAIM does not increment controller counter")
    suite.write(0x30, 0, label="valid CLAIM after high-address probes")
    for offset, word in ((0x40, 0), (0x44, 0xcafebabe), (0x48, 0x89abcdef)):
        suite.write(offset, word)
    for address in (0x3fff0130, 0x40011130, 0x40020130, 0x50010130, 0x80010130, 0xffff0130):
        suite.write(0, 1, addr=address, label=f"invalid high ACK {address:08x}")
        suite.read(4, label="invalid ACK preserves HOST_READING")
        suite.read(0x50, label="invalid ACK does not increment controller counter")
        suite.read(0x10, label="invalid ACK preserves descriptor")
    suite.write(0x4c, 1, label="valid ACK after high-address probes")
    suite.read(4)
    suite.nextid = 0
    for ident in range(128):
        suite.write(0x40, ident, hold=2, order=ident % 3,
                    label=f"all seven B ID bits {ident:02x}")
    expected = {key: values for key, values in suite.expected.items() if key[1] in PUBLIC}
    return suite, expected, reused_operations, probes


def official_models():
    net = NETLIST.read_bytes()
    names = set(re.findall(rb"\b(GTP_\w+)\s", net))
    # Explicit dependencies of the official LUT6D / LUT / carry models.
    names |= {b"GTP_MUX2LUT6", b"INT_LUTMUX2_UDP", b"INT_LUTMUX4_UDP"}
    files = [MODELS / (name.decode("ascii") + ".v") for name in sorted(names)]
    assert all(p.is_file() for p in files)
    stripped = re.sub(rb"/\*.*?\*/|//[^\n]*", b"", net, flags=re.S)
    counts = collections.Counter(x.decode("ascii") for x in re.findall(rb"\b(GTP_\w+)\s", stripped))
    return files, dict(counts)


def run_tool(folder, index, command, commands):
    command = [str(x) for x in command]
    commands.append({"cwd": str(folder), "argv": command})
    completed = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=120)
    text = completed.stdout + completed.stderr
    (folder / f"tool_{index}.log").write_text(text, encoding="utf-8")
    commands[-1]["returncode"] = completed.returncode
    if completed.returncode or "** Error" in text or "** Fatal" in text:
        raise RuntimeError(f"tool failed; see {folder}/tool_{index}.log")
    return text


def run_variant(name, sources, stimulus, models, commands):
    folder = HERE / name
    assert not folder.exists(), f"Refusing to overwrite evidence: {folder}"
    folder.mkdir()
    (folder / "stimulus.txt").write_text(stimulus, encoding="ascii")
    run_tool(folder, 0, [SIM / "vlib.exe", "work"], commands)
    run_tool(folder, 1, [SIM / "vlog.exe", "-work", "work", *models, *sources], commands)
    run_tool(folder, 2, [SIM / "vlog.exe", "-sv", "-work", "work", HERE / "tb_endpoint_wrapper.sv"], commands)
    text = run_tool(folder, 3, [SIM / "vsim.exe", "-c", "-onfinish", "stop",
                   "work.tb_endpoint_wrapper", "-do", "run -all; quit -f"], commands)
    match = re.search(r"WRAPPER_TB_COMPLETE ops=(\d+) cycles=(\d+) protocol_errors=(\d+) "
                      r"B_stall=(\d+) R_stall=(\d+) CMD_stall=(\d+) RELEASE_stall=(\d+) "
                      r"claims=(\d+) rejects=(\d+)", text)
    assert match, f"Simulation did not complete: {folder}"
    result = dict(zip(("operations", "cycles", "protocol_errors", "b_stall_cycles", "r_stall_cycles",
                       "cmd_stall_cycles", "release_stall_cycles", "claims", "rejects"), map(int, match.groups())))
    result["actual_sha256"] = sha(folder / "actual.trace")
    result["stimulus_sha256"] = sha(folder / "stimulus.txt")
    return result


def read_trace(path):
    result = collections.defaultdict(list)
    for line in path.read_text().splitlines():
        fields = line.split()
        # Keep X/Z values observable in comparisons rather than coercing to zero.
        values = tuple(int(x, 16) if not re.search("[xz]", x.lower()) else x.lower() for x in fields[2:])
        result[(int(fields[0]), fields[1])].append(values)
    return result


def compare(left, right, labels, filename):
    differences = []
    passing = 0
    for key in sorted(set(left) | set(right)):
        if left.get(key, []) != right.get(key, []):
            differences.append({"operation": key[0], "label": labels[key[0]], "channel": key[1],
                                "expected": left.get(key, []), "actual": right.get(key, [])})
        else:
            passing += 1
    save(HERE / filename, {"passing_operation_channel_groups": passing,
                          "failing_operation_channel_groups": len(differences), "differences": differences})
    failed_ops = sorted({d["operation"] for d in differences})
    return {"status": "FAIL" if differences else "PASS", "passing_groups": passing,
            "failing_groups": len(differences), "passing_operations": len(labels) - len(failed_ops),
            "failing_operations": len(failed_ops), "failed_operation_numbers": failed_ops,
            "detail_file": filename}


def trace_stats(trace):
    counts = collections.Counter()
    for (_, channel), values in trace.items():
        counts[channel] += len(values)
    return {"events": sum(counts.values()), "channel_counts": dict(sorted(counts.items())),
            "b_ids": sorted({v[0] for (op, ch), values in trace.items() if ch == "B" for v in values}),
            "r_ids": sorted({v[0] for (op, ch), values in trace.items() if ch == "R" for v in values})}


def main():
    assert not (HERE / "results.json").exists(), "Refusing to overwrite completed evidence"
    paths = protected_paths()
    before = manifest(paths)
    save(HERE / "protected_before.json", before)
    commands = []
    try:
        regression = load_regression()
        original_suite = regression.Suite().build()
        suite, expected, reused, probes = build_suite(regression)
        stimulus = "".join(str(code) + " " + " ".join(f"{v:x}" for v in args) + "\n" for code, args in suite.ops)
        (HERE / "stimulus.txt").write_text(stimulus, encoding="ascii")
        (HERE / "expected_public.trace").write_text("".join(f"{op} {ch}" + "".join(f" {v:x}" for v in event) + "\n"
            for (op, ch), values in expected.items() for event in values), encoding="ascii")
        save(HERE / "operation_labels.json", suite.labels)
        model_files, cell_counts = official_models()
        save(HERE / "official_models.json", {"installation": str(MODELS),
             "netlist_cell_instances": cell_counts,
             "files": [{"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in model_files]})
        rtl = run_variant("rtl", [CONTROL, ENDPOINT, WRAPPER], stimulus, [], commands)
        mapped = run_variant("mapped", [NETLIST], stimulus, model_files, commands)
        rtl_trace = read_trace(HERE / "rtl/actual.trace")
        mapped_trace = read_trace(HERE / "mapped/actual.trace")
        rtl.update(trace_stats(rtl_trace))
        mapped.update(trace_stats(mapped_trace))
        comparisons = {
            "rtl_vs_oracle": compare(expected, rtl_trace, suite.labels, "rtl_vs_oracle.json"),
            "mapped_vs_oracle": compare(expected, mapped_trace, suite.labels, "mapped_vs_oracle.json"),
            "mapped_vs_rtl": compare(rtl_trace, mapped_trace, suite.labels, "mapped_vs_rtl.json")}
        result = {"status": "PASS" if all(x["status"] == "PASS" for x in comparisons.values())
                  and not rtl["protocol_errors"] and not mapped["protocol_errors"] else "FAIL",
                  "scope": "existing connected synthesis top; independent functional RTL and mapped simulations",
                  "original_operations": len(original_suite.ops), "adapted_regression_operations": reused,
                  "additional_operations": len(suite.ops) - reused, "operations": len(suite.ops),
                  "omitted_internal_reset_kinds": [2, 3, 5], "boundary_read_addresses": [f"{x:08x}" for x in probes],
                  "rtl": rtl, "mapped": mapped, "comparisons": comparisons,
                  "inputs": {str(p): sha(p) for p in [NETLIST, WRAPPER, ENDPOINT, CONTROL,
                      ORIGINAL / "run_tests.py", ORIGINAL / "tb_fpga_v8_coop_axi128_endpoint.sv",
                      HERE / "run_simulation.py", HERE / "tb_endpoint_wrapper.sv"]},
                  "expected_public_sha256": sha(HERE / "expected_public.trace")}
        save(HERE / "results.json", result)
        print(json.dumps({k: result[k] for k in ("status", "operations", "rtl", "mapped", "comparisons")}, indent=2))
    finally:
        save(HERE / "commands.json", commands)
        after = manifest(paths)
        save(HERE / "protected_after.json", after)
        changed = [p for p in before if before[p] != after[p]]
        save(HERE / "preservation.json", {"protected_existing_files": len(paths),
             "changed": changed, "status": "PASS" if not changed else "FAIL"})
        assert not changed, f"Existing protected files changed: {changed}"


if __name__ == "__main__":
    main()
