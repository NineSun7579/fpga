"""Read-only baseline comparison; emit isolated viewer diff and hash manifest."""
import difflib
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
baseline = root.parent.parent / "display_latency_delivery" / "src"
allowed = {"main.cpp", "detview.pro"}
records, differences, changed = [], [], []
for source in sorted(baseline.rglob("*")):
    if not source.is_file():
        continue
    relative = source.relative_to(baseline)
    candidate = root / relative
    before, after = source.read_bytes(), candidate.read_bytes()
    same = before == after
    records.append({"path": relative.as_posix(), "baseline_sha256": hashlib.sha256(before).hexdigest(),
                    "candidate_sha256": hashlib.sha256(after).hexdigest(), "identical": same})
    if not same:
        assert relative.as_posix() in allowed, f"Unexpected baseline source change: {relative}"
        changed.append(relative.as_posix())
        differences.extend(difflib.unified_diff(before.decode("utf-8").splitlines(True),
            after.decode("utf-8").splitlines(True), fromfile="installed/" + relative.as_posix(),
            tofile="six_camera_viewer_src/" + relative.as_posix()))
assert set(changed) == allowed, changed
original = (baseline / "main.cpp").read_bytes()
candidate = (root / "main.cpp").read_bytes()

def section(data, start, end):
    return data[data.index(start):data.index(end, data.index(start))]

preserved = {
    "rgb565_raw_converter": section(original, b"static void rgb565ToRgb888Line", b"class CameraWorker") ==
                            section(candidate, b"static void rgb565ToRgb888Line", b"class CameraWorker"),
    "entire_inference_thread": section(original, b"class InferenceThread", b"class DetView :") ==
                              section(candidate, b"class InferenceThread", b"class DetView :"),
    "raw_vision_packet_conversion": section(original, b"                QImage pixels(IMG_W, IMG_H", b"                visionSink_(packet);") ==
                                    section(candidate, b"                QImage pixels(IMG_W, IMG_H", b"                visionSink_(packet);"),
}
assert all(preserved.values()), preserved
main = candidate.decode("utf-8")
assert "tdm::cameraSlotOffset" not in main and "tdm::cameraScratchOffset" not in main
assert main.count("::open(\"/dev/pango_pci_driver\"") == 1
assert "sixdma::scratchRange(op->offset_addr, op->total_length)" in main
assert "tdm::copyCameraPixels(output, pixels, FRAME_BYTES);" in main
assert "lock.unlock();" not in section(candidate, b"    int cameraRead(", b"    int thumbnailRead(").decode("utf-8")
original_viewer = root.parent / "thumbnail_viewer_src"
copied_viewer_hashes = {p.relative_to(original_viewer).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(original_viewer.rglob("*")) if p.is_file()}
for name in ("thumbnail_delivery.h", "thumbnail_delivery_selftest.cpp", "six_dma_layout.h"):
    content = (root / name).read_text(encoding="utf-8")
    differences.extend(difflib.unified_diff([], content.splitlines(True),
        fromfile="/dev/null", tofile="six_camera_viewer_src/" + name))
(root / "viewer_changes.diff").write_text("".join(differences), encoding="utf-8")
(root / "source_preservation.json").write_text(json.dumps({
    "baseline": str(baseline), "candidate": str(root), "changed_baseline_files": changed,
    "identical_baseline_files": sum(item["identical"] for item in records),
    "critical_sections_identical": preserved, "files": records,
    "protected_thumbnail_viewer_current_hashes": copied_viewer_hashes,
    "rx_reservation_static_checks": "all legacy camera offsets absent; central scratch range check; RAW copy under mutex; one open",
    "note": "Comparison reads installed sources only; generated test/build artifacts excluded from baseline list."
}, indent=2), encoding="utf-8")
print(json.dumps({"changed": changed, "identical": sum(item["identical"] for item in records),
                  "critical_sections_identical": preserved}, indent=2))
