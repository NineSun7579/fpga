# PCIe retirement contract investigation

Everything in this directory is isolated. No production RTL, IP registration,
PDS project, SSH connection or board action is modified or invoked.

Run from the workspace root:

```powershell
& 'C:\Users\NineSun\anaconda3\python.exe' 'project/fpga_v8_migration/pcie_retirement_contract/run_tests.py'
```

The runner hash-checks the byte-identical captured `pcie_fifo.v` and
`ips2l_pcie_dma_controller.v`. ModelSim 10.6e cannot directly compile their
forward declarations, even with `-permissive`; the failed compile logs are
preserved. The runner generates declaration-only compatibility copies in
`artifacts/`: registers, wires and local parameters are hoisted, wire
declaration initializers become identical continuous assignments, and two
existing implicit nets receive explicit declarations. All expressions,
procedural bodies and controller/chunk/MSI behavior remain unchanged. The
compatibility manifest records original and generated hashes. This is the
simulation of the original logic, with that declared language-compatibility
qualification, rather than a direct compilation of its exact byte stream.

It compiles those copies in Verilog mode, with the captured Pango
`pcie_rx_fifo`/`pcie_tx_fifo` RTL and installed standard Pango
`GTP_DRM36K_E1.v`/`GTP_GRS.v` simulation models. Both clock domains run independently at
10 ns and 16 ns. The real cooperative AXI128 endpoint and cooperative control
are connected after an AW-selected AXI route model. The real cooperative
producer interface publishes a READY descriptor before CLAIM.

`tests/pango_pcie_top_stub.sv` intentionally defines the external production
wrapper's module name **inside the simulation library only**. Never register
this test file in a production PDS project. It does not fake `fpga_rx_done` or
MSI: the frozen FIFO produces RX completion and the unchanged frozen controller
produces `o_fpga_msi`. It models request grants, host fetch delay and the one
clock RAM read latency needed by the actual FIFO capture pipeline. It sends the
real BAR1 descriptor words, including the 64-bit-host-address command bit.

The AXI route model keeps WREADY low before an AW selects its destination, as
an AW-routed fabric must. A response gate holds the real endpoint's B response
for 23 core clocks with a corresponding READY gate. It measures both the
endpoint's visible response and the FIFO's accepted full AXI B response.

Cases cover CLAIM, matching ACK, rejected CLAIM/ACK, consecutive 16-byte
transfers, local control AW/W backpressure, full AW backpressure, final B delay,
coordinated reset with a pending response, large streaming transfers, partial
last-beat strobe, host address offset 4, a post-AW W stall, and wrong BID.
Raw events and compiler/simulator logs are retained in `artifacts/`.

The frozen source actually uses 4096-byte intermediate chunks. Its comments
still mention 4092 and its computed PCIe boundary limit is commented out of
chunk-size selection. An actual 4092-byte *intermediate* chunk cannot be
generated from that unmodified controller. The suite exercises a 4092-byte
singleton, 4100-byte transfer, actual 4096-byte intermediate chunks and the
1,228,800-byte transfer instead, and treats offset-4 violations as negative
evidence.

The retirement candidate preserves the complete external FIFO parameter
and port API and all FPGA-to-host logic. It is a generated build artifact from
the frozen bytes with narrowly recorded replacements. A production replacement
would instantiate `fpga_v8_pcie_fifo_retired` with the same parameters and port
connections. This investigation does not integrate or deploy it.

Reset of the retirement handshake is an epoch change and requires coordinated
reset of the PCIe/controller/FIFO and AXI fabric/endpoint. A CPU-only restart,
an independent PCIe link reset or an independently reset endpoint is not a
supported recovery operation. A timeout remains delivery-unknown until the
actual pending transaction is retired or the coordinated reset is complete.

Completion does not expose BRESP to the host. Once final B has been accepted,
the appropriate host classification is `DeliveryKnownUnknownResponse`;
ordered state readback must resolve accepted versus rejected commands. MSI
alone cannot provide that classification for the frozen implementation.

The candidate does not repair the legacy W channel's post-AW stall loss, the
PCIe offset-4 boundary violation, unsynchronized legacy metadata or the
original direct cross-domain FIFO-empty observation. Those negative cases must
stay visible and prevent a general production transport acceptance claim.

The simulated boundary stops at the controller's `o_fpga_msi` pulse. PCIe MSI
grant, Linux ioctl wakeup, root-complex ordering, hardware metastability and
host memory visibility are outside this simulation. FPGA-to-host completion
also requires its own posted-write/MSI ordering proof.
