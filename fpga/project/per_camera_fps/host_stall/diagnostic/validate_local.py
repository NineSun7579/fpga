"""Linux-only validation of the prepared local artifacts; no board/device access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess

from prepare_diagnostic import exact, instrument

HERE = Path(__file__).resolve().parent


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def section(data: bytes, begin: bytes, end: bytes) -> bytes:
    if data.count(begin) != 1 or data.count(end) != 1:
        raise ValueError(f"scope anchors not unique: {begin!r}, {end!r}")
    return data[data.index(begin):data.index(end)]


def fields(line: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in line.split() if "=" in part)


def validate(prepared: Path, output: Path) -> dict:
    if platform.system() != "Linux":
        raise ValueError("run under native Linux or local WSL; this validator does not simulate clock APIs")
    prepared, output = prepared.resolve(), output.resolve()
    if not prepared.is_relative_to(HERE) or not output.is_relative_to(HERE):
        raise ValueError("validation paths must be inside diagnostic/")
    manifest = json.loads((prepared / "manifest.json").read_bytes())
    for directory, entries in (("frozen", manifest["baseline_files"]), ("candidate", manifest["candidate_files"])):
        for entry in entries:
            data = (prepared / directory / entry["path"]).read_bytes()
            if sha(data) != entry["sha256"] or len(data) != entry["size"]:
                raise ValueError(f"prepared artifact SHA/size mismatch: {directory}/{entry['path']}")
    if sha((prepared / "diagnostic.patch").read_bytes()) != manifest["patch_sha256"]:
        raise ValueError("patch SHA mismatch")
    if (HERE / "stall_timing.h").read_bytes() != (prepared / "candidate/src/stall_timing.h").read_bytes():
        raise ValueError("prepared header is stale")
    baseline = (prepared / "frozen/src/main.cpp").read_bytes()
    if instrument(baseline) != (prepared / "candidate/src/main.cpp").read_bytes():
        raise ValueError("prepared main is stale or differs from exact anchored instrumentation")
    for rejected in (lambda: instrument(baseline + b"\n"),
                     lambda: exact(b"missing", "anchor", "replacement"),
                     lambda: exact(b"anchor anchor", "anchor", "replacement")):
        try:
            rejected()
        except ValueError:
            continue
        raise AssertionError("hash mismatch or non-unique/missing anchor was not rejected")
    output.mkdir(parents=True, exist_ok=True)
    commands = []

    def run(args: list[str], cwd: Path = HERE) -> subprocess.CompletedProcess:
        result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        commands.append({"argv": args, "cwd": str(cwd), "returncode": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode != 0:
            (output / "failed_validation.json").write_text(json.dumps(commands, indent=2) + "\n")
            raise RuntimeError(f"local command failed: {args!r}\n{result.stdout}\n{result.stderr}")
        return result

    compiler = run(["g++", "--version"]).stdout.splitlines()[0]
    qt_version = run(["pkg-config", "--modversion", "Qt5Widgets"]).stdout.strip()
    qt_flags = run(["pkg-config", "--cflags", "Qt5Widgets"]).stdout.split()
    native = output / "stall_timing_selftest"
    run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-pthread",
         str(HERE / "stall_timing_selftest.cpp"), "-o", str(native)])
    result = run([str(native)])
    (output / "selftest.stdout").write_text(result.stdout)
    (output / "selftest.stderr").write_text(result.stderr)
    if "STALL_TIMING_SELFTEST_PASS" not in result.stdout:
        raise AssertionError("real clock test did not report PASS")
    lines = result.stderr.splitlines()
    camera = [fields(line) for line in lines if line.startswith("[stall_camera_window]") and fields(line)["camera"] == "1"]
    if len(camera) != 1:
        raise AssertionError(f"expected one camera window, got {len(camera)}")
    expected = {"camera": 1, "attempts": 5, "success": 2, "error": 1, "no_new": 1, "unstable": 1,
                "tag_advance_sum": 4, "tag_comparisons": 2, "tag_regressions": 0}
    if any(int(camera[0][key]) != value for key, value in expected.items()):
        raise AssertionError(f"all-outcome/tag overcount check failed: {camera[0]}")
    if not int(camera[0]["window_begin_ns"]) <= int(camera[0]["first_attempt_begin_ns"]) <= int(camera[0]["last_attempt_end_ns"]) <= int(camera[0]["window_end_ns"]):
        raise AssertionError("camera window bounds do not enclose observed attempts")
    ioctl_windows = [fields(line) for line in lines if line.startswith("[stall_ioctl_window]")]
    value = next(window for window in ioctl_windows if int(window["attempts"]) == 3)
    checks = {"success": 1, "failure": 2, "rc_failure": 1, "alarm_failure": 1,
              "failure_ioctl_wall_sum_ns": 10050000000, "failure_ioctl_wall_max_ns": 10000000000,
              "failure_ioctl_cpu_sum_ns": 7000000, "failure_ioctl_cpu_max_ns": 4000000}
    if any(int(value[key]) != expected for key, expected in checks.items()):
        raise AssertionError(f"failure censoring check failed: {value}")
    ioctl_records = [fields(line) for line in lines if line.startswith("[stall_ioctl]")]
    if not any(row["rc"] == "0" and row["raw_errno"] == "11" and row["errno_valid"] == "0" and row["errno"] == "0" for row in ioctl_records):
        raise AssertionError("successful stale errno was presented as valid")
    if not any(row["rc"] == "0" and row["alarm"] == "1" and row["application_rc"] == "-1" for row in ioctl_records):
        raise AssertionError("alarm failure was dropped")
    slow = next(fields(line) for line in lines if line.startswith("[stall_camera]") and fields(line)["camera"] == "2")
    if int(slow["dma_wait_wall_sum_ns"]) < 20000000 or int(slow["dma_wait_cpu_sum_ns"]) >= int(slow["dma_wait_wall_sum_ns"]) / 5:
        raise AssertionError("real mutex wait was not measured as off-CPU time")
    if int(slow["copy_wall_sum_ns"]) < 20000000 or int(slow["copy_cpu_sum_ns"]) >= int(slow["copy_wall_sum_ns"]) / 5:
        raise AssertionError("synthetic sleep in copy phase did not preserve paired clocks")
    if slow["low_thread_cpu"] != "1":
        raise AssertionError("slow off-CPU camera attempt was not labeled")

    # Compile exact production function bodies with real Qt and retained headers.
    includes = b'''#include <QByteArray>
#include <QElapsedTimer>
#include <QMutex>
#include <QThread>
#include <algorithm>
#include <atomic>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <functional>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include "camera_dma.h"
#include "frame_metrics.h"
#include "vision_types.h"
#include "stall_timing.h"
'''
    scope_hashes = {}
    for directory in ("frozen", "candidate"):
        data = (prepared / directory / "src/main.cpp").read_bytes()
        scope = includes + section(data, b"static const int IMG_W = 640;", b"/* ---------------- dma-heap")
        scope += section(data, b"struct DmaOp {", b"struct ModelInfo {")
        scope += section(data, b"class PangoDev {", b"class CameraThread : public QThread {")
        source = output / f"{directory}_capture_scopes.cpp"
        source.write_bytes(scope)
        scope_hashes[directory] = sha(scope)
        run(["g++", "-std=c++17", "-Wall", "-Wextra", "-fPIC", "-fsyntax-only", *qt_flags,
             "-I" + str(prepared / directory / "src"), "-I" + str(HERE), str(source)])

    replay = output / "patch_replay"
    if replay.exists():
        shutil.rmtree(replay)
    (replay / "src").mkdir(parents=True)
    shutil.copyfile(prepared / "frozen/src/main.cpp", replay / "src/main.cpp")
    run(["patch", "--batch", "--binary", "-p1", "-i", str(prepared / "diagnostic.patch")], replay)
    if sorted(str(path.relative_to(replay)) for path in replay.rglob("*") if path.is_file()) != ["src/main.cpp", "src/stall_timing.h"]:
        raise AssertionError("application patch touched more than two files")
    for relative in ("src/main.cpp", "src/stall_timing.h"):
        if (replay / relative).read_bytes() != (prepared / "candidate" / relative).read_bytes():
            raise AssertionError(f"patch replay not byte-identical: {relative}")
    receipt = {
        "stage": "prepared_not_built", "board_access": False, "deployed": False,
        "host": {"platform": platform.platform(), "machine": platform.machine(), "compiler": compiler, "qt": qt_version},
        "baseline_main_sha256": manifest["baseline_main_sha256"], "patch_sha256": manifest["patch_sha256"],
        "checks": ["real Linux wall/thread CPU sleep and busy clocks", "synthetic all-ioctl failure sum/max and valid errno",
                   "real-thread TID/TLS isolation", "all camera outcomes and tag no-overcount", "explicit camera window bounds",
                   "baseline and candidate exact capture scopes compile with real Qt", "two-file clean byte-identical patch replay",
                   "baseline SHA and unique byte-anchor rejection", "real mutex wait and copy-phase sleep with deferred ioctl drain"],
        "selftest_stdout": result.stdout.strip(), "selftest_binary_sha256": sha(native.read_bytes()),
        "capture_scope_sha256": scope_hashes,
        "limits": ["capture scope syntax compilation only; no full target viewer build", "x86_64 WSL clock overhead is not RK3568 overhead", "no runtime DMA or rendering test"]
                  + ([] if manifest["project_bytes_present"] else ["detview.pro bytes missing"]),
        "commands": commands,
    }
    (output / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (output / "failed_validation.json").unlink(missing_ok=True)
    print(json.dumps({"stage": receipt["stage"], "checks": receipt["checks"], "selftest_stdout": receipt["selftest_stdout"]}, indent=2))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=HERE / "prepared")
    parser.add_argument("--output", type=Path, default=HERE / "validation")
    args = parser.parse_args()
    validate(args.prepared, args.output)
