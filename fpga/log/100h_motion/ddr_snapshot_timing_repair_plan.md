# DDR diagnostic snapshot timing repair plan

Plan only. Apply in a new candidate only if the current route repeats the diagnostic failures. The locked current build, RTL, IP, constraints and verifiers were not changed; no PDS or board operation was performed. Current motion-pipeline verification and current final STA remain independent acceptance gates.

## Evidence and exact source identity

`timing_violations_192131.md` inventories 309 old final-STA setup failures: 304 motion endpoints and five DDR diagnostic endpoints. The diagnostic paths are:

| Endpoint | Launch | Slack | Bounded report seek |
| --- | --- | --- | --- |
| `cam5_ov5640_ddr/dbg_fault_snapshot[19]/opit_0_inv/CE` | `u_sfp_rx_cam_if/u_fifo5/rbin[3]/opit_0_inv_AQ_perm/CLK` | -0.152 ns | byte 81,781,197 |
| `cam3_ov5640_top/ov5640_ddr/dbg_fault_snapshot[{19,21,26,27}]/opit_0_inv/CE` | `ddr3/u_ddrphy_top/ddrphy_dfi/dfi_init_complete/opit_0_inv_L5Q_perm/CLK` | -0.099 ns each | byte 82,392,989 begins bit 19 |

Reviewed two 18,000-byte windows at those offsets in `project/motion_100h/run_20261003_192131/final_sta/report_timing/top.rtr`; did not read the whole 2,098,480,827-byte report. Cam5 traverses FIFO read address, distributed RAM/mux, VSYNC, `raw_sof`, capture qualification and the shared snapshot enable (`N168`, fanout 32). Data arrival/required are 12.776/12.624 ns; routing is 6.069 ns, 84.374%. Cam3 traverses `ddr_init_done` (fanout 2857, 2.314 ns route), reset-dependent FIFO logic, `capture_overflow`, qualification and snapshot enable. Arrival/required are 12.750/12.651 ns; routing is 6.272 ns, 87.708%. These are timed AXI-domain enable paths at 7.619 ns period. The displayed packed cam5 clock resource names bit 3 while its Q arc carries `rbin[2]`; preserve the report's exact names when matching new paths.

Byte comparisons of frozen `inputs/source/` in old `run_20261003_192131` and current `run_20261003_212303` found:

| Relative source | Bytes | SHA-256, identical in both runs |
| --- | ---: | --- |
| `ov5640/ov5640_top.v` | 32116 | `1e2ca4e634d8fc5016e9307bbf2f0898fb15e5688ff2eeb6d42b647953af5fc4` |
| `ov5640/ov5640_ddr/ov5640_ddr.v` | 9592 | `5770de1b2d5943cfab8862ae8ce92e42538da9565dcb7e114683e3ed88e34c16` |

Motion changes therefore did not change this local snapshot logic. Different routing may still resolve or worsen its timing; old evidence does not establish a current failure.

## Event semantics and ABI to preserve

Line references below are to current frozen sources. In `ov5640_ddr.v:72-113`, `raw_sof = s_vsync && !raw_vsync_q`; `capture_complete = capture_open && pixel_count == pixel_limit`; `diag_short = raw_sof && !capture_complete`. A source diagnostic event is `capture_open && !capture_flush && !capture_bad && !m_vsync && (capture_overflow || diag_short)`. It captures `{capture_overflow, diag_short, 1'b0, !frame_active, pixel_count[27:0]}` and increments each asserted source-fault counter. If that event is absent, `dma_abort && !capture_bad` captures `{2'b00, 1'b1, !frame_active, pixel_count[27:0]}`. Preserve this priority, including simultaneous overflow and short setting both flags and incrementing both counters.

The count is the **pre-edge** accepted `m_data_valid` count. It excludes an increment made at that same edge. Capture state at lines 125-139 can clear the count on local flush or admitted `m_vsync`, increment it, and set `capture_bad` at the event edge. The diagnostic block sees the old values through nonblocking-assignment semantics. `capture_bad` suppresses later source diagnostics for that admission. The comment "First source fault wins" is per admitted capture; the snapshot is not globally write-once. Later frames can replace it, and the abort branch has exactly its existing `!capture_bad` qualification, without additional open/flush gating. Diagnostics survive local flush and clear only on `axi_rst`.

Bit 28 is exactly `!frame_active`, where `ov5640_ddr_w_ctrl.v:246` defines `frame_active` as FSM state `DATA`. Although its comment says "tag phase", bit 28 also becomes 1 in non-DATA states besides `DATA_TAG`. Preserve that actual encoding. There is no frame sequence number or ping-pong bank in this snapshot.

The separate frame ABI uses payload writes followed by a 16-byte tag transaction at frame base plus `cam_data_len * 16`; the low 32 tag bits carry `frame_cnt + 1`, upper bits are zero (`ov5640_ddr_w_ctrl.v:29-33,248`). Buffer request, successful-frame count and bank publication follow successful tag retirement. Diagnostic pipelining must leave commands, payload, tag value/address, retirement, `frame_good`, `dma_abort_req`, FIFO flush and bank ownership cycle-for-cycle unchanged.

`ov5640_top.v:498-514,700-702` connects these diagnostics to `ov5640_reg`. Register reads expose the snapshot at `BASE_ADDR + 0x00` (`REG_ACK`; ACK writes keep their existing behavior), offered-input count at `+0x30`, and `{overflow_count[15:0], short_count[15:0]}` at `+0xA0` (`ov5640_reg.v:87,99,104,263,274,278`). No packet/register width, address or bit allocation needs changing. A one-AXI-clock later diagnostic publication is an observable read-latency change and must be documented; this interface has no atomic cross-register read latch.

`dbg_input_pixels` has a separate contract: on raw SOF it publishes the previous offered-input interval and seeds the next interval with 1 if `s_data_valid` is simultaneously asserted. Offered pixels are counted regardless of admission, quota or flush. Keep that block's timing and semantics unchanged.

## Proposed concrete RTL change for a future candidate

Use one unconditional AXI-clock stage for the **primitive diagnostic tuple**, then qualify and publish from that tuple. This cuts the FIFO/overflow-source logic before the qualification and 32-bit snapshot enable fanout. Registering only the final `diag_fault` reduces its load but retains the whole source/qualification chain before that register, so it is a weaker fallback with no timing guarantee.

Add local diagnostic registers in `ov5640_ddr.v` for `capture_open`, `capture_flush`, `capture_bad`, `m_vsync`, `capture_complete`, `raw_sof`, `capture_overflow`, `dma_abort`, `frame_active`, and `pixel_count[27:0]`. Sample every field unconditionally in the same `posedge axi_clk` block; use synchronous `axi_rst` to zero all fields. Do not use the fault condition as the stage clock enable. No functional capture/FIFO/control inputs should consume these registers.

Illustrative intended logic (names are new; this is a plan, not an applied patch):

```verilog
always @(posedge axi_clk) begin
    if (axi_rst) begin
        d_open <= 0; d_flush <= 0; d_bad <= 0; d_mvs <= 0;
        d_complete <= 0; d_sof <= 0; d_overflow <= 0;
        d_abort <= 0; d_active <= 0; d_pixels <= 0;
    end else begin
        d_open <= capture_open; d_flush <= capture_flush;
        d_bad <= capture_bad; d_mvs <= m_vsync;
        d_complete <= capture_complete; d_sof <= raw_sof;
        d_overflow <= capture_overflow; d_abort <= dma_abort;
        d_active <= frame_active; d_pixels <= pixel_count[27:0];
    end
end
wire d_short = d_sof && !d_complete;
wire d_fault = d_open && !d_flush && !d_bad && !d_mvs &&
               (d_overflow || d_short);
// In the existing diagnostic publication block, after its axi_rst branch:
if (d_fault) begin
    dbg_fault_snapshot <= {d_overflow, d_short, 1'b0,
                           !d_active, d_pixels};
    if (d_overflow) diag_overflows <= diag_overflows + 1'b1;
    if (d_short) diag_shorts <= diag_shorts + 1'b1;
end else if (d_abort && !d_bad) begin
    dbg_fault_snapshot <= {2'b00, 1'b1, !d_active, d_pixels};
end
```

Remove the original live-signal snapshot/counter update branches when implementing this; retain existing reset assignments and offered-input accounting. Counter updates move with snapshot publication, so source-fault evidence remains aligned. Counter arithmetic remains 16-bit wrapping, without a new saturation policy.

For an event sampled at edge E, original RTL publishes immediately after E. The stage samples the complete pre-E tuple at E and publishes that same event immediately after E+1. It can accept another tuple every clock. A fault at E followed by flush, a phase transition, or a new admission at E+1 still publishes E's count/phase/flags. Do not requalify the staged event using live `capture_bad`, `capture_flush`, `m_vsync`, `frame_active` or `pixel_count`. Do not clear the tuple on local flush: that would erase the evidence being retained. Global reset intentionally drops pending diagnostics and zeros outputs. Keep existing repeated abort behavior if abort is held high; do not invent edge detection or a new first-fault latch.

Simply delaying capture by one cycle corrupts the contract if the destination still samples live data: the count can be incremented or cleared, `capture_bad` can suppress the event, an overflow/SOF pulse can disappear, and the frame phase can change. Registering trigger and complete payload together would preserve event contents, but the proposed primitive stage also moves qualification after a real register boundary.

## Minimum meaningful verification for implementation

1. Add a cycle-level reference scoreboard for the original equations using pre-edge values. Compare future snapshot and reject counters against the reference delayed exactly one clock, after NBA updates. Check offered-input diagnostics without a delay. Include held outputs between events and 16-bit counter wrap. This verifies event contents and latency, beyond eventual nonzero flags.
2. Exercise short SOF with simultaneous accepted pixel, then admitted SOF/count clear; overflow followed immediately by local flush; overflow plus short plus abort together; abort without source fault during DATA and during tag/non-DATA phases; abort held for multiple cycles; already-bad/closed/flushing captures; completed-frame SOF and `m_vsync` suppression; reset with an event pending. Expect original priority and bit fields, original pre-edge count, and no duplication/loss beyond reset cancellation. For tuple-only unit stimulus, clearly label forced internal signals; retain natural end-to-end overflow and short tests as integration evidence.
3. Reuse `project/sim/dma_timeout_repro/tb_rejection_diag.sv` and its behavioral/vendor FIFO configurations in a future isolated candidate. Existing checks include exact short snapshot `0x4000000d`, watchdog snapshot `0x2000000b`, counters `0x00010003`, flush retention, natural overflow with stalled W/B, pixel order, tag errors, bank publication and tag B backpressure. Its checks after `idle()` allow the added clock but do not prove cycle alignment; the new scoreboard is required. Retain successful next-frame recovery and payload/tag memory checks. Do not edit locked verifiers in this task.
4. Verify mapped logic retains the diagnostic register boundary: source FIFO/overflow logic must end at the new stage; snapshot CE/data and reject-counter enables must launch from that stage without bypass through live signals. Check all six instances, including standalone SFP cam5/cam6 users of the same module. Synthesis may merge equivalent registers; inspect actual mapped paths rather than assuming names or RTL stages survive.
5. Require actual final multi-corner setup/hold/recovery/removal closure for the whole new candidate. Explicitly inspect paths to the new tuple registers, snapshot CE/data, and reject counters; the long DDR-init-to-overflow path can still fail at `d_overflow`. If so, review its measured path before further changes. A second aligned diagnostic stage or local physical distribution may be warranted by that evidence; functional reset/admission changes require separate analysis. No false paths, multicycle exceptions, clock changes or constraint waivers are proposed.

Expected functional result: identical fault contents, source priority, counters and frame/tag ABI, with snapshot/reject-counter publication delayed one AXI clock. Expected structural result: a register boundary before diagnostic qualification and wide destination enables. Neither simulation nor the proposed boundary proves timing closure. This task ran no implementation regressions or timing build and makes no current-build closure claim.
