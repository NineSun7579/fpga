# Actual 50K capture/merge row evidence

Production `cam2_merge.v:167` now uses `a_push | a_push_eol`, applied as exactly
one byte-preserving substitution after authorization. Original bytes are saved
in `cam2_merge_before_cap_fix.v`. Top/PDS/IP files were not edited.
`run_all.ps1` compiles the actual 50K
`cmos_8_16bit.v`, `video_async_fifo.v`, `cam2_merge.v` and PDS vendor
GTP_IOCLKBUF/GTP_IOCLKDIV models in ModelSim 10.6e. It creates a byte-preserving,
simulation-only A-cap candidate using `prepare_candidate.py`.

The test reproduces top-level input registers, independent config completion,
asynchronous camera clocks, 640 pixels/row, HTS=2000 bytes, VTS=705,
and two consecutive frames. It checks every captured pixel against camera data,
every merged pixel against capture queues, exactly 307200 pixels per camera,
614400 pixels/merged frame, 480 continuous 1280-pixel DE runs, EOL counts,
malformed rows, and actual FIFO full/write drops.

Capture pixel-clock registers lack explicit resets and the clock remains stopped
until the first VS rising edge after config. The TB initializes only those
unreset capture registers to zero to represent device power-up GRS. Without this
assumption RTL-only simulation propagates startup Xs into FIFO pointers and is
inconclusive. No FIFO/merge internal state is forced.

## Results

| Case | Result | Meaning |
|---|---|---|
| 21 MHz byte clocks, 62.5 MHz merge, VTS705 (~15fps) | PASS | Both frames have 307200 A + 307200 B; no row loss or overflow |
| Original RTL, 481 input rows/frame | FAIL | First row of frame 2 on A is discarded; only 479 pairs of frame 2 can complete |
| Modified production, 481 input rows/frame | PASS | Exactly two complete frames, zero malformed rows or overflow |
| Same 481 rows, A gate candidate | PASS | Extra rows are capped consistently; both output frames are complete |
| 84 MHz byte clocks, 62.5 MHz merge, VTS2820 (~15fps) | FAIL | Burst bandwidth causes FIFO full and extensive malformed rows |
| 84 MHz byte clocks, 100 MHz merge, VTS705 | PASS | Both full frames, every pixel checked, zero FIFO full or malformed rows |
| 84 MHz byte clocks, 125 MHz merge, VTS705 | PASS | Both full frames, every pixel checked, zero FIFO full or malformed rows |
| 84 MHz byte clocks, 481 rows, 100 MHz merge | PASS | Extra row capped, two complete output frames |
| 84 MHz byte clocks, 481 rows, 125 MHz merge | PASS | Extra row capped, two complete output frames |

### Concrete conditional first-row loss

Original `cam2_merge.v:167` wrote A pixels with
`.wr_en(a_de_r | a_push_eol)`, but EOL is generated from capped `a_push`.
Row 480 (zero based) therefore writes 640 pixels without an EOL. Camera VS
resets `a_line_cnt`, not `a_fcnt` or the pixel FIFO. Next frame's row 0 appends
another 640 pixels; its EOL sees `a_fcnt=1280`, fails the exact-640 acceptance,
and discards the combined rows. Next frame starts at row 1. The overscan log
records `MALFORMED_A eol=481 pixels=1280`, no FIFO full, and frame 2's partial
counts A=B=306560. This requires an extra input DE row; the exact-480 baseline
does not reproduce it, so it is not proof of the board's current fault.

Minimal correction proved in isolation:

```verilog
.wr_en(a_push | a_push_eol)
```

### Token/service math

An accepted camera row uses 640 pixel tokens + one EOL; each frame uses
480*641=307680 FIFO tokens per camera. EOL seals a page only at exactly 640.
Each merged pair uses 640 A output clocks + 640 B output clocks + 640 snapshot
copy clocks + four gap clocks + two WAIT/entry clocks: about 1926 clocks.
At 62.5 MHz this is 30.816 us/pair. HTS2000 at 84 MHz is 23.81 us/row,
requiring about 80.9 MHz merge service for sustained active rows. Longer
vertical blanking lowers average frame rate but does not solve this burst
deficit with finite row/FIFO storage. At 21 MHz, 95.24 us/row is ample.

Actual config source sets 0x3808/09=0x0280 (640), 0x380A/B=0x01E0 (480),
0x380C/D=0x07D0 (HTS2000), 0x380E/F=0x02C1 (VTS705).
Comments claiming 84 MHz/60fps are not measurements. Top-level merge uses
`mrg_clk`, implemented as a toggle on each falling edge of 125 MHz
`clk2core_tx` (`hdmi_ddr_ov5640_top.v:801`), so it is 62.5 MHz. Measure byte PCLK/DE rows to distinguish
slow PCLK from extended VTS on a board reporting 15fps.

Merge VS is generated AFTER each 480th output pair. There is no initial VS
before frame 0 and no source VS token in the pixel FIFOs. A downstream consumer
that waits for its first VS can ignore the initial whole frame, but that alone
does not remove one row from every later frame. B fallback repeats a snapshot
or black when late; those still produce 640 output pixels, so count alone
cannot prove camera row identity. The test's full pixel scoreboard checks it.

Optical CTC and the parent session's receiver/same-cycle rotation changes are
outside this isolated test.
