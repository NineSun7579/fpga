"""Build/run an isolated pinned-model decoder benchmark without viewer changes."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import posixpath
import shlex
import time


def run(output_dir, remote_root, iterations, helper_path, production_compat=False):
    base = Path(__file__).parent
    source_dir = base / "host_acceleration"
    spec = importlib.util.spec_from_file_location("migration_board_connection", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    client = helper.connect()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "isolated_decoder_experiment_viewer_unchanged", "remote_root": remote_root,
                "files": [], "iterations_per_frame": iterations, "frames": 30,
                "production_compatibility": production_compat,
                "limits": ["viewer remains running; NPU acquisition can contend",
                           "decoder timings use identical immutable outputs",
                           "not FPGA execution or completed viewer FPS"]}
    (output_dir / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    remote_source = posixpath.join(remote_root, "host_acceleration")
    remote_board = posixpath.join(remote_root, "board")
    remote_sdk = posixpath.join(remote_root, "sdk")
    def command(label, text, timeout=120, sudo=False):
        # Drain both streams through a remote file to prevent a compiler's
        # stderr pipe from filling while the SSH helper waits for stdout EOF.
        log_path = posixpath.join(remote_root, label + ".log")
        if label not in {"initial_processes", "create_workspace"}:
            wrapped = "(" + text + ") >" + shlex.quote(log_path) + " 2>&1"
            rc, _, error_text = helper.run(client, wrapped, timeout=timeout, sudo=sudo)
            with client.open_sftp() as sftp:
                with sftp.open(log_path, "r") as stream:
                    stdout = stream.read().decode("utf-8", errors="replace")
            stderr = error_text
        else:
            rc, stdout, stderr = helper.run(client, text, timeout=timeout, sudo=sudo)
        (output_dir / (label + ".txt")).write_text(stdout + stderr, encoding="utf-8")
        print(label, "return_code", rc, flush=True)
        if rc:
            print((stdout + stderr)[-8000:], flush=True)
            raise RuntimeError(f"Board stage {label} failed ({rc})")
        return stdout
    try:
        command("initial_processes", "ps -eo pid,etimes,args | grep -E '[d]etview|[c]amview'", sudo=True)
        command("create_workspace", "mkdir -p " + " ".join(shlex.quote(p) for p in (remote_source, remote_board, remote_sdk)))
        files = [(source_dir / name, posixpath.join(remote_source, name)) for name in
                 ("bench.cpp", "selftest.cpp", "raw_dfl_native.h", "raw_dfl_reference.h", "legacy_production_adapter.h")]
        files += [(base / "board/board_production_decoder.inc", posixpath.join(remote_board, "board_production_decoder.inc")),
                  (base.parent / "hardware_acceleration/rknn_io/prepared/sdk/rknn_api.h", posixpath.join(remote_sdk, "rknn_api.h"))]
        with client.open_sftp() as sftp:
            for local, remote in files:
                data = local.read_bytes()
                sftp.put(str(local), remote)
                manifest["files"].append({"local": str(local), "remote": remote, "sha256": hashlib.sha256(data).hexdigest()})
            rows = json.loads((base / "evaluation_frames/manifest.json").read_text(encoding="utf-8"))["images"]
            with sftp.open(posixpath.join(remote_root, "road_frames.txt"), "w") as stream:
                stream.write("\n".join(row["board_path"] for row in rows) + "\n")
        compile_prefix = "g++ -std=c++17 -O3 -fPIC -Wall -Wextra -Wpedantic -fno-fast-math -ffp-contract=off -I" + shlex.quote(remote_sdk)
        command("compile_selftest", compile_prefix + " -DRAW_DFL_WITH_LEGACY " + shlex.quote(remote_source + "/selftest.cpp")
                + " $(pkg-config --cflags --libs Qt5Core) -o " + shlex.quote(remote_root + "/raw_dfl_selftest"), timeout=180)
        command("selftest", shlex.quote(remote_root + "/raw_dfl_selftest"))
        command("compile_benchmark", compile_prefix + " " + shlex.quote(remote_source + "/bench.cpp")
                + " -L/usr/lib -Wl,-rpath,/usr/lib -lrknnrt $(pkg-config --cflags --libs Qt5Core opencv4) -o "
                + shlex.quote(remote_root + "/raw_dfl_bench"), timeout=180)
        model = "/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn"
        digest = "be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9"
        arguments = [remote_root + "/raw_dfl_bench", model, remote_root + "/road_frames.txt", remote_root + "/result",
                     digest, str(iterations), "30", "0.25", "0.45", "1" if production_compat else "0"]
        command("benchmark", " ".join(shlex.quote(arg) for arg in arguments), timeout=180, sudo=True)
        with client.open_sftp() as sftp:
            for name in sftp.listdir(remote_root):
                if name.startswith("result_") and name.endswith((".csv", ".txt")):
                    sftp.get(posixpath.join(remote_root, name), str(output_dir / name))
        command("final_processes", "ps -eo pid,etimes,args | grep -E '[d]etview|[c]amview'", sudo=True)
        manifest["completed"] = True
        print("NATIVE_BOARD_BENCHMARK_COMPLETE", output_dir, flush=True)
    finally:
        client.close()
        (output_dir / "experiment_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "native_board_benchmark")
    parser.add_argument("--remote", default="/tmp/fpga_v8_decoder_" + str(int(time.time())))
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--production-compat", action="store_true")
    parser.add_argument("--ssh-helper", type=Path, default=Path(__file__).parents[1] / "board_ssh.py")
    args = parser.parse_args()
    if args.iterations < 1:
        raise ValueError("Iterations must be positive")
    run(args.out, args.remote, args.iterations, args.ssh_helper, args.production_compat)
