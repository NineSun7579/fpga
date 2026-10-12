"""Isolated ModelSim integration regression. All writes stay below this directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
SIM = Path(os.environ.get("MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))
SOURCES = [
    PARENT / "raw_preprocess/fpga_v8_raw_letterbox.v",
    PARENT / "raw_preprocess/fpga_v8_rgb888_pack128.v",
    PARENT / "cooperative_axi/fpga_v8_raw_frame_axi.v",
    PARENT / "cooperative_control/fpga_v8_coop_control_axil.v",
    PARENT / "cooperative_arbiter/fpga_v8_ddr_write_arbiter.v",
    ROOT / "fpga_v8_cooperative_core.v",
]
CASES = {
    "leases_4x3": dict(width=4, height=3, out_height=5, top=1, mode=0, bursts=24, seed=12345, outputs=[1, 2, 3]),
    "faults_odd_1x1": dict(width=1, height=1, out_height=6, top=2, mode=1, bursts=24, seed=98765, outputs=[3]),
    "common_reset_5x3": dict(width=5, height=3, out_height=6, top=1, mode=2, bursts=24, seed=54321, outputs=[5]),
    "invalid_output_range": dict(width=4, height=3, out_height=5, top=1, mode=3, bursts=24, seed=24680, outputs=[], bank0="32'h10000000"),
    "full_640x480": dict(width=640, height=480, out_height=640, top=80, mode=4, bursts=512, seed=13579, outputs=[1]),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vectors(case: dict, seq: int) -> tuple[bytes, bytes]:
    # RGB565 source bytes generated independently of the RTL. Vary every frame.
    width, height = case["width"], case["height"]
    source = bytearray()
    body = bytearray()
    for y in range(height):
        for x in range(width):
            p = y * width + x
            red = (p * 7 + seq * 3 + y) % 32
            green = (p * 11 + seq * 5 + x) % 64
            blue = (p * 13 + seq * 9 + y * 3) % 32
            pixel = red * 2048 + green * 32 + blue
            source.extend(pixel.to_bytes(2, "little"))
            body.extend(((red * 8 + red // 4), (green * 4 + green // 16), (blue * 8 + blue // 4)))
    golden = bytes([114]) * (case["top"] * width * 3) + bytes(body)
    golden += bytes([114]) * ((case["out_height"] - height - case["top"]) * width * 3)
    source.extend(bytes([0xD7]) * ((-len(source)) % 16))
    return bytes(source), golden


def hexfile(path: Path, data: bytes) -> None:
    path.write_text("".join(f"{v:02x}\n" for v in data), encoding="ascii")


def camera_golden(bursts: int) -> bytes:
    result = bytearray()
    for owner in range(6):
        for tx in range(bursts):
            beats = (16, 3, 5, 1)[tx % 4]
            for beat in range(16):
                for lane in range(16):
                    result.append((owner * 37 + tx * 19 + beat * 11 + lane * 7) % 256 if beat < beats else 0xA5)
    return bytes(result)


def run_command(argv: list[str], workdir: Path, logname: str, timeout: int = 240) -> None:
    completed = subprocess.run(argv, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    (workdir / logname).write_bytes(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stdout.decode(errors='replace')[-6000:]}")


def trace_audit(path: Path, case: dict) -> dict:
    counts = {"selections": 0, "camera_w_words": 0, "bridge_w_words": 0, "b_responses": 0, "reset_boundaries": 0}
    rr = 0
    active = None
    for line in path.read_text(encoding="ascii").splitlines():
        fields = line.split()
        if fields[0] == "RESET":
            rr = 0
            active = None
            counts["reset_boundaries"] += 1
        elif fields[0] == "SELECT":
            _, cycle, start, mask, selected = fields
            start, mask, selected = int(start), int(mask, 16), int(selected)
            expected = next((rr + offset) % 7 for offset in range(7) if mask & (1 << ((rr + offset) % 7)))
            if start != rr or selected != expected or active is not None:
                raise AssertionError(f"RR/ownership trace mismatch: {line}")
            active = dict(owner=selected, accepted=False, beats=0, count=0)
            counts["selections"] += 1
        elif fields[0] == "AW":
            _, cycle, address, ident, beats = fields
            address, ident, beats = int(address, 16), int(ident), int(beats)
            if active is None or active["accepted"]:
                raise AssertionError(f"AW without selected owner: {line}")
            owner = active["owner"]
            if owner < 6:
                base = 0x01000000 + owner * 0x00100000
                tx = (address - base) // 256
                if address != base + tx * 256 or not 0 <= tx < case["bursts"] or ident != owner + 8 or beats != (16, 3, 5, 1)[tx % 4]:
                    raise AssertionError(f"camera AW mismatch: {line}")
                active["tx"] = tx
            elif ident != 1 or beats != 1:
                raise AssertionError(f"bridge AW mismatch: {line}")
            active.update(accepted=True, beats=beats, ident=ident)
        elif fields[0] == "W":
            _, owner, tx, beat, data, strobe = fields
            owner, tx, beat = int(owner), int(tx), int(beat)
            word, strobe = int(data, 16), int(strobe, 16)  # X/Z is rejected.
            if active is None or not active["accepted"] or active["owner"] != owner or active["count"] != beat:
                raise AssertionError(f"W owner/order mismatch: {line}")
            if owner < 6:
                expected = bytes((owner * 37 + tx * 19 + beat * 11 + lane * 7) % 256 for lane in range(16))
                if tx != active["tx"] or word.to_bytes(16, "little") != expected or strobe != 0xFFFF:
                    raise AssertionError(f"all 128 camera W bits differ: {line}")
                counts["camera_w_words"] += 1
            else:
                counts["bridge_w_words"] += 1
            active["count"] += 1
        elif fields[0] == "B":
            _, owner, ident, response = fields
            owner, ident, response = int(owner), int(ident), int(response)
            if active is None or active["owner"] != owner or ident != active["ident"] or active["count"] != active["beats"]:
                raise AssertionError(f"B ownership/count mismatch: {line}")
            if response and not (case["mode"] == 1 and owner == 6 and response == 2):
                raise AssertionError(f"unexpected B fault: {line}")
            rr = (owner + 1) % 7
            active = None
            counts["b_responses"] += 1
        else:
            raise AssertionError(f"unknown trace record: {line}")
    if active is not None:
        raise AssertionError("unretired owner in final trace")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--small-only", action="store_true")
    parser.add_argument("--case", action="append", choices=CASES)
    args = parser.parse_args()
    names = args.case or list(CASES)
    if args.small_only:
        names = [name for name in names if name != "full_640x480"]
    artifact = ROOT / "artifacts"
    artifact.mkdir(exist_ok=True)
    sources = SOURCES + [ROOT / "tb_fpga_v8_cooperative_core.sv", Path(__file__).resolve()]
    hashes = {str(path.relative_to(PARENT)).replace("\\", "/"): sha(path) for path in sources}
    summary = dict(python=sys.executable, modelsim=str(SIM), source_sha256=hashes, cases=[], scope="isolated behavioral DDR integration; no PDS or board integration")
    for name in names:
        case = CASES[name]
        directory = artifact / name
        directory.mkdir(exist_ok=True)
        for seq in range(1, 6):
            source, golden = vectors(case, seq)
            hexfile(directory / f"source_{seq}.hex", source)
            hexfile(directory / f"golden_{seq}.hex", golden)
        run_command([str(SIM / "vlib.exe"), "work"], directory, "vlib.log")
        # ModelSim 10.6e uses Verilog-2001 by default; only the TB gets -sv.
        compile_rtl = [str(SIM / "vlog.exe"), "-work", "work"] + [str(path) for path in SOURCES]
        compile_tb = [str(SIM / "vlog.exe"), "-work", "work", "-sv", str(ROOT / "tb_fpga_v8_cooperative_core.sv")]
        run_command(compile_rtl, directory, "compile_rtl.log")
        run_command(compile_tb, directory, "compile_tb.log")
        generic = [f"-gWIDTH={case['width']}", f"-gHEIGHT={case['height']}", f"-gOUT_HEIGHT={case['out_height']}",
                   f"-gTOP_ROWS={case['top']}", f"-gMODE={case['mode']}", f"-gCAMERA_BURSTS={case['bursts']}", f"-gSEED={case['seed']}"]
        if "bank0" in case:
            generic.append(f"-gBANK0={case['bank0']}")
        do_text = 'onerror {quit -code 1}\nonbreak {quit -code 0}\nrun -all\nquit -code 0\n'
        (directory / "run.do").write_text(do_text, encoding="ascii")
        sim_args = [str(SIM / "vsim.exe"), "-c", "-onfinish", "stop", "-voptargs=+acc", "-l", "transcript.log"] + generic + ["work.tb_fpga_v8_cooperative_core", "-do", "run.do"]
        started = time.monotonic()
        run_command(sim_args, directory, "console.log", timeout=600)
        log = (directory / "console.log").read_text(errors="replace")
        # A ModelSim $finish break may return zero. Require positive evidence.
        marker = re.search(r"CORE_PASS mode=(\d+) cycles=(\d+) claims=(\d+) releases=(\d+) publishes=(\d+) copied_bytes=(\d+) camera_bursts=(\d+)", log)
        if marker is None or re.search(r"CORE_FAIL|\*\* (?:Error|Fatal):", log):
            raise AssertionError(f"simulation did not pass: {name}\n{log[-5000:]}")
        outputs = []
        for seq in case["outputs"]:
            dump = directory / f"output_{seq}.bin"
            actual = dump.read_bytes()
            expected = vectors(case, seq)[1]
            if actual != expected:
                mismatch = next((index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]), min(len(actual), len(expected)))
                raise AssertionError(f"{name} frame {seq}: full byte compare failed at {mismatch}, lengths {len(actual)}/{len(expected)}")
            outputs.append(dict(seq=seq, compared_bytes=len(actual), sha256=sha(dump)))
        camera_dump = directory / "camera_output.bin"
        if camera_dump.read_bytes() != camera_golden(case["bursts"]):
            raise AssertionError(f"{name}: complete camera DDR bytes/guards differ")
        audit = trace_audit(directory / "trace.txt", case)
        result = dict(name=name, parameters=case, pass_marker=marker.group(0), seconds=round(time.monotonic()-started, 3),
                      outputs=outputs, camera_compared_bytes=camera_dump.stat().st_size, camera_sha256=sha(camera_dump), trace_audit=audit,
                      compile_rtl=compile_rtl, compile_tb=compile_tb, simulation=sim_args)
        summary["cases"].append(result)
        (artifact / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
        print(f"PASS {name}: {sum(o['compared_bytes'] for o in outputs)} output bytes, {audit['camera_w_words']} camera W words, {marker.group(0)}", flush=True)
    # Fail if a cooperating agent changed dependency RTL during the regression.
    after = {str(path.relative_to(PARENT)).replace("\\", "/"): sha(path) for path in sources}
    if after != hashes:
        raise RuntimeError("source hashes changed during regression; rerun against the final dependency files")
    summary["verified_source_hashes_unchanged"] = True
    summary["total_output_compared_bytes"] = sum(o["compared_bytes"] for c in summary["cases"] for o in c["outputs"])
    summary["total_camera_compared_bytes"] = sum(c["camera_compared_bytes"] for c in summary["cases"])
    (artifact / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
