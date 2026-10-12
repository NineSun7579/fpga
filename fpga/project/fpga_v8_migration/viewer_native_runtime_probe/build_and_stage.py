"""Stage byte-identical source dependencies only in this probe's new directory."""
import hashlib
import json
from pathlib import Path
import re
import shlex
from remote import BASE, HERE, call, connect, root


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepare():
    candidate = BASE / "viewer_native_candidate"
    recovered = BASE / "viewer_build_recovered/inputs"
    frozen = {}
    for path in sorted((candidate / "src").rglob("*")):
        if path.is_file():
            frozen[str(path.relative_to(BASE))] = sha(path.read_bytes())
    for name in ("patch.diff", "candidate_manifest.json", "frozen_inputs_sha256.json", "native_guard_selftest.cpp"):
        path = candidate / name
        frozen[str(path.relative_to(BASE))] = sha(path.read_bytes())
    write_json("candidate_public_hashes_before.json", frozen)
    dependency_dir = HERE / "dependencies"
    dependency_dir.mkdir(exist_ok=True)
    copied = []

    def copy(source, relative, data=None):
        original = source.read_bytes()
        payload = original if data is None else data
        target = dependency_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload) # Exact support snapshots; never edits originals.
        copied.append({"original": str(source), "original_sha256": sha(original), "snapshot": str(target),
            "remote_relative": relative, "bytes": len(payload), "sha256": sha(payload), "byte_identical_whole_file": data is None})
    for name in ("viewer_native_qt.hpp", "viewer_native_guard.hpp", "raw_dfl_native.h", "rknn_api.h"):
        copy(candidate / "src" / name, "src/" + name)
    copy(candidate / "native_guard_selftest.cpp", "native_guard_selftest.cpp")
    for name in ("legacy_production_adapter.h", "raw_dfl_reference.h", "raw_dfl_native.h"):
        copy(BASE / "host_acceleration" / name, "host_acceleration/" + name)
    require_native = (candidate / "src/raw_dfl_native.h").read_bytes()
    assert require_native == (BASE / "host_acceleration/raw_dfl_native.h").read_bytes()
    assert (candidate / "src/rknn_api.h").read_bytes() == (recovered / "rknn_api.h").read_bytes()
    production = (BASE / "board/board_production_decoder.inc").read_bytes()
    main = (recovered / "main.cpp").read_bytes()
    production_offset = main.find(production)
    assert production_offset >= 0, "production decoder is not exact contiguous recovered main bytes"
    copy(BASE / "board/board_production_decoder.inc", "board/board_production_decoder.inc")
    vision_types = (candidate / "src/vision_types.h").read_bytes()
    start = vision_types.index(b"struct Detection {")
    end = vision_types.index(b"\n};", start) + len(b"\n};")
    detection = vision_types[start:end]
    assert detection in (recovered / "vision_types.h").read_bytes()
    copy(candidate / "src/vision_types.h", "viewer_detection.inc", detection)
    candidate_main = (candidate / "src/main.cpp").read_bytes()
    start = candidate_main.index(b"                for (uint32_t i = 0; i < m_nOutput; ++i)\n", candidate_main.index(b"if (nativeDecode) {", candidate_main.index(b"QImage laneMask;")))
    end = candidate_main.index(b"            } catch (const std::exception& e)", start)
    conversion = candidate_main[start:end]
    assert b"const auto owned = m_nativeSession->decoder->decode(outs, attrs);" in conversion
    copy(candidate / "src/main.cpp", "candidate_conversion.inc", conversion)
    pipeline_source_bytes = (BASE / "host_acceleration/pipeline_bench.cpp").read_bytes()
    pstart = pipeline_source_bytes.index(b"cv::Mat prepare(const cv::Mat& bgr) {")
    pend = pipeline_source_bytes.index(b"\n}\n", pstart) + 2
    copy(BASE / "host_acceleration/pipeline_bench.cpp", "pipeline_prepare.inc", pipeline_source_bytes[pstart:pend])
    write_json("decoder_and_conversion_binding.json", {
        "recovered_main_sha256": sha(main), "decoder_sha256": sha(production),
        "production_contiguous_exact_offset": production_offset, "production_exact_bytes": len(production),
        "candidate_main_sha256": sha(candidate_main), "conversion_exact_offset": start,
        "conversion_bytes": len(conversion), "conversion_sha256": sha(conversion),
        "detection_struct_sha256": sha(detection), "detection_exact_recovered_and_candidate": True,
        "sdk_sha256": sha((recovered / "rknn_api.h").read_bytes())})
    write_json("source_dependencies.json", copied)
    pipeline_source = BASE / "pipeline_board_runtime_compatible/pipeline_source.json"
    pipeline = json.loads(pipeline_source.read_bytes())
    print("pipeline top-level keys:", ", ".join(pipeline), flush=True)
    frames = json.loads((BASE / "evaluation_frames/manifest.json").read_bytes())["images"]
    historical = pipeline["frames"]
    assert len(frames) == len(historical) == 30
    rows = []
    for png, prepared in zip(frames, historical):
        assert png["board_path"] == prepared["path"]
        rows.append({"board_path": png["board_path"], "png_sha256": png["sha256"], "rgb_sha256": prepared["preprocessed_rgb_sha256"]})
    write_json("input_expectations.json", {"inputs": rows, "pipeline_source_sha256": sha(pipeline_source.read_bytes()),
        "evaluation_manifest_sha256": sha((BASE / "evaluation_frames/manifest.json").read_bytes()),
        "pipeline_experiment_manifest_sha256": sha((BASE / "pipeline_board_runtime_compatible/experiment_manifest.json").read_bytes())})
    makefile_path = BASE / "viewer_rebuild_evidence/Makefile"
    makefile = makefile_path.read_text()
    def var(name):
        return re.search(r"^" + re.escape(name) + r"\s*=\s*(.*)$", makefile, re.M).group(1)
    flags = var("CXXFLAGS").replace("$(DEFINES)", "-DQT_NO_DEBUG -DQT_CORE_LIB")
    flags += " -fno-fast-math"
    includes = [p for p in shlex.split(var("INCPATH")) if "QtWidgets" not in p and "QtGui" not in p and "opencv4" not in p and p != "-I."]
    write_json("compiler_flag_binding.json", {"viewer_makefile": str(makefile_path), "viewer_makefile_sha256": sha(makefile_path.read_bytes()),
        "original_cxxflags": var("CXXFLAGS"), "original_defines": var("DEFINES"), "original_incpath": var("INCPATH"),
        "probe_cxxflags": flags, "probe_qt_includes": includes, "lflags": var("LFLAGS"),
        "adjustments": "QtCore-only defines/includes/link; explicit -fno-fast-math; exact viewer O2/GNU C++17 options"})
    return copied, flags, includes, var("LFLAGS")


def stage_and_build(copied, flags, includes, lflags):
    stage = root()
    helper, client = connect()
    try:
        with client.open_sftp() as sftp:
            for directory in ("src", "host_acceleration", "board"):
                try:
                    sftp.stat(stage + "/" + directory)
                except FileNotFoundError:
                    sftp.mkdir(stage + "/" + directory)
            for row in copied:
                sftp.put(row["snapshot"], stage + "/" + row["remote_relative"])
            for name in ("runtime_probe.cpp", "prepare_inputs.cpp", "input_expectations.json", "capture_dependencies.py"):
                sftp.put(str(HERE / name), stage + "/" + name)
        sdk_remote = "/userdata/linaro/fpga_v8_viewer_binding_20261005/rknn_api.h"
        rc, output, _ = call(helper, client, "actual_viewer_sdk_identity", "sha256sum " + shlex.quote(sdk_remote))
        assert rc == 0 and output.split()[0] == json.loads((HERE / "decoder_and_conversion_binding.json").read_text())["sdk_sha256"]
        cflags = flags + " " + " ".join(includes) + " -I" + shlex.quote(stage) + " -I" + shlex.quote(stage + "/src")
        commands = []
        for source, binary in (("prepare_inputs.cpp", "prepare_inputs"), ("runtime_probe.cpp", "runtime_probe"), ("native_guard_selftest.cpp", "native_guard_selftest")):
            extra = " -I/usr/include/opencv4" if binary == "prepare_inputs" else ""
            compile_command = "g++ " + cflags + extra + " -MD -MF " + shlex.quote(stage + "/" + binary + ".d") + " -c " + shlex.quote(stage + "/" + source) + " -o " + shlex.quote(stage + "/" + binary + ".o")
            commands.append(compile_command)
            (HERE / "compiler_link_commands.txt").write_text("\n".join(commands) + "\n")
            compile_limit = 300 if binary == "runtime_probe" else 90
            rc, _, _ = call(helper, client, binary + "_compile", "timeout " + str(compile_limit) + "s " + compile_command, timeout=compile_limit + 15)
            if rc:
                raise RuntimeError(binary + " compile failed; inspect retained stderr")
            libraries = " -lrknnrt /usr/lib/aarch64-linux-gnu/libQt5Core.so -lpthread" if binary == "runtime_probe" else ""
            if binary == "prepare_inputs":
                libraries = " -lopencv_core -lopencv_imgcodecs -lopencv_imgproc /usr/lib/aarch64-linux-gnu/libQt5Core.so -lpthread"
            link_command = "g++ " + lflags + " -o " + shlex.quote(stage + "/" + binary) + " " + shlex.quote(stage + "/" + binary + ".o") + libraries
            commands.append(link_command)
            (HERE / "compiler_link_commands.txt").write_text("\n".join(commands) + "\n")
            rc, _, _ = call(helper, client, binary + "_link", "timeout 30s " + link_command, timeout=45)
            if rc:
                raise RuntimeError(binary + " link failed")
        (HERE / "compiler_link_commands.txt").write_text("\n".join(commands) + "\n")
        rc, _, _ = call(helper, client, "prepare_inputs_cpp", "timeout 45s " + shlex.quote(stage + "/prepare_inputs") + " " + shlex.quote(stage), sudo=True, timeout=60)
        if rc:
            raise RuntimeError("RGB preparation/hash check failed; no inference performed")
        call(helper, client, "binary_identity", "sha256sum " + shlex.quote(stage + "/runtime_probe") + " " + shlex.quote(stage + "/native_guard_selftest") + "\nldd " + shlex.quote(stage + "/runtime_probe") + "\nreadelf -d " + shlex.quote(stage + "/runtime_probe"))
        rc, _, _ = call(helper, client, "dependency_identity", "python3 " + shlex.quote(stage + "/capture_dependencies.py") + " " + shlex.quote(stage), timeout=60)
        if rc:
            raise RuntimeError("dependency capture failed")
        with client.open_sftp() as sftp:
            for name in ("prepared_inputs.json", "runtime_probe.d", "native_guard_selftest.d", "compiled_dependency_hashes.json"):
                sftp.get(stage + "/" + name, str(HERE / name))
    finally:
        client.close()


if __name__ == "__main__":
    stage_and_build(*prepare())
