# Verified results and remaining integration gates

Current evidence establishes two independent results:

1. The pinned V8 RK3568 completed-inference experiment passes strict production
   parity and improves 14.5684 -> 16.0670 FPS, +10.29%. The paired workload is
   240 completed jobs per profile on the same 30 prepared inputs. It includes
   CPU input preparation and excludes camera/PCIe acquisition and display.
2. The isolated cooperative FPGA core passes full-frame simulation with six
   competing camera writers and synthesizes to 2,074 LUTs / 1,773 registers,
   without latches, DRM or APM. Its simulated source is already stable and
   leased. All top-level ports are virtual in the component PDS project.

These results do not establish installed FPGA cooperation. The required work
before a deployment or cooperative FPS claim remains:

- Recover the running viewer's exact source/compiler binding and loaded FPGA
  map; older similarly named viewer sources are not equivalent evidence.
  The full retained HDMI build directory is now frozen; its executable matches
  installed `0301f690...` and its decoder is byte-identical to the benchmark
  production include. Independent fresh reconstruction now reproduces that
  binary and all 12 objects exactly; see `viewer_build_recovery.md`.
- Supply certified unfiltered RAW input with capture-side bank references,
  whole-frame drop behavior and reset-generation reconciliation. Current ACK
  logic does not prevent reuse. The existing camera/FIR bank is not evidence
  of that source contract.
  The isolated capture wrapper/manager now passes nine actual camera/DMA/FIFO
  suites. The capture-to-core/DDR regression now retains five full RAW/input
  pairs, and host C++ preparation matches their 6,144,000 input bytes. A durable
  generation allocator passes Linux temporary-journal tests in `epoch_allocator/`;
  physical domain provisioning and coordinated reset still require integration.
  Single-C5 preprocessing uses an 80-row model-input pad. HDMI full mode merges
  C5/C6 and uses a 140-row pad after scaling; these inputs are different. The
  current single-camera FPGA candidate cannot replace merged HDMI inference
  without additional equivalence work.
- Reserve disjoint output/RAW/host receive buffers at runtime. A 1,228,800-byte
  NHWC image cannot fit one existing 0x97000 camera RX slot.
  The recovered HDMI source requests 4 MiB for each TX/RX mapping. Fresh read-only
  `/proc` evidence in `board/live_dma_layout_20261005.json` confirms two 4 MiB
  mappings and one driver owner at that observation. Mapping file offsets are
  both zero in `/proc`; use the source ioctl/mmap requests, not those offsets,
  to identify TX versus RX. This observation does not reserve any buffer.
- Connect S02 read and the added write owner into the real DDR adapter, and
  install the controller endpoint in M02 with correct AXI IDs/responses.
- Integrate host CLAIM -> complete DMA -> owned model input -> matched ACK
  into a verified driver/viewer or a separate exclusively scheduled benchmark.
- Verify whole-design resources/timing, real AXI/DDR/PCIe byte correctness and
  reset/coexistence, then compare completed cooperative FPS on actual shared
  RAW payloads. Repacking PNG into RGB565 changes the input and is not a copy
  of retained RAW bytes.

An additional concrete DDR wiring issue is confirmed by byte-level inspection
of unchanged `source/top.v`: line 524 ties `arb_s_bid` to zero, even though the
minted `ddr_axi_bid` carries the vendor/accepted transaction ID. The new core's
writer uses ID1 and its arbiter checks IDs. Merely attaching that core to the
old constant-zero response wire would fail its contract. The isolated adapter
validation now passes five actual-FIFO ModelSim suites; its original-assignment
fixture triggers both core ID errors, while the candidate preserves accepted
AWID and flags inconsistent vendor ID. Full integration compares every output
byte and 19,200 competing camera words. Production wiring is unchanged.

Read routing also deserves explicit end-to-end verification: the FIFO stores
low four RID bits while the high route bits come from a latched AR owner.
`rd_inflight` clears at vendor RLAST, but the next AR additionally requires an
empty return FIFO. The actual-FIFO test buffers all 16 returned beats under
RREADY=0, blocks the next route through drain and verifies all retained full
RIDs. This confirms the inspected gate protects ownership in that schedule;
the read logic is not a confirmed race. The candidate retains its full AR owner
until final downstream RLAST acceptance.

The current W FIFO receives WVALID instead of WVALID&&WREADY. Source inspection
and a complete-full FIFO test confirm its pointer/RAM both stop on full, matching
the current full-only READY gate. The original words survive nine additional
VALID cycles; this does not permit future ownership/READY gates to retain the
same ungated enable. The candidate uses accepted writes and stages the complete
burst before the vendor's unthrottleable write request is released. The physical
DDR controller is represented by a scheduling stub and remains unverified.

PCIe control alignment is a separate necessary interface change. Existing
register accesses use a 16-byte DMA, while the controller's local register
spacing is four bytes. Passing those writes through a generic 128-to-32-bit
AXI-Lite converter would hit four neighboring registers. A new isolated AXI128
endpoint uses 16-byte physical spacing and executes one low-32-bit operation.
The proposed base is `0x40010000`, with physical address `base + 4*local_offset`.
Current source M02 is explicitly tied off after NPU removal and returns no B/R;
neither the new endpoint nor host protocol may be used on the installed image.

PCIe completion is a demonstrated failing boundary. In the frozen motion source,
`pcie_fifo.v` derives final `fpga_rx_done` from RX FIFO exhaustion while the AXI
writer separately waits for the final B response. The driver observes an MSI
counter change and does not expose BRESP. It is therefore not yet established
that a successful H2F ioctl meets the helper's ordered, fully retired write
contract. `pcie_retirement_contract/REPORT.md` demonstrates MSI at 1.064 us,
CLAIM at 1.495 us and final full AXI B retirement at 1.735 us. Its isolated
retirement candidate completes after final B, but inherited W-stall loss and
host-offset PCIe 4KB crossing remain. Corrected transport/whole binding and
physical PCIe/Linux completion remain required. F2H posted-write visibility is
also unproven. Candidate transports must not label unproven completion retired.

The follow-up isolated H2F candidate now passes 50 cases, including the prior
W-stall and host-offset boundary defects, with 46 final completion credits and
19,587 legal segmented TLP events. It is not yet bound into the whole candidate;
the original PCIe path remains in the synthesized `whole_candidate` result.

Whole compile and synthesis now pass in `whole_candidate/compile_01/attempt_02`:
29,733 LUTs, 30,889 registers and 72.5 DRM. Core clock remains 131.25 MHz;
pre-route hold slack is -0.004 ns at ten endpoints. No PnR/timing acceptance.
The original connected component netlist passes 654 public operations against
RTL and oracle in `component_synthesis/endpoint_netlist_sim_01`; this is not
whole-design mapped equivalence. The preliminary whole candidate retains the
original PCIe path, so it cannot supply the host helper's retirement guarantee.

The frozen native viewer candidate now compiles/links successfully in
`viewer_native_build_evidence`. That audit observes externally changed live
viewer PID 149510 and executable `496acc4f...`, plus changes to the retained
source directory. The earlier exact `0301f690...` reconstruction remains valid
for its frozen inputs and historical executable, not the newer live source.
No acceleration candidate was deployed. Any viewer integration must account
for the newer live baseline before replacing it.

The latest reviewed historical FPGA restore names the frozen motion build
`motion_100h/run_20261003_212303`, top SHA256
`ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2`,
and bitstream `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`.
Those receipts are not a fresh readback of current hardware. The isolated
whole-design candidate is based on this complete frozen motion input set so
that motion and six-camera behavior are preserved during integration.

Source top SHA256 remains
`dca00ca2ecbc0b1418a32fc9abb09c673e522960a0150ef568f1e528a1681347`.
No production RTL, project registration, IP, viewer replacement or FPGA load
is justified by component-only evidence.
