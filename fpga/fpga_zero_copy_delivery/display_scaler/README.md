# Isolated RGB565 display decimator

`rgb565_display_decimator.v` is a synthesizable, single-clock building block:
640x480 RGB565 raster input -> 320x240 RGB565 raster output. Output `(u,v)`
is exactly input `(2*u,2*v)`; RGB565 bits pass through unchanged. No frame
buffer, color conversion, interpolation, vendor IP, or dummy pixels are used.
The scaler now accepts even `WIDTH`/`HEIGHT` parameters (default 640/480).
The command-driven DDR endpoint described below wraps this same scaler.

## Interface and frame protocol

| Port | Contract |
| --- | --- |
| `clk`, `rst_n` | Rising-edge clock; asynchronous active-low reset. Deassert reset synchronously to `clk` in integration. |
| `s_pixel[15:0]`, `s_valid`, `s_ready` | Input transfers only on `s_valid && s_ready`. Source holds valid and payload unchanged until accepted. Bubbles do not advance coordinates. |
| `m_pixel[15:0]`, `m_valid`, `m_ready` | Output transfers only on `m_valid && m_ready`. Pixel, valid, and tags remain stable under backpressure. |
| `m_sof`, `m_eof` | Meaningful with `m_valid`; accompany the first and last selected output pixels. These are beat tags, held during stalls. |

The first accepted input after reset is `(0,0)`. Supply exactly **307,200
real pixels** per frame, row-major, with no stride padding or blanking beats.
The next accepted beat starts the next frame automatically. Frame separation
needs no idle cycles. There is no input SOF port or automatic recovery from
missing/extra pixels: reset and restart at a known frame boundary after an
abort or upstream frame loss. Reset discards a pending output and partial
frame; the receiver must also discard any partial frame.

Selected pixels have even x and even y. Output SOF accompanies input `(0,0)`;
output EOF accompanies input `(638,478)`. **641 input beats remain after this
selected pixel**, including the last odd row: consume them to preserve the
next frame's alignment. Output EOF means the thumbnail is complete, not that
the input frame has drained. Do not reset or change the source at output EOF.

The one-entry elastic output register can accept a replacement on the same
edge as an output handshake. A full, stalled output slot stops all input
beats, including pixels that would be discarded. There is at least one clock
of output latency. No full-frame buffering is required.

## Integration boundary

Instantiate only on a display branch with a handshake-capable source. A live
camera or the existing pulse-valid preprocessing pipeline cannot directly
obey this protocol: use an independently serviced DDR reader or a suitably
sized adapter/FIFO and a defined frame-drop policy. Do not propagate display
backpressure into the RAW/YOLO branch. Cross clock domains using an appropriate
CDC FIFO outside this module. Upstream ownership must preserve both consumers
when forking a stream.

This directory does not modify the integrated RTL, project registration,
driver, viewer, legacy FPGA NPU, or RK3568 YOLO path. Integration must handle
thumbnail storage, DMA lengths/metadata, host buffer sizes, and viewer layout;
fitting 320x240 thumbnails in the current viewer may require layout support.
The old FPGA NPU removal is a separate parent-session change.

Per camera frame the display payload is **614,400 -> 153,600 bytes**,
a potential saving of **460,800 bytes (75%)**. That saving applies only when
the integrated display transport actually sends thumbnails instead of full
frames. This isolated module does not establish reduced PCIe DMA traffic,
zero-copy integration, resource/timing closure, or measured delivered benefit.

## Reproduce the genuine ModelSim test

From this directory:

```powershell
python run_test.py
```

Default simulator: `C:/modeltech64_10.6e/win64`; override with `MODELSIM_BIN`.
Python generates all 921,600 real input pixels, compiles the RTL and SystemVerilog
testbench with ModelSim, then compares every accepted output pixel and both tags
against an independent CPU coordinate reference. Any simulator failure, missing
PASS, count mismatch, pixel mismatch, or tag mismatch fails the script.

The three complete frames cover continuous input/ready, deterministic randomized
ready and input bubbles, and 97-cycle ready blackouts mixed with random readiness.
The testbench asserts output stability during stalls and resets with pending
stalled output both at the first pixel and partway through a frame. Distinct
nonlinear pixel patterns catch stale frame data and coordinate errors. A watchdog
detects deadlocks. All 76,800 pixels per output frame are checked, including SOF
and EOF absence on every interior pixel and presence at both boundaries.

Recorded run: ModelSim SE-64 10.6e, 2026-10-09, passed 230,400 bit-exact output
pixels and tags; 245,504 input-stall cycles and 40,816 bubble cycles. Compilation
reported zero errors/warnings. Simulation reported zero errors and one installed
configuration warning about `-novopt` disabling optimizations.

Evidence is in `test_results/vlog.log`, `test_results/vsim.log`,
`test_results/cpu_compare.log`, and `test_results/summary.json`. Large generated
vectors, simulator libraries, and raw outputs are ignored and reproducible.

## DDR thumbnail endpoint

`display_thumbnail_ddr.v` has the same named command, completion, and AXI
ports as the verified `delivery_rgb_ddr` endpoint. Its only geometry
parameters are `WIDTH=640, HEIGHT=480`; each must be even and in 2..2048.
`config_error` is static for unsupported geometry and blocks commands.
`display_rgb565_pack128.v` packs eight RGB565 pixels into each 128-bit beat,
first pixel in bits 15:0. The final partial beat uses exact low-byte strobes;
there are no output padding pixels. The default output is 9,600 full beats,
600 write bursts, and 153,600 payload bytes.

The DDR reader buffers up to 16 128-bit beats and serializes their eight
RGB565 lanes into the scaler. The packer and write-side buffer assemble up
to 16 output beats. Read and write transactions each have at most one
outstanding burst; their channels can progress independently. AW and W can
handshake in either order. All request payloads remain stable under stalls.

### Command and completion mapping

| Interface | Integration mapping |
| --- | --- |
| `cmd_valid`, `cmd_ready` | Command accepted on their handshake while idle, fault-free, and configured. Do not pulse valid without observing ready. |
| `cmd_src[31:0]` | Native HMIC address of the frozen/owned camera RGB565 frame, in existing camera/PCIe burst-slot layout. Latched on acceptance. |
| `cmd_dst[31:0]` | Native HMIC base of an exclusively owned thumbnail destination, same burst-slot layout. Latched on acceptance. |
| `busy` | Remains asserted through all source-pixel consumption and response retirement. Invalid addresses complete with error without asserting busy or accessing DDR. |
| `done` | One-cycle command-completion pulse; success requires `!error`. Output EOF alone never completes a command. |
| `error` | Sticky for every address, RRESP, RLAST, or BRESP fault; no new command is accepted until coordinated reset. Fault completion means outstanding traffic has drained, not a valid image. |
| `config_error` | Geometry invalid; command is never accepted. |
| `m_axi_ar*`, `m_axi_r*` | Connect to the selected DDR read master path; 128-bit data, `ARSIZE=4`, `ARBURST=INCR`. |
| `m_axi_aw*`, `m_axi_w*`, `m_axi_b*` | Connect to the selected DDR write master path; 128-bit data, 16 byte strobes, `AWSIZE=4`, `AWBURST=INCR`. |

The parent can optionally select this endpoint versus RGB preprocessing
using a command-mode mux. Latch mode at the shared command handshake, assert
`cmd_valid` only to the selected endpoint, and route **all five AXI channels**
and response ready/valid signals using that latched selection until completion
and full retirement. Forward the selected `busy/done/error/config_error` to
the existing control interface. Do not change selection in response to the
live mode register during a command. A shared fault latch must block commands
to **both** endpoints after either reports an error until coordinated reset;
switching mode must not bypass quarantine. This directory supplies the endpoint
and mapping, not the parent-owned mux/MMIO/arbiter implementation.

### Native DDR addressing and allocation

This endpoint follows the verified reference
`fpga_acceleration_delivery/ddr_rgb_letterbox/rtl/delivery_rgb_ddr.v`
and `DDR_ADDRESS_FIX.md`. **Command and bus addresses are native 16-bit-word
units, not byte addresses.** Within a burst, each 128-bit beat advances eight
native words. Full bursts contain 16 beats, but the next burst starts **256
native units** later, matching the deployed camera writer and PCIe reader.
This leaves 256 payload bytes in each 512-physical-byte slot. It is not a
linear byte-addressed AXI image. The last partial burst has its real length.

Both bases must be 256-native-unit aligned. Checked source/destination
reservations are `ceil(input_pixels/128)*256` and
`ceil(output_pixels/128)*256` **native units**, respectively, including the
unused half-slots. The 33-bit end calculations must stay within the native
28-bit aperture `[0, 0x10000000)`. Reservations must not overlap; adjacent
reservations are allowed. Conservative whole-slot reservations protect short
frames and final partial bursts. These units must not be substituted with
ordinary byte-buffer offsets in an integrating allocator.

### Independent completion barriers and faults

Successful completion waits for all `WIDTH*HEIGHT` real input pixels to
handshake through the scaler, all reads to retire, and the final successful
B acknowledgement. With 640x480, EOF leaves 641 input pixels to consume.
Final B may arrive first, or input drain may finish first; both orderings
are explicitly tested. The receiver must publish a destination only on
`done && !error`. Double buffering, source freeze/ownership, publication,
and destination reuse fences belong to the parent integration.

On any fault, no more source pixels enter the reset pipeline, partial
unissued output is discarded, and announced AR/AW/W requests remain asserted
until accepted. Issued reads drain through RLAST and issued writes finish
all W beats and B. `done` with `error` occurs only after both engines retire.
An early RLAST is a fault and terminates that response; a missing expected
RLAST causes a fault but keeps RREADY asserted until actual RLAST. A response
that never arrives requires coordinated endpoint/fabric reset; there is no
unsafe timeout/retry that might leave stale responses for a new command.
Reset with outstanding traffic must reset or otherwise flush the fabric too.

## DDR ModelSim evidence

```powershell
python run_ddr_test.py
python run_test.py
```

The DDR runner compiles synthesizable RTL with `-vlog01compat`, then runs a
SystemVerilog DDR model in genuine ModelSim. The CPU constructs a physical
source memory fixture with poisoned unused half-slots. The model maps native
bus addresses to physical bytes (`address*2`), advances 16 physical bytes
within each burst, and applies writes to physical memory with byte strobes.
The CPU compares the resulting memory against an independently sampled RGB565
reference, including every unused slot, tail byte, and 64-byte guard. A naive
single-beat byte-stride implementation would read poison or corrupt guards.

Cases include full 640x480 with early final B, full 640x480 with independent
random AR/AW/W readiness and delayed R/B responses plus a 2,048-cycle final-B
hold, partial input/output bursts and partial final strobes, bad RRESP with
stalled announced AW/W, bad BRESP while a read is outstanding, early RLAST,
late RLAST, fault quarantine, coordinated reset/recovery, and unsupported
geometries. Each configured case also checks misaligned source/destination,
overlap, range/overflow rejection, no DDR traffic on invalid commands,
latched command addresses, and stable stalled request payloads.

Logs and CPU results are in `ddr_test_results/compile.log`,
`ddr_test_results/compile_tb.log`, per-case `simulation.log`, and `report.json`.
Large physical-memory fixtures and ModelSim libraries are ignored/reproducible.
This evidence covers isolated RTL behavior; no PDS, board, integrated traffic,
or measured throughput claim is made.
