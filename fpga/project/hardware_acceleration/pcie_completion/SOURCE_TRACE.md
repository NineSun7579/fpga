# Frozen PCIe completion source trace

Scope: read-only byte-level inspection, without simulation, synthesis, programming,
driver loading or a hardware completion claim. The requested simulation subtask
was rejected by automatic tool review before execution.

The recovery record identifies `motion_100h/run_20261003_212303/top.sbit` as
SHA256 `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`.
Parent recomputation matched that bit hash and the six previously recorded core
source hashes. The additional directly inspected files also match the input
manifest: `pcie_fifo.v` is
`c6bcf1f48328ff250e097ad1bbe0e49e8e52001138fe15f9db697da1ddf62027`;
`ips2l_pcie_dma.v` is
`33363ee991706b0ac78e0b75f71512744e7813af3bf8ef6d5088857ca6975b6c`.
Source below is the immutable `inputs/source` archive of that run;
it does not assert a fresh identity query of the physically loaded FPGA.

## Actual completion wiring

1. `pcie_dma/pcie_fifo.v:558` increments `tx_beat_cnt` on `fpga_tx_clk_en`.
   Lines567-568 set `fpga_tx_done_r` when that count equals `total_beats`;
   line574 exports it. This is a source-side data-read count.
2. `pcie_dma/pcie_dma_ctrl/pango_pcie_top.v:424` forwards that completion
   signal. `ips2l_pcie_dma.v:337` connects the controller's `i_mwr_tx_busy`
   to **`~fpga_tx_done`**, rather than the MWR packet generator's busy output.
3. `ips2l_pcie_dma_controller.v:936-940` detects the falling edge of that
   input. Lines719-720 derive chunk completion. Lines998-1002 raise the
   completion MSI for the final chunk or non-chunked request.
4. The MWR generator independently defines `tx_done` as valid/ready/last
   at `ips2l_pcie_dma_mwr_tx_ctrl.v:111`, and clears its own busy at316-317.
   Those generator semantics alone do not prove the controller's completion,
   because the actual controller wiring above uses a different signal.

## Buffered output and MSI boundary

`ips2l_pcie_dma.v:416` feeds generator ready from `dma_axis_slave2_trdy`.
In its mux branches, lines497/554 connect that ready to the mux's FIFO input.
The bypass branch at602 forwards external ready directly. Branch selection
must be established before attributing a particular downstream boundary.

`ips2l_pcie_dma_tlp_tx_mux.v:182-198` places an actual prefetch FIFO between
the packet generator and PCIe output. Line201 gates FIFO output on PCIe ready;
line359 registers the selected word; lines384-387 expose the PCIe output.
Acceptance by this FIFO is distinct from final acceptance at the vendor core.

`pango_pcie_top.v:521` routes DMA MSI into the MSI arbiter, and lines622-624
connect its request, traffic class and grant to the vendor core. MWR traffic
class and attributes are zero (`ips2l_pcie_dma_mwr_tx_ctrl.v:207-208`), and MSI
traffic class is zero (`pango_pcie_top.v:623`). Applicable PCIe ordering still
requires all payload to enter the ordered core path before the completion MSI.
Source-side read completion cannot establish that requirement by itself.

The arbiter's pending update at `msi_arbiter.v:94-97` clears on grant and ORs
new rising requests only in the alternative branch. A new request coincident
with grant is therefore absent from that update unless independently retained.
Its relevance to serialized DMA completion needs an actual timing test; this
inspection does not claim a reproduced interrupt loss on the target.

## Remaining evidence

The current wiring does not prove producer drain. Required evidence includes
the data-read-to-packet-to-vendor-input timing under backpressure, actual mux
configuration, request attribution, and vendor-core ordering of buffered data
relative to its separate MSI interface. The retained source trace supplies
specific boundaries for a future test, not a substitute for it. No frozen RTL
or active FPGA source was edited, and both exporter/backend gates remain closed.
