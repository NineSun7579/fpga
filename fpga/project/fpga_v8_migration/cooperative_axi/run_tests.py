"""Run the isolated AXI candidate in ModelSim against independent Python bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
SHARED = ROOT.parent / "raw_preprocess"
MODELSIM = Path(os.environ.get("MODELSIM_BIN", r"C:\modeltech64_10.6e\win64"))


def golden(width: int, height: int, out_height: int, top: int, seed: int):
    # Pure byte arithmetic, independent of the Verilog and shared golden.py.
    src = bytearray()
    rgb = bytearray()
    for pixel in range(width * height):
        value = ((pixel * 173 + seed * 7919) ^ (pixel >> 3) ^ 0x5A3C) & 0xFFFF
        src.extend((value & 255, value >> 8))
        red = (value >> 11) & 31
        green = (value >> 5) & 63
        blue = value & 31
        rgb.extend(((red << 3) | (red >> 2), (green << 2) | (green >> 4),
                    (blue << 3) | (blue >> 2)))
    # Poison unused source lanes: an incorrect final-beat pixel count fails.
    src.extend([0xD7] * ((-len(src)) % 16))
    result = (bytes([114]) * (width * top * 3) + rgb +
              bytes([114]) * (width * (out_height - top - height) * 3))
    return bytes(src), bytes(result)


def write_hex(path: Path, data: bytes):
    path.write_text("".join(f"{byte:02x}\n" for byte in data), encoding="ascii")


def run(command: list[str], cwd: Path, timeout: int = 240):
    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    (cwd / (Path(command[0]).stem + "_console.log")).write_text(
        result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {command}\n"
                           f"{result.stdout[-10000:]}\n{result.stderr[-2000:]}")
    return time.perf_counter() - start


def run_case(name: str, geometry: tuple[int, int, int, int], full: bool,
             id_width: int = 4, axi_id: int = 1, limit: int = 0x10000000):
    case = ROOT / "artifacts" / name
    vectors = case / "vectors"
    output = case / "output"
    vectors.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    for old in output.glob("output_*.hex"):
        old.unlink()
    seeds = range(1 if full else 16)
    expected = {}
    for seed in seeds:
        source, wanted = golden(*geometry, seed)
        write_hex(vectors / f"source_{seed}.hex", source)
        write_hex(vectors / f"expected_{seed}.hex", wanted)
        expected[seed] = wanted
    if not (case / "work").exists():
        run([str(MODELSIM / "vlib.exe"), "work"], case)
    compile_command = [str(MODELSIM / "vlog.exe"), "-sv", "-work", "work",
                       str(SHARED / "fpga_v8_raw_letterbox.v"),
                       str(SHARED / "fpga_v8_rgb888_pack128.v"),
                       str(ROOT / "fpga_v8_raw_frame_axi.v"),
                       str(ROOT / "tb_fpga_v8_raw_frame_axi.v")]
    run(compile_command, case)
    do_file = case / "run.do"
    do_file.write_text("onerror {quit -code 1}\nonbreak {quit -code 0}\n"
                       "run -all\nquit -code 0\n", encoding="ascii")
    command = [str(MODELSIM / "vsim.exe"), "-c", "-onfinish", "stop",
               "-l", str(case / "transcript.log"), "-do", str(do_file),
               "work.tb_fpga_v8_raw_frame_axi"]
    for param, value in zip(("WIDTH", "HEIGHT", "OUT_HEIGHT", "TOP_ROWS"), geometry):
        command.append(f"-g{param}={value}")
    command.extend((f"-gFULL={int(full)}", f"-gID_WIDTH={id_width}", f"-gAXI_ID={axi_id}",
                    f"-gDDR_ADDRESS_LIMIT={limit}",
                    f"+VECTORS={vectors.as_posix()}", f"+OUTPUT={output.as_posix()}"))
    seconds = run(command, case)
    transcript = (case / "transcript.log").read_text(encoding="utf-8", errors="replace")
    if "AXI_RAW_PASS" not in transcript or "** Error" in transcript or "** Fatal" in transcript:
        raise AssertionError(f"Missing pass / simulator error: {name}\n{transcript[-10000:]}")
    compared = []
    for seed, wanted in expected.items():
        actual = bytes.fromhex((output / f"output_{seed}.hex").read_text(encoding="ascii"))
        if actual != wanted:
            raise AssertionError(f"Python byte comparison failed: {name}, seed={seed}")
        compared.append({"seed": seed, "bytes": len(actual),
                         "sha256": hashlib.sha256(actual).hexdigest()})
    markers = [line.removeprefix("# ") for line in transcript.splitlines()
               if "FRAME_PASS" in line or "RESET_PASS" in line or "AXI_RAW_PASS" in line
               or "ADDRESS_REJECT_PASS" in line]
    if not full and sum("ADDRESS_REJECT_PASS" in line for line in markers) != 15:
        raise AssertionError(f"Missing address rejection coverage: {name}")
    print(f"PASS {name}: {len(compared)} frames, {sum(x['bytes'] for x in compared)} bytes, "
          f"{seconds:.2f}s", flush=True)
    return {"name": name, "geometry": geometry, "id_width": id_width, "axi_id": axi_id,
            "ddr_address_limit": f"0x{limit:08x}",
            "simulation_seconds": round(seconds, 3), "compile_command": compile_command,
            "simulation_command": command, "compared": compared, "markers": markers}


def run_config():
    case = ROOT / "artifacts" / "invalid_config"
    case.mkdir(parents=True, exist_ok=True)
    if not (case / "work").exists():
        run([str(MODELSIM / "vlib.exe"), "work"], case)
    compile_command = [str(MODELSIM / "vlog.exe"), "-sv", "-work", "work",
                       str(SHARED / "fpga_v8_raw_letterbox.v"),
                       str(SHARED / "fpga_v8_rgb888_pack128.v"),
                       str(ROOT / "fpga_v8_raw_frame_axi.v"),
                       str(ROOT / "tb_fpga_v8_raw_axi_config.v")]
    run(compile_command, case)
    do_file = case / "run.do"
    do_file.write_text("onerror {quit -code 1}\nonbreak {quit -code 0}\n"
                       "run -all\nquit -code 0\n", encoding="ascii")
    command = [str(MODELSIM / "vsim.exe"), "-c", "-onfinish", "stop", "-l",
               str(case / "transcript.log"), "-do", str(do_file), "work.tb_fpga_v8_raw_axi_config"]
    seconds = run(command, case)
    transcript = (case / "transcript.log").read_text(encoding="utf-8", errors="replace")
    if "AXI_CONFIG_PASS cases=8" not in transcript or "** Error" in transcript or "** Fatal" in transcript:
        raise AssertionError(f"Configuration test failed\n{transcript[-10000:]}")
    print(f"PASS invalid_config: 8 parameter rejections, {seconds:.2f}s", flush=True)
    return {"cases": 8, "simulation_seconds": round(seconds, 3),
            "compile_command": compile_command, "simulation_command": command,
            "markers": [line.removeprefix("# ") for line in transcript.splitlines()
                        if "CONFIG_REJECT_PASS" in line or "AXI_CONFIG_PASS" in line]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--small-only", action="store_true")
    args = parser.parse_args()
    source_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (ROOT / "fpga_v8_raw_frame_axi.v", ROOT / "tb_fpga_v8_raw_frame_axi.v",
                               ROOT / "tb_fpga_v8_raw_axi_config.v", ROOT / "run_tests.py")}
    shared_before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (SHARED / "fpga_v8_raw_letterbox.v", SHARED / "fpga_v8_rgb888_pack128.v")}
    results = [run_case("small_4x3", (4, 3, 5, 1), False),
               run_case("overflow_1x1", (1, 1, 6, 2), False, 3, 3),
               run_case("smaller_limit_4x3", (4, 3, 5, 1), False, limit=0x02000000)]
    if not args.small_only:
        results.append(run_case("full_640x480", (640, 480, 640, 80), True))
    config_result = run_config()
    shared_after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (SHARED / "fpga_v8_raw_letterbox.v", SHARED / "fpga_v8_rgb888_pack128.v")}
    if shared_before != shared_after:
        raise AssertionError("Shared RTL changed during this run; rerun against the final API.")
    source_after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (ROOT / "fpga_v8_raw_frame_axi.v", ROOT / "tb_fpga_v8_raw_frame_axi.v",
                              ROOT / "tb_fpga_v8_raw_axi_config.v", ROOT / "run_tests.py")}
    if source_before != source_after:
        raise AssertionError("Candidate RTL/test sources changed during this run.")
    report = {"status": "PASS", "modelsim_bin": str(MODELSIM),
              "tested_module": "fpga_v8_raw_frame_axi",
              "tested_rtl_sha256": source_after["fpga_v8_raw_frame_axi.v"],
              "source_sha256": source_after,
              "default_ddr_address_limit": "0x10000000",
              "maximum_ddr_address_limit": "0x10000000",
              "promotion_status": "promoted_original_name",
              "component_synthesis_status": "stale_before_address_fix_rerun_required",
              "stale_component_synthesis_rtl_sha256":
                  "235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40",
              "shared_rtl_sha256": shared_after, "cases": results,
              "configuration_test": config_result,
              "total_frames": sum(len(x["compared"]) for x in results),
              "total_rejected_address_commands": sum(
                  "ADDRESS_REJECT_PASS" in marker for case in results for marker in case["markers"]),
              "total_compared_bytes": sum(f["bytes"] for x in results for f in x["compared"])}
    report_path = ROOT / "artifacts" / "results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(f"PASS report: {report_path}")


if __name__ == "__main__":
    main()
