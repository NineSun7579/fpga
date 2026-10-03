# Camera startup and recovery regression

Run `python project/sim/six_recovery/run.py` from the workspace root.
ModelSim defaults to `C:/modeltech64_10.6e/win64`; override with `MODELSIM_BIN`.
All generated includes, isolated libraries, scripts, and logs stay in this directory.
The runner rejects simulator errors/fatal assertions and missing PASS markers.

The startup bench compiles a byte-extracted reset block from the current
`source/top.v`, without an external reset or forced internal state. Four real
`ov5640` instances use their production 25 MHz clock parameters, power-on delays,
264-entry initializer, SCCB master, passthrough mux, and capture module. A slave
pin model acknowledges commands and returns sensor ID `0x5640`. Only downstream
pixel CDC is replaced with an idle sink. Assertions check reset release exactly
on edge 65536, saturation, 264 starts and 264 real completions per camera, the
two ID reads, all eight commands above index 255, and no extra commands.

The top audit checks all four `clk_50m_rst_n` connections and cam5/cam6 completion,
abort request, abort retirement, and available-data credit connections. This is
an isolated control-path simulation plus a source wiring audit, not a simulation
of the full FPGA top, SFP receiver, DDR controller, or shared write arbiter.

Existing benches are compiled directly from `../dma_timeout_repro`, without
editing them. They check full-frame pixel/tag integrity and recovery after short
frames, missing data, FIFO overflow, payload/tag BRESP errors, retained bank
requests, and AW/W/B backpressure. Credit recovery uses `WAIT_FOR_DATA(1)`, matching
cam5/cam6 in top. Vendor recovery uses the actual Pango FIFO models and generated IP.

Verified results with ModelSim 10.6e:

| Case | Result |
| --- | --- |
| Startup | Four cameras, 264 starts/completions each, ID 5640, 9788 SCL rising edges each; no external reset |
| Frame recovery, behavioral FIFO | 10 successful frames, 7 aborts, AW/B 61/61 |
| Frame recovery, vendor FIFO | 10 successful frames, 7 aborts, AW/B 1425/1425 |
| Credit-gated recovery | 10 successful frames, 7 aborts, AW/B 58/58 |
| Top wiring audit | All required reset/completion/abort/credit connections pass |

Detailed evidence is in `results.log`, the per-case `.log` files, and
`top_audit.log`. The runner checks that `top.v` remains byte-identical during its
run. No production files are written.
