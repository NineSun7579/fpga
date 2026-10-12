# Capture / CDC / FIR / DDR boundary integration

## Scope

Local ModelSim SE-64 10.6e simulation, isolated in this directory. No remote access,
programming, PDS implementation, or production/frozen source edits. The earlier
`source_counter_diagnosis/REPORT.md` and `rtl_diagnosis/DDR_GATE_REPORT.md` were read
first; this test extends them by joining their previously separate boundaries.

Run from workspace root:

```powershell
python project/fpga_v8_migration/board_v7/capture_boundary_integration/run.py
python project/fpga_v8_migration/board_v7/capture_boundary_integration/summarize.py
```

`run.py --smoke` selects the minimal 32x4 failure/control and three consecutive
normal publications. `run.py --repro` selects the full-size positive-blank
failure/control pair. Their build directories and transcripts have
`_smoke`/`_repro` suffixes, so they do not overwrite the complete sweep evidence.

The exact capture instance, unreset negedge PCLK register block, and TC04 CDC
instance are extracted byte-for-byte from frozen `rtl/ov5640_tc03_binding.v`
into `frozen_capture_chain.v`. Production settings are DATA_WIDTH=16,
DELAY=2, WAIT_FRAME=10, VSYNC_STABLE_CYCLES=0. Ten suppressed markers precede
the eleventh, admitted marker. No DUT counters or FIFO pointers are forced.

Downstream wiring follows frozen `rtl/parent_tc04_c40cee500c37.v`:
MEDIAN_EN=0 wire bypass -> actual `cam_fir3` -> KF_EN=0 wire bypass -> actual
`ov5640_ddr_tc04`, `ov5640_ddr_w_en`, packer and write controller. Hsync has
the same wire connection as the parent. I2C, IO delay and disabled image
filters are outside this digital timing experiment. Capture/counter resets
are released together after clocked reset; different I2C reset-release
epochs and arbitrary mid-line resets are not claimed covered.

## FIFO and retirement model

**No FIFO stub or custom FIFO behavioral replacement is used.** Compiled directly:

- Frozen `inputs/ipcore/ov5640_cdc_fifo` wrapper and generated RTL (1024x16,
  asynchronous FIFO, OUTPUT_REG=0), with PDS `GTP_DRM18K_E1.v`.
- Frozen `ov5640_ddr_fifo_DRM` wrapper/generated RTL with PDS
  `GTP_DRM36K_E1.v`.
- Frozen `ov5640_ddr_fifo` generated distributed FIFO RTL.
- PDS `GTP_GRS.v` with GRS_N held high; explicit local resets are asserted
  for 30 video cycles before each case.

PDS primitives come from
`C:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation`.
These are vendor functional simulation models, not place/route or physical
metastability simulation. Their historical `Fake module` header does not mean
they are empty stubs: the compiled files implement RAM writes/reads/output
registers, and every CDC output word is checked against the input queue for
value and order. Every DDR AXI beat must have known payload and command credit.

The DMA endpoint is an explicit **testbench transaction-completion model**:
command/data ready are high, command length establishes beat credit, and
`dma_done` follows the final accepted beat by several video clocks. A frame
and its separate tag command both retire through the actual controller;
`publish` is counted only at that controller's `WAIT_TAG_DONE` completion.
This checks the RTL publication decision, not a DDR controller, AXI B-channel
error response, memory contents, or PCIe host. A short transaction receives
neither invented missing beats nor a fabricated completion. dma_abort remains
low, so fault recovery is outside scope.

## Checks and stimulus interpretation

Each case checks input bytes, capture valid total, source snapshot/drop,
FIFO output count/data/order, FIR count, and absence of DDR overflow. Normal
cases also require complete CDC/DDR windows, exact admitted pixels and one
publish with zero shorts. The final full-size boundary reproduction and the
consecutive-window conservation experiment have explicit outcome assertions.
Per-case measurements are retained in `results.csv`; raw evidence is in
`modelsim/simulation.log` and `modelsim/compile.log`. `source_hashes.txt` is
checked before/after execution, covering frozen RTL/IP, the parent/binding,
and vendor primitives.

`tail` counts whole PCLK cycles with HREF=0, VSYNC=0 after the last active
byte before the next VSYNC; `head` counts such cycles after initial VSYNC.
`pulse` counts VSYNC-high PCLK cycles. Data changes just after falling PCLK
and is sampled on rising PCLK. All lines have exactly 2*W bytes. All stimuli
keep raw HREF and VSYNC disjoint; **disjoint alone does not establish an
OV5640 sensor-legal minimum blank/pulse width**. Zero/one-clock boundaries
and one-clock VSYNC are contract stress tests, not claims about the board's
configured waveform. Generous line/frame blank controls are distinguished
from these compressed boundaries. PCLK phase and video phase are restarted
deterministically for each case, with picosecond simulator precision.
Requested half-periods are rounded to that precision (e.g. nominal
11.905ns PCLK becomes two 5.953ns half-periods).

## Results

The complete sweep actually ran on **2026-10-06, 15:10:57–15:16:20**:
**649 cases, zero assertion errors**, including 15 full-size cases,
150 required-normal controls (all passed), and 134 intentionally stressed
short cases. Thirty narrow-marker cases never admitted the frame. The
consecutive-window check also passed. Compilation: 0 errors / 0 warnings.
Simulation: 0 errors / 15 warnings, from the inherited `-novopt` setting,
unused TB diagnostic outputs and two unused water-level outputs in the
unchanged vendor distributed FIFO wrapper; no unconnected required input.
The transcript also prints the simulator's `onerror` macro-use notice.

The separate `--smoke` run passes three cases and both continuous-frame
checks described below, with zero assertion errors. No failing assertion
was waived: an initial expectation of three publications with a one-clock
tail was corrected only after explicitly tracing the busy admission gate
and adding the wide-blank control.
The standalone `--repro` pair was also actually rerun, finishing at 15:19:46
in 36 seconds: `INTEGRATION_DONE cases=2 errors=0`. Its independent transcript
is `modelsim_repro/simulation_repro.log`. A final SHA256 recheck after all
three run modes confirmed every hashed frozen/vendor input unchanged.

### Full-size failure with real vendor FIFOs

Every row below sends 1280 bytes x 480 lines and receives **307200 source
valids / source snapshot 307200 / source drop 0 / total CDC output 307200**.
Line blank is 616 PCLK cycles. The complete CSV contains all individual cases.

| cam/video periods (ns) | tail blank (PCLK) | CDC/DDR input window | DDR admitted | AXI frame beats | publish | short |
|---|---:|---:|---:|---:|---:|---:|
| 11.905 / 10 | 2000 | 307200 | 307200 | 38400 | 1 | 0 |
| 15.625 / 10 | 2000 | 307200 | 307200 | 38400 | 1 | 0 |
| 12 / 30 | 2000 | 307200 | 307200 | 38400 | 1 | 0 |
| 12 / 10 | 0 | 307199 | 307199 | 38399 | 0 | 1 |
| 12 / 10 | 1 | 307200 | 307200 | 38400 | 1 | 0 |
| 12 / 16 | 1 | 307199 | 307199 | 38399 | 0 | 1 |
| 12 / 16 | 3 | 307200 | 307200 | 38400 | 1 | 0 |
| 12 / 30 | 1 | 307070 | 307070 | 38383 | 0 | 1 |
| 11.905 / 10 | 955584 | 307200 | 307200 | 38400 | 1 | 0 |

At 12/10 ns, phase 0, zero tail blank, the final real FIFO output and
synchronized VSYNC are sampled on the same video edge. The actual FIR delays
both together by one edge; the actual DDR `!s_vsync` gate rejects the final
real pixel. Adding one raw PCLK blank produces a 10ns lead for that pixel
and successful publication. This joins the earlier DDR overlap result to
an actual capture/CDC FIFO stimulus; overlap is no longer injected directly
at DDR input.

Case 646 is the positive-blank, full-size minimal pair used by `--repro`:
cam=12ns, video=16ns, phase=0, line blank=616, head=32, pulse=16,
tail=1. Input=614400 bytes, source=307200, drop=0. At video sample
172763216ns, CDC valid and CDC VSYNC are both 1 on the last real pixel.
At 172763232ns, FIR valid/VSYNC and DDR raw_sof are all 1,
`pixel_count=307199`, and admitted=0. Case 647 changes only tail to 3;
the last pixel precedes the marker by 32ns and publication succeeds.
The separate longest-blank case uses 504*1896=955584 PCLKs, corresponding
to a deliberately generous 504 blank-line budget; this does not claim
to decode the live sensor's exact HTS units or front/back porch split.

At 12/30 ns and one tail blank, the video clock is slower than the peak
pixel production rate (one pixel per two PCLKs). Horizontal blank drains
each line's backlog, so source drops are zero and the transfer is sustainable
on average. The final line's backlog has not drained before VSYNC: the
marker leads the last output by 3870ns. Seven tail pixels meet VSYNC high;
123 more meet the already-bad capture. This is a larger manifestation of
the same independent-marker ordering problem, not counter arithmetic.

### Why the RTL permits this

The frozen CDC synchronizes VSYNC with two video registers independently
of its data FIFO. The actual vendor FIFO controller synchronizes the write
pointer with two read-clock registers, registers `asyn_rempty`, then performs
the synchronous memory read; `ov5640_cdc_tc04` also registers `rd_en` into
`video_valid`. Existing FIFO backlog further increases pixel latency, but
does not delay VSYNC. The frame marker therefore has no FIFO-order guarantee.
The FIR preserves this relative timing. DDR intentionally excludes pixels
during VSYNC and declares a still-incomplete previous frame short.

These tests establish a reproducible **RTL boundary-contract failure under
insufficient trailing blank**. They do not establish that the live sensor
has that blank or clock ratio. All generous-blank controls completed normally.
In particular, source snapshots remain 307200 in the failing cases: this
mechanism can explain a short CDC/post-filter window and DDR short, but
**cannot by itself explain the reported source-domain 307199/198/193**.
No hardware/cable/delay root cause is inferred.

### Blank and startup sweeps

Small geometry is 32x4 pixels, PCLK=12ns, line blank=64 cycles,
initial pulse=16 cycles, head=32 cycles. Four deterministic phases are
0, 2.1, 4.2, 6.3ns. `tail_delta_ns` in CSV is the final video SOF sample
time minus the last real CDC valid sample time; zero and negative values
identify an overlapping/overtaking marker.

| video period (ns) | smallest trailing PCLK blank with all four phases publishing |
|---:|---:|
| 5 | 0 |
| 10 | 1 |
| 16 | 3 |
| 23 | 5 |
| 24 | 5 |
| 30 | 21 |

These are **measured thresholds for this geometry and sampled phases**, not
universal timing margins. At 30ns, backlog and geometry matter; the full-size
last line needs much more drain time than the 32-pixel line. Normal controls
use 128 trailing PCLKs in the small geometry and 2000 in the full geometry,
and pass even for video slower than the instantaneous pixel rate.

Startup uses 120 cases with raw pulse=1 PCLK and head=0..4, plus 120 cases
with pulse=3 PCLK and head=0..4, across the six video periods/four phases.
In the one-clock-pulse set, 30 cases receive no initial video SOF: accepted=0,
publish=0, short=0, while source and FIFO totals remain complete. `sof_count=1`
means only the later wide closing marker was received; `first_gap=-1` means
no SOF had arrived before the first real output. Thus zero short counters
do not prove capture ever opened. The 90 cases whose initial marker is
received accept all 128 pixels. All 120 three-clock-pulse cases receive
both markers and publish complete frames. No partial 127/126-pixel startup
admission was found.

For received markers, the first CDC real valid is at least **three video
edges after SOF** in this sweep. FIR adds the same cycle to both, so the
actual DDR start gate is already ready. The real initially-empty vendor FIFO
therefore supplies the startup margin absent from the earlier direct-DDR
test. This is not a guarantee for reset/backlog configurations not simulated.

### Consecutive windows and retirement

With three complete 128-pixel input frames and compressed trailing blank,
the actual source snapshots are `128,128,128,0`; CDC output windows are
`127,128,128,1` including the final empty flush interval. Both sums are 384,
and all 384 FIFO values match in order. The displaced final pixel is
conserved by the FIFO/windows even though DDR rejects an overlapping tail.
The short DDR transaction is deliberately not force-retired in this test.

`modelsim_smoke/simulation_smoke.log` adds actual continuous retirement:

- With the first frame's tail=1 at cam/video=12/10ns, its last pixel is safe,
  but the next raw_sof trace shows `engine_busy=1`, `capture_complete=1`,
  `published=0`. The next frame marker is discarded before the frame/tag
  transaction retires. Across three complete source frames, source/output
  totals are 384, accepted=256, published=2, short=0. This is a whole-frame
  admission skip, not a partial first-pixel loss. Busy markers are not replayed.
- With tail=128 from the first frame onward, every next raw_sof sees
  `engine_busy=0`; three continuous frames produce source/output/accepted=384,
  published=3, short=0, with 128 in each source/CDC/DDR window.

Therefore enough blank to preserve the FIFO's final pixel is **not alone
enough to admit the next frame**: the frame/tag transaction must also retire
before that SOF. Its margin depends on the downstream DMA completion latency;
the observed skip is under the stated testbench endpoint model. Generous
blank satisfies both conditions in this integration. Neither boundary
mechanism reduces source-domain valid totals or source snapshots.
