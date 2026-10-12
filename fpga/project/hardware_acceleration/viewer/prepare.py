"""Freeze a complete viewer source bundle locally; never access a board.

Run after the parent finishes edits to the source and shared native adapter.
The frozen input and candidate are immutable, hash-addressed, and byte audited.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
DEFAULT_SOURCE = PROJECT / "per_camera_fps/swap/src"
DEFAULT_ADAPTER = ROOT.parent / "rknn_io/native_adapter.h"
DEFAULT_SDK = ROOT.parent / "rknn_io/prepared/sdk/rknn_api.h"
RETAINED = PROJECT / "per_camera_fps/host_stall/diagnostic/prepared"
MODEL_SHA = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31"
RECIPE_FILES = ("prepare.py", "hardware_inference.h", "acceptance_metrics.h", "acceptance_summary.py",
                "README.md", "local_tests/run.py", "local_tests/mock_rknn.cpp",
                "local_tests/ownership_selftest.cpp", "local_tests/acceptance_selftest.cpp")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def snapshot(directory):
    require(directory.is_dir(), f"source directory missing: {directory}")
    files = {}
    for p in sorted(directory.rglob("*")):
        require(not p.is_symlink(), f"symlink not allowed in frozen source: {p}")
        if p.is_file():
            files[p.relative_to(directory).as_posix()] = p.read_bytes()
    for name in ("main.cpp", "detview.pro", "inference_preprocess.h", "vision_types.h",
                 "motion_abi.h", "motion_policy.h", "stereo_demo/stereo_depth.cpp"):
        require(name in files, f"complete source required; missing {name}")
    require("hardware_inference.h" not in files and "native_adapter.h" not in files and "acceptance_metrics.h" not in files,
            "--source must be a baseline without this native integration")
    return files


def slice_once(data, start, end):
    require(data.count(start) == 1, f"slice start is not unique: {start!r}")
    a = data.index(start)
    require(data.count(end, a) == 1, f"slice end is not unique: {end!r}")
    return data[a:data.index(end, a)]


def patch_main(data):
    patches = []

    def replace(label, old, new):
        nonlocal data
        old, new = old.encode("ascii"), new.encode("ascii")
        require(data.count(old) == 1, f"{label}: expected one byte-exact anchor")
        data = data.replace(old, new, 1)
        patches.append(dict(label=label, old=old, new=new))

    replace("model_hash_include", "#include <QApplication>\n",
            "#include <QApplication>\n#include <QCryptographicHash>\n")
    replace("native_helper_include", '#include "rknn_api.h"\n',
            '#include "rknn_api.h"\n#include "hardware_inference.h"\n')
    replace("cached_native_owner", "            rknn_context context = 0;\n",
            "            rknn_context context = 0;\n"
            "            std::shared_ptr<HardwareInference> native;\n")
    replace("requested_IO_mode", "        QVector<CachedModel> cache;\n",
            "        QVector<CachedModel> cache;\n"
            '        const QByteArray ioEnv = qgetenv("DETVIEW_RKNN_IO").trimmed();\n'
            '        const QByteArray requestedIo = ioEnv.isEmpty() ? QByteArray("legacy") : ioEnv;\n')
    replace("reload_context_cleanup", "                for (CachedModel &old : cache) rknn_destroy(old.context);\n",
            "                for (CachedModel &old : cache) {\n"
            "                    if (old.native) old.native.reset();\n"
            "                    else if (old.context) rknn_destroy(old.context);\n"
            "                }\n")
    replace("validate_then_swap_context", "                    resetOutputs(item.outs);\n                    cache.append(std::move(item));\n",
            "                    resetOutputs(item.outs);\n"
            "                    const QByteArray modelSha = QCryptographicHash::hash(item.bytes, QCryptographicHash::Sha256).toHex();\n"
            '                    std::string ioReason = "legacy_requested";\n'
            '                    if (requestedIo == "native") {\n'
            '                        if (modelSha != "' + MODEL_SHA + '" ||\n'
            "                            info.lane || info.nc != 3) {\n"
            '                            ioReason = "model_not_eligible_for_pinned_raw_DFL_adapter";\n'
            '                        } else if (qEnvironmentVariableIsSet("DET_INT8_IN")) {\n'
            '                            ioReason = "DET_INT8_IN_requires_legacy_input_semantics";\n'
            "                        } else {\n"
            "                            item.native = HardwareInference::create(item.bytes.constData(),\n"
            "                                static_cast<size_t>(item.bytes.size()), item.attrs,\n"
            '                                true, ioReason);\n'
            "                            if (item.native) {\n"
            "                                rknn_destroy(item.context);\n"
            "                                item.context = item.native->context();\n"
            "                            }\n"
            "                        }\n"
            '                    } else if (requestedIo == "native_output") {\n'
            '                        ioReason = "native_output_only_not_certified_target_runtime";\n'
            '                    } else if (requestedIo != "legacy") {\n'
            '                        ioReason = "unknown_DETVIEW_RKNN_IO_value";\n'
            "                    }\n"
            '                    fprintf(stderr, "[rknn-io] model=%s sha256=%s requested=%s actual=%s status=%s hardware_parity=unverified dequant_scale=%s reason=%s\\n",\n'
            "                            qPrintable(info.path), modelSha.constData(), requestedIo.constData(),\n"
            '                            item.native ? "native" : "legacy",\n'
            '                            item.native ? "experimental" : "baseline",\n'
            '                            item.native ? "fp16" : "runtime_float_outputs",\n'
            "                            ioReason.c_str());\n"
            "                    cache.append(std::move(item));\n")
    replace("run_dispatch_and_runtime_fallback",
            "                const bool successful = prepared && runOnce(*prepared, item.info.path, sourceGeneration, frameId,\n"
            "                                                           preprocessingMs, item.attrs, item.outs);\n",
            "                const bool successful = item.context && prepared && runOnce(*prepared, item.info.path, sourceGeneration, frameId,\n"
            "                    preprocessingMs, item.attrs, item.native ? item.native->outputs() : item.outs, item.native.get());\n"
            "                if (!successful && item.native) {\n"
            "                    // Retire a failed native context at a quiescent frame boundary.\n"
            "                    // Never rebind it, rerun the failed frame, or count fallback as success.\n"
            "                    const std::string nativeError = item.native->error();\n"
            "                    item.native.reset();\n"
            "                    item.context = 0;\n"
            "                    bool restored = rknn_init(&item.context, item.bytes.data(),\n"
            "                        static_cast<uint32_t>(item.bytes.size()), 0, nullptr) == 0;\n"
            "                    rknn_input_output_num restoredIo{};\n"
            "                    restored = restored && rknn_query(item.context, RKNN_QUERY_IN_OUT_NUM, &restoredIo, sizeof(restoredIo)) == 0 &&\n"
            "                        restoredIo.n_input == 1 && restoredIo.n_output == item.outputs;\n"
            "                    for (size_t i = 0; restored && i < item.attrs.size(); ++i) {\n"
            "                        rknn_tensor_attr attr{}; attr.index = static_cast<uint32_t>(i);\n"
            "                        restored = rknn_query(item.context, RKNN_QUERY_OUTPUT_ATTR, &attr, sizeof(attr)) == 0 &&\n"
            "                            HardwareInference::sameLogical(attr, item.attrs[i]);\n"
            "                    }\n"
            "                    if (!restored) {\n"
            "                        if (item.context) rknn_destroy(item.context);\n"
            "                        item.context = 0;\n"
            "                    }\n"
            "                    resetOutputs(item.outs);\n"
            "                    m_ctx = 0;\n"
            '                    fprintf(stderr, "[rknn-io] model=%s actual=%s reason=native_frame_failed detail=%s\\n",\n'
            '                        qPrintable(item.info.path), restored ? "legacy" : "unavailable",\n'
            '                        nativeError.empty() ? "preprocessing_or_RKNN_run_failed" : nativeError.c_str());\n'
            "                }\n")
    replace("shutdown_context_cleanup", "        for (CachedModel &item : cache) rknn_destroy(item.context);\n",
            "        for (CachedModel &item : cache) {\n"
            "            if (item.native) item.native.reset();\n"
            "            else if (item.context) rknn_destroy(item.context);\n"
            "        }\n")
    replace("run_signature", "                 std::vector<rknn_output> &outs) {\n",
            "                 std::vector<rknn_output> &outs, HardwareInference *native) {\n")
    replace("native_input_dispatch", "        if (rknn_inputs_set(m_ctx, 1, &input) != 0)\n            return false;\n",
            "        if (native) {\n"
            "            if (!native->writeInput(input.buf, input.size)) return false;\n"
            "        } else if (rknn_inputs_set(m_ctx, 1, &input) != 0) {\n"
            "            return false;\n"
            "        }\n")
    replace("native_output_dispatch",
            "        resetOutputs(outs);\n"
            "        if (rknn_outputs_get(m_ctx, m_nOutput, outs.data(), nullptr) != 0) {\n"
            "            // Preserve the existing failed-get release policy; retain no returned pointer.\n"
            "            resetOutputs(outs);\n"
            "            return false;\n"
            "        }\n",
            "        if (native) {\n"
            "            if (!native->readOutputs()) return false;\n"
            "        } else {\n"
            "            resetOutputs(outs);\n"
            "            if (rknn_outputs_get(m_ctx, m_nOutput, outs.data(), nullptr) != 0) {\n"
            "                // Preserve the existing failed-get release policy; retain no returned pointer.\n"
            "                resetOutputs(outs);\n"
            "                return false;\n"
            "            }\n"
            "        }\n")
    replace("native_output_ownership", "        rknn_outputs_release(m_ctx, m_nOutput, outs.data());\n        resetOutputs(outs);\n",
            "        if (!native) {\n"
            "            rknn_outputs_release(m_ctx, m_nOutput, outs.data());\n"
            "            resetOutputs(outs);\n"
            "        }\n")
    replace("acceptance_include", '#include "hardware_inference.h"\n',
            '#include "hardware_inference.h"\n#include "acceptance_metrics.h"\n')
    replace("acceptance_frame_requests", "        frameStartedNs = monotonicNs();\n",
            "        frameStartedNs = monotonicNs();\n"
            "        viewerAcceptance().frameRequest(camera, op.total_length, FRAME_BYTES);\n")
    replace("acceptance_ping_tag_camera", "        if (!cameraTagLocked(ping + FRAME_BYTES, a)) return -1;\n",
            "        if (!cameraTagLocked(ping + FRAME_BYTES, a, camera)) return -1;\n")
    replace("acceptance_pong_tag_camera", "        if (!cameraTagLocked(pong + FRAME_BYTES, b)) return -1;\n",
            "        if (!cameraTagLocked(pong + FRAME_BYTES, b, camera)) return -1;\n")
    replace("acceptance_tag_requests",
            "    bool cameraTagLocked(uint32_t address, uint32_t& tag) {\n"
            "        DmaOp op{};\n"
            "        op.offset_addr = tdm::cameraScratchOffset;\n"
            "        op.ddr3_addr = address;\n"
            "        op.total_length = 16;\n"
            "        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;\n",
            "    bool cameraTagLocked(uint32_t address, uint32_t& tag, int camera) {\n"
            "        DmaOp op{};\n"
            "        op.offset_addr = tdm::cameraScratchOffset;\n"
            "        op.ddr3_addr = address;\n"
            "        op.total_length = 16;\n"
            "        viewerAcceptance().tagRequest(camera, op.total_length);\n"
            "        if (ioctlTmo(F2H_CMD, &op, 2) != 0) return false;\n")
    replace("acceptance_capture_ids", "\n    uint64_t camGen[CAM_COUNT] = {};",
            "\n    uint64_t acceptanceIds[CAM_COUNT] = {};\n    uint64_t camGen[CAM_COUNT] = {};")
    replace("acceptance_delivery_commit", "            ++frames_->camGen[idx];\n",
            "            ++frames_->camGen[idx];\n"
            "            frames_->acceptanceIds[idx] = viewerAcceptance().delivered(idx);\n")
    replace("acceptance_display_ids", "        std::array<uint64_t, CAM_COUNT> cameraSequences{};\n",
            "        std::array<uint64_t, CAM_COUNT> cameraSequences{};\n"
            "        std::array<uint64_t, CAM_COUNT> acceptanceFrameIds{};\n")
    replace("acceptance_capture_snapshot_ids", "            std::array<qint64, CAM_COUNT> captureTimes{};\n",
            "            std::array<qint64, CAM_COUNT> captureTimes{};\n"
            "            std::array<uint64_t, CAM_COUNT> acceptanceIds{};\n")
    replace("acceptance_capture_snapshot_pairing", "                    camGen[i] = latest.camGen[i];\n",
            "                    camGen[i] = latest.camGen[i];\n"
            "                    acceptanceIds[i] = latest.acceptanceIds[i];\n")
    replace("acceptance_display_publish_ids", "            display.cameraPixels = cameraPixels;\n",
            "            display.cameraPixels = cameraPixels;\n"
            "            display.acceptanceFrameIds = acceptanceIds;\n")
    replace("acceptance_inference_result",
            "preprocessingMs, item.attrs, item.native ? item.native->outputs() : item.outs, item.native.get());\n",
            "preprocessingMs, item.attrs, item.native ? item.native->outputs() : item.outs, item.native.get());\n"
            "                viewerAcceptance().inference(successful);\n")
    replace("acceptance_inference_no_model", "            } else if (hadPending) {\n                ++failedRuns;\n",
            "            } else if (hadPending) {\n                ++failedRuns;\n"
            "                viewerAcceptance().inference(false);\n")
    replace("acceptance_initial_snapshot", '        setTitle("detview");\n',
            '        setTitle("detview");\n        viewerAcceptance().report();\n')
    replace("acceptance_swap_commit", "            if (m_perfEnabled) ++m_perf.swaps;\n",
            "            if (m_perfEnabled) ++m_perf.swaps;\n"
            "            viewerAcceptance().swapped(m_acceptancePaints);\n")
    replace("acceptance_submission_ids", "        m_cameraPixels = frame.cameraPixels;\n",
            "        m_cameraPixels = frame.cameraPixels;\n"
            "        m_acceptanceFrameIds = frame.acceptanceFrameIds;\n")
    replace("acceptance_periodic_snapshot", "    void reportPerformance() {\n",
            "    void reportPerformance() {\n        viewerAcceptance().report();\n")
    replace("acceptance_paint_start", "    void paintGL() override {\n",
            "    void paintGL() override {\n        m_acceptancePaints.beginPaint();\n")
    replace("acceptance_uploaded_id", "                        m_cameraTextureSlot[c] = slot;\n",
            "                        m_cameraTextureSlot[c] = slot;\n"
            "                        m_acceptanceUploadedIds[c] = m_acceptanceFrameIds[c];\n")
    replace("acceptance_actual_camera_draw", "                glDrawArrays(GL_TRIANGLE_STRIP, camera * 4, 4);\n",
            "                glDrawArrays(GL_TRIANGLE_STRIP, camera * 4, 4);\n"
            "                m_acceptancePaints.drawn(camera, m_acceptanceUploadedIds[camera],\n"
            "                    m_cameraTextureAllocated[camera][m_cameraTextureSlot[camera]]);\n")
    replace("acceptance_gui_state", "    std::array<uint64_t, CAM_COUNT> m_sequences{}, m_uploadedSequences{};\n",
            "    std::array<uint64_t, CAM_COUNT> m_sequences{}, m_uploadedSequences{};\n"
            "    std::array<uint64_t, CAM_COUNT> m_acceptanceFrameIds{}, m_acceptanceUploadedIds{};\n"
            "    viewer_acceptance::PaintIdentities m_acceptancePaints;\n")
    return data, patches


def audit_main(baseline, candidate, patches):
    # Invert every explicitly allowed edit and require full byte equality.
    # This covers camera, video, motion, stereo, UI and scheduling code,
    # not only selected fragments of the decoder.
    restored = candidate
    for p in reversed(patches):
        require(restored.count(p["new"]) == 1, f"audit inverse not unique: {p['label']}")
        restored = restored.replace(p["new"], p["old"], 1)
    require(restored == baseline, "changes outside the explicit native/acceptance patch list")
    boundaries = {
        "raw_DFL_and_all_detection_decode": (b"    static float sigmoidf(float x)", b"\n    QMutex m_mutex;\n    QWaitCondition m_cond;\n    QImage m_pending;"),
        "lane_mask_decode": (b"    static QImage decodeLaneMask(", b"    static bool selfTestLane("),
        "run_input_preparation": (b"        const bool bench = qEnvironmentVariableIsSet(\"DET_BENCH\");", b"        if (native) {\n            if (!native->writeInput("),
    }
    hashes = {}
    for label, (start, end) in boundaries.items():
        if label == "run_input_preparation":
            before = slice_once(baseline, start, b"        if (rknn_inputs_set(m_ctx, 1, &input) != 0)")
        else:
            before = slice_once(baseline, start, end)
        after = slice_once(candidate, start, end)
        require(before == after, f"protected byte slice changed: {label}")
        hashes[label] = sha(before)
    return dict(full_main_inverse_patch_identical=True, protected_slices_sha256=hashes,
                allowed_patches=[dict(label=p["label"], old_sha256=sha(p["old"]),
                                     new_sha256=sha(p["new"]), old_bytes=len(p["old"]),
                                     new_bytes=len(p["new"])) for p in patches])


def provenance(sdk_path, sdk):
    manifest_path = RETAINED / "manifest.json"
    require(manifest_path.is_file(), "retained diagnostic SDK manifest is missing")
    retained_bytes = manifest_path.read_bytes()
    retained = json.loads(retained_bytes)
    entry = next(x for x in retained["baseline_files"] if x["path"] == "sdk/rknn_api.h")
    require(sha(sdk) == entry["sha256"], "SDK is not byte-identical to the retained working SDK")
    return dict(source=str(sdk_path), sha256=sha(sdk),
                retained_manifest_path=str(manifest_path), retained_manifest_sha256=sha(retained_bytes),
                retained_entry=entry)


def prepare(args):
    source = args.source.resolve()
    adapter_path, sdk_path = args.adapter.resolve(), args.sdk.resolve()
    files = snapshot(source)
    adapter, sdk = adapter_path.read_bytes(), sdk_path.read_bytes()
    recipe = {name: (ROOT / name).read_bytes() for name in RECIPE_FILES}
    helper = recipe["hardware_inference.h"]
    sdk_provenance = provenance(sdk_path, sdk)
    # Detect the channel-capacity fix being coordinated with the parent without
    # pinning a transient shared file hash. The actual bytes are frozen below.
    require(b"storageChannels" in adapter and b"p.storageChannels < p.c" in adapter,
            "shared NativePlan padded-channel-capacity edit is not present")
    require(b"enum class DequantScale" in adapter and b"DequantScale::Fp16" in adapter,
            "shared explicit FP16 dequant scale policy is not present")
    main, patches = patch_main(files["main.cpp"])
    audit = audit_main(files["main.cpp"], main, patches)
    # No source files other than main.cpp/.pro are modified in the candidate.
    pro_append = (b"\n# Native I/O uses the frozen retained RKNN SDK and adapter.\n"
                  b"INCLUDEPATH += $$PWD/../sdk $$PWD/..\n"
                  b"HEADERS += hardware_inference.h native_adapter.h acceptance_metrics.h\n"
                  b"linux: LIBS += -ldl\n")
    candidate = dict(files)
    candidate["main.cpp"] = main
    candidate["detview.pro"] += pro_append
    candidate["hardware_inference.h"] = helper
    candidate["native_adapter.h"] = adapter
    candidate["acceptance_metrics.h"] = recipe["acceptance_metrics.h"]
    baseline_hashes = {p: sha(b) for p, b in files.items()}
    candidate_hashes = {p: sha(b) for p, b in candidate.items()}
    require(candidate["detview.pro"][:-len(pro_append)] == files["detview.pro"], ".pro base changed")
    unchanged = sorted(p for p in files if p not in ("main.cpp", "detview.pro"))
    require(all(files[p] == candidate[p] for p in unchanged), "unrelated source bytes changed")
    audit.update(unchanged_source_files=unchanged, qmake_original_bytes_preserved=True,
                 original_source_count=len(files), candidate_source_count=len(candidate))
    # Reread all inputs after auditing: fail if another agent was editing during
    # preparation, instead of silently freezing a mixture of source generations.
    require(snapshot(source) == files, "source changed during preparation; invoke again after edits finish")
    require(adapter_path.read_bytes() == adapter, "shared adapter changed during preparation")
    require(sdk_path.read_bytes() == sdk and (ROOT / "hardware_inference.h").read_bytes() == helper,
            "SDK/helper changed during preparation")
    require(all((ROOT / name).read_bytes() == data for name, data in recipe.items()),
            "integration recipe changed during preparation")
    identity = dict(baseline=baseline_hashes, candidate=candidate_hashes, sdk=sha(sdk),
                    recipe_sha256={name: sha(data) for name, data in recipe.items()}, model_sha256=MODEL_SHA)
    digest = sha(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode())
    if args.audit_only:
        print(json.dumps(dict(status="local_byte_audit_passed_no_freeze", bundle_sha256=digest,
                              source=str(source), adapter_sha256=sha(adapter), audit=audit,
                              board_access=False), indent=2))
        return
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    dest = output_root / digest[:24]
    require(not dest.exists(), f"immutable bundle already exists: {dest}; use its existing manifest")
    staging = Path(tempfile.mkdtemp(prefix=".preparing-", dir=output_root))
    try:
        manifest = dict(schema=1, status="prepared_only_no_build_or_hardware_test",
                        prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        bundle_sha256=digest, source_path=str(source), baseline_main_sha256=sha(files["main.cpp"]),
                        candidate_main_sha256=sha(main), model_sha256=MODEL_SHA,
                        default_io="legacy", native_query=9, native_status="experimental_hardware_parity_unverified",
                        input="unchanged full-frame CPU letterbox; UINT8 NHWC [1,640,640,3], pass_through=0; no -128",
                        native_modes={"native": "bound UINT8 input and bound native outputs; experimental"},
                        rejected_modes={"native_output": "native_output_only_not_certified_target_runtime"},
                        dequant_scale_policy=dict(policy="NativePlan::DequantScale::Fp16", model_sha256=MODEL_SHA,
                                                  sdk_api="2.3.0", driver="0.9.8", selection="once_at_model_setup"),
                        acceptance=dict(enabled_by="DETVIEW_ACCEPTANCE=1 or DETVIEW_ACCEPTANCE_DIR",
                                        counter_policy="cumulative_no_reset; independent_atomic_reads_with_monotonic_bounds",
                                        cadence_seconds=5, paint_source="camera_texture_draw_then_Qt_frameSwapped; not_verified_scanout",
                                        dma_request_bytes="full frame + 16 byte trailing tag; before ioctl including failures; camera tag reads separate"),
                        adapter_provenance=dict(source=str(adapter_path), sha256=sha(adapter),
                                                copied_at_prepare_time=True, hardware_certified=False),
                        sdk_provenance=sdk_provenance, audit=audit,
                        identity=identity,
                        pending=["parent native tensor/decoder hardware parity", "parent target build and dependency/runtime receipts",
                                 "matched >=120 second completed inference comparison with all six video streams and stereo"])
        for group, contents in (("frozen", files), ("candidate", candidate)):
            for name, data in contents.items():
                path = staging / group / "src" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (staging / group / "sdk").mkdir()
            (staging / group / "sdk/rknn_api.h").write_bytes(sdk)
        for name, data in recipe.items():
            path = staging / "recipe" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (staging / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        diff = difflib.unified_diff(files["main.cpp"].decode("utf-8").splitlines(True),
                                    main.decode("utf-8").splitlines(True),
                                    fromfile="frozen/src/main.cpp", tofile="candidate/src/main.cpp")
        (staging / "main.patch").write_text("".join(diff), encoding="utf-8", newline="")
        manifest["files_sha256"] = {p.relative_to(staging).as_posix(): sha(p.read_bytes())
                                     for p in sorted(staging.rglob("*")) if p.is_file()}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        verify_bundle(staging)
        os.rename(staging, dest)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps(dict(status=manifest["status"], bundle=str(dest), manifest=str(dest / "manifest.json"),
                          manifest_sha256=sha((dest / "manifest.json").read_bytes()), board_access=False)))


def verify_bundle(bundle):
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    require(all(not p.is_symlink() for p in bundle.rglob("*")), "symlink in immutable bundle")
    actual = {p.relative_to(bundle).as_posix(): sha(p.read_bytes()) for p in sorted(bundle.rglob("*"))
              if p.is_file() and p != bundle / "manifest.json"}
    require(actual == manifest["files_sha256"], "frozen bundle file set or bytes changed")
    before = (bundle / "frozen/src/main.cpp").read_bytes()
    after, patches = patch_main(before)
    require(after == (bundle / "candidate/src/main.cpp").read_bytes(), "candidate differs from exact allowed patches")
    audit_main(before, after, patches)
    for name, expected in manifest["identity"]["recipe_sha256"].items():
        require(sha((bundle / "recipe" / name).read_bytes()) == expected, f"recipe differs: {name}")
    for group in ("frozen", "candidate"):
        expected = manifest["identity"]["baseline" if group == "frozen" else "candidate"]
        got = {p.relative_to(bundle / group / "src").as_posix(): sha(p.read_bytes())
               for p in sorted((bundle / group / "src").rglob("*")) if p.is_file()}
        require(got == expected, f"{group} complete source hashes differ")
        require(sha((bundle / group / "sdk/rknn_api.h").read_bytes()) == manifest["identity"]["sdk"],
                f"{group} SDK differs")
    digest = sha(json.dumps(manifest["identity"], sort_keys=True, separators=(",", ":")).encode())
    require(digest == manifest["bundle_sha256"], "bundle identity hash differs")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help="complete baseline src tree, frozen only at invocation")
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--sdk", type=Path, default=DEFAULT_SDK)
    parser.add_argument("--output", type=Path, default=ROOT / "prepared")
    parser.add_argument("--audit-only", action="store_true", help="byte audit in memory, no source copy")
    parser.add_argument("--verify", type=Path, help="verify an existing immutable bundle without board access")
    arguments = parser.parse_args()
    if arguments.verify:
        m = verify_bundle(arguments.verify.resolve())
        print(json.dumps(dict(status="frozen_bundle_verified", bundle_sha256=m["bundle_sha256"], board_access=False)))
    else:
        prepare(arguments)
