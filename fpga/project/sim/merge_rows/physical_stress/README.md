# Actual 235509 merge audit and B input stress

Verified against `bitstream_final_50k_20261002_235509/input_sha256.json`:
current cam2_merge.v, cmos_8_16bit.v, hdmi_ddr_ov5640_top.v,
reg_config.v, sccb_diag.v, sccb_read_probe.v, video_async_fifo.v and
sfp_video_tx.v all match the archived build inputs. Archived sources.zip
top also equals the current top byte for byte. Production RTL/PDS untouched.

Run `powershell -ExecutionPolicy Bypass -File run_all.ps1` here.
Uses real production capture/merge/FIFO and Pango GTP_IOCLKBUF/IOCLKDIV
simulation primitives. Includes the top's data/HREF/VS input register stage.
Independent sensor clocks: A 11.9045 ns, B 11.900 or 11.920 ns;
merge output 16 ns (62.5 MHz). Two 640x480 frames per case.

| Case | B captured pixels, two frames | Malformed B FIFO rows | Real/repeated output B rows | Result |
|---|---:|---:|---:|---|
| Drop last 200 B pixels each frame | 614000 | 2 | 958/2 | PASS |
| Partial B rows, slower B clock, 7.3 ns start shift | 600537 | 138 | 820/140 | PASS |
| B VS asserted immediately at final HREF fall | 614400 | 2 | 958/2 | PASS |
| Odd 1279-byte B HREF every seventh row, 5.9 ns shift | 614262 | 138 | 822/138 | PASS |

All eight published frames: A=307200, B=307200, merged=614400,
480 continuous 1280-clock DE rows, zero scoreboard errors and zero FIFO
overflow. Saved-row contents checked after every eligible row.
Early-VS case checks counts, A content and B snapshot consistency; its
real B source-content comparison is disabled because deliberately truncated
FIFO acceptance differs from the capture-side good-row queue.

## Structural result

cam2_merge.v lines 336-379: S_RD_A always runs 640 clocks, then S_RD_B
always runs 640 clocks, irrespective of b_ready/b_rep/b_vs/b_de. The B
choice only selects real memory versus saved memory/black. c_de stays high
through both segments. At 480 completed pairs, lines 406-416 assert c_vs
with c_de low. No sensor VS signal resets or interrupts the output FSM.
Consequently, absent output reset, timing failure or hardware corruption,
every published merge frame has equal A/B counts. Missing A rows can delay
publication, but cannot create a completed frame with a short B segment.

Early sensor VS can clear b_line_ok before delayed B DE drains (lines
105-119), truncating the FIFO row. The early-VS test exercises exactly this:
capture itself has 640 pixels, FIFO rows become malformed, and full-length
saved B rows are published. Thus this boundary affects content, not count.

## Wiring/configuration

Top lines 342-378: A/B have symmetric one-stage input registers and use
the same cmos_8_16bit module. Each capture uses its own PCLK, HREF, data,
VS and config-done; merge lines 401-411 connect the corresponding capture
DE/data/clock and input-registered sensor VS. No cross-wired A/B sync.
The direct sensor VS is earlier than the delayed output DE on both sides.

cmos_8_16bit lines 60-75: both use GATE_EN FALSE and DIV_FACTOR 2.
enble is latched after configuration at a sensor VS rising edge; divider
phase can differ independently. cnt resets whenever HREF is low. Odd HREF
can alter capture DE length or last pixel content; the merge rejects
non-640 FIFO rows and still publishes full B output segments.

Both reg_config instances use identical module/defaults and shared
clk_25M/initial_en; each issues indices 0..356 (357 commands) to 0x78.
Final geometry 640x480, HTS=2000, VTS=705, 3035=21, 3036=69,
3824=04, 4300=60. Identical command tables do not prove sensor ACK or
actual resulting register state. SCCB diagnostics read 300A/300B/4300;
their write-address phase sends only device/register address, followed
by read address and data reception, with no register-value write byte.

No u_delay, wire_data or GTP_IODELAY instance exists in the active 50K
source tree or archived top. Such names cannot explain an A/B delay
asymmetry in this image without new netlist evidence.

## Necessary next diagnostics

The board report independently confirms CAM5 29.7738 fps while CAM6
never publishes (tag FFFFFFFF). A CAM6 count of 306938..306970 is not
explained by ordinary B sensor pixel shortage through this merge.
Localize after merge before declaring the physical RX link the cause:

1. Count DE at merge output and pixel words at TX, per generated c_vs.
   Expected 614400 pixels / 307200 two-pixel payload words per frame.
2. Count RX decoded payload pixels before A/B routing and inspect final
   combined pixel index. Compare the first missing/extra word position to
   x=640 camera selection and the last B segment/frame boundary.
3. Record TX FIFO overflow/link_ready transitions and RX decode/disparity,
   PCS alignment, reset, overflow/rejection counters over the same interval.
4. Compare RX combined count against routed CAM5/CAM6 counts. Full RX
   count with B short localizes to routing/accounting or frame publication;
   short RX count with full TX localizes to link/decoder/transport.

These RTL simulations establish the merge contract; they do not model
analog DVP setup/hold, metastability, placed-netlist faults or physical
HSST transport. Do not infer RX-only failure from merge simulation alone.
