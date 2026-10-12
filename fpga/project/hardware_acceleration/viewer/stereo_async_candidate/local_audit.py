#!/usr/bin/env python3
"""Byte audit + independent continuous-window validation. Writes only here."""
import datetime
import difflib
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parent
frozen = root.parent / "prepared/65a02d87142e090416db84bf/candidate/src"
source = root / "src"
receipt = root / "localchecksreceipt"
receipt.mkdir(exist_ok=True)
digest = lambda data: hashlib.sha256(data).hexdigest()
old = {p.relative_to(frozen).as_posix(): p.read_bytes() for p in frozen.rglob("*") if p.is_file()}
new = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob("*") if p.is_file()}
changed = sorted(name for name in old if name in new and old[name] != new[name])
added = sorted(set(new) - set(old))
missing = sorted(set(old) - set(new))
assert not missing, missing
assert changed == ["detview.pro", "vision_pipeline.cpp"], changed
untouched = sorted(name for name in old if old[name] == new[name])
for name in ("main.cpp", "hardware_inference.h", "native_adapter.h", "inference_preprocess.h", "vision_types.h",
             "template_tracker.cpp", "stereo_demo/stereo_depth.cpp", "stereo_demo/stereo_depth.h", "vision_pipeline_selftest.cpp"):
    assert name in untouched, name
diff = []
for name in changed + added:
    before = old.get(name, b"").decode("utf-8").splitlines(keepends=True)
    after = new[name].decode("utf-8").splitlines(keepends=True)
    diff.extend(difflib.unified_diff(before, after, fromfile=f"frozen/src/{name}" if name in old else "/dev/null",
                                     tofile=f"candidate/src/{name}"))
(receipt / "source.diff").write_text("".join(diff), encoding="utf-8")
windows = []
for line in (receipt / "metrics.stderr").read_text().splitlines():
    if not line.startswith("[stereo] window="):
        continue
    match = re.search(r"window=\[(\d+),(\d+)\) window_ms=5000 C(\d)/C(\d) pair_compute_ok=(\d+) pair_compute_failed=(\d+)", line)
    assert match, line
    start, end, left, right, success, failure = map(int, match.groups())
    assert end - start == 5000 and success > 0 and failure == 0, line
    windows.append(dict(start=start, end=end, pair=[left, right], success=success, failure=failure))
assert len(windows) == 4, windows
for pair in ([1, 2], [5, 6]):
    own = [w for w in windows if w["pair"] == pair]
    assert len(own) == 2 and own[0]["end"] == own[1]["start"], own
result = dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              frozen_source=str(frozen), changed_existing_files=changed, added_files=added,
              unchanged_files=untouched, missing_files=missing,
              file_hashes={name: dict(frozen=digest(old[name]) if name in old else None, candidate=digest(data))
                           for name, data in sorted(new.items())},
              continuous_five_second_windows=windows,
              scope="Local host tests only; no target build, RKNN execution, camera, GPU, SSH, PDS or board access")
(receipt / "source_and_metrics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"BYTE_AUDIT_PASS changed={changed} added={len(added)} unchanged={len(untouched)} missing=0")
print("CONTINUOUS_METRICS_PASS two adjacent five-second windows per configured pair, all compute failures zero")
