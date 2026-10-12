Actual RKNN detection parity: PASS (exact tuple equality).

Completed run: `run_fb7fd910f875b750_1791049174034119400/`. Independent `audit_report.py` audit passed and retained `audit.json`. Both SHA-isolated harnesses compiled sequentially with `make -j1`; all four offscreen processes exited 0, loaded the actual four-output RKNN model successfully, and completed three requested frames with zero errors (12 total completions).

| Shared 640x480 scene | Baseline counts | Candidate counts | Class/score/x1/y1/x2/y2 comparison |
| --- | --- | --- | --- |
| candidate_cam1 | 0, 0, 0 | 0, 0, 0 | Exact empty agreement; alone provides no positive detection evidence |
| bright_baseline_cam1 | 2, 2, 2 | 2, 2, 2 | Exact equality of both positive detection tuples in all three repetitions |

Both bright-scene detections are class 1 (vehicle). Tuples `(class, score, x1, y1, x2, y2)` in the 640-square model input coordinate space:

```text
(1, 0.586596847, 203.950729, 250.829865, 671.067871, 562.769348)
(1, 0.377569348, 65.0481262, 193.934799, 522.816711, 592.861084)
```

These are the actual decoder outputs, including the first x2 above 640; the harness performs no box clipping or tuple rewriting. Nine significant digits preserve float32 values. Exact comparison passed; the configured fallback tolerances (score 1e-6, coordinates 1e-4 pixels) were unnecessary. Both harnesses were also exactly stable across their three repetitions on each scene.

The model path is `/root/npu/whiteboard_3cls/det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn`, pinned SHA256 `21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31`. Model, both scene files and both harness binaries passed remote SHA256 checks before and after execution.

Baseline harness binary SHA256: `5887fc2d32734b234e1005d020c781fa2f0f47f4d9ef607790fc1315025c8c03`.

Candidate harness binary SHA256: `0a20827c432a99aad1c38ce70904744f290349c649fa05ac6c9f97f55c22383b`.

Evidence includes manifest inventories, build receipts/logs, raw per-scene/per-harness RKNN logs, request pins, full frame tuples in `report.json`, and log hashes in `audit.json`. Report SHA256: `33b26954d8bc8096f588860cfe046c7fca95f4c833ae6a0aa2f3feb832870463`.

Scope: original controller padding versus frozen f3406080 candidate/build053 worker preprocessing, using two screenshot crops that retain display overlays. The tests used identical images, model and Qt offscreen environment. No production files, DMA device ownership or viewer state were changed. This validates detection parity for these scenes; three completions are not a sustained throughput measurement. The parent's later direct-completion build is outside this frozen-source audit.
