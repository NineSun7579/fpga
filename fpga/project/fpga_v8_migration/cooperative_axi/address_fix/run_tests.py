"""Test the staged physical-limit RTL without changing the synthesis input."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parent
spec = importlib.util.spec_from_file_location("axi_original_golden", PARENT / "run_tests.py")
original_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original_tests)
golden = original_tests.golden
write_hex = original_tests.write_hex
run = original_tests.run
MODELSIM = original_tests.MODELSIM
SHARED = original_tests.SHARED
RTL = ROOT / "fpga_v8_raw_frame_axi_physical.v"
ORIGINAL_HASH = "235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40"


def compile_and_simulate(case: Path, tb_name: str, args: list[str]):
    case.mkdir(parents=True, exist_ok=True)
    if not (case / "work").exists():
        run([str(MODELSIM / "vlib.exe"), "work"], case)
    compile_command = [str(MODELSIM / "vlog.exe"), "-sv", "-work", "work",
                       str(SHARED / "fpga_v8_raw_letterbox.v"),
                       str(SHARED / "fpga_v8_rgb888_pack128.v"),
                       str(RTL), str(ROOT / f"{tb_name}.v")]
    run(compile_command, case)
    do_file = case / "run.do"
    do_file.write_text("onerror {quit -code 1}\nonbreak {quit -code 0}\n"
                       "run -all\nquit -code 0\n", encoding="ascii")
    command = [str(MODELSIM / "vsim.exe"), "-c", "-onfinish", "stop", "-l",
               str(case / "transcript.log"), "-do", str(do_file), f"work.{tb_name}", *args]
    seconds = run(command, case)
    transcript = (case / "transcript.log").read_text(encoding="utf-8", errors="replace")
    if "** Error" in transcript or "** Fatal" in transcript:
        raise AssertionError(f"Simulator error: {case.name}\n{transcript[-10000:]}")
    return {"simulation_seconds": round(seconds, 3), "compile_command": compile_command,
            "simulation_command": command}, transcript


def run_case(name: str, geometry: tuple[int, int, int, int], full: bool,
             id_width: int = 4, axi_id: int = 1, limit: int = 0x10000000):
    case = ROOT / "artifacts" / name
    vectors = case / "vectors"
    output = case / "output"
    vectors.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    for old in output.glob("output_*.hex"):
        old.unlink()
    expected = {}
    for seed in range(1 if full else 16):
        source, wanted = golden(*geometry, seed)
        write_hex(vectors / f"source_{seed}.hex", source)
        write_hex(vectors / f"expected_{seed}.hex", wanted)
        expected[seed] = wanted
    args = [f"-g{param}={value}" for param, value in
            zip(("WIDTH", "HEIGHT", "OUT_HEIGHT", "TOP_ROWS"), geometry)]
    args.extend((f"-gFULL={int(full)}", f"-gID_WIDTH={id_width}", f"-gAXI_ID={axi_id}",
                 f"-gDDR_ADDRESS_LIMIT={limit}",
                 f"+VECTORS={vectors.as_posix()}", f"+OUTPUT={output.as_posix()}"))
    detail, transcript = compile_and_simulate(case, "tb_fpga_v8_raw_frame_axi_physical", args)
    if "AXI_RAW_PHYSICAL_PASS" not in transcript:
        raise AssertionError(f"Missing pass: {name}\n{transcript[-10000:]}")
    compared = []
    for seed, wanted in expected.items():
        actual = bytes.fromhex((output / f"output_{seed}.hex").read_text(encoding="ascii"))
        if actual != wanted:
            raise AssertionError(f"Python byte comparison failed: {name}, seed={seed}")
        compared.append({"seed": seed, "bytes": len(actual),
                         "sha256": hashlib.sha256(actual).hexdigest()})
    markers = [line.removeprefix("# ") for line in transcript.splitlines()
               if any(marker in line for marker in ("FRAME_PASS", "RESET_PASS", "AXI_RAW_PHYSICAL_PASS",
                                                    "ADDRESS_REJECT_PASS"))]
    rejections = [line for line in markers if "ADDRESS_REJECT_PASS" in line]
    if not full and len(rejections) != 15:
        raise AssertionError(f"Missing address rejection coverage: {name}")
    print(f"PASS {name}: {len(compared)} frames, {sum(x['bytes'] for x in compared)} bytes, "
          f"{len(rejections)} rejected commands, {detail['simulation_seconds']:.2f}s", flush=True)
    return {"name": name, "geometry": geometry, "id_width": id_width, "axi_id": axi_id,
            "ddr_address_limit": f"0x{limit:08x}", **detail, "compared": compared, "markers": markers}


def run_config():
    detail, transcript = compile_and_simulate(ROOT / "artifacts" / "invalid_config",
                                              "tb_fpga_v8_raw_axi_physical_config", [])
    if "AXI_PHYSICAL_CONFIG_PASS cases=8" not in transcript:
        raise AssertionError(f"Configuration test failed\n{transcript[-10000:]}")
    print(f"PASS invalid_config: 8 parameter rejections, {detail['simulation_seconds']:.2f}s", flush=True)
    return {"cases": 8, **detail}


def protected_hashes():
    paths = [PARENT / "fpga_v8_raw_frame_axi.v", PARENT / "tb_fpga_v8_raw_frame_axi.v",
             PARENT / "tb_fpga_v8_raw_axi_config.v", PARENT / "run_tests.py",
             SHARED / "fpga_v8_raw_letterbox.v", SHARED / "fpga_v8_rgb888_pack128.v"]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--small-only", action="store_true")
    args = parser.parse_args()
    before = protected_hashes()
    if before[str(PARENT / "fpga_v8_raw_frame_axi.v")] != ORIGINAL_HASH:
        raise AssertionError("Original bridge differs from the frozen PDS input; reconcile before running.")
    results = [run_case("small_4x3", (4, 3, 5, 1), False),
               run_case("overflow_1x1", (1, 1, 6, 2), False, 3, 3),
               run_case("smaller_limit_4x3", (4, 3, 5, 1), False, limit=0x02000000)]
    if not args.small_only:
        results.append(run_case("full_640x480", (640, 480, 640, 80), True))
    config_result = run_config()
    after = protected_hashes()
    if before != after:
        raise AssertionError("A protected original/shared file changed during this run.")
    report = {"status": "PASS", "modelsim_bin": str(MODELSIM),
              "tested_module": "fpga_v8_raw_frame_axi_physical",
              "tested_rtl_sha256": hashlib.sha256(RTL.read_bytes()).hexdigest(),
              "protected_hashes_unchanged": after, "cases": results,
              "configuration_test": config_result,
              "total_frames": sum(len(x["compared"]) for x in results),
              "total_compared_bytes": sum(f["bytes"] for x in results for f in x["compared"]),
              "promotion_status": "staged_only_original_unchanged_PDS_rerun_required"}
    report_path = ROOT / "artifacts" / "results.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(f"PASS report: {report_path}", flush=True)


if __name__ == "__main__":
    main()
