"""Generate CPU vectors, run genuine ModelSim, compare every output and tag."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "test_results"
BIN = Path(os.environ.get("MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))


def pixel(frame, x, y):
    # Distinct frames and nonlinear coordinates exercise every RGB565 bit.
    return ((x * 197 + y * 911 + frame * 12347) ^ (x * y * 13) ^
            ((x << 7) | (y >> 2))) & 0xffff


def run(tool, *args):
    result = subprocess.run([str(BIN / (tool + ".exe")), *args],
                            cwd=BUILD, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    (BUILD / (tool + ".log")).write_text(result.stdout, encoding="utf-8")
    print(result.stdout)
    if result.returncode or "** Error" in result.stdout or "** Fatal" in result.stdout:
        raise RuntimeError(f"{tool} failed: see {BUILD / (tool + '.log')}")
    return result.stdout


def main():
    BUILD.mkdir(exist_ok=True)
    with (BUILD / "stimulus.hex").open("w", encoding="ascii") as stream:
        for frame in range(3):
            for y in range(480):
                for x in range(640):
                    stream.write(f"{pixel(frame, x, y):04x}\n")
    if not (BUILD / "work").exists():
        run("vlib", "work")
    run("vlog", "-sv", str(ROOT / "rgb565_display_decimator.v"),
        str(ROOT / "tb_display_scaler.sv"))
    transcript = run("vsim", "-c", "-onfinish", "stop", "work.tb_display_scaler",
                     "-do", "onerror {quit -code 1}; run -all; quit -code 0")
    if "PASS RTL:" not in transcript:
        raise AssertionError("Simulator did not reach PASS")
    rows = (BUILD / "actual.txt").read_text(encoding="ascii").splitlines()
    assert len(rows) == 3 * 76800, len(rows)
    index = 0
    for frame in range(3):
        # CPU reference independently indexes the top-left of each 2x2 block.
        for oy in range(240):
            for ox in range(320):
                value, sof, eof = rows[index].split()
                expected = (pixel(frame, 2 * ox, 2 * oy),
                            int(ox == 0 and oy == 0),
                            int(ox == 319 and oy == 239))
                actual = (int(value, 16), int(sof), int(eof))
                assert actual == expected, (frame, ox, oy, actual, expected)
                index += 1
    summary = {"simulator": str(BIN / "vsim.exe"), "status": "PASS",
               "complete_frames": 3, "input_pixels": 921600,
               "bit_exact_output_pixels": index, "pixels_per_output_frame": 76800,
               "reset_while_stalled_cases": 2,
               "tests": ["continuous-ready", "random-ready-and-bubbles",
                         "97-cycle-ready-blackouts-and-random-ready",
                         "stable-output-under-backpressure", "SOF/EOF-every-pixel"],
               "input_bytes_per_frame": 614400, "output_bytes_per_frame": 153600}
    (BUILD / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (BUILD / "cpu_compare.log").write_text(
        f"PASS CPU golden: {index} pixels and SOF/EOF tags, 3 complete 640x480 frames\n")
    print(f"PASS CPU golden: {index} pixels and tags across 3 frames")


if __name__ == "__main__":
    main()
