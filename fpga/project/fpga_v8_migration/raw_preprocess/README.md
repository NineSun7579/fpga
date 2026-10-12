# Isolated RAW inference preprocessing

This directory contains standalone Verilog-2001 ASCII RTL and ModelSim tests.
Neither module is connected to production top, DDR, PCIe, KF, or a PDS project.
The intended stream is unsigned NHWC RGB bytes for an RK3568 inference input.
There is no resize, normalization, convolution, or camera metadata filtering.

## Letterbox interface

`fpga_v8_raw_letterbox` has static parameters `WIDTH=640`, `HEIGHT=480`,
`OUT_HEIGHT=640`, `TOP_ROWS=80`, and `FILL_VALUE=114`. Output width equals source
width. Bottom padding is `OUT_HEIGHT - HEIGHT - TOP_ROWS`. Each padding pixel
contains the fill value in all three channels. Input `s_data[15:0]` is an
already assembled RGB565 word from little-endian host/source bytes. Expansion
matches `per_camera_fps/swap/src/rgb565_convert.h` exactly:

```
R = (r5 << 3) | (r5 >> 2)
G = (g6 << 2) | (g6 >> 4)
B = (b5 << 3) | (b5 >> 2)
m_data[23:0] = {B, G, R}
```

Assert `start_valid` and hold it until `start_ready` to command one frame.
`busy` starts on that handshake and blocks subsequent commands. No source data
is consumed before a command or to generate top/bottom padding. `s_ready`
is blocked while the next pixel to generate is padding. With the elastic
register, the first body pixel can be accepted on the same edge that consumes
the last top padding pixel, retaining continuous output throughput. The source must
present exactly `WIDTH * HEIGHT` pixels and assert `s_last` only on the final
one. An early marker or a missing marker at the configured boundary sets
`frame_error`; dimensions, rather than the marker, control all frame counts.
The error stays set through frame completion and idle, and clears on the next
accepted command or reset. A late surplus pixel is not accepted into that
frame; the caller must remove it before commanding another frame.

`m_last` accompanies only the final output pixel, including the last bottom
padding pixel when bottom padding is present. The one-word elastic output
register holds `m_data`, `m_last`, and `m_valid` stable under backpressure.
`done` pulses for one clock only when that final 24-bit output is accepted;
`busy` clears at the same edge. `start_ready` then rises, allowing the next
command on the following clock edge. At continuous ready/valid, the module emits one
pixel per clock, including at the padding/body transitions.

Valid geometry is `1 <= WIDTH <= 65535`, `1 <= HEIGHT <= OUT_HEIGHT <= 65535`,
`0 <= TOP_ROWS <= OUT_HEIGHT - HEIGHT`, and `0 <= FILL_VALUE <= 255`.
Invalid parameters print a simulation diagnostic at elaboration/time zero and
assert constant `config_error`; runtime commands are safely rejected with
`start_ready=0`, so no frame starts. Geometry is configured by parameters,
not by per-frame command fields.

## Byte packer and downstream completion

`fpga_v8_rgb888_pack128` accepts `{B,G,R}` pixels, appends bytes in `R,G,B`
order, and emits 128-bit words with the first byte in bits `[7:0]`. RGB pixels
may straddle word boundaries; carry bytes are retained without per-pixel or
per-row alignment padding. `m_keep[15:0]` marks valid byte lanes, low bits
first. Full words have `keep=ffff`; the final partial word has a contiguous
low-bit mask and zeroed invalid lanes. Those lanes must not be written to DDR.
`m_last` identifies the final word of each nonempty frame.

Full-ready throughput is one input pixel per clock within a frame and one
output word per 16 RGB bytes (alternating five/six pixel intervals). A final
pixel that crosses a word boundary emits a full non-final word followed by
a one/two-byte final word. The packer blocks a subsequent frame until its
final word has been consumed, preventing frame bytes from mixing. It holds
all output fields stable while stalled and creates no output for an empty
stream. Empty frames cannot be represented by this pixel interface.

Connect the letterbox's 24-bit ready/valid/last stream directly to the packer
as demonstrated only in the testbench. The letterbox's `done` means its final
pixel was accepted **by the packer**, which can precede consumption of the
final 128-bit word. A future DDR wrapper must use `m_valid && m_ready && m_last`
at the packer output (and the writer's actual completion protocol if needed)
to track packed-frame completion. No DDR writer or address generator is
included. Reset `rst_n` is asynchronous active-low on both modules; reset the
entire pipeline together to abandon pending pixels, words, and partial bytes.

This ready/valid interface requires the producer to hold data/valid/last
until accepted. It deliberately uses the new isolated protocol requested
for this block; legacy display preprocess's single-pulse/extra-dummy-pixel
protocol is not its interface.

## Reproduce validation

From this directory:

```powershell
python run_tests.py
python run_tests.py --quick
python run_tests.py --modelsim-bin C:/modeltech64_10.6e/win64
```

The runner uses only the Python standard library. It compiles with ModelSim's
`-vlog01compat`, generates independent integer golden pixels/bytes, checks
every accepted 24-bit pixel and 128-bit word in simulation, then independently
reconstructs the output byte stream in Python. All generated vectors,
simulator libraries, logs, and reports remain under `artifacts/` here.
`artifacts/report.json` records exact-byte counts, frame hashes, and measured
cycles. Simulator results are not FPGA timing closure, resource estimates,
board validation, DDR throughput, or an FPS claim.

Coverage includes default 640x480 to 640x640 full frames and sequential frames,
deterministic random source/output bubbles, distinct RGB565 colors covering
all 65536 input codes in each full frame, literal RAW `0x464b`, odd 4x3 to 4x5
frames (60 bytes, final `keep=0fff`), 2x2 without padding (12 bytes,
`keep=0fff`), padding fill variants, all packer remainder positions using
33 sequential frames of 1..33 pixels, sticky early/late marker errors,
invalid geometry/fill rejection, and clean restart after reset with pending
integrated outputs, carry bytes, an overflowing final word, or a final
partial word. Tests include a stalled final 24-bit padding pixel to verify
that letterbox `done` waits for that handshake.
