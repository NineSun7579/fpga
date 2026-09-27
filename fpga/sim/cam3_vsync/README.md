# cam3 VSYNC qualification evidence

Implemented 2026-09-26. No PDS, synthesis, place/route, programming, or board access was performed.

Production changes are restricted to `source/top.v`, `source/ov5640/ov5640_top.v`, and `source/ov5640/ov5640/ov5640.v`. `VSYNC_STABLE_CYCLES` defaults to 0 (wire bypass) and is passed through the wrapper. Only `cam3_ov5640_top` sets 64. The inline filter uses a 6-bit counter and one level register for N=64. It accepts the new level on the 64th consecutive opposite sample; a sample matching the accepted level clears the counter. It has no frame timer. Reset is the same `ov_rst_n` as capture, asynchronously forcing accepted VSYNC low and clearing the counter. A high input at reset release therefore produces one qualified rising transition after 64 samples. This is not a guarantee that the first observed frame is complete; capture retains its original WAIT_FRAME=10 startup behavior.

The raw diagnostic shift register/counter still samples `cam_vsync` after wrapper IODELAY and before qualification. Existing HREF/data connections and their IODELAY settings are unchanged. The patch script was created with patch, then used Python bytes replacement after writing `.bak_cam3_vsync_*` files; comparison confirmed the original non-ASCII byte sequence was preserved for all three RTL files. Existing files contain mixed newline styles; only inserted lines adopt the file's detected newline style.

Backups:

- `source/ov5640/ov5640/ov5640.v.bak_cam3_vsync_20260926_200532`
- `source/ov5640/ov5640_top.v.bak_cam3_vsync_20260926_200705`
- `source/top.v.bak_cam3_vsync_20260926_200705`

Run from the project root:

```powershell
python sim/cam3_vsync/run.py
python sim/cam3_vsync/check_top_compile.py
```

`run.py` extracts the actual marked production filter byte-for-byte into a test wrapper, compiles it with the actual unmodified `cmos_capture.v`, and checks static production wiring. No manually copied filter model is used. It also compiles the complete production `ov5640.v` and `ov5640_top.v` (compile only, not full hierarchy elaboration). Production ov5640 SHA256 at verification: `18a4eb6d44ec4b97965879169ccfd861ee5828464e7e0796e9821f5d42ce722e`.

Results in `results.log` and `compile_camera.log`:

- Narrow positive and negative sampled pulses: every width 1 through 63 rejected.
- Threshold boundary: no output change after 63 samples; change at 64.
- Continuous high and low for 10000 cycles: no periodic or duplicate edges.
- Reset during qualification clears history; reset from accepted high forces low.
- N=0 follows the input combinationally, including during reset; N=1 and N=3 exercise small/non-power-of-two widths and restart behavior.
- Eleven legal VSYNC pulses open the real capture's startup gate.
- 640x480 RGB565 payload, 1896 PCLK/line, 31-sample positive glitch on each active line: exactly 307200 pixel words, zero extra filtered frame edges, and HREF/valid/data equal the bypass reference on every checked clock. A subsequent legal frame pulse produces exactly one new capture frame marker.
- Final message: `PASS cam3 VSYNC: widths 1..63 both polarities, exact 64, reset, bypass, N=1/3, idle 10000 cycles, capture words=307200 raw_rises=622`.
- Camera RTL compilation: 0 errors, 0 warnings. Simulation: 0 errors, one environment warning concerning disabled optimization (`vsim-8891`).

Standalone top compilation using `vlog +define+USE_OV5640` fails with 103 existing diagnostics (including references preceding declarations and duplicate declarations). `check_top_compile.py` compiles the pre-edit backup and current top and confirms identical ordered diagnostic messages after removing file/line prefixes. Logs: `compile_top_baseline.log`, `compile_top_current.log`. No claim of complete top elaboration or implementation success is made.

Timing rationale and limits:

- Existing cam3 parameters are HTS=1896, VTS=984, active 640x480. Configuration writes HTS/VTS through registers 0x380c..0x380f. At measured 84 MHz, 64 PCLK is 0.7619 us; interpreting HTS in these clocks gives 22.571 us/line and 22.210 ms/frame (45.02 Hz), consistent with healthy camera frame rates. The nominal 504 non-active lines imply about 11.376 ms aggregate vertical blanking under that interpretation.
- Aggregate blanking does not establish the actual VSYNC pulse width or the minimum interval from a VSYNC edge to active HREF. The board waveform/specification for that precise mode was not available. Both accepted edges are delayed. Relative to the bypass capture pipeline, the same source edge is seen 64 clocks later when it first reaches a sampling edge (the filter output updates on sample 64 and capture consumes it on the next edge). Real accepted pulses must last at least 64 sampled clocks, and relevant edge-to-data margin must exceed this added latency plus existing downstream requirements. Noise near a legitimate edge can extend qualification delay further.
- The test supplies clean blanking of 128 samples per VSYNC level before active data; it demonstrates a complete synthetic frame under that explicit assumption, not that board frames are now complete.
- Glitches spanning 64 or more samples pass. Missing VSYNC, persistent stuck level, alternating noise preventing a stable run, HREF/data corruption, metastability, incorrect IODELAY phase, power/signal-integrity faults, and DDR/DMA defects are not repaired by this filter. Raw VSYNC counts may remain high by design.
- No measured pulse-width distribution is available. Abnormal edge counts suggest an input/sampling problem but do not establish the root cause. This is a scoped short-pulse mitigation, not proof of a root-cause fix or elimination of DMA zero filling.
