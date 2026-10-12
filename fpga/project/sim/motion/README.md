# Block motion detector

`block_motion_detector.v` is an isolated sideband consumer of RGB565 pixels in
one clock domain. No ready/backpressure signal is needed. Default geometry is
640x480, sampled at x%4==0 and y%4==0: 160x120 luma bytes and a 16x12 bitmap.
Partial sample grids and partial edge blocks are supported with ceiling division.
All geometry and block threshold parameters must be positive; PIXEL_THRESHOLD
must be 0..255. Derived geometry parameters must not be independently overridden.

## Adapter contract

* Assert `frame_start` for one rising clock edge **before** pixel zero. Assert
  `frame_end` for one edge **after** the last accepted image pixel. Neither marker
  edge accepts a pixel. Start takes precedence if both markers are asserted.
* Every high `pixel_valid` on an active, non-marker edge consumes one pixel,
  including consecutive cycles. Low-valid gaps do not advance coordinates.
* Only the first WIDTH*HEIGHT pixels are consumed. Tail dummy pixels, including
  any valid asserted with frame_end, never read or write history or counters.
* Synchronous RAM reads occur on a sample acceptance edge; the changed predicate
  and block selection are registered on the next edge, then local block counts
  and statistics update on the second edge. Results publish **two rising edges
  after frame_end**, including a final sampled pixel immediately before end.
  A new start at end+1 is legal: final old-frame work commits before publication
  and deferred clearing; the first new pixel may arrive at end+2.
* `result_strobe` pulses for every complete frame publication, including seeding.
  `result_valid` pulses alongside it only when a previous complete reference was
  available. Published fields remain stable between strobes. `frame_sequence`
  increments on every complete publication, starting at 1; aborted/short frames
  do not increment it. Sequence wraps naturally at 32 bits.
* The first complete frame after reset or reference invalidation seeds RAM and
  publishes zeros with result_valid=0. A short end, or start while another frame
  is active (even if all pixels arrived but end did not), invalidates history.
  A stray end outside a frame is ignored. An incomplete frame produces no strobe.
* `rst_n` asynchronously resets control; RAM is deliberately not reset. Drive
  inputs synchronously and release reset in this clock domain.

RGB565 channels expand by bit replication to 8 bits. Luma is the floor of
(R+2G+B)/4. Absolute luma difference >= PIXEL_THRESHOLD counts as changed.
A block is marked when its changed sample count reaches BLOCK_THRESHOLD, which
is inclusive. Counts saturate per block but total changed_samples counts every
changed sample, including those in blocks below threshold. Bitmap bit
`by*BLOCK_COLS+bx` represents a block. Bounding coordinates are inclusive block
coordinates over marked blocks, with bbox_valid=0 and zero coordinates when none
are marked. Seeding also produces zero sample/block counts.

## Resources

History uses 19,200x8 = 153,600 bits at defaults, in a synchronous read-before-write
single-port RAM template. There is no RAM reset, initialization loop, or
asynchronous array read. The first complete frame overwrites every sample before
comparison is enabled. Read and write access the same address on acceptance;
the template requires old-data/read-first behavior. Confirm that Pango synthesis
maps this template to BRAM with this mode before integration; no PDS run was
performed for this isolated task. Physical BRAM packing depends on available
depth/width configurations. Bitmap/counters intentionally use registers: defaults
require 192 four-bit saturating block counters plus a 192-bit working bitmap and
192-bit published bitmap. Constant coordinate division/modulo may add logic,
particularly for non-power-of-two sample steps and block dimensions. The history
read output has an enable but no reset to preserve inference.

## Simulation

Run from this directory:

    C:/modeltech64_10.6e/win64/vsim.exe -c -do run_motion.do

The self-checking testbench uses an independent full-frame software scoreboard,
checks cycle-exact publication, output stability and actual RAM contents after
surplus dummy pixels, and includes sample-step 1 for consecutive RAM accesses and
the final-pixel pipeline flush. It also tests default geometry, partial edge
blocks, RGB luma, static/uniform/localized motion, inclusive thresholds, valid
gaps, frame edges, reset, short frames and restart recovery. The transcript is
written to `motion_results.log`; simulator-generated work/log files are artifacts.

Verified with ModelSim SE-64 10.6e on 2026-10-03: all four configurations passed.
640x480 / step 4 checked 16 publications over 5,094,385 clock edges; 21x13 /
step 4 and 5x3 / step 1 each checked 28 publications; 1x1 / step 1 checked 35
publications. Compilation
reported zero errors and zero warnings. Simulation reported zero errors and one
environment warning about inherited `-novopt`. No PDS, JTAG, or integration
changes were made. The runner uses a local modelsim.ini and returns nonzero for
a test failure or missing success flag.
RTL also compiled as Verilog (without `-sv`) with zero errors/warnings. A
temporary forced result_strobe fault was detected at the first scoreboard tick
and the macro runner returned exit code 1; its log is `motion_fault_check.log`.
The fault injection was removed from the delivered runner.

The default-size run starts with the exact six-frame oracle, checked with literal
expected counts, bitmaps, validity and bounding boxes independently of the
frame scoreboard:

| Frame | Image | Changed samples | Marked blocks |
| --- | --- | ---: | --- |
| 1 | Black seed | 0 | None; comparison invalid |
| 2 | Black | 0 | None |
| 3 | White at (0,0)..(28,0), step 4 | 8 | Bit 0 |
| 4 | Same eight white samples | 0 | None |
| 5 | Black | 8 | Bit 0 |
| 6 | All white | 19,200 | All 192 bits; bbox (0,0)..(15,11) |

Further literal checks cover seven hits (no marked block), eight hits split four
each across blocks 0 and 1 (no marked block), and their falling transitions.
Two final-sample edge cases place seven hits at raw (600..624 step 4,440) and
the eighth at raw (636,476): rising without surplus tails and falling with valid
gaps and three surplus tail pixels both produce exactly eight changed samples,
bit 191 only, and bbox (15,11)..(15,11). Changing only unsampled pixels in either
direction produces zero samples and zero marked blocks at 640x480.

Exact luma boundary checks use RGB565 0x0009 (expanded B=74, luma=18) as the
reference, then 0x0010 (B=132, luma=33), 0x004f (G=8, B=123, luma=34), and
0x0011 (B=140, luma=35). With floor((R+2G+B)/4), these give attainable absolute
differences 15, 16 and 17. Literal 1x1 tests in both directions expect zero hits
for 15 and one hit/marked block for 16 and 17. The transcript records a PASS line
for each explicit oracle and ends with `PASS ALL block_motion_detector self-checks`.
This validation extension changed only the owned TB and this README; RTL and
runner architecture were unchanged.
