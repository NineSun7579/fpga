# Six-camera autonomous display candidate

Candidate: `integrated_six_background/project/project.pds`. Generate with
`python make_six_background.py`; use `--refresh` only for this isolated clone.
It copies source/project inputs only, reuses existing IP references, and adds
three ASCII modules. No baseline source, IP, bitstream, board state, or commits
are changed. The source clone is approximately 7.2 MB; build artifacts are not
copied. `BACKGROUND_PROTOCOL.md` is the host contract.

Run `python verify_six_background.py` for ModelSim 10.6e validation. Logs are in
`sim_six_background`; preservation evidence is in
`six_background_preservation_report.json` and all baseline/candidate input hashes
are in `six_background_source_manifest.json`.

## Capture and publication

The passive tap is **inside the existing ov5640_ddr wrapper**: `m_vsync` is the
exact admitted SOF from `ov5640_ddr_w_en`; `m_data_valid` and `m_data` are the
quota-gated axi-clock RAW input stream. It is not the unadmitted sensor VSYNC,
packed DMA stream, or a replay of DDR. Cameras 1..4 export the tap through their
existing wrappers after median/FIR/Kalman/bypass; cameras 5..6 export the normal
fiber pixel branch. The deferred camera 5/6 pixel faults are unchanged. Their
existing abort/overflow faults reject the corresponding thumbnail attempt.

Each producer counts the complete 640x480 source independently and selects
even x/even y RGB565. It packs eight pixels per 128-bit beat into a 64-entry
FIFO. Aggregate new FIFO payload+strobe storage is 55,296 bits (6.75 KiB), plus
packing/control registers. Storage inference/resource use awaits synthesis.
Overflow, source faults, short/new SOF before completion, or the 16,777,216-cycle
deadline drop the attempt. No branch signal feeds capture admission, RAW FIFO,
RAW DMA, sensor pixel processing, or existing capture holds.

Each camera alternates independent thumbnail banks at attempted admission,
increments its bank generation and clears valid before any AW, and predicts
the corresponding RAW sequence modulo 2^32. Successful RAW tag publication is
exported by detecting changes in the existing successful publication counter;
zero after wrap is valid. Successful RAW retirement also causes a local capture
flush: that flush is deliberately not considered a new source fault. A missing
RAW publication is rejected by the independent deadline.

All payload bursts must retire successfully before a separate tag write can
launch. Tag launch additionally requires all source pixels and matching RAW
publication. Only the successful tag B sets valid and clears busy. Announced
bursts survive source failure/deadline until their AW/W/B obligations retire;
failed attempts stay invalid. A nonzero B quarantines the background writer,
invalidates active attempts, and leaves RAW and the existing RGB endpoint
operational. An external response that never arrives retains ownership until
coordinated fabric reset; no timeout fabricates retirement.

One shared single-outstanding writer selects six producers round-robin at each
burst. A second arbiter alternates the existing RGB/on-demand endpoint and
background writer, retaining ownership through B. Reads retain the old endpoint
path. Native HMIC burst16/stride256 addressing and existing destination allowlist
are retained; final partial bursts carry precise byte strobes. No bytes outside
the allowed thumbnail bank are written.

## Register/host integration

Caps at +0xa0 are 31; bit4 advertises autonomous thumbnails. +0x180 accepts
full-strobe 0/1 writes: requested enable; read bits1/2 give quiescent/quarantine.
Reset disables it. Disable stops future admission and drains admitted attempts;
completed records survive until reused. Background ownership rejects on-demand
thumbnail leases while enabled/draining, and enable rejects an existing
on-demand thumbnail lease. RGB jobs remain available. Before a legacy thumbnail
command writes its destination, that record generation increments and valid
clears; legacy jobs do not create autonomous records.

Twelve records occupy +0x200..+0x37f. Physical camera index is 2*(cam-1)+bank;
each record has guard at +0 and RAW sequence at +16. The existing 32-bit register
bridge remains intact. The adapter latches a full 128-bit record half on the
same accepted register request and selects that value for only the record
response. PCIe ARLEN=0 expands only to +0x180 and aligned record beat starts
+0x200..+0x370. The old 304-byte snapshot remains 19 scalar register beats.
The host must negotiate caps, enable explicitly, and use guard-before/data/tag/
guard-after validation. See the protocol for every field and address formula.

## Validation and limits

The suite covers:

- 85 ordinary project RTL inputs compiled with zero ModelSim errors.
- Six simultaneous producers at 640x480, 32x16 and 10x6, all selected RGB565
  pixels checked by source-coordinate formula, burst addresses/allowlist,
  partial final strobes, full odd-row tail, RAW barrier, sequence wrap to zero,
  two independent banks, busy/valid generations, disable/drain, overflow,
  deadline, and bad-B quarantine.
- Real delivery adapter MMIO, control negotiation/strobes/conflicts, all record
  fields, concurrent RGB888 byte parity, AW/W stalls and stability, held final
  tag B, and a thumbnail B error while RGB remains active. Subsequent legacy
  thumbnail output is checked and its prior autonomous record is invalidated
  before writes.
- Real PCIe read engine and real adapter: all 384 record bytes and control,
  unchanged 304-byte snapshot order, boundaries outside the new window,
  ordinary DDR payloads, FIFO capacity stalls and AXI stalls. Only vendor PCIe
  endpoint/FIFO IP are inert stubs in this transport test.
- Independent RAW replay in baseline/candidate libraries: 10 complete frames
  compared pixel-for-pixel, seven failures/recoveries, 61 AW/B retirements,
  identical publication/abort traces and zero-strobe filler accounting despite
  an enabled overflow-prone thumbnail tap. RAW FIFO IP uses the existing test
  behavioral model. Removing only passive exports reconstructs the original
  complete capture wrapper bytes. Existing capture controller, admission gate,
  packer, DMA, shared DDR arbiter, RGB and on-demand cores are byte-identical.
- All 319 baseline input hashes and all non-ASCII bytes remain intact. New
  module names are unique. Every PDS source/IP reference resolves.

These are component/adapter/RAW regressions, **not full-top vendor simulation,
synthesis, resource fit, timing closure, or board acceptance**. The existing
legacy PCIe/top inputs have ModelSim forward-declaration/vendor dependencies;
the ordinary compile excludes top.v, ips2l_pcie_dma.v,
ips2l_pcie_dma_controller.v, pango_pcie_top.v and pcie_fifo.v (the last is exercised
as a byte-preserving declaration-normalized simulation copy). Vendor camera
FIFO semantics, full seven-master DDR contention with six live camera sources,
PLL/CDC behavior and FPGA storage inference still require parent-owned PDS and
hardware validation. Extra DDR traffic can change service latency and cause
thumbnail drops; the branch neither slows its source via feedback nor promises
a sustained display rate. The default deadline is counted in axi-clock cycles,
not milliseconds. The parent owns timing constraints and all rollout decisions.
