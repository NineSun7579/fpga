"""Build and run local mock-runtime ownership checks using Linux g++; no NPU."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import prepare
import acceptance_summary


def run(command):
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {command!r}\n"
                           + completed.stdout + completed.stderr)
    return completed.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="save the local validation receipt")
    args = parser.parse_args()
    require_linux = sys.platform.startswith("linux")
    if not require_linux:
        raise RuntimeError("invoke under WSL/Linux; this is a local mock test only")
    sdk = prepare.DEFAULT_SDK.read_bytes()
    sdk_provenance = prepare.provenance(prepare.DEFAULT_SDK, sdk)
    input_paths = {name: ROOT / name for name in prepare.RECIPE_FILES}
    input_paths["shared_native_adapter"] = prepare.DEFAULT_ADAPTER
    inputs = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in input_paths.items()}
    records = []
    with tempfile.TemporaryDirectory(prefix="rknn-viewer-ownership-") as temp:
        out = Path(temp)
        (out / "sdk").mkdir()
        (out / "sdk/rknn_api.h").write_bytes(sdk)
        includes = ["-I" + str(out / "sdk"), "-I" + str(out), "-I" + str(ROOT),
                    "-I" + str(prepare.DEFAULT_ADAPTER.parent)]
        for name, macros, mode in (("current", [], []), ("old", ["-DOMIT_CREATE2"], ["old-allocator"]),
                                    ("missing", ["-DOMIT_SYNC"], ["missing-sync"])):
            library = out / ("libmock_" + name + ".so")
            exe = out / ("ownership_" + name)
            common = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-O2"]
            run(common + includes + macros + ["-shared", "-fPIC", str(ROOT / "local_tests/mock_rknn.cpp"), "-o", str(library)])
            run(common + includes + [str(ROOT / "local_tests/ownership_selftest.cpp"), str(library), "-ldl", "-o", str(exe)])
            result = run([str(exe)] + mode)
            symbols = run(["nm", "-u", str(exe)])
            assert not any(symbol in symbols for symbol in ("rknn_create_mem", "rknn_mem_sync", "rknn_set_io_mem", "rknn_destroy_mem"))
            records.append(dict(runtime=name, result=result,
                                executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                                optional_apis_have_no_link_dependency=True))
        # Compile the actual patched InferenceThread, including cache ownership,
        # reload and fallback code, against real Qt headers. No viewer source
        # snapshot or mock copy of the worker implementation is maintained.
        main_bytes = (prepare.DEFAULT_SOURCE / "main.cpp").read_bytes()
        patched, patches = prepare.patch_main(main_bytes)
        source_audit = prepare.audit_main(main_bytes, patched, patches)
        model = prepare.slice_once(patched, b"struct ModelInfo {", b"\nstatic bool selectRotation(")
        constants = prepare.slice_once(patched, b"static const int MODEL_W =", b"\n/* ---------------- dma-heap")
        start = patched.index(b"class InferenceThread : public QThread {")
        end_marker = b"    int m_accSplitN = 0;\n};\n"
        end = patched.index(end_marker, start) + len(end_marker)
        worker = patched[start:end]
        unit = (b"#include <QtCore>\n#include <QtGui>\n#include <algorithm>\n#include <atomic>\n"
                b"#include <cmath>\n#include <cstdio>\n#include <cstring>\n#include <memory>\n#include <vector>\n#include <time.h>\n"
                b'#include "vision_types.h"\n#include "frame_metrics.h"\n#include "inference_preprocess.h"\n'
                b'#include "hardware_inference.h"\n#include "acceptance_metrics.h"\n' + constants + model + worker)
        unit_path = out / "inference_thread.cpp"
        unit_path.write_bytes(unit)
        qt_flags = shlex.split(run(["pkg-config", "--cflags", "Qt5Core", "Qt5Gui"]))
        run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC", "-fsyntax-only"] +
            includes + ["-I" + str(prepare.DEFAULT_SOURCE)] + qt_flags + [str(unit_path)])
        records.append(dict(check="actual_patched_InferenceThread_Qt_syntax", result="PASS",
                            source_main_sha256=hashlib.sha256(main_bytes).hexdigest(),
                            candidate_main_sha256=hashlib.sha256(patched).hexdigest(),
                            source_snapshot_frozen=False))
        # Execute the exact recipe's environment parsing and model-load selection
        # block, so the output-only regression cannot hide behind a helper check.
        cached = prepare.slice_once(patched, b"        struct CachedModel {", b"        QVector<CachedModel> cache;")
        requested = next(p["new"] for p in patches if p["label"] == "requested_IO_mode")
        selection = prepare.slice_once(patched, b"                    const QByteArray modelSha =",
                                       b"                    cache.append(std::move(item));")
        reset = prepare.slice_once(patched, b"    static void resetOutputs(std::vector<rknn_output> &outs)",
                                   b"\n\n    bool runOnce(")
        profile_unit = (b'#include <QtCore>\n#include <cassert>\n#include <cstdio>\n#include "hardware_inference.h"\n' +
                        model + reset + b'\nextern "C" void mock_reset();\nextern "C" int mock_stat(const char *);\n'
                        b'extern "C" int mock_live_contexts();\nextern "C" int mock_live_memories();\n'
                        b'int main(int argc, char **argv) {\n QCoreApplication app(argc, argv);\n mock_reset();\n' +
                        cached + requested + b'''
    CachedModel item;
    item.bytes = "local_mock_not_pinned_model";
    item.info.path = "local_mock.rknn";
    item.info.nc = 3;
    const ModelInfo &info = item.info;
    assert(rknn_init(&item.context, item.bytes.data(), uint32_t(item.bytes.size()), 0, nullptr) == 0);
    const rknn_context old = item.context;
    item.attrs.resize(4);
    for (uint32_t i = 0; i < 4; ++i) {
        item.attrs[i].index = i;
        assert(rknn_query(old, RKNN_QUERY_OUTPUT_ATTR, &item.attrs[i], sizeof(item.attrs[i])) == 0);
    }
    item.outs.resize(4);
    resetOutputs(item.outs);
''' + selection + b'''
    assert(!item.native && item.context == old);
    assert(mock_live_contexts() == 1 && mock_live_memories() == 0);
    assert(mock_stat("init_calls") == 1 && mock_stat("allocate_calls") == 0);
    assert(mock_stat("bind_calls") == 0 && mock_stat("sync_calls") == 0);
    assert(argc == 3 && requestedIo == argv[1] && ioReason == argv[2]);
    assert(rknn_run(item.context, nullptr) == 0);
    assert(mock_stat("run_calls") == 1);
    rknn_destroy(item.context);
    std::puts("PASS recipe selection preserves usable legacy context without native setup");
}
''')
        profile_path, profile_exe = out / "profile_selection.cpp", out / "profile_selection"
        profile_path.write_bytes(profile_unit)
        qt_core = shlex.split(run(["pkg-config", "--cflags", "--libs", "Qt5Core"]))
        run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC"] + includes +
            [str(profile_path), str(out / "libmock_current.so"), "-ldl", "-o", str(profile_exe)] + qt_core)
        profiles = []
        for value, expected_mode, reason in (("native_output", "native_output", "native_output_only_not_certified_target_runtime"),
                                             ("legacy", "legacy", "legacy_requested"),
                                             ("", "legacy", "legacy_requested"),
                                             ("unknown", "unknown", "unknown_DETVIEW_RKNN_IO_value"),
                                             ("native", "native", "model_not_eligible_for_pinned_raw_DFL_adapter")):
            result = run(["env", "DETVIEW_RKNN_IO=" + value, str(profile_exe), expected_mode, reason])
            profiles.append(dict(requested=value, actual="legacy", reason=reason, result=result))
        records.append(dict(check="actual_recipe_mode_selection", result="PASS", profiles=profiles))
        # Compile the actual capture, upload/draw and swap instrumentation with
        # Qt. Remove only unused pre-controller OpenCV/RGA includes on this host;
        # no touched class implementation is stubbed or rewritten.
        display_unit = patched[:patched.index(b"class DetViewController : public QObject {")]
        for header in (b'#include "vision_pipeline.h"\n', b'#include "template_tracker.h"\n',
                       b'#include "stereo_demo/stereo_depth.h"\n', b'#include <rga/im2d.h>\n', b'#include <rga/rga.h>\n'):
            display_unit = display_unit.replace(header, b"")
        display_path = out / "actual_capture_display.cpp"
        display_path.write_bytes(display_unit)
        qt_widgets = shlex.split(run(["pkg-config", "--cflags", "Qt5Widgets"]))
        run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC", "-fsyntax-only"] +
            includes + ["-I" + str(prepare.DEFAULT_SOURCE)] + qt_widgets + [str(display_path)])
        records.append(dict(check="actual_capture_display_acceptance_Qt_syntax", result="PASS"))
        acceptance_exe = out / "acceptance_selftest"
        run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-fPIC", "-pthread"] + includes +
            [str(ROOT / "local_tests/acceptance_selftest.cpp"), "-o", str(acceptance_exe)] + qt_core)
        result = run(["env", "DETVIEW_ACCEPTANCE_DIR=" + str(out / "private"), str(acceptance_exe)])
        records.append(dict(check="acceptance_identities_and_cumulative_counters", result=result,
                            hardware_test=False))
        fixture = json.loads((out / "private/snapshot.json").read_text())
        import copy
        first = copy.deepcopy(fixture)
        last = copy.deepcopy(fixture)
        first["sample_begin_ns"], first["sample_end_ns"] = "1000000000", "1000000300"
        last["sample_begin_ns"], last["sample_end_ns"] = "121000001000", "121000001500"
        last["snapshot"] = "25"
        last["completed"] = str(int(first["completed"]) + 2400)
        for key in acceptance_summary.ARRAYS:
            last[key] = [str(int(value) + 1000) for value in first[key]]
        summary = acceptance_summary.observed_window(first, last)
        assert summary["delta"]["completed"] == 2400 and summary["seconds_bounds"][0] >= 120
        for changed in (dict(epoch="different"), dict(sample_begin_ns="120000000000"), dict(completed="0")):
            bad = copy.deepcopy(last); bad.update(changed)
            try:
                acceptance_summary.observed_window(first, bad)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid acceptance interval was accepted")
        records.append(dict(check="acceptance_delta_bounds_and_epoch_rejection", result="PASS",
                            hardware_test=False, fixture="synthetic_endpoint_bounds"))
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == inputs[name]
               for name, path in input_paths.items()), "test inputs changed during compilation"
    report = dict(status="local_mock_checks_passed", hardware_test=False,
                  validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  compiler=run(["g++", "--version"]).splitlines()[0],
                  qt_version=run(["pkg-config", "--modversion", "Qt5Core"]),
                  retained_sdk_sha256=hashlib.sha256(sdk).hexdigest(),
                  sdk_provenance=sdk_provenance, inputs_sha256=inputs, source_audit=source_audit, records=records)
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.resolve().write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
