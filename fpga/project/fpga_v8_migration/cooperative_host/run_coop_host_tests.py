"""Compile the C++17 helper and replay its clean fixture through existing RTL.

All outputs are local. No device, driver, PDS, or board operations are performed.
The sibling endpoint sources/map/testbench are read once, never modified or polled.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections import defaultdict

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
ENDPOINT = HERE.parent / "cooperative_endpoint"
CONTROL = HERE.parent / "cooperative_control" / "fpga_v8_coop_control_axil.v"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, *, cwd=HERE, timeout=120):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    text = result.stdout + result.stderr
    (ART / log).write_text(text, encoding="utf-8")
    if result.returncode or "** Error" in text or "** Fatal" in text:
        raise RuntimeError(f"command failed ({result.returncode}): {command}\n{text}")
    return text


def main():
    ART.mkdir(exist_ok=True)
    sources = [HERE / "coop_host_protocol.hpp", HERE / "coop_host_selftest.cpp",
               HERE / "run_coop_host_tests.py", HERE / "build_local_selftest.cmd"]
    dependencies = [ENDPOINT / "register_map.json", ENDPOINT / "run_tests.py",
                    ENDPOINT / "fpga_v8_coop_axi128_endpoint.v",
                    ENDPOINT / "tb_fpga_v8_coop_axi128_endpoint.sv", CONTROL]
    before = {str(p): sha(p) for p in sources + dependencies if p.exists()}
    commands = []
    cxx = os.environ.get("COOP_HOST_CXX") or shutil.which("g++")
    binary = ART / ("coop_host_selftest.exe" if os.name == "nt" else "coop_host_selftest")
    if cxx:
        command = [cxx, "--version"]
        commands.append(command)
        version = run(command, "compiler_version.txt")
        command = [cxx, "-std=c++17", "-O2", "-pthread", "-Wall", "-Wextra", "-Werror", "-pedantic",
                   str(HERE / "coop_host_selftest.cpp"), "-o", str(binary)]
        commands.append(command)
        run(command, "compile.txt")
    elif os.name == "nt":
        command = ["cmd.exe", "/d", "/c", str(HERE / "build_local_selftest.cmd")]
        commands.append(command)
        version = run(command, "compile.txt")
        (ART / "compiler_version.txt").write_text(version, encoding="utf-8")
    else:
        raise RuntimeError("No C++17 compiler; provide COOP_HOST_CXX=g++ path")

    command = [str(binary), "--fixture", str(ART / "host.fixture")]
    commands.append(command)
    stdout = run(command, "selftest.txt")
    marker = re.search(r"COOP_HOST_PASS cases=(\d+) checks=(\d+) writes=(\d+) reads=(\d+) dma=(\d+)", stdout)
    assert marker, stdout
    counts = dict(zip(("cases", "checks", "writes", "reads", "dma"), map(int, marker.groups())))
    command = [str(binary), "--map"]
    commands.append(command)
    mapping_stdout = run(command, "host_map.txt")
    declared = {name: (int(local, 16), int(physical, 16))
                for name, local, physical in (line.split() for line in mapping_stdout.splitlines())}
    mapping = json.loads((ENDPOINT / "register_map.json").read_bytes())
    expected_mapping = {r["name"]: (int(r["local_offset"], 16), int(r["physical_address"], 16))
                        for r in mapping["registers"]}
    assert declared == expected_mapping
    assert int(mapping["base_address"], 16) == 0x40010000
    assert mapping["physical_slot_bytes"] == mapping["dma_bytes"] == 16
    assert mapping["dma_len"] == 0 and mapping["dma_size"] == 4

    # Reuse the endpoint's public transaction harness in a LOCAL work directory.
    # Its independent Python FIFO model validates the C++ fake's observations,
    # and ModelSim validates these same operations against the actual candidates.
    spec = importlib.util.spec_from_file_location("coop_host_endpoint_fixture", ENDPOINT / "run_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = module.Suite()
    suite.reset()
    fixture_counts = defaultdict(int)
    for line in (ART / "host.fixture").read_text().splitlines():
        code, *fields = line.split()
        values = [int(v, 16) for v in fields]
        fixture_counts[code] += 1
        if code == "P":
            src, seq, gen, camera, source_bank, token, output_bank = values
            suite.desc(src, seq, gen, camera, source_bank, token)
            assert suite.model.active == output_bank
            suite.done()
        elif code in ("R", "W"):
            physical, value, response = values
            assert physical % 16 == 0 and 0x40010000 <= physical < 0x40011000
            local = (physical - 0x40010000) // 4
            if code == "R":
                assert suite.model.read(local) == (value, response), line
                suite.read(local, label="C++ helper observed read")
            else:
                suite.write(local, value, strb=0xffff, label="C++ helper singleton write")
                assert suite.expected[(suite.op, "B")][-1][1] == response, line
        else:
            raise AssertionError(line)
    assert fixture_counts["P"] == 3 and fixture_counts["W"] == 15
    assert suite.model.host is None and suite.model.banks == [0, 0]
    (ART / "stimulus.txt").write_text("".join(str(code) + " " + " ".join(f"{v:x}" for v in args) + "\n"
                                                for code, args in suite.ops), encoding="ascii")
    (ART / "expected.trace").write_text("".join(f"{op} {channel}" +
        "".join(f" {value:x}" for value in event) + "\n"
        for (op, channel), events in suite.expected.items() for event in events), encoding="ascii")
    sim = Path(os.environ.get("MODELSIM_BIN", r"C:\modeltech64_10.6e\win64"))
    tool_suffix = ".exe" if os.name == "nt" else ""
    simulator_commands = [
        [str(sim / ("vlib" + tool_suffix)), "work"],
        [str(sim / ("vlog" + tool_suffix)), "-work", "work", str(CONTROL),
         str(ENDPOINT / "fpga_v8_coop_axi128_endpoint.v")],
        [str(sim / ("vlog" + tool_suffix)), "-sv", "-work", "work",
         str(ENDPOINT / "tb_fpga_v8_coop_axi128_endpoint.sv")],
        [str(sim / ("vsim" + tool_suffix)), "-c", "-onfinish", "stop",
         "work.tb_fpga_v8_coop_axi128_endpoint", "-do", "run -all; quit -f"],
    ]
    crossfixture = {"registers_checked": len(declared), "fixture_counts": dict(fixture_counts),
                    "operations": len(suite.ops), "python_model": "PASS"}
    if (sim / ("vsim" + tool_suffix)).exists():
        if (ART / "work").exists():
            shutil.rmtree(ART / "work")
        logs = []
        for i, command in enumerate(simulator_commands):
            commands.append(command)
            logs.append(run(command, f"modelsim_{i}.txt", cwd=ART))
        assert "ENDPOINT_TB_PASS" in logs[-1], logs[-1]
        actual = defaultdict(list)
        for line in (ART / "actual.trace").read_text().splitlines():
            fields = line.split()
            actual[(int(fields[0]), fields[1])].append(tuple(int(v, 16) for v in fields[2:]))
        mismatches = [key for key in set(actual) | set(suite.expected) if actual[key] != suite.expected[key]]
        assert not mismatches, mismatches
        events = sum(len(v) for v in actual.values())
        crossfixture.update(modelsim="PASS", public_events=events)
        (ART / "comparison.txt").write_text(f"PASS: {events} public events match C++ fixture / Python model.\n")
    else:
        crossfixture["modelsim"] = "UNAVAILABLE (no RTL simulation claimed)"
    after = {str(p): sha(p) for p in sources + dependencies if p.exists()}
    assert before == after, "Source/dependency changed during run; rerun against a stable snapshot"
    artifacts = [binary, ART / "host.fixture", ART / "selftest.txt", ART / "host_map.txt",
                 ART / "compiler_version.txt", ART / "compile.txt", ART / "expected.trace"]
    if crossfixture.get("modelsim") == "PASS": artifacts.append(ART / "actual.trace")
    report = dict(status="PASS", scope="host fake contracts and local candidate RTL fixture; no physical DMA/DDR",
                  compiler_version=version, commands=commands, counts=counts, crossfixture=crossfixture,
                  source_sha256=before, artifacts_sha256={str(p): sha(p) for p in artifacts})
    (ART / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(stdout, end="")
    print(json.dumps(dict(status=report["status"], counts=counts, crossfixture=crossfixture), indent=2))


if __name__ == "__main__":
    main()
