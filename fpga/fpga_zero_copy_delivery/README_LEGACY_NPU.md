# Isolated FPGA legacy NPU exclusion candidate

The generator now also integrates a cam5 thumbnail mode. See
[README_DISPLAY_INTEGRATION.md](README_DISPLAY_INTEGRATION.md) for the current
controls and complete changed-file list. The tieoff findings below remain
valid; source-count and project-change notes have been updated for both modes.

RK3568 RKNN inference remains enabled. No viewer source, model, RKNN library,
production RTL, baseline project, or board state was changed by this work.

The starting point is
`../fpga_acceleration_delivery/ddr_rgb_letterbox/integrated`. Inspection found
that this baseline **already excludes the FPGA legacy NPU**: `top.v` has no NPU
or instruction-controller instance, and `project.pds` has no entries under
`source/npu` or `source/pcie2npu`. There is no additional NPU resource saving to
claim relative to that baseline; actual resource reports require a PDS build.

## Generate and verify

From repository root:

```powershell
python fpga_zero_copy_delivery/make_integrated.py
python fpga_zero_copy_delivery/verify_integrated.py
```

Generation writes `integrated/project/project.pds`, the isolated source tree,
`legacy_npu_top.v.diff`, and `legacy_npu_manifest.json`. It copies source bytes
without transcoding GBK. It excludes the entire legacy `npu` and `pcie2npu`
source directories; the manifest lists every excluded file and module type.
None of those files were registered in the starting PDS project, so no PDS
source entries needed removal. Generation checks that project-selected RTL
does not instantiate excluded module types and resolves 278 project inputs.

IP inputs are relative references to the starting integrated project's IP
directories, including its project-local FIR. No IP is edited or copied.
Compile, synthesis, placement, timing, bitstream and other large build
directories are not copied. Keep the baseline directory in place when moving
or building this candidate; the parent can package IP separately if necessary.
The generator refreshes candidate source/project files from that baseline, so
run it before applying further candidate edits. It never launches PDS.

Verification uses ModelSim at `C:/modeltech64_10.6e/win64` and imports the
existing letterbox integration testbench generator and pixel oracle. No new
duplicate functional test suite is introduced. Logs and `report.json` are in
`legacy_npu_verification/`.

## Exact functional change

For the legacy NPU exclusion, `integrated/source/top.v` changes the old retired
master tieoff block drives only VALID and response READY, leaving payload nets
undriven. The candidate explicitly drives all 44 retired master output fields:

| Crossbar interface | Candidate behavior |
| --- | --- |
| S02 write (`npu_out_axi_*`) | AW/W VALID = 0; payload/metadata = 0; BREADY = 1 |
| S02 read (`npu_s0_axi_*`) | ARVALID = 0; payload/metadata = 0; RREADY = 1 |
| S03 read (`npu_s1_axi_*`) | ARVALID = 0; payload/metadata = 0; RREADY = 1 |
| S04 read (`npu_s2_axi_*`) | ARVALID = 0; payload/metadata = 0; RREADY = 1 |

READY above belongs to inactive masters' **response consumption**, retaining
baseline behavior. No accelerator command READY, completion, interrupt or
success response is fabricated. Crossbar routing masks remain unchanged.

312 other copied source files are byte-identical after the two additional
delivery register/adapter edits for thumbnail integration. The isolated PDS
file rebases IP references and registers three thumbnail RTL files.
`legacy_npu_top.v.diff` contains the complete NPU tieoff change;
`display_integration.diff` also includes the register/adapter extension.
The manifest records before/after SHA-256 values.

## Dependencies that must remain active

| Legacy-looking name | Actual owner and reason to preserve |
| --- | --- |
| `npu_s3_axi_*` / S05 | Cam1 KF previous-frame DDR reads |
| `npu_s4_axi_*` / S06 | RGB letterbox DDR input reads, ID 0xd |
| `npu_reg_axi_*` / M02 | Delivery MMIO adapter at 0x40020000 |
| S03 writes (`prep2`) | Existing preprocess path |
| `pcie_rx_fifo` and `pcie_fifo` RX state machine | Generic host-to-FPGA transfer; not an instruction-controller instance |
| `delivery_hold`, cam5 diagnostics/publication/abort | Admission hold, drain and published-bank selection |
| `ddr_w_arb` masters 0..5 and 6 | Six camera writers plus delivery writer |

The excluded `pcie2npu/npu_ctl.v` instantiates `pcie_npu` and `instruction_buf`,
but none is instantiated by the selected top/PCIe RX hierarchy. The retained
PCIe RX completion is transfer completion, not legacy NPU command completion.
Do not remove or fake its handshake as part of NPU exclusion.

M02 has already been repurposed by the starting delivery integration. Software
must check delivery signature `0x444c5632` before issuing its register protocol;
legacy NPU commands must not be sent to this window. This candidate does not
provide a compatibility responder for old NPU commands. The parent owns the
driver/protocol audit and PDS/board validation.

## Verified evidence and limits

- Generator passed: 278 resolved project inputs, excluded-module checks,
  baseline source/project hashes unchanged, 312 other source files identical.
- ModelSim compiled 82 ordinary project RTL files with zero errors.
- Existing integration simulations passed for W=4 and W=64 with the candidate's
  actual 44 top assignments connected to the real crossbar. They check exact
  letterbox bytes, six competing writers, routing, MMIO backpressure/errors,
  and busy/queued/unpublished-bank freeze rejection.
- Existing production-camera admission hold/resume simulation passed.
- Simulations report width warnings: retained adapter PROT/ARLOCK width
  mismatches, the existing testbench's 7-bit host IDs connected to 4-bit slave
  IDs, and four retired 4-bit LEN nets zero-extended to 8-bit crossbar ports.
  These were not hidden or treated as full-top validation; logs retain them.
- Full `top.v` and four PDS-specific PCIe source files were not ModelSim
  compiled, matching the baseline runner's exclusions for declaration-order
  and duplicate-declaration incompatibilities. Encrypted vendor-IP elaboration,
  PDS synthesis/timing/resource reports and board runs remain unperformed.

These checks establish the source isolation and exercised fabric behavior;
they do not establish zero-copy end-to-end operation, reduced resource use,
display performance, or on-board correctness.
