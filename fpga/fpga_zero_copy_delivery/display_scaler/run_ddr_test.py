"""Actual ModelSim, native HMIC physical memory, independent CPU thumbnail oracle."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "ddr_test_results"
BIN = Path(os.environ.get("MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))


def run(tool, args, folder, log):
    result = subprocess.run([str(BIN / (tool + ".exe")), *map(str, args)],
                            cwd=folder, text=True, errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=180)
    (folder / log).write_text(result.stdout, encoding="utf-8")
    if result.returncode or re.search(r"\*\* (?:Error|Fatal)|FAIL ", result.stdout):
        raise RuntimeError(f"{folder / log}:\n{result.stdout[-6000:]}")
    return result.stdout


def pixel(x, y):
    return ((x * 197 + y * 911 + 0x7351) ^ (x * y * 13) ^
            ((x << 7) | (y >> 2))) & 0xffff


def native_memory(payload, poison, guard=0):
    # Independent deployed camera/PCIe layout: fill 256 physical bytes then
    # skip 256 physical bytes. Native base addresses count 16-bit words.
    memory = bytearray([poison]) * (((len(payload) + 255) // 256) * 512 + guard)
    for start in range(0, len(payload), 256):
        chunk = payload[start:start + 256]
        physical = (start // 256) * 512
        memory[physical:physical + len(chunk)] = chunk
    return memory


def main():
    BUILD.mkdir(exist_ok=True)
    library = BUILD / "work"
    if not library.exists():
        run("vlib", [library], BUILD, "vlib.log")
    rtl = [ROOT / name for name in ("rgb565_display_decimator.v",
           "display_rgb565_pack128.v", "display_thumbnail_ddr.v")]
    # New synthesizable source is ASCII and compatible with Verilog-2001.
    for path in rtl:
        path.read_bytes().decode("ascii")
    run("vlog", ["-work", library, "-vlog01compat", *rtl], BUILD, "compile.log")
    run("vlog", ["-work", library, "-sv", ROOT / "tb_thumbnail_ddr.sv"],
        BUILD, "compile_tb.log")
    cases = [("full_early_final_b", 640, 480, 0, 0, 0),
             ("full_random_final_b_hold", 640, 480, 1, 1, 0),
             ("partial_output", 18, 10, 1, 1, 0),
             ("partial_input_and_output", 6, 6, 1, 1, 0),
             ("bad_r_drain_pending_aw_w", 64, 16, 1, 0, 1),
             ("bad_b_drain_pending_r", 64, 16, 1, 0, 2),
             ("early_rlast", 64, 16, 1, 0, 3),
             ("late_rlast_drain", 64, 16, 1, 0, 4),
             ("invalid_odd_width", 3, 4, 1, 0, 0),
             ("invalid_odd_height", 4, 3, 1, 0, 0),
             ("invalid_large_width", 2050, 2, 1, 0, 0)]
    results = []
    for name, width, height, stall, hold, fault in cases:
        folder = BUILD / name
        folder.mkdir(exist_ok=True)
        source = b"".join(pixel(x, y).to_bytes(2, "little")
                          for y in range(height) for x in range(width))
        # CPU reference samples the actual source buffer, independently of
        # both DUT counters and the simulator's native address arithmetic.
        golden = b"".join(source[2 * (y * width + x):2 * (y * width + x) + 2]
                          for y in range(0, height, 2) for x in range(0, width, 2))
        physical_source = native_memory(source, 0xd3)
        (folder / "source_physical.hex").write_text(
            "".join(f"{byte:02x}\n" for byte in physical_source), encoding="ascii")
        log = run("vsim", ["-c", "-quiet", "-onfinish", "stop", "-lib", library,
                  "tb_thumbnail_ddr", f"-gW={width}", f"-gH={height}",
                  f"-gSTALL={stall}", f"-gHOLD_B={hold}", f"-gFAULT={fault}",
                  "-do", "onerror {quit -code 1}; run -all; quit -code 0"],
                  folder, "simulation.log")
        if width % 2 or height % 2 or width > 2048:
            assert "PASS CONFIG:" in log, log
            results.append({"case": name, "rtl_pass": re.search(r"PASS CONFIG:.*", log)[0]})
            print(name, results[-1]["rtl_pass"])
            continue
        assert "PASS DDR:" in log, log
        actual = bytes(int(line, 16) for line in
                       (folder / "dest_physical.hex").read_text().splitlines())
        expected = native_memory(golden, 0xa5, guard=64)
        if actual != expected:
            mismatch = next((i for i, pair in enumerate(zip(actual, expected))
                             if pair[0] != pair[1]), min(len(actual), len(expected)))
            raise AssertionError((name, "physical DDR byte mismatch", mismatch))
        result = {"case": name, "width": width, "height": height,
                  "byte_exact_output": len(golden),
                  "physical_bytes_and_guards_checked": len(expected),
                  "output_sha256": hashlib.sha256(golden).hexdigest(),
                  "rtl_pass": re.search(r"PASS DDR:.*", log)[0]}
        results.append(result)
        print(name, result["rtl_pass"], f"CPU PASS {len(golden)} bytes + gaps/guards")
    report = {"status": "PASS", "simulator": str(BIN / "vsim.exe"),
              "scope": "isolated RTL simulation, no integrated project/PDS/board changes",
              "native_contract": "16-bit-word addresses, 16 beats, 256-unit burst stride",
              "results": results}
    (BUILD / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (BUILD / "cpu_compare.log").write_text("PASS all DDR native-memory byte comparisons\n")


if __name__ == "__main__":
    main()
