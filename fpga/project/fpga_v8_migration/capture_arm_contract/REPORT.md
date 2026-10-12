# Capture ARM contract correction

## Cause and reviewed correction

The whole-candidate review identifies a new combinational loop (baseline 0):
`u_v8_capture_lease/N9_1_6/Z -> u_v8_capture_control/N59_9/I0 -> N59_9/Z ->
u_v8_capture_lease/N9_1_6/I5 -> N9_1_6/Z`. Its source path is controller
config_valid (69-70), manager lease_block (72-73), wrapper write-engine
admission (107), wrapper engine_idle (53), and manager config_ready (71).
STA-3001 cuts timing arcs, leaving ambiguous functional ARM/SOF priority.

`fpga_v8_capture_control_axil_arm_v2.v` removes READY from the request decode
and tests READY only in the sequential dispatch decision. The original AW/W
holding registers already stage the complete immutable request. No extra
request queue is needed. This preserves immediate busy rejection, authoritative
registered accept/reject, original full API, and ARM-before-SOF admission.
`control.diff` gives the exact change; `ARM_STAGING_SEMANTICS.md` defines the
partial-slot, simultaneous-SOF, busy/start, delayed-ack, and sustained-VALID cases.

The manager, capture wrapper, production camera w_en/w/w_ctrl, DMA, official
FIFOs, and completed PCIe corrections remain immutable. Parent integration
needs to replace only the controller binding and module instantiation name.
The additional wrapper is a reviewable component harness with public reader,
release, capture diagnostics, and bus controls; it is not a production change.

## Simulation evidence

The cloned endpoint/router/controller/manager suite passes **499 operations,
4,288 observed events, 26,488 cycles**. Its manager idle predicate includes
the admitted SOF predicate to reproduce the reviewed feedback path. The
independent planned-event oracle checks all bus responses and ownership states,
matched and corrupt releases, host-held ARM rejection, both readers pending,
busy config rejection, SOF priority, delayed accept/reject, reset, backpressure,
and independent AW/W arrival orders. Results: `endpoint/artifacts/results.json`.

The first corrected actual capture/core/adapter pair suite passes all three
cases: small leases, reset ownership, and full 640x480. ARM uses the candidate
controller; every ARM explicitly races actual camera SOF. Full resolution
certifies five paired frames, **3,072,080 RAW bytes including tags** and
**6,144,000 prepared bytes**, compared byte-for-byte to the independent software
oracle. It verifies actual generated FIFOs, DMA writes, routed host/core reads,
backpressure, and immutable retained source/output banks. Reset cancels one
published ownership set with a write outstanding and validates recovery.
Results: `core/artifacts/results.json`.

The separate broader revision (`core_revision`) adds rejected ARM transactions
on actual start, ongoing pixel writing, and tag retirement; each holds AW/W
VALID while B is stalled for eight clocks and asserts no repeated request or
handshake. Its result receipt is independent of the first completed suite.
The `core_priority` suite additionally rearms an already armed manager
and aligns the controller commit with the production write engine's actual
synchronized `s_vsync_rise` pulse; it asserts both that pulse and denied admission.
The final `core_final_b` revision preserves those checks and holds the actual
camera DMA B handshake after the complete tag payload, then issues ARM while
that B is pending. It checks SLVERR, no ARM handshake, no publication/DMA done,
and retained WRITING ownership until the B is consumed. This is capture DMA
completion evidence; it does not change the separate PCIe final-B candidate.

The nine cloned immutable lease regressions also pass, including full resolution,
cooperative-only ownership, invalid geometry/bounds/alignment, actual abort,
short/overflow/flush/reset, tag/final-B publication, and exact protected-bank
data. These certify unchanged manager/capture behavior independently; they do
not substitute for the corrected-controller tests. Results:
`lease/artifacts/results.json`.

## Component synthesis evidence

`component_01` is a new isolated PDS component containing the real AXI128
endpoint, corrected full-API controller, manager, capture wrapper, production
camera engines, official distributed/DRM FIFOs, and production AXI DMA. Camera,
bus, DMA response, reader and release controls are dynamic; diagnostics and
public outputs are retained. It uses the frozen component project's virtual
port convention and a **131.25 MHz / 7.619048 ns** common input clock.

PDS compile and synthesis complete. `synthesize/snr.db` explicitly reports
**0 combinational loops and 0 latch loops**; the resource report gives
**0 latches**, **2,423 LUTs, 2,070 registers, 64 distributed RAM LUTs, 4 DRM**.
Retained resource hierarchies include controller 790 LUT/621 FF, manager
436/253, capture 619/589, DMA 391/417, and endpoint 187/190.

Slow-corner pre-route estimates: setup **+1.203 ns**, hold **+0.619 ns**, zero
failing endpoints among 4,958 same-clock checks; estimated Fmax 155.8603 MHz.
The 1,542 virtual ports exceed board IO count intentionally. No external IO
delay model is supplied, so these are internal component timing estimates.
Exact warnings and check-timing rows are retained in the audit artifacts.
Constant-probe "Loop was found" messages are optimizer diagnostics; the final
mapped check-timing database explicitly counts zero loops. No STA-3001 loop
false-path warning is used to obtain this result.

## Limits and immutability

No whole-PDS synthesis, device-map, PnR, board, SSH, external PCIe, or vendor DDR
clock integration was run. This common-clock component does not prove CDC,
physical IO timing, or whole-v2 closure. The unrelated endpoint eligible warning
is recorded exactly and its RTL is untouched. PCIe final-B completion remains
the other completed candidate's responsibility.

Warning inventory across compile plus synthesis includes 304 missing-input-delay
and 1,237 missing-output-delay warnings, 290 dangling-instance removals,
256 Verilog-2020 constant/optimization warnings, 112 constant-probe loop messages,
108 ignored vendor simulation-system-task warnings, and the endpoint's
Verilog-2021 `eligible.addr_end_1` warning twice. The exact line text, including
vendor no-drive injection pins and fanout warnings, is in
`artifacts/warnings_exact.json`; mapped check-timing evidence remains authoritative.

`artifacts/immutable_before.json` pins **1,919 files** across production source,
IP, existing PDS registrations, capture endpoint/lease/core artifacts, and whole
candidate/frozen baseline. The final audit compares exact bytes against this
snapshot and separately against the existing 119-file core-contract snapshot
and the whole candidate's protected frozen-source manifest. The reviewed whole
candidate's current entire tree is included in the 1,919-file local snapshot.
Bindings, API hashes, clone transformations, source diff, synthesis source pins,
warnings, and receipts are all local to this new directory.

Final audit status: **PASS**. All 1,919 locally pinned files, all 119 files in
the existing core snapshot, and all 1,091 whole frozen protected files retain
their exact hashes. The original complete controller API compares equal after
normalizing only the module name and whitespace/comments. Candidate SHA256:
`b65d5cc7a6e0bc1bdf765dfd6da0bb9488cc0ab27d95fe7e6db730170aa857e9`.
All four independent corrected-controller capture/core suites pass their three
cases, including the final pending-B and synchronized-SOF priority revision.
The final evidence is `artifacts/review_receipt.json`.
