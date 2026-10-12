"""Local-only build/validation of the future hardware parity tool.

No SSH, upload, driver change, device open, viewer stop or hardware run. Parent
owns target compilation/deployment and the future hardware acceptance runner.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(path):
    path = Path(path).resolve()
    if os.name == "nt":
        return "/mnt/" + path.drive[0].lower() + "/" + path.as_posix()[3:]
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abi-dir", type=Path,
                        default=Path("D:/race/ov56401/project/fpga_v8_migration"))
    parser.add_argument("--compiler", default="g++")
    parser.add_argument("--wsl-distro", default="Ubuntu-24.04")
    args = parser.parse_args()
    sources = {
        "background_thumbnail_parity.cpp": ROOT / "host/background_thumbnail_parity.cpp",
        "background_thumbnail_reader.hpp": ROOT / "host/background_thumbnail_reader.hpp",
        "pcie_session.hpp": ROOT / "host/pcie_session.hpp",
        "bound_rknn.hpp": ROOT / "host/bound_rknn.hpp",
        "rknn_api.h": ROOT.parent / "display_latency_delivery/src/rknn_api.h",
        "cooperative_linux_transport/driver_abi.hpp": args.abi_dir / "cooperative_linux_transport/driver_abi.hpp",
        "pango_zc_uapi.h": ROOT / "driver/pango_zc_uapi.h",
    }
    out = ROOT / "background_parity_local"
    out.mkdir(exist_ok=True)
    for name, source in sources.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    prefix = ["wsl", "-d", args.wsl_distro, "--"] if os.name == "nt" else []
    binary = out / "background_thumbnail_parity_local"
    flags = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread"]
    command = [args.compiler, *flags, "-I" + local_path(out),
               local_path(out / "background_thumbnail_parity.cpp"), "-o", local_path(binary)]
    results = []

    def run(cmd, expected=0):
        result = subprocess.run(prefix + cmd, capture_output=True, text=True, timeout=120)
        results.append({"command": cmd, "return_code": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        (ROOT / "background_parity_local_build.log").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8")
        if result.returncode != expected:
            raise RuntimeError(result.stdout + result.stderr)
        return result

    run(command)
    run([local_path(binary), "--self-test"])
    run([local_path(binary), "--help"])
    # All invalid options reject before constructing a PCIe session.
    for invalid in (["--cameras", "1,1"], ["--count", "9"], ["--cameras", "7"],
                    ["--timeout", "0"], ["--unknown", "1"]):
        run([local_path(binary), *invalid], expected=2)
    for name in ("thumbnail_six_parity.cpp", "thumbnail_parity.cpp", "paired_pointer.cpp"):
        run([args.compiler, *flags, "-I" + local_path(out), "-fsyntax-only",
             local_path(ROOT / "host" / name)])
    run([args.compiler, *flags, "-I" + local_path(out), "-DOFFLOAD_SHARED_INPUT",
         "-fsyntax-only", local_path(ROOT / "host/paired_pointer.cpp")])
    for name, source in sources.items():
        if source.read_bytes() != (out / name).read_bytes():
            raise RuntimeError("Source changed during build: " + name)
    manifest = {
        "hardware_executed": False, "uploaded": False, "target_compiled": False,
        "local_binary": str(binary), "binary_sha256": digest(binary),
        "sources_sha256": {name: digest(path) for name, path in sources.items()},
        "helper_sha256": digest(Path(__file__)),
        "protocol_sha256": digest(ROOT / "BACKGROUND_PROTOCOL.md"),
        "documentation_sha256": digest(ROOT / "README_BACKGROUND_PARITY.md"),
        "checks": results,
        "target_build_command": "g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread -I. background_thumbnail_parity.cpp -o background_thumbnail_parity",
        "limitations": ["Local tests do not establish hardware pixel parity or RAW/background timing alignment.",
                        "No SSH orchestration/recovery implemented; parent owns board operations."],
    }
    (ROOT / "background_parity_local_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"local_checks_passed": True, "hardware_executed": False,
                      "manifest": str(ROOT / "background_parity_local_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
