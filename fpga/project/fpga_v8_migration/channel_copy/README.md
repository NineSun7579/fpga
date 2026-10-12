# Isolated channel copy

`fpga_v8_channel_copy.v` is an ASCII Verilog-2001 hardware primitive. All
simulation files and results stay in this directory. It has no PDS, board,
production RTL, memory allocator, or model scheduler integration.

The source and destination byte contract is
`[row, column, channel_group, lane]` (HWC16): each word holds 16 uint8 lanes,
with lane 0 in bits `[7:0]` and lane 15 in bits `[127:120]`. The source stream
contains every group of pixel 0, then every group of pixel 1, in row order.
The destination stream contains the selected groups of each pixel in that
same order. This is a physical copy into an independent output stream; it
does not assume a channel slice can alias one contiguous source allocation.
The Python golden is independent of the migration's feature-layout codec.

The ready/valid command snapshots `cmd_total_pixels[31:0]`,
`cmd_groups_per_pixel[15:0]`, `cmd_first_group[15:0]`, and
`cmd_group_count[15:0]`. Pixels, groups, and count must be nonzero, and the
17-bit sum of first and count must be within groups. Invalid handshakes pulse
`cmd_error` for one cycle and leave the engine idle. Channels are naturally
aligned to groups of 16; this primitive does not slice individual lanes.

After a valid command, `busy` stays high until both the declared source word
count is consumed and the final selected output is accepted. `done` pulses
for one cycle, and the next command may be accepted after that pulse. Input
is disabled before a command and after its declared word count. Skipped
groups may be accepted while an output is stalled, but another selected
group requires output room. `m_data`, `m_last`, and `m_valid` remain stable
under backpressure. `m_last` marks the last selected group of the final pixel.

`s_last` must mark only the final declared source word. A mismatch on an
input handshake sets sticky `frame_error`; an early or missing/late marker
does not change counters, output selection, or completion. A marker presented
past the declared source count cannot be accepted without a new command.
`frame_error` clears on reset or acceptance of a valid new command. Invalid
commands preserve it. Active-low asynchronous `rst_n` clears the command,
pending output, completion, and errors, and gates both ready outputs.

Run from any directory:

```powershell
python C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/channel_copy/run_tests.py
```

The runner defaults to `C:/modeltech64_10.6e/win64`; use `--modelsim-bin` to
override it. It verifies all 14 ChannelViews against the read-only audit and
simulates their exact 80x80, 40x40, and 20x20 shapes, including both halves of
4, 8, and 16 source groups. Other cases cover first, second, middle, and full
selections; uneven groups/counts; random input bubbles/output stalls; live
command changes after acceptance; both orders of source/output completion;
malformed last; 16-bit group limits; invalid configurations; and reset with
selected output pending. All output words and last flags are checked in the
testbench, then every complete output byte sequence is checked again in
Python with explicit lengths. No truncated-prefix comparison is used.

`artifacts/test_results.json` records tool commands, hashes, case geometry,
complete byte counts, and protocol coverage. `artifacts/vsim.log` contains
the per-case simulation results; vectors and observed outputs are under
`artifacts/vectors/`.
