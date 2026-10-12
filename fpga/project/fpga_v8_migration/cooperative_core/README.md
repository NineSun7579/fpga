# Isolated cooperative core candidate

`fpga_v8_cooperative_core.v` is an ASCII Verilog-2001 internal-IO wrapper.
It connects the existing, read-only leased-input control module, promoted RAW
frame bridge, and seven-writer arbiter. Neither production RTL, generated IP,
PDS projects, board programs nor host applications are changed.

All interfaces share `core_clk` and common active-low `rst_n`. The actual
`fpga_v8_ddr_write_arbiter` interface has synchronous active-low `rst_n`, as
confirmed in its RTL and README. The wrapper therefore connects `rst_n`
directly. The initial request's active-high reset description does not match
this completed dependency API. Hold reset through clock edges and reset all
external camera writers, lease bookkeeping, AXI interconnect and DDR slave/glue
together if traffic is outstanding. Reset does not drain old AXI transactions.

The wrapper's default geometry is 640x480 RGB565 input to 640x640 RGB888 output,
with 80 top rows and fill byte 114. The output-bank addresses default to
`0x08000000` and `0x08200000`; the bridge receives an explicit
`DDR_ADDRESS_LIMIT=0x10000000` (physical 256 MiB). The bridge validates command
alignment, source/destination disjointness, and the full rounded bus footprints
before issuing traffic. Invalid output addresses reject the command; the
control module frees the destination and holds the existing input lease release
until acknowledged. Camera write addresses remain the external writers'
responsibility; the bridge's range validator does not filter camera traffic.
Configured output-bank bus footprints must be mutually disjoint and reserved
from all camera/other allocations. This wrapper does not validate the two bank
ranges against each other or against external allocations; those are allocator
preconditions. It checks each command's physical range through the bridge.

`input_*` is externally certified metadata for an EXISTING stable RAW source
lease. Acceptance transfers that lease; it does not create or freeze a camera
buffer. The full source address, sequence, generation, camera, camera bank and
64-bit token return through `src_release_*` after bridge transaction retirement.
An external owner must keep the source bytes immutable until the release
handshake, and must handle reset reconciliation. `input_reject` does not take a
lease. The wrapper makes no claim that original camera RAW frames are stable.

`camera_*` exposes six packed complete AXI4 write channels, m0..m5. Slot i is
`[i*FIELD_WIDTH +: FIELD_WIDTH]` and m0 is least significant. Their widths are
six times ID=4, address=32, LEN=8, SIZE=3, BURST=2, LOCK=1, CACHE=4, PROT=3,
QOS=4, REGION=4, DATA=128, STRB=16 and RESP=2. The bridge occupies internal m6.
All fields, including full BID/BRESP and QOS/REGION, are connected explicitly.
There is no WID. Cameras must stage their complete burst before AW, or provide
equivalent staging that guarantees data without waiting for future pixels.
The bridge captures a complete output word before its single-beat AW.

`m_axi_write_*` is the arbiter's complete single DDR AW/W/B interface.
`m_axi_read_*` is the complete bridge AR/R interface forwarded directly with
4-bit IDs, suitable for a future crossbar S02 connection after system review.
The wrapper creates no crossbar connection or additional host DDR reader.
`s_axil_*` is a local 32-bit AXI-Lite endpoint; its addresses pass directly to
the controller without a BAR/window decoder. This is not installed in PCIe.

The controller's local register map remains the dependency's map:

| Offset | Use |
| --- | --- |
| `0x00/04/08` | Device ID, status, version |
| `0x0c` | Oldest READY bank, or `0xffffffff` |
| `0x30` write | CLAIM specified oldest READY bank (0 or 1) |
| `0x10..38` read | Descriptor bound to current host claim |
| `0x40/44/48` write | Stage ACK bank, source sequence, generation |
| `0x4c` write bit 0 | ACK; free only the matching HOST_READING bank |
| `0x50..6c` read | Counters and last error |

Host software must CLAIM, read the bound descriptor, copy every output byte,
and ACK with matching bank/sequence/generation. Stale ACKs return SLVERR and
retain ownership. This requires a host-side protocol implementation; the
current driver is not claimed to support it unchanged. Output-bank allocation,
DDR access arbitration and coherence, reset/CDC boundaries, address-window
installation, and physically safe production source leases remain external
integration work. The default output banks are candidate addresses, not a
confirmed production allocation.

Run the isolated regression from this directory in PowerShell:

```powershell
& '../.venv/Scripts/python.exe' run_tests.py
```

ModelSim defaults to `C:/modeltech64_10.6e/win64`; `MODELSIM_BIN` overrides it.
`--small-only` runs four directed/randomized small suites; repeat `--case NAME`
to select cases. RTL compiles in ModelSim's default Verilog-2001 mode and only
the testbench uses SystemVerilog. Generated work libraries, vectors, logs,
complete output/camera dumps and transaction traces stay under `artifacts/`.
No PDS process is invoked.

The behavioral DDR slave has 128-bit words and independent randomized AW, W,
B, AR and R stalls/delays. Six simultaneous camera streams issue staged
16/3/5/1-beat bursts into disjoint DDR regions. The full frame case uses 512
bursts per camera. An independent RR scoreboard checks selection from each
observed pending request mask; Python verifies the same trace's selection,
owner, full camera W word, beat counts and response IDs. Camera dumps include
every written byte and all unused burst slots as guards.

Every successful frame is copied from modeled DDR before ACK and dumped in
full. A Python RGB565-to-RGB888 bit-replication/letterbox oracle compares all
bytes, including all 1,228,800 bytes in the full case. The testbench also checks
every strobed output byte during writes, final partial strobes, unstrobed bytes,
guard bytes, valid payload stability and unknown control/data values.
Source memory is initialized with explicit little-endian source byte vectors;
unused lanes are poisoned. A source-lease scoreboard refuses memory reuse
before release.

Coverage includes two READY/owned outputs and input backpressure; stable CLAIM
metadata across processing of the other bank; stale sequence/generation ACKs;
last B held with no publication, claim or source release; independent host AW
and W acceptance orders; the next host AW/W asserted behind blocked B; the next
host AR asserted behind stalled R and simultaneous R/AR replacement;
RRESP/final-BRESP faults
that drain before freeing without publication; odd output lengths; invalid
physical output range; and common reset while AR/AW/W is stalled or final B is
outstanding. Behavioral host copies read the modeled DDR byte arrays directly;
they do not model PCIe DMA or a production host-memory path.

`artifacts/results.json` records exact commands, pass markers, byte counts,
cycles, dump hashes and SHA-256 hashes of all used RTL/test sources. Source
hashes are checked again after the complete regression. This evidence applies
to simulation only; no synthesis, timing closure, board throughput, production
buffer allocation, source lease implementation or installed endpoint is claimed.
