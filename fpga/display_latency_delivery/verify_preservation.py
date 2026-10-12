"""Verify the isolated candidate against production; never writes production."""
from pathlib import Path
import difflib
import hashlib
import json

root = Path(__file__).resolve().parent
baseline = root.parent / "detview_display_fix" / "src"
candidate = root / "src"
sha = lambda data: hashlib.sha256(data).hexdigest()
original = (baseline / "main.cpp").read_bytes()
updated = (candidate / "main.cpp").read_bytes()

def section(data, start, end):
    begin = data.index(start.encode())
    return data[begin:data.index(end.encode(), begin)]

regions = [
    ("InferenceThread (all YOLO preprocess, inference, decoders and NMS)",
     "class InferenceThread :", "class DetView :"),
    ("CameraWorker analytics submission (pixels, frame ID, camera, tag, generation)",
     "            if (visionSink_ &&", "            QMutexLocker lock(&frames_->mutex);\n            /*"),
    ("HDMI analytics submission", "            if (hdmiFull && m_visionSink",
     "            if (!ready)"),
    ("Video decode and analytics publication", "    void runVideo() {",
     "    void publishDisplay(DisplayFrame frame)"),
    ("RGB565 analytics conversion", "static void rgb565ToRgb888Line",
     "class CameraWorker :"),
]
results = []
for name, start, end in regions:
    old, new = section(original, start, end), section(updated, start, end)
    results.append(dict(region=name, baseline_sha256=sha(old), candidate_sha256=sha(new), identical=old == new))

files = []
for path in sorted(baseline.rglob("*")):
    if not path.is_file():
        continue
    relative = path.relative_to(baseline)
    other = candidate / relative
    old = path.read_bytes()
    new = other.read_bytes() if other.exists() else b""
    files.append(dict(path=relative.as_posix(), baseline_sha256=sha(old), candidate_sha256=sha(new), identical=old == new))
unexpected = [item["path"] for item in files if not item["identical"] and item["path"] != "main.cpp"]
report = dict(baseline=str(baseline), candidate=str(candidate), protected_regions=results,
              files=files, unexpected_changes=unexpected,
              scope="Source preservation only; target compilation and measured latency require board verification.")
(root / "preservation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
patch = "".join(difflib.unified_diff(original.decode("utf-8").splitlines(True),
                                   updated.decode("utf-8").splitlines(True),
                                   fromfile="a/src/main.cpp", tofile="b/src/main.cpp"))
(root / "latency_candidate.patch").write_text(patch, encoding="utf-8", newline="\n")
assert not unexpected, unexpected
assert all(item["identical"] for item in results), results
print("PRESERVATION_PASS: all protected YOLO regions byte-identical; only src/main.cpp changed")
print("Candidate main.cpp SHA256:", sha(updated))
