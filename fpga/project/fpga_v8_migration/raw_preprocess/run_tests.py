"""ModelSim regression with byte-exact independent Python golden comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from golden import letterbox, packed_words, self_check, source_pixels, write_hex

ROOT = Path(__file__).resolve().parent


def run(command, cwd, logfile):
    result = subprocess.run([str(x) for x in command], cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", timeout=240)
    logfile.write_text(result.stdout, encoding="utf-8")
    if result.returncode or "FAIL " in result.stdout or "** Error" in result.stdout:
        raise RuntimeError(f"Command failed; see {logfile}\n{result.stdout[-5000:]}")
    return result.stdout


def vectors(folder, width, height, out_height, top, fill, frames):
    all_source, all_pixels, all_words, expected_frames = [], [], [], []
    for index in range(frames):
        src = source_pixels(width * height, index)
        if width * height >= 65543:
            assert len(set(src)) == 65536, "Full frame must cover all RGB565 codes"
        data = letterbox(src, width, height, out_height, top, fill)
        all_source.extend(src)
        all_pixels.extend(int.from_bytes(data[i:i+3], "little")
                          for i in range(0, len(data), 3))
        all_words.extend(packed_words(data))
        expected_frames.append(data)
    write_hex(folder / "source.hex", all_source, 4)
    write_hex(folder / "pixels.hex", all_pixels, 6)
    write_hex(folder / "words.hex", [w[0] for w in all_words], 32)
    write_hex(folder / "keeps.hex", [w[1] for w in all_words], 4)
    return all_words, expected_frames


def compare_actual(folder, expected_words, expected_frames):
    lines = (folder / "actual_words.txt").read_text(encoding="ascii").splitlines()
    actual_words, actual_frames = [], []
    frame_bytes = bytearray()
    for line in lines:
        data, keep, last, cycle = line.split()
        word = (int(data, 16), int(keep, 16), int(last))
        if word[1] == 0 or word[1] & (word[1] + 1):
            raise AssertionError(f"Non-contiguous/empty keep: {line}")
        actual_words.append(word)
        valid_bytes = word[1].bit_count()
        frame_bytes.extend(word[0].to_bytes(16, "little")[:valid_bytes])
        if word[2]:
            actual_frames.append(bytes(frame_bytes))
            frame_bytes.clear()
    if frame_bytes or actual_words != expected_words or actual_frames != expected_frames:
        raise AssertionError(f"Python DDR byte comparison failed in {folder}")
    return {"words_checked": len(actual_words),
            "bytes_checked": sum(map(len, actual_frames)),
            "frame_sha256": [hashlib.sha256(f).hexdigest() for f in actual_frames]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", default=os.environ.get(
        "MODELSIM_BIN", "C:/modeltech64_10.6e/win64"))
    parser.add_argument("--quick", action="store_true", help="Skip the two 640x480 cases")
    args = parser.parse_args()
    self_check()
    bin_dir = Path(args.modelsim_bin)
    build = ROOT / "artifacts"
    build.mkdir(exist_ok=True)
    library = build / "work"
    if not library.exists():
        run([bin_dir / "vlib.exe", library], build, build / "vlib.log")
    sources = [ROOT / name for name in (
        "fpga_v8_raw_letterbox.v", "fpga_v8_rgb888_pack128.v", "tb_raw_pipeline.v",
        "tb_rgb888_pack128.v", "tb_raw_config.v", "tb_raw_reset.v", "tb_raw_letterbox.v")]
    for path in sources:
        path.read_bytes().decode("ascii")
    compile_log = run([bin_dir / "vlog.exe", "-work", library, "-vlog01compat", *sources],
                      build, build / "compile.log")
    if "Errors: 0" not in compile_log:
        raise AssertionError("Compiler did not report zero errors")
    results = []

    def simulate(name, tb, parameters=None, plusargs=None):
        folder = build / name
        folder.mkdir(exist_ok=True)
        command = [bin_dir / "vsim.exe", "-c", "-quiet", "-onfinish", "exit",
                   "-lib", library, tb]
        command += [f"-g{k}={v}" for k, v in (parameters or {}).items()]
        command += plusargs or []
        command += ["-do", "onerror {quit -code 2}; run -all; quit -code 0"]
        log = run(command, folder, folder / "simulation.log")
        if f"PASS {tb}" not in log:
            raise AssertionError(f"Missing pass marker: {folder}")
        return folder, log

    cases = [
        ("odd_stalls", 4, 3, 5, 1, 114, 3, 1, 0, 1),
        ("no_padding", 2, 2, 2, 0, 114, 3, 0, 0, 1),
        ("early_last", 4, 3, 5, 1, 114, 2, 1, 1, 1),
        ("late_last", 4, 3, 5, 1, 114, 2, 1, 2, 1),
        ("top_only", 7, 2, 3, 1, 0, 2, 1, 0, 1),
        ("bottom_only", 3, 2, 3, 0, 255, 2, 1, 0, 1),
        ("single_pixel", 1, 1, 1, 0, 114, 3, 1, 0, 1),
        ("zero_fill", 5, 3, 7, 2, 0, 2, 1, 0, 1),
    ]
    if not args.quick:
        cases += [("full_ready", 640, 480, 640, 80, 114, 2, 0, 0, 0),
                  ("full_stalls", 640, 480, 640, 80, 114, 2, 1, 0, 1)]
    for name, width, height, out_height, top, fill, frames, stalls, marker, final in cases:
        folder = build / name
        folder.mkdir(exist_ok=True)
        expected, expected_frames = vectors(folder, width, height, out_height, top, fill, frames)
        simulate(name, "tb_raw_pipeline", dict(WIDTH=width, HEIGHT=height,
                 OUT_HEIGHT=out_height, TOP_ROWS=top, FILL_VALUE=fill, FRAMES=frames),
                 [f"+STALLS={stalls}", f"+MARKER_MODE={marker}", f"+FINAL_STALL={final}"])
        result = {"name": name, "geometry": [width, height, out_height, top],
                  "fill": fill, "frames": frames, "marker_mode": marker,
                  "random_stalls": bool(stalls), **compare_actual(folder, expected, expected_frames)}
        result["cycles"] = [dict(zip(("frame", "rgb_cycles", "packed_cycles",
            "max_source_run", "max_rgb_run", "packed_stall_cycles"), map(int, line.split())))
            for line in (folder / "cycles.txt").read_text(encoding="ascii").splitlines()]
        if name == "full_ready":
            for stats in result["cycles"]:
                assert stats["max_source_run"] == width * height
                assert stats["max_rgb_run"] == width * out_height
                assert stats["rgb_cycles"] == width * out_height + 1
        results.append(result)
        print(f"PASS {name}: {result['bytes_checked']} exact RGB bytes", flush=True)

    name = "packer_all_boundaries"
    folder = build / name
    folder.mkdir(exist_ok=True)
    inputs, input_last, expected, expected_frames = [], [], [], []
    for frame in range(1, 34):
        data = bytes((i * 29 + frame * 17) % 256 for i in range(frame * 3))
        inputs += [int.from_bytes(data[i:i+3], "little") for i in range(0, len(data), 3)]
        input_last += [0] * (frame - 1) + [1]
        expected.extend(packed_words(data))
        expected_frames.append(data)
    write_hex(folder / "source24.hex", inputs, 6)
    write_hex(folder / "source_last.hex", input_last, 1)
    write_hex(folder / "words.hex", [w[0] for w in expected], 32)
    write_hex(folder / "keeps.hex", [w[1] for w in expected], 4)
    write_hex(folder / "word_last.hex", [w[2] for w in expected], 1)
    _, log = simulate(name, "tb_rgb888_pack128", dict(INPUTS=len(inputs), WORDS=len(expected)))
    results.append({"name": name, "frames": 33,
                    **compare_actual(folder, expected, expected_frames),
                    "observed": re.search(r"PASS tb_rgb888_pack128[^\r\n]*", log).group(0)})
    print("PASS packer lengths 1..33: all final byte boundaries", flush=True)

    folder = build / "reset_pending"
    folder.mkdir(exist_ok=True)
    vectors(folder, 4, 3, 5, 1, 114, 1)
    simulate("reset_pending", "tb_raw_reset")
    results.append({"name": "reset_pending", "status": "pass",
                    "checks": ["idle rejects source", "busy rejects held command",
                    "integrated pending reset", "restart exact bytes", "carry reset",
                    "full word plus final flush reset", "final partial reset", "no ghosts"]})
    print("PASS reset abandonment and clean restart", flush=True)
    folder = build / "letterbox_final_stall"
    folder.mkdir(exist_ok=True)
    vectors(folder, 4, 3, 5, 1, 114, 1)
    _, log = simulate("letterbox_final_stall", "tb_raw_letterbox")
    results.append({"name": "letterbox_final_stall", "status": "pass",
                    "observed": re.search(r"PASS tb_raw_letterbox[^\r\n]*", log).group(0)})
    print("PASS letterbox stalled final padding pixel and done timing", flush=True)
    invalids = [dict(WIDTH=0), dict(HEIGHT=0), dict(WIDTH=-1), dict(WIDTH=65536),
                dict(HEIGHT=6), dict(OUT_HEIGHT=65536), dict(TOP_ROWS=-1),
                dict(TOP_ROWS=3), dict(FILL_VALUE=-1), dict(FILL_VALUE=256)]
    for index, invalid in enumerate(invalids):
        parameters = dict(WIDTH=4, HEIGHT=3, OUT_HEIGHT=5, TOP_ROWS=1, FILL_VALUE=114)
        parameters.update(invalid)
        simulate(f"invalid_{index}", "tb_raw_config", parameters)
        results.append({"name": f"invalid_{index}", "parameters": parameters, "status": "rejected"})
    print("PASS 10 invalid parameter configurations", flush=True)
    report = {"status": "pass", "simulator": str(bin_dir), "language": "Verilog-2001 ASCII",
              "integration": "isolated modules only; no DDR/top/PDS wiring", "results": results}
    (build / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="ascii")
    print(f"PASS all checks; report: {build / 'report.json'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
