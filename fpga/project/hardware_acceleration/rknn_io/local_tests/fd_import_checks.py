"""Local build and pure FD lifecycle/runner checks. Never loads RKNN or uses hardware."""
import argparse
from collections import Counter
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fd_import_runner", ROOT / "run_target.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
FD, CONTROL = runner.FD_CANDIDATE, runner.SINGLE_COPY
FIRST_BIND_ARCHIVE = ROOT.parent / "runs/rknn_experiment_49b3adc489d74eb596fc8b393e3ec23b/artifacts/results/native_io_fd_import_bright_baseline_cam1_cert_candidate.stdout"


def config(**overrides):
    values = dict(binary="unused_binary", lib="unused_lib", model="unused_model", candidates=[FD],
                  timing_reference=CONTROL, native_query=9, dequant_scale="fp16", fixtures=None,
                  rounds=4, iterations=50, warmup=5, timeout=120, atol=1e-6, rtol=1e-6)
    values.update(overrides)
    return argparse.Namespace(**values)


def orchestration(directory, fail=None):
    calls, comparisons, saved = [], [], {}
    binary = directory / "boundary_substitute"
    binary.write_bytes(b"nonexecutable; subprocess boundary substituted")
    (directory / "build_receipt.json").write_text(json.dumps(dict(executable_sha256="bound",
        prepared_manifest_sha256="bound", rknn_runtime_sha256="bound")))

    def bench(args, directory, mode, fixture=None, label="probe", iterations=None, all_snapshots=False):
        calls.append((mode, fixture["name"] if fixture else None, iterations or args.iterations, all_snapshots))
        rows = [dict(event="summary", completed_fps=1)]
        if mode == FD:
            rows.append(dict(event="native_input_copy", policy="one_memcpy_full_model_input_each_frame"))
        return dict(label=label, mode=mode, events=rows)

    def parity(reference, actual, args, full=False):
        comparisons.append((reference["mode"], actual["mode"], full))
        bad = (fail == "candidate_certificate" and full and actual["mode"] == FD or
               fail == "control_certificate" and full and actual["mode"] == CONTROL or
               fail == "measured_arrays" and not full)
        return dict(certified=True, all_float_arrays_bitwise_equal=not bad)

    args = config(binary=str(binary))
    with patch.object(runner, "target", return_value=dict(library_sha256="bound")), \
         patch.object(runner, "digest", return_value="bound"), patch.object(runner, "bench", side_effect=bench), \
         patch.object(runner, "parity", side_effect=parity), patch.object(runner, "stages", return_value={}), \
         patch.object(runner, "save", side_effect=lambda path, value: saved.__setitem__(Path(path).name, copy.deepcopy(value))), \
         contextlib.redirect_stdout(io.StringIO()):
        failed = False
        try:
            runner.experiment(args, dict(fixtures=[dict(name=f"mock{i}") for i in range(4)]), directory)
        except RuntimeError:
            failed = True
    assert failed == bool(fail)
    report = saved["report.json"]
    if fail:
        assert "failed_no_performance_claim" in report["status"]
        return
    assert len(report["certifications"]) == 4 and len(report["timing_reference_certifications"]) == 4
    assert all(reference == "baseline" for reference, _, full in comparisons if full)
    assert all(x["bitwise_arrays_required"] and x["certified"] for x in
               report["certifications"] + report["timing_reference_certifications"] + report["comparisons"])
    measured = [x for x in calls if x[1] is not None and not x[3]]
    assert Counter(x[0] for x in measured) == {FD: 16, CONTROL: 16}
    assert all(sum(x[2] for x in measured if x[0] == mode) == 800 for mode in (FD, CONTROL))
    for index, comparison in enumerate(report["comparisons"]):
        assert comparison["order"] == ([CONTROL, FD] if index % 2 == 0 else [FD, CONTROL])
    assert args.experiment_deadline > runner.time.monotonic()
    assert report["acceleration_scope"] == "native_npu_allocator_and_software_cpu_sync_copy"
    assert not report["fpga_acceleration_claim"]


def synthetic_evidence(iterations=3, warmup=5, certification=True):
    """Explicitly synthetic parser data; never saved as a hardware receipt."""
    roles = ["output0", "output1", "output2", "output3", "input_UINT8_NHWC_runtime_conversion"]
    memories = [dict(descriptor_hex=str(i + 100), virt_addr_hex=str(i + 1000), fd=i + 10, size=size,
                     offset=0, flags=2, phys_addr_hex="ffffffffffffffff" if i % 2 == 0 else format(0xffa80000 + i * 4096, "x"))
                for i, size in enumerate([8192, 28672, 8192, 28672, 1228800])]
    bound = copy.deepcopy(memories)
    for i, mem in enumerate(bound):
        mem["phys_addr_hex"] = format(0xffa80000 + i * 4096, "x")
    rows = [dict(event="runtime_library", sha256="synthetic_runtime"),
            dict(event="dma_heap_import_symbol", symbol="rknn_create_mem_from_fd", exact_sdk_signature=True,
                 address_hex="synthetic_address", provider_sha256="synthetic_runtime", runtime_sha256="synthetic_runtime", offset=0),
            dict(event="dma_heap_import_config", context_flags=0, persistent_imports=5, heap_path="/dev/dma_heap/system",
                 timing_reference=CONTROL, ownership_probe_passed=True, cpu_access_sessions_span_run=False,
                 flags_or_priv_data_modified=False, hardware_certified=False, page_size=4096)]
    for i in range(4):
        rows.append(dict(event="native_plan", query=9, dequant_scale="fp16", conversion_kernel="aarch64_neon_nc1hwc2_c2_8"))
    for index, (role, mem) in enumerate(zip(roles, memories)):
        rows.append(dict(event="memory", purpose=FD, role=role, metadata=mem, fd=mem["fd"], page_size=4096,
                         mapping_bytes=mem["size"], requested_size=25600 if index in (1, 3) else mem["size"],
                         allocator="dma_heap_system_fd_import", heap_path="/dev/dma_heap/system", map_shared=True,
                         flags_modified=False, st_ino=str(index + 1)))
        rows.append(dict(event="input_binding_result" if index == 4 else "output_binding", rc=0, output=index,
                         attributes_changed=False, memory_changed=mem != bound[index], before={}, after={}, memory_before=mem,
                         memory_after=bound[index], binding_device_address_resolved=index % 2 == 0,
                         binding_device_address_policy=runner.FD_BINDING_DEVICE_ADDRESS_POLICY))
    for phase in ("before_frames", "after_frames"):
        rows.append(dict(event="dma_heap_binding_snapshot", phase=phase, memories=copy.deepcopy([bound[4], *bound[:4]]),
                         input_binding={}, output_bindings=[{}] * 4, metadata_stable=True))

    def buffer(role, read, write):
        counts = {name: dict(attempts=count, success=count, failures=0, eintr=0, last_rc=0) for name, count in
                  (("start_read", read), ("end_read", read), ("start_write", write), ("end_write", write))}
        return dict(role=role, before_destroy_fd_identity=True, before_destroy_mapping=True,
                    after_import_destroy_fd_identity=True, after_import_destroy_mapping=True,
                    after_context_destroy_fd_identity=True, after_context_destroy_mapping=True,
                    before_destroy_inspected=True, after_import_destroy_inspected=True, after_context_destroy_inspected=True,
                    destroy_mem_attempted=True, destroy_mem_skipped=False, destroy_mem_rc=0,
                    munmap_attempted=True, munmap_skipped=False, munmap_rc=0, close_attempted=True, close_skipped=False, close_rc=0,
                    import_descriptor_retained=False, owned_buffer_retained=False, cpu_active=False, cpu_access=counts)

    for purpose in ("ownership_probe", FD):
        buffers = [buffer("unused_probe", 0, 1)] if purpose == "ownership_probe" else [
            buffer(role, 1 + (iterations if certification else 0), warmup + iterations + 1)
            if role.startswith("input") else buffer(role, warmup + iterations, 0) for role in roles]
        rows.append(dict(event="dma_heap_retirement", purpose=purpose, buffers=buffers, cleanup_ok=True,
                         retirement_branch="normal", process_teardown_only=False, release_boundary="explicit_retirement",
                         context_destroy_attempted=True, context_destroy_skipped=False, context_retained=False,
                         retained_context_hex="0", runtime_library_retained=False, fatal_no_continue=False,
                         context_destroy_rc=0, order="paired_cpu_end_then_imports_then_context_then_owned_munmap_close"))
    return rows


def parser_checks():
    rows = synthetic_evidence()
    runner.validate_fd_evidence(rows, 3, 5, True)
    runner.validate_fd_evidence(synthetic_evidence(50, 5, False), 50, 5, False)
    mutations = [
        ("dma_heap_import_symbol", "provider_sha256", "wrong"),
        ("dma_heap_import_config", "flags_or_priv_data_modified", True),
        ("dma_heap_import_config", "cpu_access_sessions_span_run", True),
        ("native_plan", "conversion_kernel", "scalar_reference"),
        ("memory", "mapping_bytes", 123),
        ("output_binding", "memory_changed", False),
        ("output_binding", "binding_device_address_resolved", False),
        ("input_binding_result", "binding_device_address_policy", "allow_any_address_change"),
        ("input_binding_result", "attributes_changed", True),
        ("dma_heap_binding_snapshot", "memories", []),
        ("dma_heap_retirement", "cleanup_ok", False),
    ]
    for event, key, value in mutations:
        bad = copy.deepcopy(rows)
        next(x for x in bad if x["event"] == event)[key] = value
        rejected = False
        try: runner.validate_fd_evidence(bad, 3, 5, True)
        except (RuntimeError, KeyError): rejected = True
        assert rejected, (event, key)
    for key, value in (("after_import_destroy_fd_identity", False), ("after_context_destroy_mapping", False),
                       ("cpu_active", True), ("destroy_mem_rc", -1)):
        bad = copy.deepcopy(rows)
        next(x for x in bad if x["event"] == "dma_heap_retirement")["buffers"][0][key] = value
        try: runner.validate_fd_evidence(bad, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError(key)
    for key in ("attempts", "success", "failures", "last_rc"):
        bad = copy.deepcopy(rows)
        next(x for x in bad if x["event"] == "dma_heap_retirement")["buffers"][0]["cpu_access"]["end_write"][key] += 1
        try: runner.validate_fd_evidence(bad, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError(key)
    assert not runner.require_bitwise(dict(certified=True, all_float_arrays_bitwise_equal=False), True)["certified"]


def first_binding_checks():
    original = next(row for row in runner.events(FIRST_BIND_ARCHIVE) if row["event"] == "output_binding")
    assert original["rc"] == 0 and original["memory_changed"] and not original["attributes_changed"]
    assert original["memory_before"]["phys_addr_hex"] == "ffffffffffffffff"
    assert original["memory_after"]["phys_addr_hex"] == "ffa80000"
    assert runner.validate_fd_binding(original["before"], original["after"], original["memory_before"], original["memory_after"])
    annotated = copy.deepcopy(original)
    annotated.update(binding_device_address_resolved=True, binding_device_address_policy=runner.FD_BINDING_DEVICE_ADDRESS_POLICY)
    assert runner.validate_fd_binding_event(annotated)

    def rejected(row):
        try: runner.validate_fd_binding_event(row)
        except (RuntimeError, KeyError): return
        raise AssertionError("unknown binding mutation accepted")

    for key in original["before"]:
        bad = copy.deepcopy(annotated); del bad["after"][key]; rejected(bad)
    for key in original["memory_before"]:
        if key == "phys_addr_hex": continue
        bad = copy.deepcopy(annotated); bad["memory_after"][key] = "mutated"; rejected(bad)
    for key, value in (("rc", -1), ("attributes_changed", True), ("memory_changed", False),
                       ("binding_device_address_resolved", False), ("binding_device_address_policy", "anything")):
        bad = copy.deepcopy(annotated); bad[key] = value; rejected(bad)
    for before, after in (("0", "ffa80000"), ("ffffffffffffffff", "0"), ("ffa80000", "ffa90000"),
                          ("ffa80000", "ffffffffffffffff"), ("ffffffffffffffff", "10000000000000000"),
                          ("ffffffffffffffff", "FFA80000"), ("ffffffffffffffff", "00")):
        bad = copy.deepcopy(annotated)
        bad["memory_before"]["phys_addr_hex"] = before; bad["memory_after"]["phys_addr_hex"] = after
        rejected(bad)
    for address in ("0", "ffa80000", "ffffffffffffffff"):
        good = copy.deepcopy(annotated)
        good["memory_before"]["phys_addr_hex"] = good["memory_after"]["phys_addr_hex"] = address
        good.update(memory_changed=False, binding_device_address_resolved=False)
        assert not runner.validate_fd_binding_event(good)
    # Full success-shaped evidence tests all four output and input setup bindings;
    # a second address change after setup still fails the strict frame snapshots.
    for index in range(5):
        rows = synthetic_evidence()
        binding = [x for x in rows if x["event"] in ("output_binding", "input_binding_result")][index]
        binding["memory_after"]["fd"] += 1
        try: runner.validate_fd_evidence(rows, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError("FD mutation accepted for setup binding " + str(index))
    for phase in ("before_frames", "after_frames"):
        rows = synthetic_evidence()
        snapshot = next(x for x in rows if x.get("phase") == phase)
        snapshot["memories"][0]["phys_addr_hex"] = "ffa99999"
        try: runner.validate_fd_evidence(rows, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError("postbinding address mutation accepted")


def retirement_proof_checks(directory):
    rows = synthetic_evidence()
    for field, value in (("retirement_branch", "uncertain_run_process_teardown"), ("process_teardown_only", True),
                         ("runtime_library_retained", True), ("context_retained", True), ("fatal_no_continue", True),
                         ("release_boundary", "process_teardown"), ("context_destroy_attempted", False),
                         ("context_destroy_skipped", True), ("context_destroy_rc", None), ("retained_context_hex", "7b")):
        bad = copy.deepcopy(rows)
        next(x for x in bad if x["event"] == "dma_heap_retirement")[field] = value
        try: runner.validate_fd_evidence(bad, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError("invalid retirement proof accepted: " + field)
    for field, value in (("destroy_mem_attempted", False), ("destroy_mem_skipped", True), ("destroy_mem_rc", None),
                         ("munmap_attempted", False), ("close_attempted", False), ("before_destroy_inspected", False),
                         ("import_descriptor_retained", True), ("owned_buffer_retained", True)):
        bad = copy.deepcopy(rows)
        next(x for x in bad if x["event"] == "dma_heap_retirement")["buffers"][0][field] = value
        try: runner.validate_fd_evidence(bad, 3, 5, True)
        except RuntimeError: pass
        else: raise AssertionError("skipped cleanup accepted: " + field)
    # Exercise the real bench receipt boundary on all process RCs, before its
    # unsupported shortcut or success/provenance checks can permit continuation.
    for branch in ("uncertain_run_process_teardown", "context_destroy_failed_process_teardown"):
        fatal_rows = [dict(event="dma_heap_retirement", retirement_branch=branch, process_teardown_only=True,
                           cleanup_ok=False, runtime_library_retained=True, fatal_no_continue=True)]
        for rc in (0, 2, 3):
            with patch.object(runner, "invoke", return_value=dict(returncode=rc)) as invoked, \
                 patch.object(runner, "events", return_value=fatal_rows), patch.object(runner, "save"), \
                 patch.object(runner, "hardware_snapshot", return_value={}), patch.object(runner, "dependency_hashes", return_value={}):
                try: runner.bench(config(), directory, FD)
                except RuntimeError as error: assert "fatal, stop experiment" in str(error)
                else: raise AssertionError("deferred retirement escaped fatal bench gate")
                assert invoked.call_count == 1


def cli_checks(directory):
    base = ["run_target.py", "experiment", "--board-exclusive", "--lib", str(directory / "unused_lib"),
            "--binary", str(directory / "unused_binary")]
    valid = ["--candidates", FD, "--timing-reference", CONTROL, "--native-query", "9", "--dequant-scale", "fp16"]
    cases = [(valid, True), ([], True), (valid + ["--native-query", "11"], False),
             (valid + ["--dequant-scale", "fp32"], False), (valid + ["--timing-reference", "baseline"], False),
             (valid + ["--fixtures", "one"], False), (valid + ["--rounds", "1"], False),
             (valid + ["--iterations", "1"], False), (valid + ["--warmup", "0"], False)]
    for index, (extra, accepted) in enumerate(cases):
        seen = []
        with patch.object(sys, "argv", base + ["--out", str(directory / f"parse_{index}")] + extra), \
             patch.object(runner, "verify", return_value={}), patch.object(runner, "experiment", side_effect=lambda args, *_: seen.append(args)), \
             contextlib.redirect_stderr(io.StringIO()):
            failed = False
            try: assert runner.main() == 0
            except SystemExit as error:
                assert error.code == 2
                failed = True
        assert failed != accepted
        if accepted and not extra:
            assert seen[0].candidates == ["prealloc", "native", "native_io"] and seen[0].dequant_scale == "fp32"


def run(argv, directory, name, expected=0):
    process = subprocess.run([str(x) for x in argv], cwd=ROOT, capture_output=True, check=False, timeout=60)
    (directory / (name + ".stdout")).write_bytes(process.stdout)
    (directory / (name + ".stderr")).write_bytes(process.stderr)
    assert process.returncode == expected, (name, process.returncode, process.stderr.decode(errors="replace"))
    return dict(name=name, argv=[str(x) for x in argv], returncode=process.returncode, expected_returncode=expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="New local validation directory")
    parser.add_argument("--binding-only", action="store_true", help="First-binding policy change: skip unchanged lifecycle/sanitizer builds")
    args = parser.parse_args()
    directory = args.out.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    protected = [ROOT / "native_adapter.h", ROOT / "single_copy_input.h", ROOT / "prepare.py",
                 ROOT.parent / "run_rknn.py", *sorted((ROOT / "prepared").rglob("*"))]
    if args.binding_only:
        protected += [ROOT / "dma_heap_import.h", ROOT / "dma_heap_import_selftest.cpp"]
    before = {str(p): runner.digest(p) for p in protected if p.is_file()}
    compile((ROOT / "run_target.py").read_text(), str(ROOT / "run_target.py"), "exec")
    parser_checks()
    first_binding_checks()
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        temporary = Path(temporary)
        for fail in (None, "candidate_certificate", "control_certificate", "measured_arrays"):
            orchestration(temporary, fail)
        cli_checks(temporary)
        retirement_proof_checks(temporary)
        a, b = temporary / "a.f32", temporary / "b.f32"
        a.write_bytes(struct.pack("<ff", 0.0, 1.0)); b.write_bytes(struct.pack("<ff", -0.0, 1.0))
        metrics = runner.float_metrics(a, b, 1e-6, 1e-6)
        assert metrics["within_epsilon"] and not metrics["bitwise_equal"]
        b.write_bytes(struct.pack("<ff", float("nan"), 1.0))
        try: runner.float_metrics(a, b, 1e-6, 1e-6)
        except RuntimeError: pass
        else: raise AssertionError("nonfinite snapshot accepted")
    commands = []
    lifecycle_builds = [] if args.binding_only else [("lifecycle", ["-O2"]),
        ("lifecycle_sanitized", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"])]
    for name, flags in lifecycle_builds:
        binary = directory / name
        commands.append(run(["g++", "-std=c++17", "-Wall", "-Wextra", "-pedantic", *flags,
                             "dma_heap_import_selftest.cpp", "-o", binary], directory, name + "_build"))
        commands.append(run([binary], directory, name))
    qt = subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt5Core", "Qt5Gui"], text=True).split()
    retirement_test_source = ROOT / "validation/fd_retirement_src/retirement_event_selftest.cpp"
    retirement_test = directory / "retirement_event_selftest"
    commands.append(run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic", "-fPIC", "-Iprepared",
                         retirement_test_source, "-o", retirement_test, *qt, "-ldl"], directory, "retirement_event_build"))
    commands.append(run([retirement_test], directory, "retirement_event"))
    retirement_rows = runner.events(directory / "retirement_event.stdout")
    assert len(retirement_rows) == 4
    for row in retirement_rows:
        if row["purpose"] == "mock_success":
            runner.refuse_process_teardown_retirement([row])
        else:
            try: runner.refuse_process_teardown_retirement([row])
            except RuntimeError: pass
            else: raise AssertionError("actual mocked deferred report accepted")
    binding_test = directory / "fd_binding_selftest"
    commands.append(run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic", "-fPIC",
                         "fd_binding_selftest.cpp", "-o", binding_test, *qt], directory, "binding_policy_build"))
    commands.append(run([binding_test, FIRST_BIND_ARCHIVE], directory, "binding_policy"))
    bench = directory / "rknn_io_bench_host"
    commands.append(run(["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-pedantic", "-fPIC", "-Iprepared",
                         "bench.cpp", "-o", bench, *qt, "-ldl"], directory, "benchmark_build"))
    commands.append(run([bench, "--mode", FD, "--diagnose-native"], directory, "diagnostic_decline", 3))
    declined = runner.events(directory / "diagnostic_decline.stdout")
    assert runner.only(declined, "unsupported")["mode"] == FD and not any(x["event"] in ("identity", "runtime_library") for x in declined)
    for name, flags in (("missing_control", ["--dequant-scale", "fp16"]),
                        ("wrong_query", ["--native-query", "11", "--dequant-scale", "fp16", "--timing-reference", CONTROL]),
                        ("wrong_scale", ["--dequant-scale", "fp32", "--timing-reference", CONTROL])):
        commands.append(run([bench, "--mode", FD, *flags], directory, name, 3))
        rows = runner.events(directory / (name + ".stdout"))
        assert "requires native-query9" in runner.only(rows, "unsupported")["reason"]
        assert not any(x["event"] in ("identity", "runtime_library") for x in rows)
    commands.append(run([sys.executable, ROOT / "validation/single_copy_01/runner_checks.py"], directory, "legacy_runner_regression"))
    assert before == {path: runner.digest(path) for path in before}, "protected files changed during local checks"
    sources = [ROOT / "bench.cpp", ROOT / "run_target.py", ROOT / "dma_heap_import.h", ROOT / "dma_heap_import_selftest.cpp",
               ROOT / "fd_binding_policy.h", ROOT / "fd_binding_selftest.cpp", Path(__file__), ROOT / "README.md", retirement_test_source]
    receipt = dict(status="local_fd_first_binding_policy_checks_passed_pending_parent_freeze" if args.binding_only else
                   "local_fd_lifecycle_build_runner_checks_passed_pending_parent_freeze", hardware_executed=False,
                   hardware_compatibility_claim=False, hardware_certified=False, performance_claim=False, ssh_used=False,
                   scope="native_npu_allocator_and_software_cpu_sync_copy", protected_sha256=before,
                   source_sha256={str(p.relative_to(ROOT)): runner.digest(p) for p in sources},
                   lifecycle_optimized_passed=True if lifecycle_builds else None,
                   lifecycle_asan_ubsan_passed=True if lifecycle_builds else None, benchmark_compile_passed=True,
                   binding_only=args.binding_only, first_binding_policy_selftest_passed=True,
                   deferred_retirement_proof_gates_passed=True, actual_mocked_retirement_event_fields_passed=True,
                   uncertain_run_zero_release_and_deferred_runtime_unload_passed=True if lifecycle_builds else None,
                   first_binding_archive_sha256=runner.digest(FIRST_BIND_ARCHIVE),
                   strict_candidate_and_control_baseline_certificate_rejections_passed=True,
                   measured_bitwise_rejection_passed=True, four_fixtures_16_pairs_800_each_orchestration_passed=True,
                   ownership_and_sync_evidence_rejections_passed=True, cli_guards_passed=True,
                   legacy_runner_regression_passed=True, commands=commands,
                   log_sha256={p.name: runner.digest(p) for p in directory.iterdir() if p.suffix in (".stdout", ".stderr")},
                   parent_next=dict(freeze_required=True, fresh_private_target_build_required=True, candidates=[FD],
                                    timing_reference=CONTROL, native_query=9, dequant_scale="fp16", entire_timeout_seconds=1600))
    runner.save(directory / "receipt.json", receipt)
    print(json.dumps(dict(status=receipt["status"], receipt=str(directory / "receipt.json"), hardware_executed=False)))


if __name__ == "__main__":
    main()
