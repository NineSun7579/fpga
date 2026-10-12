"""Optional local ARM/NEON CPU validation using private, uninstalled deb packages.

No SSH, no board access, no apt install/update, no RGA execution. All downloaded
packages, extracted tools, executables and receipts stay in local_evidence/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headers-root", type=Path, default=HERE / "local_evidence" / "upstream_headers")
    parser.add_argument("--reuse-tools", action="store_true", help="Reuse tools already privately extracted; no download or extraction")
    args = parser.parse_args()
    evidence = HERE / "local_evidence"
    debs = evidence / "private_cross_debs"
    root = evidence / "private_cross_root"
    debs.mkdir(parents=True, exist_ok=True)
    root.mkdir(exist_ok=True)
    receipt = {"hardware_executed": False, "arm_execution": "local QEMU CPU emulation only",
               "packages_installed": False, "commands": [], "passed": False}
    receipt["source_sha256"] = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                               for name in ("reference.hpp", "reference_selftest.cpp", "native_probe.cpp")}

    def command(argv, env=None, cwd=HERE):
        run = subprocess.run(argv, text=True, capture_output=True, cwd=cwd, env=env, timeout=60, check=False)
        row = {"command": [str(v) for v in argv], "returncode": run.returncode,
               "stdout": run.stdout, "stderr": run.stderr}
        receipt["commands"].append(row)
        if run.returncode:
            raise RuntimeError(f"Local validation command failed: {argv[0]}\n{run.stderr}")
        return row

    try:
        packages = ["g++-13-aarch64-linux-gnu", "gcc-13-aarch64-linux-gnu", "binutils-aarch64-linux-gnu",
                    "libc6-dev-arm64-cross", "libc6-arm64-cross", "linux-libc-dev-arm64-cross",
                    "libgcc-13-dev-arm64-cross", "libgcc-s1-arm64-cross",
                    "libstdc++-13-dev-arm64-cross", "libstdc++6-arm64-cross", "qemu-user", "libcapstone4", "liburing2"]
        if not args.reuse_tools:
            command(["apt-get", "download", *packages], cwd=debs)
        receipt["deb_sha256"] = {}
        for deb in sorted(debs.glob("*.deb")):
            receipt["deb_sha256"][deb.name] = hashlib.sha256(deb.read_bytes()).hexdigest()
            if not args.reuse_tools:
                command(["dpkg-deb", "-x", str(deb), str(root)])
        env = dict(os.environ)
        env["PATH"] = str(root / "usr" / "bin") + os.pathsep + env.get("PATH", "")
        env["LD_LIBRARY_PATH"] = str(root / "usr" / "lib" / "x86_64-linux-gnu")
        cc = root / "usr" / "bin" / "aarch64-linux-gnu-g++-13"
        binary = evidence / "reference_selftest_aarch64"
        command([str(cc), "--version"], env=env)
        flags = ["--sysroot=" + str(root), "-O3", "-std=gnu++14", "-Wall", "-Wextra"]
        command([str(cc), *flags, str(HERE / "reference_selftest.cpp"), "-o", str(binary)], env=env)
        command([str(cc), *flags, "-fsyntax-only", "-I" + str(args.headers_root.resolve()),
                 str(HERE / "native_probe.cpp")], env=env)
        fixtures = [evidence / "fixtures" / f"cam{i}.rgb565" for i in range(1, 7)]
        qemu = root / "usr" / "bin" / "qemu-aarch64"
        row = command([str(qemu), "-L", str(root / "usr" / "aarch64-linux-gnu"), str(binary),
                       *[str(path) for path in fixtures]], env=env)
        records = [json.loads(line) for line in row["stdout"].splitlines()]
        oracle = json.loads((evidence / "reference_receipt.json").read_text())
        if len(records) != 7 or not records[0].get("passed"):
            raise RuntimeError("Missing emulated ARM exhaustive reference evidence")
        for expected, actual in zip([oracle["gradient"], *oracle["fixtures"]], records):
            for key in ("raw_fnv1a64", "rgb_fnv1a64", "model_fnv1a64"):
                if expected[key] != actual[key]:
                    raise RuntimeError(f"ARM NEON vs independent oracle mismatch: {key}")
        (evidence / "reference_aarch64_emulated.jsonl").write_text(row["stdout"], encoding="utf-8")
        receipt["reference_executable_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        for name, expected in receipt["source_sha256"].items():
            if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("Source changed during emulated CPU validation")
        receipt["passed"] = True
    finally:
        (evidence / "aarch64_local_checks.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": True, "hardware_executed": False, "neon_cpu_emulated": True}))


if __name__ == "__main__":
    main()
