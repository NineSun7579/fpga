"""Independent mapped eligibility tests and frozen-source integrity evidence."""
from collections import Counter, defaultdict
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import subprocess
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parent
MIGRATION = ROOT.parent
MODELS = Path(r"C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation")
SIM = Path(r"C:/modeltech64_10.6e/win64")
ENDPOINT = MIGRATION / "cooperative_endpoint/fpga_v8_coop_axi128_endpoint.v"
ORIGINAL_SHA = "5ea714da5ed63168615f0f9162cb6a773a5ef5780f6fa5a33e2c3fce7cfafc1e"


def stamp():
    return datetime.datetime.now().astimezone().isoformat()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def digest(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def inventory():
    return [digest(path) for path in sorted(ROOT.rglob("*")) if path.is_file()
        and path.relative_to(ROOT).parts[0] != WORK.name]


def check_pds(label):
    command = ["powershell.exe", "-NoProfile", "-Command",
        "$mapAuditProcesses=@(Get-Process pds,pds_shell -ErrorAction SilentlyContinue | "
        "Select-Object Id,ProcessName,Path); ConvertTo-Json -InputObject $mapAuditProcesses -Compress"]
    completed = subprocess.run(command, cwd=WORK, capture_output=True, text=True, check=True)
    result = {"timestamp": stamp(), "command": command,
        "processes": json.loads(completed.stdout.strip() or "[]"), "stderr": completed.stderr}
    save(WORK / f"process_check_{label}.json", result)
    assert not result["processes"], "BLOCKED: PDS GUI/shell exists; no process was changed"


def before():
    assert not (WORK / "history_before.json").exists(), "Initial evidence already exists"
    check_pds("initial")
    assert digest(ENDPOINT)["sha256"] == ORIGINAL_SHA
    save(WORK / "history_before.json", {"timestamp": stamp(), "files": inventory()})
    paths = [ENDPOINT, MIGRATION / "cooperative_control/fpga_v8_coop_control_axil.v"]
    paths += [MIGRATION / "cooperative_endpoint" / name for name in
        ["run_tests.py", "tb_fpga_v8_coop_axi128_endpoint.sv", "REPORT.md",
         "artifacts/expected.trace", "artifacts/stimulus.txt", "artifacts/results.json"]]
    save(WORK / "sources_before.json", {"timestamp": stamp(), "files": [digest(p) for p in paths]})
    warn = ROOT / "endpoint_ctrl_01/diagnostics_extracted.txt"
    lines = [line for line in warn.read_text(encoding="utf-8").splitlines() if "Verilog-2021" in line]
    save(WORK / "warning_input.json", {"warning_lines": lines, "original_endpoint": digest(ENDPOINT),
        "existing_netlist": digest(ROOT / "endpoint_ctrl_01/synthesize/fpga_v8_endpoint_ctrl_synth_syn.vm"),
        "source_assignment_exists": "addr_end = {1'b0, addr} + 33'd16;" in ENDPOINT.read_text(encoding="ascii")})
    print("Original endpoint pinned; all previous component evidence and frozen 419-suite files snapshotted.")


def vectors():
    result = []
    # Independent scalar contract; no expression copied from the RTL function.
    def add(addr, length=0, size=4, burst=1, mode=0):
        result.append((addr & 0xffffffff, length, size, burst, mode))
    for addr in [0, 0x40010000-16, 0x40010000-1, 0x40010000, 0x40010ff0,
        0x40010ff1, 0x40010fff, 0x40011000, 0x40011010, 0xffffffe0, 0xfffffff0, 0xffffffff]:
        for burst in [0, 1]: add(addr, burst=burst)
    # Every byte in and around the window, followed by thousands of arbitrary aligned addresses.
    for delta in range(-32, 4096+32): add(0x40010000+delta, burst=(delta & 1))
    rng = random.Random(0x13d1e7)
    for _ in range(6000): add(rng.getrandbits(32) & ~15)
    for bit in range(32):
        add(0x40010000 ^ (1 << bit));add(0x40010ff0 ^ (1 << bit))
    for addr in [0x40010000, 0x40010ff0, 0x40011000, 0xfffffff0]:
        for size in range(8): add(addr, size=size)
        for burst in range(4): add(addr, burst=burst)
        for length in [1,2,3,15,16,31,127,255]: add(addr, length=length)
    for mode in [1,2]:
        for length in [0,1,15]: add(0x40010000, length=length, mode=mode)
    return result


def prepare_stimulus(folder):
    cases = vectors()
    stimulus, expected, counts = [], [], Counter()
    for op, (addr, length, size, burst, mode) in enumerate(cases, 1):
        ident = (op * 37) & 127
        eligible = int(length == 0 and size == 4 and burst in [0,1]
            and addr % 16 == 0 and 0x40010000 <= addr <= 0x40010ff0)
        write_ok = eligible and mode != 1
        stimulus.append(f"{addr:08x} {length} {size} {burst} {ident} {mode} {op%3} {op%4} {int(write_ok)}\n")
        expected.append(f"{op} B {ident:x} {0 if write_ok else 2:x}\n")
        for beat in range(length+1):
            data = (0x6a19c4e7 ^ ((addr-0x40010000)//4)) if eligible else 0
            expected.append(f"{op} R {ident:x} {data:x} {0 if eligible else 2:x} {int(beat==length):x}\n")
        expected.append(f"{op} LOCAL {int(write_ok)} {int(write_ok)} {eligible}\n")
        counts.update(B=1,R=length+1,local_AW=int(write_ok),local_W=int(write_ok),local_AR=eligible)
    (folder / "stimulus.txt").write_text("".join(stimulus), encoding="ascii")
    (folder / "expected.trace").write_text("".join(expected), encoding="ascii")
    return {"operations": len(cases), "counts": dict(counts), "seed": "0x13d1e7",
        "address_test_vectors": len(cases), "write_and_read_transactions": 2*len(cases)}


def tool(folder, index, command, timeout=120):
    start = stamp()
    done = subprocess.run([str(x) for x in command], cwd=folder, capture_output=True, timeout=timeout)
    text = (done.stdout+done.stderr).decode("utf-8",errors="backslashreplace")
    (folder / f"tool_{index}.log").write_text(text, encoding="utf-8")
    record = {"command": [str(x) for x in command], "cwd": str(folder), "started": start,
        "finished": stamp(), "returncode": done.returncode}
    save(folder / f"command_{index}.json", record)
    if done.returncode or "** Error" in text or "** Fatal" in text or "FATAL:" in text:
        raise RuntimeError("Tool failure; see " + str(folder / f"tool_{index}.log"))
    return text


def vendor_files(netlist):
    cells = set(re.findall(rb"\b(GTP_\w+)\s", netlist.read_bytes()))
    cells |= {f"GTP_LUT{i}".encode("ascii") for i in range(1,7)}
    cells |= {b"GTP_MUX2LUT6",b"INT_LUTMUX2_UDP",b"INT_LUTMUX4_UDP"}
    return [MODELS / (name.decode("ascii") + ".v") for name in sorted(cells)]


def leaf(mode):
    folder = WORK / ("leaf_" + mode)
    if folder.exists():
        folder = WORK / ("leaf_" + mode + "_02")
    assert not folder.exists(), "Refusing to overwrite simulation evidence"
    folder.mkdir()
    plan = prepare_stimulus(folder)
    mapped = WORK / "synthesize/fpga_v8_coop_axi128_endpoint_syn.vm"
    source = ENDPOINT if mode == "rtl" else mapped
    models = [] if mode == "rtl" else vendor_files(mapped)
    save(folder / "inputs.json", {"timestamp": stamp(), "mode": mode, "plan": plan,
        "sources": [digest(p) for p in [source,WORK / "tb_mapping_leaf.sv"] + models]})
    tool(folder,0,[SIM / "vlib.exe","work"])
    tool(folder,1,[SIM / "vlog.exe","-work","work"] + models + [source])
    tool(folder,2,[SIM / "vlog.exe","-sv","-work","work",WORK / "tb_mapping_leaf.sv"])
    log = tool(folder,3,[SIM / "vsim.exe","-c","-onfinish","stop","work.tb_mapping_leaf",
        "-do","run -all; quit -f"],timeout=240)
    assert "MAPPING_LEAF_PASS" in log, "No leaf PASS marker"
    actual = (folder / "actual.trace").read_text().splitlines()
    expected = (folder / "expected.trace").read_text().splitlines()
    canonical = lambda lines: [(int(f[0]),f[1],tuple(int(v,16) for v in f[2:]))
        for f in (line.split() for line in lines)]
    mismatches = []
    a, e = canonical(actual), canonical(expected)
    if a != e:
        mismatches = [f"line {i+1}: expected {x} actual {y}" for i,(x,y) in enumerate(zip(e,a)) if x != y][:20]
        if len(a) != len(e):mismatches.append(f"event counts {len(e)}/{len(a)}")
    (folder / "comparison.txt").write_text("\n".join(mismatches) if mismatches else "PASS: all independent expected events match exactly.\n")
    assert not mismatches, "Independent leaf oracle mismatch"
    coverage = re.search(r"MAPPING_LEAF_PASS ops=(\d+) local_AW=(\d+) local_W=(\d+) local_AR=(\d+) B=(\d+) R=(\d+) cycles=(\d+)",log)
    result = {"status": "PASS", "mode": mode, "operations": int(coverage[1]),
        "counts": dict(zip(["local_AW","local_W","local_AR","B","R"],map(int,coverage.groups()[1:6]))),
        "cycles": int(coverage[7]), "exact_events": len(actual), "source": digest(source),
        "actual_trace": digest(folder / "actual.trace"), "expected_trace": digest(folder / "expected.trace")}
    assert result["operations"] == plan["operations"] and result["counts"] == plan["counts"]
    save(folder / "results.json", result)
    print(json.dumps(result,indent=2))


def integrity():
    previous = json.loads((WORK / "history_before.json").read_text())["files"]
    pinned = json.loads((WORK / "sources_before.json").read_text())["files"]
    result = {"timestamp": stamp(), "all_previous_component_files_unchanged": inventory() == previous,
        "historical_file_count": len(previous),
        "frozen_source_and_regression_files_unchanged": all(digest(Path(p["path"])) == p for p in pinned),
        "original_endpoint_sha256": digest(ENDPOINT)["sha256"]}
    check_pds("after_integrity")
    save(WORK / "integrity_after.json", result)
    print(json.dumps(result,indent=2))
    assert result["all_previous_component_files_unchanged"] and result["frozen_source_and_regression_files_unchanged"]


def regression():
    folder = WORK / "frozen_419_mapped_leaf"
    assert not folder.exists(), "Refusing to overwrite regression evidence"
    folder.mkdir()
    old = MIGRATION / "cooperative_endpoint"
    for name in ["stimulus.txt","expected.trace"]:
        (folder / name).write_bytes((old / "artifacts" / name).read_bytes())
    tb = (old / "tb_fpga_v8_coop_axi128_endpoint.sv").read_bytes()
    tb = tb.replace(b"module tb_fpga_v8_coop_axi128_endpoint;",b"module tb_frozen_419_mapped_leaf;")
    (folder / "tb_frozen_419_mapped_leaf.sv").write_bytes(tb)
    source = WORK / "synthesize/fpga_v8_coop_axi128_endpoint_syn.vm"
    control = MIGRATION / "cooperative_control/fpga_v8_coop_control_axil.v"
    models = vendor_files(source)
    save(folder / "inputs.json", {"sources": [digest(p) for p in [source,control,folder / "tb_frozen_419_mapped_leaf.sv"] + models],
        "adaptation": "Only testbench top module name changed. All 419 stimulus operations, expected events, gates, assertions and comparisons unchanged."})
    tool(folder,0,[SIM / "vlib.exe","work"])
    tool(folder,1,[SIM / "vlog.exe","-work","work"] + models + [control,source])
    tool(folder,2,[SIM / "vlog.exe","-sv","-work","work",folder / "tb_frozen_419_mapped_leaf.sv"])
    log = tool(folder,3,[SIM / "vsim.exe","-c","-onfinish","stop","work.tb_frozen_419_mapped_leaf",
        "-do","run -all; quit -f"],timeout=240)
    assert "ENDPOINT_TB_PASS" in log
    events = lambda path: [(int(f[0]),f[1],tuple(int(v,16) for v in f[2:])) for f in
        (line.split() for line in path.read_text().splitlines())]
    actual, expected = defaultdict(list), defaultdict(list)
    for op,ch,data in events(folder / "actual.trace"): actual[(op,ch)].append(data)
    for op,ch,data in events(folder / "expected.trace"): expected[(op,ch)].append(data)
    mismatch = [str(k) for k in set(actual)|set(expected) if actual[k] != expected[k]]
    (folder / "comparison.txt").write_text("FAIL " + str(mismatch) if mismatch else "PASS: unchanged exact per-operation/channel oracle, all 419 operations / 3803 events.\n")
    assert not mismatch
    result = {"status": "PASS", "operations": len({op for op,ch in actual}),
        "exact_events": sum(map(len,actual.values())),
        "channel_counts": dict(Counter(ch for (op,ch),values in actual.items() for _ in values)),
        "actual_trace": digest(folder / "actual.trace"),"expected_trace": digest(folder / "expected.trace"),
        "limit": "Mapped standalone endpoint plus unchanged RTL controller with original testbench gates; distinct from old connected mapped top"}
    assert result["operations"] == 419 and result["exact_events"] == 3803
    save(folder / "results.json",result)
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "before": before()
    elif command in ["rtl","mapped"]: leaf(command)
    elif command == "integrity": integrity()
    elif command == "regression": regression()
    else: raise RuntimeError("Unknown operation")
