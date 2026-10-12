"""Local AArch64 NEON tests; reuse private tools read-only, never install/SSH/NPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-root", type=Path, default=ROOT.parent / "rga/local_evidence/private_cross_root")
    parser.add_argument("--out", type=Path, default=ROOT / "validation/neon_01")
    args = parser.parse_args()
    tools, out = args.tools_root.resolve(), args.out.resolve()
    if ROOT not in out.parents:
        parser.error("all generated files must remain in rknn_io/")
    out.mkdir(parents=True, exist_ok=False)
    (out / "tmp").mkdir()
    env = dict(os.environ, PATH=str(tools / "usr/bin") + os.pathsep + os.environ.get("PATH", ""),
               LD_LIBRARY_PATH=str(tools / "usr/lib/x86_64-linux-gnu"), TMPDIR=str(out / "tmp"))
    cc = tools / "usr/bin/aarch64-linux-gnu-g++-13"
    qemu = tools / "usr/bin/qemu-aarch64"
    receipt = dict(passed=False, hardware_executed=False, execution="local_QEMU_AArch64_NEON",
                   packages_installed=False, tools_read_only=True, commands=[],
                   source_sha256={name: sha(ROOT / name) for name in ("native_adapter.h", "neon_selftest.cpp", "verify_neon.py")},
                   tools_sha256={str(path): sha(path) for path in (cc, qemu)})

    def run(label, argv):
        proc = subprocess.run([str(v) for v in argv], cwd=ROOT, env=env, capture_output=True, timeout=60)
        (out / (label + ".stdout")).write_bytes(proc.stdout)
        (out / (label + ".stderr")).write_bytes(proc.stderr)
        receipt["commands"].append(dict(label=label, argv=[str(v) for v in argv], returncode=proc.returncode,
                                        stdout_sha256=sha(out / (label + ".stdout")), stderr_sha256=sha(out / (label + ".stderr"))))
        if proc.returncode:
            raise RuntimeError(label + " failed: " + proc.stderr.decode(errors="replace"))
        return proc.stdout

    try:
        flags = ["--sysroot=" + str(tools), "-std=c++17", "-O3", "-Wall", "-Wextra", "-pedantic",
                 "-fno-fast-math", "-ffp-contract=off", "-I" + str(ROOT / "prepared")]
        binary = out / "neon_selftest_aarch64"
        run("compiler", [cc, "--version"])
        run("compile", [cc, *flags, ROOT / "neon_selftest.cpp", "-o", binary])
        archived = ROOT.parent / "runs/rknn_diagnose_4ad952c78e814a14b87784e51ec250de/artifacts"
        baseline = ROOT.parent / "runs/rknn_experiment_892e53bcaad44f23bcb0c617dd6c77dd/artifacts/results"
        params = []
        for i in range(4):
            params += [archived / f"native.c1.o{i}.f32", baseline / f"native_bright_baseline_cam1_cert_baseline.c1.o{i}.f32"]
        # Verify downloads against their actual producing runtime event hashes.
        expected = {}
        for log in (archived / "supervisor.stdout", baseline / "native_bright_baseline_cam1_cert_baseline.stdout"):
            for line in log.read_text().splitlines():
                if line.startswith("{"):
                    row = json.loads(line)
                    if row.get("event") == "output_snapshot" and row["completion"] == 1:
                        expected[Path(row["path"]).name] = row["sha256"]
        for path in params:
            if sha(path) != expected[path.name]:
                raise RuntimeError("archive hash mismatch: " + str(path))
        receipt["archive_sha256"] = {str(path): sha(path) for path in params}
        text = run("qemu", [qemu, "-L", tools / "usr/aarch64-linux-gnu", binary, *params]).decode()
        if "neon_cases=0;" in text or "bitwise_parity=true" not in text:
            raise RuntimeError("missing real NEON execution/parity evidence")
        # Also run existing independent IEEE and adapter metadata/bounds checks
        # on this ISA; these exercise default conversion dispatch too.
        for test in ("scale_selftest", "adapter_selftest"):
            exe = out / (test + "_aarch64")
            run(test + "_compile", [cc, *flags, ROOT / (test + ".cpp"), "-o", exe])
            run(test + "_qemu", [qemu, "-L", tools / "usr/aarch64-linux-gnu", exe])
        receipt["executable_sha256"] = sha(binary)
        for name, digest in receipt["source_sha256"].items():
            if sha(ROOT / name) != digest:
                raise RuntimeError("source changed during tests: " + name)
        receipt["passed"] = True
        print(text, end="")
    finally:
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
