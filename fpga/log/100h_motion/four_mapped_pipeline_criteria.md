# CAM1–4 mapped pipeline review criteria

Prepared from frozen `project/motion_100h/run_20261003_212303/inputs/source/motion/{block_motion_detector,motion_stream_adapter}.v` and `project/tools/audit_motion_mapping.py`. Source-derived requirements only; no active dump read, audit execution, PDS launch, mapped equivalence finding, or gate acceptance.

Apply independently to these exact detector prefixes `D` (adapter prefix `A` = `D` without `/u_detector`):

| Camera | D |
|---|---|
| CAM1 | `ov5640_top/u_motion_tap/u_detector` |
| CAM2 | `cam2_ov5640_top/u_motion_tap/u_detector` |
| CAM3 | `cam3_ov5640_top/u_motion_tap/u_detector` |
| CAM4 | `cam4_ov5640_top/u_motion_tap/u_detector` |

Default geometry to corroborate per elaborated instance: WIDTH=640, HEIGHT=480, SAMPLE_STEP=4, SAMPLE_COLS=160, SAMPLE_ROWS=120, BLOCK_SAMPLES_X/Y=10, BLOCK_COLS=16, BLOCK_ROWS=12, TOTAL_PIXELS=307200, TOTAL_SAMPLES=19200, TOTAL_BLOCKS=192, PIXEL_THRESHOLD=16, BLOCK_THRESHOLD=8. The two RTL files establish defaults/parameter propagation; the helper's wrapper/top checks establish actual camera wiring when run later. Do not infer specialization solely from these defaults.

## Register inventory and reset

Widths below assume that geometry. All detector control/work/output registers reset asynchronously to **zero** on `!D.rst_n`; rising clock must resolve to `axi_clk`. Detector reset input is `A.rst_n && !A/overflow_reset`; the helper expects local-camera `A.rst_n=ddr_init_done` and reset net `D/N78 = !ddr_init_done || A/overflow_reset`. Verify actual routing/polarity. `history` and `history_q` have **no RTL reset or clear**.

| Exact detector names (relative to D) | Required logical bits |
|---|---:|
| `compare_pending`, `compare_enabled` | 1 each |
| `current_q[7:0]` | 8 |
| `block_q[7:0]` | 8 |
| `bx_q[3:0]`, `by_q[3:0]` | 4 each |
| `update_pending`, `changed_q` | 1 each |
| `select_q[191:0]` | **192 distinct decoded destinations** |
| `update_bx[3:0]`, `update_by[3:0]` | **4 each** |
| `active`, `reference_valid` | 1 each |
| `pixel_count[18:0]`, `x[9:0]`, `y[8:0]`, `sample_address[14:0]` | 19, 10, 9, 15 |
| `block_hits[i][3:0]`, i=0..191 | 192 × 4 = 768 |
| `bitmap_work[191:0]`, `blocks_work[7:0]`, `samples_work[14:0]` | 192, 8, 15 |
| `bbox_work_valid`, `min_x_work[3:0]`, `max_x_work[3:0]`, `min_y_work[3:0]`, `max_y_work[3:0]` | 1; 4 each |
| `end_pending`, `publish_pending`, `publish_comparison_valid`, `clear_after_publish` | 1 each |
| `result_strobe`, `result_valid`, `bbox_valid` | 1 each |
| `block_bitmap[191:0]`, `changed_blocks[7:0]`, `changed_samples[14:0]` | 192, 8, 15 |
| `bbox_min_x[3:0]`, `bbox_max_x[3:0]`, `bbox_min_y[3:0]`, `bbox_max_y[3:0]` | 4 each |
| `frame_sequence[31:0]` | 32; adapter leaves output unconnected, so mapped removal is expected |
| `history_q[7:0]`, `history[0:19199][7:0]` | 8; 19200 × 8, uninitialized by RTL |

Critical decision-register count is **202 logical bits**: 1 `update_pending` + 1 `changed_q` + 192 `select_q` + 4 `update_bx` + 4 `update_by`. Identify every bit index and reset/data route; packed cells are not bit counts. Any optimized/renamed representation requires explicit functional correspondence, not a silent count exemption.

Adapter registers also asynchronously reset to zero on `!A.rst_n`: `vs_q`, `acquired`, `head_started`, `active`, `end_pending`, `tail_seen`, `tail_bad`, `overflow_reset`, `error_pending`, `publish_error` (1 each); `wr_ptr[3:0]`, `rd_ptr[3:0]`; `queued[4:0]`; `marker_idle[2:0]`; `pixels[18:0]`; `source_sequence[31:0]`, `active_sequence[31:0]`, `publish_sequence[31:0]`, `overflow_count[31:0]`, `short_frame_count[31:0]`; `core_start`, `core_end`, `core_valid` (1 each), `core_rgb[15:0]`; `motion_record[319:0]`. Diagnostic counters may optimize away if unobserved. `events[0:15][17:0]` and `event_sequences[0:15][31:0]` have no reset.

## Exact next-state dependencies

Notation: RHS reads **pre-edge** values; `q+` is post-edge, with asynchronous reset taking priority. `frame_start=D.frame_start=A/core_start`, `frame_end=A/core_end`, `pixel_valid=A/core_valid`, `pixel_rgb565=A/core_rgb`. Equations below describe reset-deasserted behavior; all comparisons/divisions are unsigned as declared.

1. **Acceptance / RAM / metadata capture** (detector lines 54–85, 165–172):
   - `accept_pixel = active && pixel_valid && !frame_start && !frame_end && pixel_count < 307200`.
   - `accept_sample = accept_pixel && x%4==0 && y%4==0`.
   - `sample_bx=(x/4)/10`, `sample_by=(y/4)/10`, `sample_block=sample_by*16+sample_bx` (4, 4, 8 bits respectively).
   - `red={pixel_rgb565[15:11],pixel_rgb565[15:13]}`, `green={pixel_rgb565[10:5],pixel_rgb565[10:9]}`, `blue={pixel_rgb565[4:0],pixel_rgb565[4:2]}`; `luma_sum={2'b0,red}+{1'b0,green,1'b0}+{2'b0,blue}`, `luma=luma_sum[9:2]`.
   - RAM enable `D/N63 = D.rst_n && accept_sample` (camera expansion: `ddr_init_done && !A/overflow_reset && accept_sample`). Helper matches `ddr_init_done && accept_sample`; validate the missing reset factor via the acceptance cone: adapter `fire` excludes `overflow_reset`, and overflow flushing zeros the registered tuple. Do not assume that implication from names.
   - Under RAM enable: `history_q+ = old history[sample_address]`, `history[sample_address]+ = luma`. Otherwise hold; same address, READ_BEFORE_WRITE.
   - `compare_pending+ = !frame_start && accept_sample` (unconditional clocked assignment with later start override; no hold on an idle clock).
   - On `accept_sample`: `current_q+=luma`, `block_q+=sample_block`, `bx_q+=sample_bx`, `by_q+=sample_by`, `compare_enabled+=reference_valid`; otherwise all five hold. Required CE or equivalent feedback-mux function is **accept_sample**, including for `compare_enabled`.

2. **Registered decision / destination** (lines 95–104, 159–164, 200–201):
   - `difference = current_q>=history_q ? current_q-history_q : history_q-current_q` (8-bit absolute difference, not signed subtraction).
   - `changed_q+ = compare_enabled && difference>=16`. No `compare_pending`, `accept_sample`, or `frame_start` qualification in this D function; it refreshes every rising edge.
   - For **every i=0..191**, `select_q[i]+ = (block_q == i)`, a full 8-bit equality decode. No pending/valid enable. Inputs 192..255 decode to all zero; reset forces all zero even though decoding block_q=0 on a subsequent clock selects bit 0.
   - `update_bx[k]+ = bx_q[k]`, `update_by[k]+ = by_q[k]`, k=0..3, each unconditional; do not recalculate them from live `x/y` or `block_q`.
   - `update_pending+ = frame_start ? 0 : compare_pending`. Start overrides only the pending registers, not `changed_q`, `select_q`, or coordinates.

3. **Qualified local work update** (lines 102–105, 205–237):
   - `C = (frame_start && !end_pending) || (publish_pending && clear_after_publish)` is work-clear priority.
   - `U = !C && update_pending && changed_q`; `samples_work+=samples_work+1` iff U, else hold unless C clears it.
   - `mark_block[i] = update_pending && changed_q && select_q[i] && block_hits[i]==7`; `mark_any=OR(mark_block[191:0])`. These wires themselves do not include C; their work consumers do.
   - `block_hits[i]+ = C ? 0 : (U && select_q[i] && block_hits[i]<8 ? block_hits[i]+1 : block_hits[i])`. Four-bit counter saturates at 8, not wraps; no selected-counter read mux is required by the source.
   - `bitmap_work[i]+ = C ? 0 : (U && mark_block[i] ? 1 : bitmap_work[i])`.
   - `blocks_work` increments and `bbox_work_valid` sets iff `!C && mark_any`; C clears both. This predicate is equivalent to `U && mark_any` by the mark definition.
   - On `!C && mark_any`, each min/max uses registered `update_bx/update_by`, updates when `!bbox_work_valid` or the corresponding strict `<`/`>` comparison holds; otherwise hold. C clears coordinates.

4. **End, restart, publication** (lines 155–158, 177–203, 248–254):
   - `end_pending+ = !frame_start && frame_end && active && pixel_count==307200`; `publish_pending+ = end_pending` every clock.
   - `publish_comparison_valid` captures `reference_valid` only on that complete-frame predicate; otherwise holds. A complete end sets `reference_valid=1`, incomplete active end clears it, and `frame_start && active` clears it.
   - `clear_after_publish+ = C ? 0 : (frame_start ? end_pending : clear_after_publish)`; clear assignment is later than the start assignment.
   - `result_strobe+ = publish_pending`; `result_valid+ = publish_pending && publish_comparison_valid`. Other result fields capture their corresponding work registers iff `publish_pending`, otherwise hold. Publication reads pre-edge work even when C clears work on the same edge.
   - Sample accepted at edge S: RAM old data and current/metadata capture at S; decision/destination at S+1; qualified work commit at S+2. Complete end at E: last sample's work can commit at E+1; result captures at E+2. Start at E+1 must preserve the old pending work update at that edge and defer clear to E+2. Start without `end_pending` must clear work and discard pending updates.

## Adapter qualification and metadata consistency

Use adapter lines 48–61, 100–116, 139–158 to trace the tuple and overflow qualification, rather than treating `core_valid` as an external unqualified pixel:

- `boundary_busy=(marker_idle!=0)`, `have=(queued!=0)`, `head=events[rd_ptr]`, `rise=vsync&&!vs_q`.
- `push=(acquired||rise)&&(rise||pixel_valid)`; `start=have&&head[17]&&!head_started&&!boundary_busy`; `pop=have&&!boundary_busy&&(!start||!head[16])`; `overflow=push&&queued==16&&!pop`.
- `excess=have&&!start&&!boundary_busy&&head[16]&&!active&&tail_seen&&!tail_bad`.
- `fire=have&&!start&&!boundary_busy&&head[16]&&active&&!overflow&&!overflow_reset`.
- With `overflow||overflow_reset`, `core_start/core_end/core_valid/core_rgb` all clear and record capture is suppressed. Otherwise each clocks unconditionally: `core_start+=start||excess`, `core_end+=A/end_pending`, `core_valid+=fire`, `core_rgb+=head[15:0]`. Data/control must share this one-edge boundary.
- `overflow_reset+=overflow` every clock; it asynchronously resets detector control while leaving history intact. FIFO flush also clears acquisition, pointers, occupancy, active/end/tail state, marker_idle and pixels; sets error_pending. It does not clear the previously captured motion_record.
- On last issued pixel (`fire && pixels==307199`): `publish_sequence+=active_sequence`, `publish_error+=error_pending`, `marker_idle+=4`, `A/end_pending+=1`. Source start records carry `event_sequences`; no DDR tag substitutes for `publish_sequence`.
- Capture `motion_record` iff `strobe && !overflow && !overflow_reset`, one edge after detector publication (core end+3). Exact bit mapping: `[319:128]=bitmap`, `[127:112]=0`, `[111:108]=maxy`, `[107:104]=miny`, `[103:100]=maxx`, `[99:96]=minx`, `[95:88]=0`, `[87:72]={1'b0,samples[14:0]}`, `[71:64]=blocks`, `[63:35]=0`, `[34]=publish_error`, `[33]=bbox_valid`, `[32]=comparison_valid`, `[31:0]=publish_sequence`. All 320 logical bits belong to one snapshot; constant bits may map to ties.

## Evidence to collect after export notification

For each D, record indexed logical-bit coverage, mapped instance/cell, actual clock/reset/CE or hold mux, data driver and all input dependencies, plus cell/net quotes and dump provenance. Decode each changed/select/update cone to the equations above; register presence or an input-net occurrence alone does not establish a D function. Trace work-clear and frame_start priority through muxes. Keep per-camera unresolved items explicit.

Helper boundaries: `control_summary` (lines 500–520) checks only presence/clocks for the five decision register groups and an input connection from `compare_pending` to `update_pending`; it deliberately leaves decision/select functions and bit counts unresolved (also line 757). `logic_witnesses` omits `block_q`, `bx_q`, `by_q`, `compare_enabled`, work counters/clear/publication and adapter tuple cones, so additional actual dump nodes are necessary. Decode supported scalar LUT6 with index `sum(Ik*2**k)` and MSB-first BITVEC; supported dual L6 uses INIT[63:32] over I0..I4. Do not apply that decoder to ARITH/carry or unsupported packed outputs; trace their documented operator semantics.

RAM corroboration remains separate: four attributed histories, eight history_0..7 DRM36K slices per D (32 total), 15 address bits `D/sample_address[14:0]`, write `D/luma_sum[9:2]` in bit order, read `D/history_q[7:0]`, common axi_clk/enable, width-one A0 READ_BEFORE_WRITE, noninverted clock and disabled extra output register. Physical 32768×1 slices do not establish logical depth 19200; corroborate address limit 19199 and parameter specialization. CAM5/6 detector histories are outside the required allocation. This checklist is not a mapped verdict or resource-gate proof.
