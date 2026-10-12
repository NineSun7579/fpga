"""Local byte-preserving preparation only; never connects to or runs a board."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
MODEL_SHA = "21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31"
MODEL = "/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def slice_once(data, start, end):
    assert data.count(start) == 1, start
    a = data.index(start)
    b = data.index(end, a)
    return data[a:b]


def prepare():
    frozen = PROJECT / "per_camera_fps/host_stall/diagnostic/prepared/frozen"
    retained_manifest = PROJECT / "per_camera_fps/host_stall/diagnostic/prepared/manifest.json"
    retained = json.loads(retained_manifest.read_text(encoding="utf-8"))
    main = (frozen / "src/main.cpp").read_bytes()
    sdk = (frozen / "sdk/rknn_api.h").read_bytes()
    assert sha(main) == retained["baseline_main_sha256"]
    sdk_entry = next(x for x in retained["baseline_files"] if x["path"] == "sdk/rknn_api.h")
    assert sha(sdk) == sdk_entry["sha256"]
    out = ROOT / "prepared"
    (out / "frozen").mkdir(parents=True, exist_ok=True)
    (out / "sdk").mkdir(exist_ok=True)
    (out / "fixtures").mkdir(exist_ok=True)
    (out / "historical").mkdir(exist_ok=True)
    for name in ("main.cpp", "vision_types.h"):
        (out / "frozen" / name).write_bytes((frozen / "src" / name).read_bytes())
    (out / "sdk/rknn_api.h").write_bytes(sdk)
    # Every decoder statement is copied verbatim, including layout detection,
    # DFL, sigmoid heuristics, sorting, confidence threshold and NMS.
    decoder = slice_once(main, b"    static float sigmoidf(float x)", b"\n    QMutex m_mutex;\n    QWaitCondition m_cond;\n    QImage m_pending;")
    constants = slice_once(main, b"static const int MODEL_W =", b"\nstatic qint64 monotonicMs()")
    converter = slice_once(main, b"static void rgb565ToRgb888Line(", b"\nclass CameraWorker :")
    header = (b"#pragma once\n#include <algorithm>\n#include <atomic>\n#include <cmath>\n"
              b"#include <cstring>\n#include <vector>\n#include \"sdk/rknn_api.h\"\n"
              b"#include \"frozen/vision_types.h\"\n" + constants + converter +
              b"\nclass FrozenDecoder {\npublic:\n" + decoder +
              b"\nprivate:\n    int m_nc = 3;\n    bool m_xyxy = false;\n"
              b"    std::atomic<float> m_conf{0.25f};\n};\n")
    (out / "frozen_decoder.h").write_bytes(header)
    parity = PROJECT / "performance_100h/cache_parity"
    parity_manifest = json.loads((parity / "manifest.json").read_text(encoding="utf-8"))
    history = parity / "run_bf6d599692ac0dc4_1791077103421728300"
    request_bytes = (history / "request.json").read_bytes()
    request = json.loads(request_bytes)
    assert request["pins"][MODEL] == MODEL_SHA
    (out / "historical/request.json").write_bytes(request_bytes)
    fixtures = []
    for name in ("bright_baseline_cam1", "candidate_cam1"):
        old = parity_manifest["scenes"][name]
        data = (parity / old["path"]).read_bytes()
        assert sha(data) == old["sha256"]
        dest = "fixtures/" + old["path"]
        (out / dest).write_bytes(data)
        log_name = name + "_reload1_baseline.log"
        log = (history / log_name).read_bytes()
        (out / "historical" / log_name).write_bytes(log)
        rows = [json.loads(line.split("[parity] ", 1)[1]) for line in log.decode("utf-8").splitlines()
                if "[parity] " in line]
        frames = [x for x in rows if x["event"] == "frame"]
        assert len(frames) == 3 and all(x["detections"] == frames[0]["detections"] for x in frames)
        assert next(x for x in rows if x["event"] == "load")["info"] == "4 outputs cached"
        # Earlier harness prints nine significant digits, sufficient to recover
        # exactly the original float32 rather than compare rounded JSON doubles.
        tuples = [{key: value if key == "class" else struct.unpack("<f", struct.pack("<f", value))[0]
                   for key, value in detection.items()} for detection in frames[0]["detections"]]
        reference = dict(path="historical/" + log_name, sha256=sha(log), output_count=4,
                         count=frames[0]["count"], detections=tuples,
                         historical_request_sha256=sha(request_bytes),
                         policy="Require exact recovered FP32 tuples from previously executed baseline fixture; fail if current runtime differs.")
        fixtures.append(dict(name=name, path=dest, kind="png", sha256=sha(data), provenance=old,
                             historical_reference=reference))
    for camera in (1, 2):
        src = PROJECT / f"tp/quad_accept/live_cam{camera}_bank0_0.rgb565"
        data = src.read_bytes()
        assert len(data) == 640 * 480 * 2, (src, len(data))
        dest = "fixtures/" + src.name
        (out / dest).write_bytes(data)
        fixtures.append(dict(name=src.stem, path=dest, kind="rgb565_le", sha256=sha(data),
                             provenance={"source": src.relative_to(PROJECT).as_posix(),
                                         "source_sha256": sha(data),
                                         "limitation": "Retained full camera fixture; no fresh camera/DMA access."}))
    hashes = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    local_sources = {path.name for path in ROOT.iterdir() if path.is_file() and path.suffix in {'.h', '.cpp', '.pro'}}
    fd_checks = ROOT/'local_tests/fd_import_checks.py'
    if fd_checks.is_file():
        local_sources.add('local_tests/fd_import_checks.py')
    for name in sorted(local_sources | {"prepare.py", "run_target.py", "README.md"}):
        path = ROOT / name
        hashes[name] = sha(path.read_bytes())
    manifest = dict(schema=1, status="prepared_only_no_build_or_hardware_test",
                    model_path=MODEL, model_sha256=MODEL_SHA,
                    retained_manifest_sha256=sha(retained_manifest.read_bytes()),
                    retained_main_sha256=sha(main), retained_sdk_sha256=sha(sdk),
                    decoder_slice_sha256=sha(decoder), constants_slice_sha256=sha(constants),
                    converter_slice_sha256=sha(converter), fixture_width=640, fixture_height=480,
                    model_input="UINT8 NHWC RGB888 full 640x480 at y=80, gray114 640x640; pass_through=0",
                    decoder={"nc": 3, "xyxy": False, "confidence": 0.25, "iou": 0.45},
                    source_binary_binding="Extracted verbatim from retained working source; no claim of complete original viewer compiler-input binding.",
                    output_shapes="Query real model; never infer four/six tensors from filename.",
                    fixtures=fixtures, files_sha256=hashes,
                    hardware_pending=["runtime/driver ABI queries", "native layout certification against float arrays",
                                      "exact decoder tuples", "completed FPS and stage wall/thread CPU measurements"])
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "manifest": str(out / "manifest.json"),
                      "manifest_sha256": sha((out / "manifest.json").read_bytes()), "board_access": False}))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    prepare()
