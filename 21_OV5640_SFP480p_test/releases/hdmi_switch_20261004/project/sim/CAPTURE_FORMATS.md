HDMI capture format extension
=============================

`hdmi_720p_capture.v` defaults to automatic recognition of progressive,
positive-VS 1280x720 and 1920x1080 RGB888 DVP input. Recognition uses every
actual DE line width and the number of DE lines between VS rising edges.
One complete valid frame is measured before payload from the next frame is
admitted. A line-width change, excess rows/pixels, short line, short height
at the following VS, or FIFO overflow aborts an admitted frame and asserts
the existing sticky fault. The mode switch drains and resets both FIFO
domains, then capture reacquires from a complete frame. Unsupported input
still produces SOF controls but no admitted payload.

The optical output always contains 1280x480 = 614400 ordered RGB565 pixels:

| Input | Output column x selects input column | Output row y selects input row |
| --- | --- | --- |
| 1280x720 | x | 3*floor(y/2) + (y mod 2) |
| 1920x1080 | 3*floor(x/2) + (x mod 2) | 9*floor(y/4) + [0,2,4,7][y mod 4] |

RGB565 is `{R[7:3],G[7:2],B[7:3]}`. The formulas above describe the mapping;
RTL uses only phase counters, registered retention/boundary flags and
constant comparisons, without division. The receiver still partitions the
output into its left/right 640-pixel halves. This is decimation without
filtering, frame storage or aspect correction; thin features can disappear.

720p60 uses 74.25 MHz input. 1080p60 uses 148.5 MHz input, retaining two of
three columns for an effective 99 Mpixel/s within selected rows. Retained
1080 rows are separated by at least one dropped row. For a 1920-pixel line,
1280 writes arrive over about 12.93 us while the 62.5 MHz consumer drains
about 808 pixels, giving about 472 pixels of local backlog. A 280-pixel
horizontal blank plus a dropped line lets that backlog drain before the
next retained row. The default 2048-entry FIFO comfortably covers this
traffic under the tested clocks; adjacent retained input pixels still
require the FIFO write logic to meet the full 148.5 MHz clock.

Legacy explicit INPUT_WIDTH, INPUT_HEIGHT, OUTPUT_HEIGHT and FIFO_DEPTH
parameters remain available. Non-default dimensions automatically select
the original two-of-three-row preset; AUTO_FORMAT can also be set explicitly.
Production defaults are the fixed formats above. Overrides are intended
for existing reduced-geometry tests, not automatic arbitrary scaling.

Run from `E:\build\50k_hdmi_switch\project\sim`:

```powershell
$env:FORMAT_RUN_MODES='1' # include keys/mode-switch integration regression
Remove-Item Env:FORMAT_TEST_TOP -ErrorAction SilentlyContinue
& 'E:\questasim64_2021.1\win64\vsim.exe' -c -do runformat.do -l capture_formats.log
```

`runformat.do` copies all compiled inputs into a new `format_sim_*` directory
under the project root and records SHA-256 hashes in `source_sha256.txt`.
This isolates each simulation from concurrent edits by the timing agent.
The new full-size `tb_capture_formats.sv` uses 50 MHz system, 62.5 MHz output,
125 MHz fabric, and 74.25/148.5 MHz HDMI clocks (periods rounded to 1 ps).
Every admitted complete frame checks all 614400 capture and actual 100H
`receiver/sfp/sfp_video_rx.v` pixels, with FIFO occupancy and RX overflow
checks. It covers repeated 1080 frames, automatic transitions both ways,
unsupported width/height, mixed line widths, admitted short height, and
unplug timeout/flush. `tb_hdmi_modes.sv` additionally covers key debounce,
latching, priority and frame-boundary switching for both formats.

An abruptly changed or unplugged source can leave an incomplete last frame
at the receiver; capture cannot retract already transmitted pixels without
a frame buffer. The next accepted SOF restores receiver ordering. Interlace,
other dimensions and rates above the tested input clock are unsupported.
MS7200 configuration/EDID is unchanged. Digital simulation does not qualify
external input arrival timing, placed FPGA timing or the analog optical
link. The timing agent owns those constraints and the shared FIFO; this
capture work does not run PDS. The parent must run final combined-source
simulation after both agents' changes stabilize.

Recorded validation, 2026-10-04
-------------------------------

* `capture_formats.log`: TEST PASS, zero errors/warnings, 272076688 ns
  simulated, 89 seconds wall time. Three complete 720p frames and two complete
  1080p frames each compared all 614400 pixels at both capture output and the
  actual RX. Peak FIFO occupancy across valid and aborted transition frames
  was 745/2048; no capture full or actual receiver overflow occurred.
  Immutable inputs: `format_sim_20261004_122220_28400/source_sha256.txt`.
* `capture_modes.log`: TEST PASS, zero errors/warnings, 211755220 ns
  simulated, 83 seconds wall time, 1843903 payload packets. Covers original
  keys/mode switching plus complete 1080p output and transitions both ways.
  Immutable inputs: `format_sim_20261004_122556_11520/source_sha256.txt`.
  This run returned shell code 1 because the then-current runner treated
  successful `$finish` as a break; the final runner resumes its macro and
  checks an explicit test-pass flag before returning 0.
* `capture_preset.log`: TEST PASS, zero errors/warnings, shell code 0,
  3986538 ps simulated. Verifies legacy 6x6->6x4 overrides, all 24 RGB565
  pixels and final DE falling together with VS rising. Immutable inputs:
  `format_sim_20261004_123836_26328/source_sha256.txt`.

The full-size and mode runs used FIFO SHA-256
`AB07126F26CFF1EB3E29EEF2A9610B69EAA862C1BD135232ADE601D5A3B549E7`.
The later preset used timing-agent FIFO SHA-256
`2BE95F6ADF3CD38E88C9BD7014C6B4623A0580B02BE108E56A392F98EC148581`.
The parent still needs the full combined-source run with the final FIFO.
Capture functionality was unchanged after the full-size passes; subsequent
changes added test completion flags, the separate preset module, runner
exit handling and a corrected half-cycle timing comment. These extensive
full-frame runs exceed a 30/45-second wall-time cutoff on this workstation.

To run only the short preset, set `FORMAT_TEST_TOP='tb_capture_preset'` and
`FORMAT_RUN_MODES='0'`. For mode integration alone set
`FORMAT_TEST_TOP='tb_hdmi_modes'`. The runner retains signal access for its
explicit pass flag; final combined runs may therefore take longer than the
optimized earlier timings above.
