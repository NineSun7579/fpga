# PLL56 counter-control experiment and exact capture-build diagnosis

## Terminal result: counter mapping rejected

`build_counter_bwnmjek8` finished **failed at 2026-10-04 20:24:01**, after
17m00s. Compile, synthesis and device mapping completed. The counter mapping
gate rejected the candidate before routing, final STA or bitgen.
All 32 inspected counter bits retained `GTP_DFF_CE` with dynamic `CE=N11`;
N11 implements `frame || (s_valid && full)`, not a constant enable. Inspection
of all four specialized counter modules confirms the same dynamic CE on all
128 physical-design counter register declarations. Thus the documented
attribute did not accomplish the intended mapping in this flow. The compile
log recognizes it and converts its name to `PAP_MIN_CONTROLSET_SIZE`; the
attribute was not merely misspelled or rejected as unknown.

No routed timing improvement, new STA result or bitstream exists for this
experiment. The lock was released. No additional build has been started.
The simulation passed functional equivalence; the mapping hypothesis failed.
The exact vendor-flow reason for retaining CE is not established by these
logs. It must be investigated before another control-set experiment; changing
seeds cannot establish that the requested CE removal happened.

`build_capture_538dxoxa` failed final timing verification at 2026-10-04
19:51:20 after 35m26s. All 126 summary rows were parsed and the report hashes
were rechecked against the STA bytes. No bitstream was generated.

| Build | Slow setup failing endpoints | WNS ns | TNS ns |
| --- | ---: | ---: | ---: |
| seed1 `build_aai6kbmf` DDR | 5 | -0.086 | -0.378 |
| seed2 `build_mfwcoqj3` DDR | 7 | -0.195 | -0.855 |
| capture `build_capture_538dxoxa` CAM3 PCLK | 6 | -0.785 | -2.484 |
| capture `build_capture_538dxoxa` DDR | 36 | -0.642 | -11.280 |

All hold/recovery/removal/pulse-width rows pass. Worst slow/fast hold slacks
are +0.247/+0.171 ns for seed1, +0.242/+0.171 ns for seed2, and
+0.108/+0.163 ns for capture. Hold TNS and failing endpoints are zero.
The capture build passes exact 112-pin equality, dedicated PHY equality and
all 32 attributable read-before-write motion banks. Those gates do not prove
timing closure or measured 40/30 FPS acceptance.

The seed1 failures are CAM4 `vs_q/CLK` to `motion_record[136,165,166,202]/CE`
at -0.086 ns, and `[171]/CE` at -0.034 ns, on `ddrphy_sysclk`. Its five-level
cone is `rise -> push -> overflow -> N77 -> N368`, with 0.766 ns logic and
6.372 ns route delay. N368 has fanout 262 and 2.354 ns route delay.
Seed2 has four CAM2 record CEs at -0.195 ns each (TNS -0.780), launched from
merged `diag_vs_q`, plus CAM5 `dbg_fault_snapshot[18,20,22]/CE` at -0.025 ns
each (TNS -0.075), launched from `u_fifo5/rbin[3]`, all on `ddrphy_sysclk`.

The capture rewrite survives synthesis: all four adapter variants retain
record CE pins, now driven by `record_capture`. The CE cone bypasses `push`
and `overflow`; the `vs_q -> rise -> LUT5 -> record_capture` path is three
LUT levels. The Z5 LUT output is shared with existing event-control logic;
this is ordinary combinational packing, not restoration of the original
five-level predicate. Exact INITs, ports and netlist hashes are preserved in
`all_adapter_mapping_cones.json`. No motion_record endpoint is violated in
the capture report. A positive numerical record margin is not claimed:
the production report lists violated paths and per-clock worst paths, not
the best available margin of every individual passing record endpoint.

The capture failures comprise three independent families:

| Family | Failing endpoints | WNS ns | TNS ns |
| --- | ---: | ---: | ---: |
| CAM3 `src_drop` CEs | 6 | -0.785 | -2.484 |
| CAM2 detector work-state CEs | 22 | -0.642 | -7.212 |
| CAM4 DDR diagnostics/pixel controls | 14 | -0.528 | -4.068 |

Worst CAM3 endpoint is
`cam3_ov5640_top/ov5640/ov5640_cdc/src_drop[31]/opit_0_inv_AQ_perm/CE`,
launched by falling-edge `cmos_frame_vsync_r/opit_0_inv/CLK`, captured on the
next rising `cmos3_pclk` edge. Period remains 17.857 ns (half-cycle 8.9285 ns).
Clock skew is -1.828 ns. It has nine logic levels: two LUTs followed by seven
CECO/CECI hops of 0.136 ns each; logic is 1.559 ns and route 6.049 ns.
The N18 net has fanout49 and 3.858 ns route delay. Other failing bits are
[28,24,16,12,8]. This is a real synchronous half-cycle path.

Worst DDR endpoint is CAM2 detector `max_x_work[0]/CE`, launched by
`update_pending/CLK`, skew -0.086 ns, slack -0.642 ns. A 398-fanout enable
and mark-block reduction affect bbox and statistics. CAM4 failures instead
launch from `ddr3/u_ddrphy_top/ddrphy_dfi/dfi_init_complete/CLK`, through
`ddr_init_done`/reset/admission logic, to diagnostic CEs, pixel_count RS pins,
and `dbg_fault_snapshot[28]/CE`. No detector, DDR reset, snapshot or fault
counter logic is changed by the counter experiment.

The source diagnostic CDC is a held 96-bit `{sequence, drop, input}` bus:
source snapshots change only on the source frame edge, data passes through
two destination stages, and a three-stage toggle notifies publication. It
is not a live asynchronous binary counter read. The extracted counter keeps
the exact original source edge, asynchronous source reset, modulo32-bit
increment, frame-edge load of zero/one and old-value snapshot semantics.
No receiving CDC stage, reset or notification changes. The DDR fault snapshot
is separately updated on `axi_clk` from the same fault/abort priority branch.
It is also preserved, including all acceptance counters.

The focused candidate extracts only src_drop into
`pll56_source_drop_counter`, with documented module-scoped
`syn_reduce_controlset_size=64` and `syn_useioff=0` (ADS Synthesis User Guide
section5.17, PDF pages96-100). The vendor documents moving synchronous control
pins to D below this threshold. This avoids relying on a new clock phase or
register duplication. A synthesis gate requires actual counter FF evidence
with no CE pins before routing; the attribute alone is not accepted as proof.

ModelSim integration equivalence passed 327708 camera edges and 768005 video
edges, comparing all source state, held snapshots, toggle/data stages,
diagnostic outputs and video interface outputs. It covered a full307200-pixel
offered frame with gaps/drop pressure, coincident frame/valid/full, 32-bit
wrap, asynchronous source reset, independent destination reset and recovery,
short/restarted frames and sustained VSYNC. The FIFO is an identical controlled
interface model in both instances; unchanged production FIFO behavior is not
revalidated by this test. The passing receipt and log hashes are under
`simulation/` and the candidate hash is
`ba860f27f8f5a41f702fbb3ace2ada605a17420ad61300dad756498b52400c59`.

One isolated full-flow build started at **2026-10-04 20:07:01** as
**`build_counter_bwnmjek8`**, after PDS process-idle and absent shared-lock
checks. Compile stage started20:07:04 with PDS PID74152. The exclusive shared
`per_camera_fps/fpga/build.lock` is owned throughout the flow. Placement seed
is unchanged at1. Its694-file input inventory differs from the capture build
only at `source/ov5640/ov5640/ov5640_cdc.v`; `input_diff_proof.json` in the build
records exact hashes. PLL56/17.857 clocks, constraints/exceptions, full six
video/inference paths, detector32 banks and fault-recovery policy are preserved.
Every original strict pin/PHY/resource/all126 STA gate remains required before
bitgen. The known independent DDR failures may remain; no closure prediction
is made. Stage/terminal receipts and error/finished timestamps are written by
the supervisor; the `build_*` path is picked up by the existing live monitor.

The first launcher attempt failed a CRLF marker assertion before any vendor
launch; its failure receipt is retained as `launch_attempt_1_failure.json`.
The script generation was corrected to normalize script line endings, with
RTL edits remaining byte-oriented and preserving GBK comment bytes.

No SSH, board programming, Flash, deployment or healthy-board changes occurred.
The build is now terminally failed at the mapping gate, as recorded above.
Parent should use the build and launch receipts for exact stage timestamps.
