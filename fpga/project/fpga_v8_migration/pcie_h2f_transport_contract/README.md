# Isolated PCIe H2F transport corrections

This directory contains the follow-up to the immutable
`../pcie_retirement_contract` investigation. All generated candidates, simulation
libraries, diffs and logs remain here. It performs no production/IP/PDS edits,
PDS builds, SSH, board, driver or host-tool operations.

Run from the workspace root:

```powershell
& 'C:\Users\NineSun\anaconda3\python.exe' 'project/fpga_v8_migration/pcie_h2f_transport_contract/run_tests.py'
```

The frozen FIFO/controller hashes and the validated retirement candidate are
pinned in `build_candidates.py`. The test runner hashes the previous contract
directory and every external simulation dependency before/after running. A
declaration-only compatibility copy is compiled for ModelSim because the
original frozen Verilog uses forward declarations rejected by ModelSim 10.6e.
The production candidate artifacts retain the original source bytes outside
the explicitly listed edits; normalization applies only to simulation copies.

Generated production artifacts:

- `artifacts/fpga_v8_pcie_fifo_h2f.v`: original FIFO API, byte reassembly across
  PCIe chunks, reserved synchronous-FIFO reads and a two-word AXI W queue,
  inherited final accepted-B completion credit.
- `artifacts/fpga_v8_pcie_dma_controller_h2f.v`: original controller API,
  H2F-only `min(remaining,4096,4096-host_low12)` chunking and 64-bit host carry.
- `artifacts/fpga_v8_pcie_dma_h2f.v`: production DMA wrapper clone, renamings
  only, binding the unique controller.
- `artifacts/fpga_v8_pango_pcie_top_h2f.v`: production PCIe shell clone,
  renamings only, binding the unique DMA wrapper.

The FIFO binds the unique production shell while retaining its original
instance name. All four candidates keep their original parameter/port APIs.
The production shell still instantiates the unchanged vendor PCIe IP. The
simulation shell defines the same unique production shell name only inside
an isolated simulator library; **never register `tests/pcie_shell.sv` in PDS**.

Future integration must add the four production artifacts to an isolated
integration manifest, replace the top-level FIFO module type with
`fpga_v8_pcie_fifo_h2f`, and keep the same parameters/named connections. Do not
modify generated IP. Existing DMA/PCIe wrappers may coexist under their
original names; the candidate wrapper chain explicitly binds the new names.
No integration or project registration is performed by this directory.

The controller and unmodified actual `ips2l_pcie_dma_mrd_tx_ctrl` segmenter run
inside the simulation shell. The segmenter's real TLP headers populate the
modeled chunk RAM, and completion tags return after a controlled latency.
Every candidate chunk request and real segmented MRD TLP is asserted legal
against 4KB boundaries, DWORD alignment and configured MRRS. RX RAM reads have
one clock latency; RX/TX FIFOs and DRM primitives are official Pango models.
The testbench keeps the real cooperative endpoint/control for CLAIM/ACK.

The host starts on a DWORD boundary (offsets 0,4,8,12 modulo 16); FPGA AXI
destination starts on a 16-byte boundary. Final non-DWORD byte counts round
the MRD wire length up to a DWORD as the unchanged segmenter requires, discard
the fetched extra bytes, and strobe only requested bytes on the final AXI W.
The driver must provide mapped backing bytes for that final rounded DWORD.

Final accepted ID-zero B toggles one persistent completion credit. SLVERR on
the final B still retires, so host-visible completion means
`DeliveryKnownUnknownResponse`; state readback resolves command acceptance.
An intermediate error, wrong BID or held final B does not produce final MSI.
Coordinated PCIe/controller/FIFO and AXI fabric/endpoint reset is the only
tested pending-transaction cleanup. Independent resets remain unsupported.

This is H2F correction evidence pending integration. It does not validate
F2H posted-write retirement, Linux ioctl semantics, hard-IP link/completion
behavior, root-complex ordering, CDC implementation or board timing.
