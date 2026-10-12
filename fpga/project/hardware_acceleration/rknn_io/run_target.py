"""Parent-invoked target preparation/probe/paired RKNN experiment. No SSH."""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
FD_CANDIDATE = "native_io_fd_import"
SINGLE_COPY = "native_io_single_copy"
FD_BINDING_DEVICE_ADDRESS_POLICY = "fixed_after_first_binding"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verify():
    manifest = json.loads((ROOT / "prepared/manifest.json").read_text(encoding="utf-8"))
    for rel, expected in manifest["files_sha256"].items():
        if digest(ROOT / rel) != expected:
            raise RuntimeError("prepared file SHA mismatch: " + rel)
    return manifest


def invoke(argv, directory, name, timeout=120):
    argv = [str(x) for x in argv]
    stamp = time.monotonic()
    with (directory / (name + ".stdout")).open("wb") as out, (directory / (name + ".stderr")).open("wb") as err:
        try:
            process = subprocess.run(argv, cwd=directory, stdout=out, stderr=err, timeout=timeout, check=False)
            rc = process.returncode
        except subprocess.TimeoutExpired:
            rc = 124
    receipt = dict(argv=argv, cwd=str(directory), returncode=rc, elapsed_seconds=time.monotonic() - stamp,
                   stdout_sha256=digest(directory / (name + ".stdout")),
                   stderr_sha256=digest(directory / (name + ".stderr")))
    save(directory / (name + ".command.json"), receipt)
    return receipt


def events(path):
    result = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        # Vendor runtime may log non-JSON to stdout. Preserve it in the raw log.
        if line.startswith("{"):
            row = json.loads(line)
            if row.get("event") == "completion":
                # Every decoder tuple field is FP32. Recover those exact bits
                # across Qt versions with different double JSON formatting.
                row["detections"] = [{k: v if k == "class" else struct.unpack("<f", struct.pack("<f", v))[0]
                                      for k, v in d.items()} for d in row["detections"]]
            result.append(row)
    return result


def only(rows, event):
    found = [x for x in rows if x.get("event") == event]
    if len(found) != 1:
        raise RuntimeError("expected one " + event + ", got " + str(len(found)))
    return found[0]


def dependency_hashes(path):
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        columns = line.split(maxsplit=5)
        if len(columns) == 6 and columns[5].startswith("/"):
            name = columns[5]
            if name.endswith(" (deleted)"):
                name = name[:-10]
            file = Path(name)
            if file.is_file() and str(file) not in result:
                result[str(file)] = digest(file)
    return result


def hardware_snapshot():
    result = {"monotonic_seconds": time.monotonic()}
    files = [Path("/proc/loadavg")]
    for root, names in (("/sys/class/devfreq", ("cur_freq", "min_freq", "max_freq", "governor")),
                        ("/sys/class/thermal", ("type", "temp")),
                        ("/sys/devices/system/cpu", ("cpufreq/scaling_cur_freq", "cpufreq/scaling_governor"))):
        for name in names:
            files.extend(Path(root).glob("*/" + name))
    for file in files:
        try:
            result[str(file)] = file.read_text(encoding="utf-8").strip()
        except OSError as e:
            result[str(file)] = str(e)
    return result


def target(args, manifest, directory):
    info = dict(platform=platform.platform(), machine=platform.machine(), python=sys.version,
                python_executable=str(Path(sys.executable).resolve()), python_executable_sha256=digest(sys.executable),
                prepared_manifest_sha256=digest(ROOT / "prepared/manifest.json"),
                library_path=str(Path(args.lib).resolve()), library_sha256=digest(args.lib),
                model_path=args.model, model_sha256=digest(args.model),
                pending_runtime_abi="Compiled probe queries actual runtime version and every tensor field.")
    if info["model_sha256"] != manifest["model_sha256"]:
        raise RuntimeError("target model SHA mismatch")
    for file in ("/proc/version", "/proc/device-tree/model", "/sys/kernel/debug/rknpu/version"):
        try:
            info[file] = Path(file).read_bytes().decode("utf-8", errors="replace").strip("\x00\n")
        except OSError as e:
            info[file] = str(e)
    for tool, query in (("g++", ["--version"]), ("qmake", ["-v"]), ("make", ["--version"])):
        resolved = shutil.which(tool)
        if resolved:
            info[tool] = dict(path=str(Path(resolved).resolve()), sha256=digest(Path(resolved).resolve()))
            receipt = invoke([resolved] + query, directory, "tool_" + tool.replace("+", "p"))
            info[tool]["query"] = receipt
    if shutil.which("g++"):
        cc = invoke(["g++", "-print-prog-name=cc1plus"], directory, "cc1plus_path")
        if cc["returncode"] == 0:
            cc_path = Path((directory / "cc1plus_path.stdout").read_text(encoding="utf-8").strip())
            if cc_path.is_file():
                info["cc1plus"] = dict(path=str(cc_path.resolve()), sha256=digest(cc_path))
    save(directory / "target.json", info)
    print(json.dumps({"event": "target", **info}), flush=True)
    return info


def build(args, manifest, directory):
    target(args, manifest, directory)
    for command, name in ((["qmake", ROOT / "rknn_io.pro"], "qmake"), (["make", "-j2"], "make")):
        rc = invoke(command, directory, name, timeout=300)
        if rc["returncode"]:
            raise RuntimeError(name + " failed; read retained stdout/stderr")
    binary = directory / "rknn_io_bench"
    deps = {}
    for dependency in sorted(directory.glob("*.d")):
        content = dependency.read_text(encoding="utf-8", errors="replace").replace("\\\n", " ")
        for word in content.split()[1:]:
            file = Path(word) if word.startswith("/") else directory / word
            if file.is_file():
                deps[str(file.resolve())] = digest(file)
    if not deps or not any(p.endswith("/rknn_api.h") for p in deps):
        raise RuntimeError("compiler dependency files do not bind retained RKNN SDK header")
    ldd = invoke(["ldd", binary], directory, "ldd")
    libraries = {}
    for line in (directory / "ldd.stdout").read_text(encoding="utf-8").splitlines():
        for word in line.split():
            if word.startswith("/") and Path(word).is_file():
                libraries[str(Path(word).resolve())] = digest(Path(word).resolve())
    receipt = dict(status="target_build_only_no_performance_claim", binary=str(binary),
                   executable_sha256=digest(binary), prepared_manifest_sha256=digest(ROOT / "prepared/manifest.json"),
                   makefile_sha256=digest(directory / "Makefile"),
                   object_sha256={p.name: digest(p) for p in directory.glob("*.o")},
                   compiler_dependency_sha256=deps, linked_library_sha256=libraries, ldd=ldd,
                   rknn_runtime_sha256=digest(args.lib))
    save(directory / "build_receipt.json", receipt)
    print(json.dumps({"event": "build", **receipt}), flush=True)


def bench(args, directory, mode, fixture=None, label="probe", iterations=None, all_snapshots=False):
    prefix = directory / label
    command = [args.binary, "--mode", mode, "--lib", args.lib, "--model", args.model,
               "--manifest", ROOT / "prepared/manifest.json", "--native-query", str(args.native_query),
               "--dequant-scale", args.dequant_scale]
    if mode == FD_CANDIDATE:
        command += ["--timing-reference", args.timing_reference]
    if fixture:
        command += ["--fixture", ROOT / "prepared" / fixture["path"], "--kind", fixture["kind"],
                    "--prefix", prefix, "--warmup", str(args.warmup),
                    "--iterations", str(iterations or args.iterations)]
        if all_snapshots:
            command += ["--snapshot-all"]
    before = hardware_snapshot()
    timeout = args.timeout
    deadline = getattr(args, "experiment_deadline", None)
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("FD candidate experiment exceeded 1600-second budget")
        timeout = min(timeout, remaining)
    receipt = invoke(command, directory, label, timeout=timeout)
    after = hardware_snapshot()
    rows = events(directory / (label + ".stdout"))
    result = dict(label=label, mode=mode, fixture=fixture["name"] if fixture else None,
                  command=receipt, events=rows,
                  hardware_before=before, hardware_after=after,
                  loaded_dependency_sha256=dependency_hashes(Path(str(prefix) + ".maps")))
    save(directory / (label + ".receipt.json"), result)
    refuse_process_teardown_retirement(rows)
    if receipt["returncode"] == 3:
        reasons = [x.get("reason") for x in rows if x.get("event") == "unsupported"]
        result["unsupported"] = reasons
        save(directory / (label + ".receipt.json"), result)
        print(json.dumps({"event": "unsupported", "label": label, "reasons": reasons}), flush=True)
        return result
    if receipt["returncode"] != 0:
        raise RuntimeError(label + " failed rc=" + str(receipt["returncode"]) + "; retained raw logs")
    only(rows, "version")
    only(rows, "summary")
    if only(rows, "runtime_library")["sha256"] != digest(args.lib):
        raise RuntimeError("resolved runtime library differs from requested target library")
    if only(rows, "identity")["executable_sha256"] != digest(args.binary):
        raise RuntimeError("executed binary identity differs from requested executable")
    if fixture:
        if only(rows, "fixture")["source_sha256"] != fixture["sha256"]:
            raise RuntimeError("fixture changed on target")
        historical = fixture.get("historical_reference")
        if historical:
            if only(rows, "io_count")["n_output"] != historical["output_count"]:
                raise RuntimeError("actual queried output count differs from retained target fixture result")
            for frame in [x for x in rows if x.get("event") == "completion"]:
                if frame["count"] != historical["count"] or frame["detections"] != historical["detections"]:
                    raise RuntimeError(label + " differs from historical target detections; raw log retained")
        summary = only(rows, "summary")
        expected = iterations or args.iterations
        if (summary["requested"] != expected or summary["completed"] != expected or
            summary["warmed"] != args.warmup or summary["attempted"] != expected + args.warmup or
            summary["failed"] != 0 or summary["window"]["wall_ms"] <= 0):
            raise RuntimeError("hardware completion accounting or timing is incomplete")
        if mode in (SINGLE_COPY, FD_CANDIDATE):
            copy = only(rows, "native_input_copy")
            input_sha = only(rows, "fixture")["input_sha256"]
            if (copy["mode"] != mode or copy["policy"] != "one_memcpy_full_model_input_each_frame" or
                copy["source_bytes"] != 1228800 or copy["allocation_bytes"] != 1228800 or copy["input_row_bytes"] != 1920 or
                copy["per_frame_input_bytes_written"] != 1228800 or not copy["includes_warmups"] or
                not copy["byte_match"] or copy["source_sha256"] != input_sha or copy["copied_sha256"] != input_sha or
                copy["hash_scope"] != "setup_preflight_before_warmups_and_timing" or copy["timed_frame_input_hashes"]):
                raise RuntimeError("single-copy policy or preflight input evidence differs")
            checks = [x for x in rows if x.get("event") == "native_input_copy_verification"]
            expected_completions = list(range(1, expected + 1)) if all_snapshots else []
            if [x["completion"] for x in checks] != expected_completions or any(
                not x["byte_match"] or not x["checked_before_sync_and_run"] or not x["certification_only"] or
                x["source_sha256"] != input_sha or x["copied_sha256"] != input_sha for x in checks
            ):
                raise RuntimeError("single-copy certification input hashes missing/different or present in timed frames")
        if mode == FD_CANDIDATE:
            validate_fd_evidence(rows, expected, args.warmup, all_snapshots)
    return result


def validate_fd_binding(before_attr, after_attr, before_memory, after_memory):
    """Pure first-binding policy; device address metadata is never used as a physical pointer."""
    if before_attr != after_attr:
        raise RuntimeError("FD binding attributes changed")
    required = {"descriptor_hex", "virt_addr_hex", "phys_addr_hex", "fd", "offset", "size", "flags"}
    if not required <= before_memory.keys() or not required <= after_memory.keys():
        raise RuntimeError("FD binding descriptor field missing")
    addresses = []
    for memory in (before_memory, after_memory):
        value = memory["phys_addr_hex"]
        if (not isinstance(value, str) or not 1 <= len(value) <= 16 or
            any(c not in "0123456789abcdef" for c in value)):
            raise RuntimeError("FD binding device address is not canonical uint64 hex")
        address = int(value, 16)
        if format(address, "x") != value:
            raise RuntimeError("FD binding device address is not canonical uint64 hex")
        addresses.append(address)
    fixed = lambda memory: {k: v for k, v in memory.items() if k != "phys_addr_hex"}
    if fixed(before_memory) != fixed(after_memory):
        raise RuntimeError("FD binding non-address descriptor field changed")
    before, after = addresses
    if before == after:
        return False
    if before == 0xffffffffffffffff and 0 < after < 0xffffffffffffffff:
        return True
    raise RuntimeError("FD binding unexpected device address transition")


def validate_fd_binding_event(binding):
    if binding["rc"] != 0:
        raise RuntimeError("FD binding failed")
    resolved = validate_fd_binding(binding["before"], binding["after"], binding["memory_before"], binding["memory_after"])
    if (binding["attributes_changed"] is not False or
        binding["memory_changed"] is not (binding["memory_before"] != binding["memory_after"]) or
        binding["binding_device_address_resolved"] is not resolved or
        binding["binding_device_address_policy"] != FD_BINDING_DEVICE_ADDRESS_POLICY or
        "binding_policy_error" in binding):
        raise RuntimeError("FD binding policy/resolution/change evidence differs")
    return resolved


def refuse_process_teardown_retirement(rows):
    for row in rows:
        if row.get("event") != "dma_heap_retirement":
            continue
        if (row.get("process_teardown_only") or row.get("runtime_library_retained") or row.get("context_retained") or
            row.get("fatal_no_continue") or row.get("release_boundary") == "process_teardown" or
            row.get("retirement_branch") in ("uncertain_run_process_teardown", "context_destroy_failed_process_teardown")):
            raise RuntimeError("FD retirement deferred to process teardown; fatal, stop experiment without certification or timing")


def validate_fd_evidence(rows, iterations, warmup, all_snapshots):
    refuse_process_teardown_retirement(rows)
    symbol = only(rows, "dma_heap_import_symbol")
    runtime = only(rows, "runtime_library")["sha256"]
    config = only(rows, "dma_heap_import_config")
    if (symbol["symbol"] != "rknn_create_mem_from_fd" or not symbol["exact_sdk_signature"] or
        not symbol["address_hex"] or symbol["provider_sha256"] != runtime or symbol["runtime_sha256"] != runtime or
        symbol["offset"] != 0 or config["context_flags"] != 0 or config["persistent_imports"] != 5 or
        config["heap_path"] != "/dev/dma_heap/system" or config["timing_reference"] != SINGLE_COPY or
        not config["ownership_probe_passed"] or config["cpu_access_sessions_span_run"] or
        config["flags_or_priv_data_modified"] or config["hardware_certified"]):
        raise RuntimeError("FD import symbol/config evidence differs")
    plans = [x for x in rows if x.get("event") == "native_plan"]
    if len(plans) != 4 or any(x["query"] != 9 or x["dequant_scale"] != "fp16" or
                            x["conversion_kernel"] != "aarch64_neon_nc1hwc2_c2_8" for x in plans):
        raise RuntimeError("FD candidate changed query9 FP16-scale NEON output plans")
    allocations = [x for x in rows if x.get("event") == "memory" and x.get("purpose") == FD_CANDIDATE]
    roles = {"output0", "output1", "output2", "output3", "input_UINT8_NHWC_runtime_conversion"}
    if len(allocations) != 5 or {x["role"] for x in allocations} != roles:
        raise RuntimeError("five dedicated FD import allocations missing")
    descriptors, fds = set(), set()
    for alloc in allocations:
        page, size, requested = alloc["page_size"], alloc["mapping_bytes"], alloc["requested_size"]
        mem = alloc["metadata"]
        if (page != config["page_size"] or page <= 0 or size != ((requested + page - 1) // page) * page or
            size > 0xffffffff or mem["size"] < requested or mem["size"] > size or
            alloc["fd"] < 0 or mem["fd"] != alloc["fd"] or mem["offset"] != 0 or
            alloc["allocator"] != "dma_heap_system_fd_import" or alloc["heap_path"] != "/dev/dma_heap/system" or
            not alloc["map_shared"] or alloc["flags_modified"] or not alloc["st_ino"]):
            raise RuntimeError("FD allocation alignment/identity/size evidence differs")
        descriptors.add(mem["descriptor_hex"])
        fds.add(alloc["fd"])
    if len(descriptors) != 5 or len(fds) != 5:
        raise RuntimeError("FD candidate reused a persistent descriptor/FD")
    for event in ("output_binding", "input_binding_result"):
        bindings = [x for x in rows if x.get("event") == event]
        if len(bindings) != (4 if event == "output_binding" else 1):
            raise RuntimeError("FD binding coverage differs")
        for binding in bindings:
            validate_fd_binding_event(binding)
    snapshots = [x for x in rows if x.get("event") == "dma_heap_binding_snapshot"]
    if (len(snapshots) != 2 or [x["phase"] for x in snapshots] != ["before_frames", "after_frames"] or
        snapshots[0]["memories"] != snapshots[1]["memories"] or
        snapshots[0]["input_binding"] != snapshots[1]["input_binding"] or
        snapshots[0]["output_bindings"] != snapshots[1]["output_bindings"] or
        len(snapshots[0]["memories"]) != 5 or len(snapshots[0]["output_bindings"]) != 4 or not snapshots[1]["metadata_stable"]):
        raise RuntimeError("FD metadata snapshots missing/unstable")
    outputs = [x for x in rows if x.get("event") == "output_binding"]
    input_binding = only(rows, "input_binding_result")
    if {x["output"] for x in outputs} != {0, 1, 2, 3}:
        raise RuntimeError("FD output binding index coverage differs")
    outputs.sort(key=lambda binding: binding["output"])
    bound_memories = [input_binding["memory_after"], *[x["memory_after"] for x in outputs]]
    if (snapshots[0]["memories"] != bound_memories or snapshots[0]["input_binding"] != input_binding["after"] or
        snapshots[0]["output_bindings"] != [x["after"] for x in outputs]):
        raise RuntimeError("FD frame metadata snapshots differ from first binding")
    allocation_by_role = {x["role"]: x for x in allocations}
    for role, binding in [("input_UINT8_NHWC_runtime_conversion", input_binding),
                          *[("output" + str(x["output"]), x) for x in outputs]]:
        if binding["memory_before"] != allocation_by_role[role]["metadata"]:
            raise RuntimeError("FD first binding descriptor differs from imported allocation")
    retirements = [x for x in rows if x.get("event") == "dma_heap_retirement"]
    if len(retirements) != 2 or {x["purpose"] for x in retirements} != {"ownership_probe", FD_CANDIDATE}:
        raise RuntimeError("FD probe/retirement evidence missing")
    for retirement in retirements:
        if (not retirement["cleanup_ok"] or retirement["context_destroy_rc"] != 0 or
            retirement["retirement_branch"] != "normal" or retirement["process_teardown_only"] is not False or
            retirement["release_boundary"] != "explicit_retirement" or retirement["context_destroy_attempted"] is not True or
            retirement["context_destroy_skipped"] is not False or retirement["context_retained"] is not False or
            retirement["retained_context_hex"] != "0" or retirement["runtime_library_retained"] is not False or
            retirement["fatal_no_continue"] is not False or
            retirement["order"] != "paired_cpu_end_then_imports_then_context_then_owned_munmap_close"):
            raise RuntimeError("FD import teardown failed")
        expected_roles = {"unused_probe"} if retirement["purpose"] == "ownership_probe" else roles
        if len(retirement["buffers"]) != len(expected_roles) or {x["role"] for x in retirement["buffers"]} != expected_roles:
            raise RuntimeError("FD teardown buffer coverage differs")
        for buffer in retirement["buffers"]:
            if (not all(buffer[x] for x in ("before_destroy_fd_identity", "before_destroy_mapping",
                    "after_import_destroy_fd_identity", "after_import_destroy_mapping",
                    "after_context_destroy_fd_identity", "after_context_destroy_mapping",
                    "before_destroy_inspected", "after_import_destroy_inspected", "after_context_destroy_inspected")) or
                any(buffer[x] != 0 for x in ("destroy_mem_rc", "munmap_rc", "close_rc")) or buffer["cpu_active"] or
                any(buffer[x] is not True for x in ("destroy_mem_attempted", "munmap_attempted", "close_attempted")) or
                any(buffer[x] is not False for x in ("destroy_mem_skipped", "munmap_skipped", "close_skipped",
                                                   "import_descriptor_retained", "owned_buffer_retained"))):
                raise RuntimeError("runtime removed owned FD/mapping or failed teardown")
            read = write = 0
            if retirement["purpose"] == "ownership_probe":
                write = 1
            elif buffer["role"].startswith("input"):
                write = warmup + iterations + 1
                read = 1 + (iterations if all_snapshots else 0)
            else:
                read = warmup + iterations
            if set(buffer["cpu_access"]) != {"start_read", "end_read", "start_write", "end_write"}:
                raise RuntimeError("FD CPU access counter coverage missing")
            for name, count in buffer["cpu_access"].items():
                expected = write if name.endswith("write") else read
                if (count["success"] != expected or count["failures"] != 0 or count["last_rc"] != 0 or
                    count["attempts"] != expected + count["eintr"]):
                    raise RuntimeError("FD CPU access attempt/success/failure accounting differs")


def require_bitwise(certificate, required):
    certificate["bitwise_arrays_required"] = required
    if required:
        certificate["certified"] = certificate["certified"] and certificate["all_float_arrays_bitwise_equal"]
    return certificate


def float_metrics(reference_path, actual_path, atol, rtol):
    if Path(reference_path).stat().st_size != Path(actual_path).stat().st_size:
        raise RuntimeError("FP32 snapshot byte count differs")
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        a = np.fromfile(reference_path, dtype="<f4").astype(np.float64)
        b = np.fromfile(actual_path, dtype="<f4").astype(np.float64)
        finite = np.isfinite(a) & np.isfinite(b)
        if not finite.all():
            raise RuntimeError("nonfinite FP32 snapshot")
        delta = np.abs(a - b)
        limit = atol + rtol * np.abs(a)
        failures = int(np.count_nonzero(delta > limit))
        relative = delta / np.maximum(np.abs(a), 1e-30)
        return dict(elements=int(a.size), max_abs=float(delta.max(initial=0)),
                    mean_abs=float(delta.mean()), rmse=float(np.sqrt(np.mean(delta * delta))),
                    max_relative=float(relative.max(initial=0)), mismatched_elements=failures,
                    bitwise_equal=digest(reference_path) == digest(actual_path), within_epsilon=failures == 0)
    a, b = array.array("f"), array.array("f")
    for vec, path in ((a, reference_path), (b, actual_path)):
        with Path(path).open("rb") as file:
            vec.frombytes(file.read())
        if sys.byteorder != "little":
            vec.byteswap()
    max_abs = max_rel = total = squares = 0.0
    bad = 0
    for x, y in zip(a, b):
        if not math.isfinite(x) or not math.isfinite(y):
            raise RuntimeError("nonfinite FP32 snapshot")
        delta = abs(x - y)
        max_abs, max_rel = max(max_abs, delta), max(max_rel, delta / max(abs(x), 1e-30))
        total += delta
        squares += delta * delta
        bad += delta > atol + rtol * abs(x)
    return dict(elements=len(a), max_abs=max_abs, mean_abs=total / len(a), rmse=math.sqrt(squares / len(a)),
                max_relative=max_rel, mismatched_elements=bad, bitwise_equal=digest(reference_path) == digest(actual_path),
                within_epsilon=bad == 0)


def parity(reference, candidate, args, full=False):
    re, ce = reference["events"], candidate["events"]
    rs, cs = only(re, "summary"), only(ce, "summary")
    if rs.get("failed") != 0 or cs.get("failed") != 0:
        raise RuntimeError("failed inference in parity comparison")
    rf, cf = only(re, "fixture"), only(ce, "fixture")
    if rf["source_sha256"] != cf["source_sha256"] or rf["input_sha256"] != cf["input_sha256"]:
        raise RuntimeError("different source/model input bytes")
    for event, key in (("runtime_library", "sha256"), ("identity", "model_sha256"),
                       ("identity", "executable_sha256"), ("identity", "manifest_sha256")):
        if only(re, event)[key] != only(ce, event)[key]:
            raise RuntimeError("comparison provenance changed: " + key)
    if only(re, "version") != only(ce, "version"):
        raise RuntimeError("runtime API/driver versions changed")
    logical = lambda rows: [x for x in rows if x.get("event") == "tensor" and x["query"] in (1, 2)]
    if logical(re) != logical(ce):
        raise RuntimeError("queried logical tensor attributes changed")
    rframes = [x for x in re if x.get("event") == "completion"]
    cframes = [x for x in ce if x.get("event") == "completion"]
    if len(rframes) != rs["requested"] or len(cframes) != cs["requested"]:
        raise RuntimeError("completion count differs from requested runs")
    # A repeated immutable input must reproduce the first reference exactly,
    # including tuple order, class, float score and all box coordinates.
    reference_tuple = rframes[0]["detections"]
    tuple_errors = [dict(label=run["label"], completion=frame["completion"], detections=frame["detections"])
                    for run, frames in ((reference, rframes), (candidate, cframes))
                    for frame in frames if frame["count"] != len(reference_tuple) or frame["detections"] != reference_tuple]
    ra = [x for x in re if x.get("event") == "output_snapshot"]
    ca = [x for x in ce if x.get("event") == "output_snapshot"]
    first_outputs = {x["output"]: x for x in ra if x["completion"] == 1}
    if not first_outputs:
        raise RuntimeError("no raw FP32 reference arrays")
    expected_outputs = [x for x in logical(re) if x["query"] == 2]
    expected_indices = {x["attr"]["index"] for x in expected_outputs}
    if set(first_outputs) != expected_indices:
        raise RuntimeError("missing queried reference outputs")
    metrics = []
    for run, snapshots in ((reference, ra), (candidate, ca)):
        completions = {x["completion"] for x in snapshots}
        expected_completions = set(range(1, only(run["events"], "summary")["requested"] + 1)) if full else {1, only(run["events"], "summary")["requested"]}
        if completions != expected_completions:
            raise RuntimeError("missing raw float completions")
        for completion in sorted(completions):
            if {x["output"] for x in snapshots if x["completion"] == completion} != expected_indices:
                raise RuntimeError("missing output in raw float completion")
        for snapshot in snapshots:
            if digest(snapshot["path"]) != snapshot["sha256"]:
                raise RuntimeError("snapshot changed after run")
            index = snapshot["output"]
            metrics.append(dict(label=run["label"], completion=snapshot["completion"], output=index,
                                **float_metrics(first_outputs[index]["path"], snapshot["path"], args.atol, args.rtol)))
    return dict(reference=reference["label"], candidate=candidate["label"],
                exact_tuples=not tuple_errors, tuple_errors=tuple_errors,
                all_float_arrays_within_epsilon=all(x["within_epsilon"] for x in metrics),
                all_float_arrays_bitwise_equal=all(x["bitwise_equal"] for x in metrics),
                atol=args.atol, rtol=args.rtol, array_coverage="every certification completion" if full else "first/last timed completion",
                reference_count=len(reference_tuple), reference_detections=reference_tuple, arrays=metrics,
                certified=not tuple_errors and all(x["within_epsilon"] for x in metrics))


def stages(run):
    frames = [x for x in run["events"] if x.get("event") == "completion"]
    result = {}
    for stage in frames[0]["stages"]:
        result[stage] = {}
        for metric in ("wall_ms", "thread_cpu_ms"):
            values = [x["stages"][stage][metric] for x in frames]
            result[stage][metric] = dict(mean=statistics.mean(values), median=statistics.median(values),
                                        minimum=min(values), maximum=max(values))
    return result


def experiment(args, manifest, directory):
    if FD_CANDIDATE in args.candidates and len(manifest["fixtures"]) != 4:
        raise RuntimeError("FD candidate requires exactly four pinned fixtures")
    if FD_CANDIDATE in args.candidates:
        args.experiment_deadline = time.monotonic() + 1600
    target_info = target(args, manifest, directory)
    binary = Path(args.binary).resolve()
    build_receipt = binary.parent / "build_receipt.json"
    if not build_receipt.is_file():
        raise RuntimeError("build receipt missing; build with this runner first")
    binding = json.loads(build_receipt.read_text(encoding="utf-8"))
    if (binding["executable_sha256"] != digest(binary) or
        binding["prepared_manifest_sha256"] != digest(ROOT / "prepared/manifest.json") or
        binding["rknn_runtime_sha256"] != target_info["library_sha256"]):
        raise RuntimeError("build receipt does not bind current executable/source/runtime")
    save(directory / "build_receipt.json", binding)
    probe = bench(args, directory, "probe")
    report = dict(status="hardware_in_progress", target=target_info, probe=probe["label"],
                  comparisons=[], certifications=[], unsupported=[], dequant_scale=args.dequant_scale,
                  timing_reference=args.timing_reference, timing_reference_certifications=[],
                  full_viewer_fps_claim=False)
    save(directory / "report.json", report)
    chosen = [x for x in manifest["fixtures"] if not args.fixtures or x["name"] in args.fixtures]
    if not chosen or (args.fixtures and set(args.fixtures) != {x["name"] for x in chosen}):
        raise RuntimeError("unknown fixture selector")
    certified_timing_fixtures = set()
    for candidate in args.candidates:
        candidate_supported = True
        for fixture in chosen:
            name = candidate + "_" + fixture["name"]
            print(json.dumps({"event": "certify", "candidate": candidate, "fixture": fixture["name"]}), flush=True)
            reference = bench(args, directory, "baseline", fixture, name + "_cert_baseline", 3, True)
            actual = bench(args, directory, candidate, fixture, name + "_cert_candidate", 3, True)
            if "unsupported" in actual:
                report["unsupported"].append(dict(candidate=candidate, fixture=fixture["name"], reasons=actual["unsupported"]))
                candidate_supported = False
                save(directory / "report.json", report)
                break
            certificate = parity(reference, actual, args, full=True)
            certificate.update(reference_profile="baseline", candidate_mode=candidate)
            require_bitwise(certificate, candidate == FD_CANDIDATE)
            if candidate in (SINGLE_COPY, FD_CANDIDATE):
                certificate["native_input_copy"] = only(actual["events"], "native_input_copy")
                certificate["native_input_copy_verifications"] = [x for x in actual["events"]
                    if x.get("event") == "native_input_copy_verification"]
            report["certifications"].append(certificate)
            save(directory / "report.json", report)
            if not certificate["certified"]:
                report["status"] = "parity_failed_no_performance_claim"
                save(directory / "report.json", report)
                raise RuntimeError("raw float or exact tuple parity failed: " + name)
            # A native timing control is separately certified against baseline;
            # it never replaces baseline in logical/output certification.
            if args.timing_reference != "baseline" and fixture["name"] not in certified_timing_fixtures:
                timing_control = bench(args, directory, args.timing_reference, fixture, name + "_cert_timing_reference", 3, True)
                if "unsupported" in timing_control:
                    report["unsupported"].append(dict(candidate=args.timing_reference, role="timing_reference",
                                                      fixture=fixture["name"], reasons=timing_control["unsupported"]))
                    candidate_supported = False
                    save(directory / "report.json", report)
                    break
                control_certificate = parity(reference, timing_control, args, full=True)
                control_certificate.update(reference_profile="baseline", candidate_mode=args.timing_reference)
                require_bitwise(control_certificate, candidate == FD_CANDIDATE)
                report["timing_reference_certifications"].append(control_certificate)
                save(directory / "report.json", report)
                if not control_certificate["certified"]:
                    report["status"] = "timing_reference_parity_failed_no_performance_claim"
                    save(directory / "report.json", report)
                    raise RuntimeError("timing reference differs from logical baseline: " + name)
                certified_timing_fixtures.add(fixture["name"])
        if not candidate_supported:
            continue
        for fixture in chosen:
            for round_index in range(args.rounds):
                # AB, BA, AB, BA controls order; each process reloads its model.
                order = [args.timing_reference, candidate] if round_index % 2 == 0 else [candidate, args.timing_reference]
                runs = {}
                for mode in order:
                    label = f"{candidate}_{fixture['name']}_r{round_index}_{mode}"
                    print(json.dumps({"event": "measure", "label": label}), flush=True)
                    runs[mode] = bench(args, directory, mode, fixture, label)
                    if "unsupported" in runs[mode]:
                        raise RuntimeError("previously certified profile became unsupported")
                comparison = parity(runs[args.timing_reference], runs[candidate], args)
                comparison.update(reference_profile=args.timing_reference, candidate_mode=candidate)
                # The copy-only candidate must reproduce the native control
                # bitwise in the retained first/last arrays. Baseline tolerance
                # and exact tuple certification gates remain unchanged.
                copy_bitwise_required = (candidate == SINGLE_COPY and args.timing_reference == "native_io") or candidate == FD_CANDIDATE
                require_bitwise(comparison, copy_bitwise_required)
                if not comparison["certified"]:
                    report["status"] = "timed_parity_failed_no_performance_claim"
                    report["comparisons"].append(comparison)
                    save(directory / "report.json", report)
                    raise RuntimeError("parity failed in timed round")
                bsummary = only(runs[args.timing_reference]["events"], "summary")
                csummary = only(runs[candidate]["events"], "summary")
                comparison.update(candidate_mode=candidate, fixture=fixture["name"], round=round_index,
                                  order=order, baseline=bsummary, candidate_summary=csummary,
                                  baseline_stages=stages(runs[args.timing_reference]), candidate_stages=stages(runs[candidate]),
                                  completed_fps_ratio=csummary["completed_fps"] / bsummary["completed_fps"])
                report["comparisons"].append(comparison)
                save(directory / "report.json", report)
    report["status"] = "isolated_hardware_comparison_complete" if report["comparisons"] else "all_candidates_declined"
    report["performance_scope"] = "Pinned fixtures; genuine blocking NPU + I/O + frozen decoder + release. Input preprocessing, live DMA/viewer/stereo excluded."
    if FD_CANDIDATE in args.candidates:
        report["acceleration_scope"] = "native_npu_allocator_and_software_cpu_sync_copy"
        report["fpga_acceleration_claim"] = False
    report["candidate_summaries"] = {}
    for mode in args.candidates:
        comparisons = [c for c in report["comparisons"] if c.get("candidate_mode") == mode]
        if comparisons:
            ratios = [c["completed_fps_ratio"] for c in comparisons]
            report["candidate_summaries"][mode] = dict(pairs=len(ratios),
                reference_profile=args.timing_reference,
                median_completed_fps_ratio=statistics.median(ratios),
                minimum_completed_fps_ratio=min(ratios), maximum_completed_fps_ratio=max(ratios),
                parity_certified=True, needs_live_viewer_confirmation=True)
    save(directory / "report.json", report)
    print(json.dumps({"event": "finished", "report": str(directory / "report.json"),
                      "status": report["status"], "candidate_summaries": report["candidate_summaries"],
                      "unsupported": report["unsupported"], "full_viewer_fps_claim": False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("inspect", "build", "probe", "experiment"))
    parser.add_argument("--board-exclusive", action="store_true", help="Parent has released competing board work")
    parser.add_argument("--lib", required=True, help="Absolute path of the real target librknnrt.so")
    parser.add_argument("--model", default="/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn")
    parser.add_argument("--binary", help="Binary produced by a retained build receipt")
    parser.add_argument("--out", required=True, help="New private output directory; never overwrite")
    parser.add_argument("--native-query", choices=(9, 11), type=int, default=9)
    parser.add_argument("--dequant-scale", choices=("fp32", "fp16"), default="fp32",
                        help="Native affine scale precision; fp16 rounds only scale to IEEE binary16; parity gates unchanged")
    parser.add_argument("--candidates", nargs="+", choices=("prealloc", "native", "native_io", SINGLE_COPY, FD_CANDIDATE),
                        default=["prealloc", "native", "native_io"])
    parser.add_argument("--timing-reference", choices=("baseline", "native_io", SINGLE_COPY), default="baseline",
                        help="Performance control only; candidate and native control certification always use logical baseline")
    parser.add_argument("--fixtures", nargs="+")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--rtol", type=float, default=1e-6)
    args = parser.parse_args()
    if args.phase != "inspect" and not args.board_exclusive:
        parser.error("parent must supply --board-exclusive after its active diagnostic finishes")
    if args.phase in ("probe", "experiment") and not args.binary:
        parser.error("--binary required")
    if not Path(args.lib).is_absolute():
        parser.error("--lib must be an absolute target library path")
    if args.binary:
        args.binary = str(Path(args.binary).resolve())
    args.lib = str(Path(args.lib).resolve())
    args.model = str(Path(args.model).resolve())
    if min(args.iterations, args.rounds, args.timeout) < 1 or args.warmup < 0:
        parser.error("invalid timing options")
    if not all(math.isfinite(x) and x >= 0 for x in (args.atol, args.rtol)):
        parser.error("invalid epsilon")
    if args.phase == "experiment":
        if len(set(args.candidates)) != len(args.candidates) or args.timing_reference in args.candidates:
            parser.error("candidates must be distinct and different from --timing-reference")
        if (SINGLE_COPY in args.candidates or args.timing_reference == SINGLE_COPY) and (args.native_query != 9 or args.dequant_scale != "fp16"):
            parser.error("native_io_single_copy requires --native-query 9 --dequant-scale fp16")
        if FD_CANDIDATE in args.candidates:
            if (args.candidates != [FD_CANDIDATE] or args.timing_reference != SINGLE_COPY or
                args.native_query != 9 or args.dequant_scale != "fp16"):
                parser.error("FD candidate requires isolation, --timing-reference native_io_single_copy --native-query 9 --dequant-scale fp16")
            if args.fixtures or args.rounds != 4 or args.iterations != 50 or args.warmup != 5:
                parser.error("FD candidate requires all four fixtures, four alternating rounds, 50 iterations and five warmups")
    manifest = verify()
    directory = Path(args.out).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    try:
        if args.phase == "inspect":
            target(args, manifest, directory)
        elif args.phase == "build":
            build(args, manifest, directory)
        elif args.phase == "probe":
            target(args, manifest, directory)
            bench(args, directory, "probe")
        else:
            experiment(args, manifest, directory)
    except Exception as e:
        save(directory / "failure.json", dict(status="failed_no_performance_claim", reason=str(e)))
        print(json.dumps({"event": "failure", "reason": str(e), "logs": str(directory)}), flush=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
