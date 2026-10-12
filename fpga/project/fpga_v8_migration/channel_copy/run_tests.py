"""Generate independent HWC16 golden bytes and run isolated ModelSim tests."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
MODEL_SCENARIOS = (
    (4, 64, 80, 80, 0, 32), (5, 64, 80, 80, 32, 32),
    (13, 128, 40, 40, 0, 64), (14, 128, 40, 40, 64, 64),
    (22, 256, 20, 20, 0, 128), (23, 256, 20, 20, 128, 128),
    (38, 128, 40, 40, 0, 64), (39, 128, 40, 40, 64, 64),
    (47, 64, 80, 80, 0, 32), (48, 64, 80, 80, 32, 32),
    (56, 128, 40, 40, 0, 64), (57, 128, 40, 40, 64, 64),
    (65, 256, 20, 20, 0, 128), (66, 256, 20, 20, 128, 128),
)


def make_cases():
    cases = []

    def add(name, height, width, groups, first, count, mode=0,
            framing="normal", task_id=None):
        case_id = len(cases)
        pixels = height * width
        if not (0 < pixels <= 0xffffffff and 0 < groups <= 65535 and
                0 <= first < groups and 0 < count <= groups - first):
            raise ValueError("Invalid generated configuration: " + name)
        if pixels * groups > 65536:
            raise ValueError("Case exceeds testbench word memory: " + name)
        cases.append({
            "id": case_id, "name": name, "height": height, "width": width,
            "pixels": pixels, "groups": groups, "first": first, "count": count,
            "mode": mode, "framing": framing,
            "expected_frame_error": int(framing != "normal"),
            "source_words": pixels * groups, "output_words": pixels * count,
            "seed": 0x1234567 + case_id * 7919, "model_task_id": task_id,
        })

    for height, width, groups, first, count in (
        (1, 1, 1, 0, 1), (1, 7, 1, 0, 1),
        (1, 5, 2, 0, 1), (1, 7, 2, 1, 1), (1, 3, 2, 0, 2),
        (1, 5, 4, 0, 1), (1, 7, 4, 1, 1), (2, 3, 4, 1, 2),
        (1, 9, 4, 2, 2), (1, 5, 4, 3, 1), (1, 3, 4, 0, 4),
        (1, 5, 8, 0, 4), (1, 7, 8, 4, 4), (3, 3, 8, 2, 3),
        (1, 5, 8, 7, 1), (1, 3, 8, 0, 8),
        (1, 7, 3, 1, 1), (1, 11, 5, 1, 3),
        (1, 13, 7, 2, 4), (1, 5, 9, 3, 5),
    ):
        add("groups%d_first%d_count%d_%dx%d" %
            (groups, first, count, height, width),
            height, width, groups, first, count)

    add("final_output_before_trailing_skips", 1, 1, 8, 0, 1, mode=1)
    add("source_end_before_stalled_final_output", 1, 1, 8, 0, 1, mode=2)
    add("selected_output_stall_then_replace", 1, 3, 4, 1, 2, mode=3)
    add("waiting_command_cannot_restart_busy_frame", 1, 7, 4, 1, 2, mode=4)
    add("stalled_selection_across_skip_and_pixel_wrap", 1, 3, 4, 3, 1, mode=3)
    add("early_last_first_word", 1, 7, 4, 1, 2, framing="early_first")
    add("early_last_middle_word", 1, 9, 8, 3, 3, framing="early_middle")
    add("missing_final_last", 1, 7, 4, 2, 2, framing="missing_final")
    add("late_last_extra_word_not_consumed", 1, 5, 8, 0, 2,
        mode=5, framing="missing_final")
    add("multiple_early_last_flags", 1, 7, 4, 0, 2, framing="multiple")
    add("maximum_groups_last_group", 1, 1, 65535, 65534, 1)

    generator = random.Random(0x5640c016)
    for index in range(24):
        groups = generator.randint(1, 17)
        first = generator.randrange(groups)
        count = generator.randint(1, groups - first)
        add("random_geometry_%02d" % index, 1, generator.randint(2, 23),
            groups, first, count)

    # Read the audit only; never change artifacts from other agents.
    audit_path = ROOT.parent / "audit" / "tasks.json"
    audit = json.loads(audit_path.read_bytes())
    views = [task for task in audit["tasks"] if task["op"] == "ChannelView"]
    observed = []
    for task in views:
        batch, channels, height, width = task["input_shapes"][0]
        if batch != 1 or channels % 16 or task["channel_start"] % 16 or task["channel_count"] % 16:
            raise AssertionError("Model view is not a batch-1 C16-aligned slice")
        scenario = (task["id"], channels, height, width,
                    task["channel_start"], task["channel_count"])
        observed.append(scenario)
        add("model_task_%d_%s" % (task["id"], task["name"]),
            height, width, channels // 16, task["channel_start"] // 16,
            task["channel_count"] // 16, task_id=task["id"])
        if task["output_shape"] != [1, task["channel_count"], height, width]:
            raise AssertionError("Unexpected ChannelView output shape")
    if tuple(observed) != MODEL_SCENARIOS:
        raise AssertionError("Audit no longer matches the 14 exact model scenarios")
    return cases, hashlib.sha256(audit_path.read_bytes()).hexdigest()


def golden_bytes(case):
    """Make an HWC tensor and slice channels directly, without an RTL oracle.

    Every pixel owns all its channels. Source serialization uses 16 channels
    per word, low lane first. Desired output is the per-pixel byte slice;
    no source/output address overlap or shared allocation is assumed.
    """
    source = bytearray()
    output = bytearray()
    channels = case["groups"] * 16
    start = case["first"] * 16
    stop = (case["first"] + case["count"]) * 16
    for row in range(case["height"]):
        for column in range(case["width"]):
            # Two-byte-dependent channel signature distinguishes group 0
            # from groups 16 and beyond in the maximum-width case as well.
            pixel = bytes(((row * 37 + column * 53 + channel * 97 + case["id"] * 19)
                           ^ (channel >> 4) ^ (channel >> 12)
                           ^ ((row * 11 + column * 7) >> 2)) & 255
                          for channel in range(channels))
            source.extend(pixel)
            output.extend(pixel[start:stop])
    if len(source) != case["source_words"] * 16 or len(output) != case["output_words"] * 16:
        raise AssertionError("Golden did not preserve complete tensor sizes")
    return bytes(source), bytes(output)


def source_last(case, word):
    final = word == case["source_words"] - 1
    framing = case["framing"]
    if framing == "normal":
        return final
    if framing == "early_first":
        return final or word == 0
    if framing == "early_middle":
        return final or word == case["source_words"] // 2
    if framing == "missing_final":
        return False
    if framing == "multiple":
        return final or word in (0, 3, case["source_words"] // 2)
    raise ValueError(framing)


def generate_vectors(cases, directory):
    descriptors = []
    for case in cases:
        source, expected = golden_bytes(case)
        case_id = case["id"]
        for kind, data in (("input", source), ("expected", expected)):
            lines = []
            words = len(data) // 16
            for index in range(words):
                last = source_last(case, index) if kind == "input" else index == words - 1
                word = int.from_bytes(data[index * 16:(index + 1) * 16], "little")
                lines.append("%033x" % (word | (int(last) << 128)))
            (directory / ("case_%d_%s.hex" % (case_id, kind))).write_text(
                "\n".join(lines) + "\n", encoding="ascii")
        (directory / ("case_%d_expected.bin" % case_id)).write_bytes(expected)
        case["source_byte_sha256"] = hashlib.sha256(source).hexdigest()
        case["expected_byte_sha256"] = hashlib.sha256(expected).hexdigest()
        descriptors.append("%d %d %d %d %d %d %d %d %d %d" % (
            case_id, case["pixels"], case["groups"], case["first"], case["count"],
            case["mode"], case["expected_frame_error"], case["source_words"],
            case["output_words"], case["seed"]))
    (directory / "cases.txt").write_text("\n".join(descriptors) + "\n", encoding="ascii")
    (directory / "case_manifest.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="ascii")


def check_complete_outputs(cases, directory):
    for case in cases:
        case_id = case["id"]
        actual_lines = (directory / ("case_%d_actual.hex" % case_id)).read_text().splitlines()
        expected_lines = (directory / ("case_%d_expected.hex" % case_id)).read_text().splitlines()
        if len(actual_lines) != case["output_words"] or len(expected_lines) != case["output_words"]:
            raise AssertionError("Truncated or extra output for case %d: %d / %d" %
                                 (case_id, len(actual_lines), case["output_words"]))
        actual = [int(line, 16) for line in actual_lines]
        expected = [int(line, 16) for line in expected_lines]
        if actual != expected:
            raise AssertionError("Complete word/last sequence mismatch for case %d" % case_id)
        actual_bytes = b"".join((word & ((1 << 128) - 1)).to_bytes(16, "little") for word in actual)
        expected_bytes = (directory / ("case_%d_expected.bin" % case_id)).read_bytes()
        if actual_bytes != expected_bytes:
            raise AssertionError("Complete HWC16 byte sequence mismatch for case %d" % case_id)
        if [word >> 128 for word in actual] != [0] * (case["output_words"] - 1) + [1]:
            raise AssertionError("Output last flags are not exact for case %d" % case_id)
        case["actual_byte_sha256"] = hashlib.sha256(actual_bytes).hexdigest()
        case["verified_words"] = len(actual)
        case["verified_bytes"] = len(actual_bytes)
    return sum(case["verified_bytes"] for case in cases)


def check_golden_layout():
    # An explicit asymmetric example detects accidental group-major order.
    case = {"id": 0, "groups": 4, "first": 1, "count": 2,
            "height": 2, "width": 3, "source_words": 24, "output_words": 12}
    source, expected = golden_bytes(case)
    direct = b"".join(source[pixel * 64 + 16:pixel * 64 + 48] for pixel in range(6))
    if expected != direct or expected == source[16:16 + len(expected)]:
        raise AssertionError("Golden channel slicing is not per-pixel HWC16")
    # Lane 0 must occupy the least significant byte of the transmitted word.
    first_word = int.from_bytes(source[:16], "little")
    if (first_word & 255) != source[0] or (first_word >> 120) != source[15]:
        raise AssertionError("Unexpected golden word lane byte order")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelsim-bin", type=Path, default=Path("C:/modeltech64_10.6e/win64"))
    args = parser.parse_args()
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    vectors = artifacts / "vectors"
    vectors.mkdir(exist_ok=True)
    evidence = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable, "python_version": sys.version,
        "modelsim_bin": str(args.modelsim_bin.resolve()),
        "scope": "channel_copy only; isolated simulation; no production/PDS/board writes",
        "byte_contract": "[row,column,channel_group,lane], 16 u8 lanes per 128-bit word; lane 0 in bits 7:0",
        "commands": [],
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(ROOT.iterdir()) if path.suffix in (".v", ".py")},
    }

    def run(label, arguments):
        command = [str(part) for part in arguments]
        result = subprocess.run(command, cwd=artifacts, capture_output=True, text=True,
                                errors="replace", timeout=180,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        output = result.stdout + result.stderr
        (artifacts / (label + ".log")).write_text(output, encoding="ascii", errors="backslashreplace")
        evidence["commands"].append({"label": label, "argv": command,
                                      "cwd": str(artifacts), "returncode": result.returncode,
                                      "log": label + ".log"})
        print("COMMAND %s returncode=%d" % (label, result.returncode))
        if result.returncode or re.search(r"\bFAIL\b|\*\*\s+(Error|Fatal):", output):
            print(output)
            raise RuntimeError(label + " failed")
        return output

    try:
        check_golden_layout()
        for name in ("vlib.exe", "vlog.exe", "vsim.exe"):
            if not (args.modelsim_bin / name).is_file():
                raise RuntimeError("Missing ModelSim tool: " + name)
        cases, audit_hash = make_cases()
        evidence["audit_tasks_sha256"] = audit_hash
        generate_vectors(cases, vectors)
        print("GOLDEN cases=%d model_views=%d input_words=%d output_words=%d" % (
            len(cases), sum(case["model_task_id"] is not None for case in cases),
            sum(case["source_words"] for case in cases), sum(case["output_words"] for case in cases)))
        if not (artifacts / "work").exists():
            run("vlib", [args.modelsim_bin / "vlib.exe", "work"])
        run("vlog", [args.modelsim_bin / "vlog.exe", "-vlog01compat", "-work", "work",
                      ROOT / "fpga_v8_channel_copy.v", ROOT / "tb_fpga_v8_channel_copy.v"])
        (artifacts / "run.do").write_text(
            "onerror {quit -f -code 2}\nrun -all\nquit -f -code 0\n", encoding="ascii")
        output = run("vsim", [args.modelsim_bin / "vsim.exe", "-c", "-onfinish", "stop",
                              "work.tb_fpga_v8_channel_copy", "+VECTORS=" + vectors.as_posix(),
                              "-do", "run.do"])
        if "PASS_SIM " not in output or output.count("PASS_CASE ") != len(cases):
            raise RuntimeError("Simulation did not complete every golden case")
        verified_bytes = check_complete_outputs(cases, vectors)
        stats = {key: int(value) for key, value in
                 (line.split() for line in (vectors / "simulation_stats.txt").read_text().splitlines())}
        if stats["cases"] != len(cases) or stats["source_words"] != sum(case["source_words"] for case in cases):
            raise AssertionError("Simulation input totals differ from complete generated cases")
        if stats["output_words"] * 16 != verified_bytes:
            raise AssertionError("Simulation output count differs from complete byte comparisons")
        evidence.update(status="PASS", cases=cases, statistics=stats,
                        complete_bytes_verified=verified_bytes, model_views_verified=14,
                        malformed_last_cases=sum(case["expected_frame_error"] for case in cases))
        print("PASS channel_copy: %d complete cases, 14 exact model views, %d bytes; "
              "9 invalid configurations, 4 reset-pending scenarios" % (len(cases), verified_bytes))
        print("STATISTICS " + json.dumps(stats, sort_keys=True))
    except Exception as exc:
        evidence.update(status="FAIL", error=str(exc))
        raise
    finally:
        report = artifacts / "test_results.json"
        report.write_text(json.dumps(evidence, indent=2) + "\n", encoding="ascii")
        print("EVIDENCE " + str(report))


if __name__ == "__main__":
    main()
