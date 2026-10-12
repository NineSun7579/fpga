# Isolated capture host-control candidate

This directory adds two ASCII Verilog-2001 modules:
`fpga_v8_capture_control_axil` and `fpga_v8_coop_axil_router`. They provide
fresh-generation ARM and explicit host input-frame lease CLAIM/ACK behind
the finalized 128-bit endpoint. All authored and generated files stay here.
The existing cooperative endpoint, tests, artifacts, controller, capture
manager and wrapper are preserved byte-for-byte. No PDS, IP, production
source, SSH, DDR-adapter or physical board operation is performed.

## Fixed port API and chain

`port_api.json` lists exact port names, widths, directions and bindings.
The capture-control manager-facing names match
`../capture_lease/fpga_v8_capture_lease.v` exactly. Connect one common clock
to endpoint/router/capture control/manager and the cooperative controller's
`core_clk`. The bus/control modules use `rst_n`; the manager uses
`rst = !rst_n`. Reset must also cover the wrapper/FIFOs/DMA, bridge,
interconnect, host transactions and external lease recovery.

```
global full AXI128
  -> preserved fpga_v8_coop_axi128_endpoint
  -> fpga_v8_coop_axil_router.s_axil_*
       m0_axil_* -> existing fpga_v8_coop_control_axil.s_axil_*
       m1_axil_* -> fpga_v8_capture_control_axil.s_axil_*
                       <-> actual capture manager's matching named ports
```

Router child 0 receives **unsigned full local addresses below `0x100`**.
All other addresses go to child 1; capture control rejects anything outside
its exact known, aligned range. Addresses and PROT are forwarded unchanged,
without truncation or subtraction. Each AW snapshots its child route. W may
arrive first and is buffered; it cannot reach a child until the route is
known. Local AW/W handshakes then proceed independently in either order.
One B owner remains selected through the upstream B handshake. AR snapshots
its independent route, and one captured R owner remains selected through R
consumption. Read and write may target different children concurrently.
There is no cancellation or timeout.

Capture control has `LOCAL_BASE=0x00000100` and decodes all 32 documented
words in `0x100..0x17c`. Its AXI-Lite prefix is `s_axil_`; addresses and data
are 32 bits, strobes are 4 bits, and PROT is 3 bits, accepted and ignored.
AW and W have separate holding slots. B blocks new writes until consumed;
R independently snapshots the current accepted address and remains stable
under backpressure. Unknown or unaligned addresses and RO writes return
SLVERR, with zero on invalid reads. Writable staging words merge byte
strobes. Doorbells act only with low-byte strobe and data bit 0 set; higher
command bits are ignored. RAW CLAIM compares the complete low 32-bit bank
word, so only 0 or 1 can succeed. Zero-low-strobe writable accesses are
OKAY no-ops.

## Shared physical map

`register_map.json` is the machine-readable complete map, including STATUS
bits. The preserved AXI128 endpoint proposes global M02 base `0x40010000`
with a 4096-byte window. The parent must recover the existing NPU decode
and reserve `0x40010000..0x40010fff` without overlap before global acceptance.
This candidate makes no global reservation. Feed that endpoint the full
global address and preserve all seven ID bits including `010` route bits.

```
physical_address = 0x40010000 + 4 * local_offset
```

| Action | Local offset | Physical address |
| --- | --- | --- |
| CAPL device ID | `0x100` | `0x40010400` |
| STATUS | `0x104` | `0x40010410` |
| Stage generation | `0x10c` | `0x40010430` |
| ARM doorbell | `0x110` | `0x40010440` |
| Host RAW CLAIM | `0x114` | `0x40010450` |
| Bound RAW descriptor, eight words | `0x118..0x134` | `0x40010460..0x400104d0`, stride 16 |
| RAW ACK bank/seq/generation/token low/token high/camera | `0x138..0x14c` | `0x400104e0..0x40010530`, stride 16 |
| RAW ACK doorbell | `0x150` | `0x40010540` |
| Accepted generation | `0x170` | `0x400105c0` |

Use one 16-byte beat per register, `LEN=0`, `SIZE=4`, and FIXED or INCR burst.
Only the little-endian low 32 bits and four low strobes reach the selected
child; random high 96 bits and all 16 write strobes cannot access adjacent
registers. Reads return low 32 bits plus zero high 96 bits. The new router
does not alter the preserved endpoint's invalid-burst draining behavior.

STATUS bits 0..6 are armed, config_ok, protocol_fault, host_bound,
manager host_valid, config acknowledgement pending, and release
acknowledgement pending. Bits 7..9 are config_ready, host_release_ready and
epoch_start. Bit 10 reports the offered manager host bank when bit 4 is
set, giving software a selection hint before CLAIM. Higher bits are zero.
`0x16c` packs manager bank0 state in bits 1:0 and bank1 in 3:2;
FREE=0, WRITING=1, HELD=2. All live reads are snapshots.

## ARM and acknowledgement timing

After common reset the actual manager is unarmed; generation staging is
zero. The host must obtain a **fresh nonzero generation from a persistent
external allocator**, stage it at `0x10c`, and write bit 0 to `0x110`.
Neither module automatically allocates generations or remembers history
across reset/power loss. The manager rejects zero and its current generation
but cannot detect reuse of older epochs. Never reuse an epoch while an old
host/cooperative ACK could still arrive; define exhaustion/recovery policy
outside this hardware.

ARM rejects immediately with SLVERR if a host descriptor is bound or
`config_ready` is low. It queues no configuration behind outstanding leases
or engine work, so an ARM B cannot deadlock the same host's necessary RAW
ACK writes. Rejected attempts increment `0x15c`.

When ARM can dispatch, `config_valid` is combinational from **held AW/W
metadata and that edge's actual config_ready**. It handshakes on the dispatch
edge, with stable staged generation. No unaccepted configuration is queued.
The manager includes `config_valid` in `lease_block`, blocking source SOF
admission on that same edge. This avoids a registered-command gap in which
a new frame could reserve a bank after the ready decision. Connect manager
`epoch_start` to the actual idle wrapper's epoch restart.

After dispatch, capture control waits for the manager's registered
`config_accept` or `config_reject`. A ready handshake alone never causes an
OKAY B. Acceptance records the generation at `0x170`, increments accepted
config count `0x174`, and responds OKAY. Rejection increments `0x15c` and
responds SLVERR. The one pending write is retained without timeout until the
real acknowledgement is observed. STATUS and other reads remain available.

## Host input-frame CLAIM and exact RAW ACK

Wait for STATUS bit 4, select the offered bank from bit 10, and write its
full 32-bit value to `0x114`. A claim succeeds only when no descriptor is
already bound, the manager offer is valid, and the requested bank matches
the actual offer on the commit edge. The `host_ready` handshake captures
all eight descriptor words together: bank, sequence, generation, byte
length, source address, camera, token low and token high. These remain
immutable while another bank publishes, the offer changes, or the
cooperative consumer finishes. Before a claim, bound-bank reads return
`0xffffffff`; the other descriptor words return zero. `0x114` reads the
bound bank or `0xffffffff`, like `0x118`.

After finishing **all input-frame reads and host DMA**, stage the six full
ACK words at `0x138..0x14c` and ring `0x150`. The complete key must equal
the bound bank/sequence/generation/token/camera. High bits of staged bank
or camera words must be zero; there is no matching after truncation.
Offered-but-unclaimed descriptors, wrong keys and duplicate releases
produce immediate SLVERR and increment bad-ACK count `0x158`, without
emitting a manager release. A matched dispatch sends the captured bound
identity and waits for registered `host_release_accept/reject`. Acceptance
alone clears the bound descriptor and increments `0x178`; rejection keeps
it intact and increments `0x158`. READY alone never clears ownership.
The current manager token is `{generation,sequence}`; capture control
compares the exact captured 64-bit token rather than deriving or assuming
one from the ACK staging words.

The host source lease is independent of cooperative conversion. A source
bank remains HELD until **both** consumers have claimed and successfully
released it, in either order. Host ACK can clear host_bound while the source
bank is still HELD for cooperative work. Conversely, the cooperative bridge
may release its source while host RAW DMA is still reading. Output-bank
CLAIM/ACK remains the existing route-0 cooperative controller's operation.
Neither ACK certifies input validity or releases an unrelated bank.

Counters `0x154/0x158/0x15c` record rejected host claims, bad host ACKs and
rejected configs. `0x160/0x164/0x168` pass through manager publication,
retired-error and rejected-release counts. `0x174/0x178/0x17c` count accepted
configs, host releases and host claims. Common reset clears local and manager
counters; they wrap at 32 bits. No software clear is provided.

The existing host DMA ioctl may not propagate AXI BRESP. Until propagation
is proven, serialize writes and confirm them with reads: ARM must advance
accepted config count and accepted generation; CLAIM must set host_bound,
advance accepted claim count and bind the expected descriptor; RAW ACK must
clear host_bound and advance accepted release count without increasing bad
ACKs. A current FREE bank-state reading is not required, because another
consumer may still own it or a new capture may reserve it. Rejected counters
and bound identity provide explicit error evidence. Parent host-client work
must supply this confirmation policy and output/input DMA sequencing.

## Source and layout boundary

The test and API refer to an **incoming unfiltered RGB565 stream** whose
validity must be established by controlled parent integration. This work
does not assert a physical camera format, confirm the currently loaded
upstream image, or establish a camera-to-50K board path. Manager `input_raw_valid`
means its selected, correctly integrated source published successfully; it
does not independently inspect sensor/FIR format. Host cannot manufacture
`admitted_sof/publish/retired_error`: these must come from the actual wrapper
and its fully retired DMA/tag B events.

Defaults in the actual manager are two source bases `0x01800000/0x01a00000`,
640x480 RGB565, 614400 payload bytes plus a separate 16-byte tag, CAM_ID=4
as an integration index, HOST_REQUIRED=1, and **DDR_LIMIT=`0x10000000`**.
The parent must confirm actual DDR capacity, geometry, bank/tag bounds,
alignment, source/output/other-client nonoverlap, and the bridge's matching
source geometry. `DDR_LIMIT` is a manager parameter, not evidence of physical
capacity; do not increase it merely to bypass checks. Manager `config_ok`
reports its compile-time guards. Parent integration must keep wrapper/DMA/
manager parameters consistent and respect those guards. This controller
does not expose runtime bank address or geometry writes.

## Regression and isolation

Run `python run_tests.py` here. `MODELSIM_BIN` overrides the default
`C:\modeltech64_10.6e\win64`. All tools run under this directory's artifacts;
the finalized cooperative tests are not rerun or modified. Candidate RTL,
actual manager, actual cooperative controller and preserved AXI128 endpoint
compile without `-sv`; only the new TB is SystemVerilog.

The TB uses the real manager and controllers, with directed admitted-SOF,
publish and retired-error **contract events** and controlled bridge status.
It gates attempted SOF with the manager's actual `lease_block`, including
ARM's dispatch edge. This suite does not instantiate the camera/wrapper/
FIFO/DMA or inspect real frame bytes; the existing nine capture-lease suites
provide separate datapath evidence. No claim about frozen physical DDR
contents is made here; this suite checks held states and immutable lease
metadata. Full candidate stream/data integration remains with the parent.

The Python oracle creates expected transactions from host intent and source
event plans before simulation. Independent lease records, consumer obligations
and FIFO output ordering predict register data, command/release identities and
bank states. It never reads DUT hierarchy or derives expected identity from
DUT trace metadata. The public trace compares every full and routed AXI-Lite
handshake, manager command/accept/reject, host/cooperative descriptor claim,
release, and final ownership state. SV checks all public outputs for X/Z,
stable data/responses under stalls, stable manager offers before claim, route
ownership and delayed acknowledgement behavior. A documented downstream
token-corruption injection causes the real manager's release rejection;
that test checks propagation and retained bound metadata.

`artifacts/source_hashes_initial/before/after.json` audit every finalized
cooperative-endpoint file, including artifacts, plus parent controller,
manager and wrapper dependencies. `REPORT.md`, `artifacts/results.json`,
tool logs, planned/actual traces and comparison output retain the evidence.
This is isolated control-chain evidence; global decode, host driver behavior,
actual source stream/frame bytes, DDR capacity/content, CDC and hardware
timing require separate integration validation.
