# DMA timeout / shared write wedge reproduction

Initial investigation added simulation only. The authorized repair now changes
only production `source/axi_dma/axi_dma_write.v`, via `patch_dma_ledger.py`
(Python bytes editing, exact original backup `axi_dma_write.v.ledger.bak`).
The original findings below refer to the pre-repair RTL and transcript.log.

## Repair validation

`run.do` now runs regression expectations for the fixed RTL; `baseline.do`
runs the identical test against the original .bak. Logs are `fixed.log` and
`baseline_failure.log`. ModelSim returns exit code zero even on the testbench's
$fatal with this do-file, so validate log contents, not process status alone.

The baseline passes normal burst/tag/burst, then fails:
`Fatal: AW changed under backpressure cam=1`.

The repaired source passes:

- Normal burst/tag/burst: AW=4 B=4 W=49.
- Watchdog terminal value while AW waits: stable AWVALID/address/length,
  retained transaction, no false done or command-ready.
- Zero-fill data/strobes checked on every camera 3 external W handshake.
- Internal act=0 while final W remains buffered/backpressured: trans retained,
  BREADY=0, no done or command-ready.
- Final external W complete, B withheld, watchdog forced again: no release.
- All cameras recover: AW=5/1/1 B=5/1/1 W=65/16/16 DONE=4/1/1.
- A 32-beat command aborted during its first 16-beat burst retires only after
  that burst's real B, then discards the unissued remainder without another AW.
- A subsequent single-beat command completes normally.

Only watchdog counter terminal values are forced. W and B stalls are normal
testbench sink behavior, not force statements on DUT interfaces. Compile has
zero errors/warnings; simulation reports unused output port/ID-width warnings
from the minimal bench and the existing ModelSim optimization setting.

Repair behavior: watchdog applies only to an accepted burst; AW payload holds
while AWVALID is asserted; abort_done requires real B; BREADY is armed by the
external last-W handshake. Missing AWREADY/B cannot be bypassed by watchdog.
The existing completion interface still has no separate aborted-frame status:
after zero-fill and real B, it reports completion and discards unissued frame
remainder. This patch does not repair the independent frequent-VSYNC source.

Run in this directory with ModelSim 10.6e:

```
vsim -c -do run.do -l transcript.log
vsim -c -do vsync.do -l vsync.log
```

Both tests passed on 2026-09-26. `tb_timeout` instantiates three original
axi_dma_write modules, their original stream_pipe modules, and ddr_w_arb.
The DDR sink is a behavioral FIFO occupancy / AW staging / B model matching
the top-level interface contract, not a Pango DDR timing model. Watchdog counters
are forced to their terminal value to accelerate timeout; no control/output
signals are forced. The test deliberately expires waiting masters before the
owner. This ordering is possible when the owner has made W progress after the
waiting masters started their commands (their own progress counters never reset).
This is a proven RTL failure mechanism, not a captured board waveform proving
that this exact ordering happened on the board.

Evidence in transcript.log:

```
PASS healthy burst/tag/burst AW=4 B=4 W=49
PROVED stalled AW survives timeout: valid=1 len=255 internal_len=0 trans=0
AW t=1995000 cam=1 len=255
FINAL owner=0 busy=1 stage_hold=1 heldlen=15 fifo=0 act0=0 AW=5/0/1 B=4/0/1
PASS reproduced shared permanent write wedge with data_valid high on cam1/2
```

Mechanism:

1. axi_dma_write.v:224 watchdog runs whenever trans=1, including AW waiting
   for another camera's arbiter ownership to finish.
2. With no accepted AW, act_burst_len=0. Timeout therefore immediately satisfies
   abort_done (line 265), clears len (99-100) and trans (116-117).
3. AWVALID clears only on reset or AW handshake (166-180). The waiting AW remains
   asserted. AWLEN is recomputed every cycle (182-184): len=0 -> AWLEN=255.
4. top.v:136 declares ddr_axi_awlen as FOUR bits; assignment at 461 truncates
   255 to 15. The fits check accepts this as 16 beats when FIFO is empty.
5. On the same handshake the DMA loads its EIGHT-bit act_burst_len with
   m_axi_awlen+8'd1 (200-201), wrapping 255+1 to zero. It produces no W beats,
   even with data_in_valid continuously asserted.
6. top.v:567 waits for sixteen FIFO words before exposing AW to DDR.
   No words arrive. ddr_w_arb.v:174 needs B to release owner. No DDR AW, no B.
   All three write masters are blocked permanently until reset/recovery.

Normal AWLEN timing and tag-to-next-command sequencing passed the control
case. In that case len/addr are stable during AW wait and B serializes bursts.
stream_pipe does not create a length error in the tested case. Its two slots
do mean act_burst_len=0 measures words accepted into the pipe, not necessarily
words delivered to DDR; the timeout close must not be equated with a real B.

Frequent VSYNC test compiles the original ov5640_ddr_w_en and w_ctrl modules.
At 100 MHz with VSYNC every 10000 clocks, continuously valid 16-bit pixels:

```
COMMAND bytes=614400
VSYNC RESULT raw_pixels=50000 admitted_pixels=10000 accepted_vsync=1 commands=1 ctrl_state=4 gate_state=1
```

The first VSYNC admits one frame and a full-size command. The second VSYNC
finds engine_busy=1 and changes the admission gate to IDLE (w_en:50-56).
Further raw data is suppressed by w_en:88 and VSYNC is suppressed by line 92.
The controller remains DATA with a full 307200-pixel command, although only
10000 pixels were admitted even in this maximum-rate synthetic source.
Thus high raw data_valid does not establish sufficient admitted frame data.
This test establishes the input-side truncation independently; it does not
simulate the physical source of the 10 kHz VSYNC or a full camera FIFO chain.

Repair requirements for a later authorized RTL change: preserve outstanding
AW payload through timeout; do not mark transaction done or clear its ledger
until accepted AW/W/B obligations are drained; prevent an unaccepted waiting
AW timeout from mutating its length; validate the 8-bit-to-4-bit boundary.
Simply clamping AWLEN or disabling the stage gate will not repair the ledger.
