# Next revision integration checklist (no integration performed)

The existing top still binds the original PCIe FIFO and controller. Concrete old hierarchy and PDS registrations are in `integration.json`.

| Candidate-local source and line | Existing module type | Existing instance hierarchy |
| --- | --- | --- |
| `rtl/fpga_v8_cooperative_top.v:446` | `pcie_fifo` | `pcie_fifo` |
| `inputs/source/pcie_dma/pcie_fifo.v:216` | `pango_pcie_top` | `pcie_fifo/pango_pcie_top` |
| `inputs/source/pcie_dma/pcie_dma_ctrl/pango_pcie_top.v:349` | `ips2l_pcie_dma` | `pcie_fifo/pango_pcie_top/u_ips2l_pcie_dma` |
| `inputs/source/pcie_dma/pcie_dma_ctrl/ips2l_pcie_dma.v:328` | `ips2l_pcie_dma_controller` | `pcie_fifo/pango_pcie_top/u_ips2l_pcie_dma/u_ips2l_pcie_dma_controller` |

Candidate PDS registrations: `ips2l_pcie_dma.v:590`, `ips2l_pcie_dma_controller.v:594`, `pango_pcie_top.v:666`, `pcie_fifo.v:674` (line numbers refer to project.pds). The baseline top's PCIe instance is retained as `pcie_fifo` at top:449; its type begins at top:446. Frozen and candidate-local wrappers are byte-bound in the source receipts.

**Required binding chain.** A later isolated top must change its module type to `fpga_v8_pcie_fifo_h2f` while retaining instance `pcie_fifo`. That candidate binds `fpga_v8_pango_pcie_top_h2f` at retained instance `pango_pcie_top`; that wrapper binds `fpga_v8_pcie_dma_h2f` at `u_ips2l_pcie_dma`; that wrapper binds `fpga_v8_pcie_dma_controller_h2f` at `u_ips2l_pcie_dma_controller`. Merely registering the new controller leaves the old ips2l_pcie_dma controller binding active. All four unique artifacts are therefore required; no hard-IP RTL, configuration or vendor registration needs changing.

Artifacts read from `../pcie_h2f_transport_contract/artifacts/` relative to whole_candidate's parent:

| Artifact | Verified SHA-256 |
| --- | --- |
| `fpga_v8_pcie_fifo_h2f.v` | `507ef4c56999aac5356dd51f51a669232fb7c40070c67e3ab108da444b32640d` |
| `fpga_v8_pango_pcie_top_h2f.v` | `4e56ac9284370149c5374660110fd51440951a89f8755fd8f1e6c87a5af7cddf` |
| `fpga_v8_pcie_dma_h2f.v` | `b4dd9cf5ba7b6d9e859640279247d6faeb2e6c1d4c2783fccd1e4c0ac9a9cfee` |
| `fpga_v8_pcie_dma_controller_h2f.v` | `dc87498f41e5c977962e131491d1e932dd716a91a7eb15f94e433f8363f67cd1` |

At read time their edit-manifest hashes matched and API-identical receipts were true. The correction receipt is `H2F_CORRECTIONS_PASS_PENDING_INTEGRATION`: **50 cases**, **4 fault cases**, AW 9,925, W 158,368, B 9,924, MSI 41. Its scope is the actual controller and MRD segmenter plus official FIFO/DRM with a simulated PCIe completion/RAM shell. This is separate source evidence and is not a whole integration acceptance. Original whole PDS pending fields remain untouched.

**Inherited defect.** The original pcie_fifo:189-203 raises fpga_rx_done from RAM count/FIFO empty or intermediate chunk completion without accepted AXI B retirement. The DMA wrapper:338 feeds its inverse to controller i_mrd_rx_busy; controller:719 and 942-953 detect completion, controller:992-1006 issues MSI, and ips2l_pcie_dma:112-127 stretches the pulse to grant. The old measured CLAIM MSI is **1.064 us**, full B **1.735 us**, **671 ns early**. The retirement-only predecessor still drops singleton WVALID under a post-AW W stall and permits a 4KB-crossing host chunk at +4. The current correction artifacts separately address W reservation/backpressure, byte reassembly and controller 4KB chunking; binding the retirement-only FIFO cannot claim these fixes.

- [ ] Parent review must pin the complete correction artifact set, exact edit-manifest, results and source hashes before creating a separately authorized next whole revision. No new whole source is generated in this review.
- [ ] In the later isolated revision, copy only these four approved unique modules into its own RTL tree, bind the chain above, register source timespec fields and select a unique top. Keep the old instance names so PCIe clock/HSST/pin constraint hierarchies continue to resolve. Keep protected pcie_fifo, pango_pcie_top, ips2l_pcie_dma, controller and hard-IP bytes untouched.
- [ ] Verify API/parameter equality, candidate module uniqueness, elaborated controller binding, reachable hierarchy and no accidental simultaneous old/new writer use. Use production artifact names, not the ModelSim compatibility `candidate_fifo.v`/`candidate_controller.v` aliases.
- [ ] Verify the corrected H2F path in the connected whole netlist: WREADY before AW, first and later W stalls, stable WDATA/WSTRB/WLAST under stall, partial final strobes, +4/+8/+12 host offsets, 4KB boundaries, 64-bit host address carry, back-to-back chunks and backpressure across the actual crossbar/M02/control path.
- [ ] Verify final completion follows accepted matching ID-zero B; wrong BID, held final B and intermediate errors must keep completion pending. MSI delivery qualifies only the proved retirement boundary; use ordered register readback to resolve accepted/rejected commands because BRESP is not exposed by this ioctl API.
- [ ] Resolve the capture ARM/SOF combinational loop with the capture owner and rerun connected mapped behavior. The endpoint 654-operation mapped receipt does not include the whole lease/wrapper feedback path.
- [ ] Define and implement a coordinated transaction epoch reset, with synchronized release in both domains, for PCIe/controller/FIFO plus crossbar/endpoint/AXI state. Verify it abandons pending work without credit/MSI, drains or clears both FIFO sides consistently and restarts with a new generation. Independent resets are unsupported by the correction receipt.
- [ ] Keep F2H posted-write/MSI ordering, Linux ioctl completion semantics, hard-IP link/completion recovery and board behavior separately pending. Whole mapped checks, route setup/hold at both corners, and hardware acceptance require their own evidence and authorization.

**Actual clock/reset domains.** pango_pcie_top:68-69 drives `fifo_pcie_clk=pclk_div2` (**125 MHz**) and `fifo_pcie_rst=~core_rst_n`. Its DMA/controller use pclk_div2/core_rst_n at pango_pcie_top:356-359 and DMA:334-335. button_rst_n and perst_n feed ref_clk (**100 MHz**) debounce/synchronizers at pango_pcie_top:203-241 and the hard PCIe wrapper reset inputs at 555-564. The AXI side uses DDR core/axi_clk (**131.25 MHz**) and `axi_rst=~ddr_init_done`, with endpoint/control rst_n `~axi_rst`. RX FIFO write reset is fifo_pcie_rst and read reset is axi_rst (pcie_fifo:266-279); TX reverses domains (pcie_fifo:471-489). The existing DDR instance ties rst_n **1'b1** at top:247. Neither button nor PERST demonstrates a shared reset for these states. A coordinated host-triggerable reset is **not implemented or available as a validated contract** in the existing whole top. CPU restart, MSI clear or only one side's reset is not epoch recovery.
