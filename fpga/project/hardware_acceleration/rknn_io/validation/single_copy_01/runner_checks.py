"""Pure runner control/evidence checks; substituted process boundary, no RKNN execution."""
import argparse
from collections import Counter
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import struct
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("single_copy_runner", ROOT / "run_target.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
compile((ROOT / "run_target.py").read_text(), str(ROOT / "run_target.py"), "exec")


def config(**overrides):
    data = dict(binary="test_binary", lib="test_lib", dequant_scale="fp16", native_query=9,
                candidates=["native_io_single_copy"], timing_reference="native_io", fixtures=None,
                iterations=50, rounds=4, warmup=5, timeout=120, atol=1e-6, rtol=1e-6)
    data.update(overrides)
    return argparse.Namespace(**data)


def orchestration(timing_reference="native_io", candidate="native_io_single_copy", fail_bitwise=False,
                  fail_control=False):
    calls, parity_calls, saved = [], [], {}
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
        directory = Path(temporary)
        binary = directory / "test_binary"
        binary.write_bytes(b"not executable; process boundary substituted")
        (directory / "build_receipt.json").write_text(json.dumps(dict(executable_sha256="bound",
            prepared_manifest_sha256="bound", rknn_runtime_sha256="bound")))
        args = config(binary=str(binary), candidates=[candidate], timing_reference=timing_reference)
        fixtures = [dict(name=f"fixture{i}") for i in range(4)]

        def bench(args, directory, mode, fixture=None, label="probe", iterations=None, all_snapshots=False):
            calls.append((mode, fixture["name"] if fixture else None, label, iterations or args.iterations, all_snapshots))
            summary = dict(event="summary", completed_fps=10 if mode == timing_reference else 20)
            rows = [summary]
            if mode == "native_io_single_copy":
                rows.append(dict(event="native_input_copy", policy="one_memcpy_full_model_input_each_frame"))
            return dict(label=label, mode=mode, events=rows)

        def parity(reference, actual, args, full=False):
            parity_calls.append((reference["mode"], actual["mode"], full))
            return dict(certified=not (fail_control and full and actual["mode"] == "native_io"),
                        all_float_arrays_bitwise_equal=not (fail_bitwise and not full))

        with patch.object(runner, "target", return_value=dict(library_sha256="bound")), \
             patch.object(runner, "digest", return_value="bound"), patch.object(runner, "bench", side_effect=bench), \
             patch.object(runner, "parity", side_effect=parity), patch.object(runner, "stages", side_effect=lambda r: r["mode"]), \
             patch.object(runner, "save", side_effect=lambda p, v: saved.__setitem__(Path(p).name, copy.deepcopy(v))):
            failed = False
            try:
                runner.experiment(args, dict(fixtures=fixtures), directory)
            except RuntimeError:
                failed = True
        report = saved["report.json"]
        if fail_bitwise or fail_control:
            assert failed and "failed_no_performance_claim" in report["status"]
            if fail_bitwise:
                assert not report["comparisons"][-1]["certified"]
            return
        assert not failed and report["timing_reference"] == timing_reference
        assert len(report["certifications"]) == 4
        assert all(x["reference_profile"] == "baseline" for x in report["certifications"])
        if candidate == "native_io_single_copy":
            assert all(x["native_input_copy"]["policy"] == "one_memcpy_full_model_input_each_frame" for x in report["certifications"])
        assert len(report["timing_reference_certifications"]) == (4 if timing_reference == "native_io" else 0)
        assert all(r == "baseline" for r, _, full in parity_calls if full)
        measured = [x for x in calls if x[1] is not None and not x[4]]
        assert Counter(x[0] for x in measured) == {timing_reference: 16, candidate: 16}
        assert sum(x[3] for x in measured if x[0] == candidate) == 800
        assert sum(x[3] for x in measured if x[0] == timing_reference) == 800
        for i, pair in enumerate(report["comparisons"]):
            assert pair["reference_profile"] == timing_reference and pair["baseline_stages"] == timing_reference
            assert pair["completed_fps_ratio"] == 2
            assert pair["order"] == ([timing_reference, candidate] if i % 2 == 0 else [candidate, timing_reference])
            assert pair["bitwise_arrays_required"] == (candidate == "native_io_single_copy" and timing_reference == "native_io")


orchestration()
orchestration("baseline", "prealloc")
orchestration(fail_bitwise=True)
orchestration(fail_control=True)

# Exercise real bench() receipt checks with archived queried/fixture/tuple events
# as input. Only subprocess/filesystem boundaries are replaced; no model runs.
archive = ROOT.parent / "runs/rknn_experiment_0266179cb55d488f9b1bde85c96b17e5/artifacts/results"
receipt = json.loads((archive / "native_io_bright_baseline_cam1_cert_candidate.receipt.json").read_text())
original = receipt["events"]
input_sha = runner.only(original, "fixture")["input_sha256"]
evidence = dict(event="native_input_copy", mode="native_io_single_copy", policy="one_memcpy_full_model_input_each_frame",
    source_bytes=1228800, allocation_bytes=1228800, input_row_bytes=1920, per_frame_input_bytes_written=1228800,
    includes_warmups=True, byte_match=True, source_sha256=input_sha, copied_sha256=input_sha,
    hash_scope="setup_preflight_before_warmups_and_timing", timed_frame_input_hashes=False)
verifications = [dict(event="native_input_copy_verification", completion=i, byte_match=True,
    checked_before_sync_and_run=True, certification_only=True, source_sha256=input_sha, copied_sha256=input_sha)
    for i in range(1, 4)]
rows = original + [evidence] + verifications
fixture = dict(name="archived_fixture", path="fixtures/bright_baseline_cam1.png", kind="png",
               sha256=runner.only(original, "fixture")["source_sha256"])
ident = runner.only(original, "identity")


def check_evidence(events, all_snapshots=True, accepted=True):
    def digest(path):
        return runner.only(original, "runtime_library")["sha256"] if str(path) == "test_lib" else ident["executable_sha256"]
    with patch.object(runner, "invoke", return_value=dict(returncode=0)), patch.object(runner, "events", return_value=events), \
         patch.object(runner, "hardware_snapshot", return_value={}), patch.object(runner, "dependency_hashes", return_value={}), \
         patch.object(runner, "digest", side_effect=digest), patch.object(runner, "save"):
        failed = False
        reason = ""
        try:
            runner.bench(config(model="test_model"), Path("unused"), "native_io_single_copy", fixture,
                         "pure_evidence_test", 3, all_snapshots)
        except (RuntimeError, KeyError) as error:
            failed = True
            reason = str(error)
    assert failed != accepted, reason


check_evidence(rows)
check_evidence(original + [evidence], False)
check_evidence(original, accepted=False)
check_evidence(rows[:-1], accepted=False)
check_evidence(rows, False, False)  # per-frame hashes forbidden in paired timing
for key, value in [("allocation_bytes", 1228801), ("copied_sha256", "wrong"), ("includes_warmups", False),
                   ("byte_match", False), ("timed_frame_input_hashes", True), ("policy", "reuse_prior_input")]:
    bad = copy.deepcopy(rows)
    next(x for x in bad if x.get("event") == "native_input_copy")[key] = value
    check_evidence(bad, accepted=False)
bad = copy.deepcopy(rows)
next(x for x in bad if x.get("event") == "native_input_copy_verification")["copied_sha256"] = "wrong"
check_evidence(bad, accepted=False)

with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
    base = Path(temporary)
    a, b = base / "positive_zero.f32", base / "negative_zero.f32"
    a.write_bytes(struct.pack("<ff", 0.0, 1.0))
    b.write_bytes(struct.pack("<ff", -0.0, 1.0))
    metrics = runner.float_metrics(a, b, 1e-6, 1e-6)
    assert metrics["within_epsilon"] and not metrics["bitwise_equal"]
    for i, (extra, accepted) in enumerate([
        ([], True),
        (["--candidates", "native_io_single_copy", "--dequant-scale", "fp16", "--timing-reference", "native_io"], True),
        (["--candidates", "native_io_single_copy"], False),
        (["--candidates", "native_io_single_copy", "--dequant-scale", "fp16", "--native-query", "11"], False),
        (["--candidates", "native_io", "--timing-reference", "native_io"], False),
    ]):
        parsed = []
        argv = ["run_target.py", "experiment", "--board-exclusive", "--lib", str(base / "unused_lib"),
                "--binary", str(base / "unused_binary"), "--out", str(base / f"unused_out{i}"), *extra]
        with patch.object(sys, "argv", argv), patch.object(runner, "verify", return_value={}), \
             patch.object(runner, "experiment", side_effect=lambda args, *_: parsed.append(args)), \
             contextlib.redirect_stderr(io.StringIO()):
            failed = False
            try:
                assert runner.main() == 0
            except SystemExit as error:
                assert error.code == 2
                failed = True
        assert failed != accepted
        if accepted and not extra:
            assert parsed[0].timing_reference == "baseline" and parsed[0].dequant_scale == "fp32"
            assert parsed[0].candidates == ["prealloc", "native", "native_io"]
print("runner_checks_passed=true; four_fixture_baseline_certification=true; native_reference_16_pairs_800_each=true; "
      "default_baseline_unchanged=true; bitwise_failure_and_input_hash_rejections=true; CLI_guards_passed=true; hardware_executed=false")
