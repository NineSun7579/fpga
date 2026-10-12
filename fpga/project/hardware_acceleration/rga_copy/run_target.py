"""Parent-run private RGA copy build/probe. No SSH, PCIe, RKNN or viewer operations."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import statistics
import struct
import subprocess

HERE = Path(__file__).resolve().parent
SOURCES = ("same_format_copy.h", "probe.cpp", "run_target.py", "README.md")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def elf(path):
    with Path(path).open("rb") as file:
        data = file.read(64)
    if len(data) < 20 or data[:4] != b"\x7fELF" or data[5] not in (1, 2):
        raise RuntimeError("expected actual ELF file: " + str(path))
    endian = "<" if data[5] == 1 else ">"
    return dict(elf_class=data[4], little_endian=data[5] == 1,
                machine=struct.unpack_from(endian + "H", data, 18)[0])


def records(text):
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("build", "experiment"), required=True,
                        help="experiment snapshots, builds and runs in one fresh directory")
    parser.add_argument("--sourcepath", type=Path, default=HERE, help="This unit's source directory")
    parser.add_argument("--out", type=Path, required=True, help="New private empty directory; never overwrite")
    parser.add_argument("--headers-root", type=Path, default=Path("/usr/include"))
    parser.add_argument("--board-exclusive", action="store_true",
                        help="Parent holds its global shared board lock, with NPU/RGA work idle")
    parser.add_argument("--cc", default="g++")
    parser.add_argument("--frames", type=int, default=25)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    if not args.board_exclusive:
        parser.error("parent must hold its existing global board lock and supply --board-exclusive")
    if platform.machine() != "aarch64":
        parser.error("target runner requires the actual AArch64 board; local checks use compile-only commands")
    if not (1 <= args.frames <= 100 and 2 <= args.rounds <= 4 and 0 <= args.warmup <= 5):
        parser.error("quick probe bounds: frames1..100 rounds2..4 warmup0..5")
    source, headers, out = args.sourcepath.resolve(), args.headers_root.resolve(), args.out.resolve()
    if any(not (source / name).is_file() for name in SOURCES):
        parser.error("sourcepath must contain this unit's helper, probe, runner and README")
    if not (headers / "rga/im2d.h").is_file() or not (headers / "rga/rga.h").is_file():
        parser.error("matching installed RGA SDK headers missing")
    compiler = shutil.which(args.cc)
    if not compiler:
        parser.error("actual compiler unavailable")
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="preparing", started_utc=datetime.now(timezone.utc).isoformat(), phase=args.phase,
                   hardware_requested=False, hardware_copy_executed=False, PCIe_access=False, NPU_access=False,
                   live_throughput_measured=False, scope="cached_system_heap_copy_calibration_only",
                   platform=platform.uname()._asdict(), actual_page_size=os.sysconf("SC_PAGE_SIZE"),
                   parent_global_lock_asserted=True, runner_acquires_lock=False,
                   frames=args.frames, rounds=args.rounds, warmup=args.warmup, commands=[],
                   compiler=dict(path=str(Path(compiler).resolve()), sha256=sha(compiler)))

    def save():
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def command(name, argv, timeout=120):
        argv = [str(x) for x in argv]
        with (out / (name + ".stdout")).open("xb") as stdout, (out / (name + ".stderr")).open("xb") as stderr:
            try:
                result = subprocess.run(argv, cwd=out, stdout=stdout, stderr=stderr, timeout=timeout, check=False)
                rc = result.returncode
            except subprocess.TimeoutExpired:
                rc = 124
        receipt["commands"].append(dict(name=name, argv=argv, cwd=str(out), returncode=rc,
            stdout_sha256=sha(out / (name + ".stdout")), stderr_sha256=sha(out / (name + ".stderr"))))
        save()
        if rc:
            raise RuntimeError(name + " failed rc=" + str(rc) + "; preserve stdout/stderr")
        return (out / (name + ".stdout")).read_text(encoding="utf-8", errors="replace")

    save()
    try:
        (out / "source").mkdir()
        for name in SOURCES:
            shutil.copyfile(source / name, out / "source" / name)
        shutil.copytree(headers / "rga", out / "headers/rga")
        receipt["source_sha256"] = {name: sha(out / "source" / name) for name in SOURCES}
        receipt["headers_sha256"] = {str(p.relative_to(out / "headers")): sha(p)
            for p in sorted((out / "headers").rglob("*")) if p.is_file()}
        command("compiler_version", [compiler, "--version"])
        receipt["compiler_tools"] = {}
        for tool in ("cc1plus", "as", "ld", "collect2"):
            resolved = command("compiler_" + tool, [compiler, "-print-prog-name=" + tool]).strip()
            path = Path(resolved) if Path(resolved).is_absolute() else Path(shutil.which(resolved) or resolved)
            if not path.is_file():
                raise RuntimeError("cannot identify actual compiler tool: " + tool)
            receipt["compiler_tools"][tool] = dict(path=str(path.resolve()), sha256=sha(path))
        binary = out / "same_format_copy_probe"
        command("compile", [compiler, "-std=gnu++17", "-O2", "-Wall", "-Wextra", "-MD",
                            "-MF", out / "probe.d", "-I" + str(out / "headers"), out / "source/probe.cpp",
                            "-o", binary, "-lrga", "-ldl"])
        dependency_text = (out / "probe.d").read_text().replace("\\\n", " ")
        dependency_paths = [Path(word) for word in shlex.split(dependency_text.partition(":")[2])]
        dependencies = {str((p if p.is_absolute() else out / p).resolve()): sha(p if p.is_absolute() else out / p)
                        for p in dependency_paths if (p if p.is_absolute() else out / p).is_file()}
        if not all(any(p.endswith(suffix) for p in dependencies)
                   for suffix in ("/im2d.h", "/same_format_copy.h", "/linux/dma-buf.h", "/linux/dma-heap.h")):
            raise RuntimeError("compiler dependencies do not bind the actual RGA and Linux UAPI headers")
        receipt["compiler_dependency_sha256"] = dependencies
        receipt["executable"] = dict(path=str(binary), sha256=sha(binary), elf=elf(binary))
        if receipt["executable"]["elf"] != dict(elf_class=2, little_endian=True, machine=183):
            raise RuntimeError("expected little-endian ELF64 AArch64 executable")
        libraries = {}
        for line in command("ldd", ["ldd", binary]).splitlines():
            match = re.search(r"(?:=>\s*)?(/\S+)\s+\(", line)
            if match and Path(match[1]).is_file():
                path = Path(match[1]).resolve()
                libraries[str(path)] = dict(sha256=sha(path), elf=elf(path))
        rga_libraries = [p for p in libraries if Path(p).name.startswith("librga")]
        if len(rga_libraries) != 1:
            raise RuntimeError("must identify exactly one actual linked librga ELF")
        receipt["linked_libraries"] = libraries
        receipt["status"] = "target_build_only_capability_unverified"
        save()
        # Bind the copied sources, all compiler-read headers and linked ELF
        # dependencies again immediately before optional device execution.
        for path, expected in dependencies.items():
            if sha(path) != expected:
                raise RuntimeError("compiler input changed after build: " + path)
        for path, data in libraries.items():
            if sha(path) != data["sha256"]:
                raise RuntimeError("linked library changed after build: " + path)
        if args.phase == "experiment":
            receipt["hardware_requested"] = True
            save()
            text = command("probe", [binary, "--frames", args.frames, "--rounds", args.rounds, "--warmup", args.warmup], timeout=10)
            rows = records(text)
            runtimes = [r for r in rows if r.get("event") == "runtime"]
            completions = [r for r in rows if r.get("event") == "complete"]
            checks = [r for r in rows if r.get("event") == "correctness"]
            pairs = [r for r in rows if r.get("event") == "pair"]
            receipt["hardware_copy_executed"] = any(r.get("exact") for r in checks)
            if len(runtimes) != 1 or str(Path(runtimes[0]["library_path"]).resolve()) != rga_libraries[0]:
                raise RuntimeError("queried runtime is not the hashed linked librga")
            expected_checks = {(name, frame) for name in ("all_65536_words", "zero_ff_checkerboard", "changing_byte_ramps", "moving_word_split")
                               for frame in range(3)}
            if len(checks) != 12 or {(r["pattern"], r["frame"]) for r in checks} != expected_checks or any(
                not r["exact"] or not r["source_unchanged"] or not r["snapshot_canaries"] or r["bytes_compared"] != 614400 for r in checks
            ):
                raise RuntimeError("missing full-byte changing-frame correctness evidence")
            if len(pairs) != args.frames * args.rounds or {(r["round"], r["frame"]) for r in pairs} != {
                (round_index, frame) for round_index in range(args.rounds) for frame in range(1, args.frames + 1)
            } or any(not r["exact"] or r["bytes_compared_each"] != 614400 for r in pairs):
                raise RuntimeError("paired copy completion/byte checks incomplete")
            if len(completions) != 1 or not completions[0]["passed"] or not completions[0]["hardware_copy_executed"] or (
                completions[0]["paired_frames"] != len(pairs) or
                completions[0]["rga_completed_including_correctness_and_warmups"] != 12 + args.rounds * (args.frames + args.warmup) or
                completions[0]["cpu_completed_including_warmups"] != args.rounds * (args.frames + args.warmup)
            ):
                raise RuntimeError("probe did not complete the requested genuine copies")
            for pair in pairs:
                expected_order = "cpu_cached_heap_then_rga" if pair["round"] % 2 == 0 else "rga_then_cpu_cached_heap"
                if pair["order"] != expected_order:
                    raise RuntimeError("pair order differs from AB/BA")
                timings = [pair["cpu_cached_heap_copy"], *pair["rga_heap_copy_to_owned_snapshot"].values()]
                if any(not math.isfinite(d[key]) or d[key] < 0 for d in timings for key in ("wall_ms", "thread_cpu_ms")):
                    raise RuntimeError("copy stage timing invalid")
            receipt["runtime_query"] = runtimes[0]
            receipt["completion"] = completions[0]
            receipt["paired_costs"] = dict(pairs=len(pairs), cpu_cached_heap_mean_ms=statistics.mean(r["cpu_cached_heap_copy"]["wall_ms"] for r in pairs),
                rga_to_owned_snapshot_mean_ms=statistics.mean(r["rga_heap_copy_to_owned_snapshot"]["total"]["wall_ms"] for r in pairs),
                median_rga_minus_cpu_ms=statistics.median(r["rga_heap_copy_to_owned_snapshot"]["total"]["wall_ms"] -
                                                        r["cpu_cached_heap_copy"]["wall_ms"] for r in pairs))
            receipt["status"] = "heap_only_correctness_and_paired_copy_cost_complete"
        for name, expected in receipt["source_sha256"].items():
            if sha(out / "source" / name) != expected:
                raise RuntimeError("private compiled source changed: " + name)
        for path, data in libraries.items():
            if sha(path) != data["sha256"]:
                raise RuntimeError("linked library changed: " + path)
        for path, expected in dependencies.items():
            if sha(path) != expected:
                raise RuntimeError("compiler input changed during probe: " + path)
        if sha(binary) != receipt["executable"]["sha256"]:
            raise RuntimeError("executed binary changed during probe")
    except Exception as error:
        receipt["status"] = "failed_no_performance_claim"
        receipt["error"] = str(error)
        # Recover honest partial evidence even for timeout/nonzero return code.
        if (out / "probe.stdout").is_file():
            try:
                receipt["hardware_copy_executed"] = any(r.get("hardware_copy_executed") or
                    (r.get("event") in ("correctness", "pair") and r.get("exact"))
                    for r in records((out / "probe.stdout").read_text(errors="replace")))
            except (ValueError, KeyError):
                receipt["partial_log_incomplete"] = True
        return 1
    finally:
        receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
        print(json.dumps({"status": receipt["status"], "receipt": str(out / "receipt.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
