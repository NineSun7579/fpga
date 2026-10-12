"""Deferred local-on-RK3568 runner. No SSH, PCIe DMA, viewer, model or FPGA writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, timeout=120):
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    return {"command": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board-free", action="store_true",
                        help="Parent asserts its diagnostic compile is finished and this board slot is available")
    parser.add_argument("--fixtures", type=Path, default=HERE / "local_evidence" / "fixtures")
    parser.add_argument("--output", type=Path,
                        help="New private output directory; refuses existing directories")
    parser.add_argument("--headers-root", type=Path, default=Path("/usr/include"),
                        help="Root containing rga/im2d.h and the board's matching SDK headers")
    parser.add_argument("--memory", choices=("fd", "virtual", "both"), default="fd")
    parser.add_argument("--heap", default="/dev/dma_heap/system")
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--cc", default="g++")
    parser.add_argument("--cpu-core", type=int, help="Optional process-only CPU affinity; does not change any system governor")
    args = parser.parse_args()
    if not args.board_free:
        parser.error("Deferred: --board-free is required; no board command or device open has occurred")
    if platform.machine() != "aarch64":
        parser.error("Run this hardware runner on the RK3568 AArch64 board")
    allowed_cpus = sorted(os.sched_getaffinity(0))
    if args.cpu_core is not None:
        if args.cpu_core not in allowed_cpus:
            parser.error("Requested CPU is outside the allowed process affinity")
        os.sched_setaffinity(0, {args.cpu_core})
    if not 1 <= args.frames <= 100000 or not 0 <= args.warmup <= 10000:
        parser.error("Invalid frame/warmup bounds")
    headers = args.headers_root.resolve()
    if not (headers / "rga" / "im2d.h").is_file() or not (headers / "rga" / "rga.h").is_file():
        parser.error("Missing captured/installed board headers rga/im2d.h and rga/rga.h")
    fixture_dir = args.fixtures.resolve()
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = manifest["fixtures"]
    if [row["name"] for row in rows] != [f"cam{i}.rgb565" for i in range(1, 7)]:
        parser.error("Require all six pinned fixtures in cam1..cam6 order")
    for row in rows:
        name = row["name"]
        if Path(name).name != name or not re.fullmatch(r"cam[1-6]\.rgb565", name):
            parser.error("Invalid fixture name")
        path = fixture_dir / name
        if not path.is_file() or path.stat().st_size != 614400 or sha(path) != row["raw_sha256"]:
            parser.error(f"Fixture hash/size mismatch: {name}")
    output = args.output or HERE / ("board_run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    captured_headers = output / "headers" / "rga"
    shutil.copytree(headers / "rga", captured_headers)
    sources = output / "source"
    sources.mkdir()
    source_names = ("reference.hpp", "native_probe.cpp", "reference_selftest.cpp", "run_board.py")
    for name in source_names:
        shutil.copyfile(HERE / name, sources / name)
    receipt = {
        "started_utc": datetime.now(timezone.utc).isoformat(), "status": "preparing",
        "hardware_executed": False, "viewer_changed": False,
        "pci_dma_opened": False, "fpga_changed": False, "model_changed": False,
        "platform": platform.uname()._asdict(), "frames": args.frames, "warmup": args.warmup,
        "source_sha256": {name: sha(sources / name) for name in source_names},
        "headers_sha256": {str(path.relative_to(output / "headers")): sha(path)
                           for path in captured_headers.rglob("*") if path.is_file()},
        "fixtures": rows, "commands": [], "library_files": {}, "driver_version_files": {},
        "driver_version_policy": "Record only available actual files/log entries; absent version is unknown",
        "allowed_cpus_before": allowed_cpus, "process_affinity": sorted(os.sched_getaffinity(0)),
    }

    def clocks():
        result = {}
        for policy in Path("/sys/devices/system/cpu/cpufreq").glob("policy*"):
            for name in ("scaling_governor", "scaling_cur_freq", "scaling_min_freq", "scaling_max_freq"):
                path = policy / name
                try:
                    result[str(path)] = path.read_text().strip()
                except OSError:
                    pass
        return result

    receipt["cpu_clock_before"] = clocks()

    def save():
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def command(argv, timeout=120):
        result = execute(argv, timeout)
        receipt["commands"].append(result)
        save()
        if result["returncode"]:
            raise RuntimeError(f"Command failed ({result['returncode']}): {argv[0]}")
        return result

    def parse_records(text):
        records = []
        other = []
        for line in text.splitlines():
            if line.strip().startswith("{"):
                record = json.loads(line)
                if isinstance(record, dict) and record.get("kind"):
                    records.append(record)
                    continue
            if line.strip():
                other.append(line)
        return records, other

    save()
    try:
        command([args.cc, "--version"])
        # Compile and link with captured headers and the *installed* matching
        # librga. Unsupported APIs fail here; there is no SDK substitution.
        flags = ["-O3", "-std=gnu++14", "-Wall", "-Wextra", "-I" + str(output / "headers")]
        reference_bin = output / "reference_selftest"
        native_bin = output / "native_probe"
        command([args.cc, *flags, str(sources / "reference_selftest.cpp"), "-o", str(reference_bin)])
        command([args.cc, *flags, str(sources / "native_probe.cpp"), "-o", str(native_bin), "-lrga", "-ldl"])
        receipt["executables_sha256"] = {path.name: sha(path) for path in (reference_bin, native_bin)}
        ldd = command(["ldd", str(native_bin)])["stdout"]
        for line in ldd.splitlines():
            match = re.search(r"(?:=>\s*)?(/\S+)\s+\(", line)
            if match:
                library = Path(match.group(1)).resolve()
                if library.is_file():
                    receipt["library_files"][str(library)] = sha(library)
        if not any("librga" in path for path in receipt["library_files"]):
            raise RuntimeError("No actual linked librga file found in ldd output")
        # Read-only provenance. Never mount debugfs, unload modules or change a driver.
        for name in ("/sys/module/rga/version", "/sys/module/rga2/version", "/sys/module/rga3/version",
                     "/sys/kernel/debug/rkrga/driver_version", "/sys/kernel/debug/rga/driver_version",
                     "/sys/kernel/debug/rga/version", "/proc/rga/driver_version"):
            try:
                receipt["driver_version_files"][name] = Path(name).read_text().strip()
            except (OSError, UnicodeError):
                pass
        kernel_log = execute(["dmesg"], timeout=10)
        receipt["rga_kernel_log"] = {
            "returncode": kernel_log["returncode"],
            "lines": [line for line in kernel_log["stdout"].splitlines()
                      if re.search(r"\brga[0-9]?\b|rkrga", line, flags=re.I)][-100:],
            "stderr": kernel_log["stderr"],
        }
        cpu = command([str(reference_bin), *[str(fixture_dir / row["name"]) for row in rows]])
        records, _ = parse_records(cpu["stdout"])
        if len(records) != 7 or not records[0].get("passed"):
            raise RuntimeError("Missing exhaustive native CPU reference evidence")
        for row, record in zip(rows, records[1:]):
            for key in ("raw_fnv1a64", "rgb_fnv1a64", "model_fnv1a64"):
                if record[key] != row[key]:
                    raise RuntimeError(f"Target CPU differs from local independent oracle: {row['name']} {key}")
        modes = ("fd", "virtual") if args.memory == "both" else (args.memory,)
        for mode in modes:
            dumps = output / (mode + "_outputs")
            dumps.mkdir()
            argv = [str(native_bin), "--memory", mode, "--heap", args.heap,
                    "--frames", str(args.frames), "--warmup", str(args.warmup), "--dump-dir", str(dumps)]
            for row in rows:
                argv.extend(("--fixture", str(fixture_dir / row["name"])))
            # Stream the potentially long probe so partial evidence survives.
            stdout = output / (mode + ".jsonl")
            stderr = output / (mode + ".stderr")
            receipt["hardware_requested"] = True
            save()
            with stdout.open("w") as out, stderr.open("w") as err:
                run = subprocess.run(argv, stdout=out, stderr=err, timeout=1800, check=False)
            receipt["commands"].append({"command": argv, "returncode": run.returncode,
                                         "stdout_file": stdout.name, "stderr_file": stderr.name})
            data, other = parse_records(stdout.read_text())
            receipt[mode + "_library_stdout"] = {"lines": other[:100], "count": len(other)}
            receipt["hardware_executed"] |= any(row["kind"] == "format_calibration" for row in data)
            if run.returncode or not any(row["kind"] == "complete" and row.get("passed") for row in data):
                raise RuntimeError(f"RGA {mode} probe failed; retain partial JSONL and stderr")
            complete = next(row for row in data if row["kind"] == "complete")
            paths = complete.get("supported_paths", [])
            if "full_frame" not in paths or not set(paths) & {"model_direct_roi", "model_two_stage_roi"}:
                raise RuntimeError("Missing full-frame and model-letterbox supported path evidence")
            receipt[mode + "_supported_paths"] = paths
            receipt[mode + "_rejected_paths"] = [row for row in data if row["kind"] == "path_rejected"]
            # Bind every dumped output to SHA256, and insist every corrected
            # output matches the original model/full-frame oracle byte-for-byte.
            hashes = {}
            for path in dumps.glob("*.rgb888"):
                match = re.fullmatch(r"fixture([1-6])_(.+)_(direct|corrected)\.rgb888", path.name)
                if not match:
                    raise RuntimeError(f"Unexpected output name: {path.name}")
                row = rows[int(match[1]) - 1]
                expected = row["rgb_sha256" if match[2] == "full_frame" else "model_sha256"]
                actual = sha(path)
                if match[3] == "corrected" and actual != expected:
                    raise RuntimeError(f"SHA256 oracle mismatch: {path.name}")
                hashes[path.name] = {"sha256": actual, "expected_sha256": expected,
                                     "exact": actual == expected}
            required = {f"fixture{i}_{path}_{kind}.rgb888"
                        for i in range(1, 7) for path in paths for kind in ("direct", "corrected")}
            if not required.issubset(hashes):
                raise RuntimeError("Missing full-frame or model output evidence")
            receipt[mode + "_output_hashes"] = hashes
            receipt[mode + "_jsonl_sha256"] = sha(stdout)
            save()
        receipt["status"] = "complete_probe_only"
        receipt["rkNN_detection_parity_tested"] = False
        receipt["completed_inference_fps_measured"] = False
        # Receipt binds the immutable snapshot actually compiled and invoked.
        for name, expected in receipt["source_sha256"].items():
            if sha(sources / name) != expected:
                raise RuntimeError("Private source changed during hardware probe")
        for path, expected in receipt["library_files"].items():
            if sha(Path(path)) != expected:
                raise RuntimeError("Linked dependency changed during hardware probe")
    except Exception as exc:
        receipt["status"] = "failed"
        receipt["error"] = str(exc)
        raise
    finally:
        receipt["cpu_clock_after"] = clocks()
        receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        print(str(output / "receipt.json"))


if __name__ == "__main__":
    main()
