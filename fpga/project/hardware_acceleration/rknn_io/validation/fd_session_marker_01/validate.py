"""Validation only: current session-marker build and pure proof checks, no RKNN runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PRIOR = ROOT / "validation/fd_retirement_01/receipt.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    prior = json.loads(PRIOR.read_text())
    names = list(prior["source_sha256"])
    assert len(names) == 9
    before = {name: digest(ROOT / name) for name in names}
    changed = [name for name in names if before[name] != prior["source_sha256"][name]]
    assert changed == ["bench.cpp"], changed
    old_receipt_hash = digest(PRIOR)
    marker = 'emitJson({{"event", "dma_heap_session_started"}, {"purpose", purpose}});'
    source = (ROOT / "bench.cpp").read_text()
    constructor = source[source.index("ImportedSession(Api &api"):source.index("~ImportedSession()")]
    assert marker in constructor and source.count(marker) == 1
    save(OUT / "source_before.json", before)

    argv = [sys.executable, str(ROOT / "local_tests/fd_import_checks.py"), "--binding-only", "--out", str(OUT / "checks")]
    process = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60, check=False)
    (OUT / "runner.stdout").write_bytes(process.stdout)
    (OUT / "runner.stderr").write_bytes(process.stderr)
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    checks = json.loads((OUT / "checks/receipt.json").read_text())
    assert checks["source_sha256"] == before
    assert checks["binding_only"] and checks["lifecycle_asan_ubsan_passed"] is None
    for key in ("benchmark_compile_passed", "actual_mocked_retirement_event_fields_passed",
                "deferred_retirement_proof_gates_passed", "legacy_runner_regression_passed",
                "first_binding_policy_selftest_passed", "strict_candidate_and_control_baseline_certificate_rejections_passed"):
        assert checks[key], key
    # Reuse the exact receipt command arguments with only output paths remapped.
    reused = []
    old_out = str(PRIOR.parent)
    for name in ("benchmark_build", "retirement_event_build", "retirement_event"):
        old = next(c for c in prior["commands"] if c["name"] == name)
        current = next(c for c in checks["commands"] if c["name"] == name)
        expected = [arg.replace(old_out, str(OUT / "checks")) for arg in old["argv"]]
        assert current["argv"] == expected, name
        assert current["returncode"] == 0
        reused.append(current)

    spec = importlib.util.spec_from_file_location("marker_fd_checks", ROOT / "local_tests/fd_import_checks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    starts = [dict(event="dma_heap_session_started", purpose=purpose) for purpose in ("ownership_probe", module.FD)]
    module.runner.validate_fd_evidence(starts + module.synthetic_evidence(), 3, 5, True)
    module.runner.validate_fd_evidence(starts + module.synthetic_evidence(50, 5, False), 50, 5, False)
    rows = module.runner.events(OUT / "checks/retirement_event.stdout")
    assert len(rows) == 4
    for row in rows:
        marked = [dict(event="dma_heap_session_started", purpose=row["purpose"]), row]
        if row["purpose"] == "mock_success":
            module.runner.refuse_process_teardown_retirement(marked)
        else:
            try:
                module.runner.refuse_process_teardown_retirement(marked)
            except RuntimeError:
                pass
            else:
                raise AssertionError("session marker permitted deferred retirement")
    assert {name: digest(ROOT / name) for name in names} == before
    assert digest(PRIOR) == old_receipt_hash
    warnings = {name: (OUT / "checks" / (name + ".stderr")).read_text() for name in ("benchmark_build", "retirement_event_build")}
    assert not any(warnings.values()), warnings
    receipt = dict(status="local_session_marker_compile_and_proof_checks_passed", source_sha256=before,
                   files_changed_since_prior_receipt=changed, source_files_stable=True, source_edits_by_this_validation=False,
                   prior_receipt_sha256=old_receipt_hash, prior_receipt_unchanged=True, prior_commands_reused=reused,
                   fd_checks_command=dict(argv=argv, returncode=process.returncode),
                   marker_in_constructor_verified=True, marker_acceptance_for_certification_and_timing_proofs_passed=True,
                   marked_deferred_retirement_rejections_passed=True, actual_mocked_retirement_events_passed=True,
                   sdk_qt_benchmark_compile_passed=True, compiler_warnings=False, lifecycle_asan_rerun=False,
                   lifecycle_header_sha256_unchanged=before["dma_heap_import.h"],
                   benchmark_sha256=digest(OUT / "checks/rknn_io_bench_host"),
                   retirement_event_binary_sha256=digest(OUT / "checks/retirement_event_selftest"),
                   nested_receipt_sha256=digest(OUT / "checks/receipt.json"),
                   log_sha256={str(p.relative_to(OUT)): digest(p) for p in OUT.rglob("*") if p.suffix in (".stdout", ".stderr")},
                   ssh_used=False, hardware_executed=False, hardware_certified=False, performance_claim=False,
                   imported_constructor_executed_on_hardware=False, parent_restoration_guard_tests_rerun=False)
    save(OUT / "receipt.json", receipt)
    print(json.dumps(dict(status=receipt["status"], receipt=str(OUT / "receipt.json"), source_files_stable=True, hardware_executed=False)))


if __name__ == "__main__":
    main()
