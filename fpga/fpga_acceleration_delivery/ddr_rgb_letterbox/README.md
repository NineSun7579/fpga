# Isolated camera-DDR RGB letterbox candidate

Implemented in this directory only. Production source, IP, camera fixes,
constraints and PDS project are untouched. No PDS run, driver replacement,
board flash, FPGA measurement, or speedup claim accompanies this delivery.

## Concrete operation

`rtl/delivery_rgb_ddr.v` is a synthesizable Verilog-2001, single-clock,
128-bit AXI DDR master. One command contains aligned source and destination
addresses. It reads an already-completed camera RGB565 frame from DDR,
expands channels with bit replication, adds gray-114 letterbox rows, packs
contiguous NHWC RGB bytes, and writes a separate destination DDR allocation.
Default geometry is 640x480 -> 640x640, with 80 rows above and below. There
is no resize, signed-input conversion, metadata stripping, or H2F upload.

The expansion/packer are adapted from the existing migration raw_preprocess
blocks, with unique module names and equivalent datapath logic. The new work
is the actual reader, pixel unpacker, writer, transaction completion/fault
state machine, full DDR testbench and paired benchmark integration surface.

Source and output are each tightly packed by row. An input word contains
eight RGB565 pixels, first pixel in bits 15:0. The output order is R,G,B,
first byte in bits 7:0; pixels cross 128-bit boundaries without alignment
padding. WSTRB protects the final partial word. Round both allocations up
to 16 bytes; the reader may fetch unused source lanes in the final word.

## AXI and command contract

- Accept a command only on `cmd_valid && cmd_ready`. Addresses are latched.
- Address checks reject misalignment, overlapping rounded allocations, and
  ranges outside the current 256 MiB DDR aperture. Rejection emits `done`
  with `error` and issues no bus request. These checks do not establish
  ownership: software must reserve the destination and lease the source.
- Geometry is static, bounded to 2048 in each dimension. Invalid geometry
  asserts `config_error` and prevents commands.
- Single-beat INCR, ARLEN/AWLEN=0, ARSIZE/AWSIZE=4. At most one outstanding
  read and one outstanding write. AW and W can handshake in either order;
  their payloads persist independently under backpressure.
- `busy` remains asserted until the final destination word's B response.
  `done` is a one-cycle pulse; `error` persists until a new accepted command
  or reset. A software register wrapper must latch done/error for polling.
- Read/B errors or an invalid RLAST quarantine the endpoint: accepted
  outstanding requests drain, pending RGB is abandoned, and new commands
  remain disabled until coordinated reset. Failed output is not publishable.
- A missing response has no safe local retry or timeout cancellation.
  Reset must also reset/quiesce the connected AXI fabric and ownership
  protocol. Resetting only this endpoint with outstanding traffic is unsafe.
- Tie AXI IDs to a reserved constant at integration; this master has no
  interleaving. Tie lock/cache/prot/qos/user fields explicitly per crossbar
  contract. The current DDR bridge serializes reads and synthesizes B after
  the IP consumes write beats; final B is completion in that bridge's terms.

## Local evidence

Run `python run_tests.py` here (ModelSim defaults to
`C:/modeltech64_10.6e/win64`). `--quick` omits full-size cases.
`artifacts/report.json` and per-case simulation logs are generated evidence.

All eight cases passed. Both full-size cases compare every byte of two
640x640 RGB frames against an independent Python oracle: 2,457,600 bytes
per case. The source patterns cover every RGB565 code. Small cases cover
unaligned byte tails, final-pixel word overflow, no padding, address
rejection, read/B/last-marker faults, quarantine and coordinated restart.
The TB delays R/B, independently stalls AR/AW/W, checks stable payloads,
validates exact DDR addresses/counts, and rejects early completion.

The full-ready case took 1,126,427 simulated clock cycles for its entire
two-frame test including setup; full-stalls took 1,742,764. These are
testbench cycles, not measured FPGA latency or throughput. The regression
hashed 892 production source/IP/project files before and after: unchanged.
The new modules passed a byte-level collision scan against production RTL.
Integrated arbitration simulation is now available as described below. No
timing closure, resource estimate, hardware correctness or FPS evidence exists.

## Paired benchmark code

`host/paired_preprocess.cpp` uses the existing pinned RKNN model/runtime
identity checks in `fpga_v8_migration/cooperative_paired_bench/rknn_runner.hpp`.
Both arms use the SAME native output mode and decoder. It alternates arm
order, compares every RGB byte, compares detections, records frame identity
and SHA256 values, and emits JSONL timings only after successful teardown.
Its baseline is RAW DDR DMA + CPU conversion/letterbox + inference; its
candidate is FPGA DDR preprocessing + RGB DDR DMA + inference. Claim time
is included in both. This is per-frame latency accounting, not concurrent
viewer FPS. Warmups are excluded from report rows.

`host/linux_provider.cpp` now implements the real binding against the retained
`driver_ownership_audit/board_files/000_pango_pci_driver.c` and matching header,
using `cooperative_linux_transport/driver_abi.hpp` for the natural 40-byte ABI.
MAP cmd 0/1 allocates TX/RX windows; ioctl number 4 is H2F, number 5 is F2H.
The existing detview `pango_dev.h` confirms the mapping and register access.
The clone masks camera/NPU MSI requests exactly as the current top does, so this
binding does not enable the driver's asynchronous camera queue. RKNN source and
provider passed local Linux syntax checks; provider used `-Wall -Wextra -Werror`.
No Linux provider ioctl, inference run or board build occurred in this step.
The earlier RK3568 syntax receipt concerns the benchmark source alone.

This provider requires root to inspect every `/proc/*/fd` before opening the
driver, rejects any existing owner, and holds `/run/lock/delivery-pango.lock`.
Parent must stop viewers and prevent other clients from starting for the whole
run; the advisory lock cannot exclude a client which ignores it. It checks actual
DLV2 MMIO identity/geometry, reads camera 1..4 bank registers for destination
overlap, freezes cam5 and reads its published frame tag. It validates the hold,
bank and generation around both readbacks. A job counter prevents an old sticky
done bit from satisfying a new submission. Signature is hardware register data,
not a claimed bitstream SHA or an evidence boolean.

On uncertainty, `quarantine()` raises SIGSTOP and retains the fd/mappings.
The retained driver's release frees global DMA memory; parent must quiesce/reset
hardware before resuming/terminating a quarantined process. No replay or automatic
capture resume occurs. Ordinary successful completion unmaps and closes.
Existing cooperative Linux transport itself remains unbound.

Build on RK3568 with the board's actual Qt/RKNN development environment, explicit
`MIGRATION_ROOT` and `RKNN_RUNTIME` CMake arguments. The provider defaults to
`linux_provider.cpp`; RKNN headers resolve from the retained
`current_viewer_native_candidate_02/src` snapshot. Run
`paired_preprocess PINNED_MODEL 10 100` with exclusive hardware ownership.
Record the exact build sources and flashed bitstream SHA independently.

## Wired isolated PDS project

Open `integrated/project/project.pds` for the parent's coordinated PDS run.
`python build_integration.py` reproduces the clone from current production bytes,
copies source/IP/constraints, adds five delivery modules, and verifies source
references and production hashes. Do not regenerate after reviewing a baseline
without reviewing the new hashes. `integration_manifest.json`, `top.v.diff` and
`ddr_w_arb.v.diff` provide the review boundary. Only the cloned `top.v` and
`ddr_w_arb.v` change among pre-existing design sources; camera RTL/IP are copied
byte-for-byte. 892 production files remain unchanged; 275 project RTL/IP/constraint
references resolve. Generated compile/route/bitstream output records are inherited
project records, not copied results or evidence of a new build.

Audit against the current source established:

- `top.v` ties `npu_s4_axi_arvalid/rready` off and connects that interface to
  crossbar S06. The candidate removes exactly those two tieoffs and drives S06
  with single-beat reads and ID 0xd. S03/S04 NPU and S05 history reads stay wired.
- Crossbar M00 writes are disabled. The camera `ddr_w_arb` feeds the existing
  DDR glue directly. Its clone gains m6, retaining locked AW selection, W/B
  ownership, and round-robin retirement, with ID 0xd for delivery writes.
- Crossbar M02 is the retired NPU register window (`0x40000000` aperture).
  Existing top has no active register responder there, only response tieoffs.
  The clone replaces those tieoffs with the real `axi_to_axi_lite` bridge and
  exact register cases at `0x40020000..0x400200ff`. Other addresses return SLVERR.
  Seven-bit M02 IDs and eight-bit lengths replace truncated/implicit declarations.
- Cam5's hard-coded banks are `0x01800000` and `0x01a00000`. Admission hold drives
  its existing `axi_cam_en`, allowing current data/tag to drain. Freeze requires
  engine IDLE, no command/AW/W/abort for 32 clocks, and the previous bank's actual
  published request bit. It then latches the bank until release.
- Destination is fixed to `[0x0a000000,0x0a12c000)`, matching the disabled legacy
  preprocess buffer. Active default camera banks are below `0x02000000`.
  This is the clone's reservation, not a live-board allocation claim: parent must
  prevent other software/NPU uploads from using it. Provider additionally rejects
  live programmable camera-bank overlap, conservatively reserving 2 MiB per bank.

MMIO uses 16-byte DMA beats, low 32-bit register data, at these offsets:

| Offset | Meaning |
| --- | --- |
| 00 | signature `0x444c5632` (DLV2) |
| 10 | status bits 0 hold, 1 frozen, 2 busy, 3 done, 4 error, 5 config error, 6 quarantined |
| 20 | control: bit 0 hold; bit 1 submit (write 1, wait frozen, then write 3) |
| 30 | frozen source bank, read only |
| 40 | fixed destination; writes accept only `0x0a000000` |
| 50 | hold generation |
| 60 | RGB byte count |
| 70 | completed job busy-clock count |
| 80 | RAW byte count |
| 90 | completed job counter |

`python run_integration_tests.py` passes: 79 ordinary project RTL files compile;
the real S00/M02 MMIO path, S06/M00 read crossbar, adapter and seven-master write
arbiter simulate with independently stalled memory and six continuous competing
camera writers. Two small frames compare 120 RGB bytes, validate camera data
routing/progress, freeze acknowledgment and job counters, and reject invalid
MMIO addresses, premature submit, arbitrary destination and busy release.
A second test uses the
unchanged production admission block and checks mid-frame drain, later-frame
blocking, and next-SOF resume. `integration_artifacts/report.json` records results.

Important validation boundary: the DDR slave in this integration simulation is
an AXI memory model. Actual top DDR glue, vendor DDR/PCIe IP, CDC, camera packet
pipeline and Linux DMA completion are not elaborated together. ModelSim rejects
pre-existing forward/repeated declarations in `top.v` and legacy PCIe modules;
those five files are explicitly excluded from this ordinary-RTL compile, not
reported as passing. PDS syntax/elaboration, synthesis, resources and timing for
the full clone remain unverified. No PDS process was launched.

## Coordinated deployment work remaining

1. Review the clone/diffs and reserve the destination for this exclusive test.
2. Parent runs the isolated project in a single PDS instance, reviews elaboration,
   DDR-glue behavior, timing/resources and cam5 regression before flashing.
3. Confirm the deployed driver ABI matches the retained source; stop all clients,
   block restarts, then build with actual RK3568 Qt/RKNN runtime and pinned model.
4. Validate DLV2 MMIO writes/readback and capture drain on hardware. A nonreturning
   ioctl requires parent-coordinated quiesce; the poll deadline cannot interrupt
   a blocked kernel ioctl. Historical H2F stalls do not prove M02 control works.
5. Compare hardware RGB bytes against CPU on the same frozen cam5 frames, run
   `paired_preprocess PINNED_MODEL 10 100`, then full detview and cam5 regression.

This minimal endpoint favors small, auditable control logic over throughput.
It transfers 1,228,800 model-input bytes to the host instead of 614,400 RAW
bytes, and uses single-beat DDR transactions. Removing CPU preprocessing
may therefore lose overall performance. Only the paired hardware measurements
can decide whether to keep it or add burst scheduling/direct input DMA.
