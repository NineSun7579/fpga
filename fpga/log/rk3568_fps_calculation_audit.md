# RK3568 FPS calculation audit

Checked currently running PID17531 and candidate main.cpp against local
project/host/camview/main.cpp. Both SHA256:
02c1588f8e7bb45de2ed8492e0affcbc9d221eb2ac40c1685643a2fee9d73535.
Live evidence saved in rk3568_fps_calculation_audit.txt.

## Findings

- cameraRead lines157-181 rejects unchanged/older tags and verifies the
  adjacent commit tag after reading614416bytes. Worker counters increment
  only on successful full-frame reads. delivered_fps is complete new frames
  divided by monotonic elapsed time. Current CAM5/6~40.4fps is supported.
- sequence_fps measures committed tag advancement; it can exceed delivered
  fps when the host skips frames. It cannot alone establish full host capture.
- camview_fps at lines398-401 counts producer submissions. Qt may coalesce
  updates; its~60fps does not measure GPU rendering/screen scanout.
- uploaded_fps and present camera at lines659-702 count texture uploads in
  paintGL. Changed QByteArray storage marks each camera texture dirty.
  These measure new-image uploads (~20fps), not physical scanout completion.
  The HUD uses these counters, not the worker capture counters.
- fpsTimer and auditTimer start on the first counted frame, so the initial
  sample includes an event at time zero: approximately one excess frame
  per window (up to~2fps for0.5s,~0.2fps for5s). Subsequent windows do not
  have this startup-count issue. Previous acceptance omitted startup samples.
- Worker stats refresh only on successful frames; upload stats refresh only
  on uploads. If a stream stops or display pauses, old rates can remain
  visible instead of dropping to0. This is a stale reporting issue.
- HUD cache key lines720-724 rounds rates to0 decimals while the text displays
  1 decimal. A20.04->19.81 change may leave old decimal text until another
  cache-key field changes. This affects displayed precision, not counters.
- transferNs includes tag reads, lock-held transfer and CPU copy; dma_ms is
  not isolated hardware DMA duration. This is a diagnostic naming limitation.

Current live capture windows CAM5:40.392/40.462fps; CAM6:40.335/40.392fps;
unstable0. Upload windows~20.0fps and producer submission~60fps coexist
because they measure different pipeline stages.

Conclusion: no evidence that CAM5/6 capture40fps was caused by double counting.
Reporting labels, startup samples, stale values and HUD cache precision need
correction. This audit did not modify or restart the running viewer or FPGA.
