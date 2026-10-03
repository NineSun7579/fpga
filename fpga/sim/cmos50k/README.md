# Actual 50K CMOS bytepacker investigation

Run from this directory in PowerShell:

```powershell
& C:\modeltech64_10.6e\win64\vsim.exe -c -do run.do -l results.log
```

This compiles the actual, unchanged production bytepacker at
`../../../ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/cmos_8_16bit.v`.
It compiles the installed Pango `GTP_GRS`, `GTP_IOCLKBUF`, and `GTP_IOCLKDIV`
models directly, including the divider's reset-release pipeline. No clock
stub or copied bytepacker is used. The test reproduces the top's single-PCLK
input registers for data/HREF/VSYNC. It does not compile or inspect merge RTL.
Clock period is 10 ns; results scale in PCLK cycles, not absolute hardware ns.
The first HREF rises asynchronously, with its first byte stable before sampling;
later bytes change on falling PCLK. This is a functional test, not an input
setup/hold or metastability model.

Verified with ModelSim SE-64 10.6e on 2026-10-02: 18 cases, compilation errors 0,
`SUMMARY clean_failures=0`. The single simulator warning is the inherited
`-novopt` setting. `results.log` contains all counts and mismatch examples.

## Clean input does not lose a row or pixel

Cases 1-4 send 480 continuous rows of 1280 bytes, with 720-PCLK HREF gaps,
using first-HREF offsets 1, 7, 13, and 19 ns. Cases 5-6 use 721-PCLK gaps,
making row-start parity alternate, and offsets 1 and 11 ns. All six yield:

- 307200 pixels, 480 output rows, 640 pixels per row.
- Zero data mismatches against row/column-specific RGB565 values.
- Zero row-local mismatches; no VSYNC overlap with sufficiently long blanking.

Both divider/HREF phases therefore work for complete even-width rows. The
packer does not reproduce CAM5's 640-pixel loss from clean 480-row input.

## Proven conditional defect: odd-width DE is not complete-word valid

Production `cmos_8_16bit.v:77` resets `cnt` whenever DE is low. Pair creation at
line 98 requires DE and `cnt==1`, so only complete byte pairs become new words.
However, `de_out1` at line 107 follows delayed HREF edges independently of pair
completion. Lines 125-133 sample this level and the held pair register on a
free-running /2 clock. An odd-length HREF can qualify a duplicate final word.

Cases 7-10 change every 17th row, including row 0: 29 affected rows per frame.

| Input | Complete pairs/frame | Output pixels, phase 1 / 11 | Output rows | Row-local bad samples |
| --- | ---: | ---: | ---: | ---: |
| 1279 bytes on affected rows | 307171 | 307185 / 307186 | 480 / 480 | 14 / 15 |
| 1281 bytes on affected rows | 307200 | 307214 / 307215 | 480 / 480 | 14 / 15 |

For 1279 bytes, affected rows have either 639 correct output pixels or 639
correct pixels plus a duplicate of pixel 638 (640 DE-qualified samples).
For 1281 bytes, affected rows have either 640 correct pixels or 640 correct
pixels plus a duplicate of pixel 639. The affected rows alternate divider
phase because their total line period is odd. Other rows retain correct data.

`bad_data` is the global stream comparison: one insertion offsets subsequent
comparisons, producing a large mismatch total. `local_bad_samples` and
`bad_rows` compare each output row independently and isolate actual defects.
The test asserts this odd-width signature as well as clean-frame correctness.

A 1279-byte source row can thus appear one pixel short; an undamaged 1280-byte
source row did not lose a pixel in these tests. Odd-width handling retains all
480 rows and cannot by itself explain a whole missing row.

## Proven timing mismatch: VSYNC bypasses the packed output pipeline

Top `hdmi_ddr_ov5640_top.v:321` registers the sensor inputs once on PCLK,
and its consumer connections at lines 371 and 377 use `cmos*_vsync_d0` directly.
Packed data and DE pass through three pixel-clock registers (bytepacker
lines 125-133); VSYNC does not follow that pipeline.

Cases 11-15 move the next raw VSYNC rise toward the final HREF falling edge:

| Raw VSYNC after raw HREF ends, PCLK periods | Post-update DE samples under VSYNC | Downstream synchronous samples under VSYNC |
| ---: | ---: | ---: |
| 0 | 3 | 4 |
| 1 | 2 | 3 |
| 2 | 2 | 3 |
| 4 | 1 | 2 |
| 8 | 0 | 0 |

The downstream column samples the old output registers at the pixel-clock
edge, as synchronous RTL consumers do. The packed DE falling transition is
65 or 75 ns after raw HREF falls in this test (the logged 66/76 ns includes
the scoreboard's 1-ns post-update observation delay). Close VSYNC can therefore
mark a frame boundary while valid tail pixels are still arriving. The packer
itself still produces 307200 correct pixels in every boundary case. Whether a
consumer discards them depends on that consumer; no merge behavior was tested.
The demonstrated loss exposure is a few pixels, not 640 pixels. Normal long
vertical blanking removes this overlap. Hardware blanking was not measured.

## Source shortages reproduce the observed totals exactly

| Case | Source HREF rows and widths | Output count | Data errors |
| ---: | --- | ---: | ---: |
| 16 | 479 x 1280 bytes | 306560 | 0 |
| 17 | 478 x 1280 + one 1000-byte row | 306420 | 0 |
| 18 | 478 x 1280 + one 1192-byte row | 306516 | 0 |

CAM5 is exactly `479*640`. CAM6's range is 44-140 pixels below that baseline,
equivalent to another 88-280 missing bytes after a whole-row shortage. These
are demonstrated source patterns consistent with the totals, not proof of
the actual sensor/cable cause. Counts alone also cannot distinguish missing
source HREF from later whole-row exclusion. Ordinary complete-row divider
phase variation is excluded by the clean tests. Merely shortening every 17th
row by one byte produces counts around 307185, not the observed CAM6 range.

The bytepacker has no FIFO and no overflow signal; these source-shortage cases
require no overflow mechanism.

## Relevant sensor configuration and limits

The final register table in `source/rtl/reg_config.v` writes:

- `0x4300=0x60`, `0x501f=0x01`: RGB565/RGB output selection.
- `0x3808/09=0x0280`, `0x380a/0b=0x01e0`: 640 x 480 output dimensions.
- `0x380c/0d=0x07d0`, `0x380e/0f=0x02c1`: HTS 2000, VTS 705.
- `0x3814/15=0x31`, crop x=672..1951 and y=492..1451.
- `0x4713=0x03`, `0x460b=0x37`, `0x460c=0x20`, `0x3824=0x04`.

The programmed dimensions require 1280 active bytes per 640-pixel RGB565 row;
they do not request 479 rows or an odd byte width. Register source and comments
are not sensor readback or a pin timing measurement. No sensor configuration
defect is proven here. Capture raw PCLK-sampled HREF widths, HREF row count,
and VSYNC-to-HREF spacing on each affected camera to distinguish the source
shortage hypothesis from downstream row exclusion.

No production files were edited. SHA256 of inspected production files:

```text
cmos_8_16bit.v:
b9514a3fdfa3f59283a3e6e641e0ee083c9a079ec550a8340c6628e0efde8466
hdmi_ddr_ov5640_top.v:
df33b465d35598a6cce04f23293a632faaec504119756007c289d23c0f2e720b
reg_config.v:
572b5344a23f2cee6e31c6161b0f976402488ecf13f3259b37f004049fd60822
```
