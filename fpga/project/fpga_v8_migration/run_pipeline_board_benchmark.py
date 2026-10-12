"""Run isolated AB/BA completed-inference profiles; never replaces the viewer."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import shlex
import time


def run(output_dir, remote_root, cycles, compatibility, helper_path, probe=False, runtime_compat=True):
    base = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("migration_board_connection", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = helper.connect()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "isolated_paired_completed_inference_not_viewer_or_FPGA_fps",
                "remote_root": remote_root, "cycles_per_block": cycles,
                "production_compatibility": compatibility, "pinned_runtime_dequantization": runtime_compat,
                "dequant_probe": probe, "files": [],
                "viewer_action": "none; benchmark shares board resources"}
    manifest_path = output_dir / "experiment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    remote_source = remote_root + "/host_acceleration"
    remote_board = remote_root + "/board"
    remote_sdk = remote_root + "/sdk"

    def command(label, text, timeout=120, sudo=False, allow_failure=False):
        log_path = remote_root + "/" + label + ".log"
        rc, _, stderr = helper.run(client, "(" + text + ") >" + shlex.quote(log_path) + " 2>&1",
                                  timeout=timeout, sudo=sudo)
        with client.open_sftp() as sftp:
            with sftp.open(log_path, "r") as stream:
                stdout = stream.read().decode("utf-8", errors="replace")
        (output_dir / (label + ".txt")).write_text(stdout + stderr, encoding="utf-8")
        print(label, "return_code", rc, flush=True)
        if rc and not allow_failure:
            print((stdout + stderr)[-8000:], flush=True)
            raise RuntimeError(f"Board stage {label} failed ({rc})")
        return rc

    environment = """date -Iseconds
uname -a
g++ --version
pkg-config --modversion Qt5Core opencv4
sha256sum /usr/lib/librknnrt.so
ps -eo pid,etimes,args | grep -E '[d]etview|[c]amview'
cat /proc/loadavg
for node in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq /sys/devices/system/cpu/cpufreq/policy*/scaling_governor /sys/class/thermal/thermal_zone*/temp /sys/kernel/debug/rknpu/load; do
    if test -r "$node"; then printf '%s=' "$node"; cat "$node"; fi
done"""
    try:
        rc, stdout, stderr = helper.run(client, "mkdir -p " + " ".join(shlex.quote(path) for path in
                                      (remote_source, remote_board, remote_sdk)), timeout=30)
        if rc:
            raise RuntimeError("Cannot create board experiment directory: " + stdout + stderr)
        command("environment_before", environment, sudo=True)
        files = [(base / "host_acceleration" / name, remote_source + "/" + name) for name in
                 ("pipeline_bench.cpp", "dequant_probe.cpp", "raw_dfl_native.h", "raw_dfl_reference.h", "legacy_production_adapter.h")]
        files += [(base / "board/board_production_decoder.inc", remote_board + "/board_production_decoder.inc"),
                  (base.parent / "hardware_acceleration/rknn_io/prepared/sdk/rknn_api.h", remote_sdk + "/rknn_api.h")]
        with client.open_sftp() as sftp:
            for local, remote in files:
                data = local.read_bytes()
                sftp.put(str(local), remote)
                manifest["files"].append({"local": str(local), "remote": remote,
                                          "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            frame_manifest = base / "evaluation_frames/manifest.json"
            rows = json.loads(frame_manifest.read_text(encoding="utf-8"))["images"]
            manifest["frames_manifest_sha256"] = hashlib.sha256(frame_manifest.read_bytes()).hexdigest()
            with sftp.open(remote_root + "/road_frames.txt", "w") as stream:
                stream.write("\n".join(row["board_path"] for row in rows) + "\n")
        entry_source = "dequant_probe.cpp" if probe else "pipeline_bench.cpp"
        command("compile", "g++ -std=c++17 -O3 -fPIC -Wall -Wextra -Wpedantic -fno-fast-math -ffp-contract=off -I"
                + shlex.quote(remote_sdk) + " " + shlex.quote(remote_source + "/" + entry_source)
                + " -L/usr/lib -Wl,-rpath,/usr/lib -lrknnrt -ldl $(pkg-config --cflags --libs Qt5Core opencv4) -o "
                + shlex.quote(remote_root + "/pipeline_bench"), timeout=240)
        command("binary_identity", "sha256sum " + shlex.quote(remote_root + "/pipeline_bench") + "\nldd "
                + shlex.quote(remote_root + "/pipeline_bench"))
        model = "/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn"
        arguments = [remote_root + "/pipeline_bench", model, remote_root + "/road_frames.txt",
                     remote_root + "/pipeline", "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9",
                     str(cycles), "1" if compatibility else "0", "1" if runtime_compat else "0"]
        if probe:
            arguments = arguments[:5]
        rc = command("benchmark", " ".join(shlex.quote(arg) for arg in arguments), timeout=600,
                     sudo=True, allow_failure=True)
        with client.open_sftp() as sftp:
            for name in sftp.listdir(remote_root):
                if name.startswith("pipeline_") and name.endswith((".csv", ".json")):
                    sftp.get(posixpath.join(remote_root, name), str(output_dir / name))
        command("environment_after", environment, sudo=True)
        manifest["benchmark_return_code"] = rc
        manifest["completed"] = True
        print("PIPELINE_BOARD_BENCHMARK_RECORDED", "return_code", rc, output_dir, flush=True)
    finally:
        client.close()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "pipeline_board_benchmark")
    parser.add_argument("--remote", default="/tmp/fpga_v8_pipeline_" + str(int(time.time())))
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--queried-affine", action="store_true")
    parser.add_argument("--ssh-helper", type=Path, default=Path(__file__).parents[1] / "board_ssh.py")
    args = parser.parse_args()
    if args.cycles < 1:
        raise ValueError("Cycles must be positive")
    run(args.out, args.remote, args.cycles, not args.canonical, args.ssh_helper, args.probe, not args.queried_affine)
