# FPGA-compressed C3/C4 with six-camera 200% display

## User acceptance

- Keep six cameras in the existing 3x2 layout.
- FPGA reduces C3/C4 from 640x480 to 320x240 with a 2x2 mean before DDR writes.
- Host image DMA requests for C3/C4 must be 153600 pixel bytes plus the existing 16-byte frame-tag beat; no 640x480 RAW requests for these cameras.
- GPU expands each 320x240 texture into its original logical 640x480 tile: width and height each 200%, original 4:3 aspect preserved.
- C1/C2/C5/C6 keep their original 640x480 acquisition/display.
- One YOLO input includes both compressed cameras as 640x240 plus 120 gray rows above/below, giving 640x480.
- Validate six panes, on-wire geometry/payload receipts, pixel composition parity, fresh capture/display/inference FPS and sustained errors.

## Implementation

The isolated source tree starts from the verified integrated_six_batch SRAM candidate. All vendor IP resources are copied unchanged from the matching tested source tree. The main workspace RTL/project edits made during initial exploration have been restored; the independent candidate owns further changes.

C3/C4 CAM_DATA_LEN=9600 128-bit beats. Existing DDR tag publication logic is reused at base+153600. The downsampler indexes rows by accepted valid pixels rather than async HS timing and drops source dummy pixels after 307200 accepted pixels. Read-only camera page registers +0x140..0x170 report C342 magic, H/W, frame bytes, row stride. New host requires C3/C4 metadata to match literal compressed geometry before starting acquisition.

## Evidence stages

Full raster golden simulation checks three complete 640x480 frames, arbitrary valid/HS gaps, dummy tails and reset after an interrupted frame. Real ov5640_ddr + AXI DMA simulation verifies compressed data, tag offset, no short-frame commit and no publication before actual B response. Register simulation verifies compressed read-only geometry.

Six RK3568 selftest groups are retained; the wire-input test rejects full-size RAW buffers. New viewer frames read the compressed bytes directly; there is no additional host reduction before inference/display.

Only an image with passing post-route AND detailed timing reports may be generated/deployed. First seed3 route failed existing cam5/6 setup and cam1 diagnostic hold paths; this result is archived and unprogrammed. Seed4 is a physical rerun with unchanged source and timing constraints. Original SPI Flash and installed viewer remain preserved; rollout is SRAM only with precise current owner retirement and a recorded restore recipe.
