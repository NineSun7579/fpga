# Background viewer candidate

Implemented isolated `six_camera_background_viewer_src`, target
`detview_six_camera_background_candidate`. Only this clone and this report are
owned by this work. No RTL, FPGA project, external scripts, board, PDS or commits
were touched. Parent owns full target compilation and hardware acceptance.

Default RAW performs no background protocol negotiation. Both
`DETVIEW_FPGA_BACKGROUND_THUMBNAIL=1` and existing
`DETVIEW_FPGA_SIX_THUMBNAIL=1` select autonomous display. Explicit background
requests on endpoints without capability value16 fail clearly before control
or record operations. Legacy SIX-only thumbnail fallback is accepted only when
negotiated capabilities lack value16. SIX-only mode on a background-capable
endpoint fails with the two-variable requirement.

Before workers start, lease then DMA protects signature, geometry, supported
cameras, capabilities31, legacy idle/freeze and disabled/quiescent status
verification. Full16-byte control write1 enables once; readback verifies enable
without quarantine. After every worker stops and joins, write0 stops admissions
and status polls require quiescent. A two-second drain deadline retains process,
fd, mappings and lease through the existing SIGSTOP quarantine; it never claims
AXI retirement. Control errors and quarantine also retain lifetime.

The copied pure reader is unchanged and SHA256-pinned in the clone manifest.
The callback adapter reads each first16-byte record half atomically for guard,
physical camera, bank and destination; the second half supplies sequence,
payload length, packed320x240 geometry and tag address. Every identity/address
is checked against the immutable twelve-bank allowlist, C5,C1,C2,C3,C4,C6 slots.
Tag displacement is ceil(153600/256)*256=153600, compile-time asserted. One host
transfer reads contiguous153616 bytes into low RX; tag is at153600. HMIC bus
addresses preserve deployed burst stride256; no byte-linear beat substitution.
Metadata uses RX1MiB. All accesses stay below the reserved RX2MiB shared input.
Corrected command/address/offset/length rejects the copy. The DMA critical
section includes ioctl validation and the complete owned copy.

Autonomous reads take individual DMA locks and no endpoint lease; no selectors
are written. Lease is used for enable/disable control and retained legacy
transactions. RGB shared-input callbacks retain their original lease then DMA
borrow locks throughout, because direct callback source semantics remain
uncertain. RAW readers still take only DMA. The adapter tests prove DMA-only
availability under a lease and exclusion under a borrowed RGB session.

Background display has an independent cursor. Guard/sequence/tag validation
does not commit it: workers recheck source generation and display eligibility
first, then commit and publish. Rejected eligibility resets/retries without
advancing the background cursor. RAW inference/stereo/full-view/HDMI and
calibration remain unchanged. Manifest byte checks cover the complete inference
and display class region, RAW transfer and analytics blocks, RGB borrow callback,
DMA timeout/quarantine, all non-ASCII main bytes, and all other copied sources.
Only main.cpp and detview.pro differ among baseline files.

Five-second background logs count validated frames/bytes, retries, reuse/tag
drops, no-fresh outcomes, operation count, DMA wait/transfer/copy nanoseconds.
Worker logs add committed frames and eligibility drops. Existing capture logs
measure delivered rate. These distinguish read throughput from actual display
publication; no sustained hardware rate is asserted.

Local validation (logs inside clone): new adapter fake tests cover all twelve
maps, full128-bit non-scalar identity regression, scratch/owned-copy canaries,
metadata and payload operation corrections, writer reuse, tag mismatch, sequence
wrap, half-range ambiguity, missing capability without I/O and delayed commit.
The unchanged reader passes128 meaningful adversarial tests. Existing standalone
thumbnail tests pass534 cases, snapshot transport1545 cases, frame metrics216
checks, temporal118 checks and MVP decode pass. Qt QMutex endpoint lock, RAW
camera DMA, HDMI pairing/geometry and inference geometry tests also pass.
Full vision/display and complete target checks still
require the parent's Linux target toolchain. No device or fabric drain was tested.
