"""Audit local receipts and deferred-runner guard; writes no external files."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "local_evidence"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reference = json.loads((EVIDENCE / "reference_receipt.json").read_text())
    checks = json.loads((EVIDENCE / "local_checks.json").read_text())
    arm = json.loads((EVIDENCE / "aarch64_local_checks.json").read_text())
    bundle = json.loads((EVIDENCE / "bundle_sha256.json").read_text())
    if not reference.get("cpp_python_oracle_exact") or not checks.get("passed") or not arm.get("passed"):
        raise RuntimeError("Missing successful local reference, syntax or ARM emulation receipts")
    if any(row.get("hardware_executed") for row in (reference, checks, arm, bundle)):
        raise RuntimeError("Local preparation receipt incorrectly claims hardware execution")
    for row in (reference, checks, arm):
        for name, expected in row.get("source_sha256", {}).items():
            if sha(HERE / name) != expected:
                raise RuntimeError(f"Stale local source check receipt: {name}")
    sanitized = [json.loads(line) for line in (EVIDENCE / "reference_sanitized.jsonl").read_text().splitlines()]
    if len(sanitized) != 7 or not sanitized[0].get("passed"):
        raise RuntimeError("Missing sanitized exhaustive CPU selftest")
    for expected, actual in zip([reference["gradient"], *reference["fixtures"]], sanitized):
        for key in ("raw_fnv1a64", "rgb_fnv1a64", "model_fnv1a64"):
            if expected[key] != actual[key]:
                raise RuntimeError("Sanitized CPU result differs from independent oracle")
    archive_path = EVIDENCE / bundle["name"]
    if sha(archive_path) != bundle["sha256"]:
        raise RuntimeError("Staged source bundle hash mismatch")
    with tarfile.open(archive_path, "r:gz") as archive:
        for name in ("reference.hpp", "reference_selftest.cpp", "native_probe.cpp", "run_board.py", "README.md"):
            data = archive.extractfile(name).read()
            if hashlib.sha256(data).hexdigest() != sha(HERE / name):
                raise RuntimeError("Bundle contains stale source")
        for row in reference["fixtures"]:
            if hashlib.sha256(archive.extractfile("fixtures/"+row["name"]).read()).hexdigest() != row["raw_sha256"]:
                raise RuntimeError("Bundle contains a different fixture")
    # Without authorization flag, this must stop before architecture checks,
    # command execution, fixture/header access, or hardware device opening.
    guard = subprocess.run([sys.executable, str(HERE / "run_board.py")], text=True, capture_output=True, check=False)
    if guard.returncode != 2 or "Deferred: --board-free is required" not in guard.stderr:
        raise RuntimeError("Deferred runner guard did not reject execution")
    guard_with_flag = subprocess.run([sys.executable, str(HERE / "run_board.py"), "--board-free"],
                                    text=True, capture_output=True, check=False)
    if guard_with_flag.returncode != 2 or "Run this hardware runner on the RK3568 AArch64 board" not in guard_with_flag.stderr:
        raise RuntimeError("Local x86 guard did not reject hardware execution")
    for name in ("prepare_local.py", "run_board.py", "check_local.py", "verify_aarch64.py", "finalize_local.py"):
        compile((HERE / name).read_text(), name, "exec")
    result = {
        "status": "local_preparation_complete", "hardware_executed": False,
        "board_connected": False, "fpga_pcie_dma_opened": False, "viewer_changed": False,
        "board_sdk_verified": False, "rga_driver_verified": False,
        "completed_inference_fps_measured": False, "rkNN_detection_parity_tested": False,
        "cpp_python_oracle_exact": True, "exhaustive_colors": 65536, "historical_fixtures": 6,
        "x86_asan_ubsan_passed": True, "aarch64_neon_emulated_cpu_passed": True,
        "public_sdk_native_syntax_passed": True, "deferred_guard_passed": True,
        "source_sha256": {path.name: sha(path) for path in HERE.iterdir()
                           if path.is_file() and path.suffix in (".cpp", ".hpp", ".py", ".md")},
        "bundle": bundle,
        "parent_future_command": "python3 run_board.py --board-free --fixtures fixtures --headers-root /usr/include --frames 500 --warmup 30 --memory fd --output results_fd",
        "next_required": "Parent first finishes diagnostic compile and declares board free; SFTP private bundle, verify current board SDK/library, run probe, then separate native RKNN parity experiment",
    }
    (EVIDENCE / "handoff_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "hardware_executed": False,
                      "deferred_guard_passed": True, "bundle_sha256": bundle["sha256"]}))


if __name__ == "__main__":
    main()
