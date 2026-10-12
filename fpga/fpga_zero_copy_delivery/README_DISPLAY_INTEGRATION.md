# Cam5 display endpoint integration candidate

This is the first **cam5-only, leased-frame display benchmark** integration.
Six camera capture/display paths and RAW RK3568 inference remain in place.
The delivery adapter shares existing S06 DDR reads and m6 DDR writes between
RGB888 letterbox and the real RGB565 thumbnail endpoint. It does not implement
continuous six-camera display offload, change the viewer, or prove performance.
Full six-camera offload needs a separate design for safe ownership of each
camera's published frames and each consumer's output buffers.

## Build inputs and generation

```powershell
# Run from repository root. No PDS or board operations occur here.
python fpga_zero_copy_delivery/make_integrated.py
python fpga_zero_copy_delivery/verify_integrated.py
```

`make_integrated.py` requires all three real `display_scaler/` RTL inputs before
touching candidate files. It creates no placeholder or blackbox. The current
endpoint exists and is registered in `integrated/project/project.pds` as:

- `source/display/display_thumbnail_ddr.v`
- `source/display/rgb565_display_decimator.v`
- `source/display/display_rgb565_pack128.v`

The generator copies them, records their hashes, and retains relative baseline
IP references. It also preserves the retired legacy NPU tieoffs. Only these
existing RTL files are modified relative to the letterbox integrated baseline:

- `source/top.v`: the existing deterministic retired NPU master tieoffs.
- `source/delivery/delivery_regs.v`: capabilities, selected mode, immutable
  mode-specific destination, selected output size and mode-write guards.
- `source/delivery/delivery_top_adapter.v`: both real cores and the DDR mux.

312 other baseline source files are byte-identical. The PDS project additionally
registers the three display RTL files and rebases IP references. Regeneration
refreshes generated files from the baseline and current endpoint inputs;
apply any further generated-source changes through the generator.
`display_integration.diff` contains all existing-RTL edits;
`legacy_npu_manifest.json` records source exclusions, hashes and resolved inputs.

## MMIO controls

All offsets below are relative to M02 base `0x40020000`, on the existing
16-byte register stride. Signature remains `0x444c5632` (DLV2).

| Offset | Access | Meaning |
| --- | --- | --- |
| `+0x00` | R | DLV2 signature, unchanged |
| `+0x10` | R | bit0 hold, bit1 frozen, bit2 busy, bit3 completed, bit4 failed, bit5 selected-core configuration error, bit6 quarantined |
| `+0x20` | RW | Existing command: write 1 to hold; write 3 after frozen to submit; write 0 after completion to release |
| `+0x30` | R | Frozen cam5 source base, unchanged |
| `+0x40` | RW | Destination: only the selected mode's fixed destination is accepted |
| `+0x50` | R | Capture lease epoch, unchanged |
| `+0x60` | R | Selected mode's logical output byte count |
| `+0x70` | R | Last job cycles, unchanged |
| `+0x80` | R | RAW input byte count, unchanged (`640*480*2`) |
| `+0x90` | R | Completed jobs counter, unchanged |
| `+0xa0` | R | Capabilities = 3: bit0 RGB888 letterbox, bit1 RGB565 thumbnail |
| `+0xb0` | RW | Mode: 0 = RGB888 letterbox (reset default); 1 = RGB565 thumbnail |

Mode and destination writes require all four byte strobes. Invalid modes,
partial mode writes, mode writes while busy/pending, while `capture_hold=1`,
or in quarantine return SLVERR and leave state unchanged. Mode selection also
sets the fixed destination and clears stale completion/failure/last-cycle state;
it does not reset the completed-jobs counter. Unknown offsets return SLVERR.

| Mode | Geometry | Destination | `+0x60` at production geometry |
| --- | --- | --- | --- |
| 0 | 640x480 RAW -> 640x640 RGB888 letterbox | `0x0a000000` | 1,228,800 bytes (`0x12c000`) |
| 1 | 640x480 RAW -> 320x240 RGB565, even-row/even-column sampling | `0x0a200000` | 153,600 bytes (`0x25800`) |

RGB's reserved native-address range ends at `0x0a12c000`; thumbnail uses
`0x0a200000..0x0a225800` exclusively (end address excluded). Both retain the
native HMIC burst layout: 16-bit-word base addresses, up to 16 beats per burst,
and 256 native address units between full bursts. Logical output bytes must
be unpacked using that existing native layout; they are not a promise of a
contiguous PCIe-readable physical byte array.

## Lease and core ownership

For thumbnail software: verify DLV2 and capability bit1; with hold=0 and idle,
write mode=1, verify mode/destination/size; write hold=1; wait for frozen;
write command=3; wait for completed while checking failed/quarantined; read
the output under the lease; release hold=0; select mode=0 to restore letterbox.
The existing cam5 quiet/drain/published-bank admission checks are unchanged.

Only the selected core sees command VALID. Its AXI request/response channels
are routed to S06/m6; inactive core inputs are gated to zero and receive no
response VALID or READY. Both cores' busy signals contribute to status, so
an in-flight owner cannot be switched out. The mode remains fixed throughout
hold, command pending, active processing and fault quarantine. Completion
comes from the selected real core; no empty completion is synthesized.

Thumbnail completion requires the final write B response **and all announced
input reads/tail pixels to drain**. A fault keeps the lease and selected owner
quarantined; reset must include the connected fabric. Software must not try
to escape a failed transfer by switching modes or prematurely reusing buffers.

## Validation limits

The verifier compiles ordinary candidate project RTL, reruns the real crossbar
and seven-master arbitration tests with the retired top tieoffs, and adds mode
and capability checks to the existing RGB tests. It extends the endpoint's
physical-memory testbench through the real MMIO adapter and core mux to check
thumbnail bytes, final-B/tail-drain ordering, busy/held writes, fault quarantine
and restoration to RGB mode. Test results live in
`legacy_npu_verification/report.json` and its logs.

Verified results for this candidate: 82 ordinary project RTL files compiled
with zero errors; RGB crossbar/arbitration cases W=4/W=64 and camera hold/resume
passed; both 640x480 thumbnail cases matched 153,600 payload bytes and 307,264
physical bytes including gaps/guards. Read- and write-fault cases at 64x16
passed quarantine/ownership checks and reset recovery, then matched the
512-byte thumbnail and its physical gaps/guards. Simulation width warnings
from the retained bridge and testbench are recorded in the logs.

Full top-level/vendor-IP elaboration, PDS resource/timing results, driver
compatibility, cam5 on-board performance and six-camera live behavior remain
parent validation tasks. No PDS or board operations are part of this delivery.
