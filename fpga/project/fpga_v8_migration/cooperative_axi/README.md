# Isolated RAW frame AXI candidate

The physical 256 MiB address correction is promoted into
`fpga_v8_raw_frame_axi.v`. `address_fix/` retains the uniquely named staged
copy, promotion patch, and previous test artifacts as history. The completed
`component_synthesis` run used the pre-correction bridge hash and is stale;
it must be rerun for the promoted RTL. No new PDS run is started by promotion.

`fpga_v8_raw_frame_axi.v` is a standalone candidate, with distinct 128-bit AXI4
read and write interfaces. It instantiates the existing, read-only
`../raw_preprocess/fpga_v8_raw_letterbox.v` and
`../raw_preprocess/fpga_v8_rgb888_pack128.v`. No board/source RTL, DDR IP, PDS
project, or existing preprocessing file is changed. It is not registered in
the board project. Protocol/source integration belongs to the parent task.

## Command and completion interface

All signals use `clk` and active-low `rst_n`.

| Signal | Meaning |
| --- | --- |
| `cmd_valid`, `cmd_ready` | Command handshake; ready only when the bridge and pipeline are idle. |
| `cmd_src_addr[31:0]` | First byte of contiguous source RGB565. |
| `cmd_dst_addr[31:0]` | First byte of output contiguous NHWC RGB888. |
| `cmd_frame_id[31:0]` | Identifier captured on command acceptance. |
| `active_src_addr`, `active_dst_addr`, `active_frame_id` | Snapshots of the accepted command; later input changes do not affect it. |
| `busy` | Accepted, valid frame is in progress, including its final B wait. |
| `cmd_error` | One-cycle rejection indication for each invalid command handshake; no AXI traffic and no `done`. |
| `error` | Sticky command/frame error; cleared by reset or the next accepted valid command. |
| `done` | One-cycle indication that a valid command has fully retired, including a failed frame. |
| `completed_frame_id[31:0]` | Last retired valid command's ID, updated on `done`, including errored frames. |

**Publish the destination only when `done && !error`.** `done` means transaction
retirement, not success. A final B error is visible in `error` before `done`.
An invalid command updates the active snapshots, leaves `busy` low, sets
`error`/`cmd_error`, and leaves `completed_frame_id` unchanged. Keeping
`cmd_valid` high while idle submits a command on every ready/valid handshake.

Defaults: `WIDTH=640`, `HEIGHT=480`, `OUT_HEIGHT=640`, `TOP_ROWS=80`,
`FILL_VALUE=114`, `ID_WIDTH=4`, `AXI_ID=1`,
`DDR_ADDRESS_LIMIT=32'h10000000`. The top padding parameter uses the
shared letterbox module's name `TOP_ROWS`. Output width equals source width;
this pipeline pads and expands RGB565, without resizing.

## Byte layout and AXI behavior

Each source pixel is a little-endian RGB565 word: low byte first, then high
byte. A 128-bit R word contains eight pixels, with its first pixel in bits
15:0. The last R word may contain fewer than eight meaningful pixels. The
serializer consumes exactly `WIDTH * HEIGHT` pixels and generates the source
`s_last` from that count, independently of AXI `RLAST`.

Output bytes are R, G, B for each pixel, in row order. RGB565 channels use bit
replication (5-to-8 and 6-to-8 expansion). Top and bottom rows contain three
copies of `FILL_VALUE` per pixel. Default source length is 614,400 bytes;
default output length is 1,228,800 bytes. `m_keep` becomes `WSTRB`; unused lanes
of the final destination word remain untouched.

Ports use prefixes `m_axi_read_ar*`, `m_axi_read_r*`, `m_axi_write_aw*`,
`m_axi_write_w*`, and `m_axi_write_b*`. AXI4 W has no WID. Both address ports
have LEN=0, SIZE=4, BURST=INCR, LOCK=0, CACHE=3, PROT=0, QOS=0, REGION=0,
and constant ID=`AXI_ID`. WLAST is asserted for every single-beat write.
16-byte alignment makes each single beat stay within a 4 KiB boundary.

The reader allows one outstanding AR and issues it only with a free
serializer. It holds ARVALID/address through AR backpressure and accepts R
only when the serializer is free. A received R word is buffered before RGB
output consumes it, so padding/output stalls do not reserve a DDR read
transaction while waiting for output generation.

The writer captures a packed valid word before asserting AWVALID. It accepts
AW first, holds WVALID/data/strobes until WREADY, and waits for B before the
next AW. Packed data may wait in the pipeline while B is pending. `done` and
the next command remain blocked until the final B has been accepted and all
pipeline/read/write state is idle.

Wrong RID, non-OKAY RRESP, or missing RLAST on any single-beat R set sticky
`error`. Wrong BID or non-OKAY BRESP also set it. The bridge continues the
configured frame and drains all its requested transactions. It does not use
an erroneous RLAST as the image boundary. Responses are counted per requested
single beat; an AXI slave that invents extra beats or omits responses requires
system-level recovery. There is no transaction timeout in this candidate.

## Validation and reset contract

Commands require 16-byte source and destination alignment. Address footprints
are `ceil(WIDTH*HEIGHT*2/16)*16` and
`ceil(WIDTH*OUT_HEIGHT*3/16)*16`. Their half-open ranges must not overlap, and
each base plus footprint must be at most `DDR_ADDRESS_LIMIT`, without 32-bit
wrap. The bridge defaults this 32-bit parameter to
`0x10000000` (256 MiB). Valid overrides are nonzero, 16-byte aligned, and at
most `0x10000000`; `0x20000000` is an invalid override on this board.
Wide arithmetic prevents overflow during validation. Exact upper-limit and
adjacent disjoint ranges are allowed. Invalid geometry, padding, fill, ID
width, or oversized footprints also reject the command before AXI traffic.

Diagnostic: live `project/source/top.v:626` assigns
`ddr3_aw_addr <= ddr_axi_awaddr[27:0]`, and line 647 assigns
`ddr3_ar_addr <= ddr_axi_araddr[27:0]`. The crossbar's 512 MiB decode does not
preserve address bit 28 at the DDR adapter. For example, `0x10001000` aliases
to `0x00001000`. The promoted bridge rejects this alias address for either
source or destination, and rejects the old `0x20000000` boundary.

**Reset while AXI is outstanding requires common reset of this bridge and
the AXI interconnect/slave.** A bridge-only reset cannot cancel requests
already accepted by a slave, and IDs are reused. The regression resets both
the bridge and behavioral slave while AR is stalled, R is pending, AW is
stalled, W is stalled, and the final B is delayed, then verifies clean restart
and absence of ghost completion.

## Exact ModelSim regression

From this directory in PowerShell:

```powershell
& 'C:/Users/NineSun/anaconda3/python.exe' run_tests.py
```

`MODELSIM_BIN` overrides the default
`C:/modeltech64_10.6e/win64`. `--small-only` skips the full baseline. Python
uses only standard-library modules. Each case receives its own ModelSim work
library under `artifacts/`, and compiles the shared modules from their original
paths. The independent Python golden model imports neither shared golden
code nor RTL-derived data. The AXI memory testbench compares every strobed
byte, verifies final unstrobed/guard bytes, then Python compares every dumped
destination byte again. Unused source lanes are poisoned.

The runner requires the explicit pass marker and rejects simulator errors;
exit status alone is insufficient because ModelSim treats `$finish` as a
break with `-onfinish stop`. Exact compile/simulation argument lists, tested
module/source hashes, shared RTL hashes, output SHA-256 hashes, byte counts,
cycle counts, stale synthesis status, and pass markers
are recorded in `artifacts/results.json`. Each case also retains `run.do`,
`transcript.log`, console logs, input/golden vectors, and output dumps.

Coverage includes 4x3 input to 4x5 output with four meaningful pixels in the
last R beat and a 12-byte final W beat; a 1x1-to-1x6 case with a final pixel
spanning two packed words and a 2-byte final W beat; default 640x480-to-640x640;
three successive clean frames; RID/RRESP/RLAST/BID/BRESP errors; alignment,
overlap, range and wrap rejection; command snapshots; AR/AW/W stalls; R/B
bubbles; five common-reset phases; and an 80-cycle final-B delay.

The full promoted suite passes 49 retired frames, 1,231,008 compared bytes,
45 address-command rejections, and eight invalid parameter configurations.
It tests exact source/destination ends at `0x10000000`, rejection of aliases
and invalid limit overrides, and a legal smaller limit of `0x02000000`.
The previous component synthesis used bridge SHA-256
`235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40`;
the promoted bridge SHA-256 is
`c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f`.
Rerun isolated component compile/synthesis before relying on its result for
the physical address correction.

Simulation cycles describe only this behavioral memory model. No DDR board
throughput, timing closure, or speedup result is claimed.
