"""Prepare retained PNGs without inference, requiring historical RGB hashes."""
import hashlib
import json
import math
from pathlib import Path
import sys
import cv2
import numpy as np

stage = Path(sys.argv[1]).resolve()
manifest = json.loads((stage / "input_expectations.json").read_text())
cv2.setNumThreads(1)
rows = []
for row in manifest["inputs"]:
    png = Path(row["board_path"])
    png_sha = hashlib.sha256(png.read_bytes()).hexdigest()
    if png_sha != row["png_sha256"]:
        raise RuntimeError("retained PNG hash changed: " + str(png))
    bgr = cv2.imread(str(png), cv2.IMREAD_COLOR)
    scale = min(640.0 / bgr.shape[1], 640.0 / bgr.shape[0])
    width = math.floor(bgr.shape[1] * scale + 0.5)
    height = math.floor(bgr.shape[0] * scale + 0.5)
    resized = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    padded = np.full((640, 640, 3), 114, dtype=np.uint8)
    x, y = (640 - width) // 2, (640 - height) // 2
    padded[y:y + height, x:x + width] = rgb
    data = padded.tobytes()
    actual = hashlib.sha256(data).hexdigest()
    if len(data) != 1228800 or actual != row["rgb_sha256"]:
        raise RuntimeError("prepared RGB differs from retained pipeline: " + str(png))
    prepared = stage / ("frame_%02d.rgb" % (len(rows) + 1))
    prepared.write_bytes(data)
    rows.append(dict(row, prepared_path=str(prepared), actual_rgb_sha256=actual, bytes=len(data)))
if len(rows) != 30:
    raise RuntimeError("expected exactly 30 retained inputs")
(stage / "prepared_inputs.json").write_text(json.dumps({"inputs": rows, "opencv_version": cv2.__version__,
    "preparation": "same retained RGB640 bilinear letterbox; all bytes verified by historical SHA256"}, indent=2) + "\n")
print("PREPARED_INPUTS_HASH_PASS", len(rows))
