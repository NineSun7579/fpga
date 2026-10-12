# 50K normal-image final-column investigation

The initial investigation did not edit production RTL, PDS, IP, hardware, or 100H sources. All
preparation reads/writes HDL as bytes. Tests compile the actual 50K
`cmos_8_16bit.v`, `video_async_fifo.v`, and `cam2_merge.v`, with installed
Pango `GTP_IOCLKBUF` / `GTP_IOCLKDIV` models. The harness reproduces the top's
single-PCLK data/HREF/VSYNC registers. It initializes otherwise unreset capture
output registers while clocks are stopped, as the inherited physical-stress
harness does; its global GRS instance supplies the vendor divider model.

## Reproduce

From this directory in PowerShell:

```powershell
python prepare.py
python prepare_sensor_candidate.py
& C:\modeltech64_10.6e\win64\vsim.exe -c -do run.do -l equal_rate_gray_verified.log
& C:\modeltech64_10.6e\win64\vsim.exe -c -do 'set SHIFT 24; do run.do' -l equal_rate_phase_gray_verified.log
```

## Proven capture/merge behavior

Two full 640x480 frames per camera. Every active source pixel varies by camera,
frame, row, and column; adjacent final pixels differ. The HBLANK bus cycles
`a5,34,84,10` immediately after HREF falls. Capture is compared directly to
the generator formula, independently of the queue used to check merge.
Merge is checked pixel-by-pixel including B snapshot storage.

Both verified logs finish `TEST PASS`, with:

- 614400 correctly captured pixels / 960 rows per camera.
- 1920 independently checked final-two-column samples per camera.
- Zero source identity, capture width, merge data, FIFO-full, or malformed-EOL
  errors; two merged frames of 614400 pixels, 480 rows each.
- All 960 B rows real; no repeated or black B rows in these equal-rate cases.

The two shifts alter B's line-start parity by a PCLK. Equal byte clocks are
42 MHz; HTS=2000 byte clocks and VTS=705 give 29.787 frames/s in this harness.
This excludes a deterministic replacement of the last two valid words by
HBLANK data for clean, correctly aligned 1280-byte source HREF rows. It does
not model pin setup/hold, sensor ISP, DDR, TX, or arbitrary clock gating.
It is not proof that hardware HREF contains valid sensor pixels at every byte.

## Asymmetric-rate finding: do not hide this failure

`normal_gray_blank.log` ran A at 42 MHz and B at 21 MHz (29.787/14.894 fps in
this modeled byte-line schedule). Both captures still had zero source errors
and 1920 correct final-column samples each. However, merge failed: frame 1
had 81920 B data mismatches, and the test eventually logged 375534 B FIFO-full
write attempts and one malformed B row. It continues both cameras until B
finishes two frames, so A has already stopped for part of the observation;
the total FIFO-full count cannot be attributed solely to concurrent streaming.
The B mismatch occurs in merged frame 1, before A stops. This is a separate
rate/phase/backlog exposure, not a demonstrated two-column gray artifact:
A's output remains exact and B failures affect complete rows. Hardware frame
rates alone do not establish this PCLK/HTS schedule; sensor AEC can change VTS.

`equal_rate_phase_gray.log` is an earlier run with zero data/count errors but
an inherited pass predicate that assumed an 84 MHz byte clock. The verified
log fixes that test predicate. No production fix was needed for either clean
equal-rate run.

## Register evidence and isolated candidate

No local OV5640 vendor PDF existed in the workspace. A public vendor datasheet
was downloaded to `evidence/OV5640_datasheet.pdf`, with searchable extracted
text alongside it:

https://s1-dl.theimagingsource.com/api/2.5/packages/publication/sensor-omnivision/ov5640/98284436-e865-5de5-a517-7a514df571b6/ov5640_1.0.en_US.pdf

Vendor version 2.03, printed pages:

- 2-4 (PDF p22): VGA 640x480 uses an intermediate 648x484 with dummy pixels.
- 4-2/4-3 (PDF p40/41): output window lies inside ISP input, controlled by
  X/Y offsets; with scaling, pre-scaling dimensions subtract twice the offsets.
- 5-1 (PDF p59): `0x5001[5]` enables scaling. Current `0x83` disables it.
- 6-11 (PDF p87): `0x4300=0x60` emits BGR565, MSB byte first. The existing
  merge R/B swap matches this. Changing to `0x61` would also require changing
  merge color handling; it is not an edge-alignment remedy.
- 7-34 (PDF p132): `0x460c[1]` selects manual DVP PCLK control via `0x3824`;
  current `0x20` selects auto. Footer bit 2 concerns JPEG mode 2's last six
  bytes of a frame; current `0x4713=0x03` is mode 3, and the output is RGB565.
  This is not evidence for a standard two-gray-pixel RGB footer per line.
- 7-34 (PDF p132): `0x4711/12` add left/right padding in HSYNC mode, default
  zero. Readback is useful if padding is suspected.
- 4-5 (PDF p43): `0x503d[7]` enables color bars. The normal table does not
  write index 357, so reset default zero applies; only COLOR_BAR_TEST writes
  `0x503d=0x80`. No production write to `0x4740` was found.

Independent driver evidence:
https://github.com/torvalds/linux/blob/master/drivers/media/i2c/ov5640.c
uses VGA DVP input width 2624 and horizontal offset 16, and explicitly retains
minimum ISP processing margins in CSI-2 configurations. Its low-res settings
use `460b=35,460c=22,3824=02,5001=a3`; its 720p settings use the current
`37,20,04,83` combination. That difference is evidence for a coherent alternate
mode family, not proof that changing any single clock register repairs this
artifact. Do not change all of these alongside the first margin experiment.

Current input window x=672..1951 is exactly 1280 sensor columns; with 2:1
subsampling it supplies only 640 ISP columns, X offset zero, scaler disabled.
That leaves no surrounding input pixels for normal ISP edge processing.
Color bars do not establish that normal ISP borders are valid scene pixels.

`candidate/reg_config.v` changes exactly three register values:

| Register | Current | Candidate | Effect |
|---|---:|---:|---|
| 3811 | 00 | 10 | 16 ISP-column horizontal offset |
| 3801 | a0 | 80 | x start 672 -> 640 |
| 3805 | 9f | bf | x end 1951 -> 1983 |

The candidate expands sensor input to 1344 columns, 32 extra sensor columns
on each side, and offsets the 2:1-subsampled window by 16 ISP columns. Nominal
visible sensor interval remains 672..1951; requested output stays 640x480.
Vertical window, RGB format, PLL, HTS/VTS, scaling, and capture/merge RTL stay
identical. This supplies context to the sensor ISP; it does not discard,
paint, or replicate output pixels. Exact effective mapping must be confirmed
on the sensor because increment phase and ISP behavior are not modeled here.

This is a reviewable diagnostic candidate, not a proven fix. The candidate
and actual production `i2c_com.v` compiled with ModelSim
`vlog -work candidate_work` with zero errors and zero warnings. To test
it, keep normal mode, capture fresh frames on both sensors before/after,
compare columns 632..639 against actual scene content, retain exact 640x480
counts, and check view alignment and fps. A parent-approved hardware test can
also read `3800..3815,3820/21,460c,4711/12,4740/41,5001,503d`; production table
values alone are not readback. Raw final active DVP bytes would distinguish
sensor-generated gray from pin timing contamination if the margin test fails.

SHA256 of inspected source:

```text
reg_config.v 305b82b140c880c5ccdb43589629f792d1e3a181f58e612faa08e07eedc33d0c
cmos_8_16bit.v b9514a3fdfa3f59283a3e6e641e0ee083c9a079ec550a8340c6628e0efde8466
cam2_merge.v 462ae7a978678d6440cdc2bdfb05015d8caa3a18db8b904f2dba92548cae0a7c
video_async_fifo.v 17c2892ddc2f707fce1ff78fcb736528f7cd6d72b9efeccda52fa8f8706475b5
hdmi_ddr_ov5640_top.v 88dc3630d558de1c7934ac7ad91f5e277c7514c690c11dca9f497bfa5ce084d5
candidate/reg_config.v 1cd4405242a95f054fec9b7dd1e3ec7b84a46f5a5d15a02fad9a6902534e7124
```

## Authorized normal-image margin experiment

`validate_margin.py` builds a separate SCCB test in `margin_sccb/` from the
immutable 023911 normal-image source archive. Its golden commands use the
old table with exactly the three explicit value changes at indexes 147,
316, and 320. It checks duplicate command indexes and the effective final
register map in command order. The normal sequence retains its existing
100 default `ffffff` commands at indexes 2..101; no commands are inserted.
3811 is written only at index 147, so 10 remains effective at completion.
Normal mode has 357 commands and no 503d write; color-bar mode has 358.
The reused bus monitor verifies every serial bit on both actual sensor
instances through two complete configuration rounds and stopped-clock reset.

Run `python validate_margin.py`, then `margin_sccb/run.ps1`. Only after both
modes pass, `project/tools/prepare_50k_margin.py` preserves the exact current
normal table, top, and TX files in `current_normal_023911_backup/`, checks all
source/constraint/IP hashes against 023911, applies the candidate as bytes,
and prepares a fresh immutable archive through `build_50k_final.py`.
The visible `build_50k_final.ps1` uses the existing full physical/STA flow.
No constraints, IP, capture/merge RTL, or 100H inputs are part of this edit.

`log/50k_margin_launch.json` identifies the new archive, evidence directory,
flash Tcl, and persistent post-runner handoff. The parametrized
`finish_normal_023911.py --margin-candidate` checks the exact candidate hash
and normal rollback hash before programming, verifies the PGL50H-only chain,
collects continuous diagnostics and fresh frames for 30 seconds, restores
camview, and captures the actual X11 display. It saves every output pixel:
640x480, 307200 pixels, 614400 RGB565 bytes per frame. Per-column histograms
for 632..639 include A534/8410 counts in both baseline and candidate frames.
No image cropping, masking, painting, or replication is applied.

The known rollback is normal 023911, SHA256
`1df94407f27a81bfa963be9c0e7f89a3d44ef6ac295680d26aafb66884fdcf5e`.
It has accepted counts and freshness but retains the right-edge artifact.
Candidate success still requires actual normal-scene visual review, including
nominal view alignment and absence of the gray columns. Passing simulation,
STA, programming, or stream counts alone does not establish repair. The
post-runner deliberately leaves `objective_complete=false` for parent review.

The authorized 033106 candidate completed build and verified programming,
with bit SHA256 `99e4a240962915e80c3d9c045a7787e219e346e494f20f9f2478b3605627a384`.
Thirty-second board acceptance passed. CAM5/6 retain 640x480 and measured
29.8017/14.9008 fps. In the captured frames, A534 at column 638 dropped from
388/353 rows to zero, and 8410 at column 639 dropped from 368/365 to zero.
The full frames and actual X11 screenshot show no right gray border; monitor
position and nominal view remain consistent with baseline. See
`log/six_margin_board_20261003_033106/VISUAL_REVIEW.md` and the full column
histograms for evidence and limitations. The candidate remains on the board;
parent review and goal closure remain separate.
