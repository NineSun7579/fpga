# Autonomous thumbnail protocol

Status: implemented in isolated integrated_six_background; ModelSim evidence
is recorded in SIX_BACKGROUND_REPORT.md. Hosts must not enable this protocol
on existing bitstreams. Capability bit 4 (16), combined caps 31, identifies the
new implementation. Delivery base is 0x40020000. Existing
304-byte snapshot and RGB/on-demand registers retain their meanings.

Control at base+0x180: full-strobe 32-bit write 1 enables admission at future
admitted RAW SOFs; write 0 stops new thumbnail admission immediately. Reads:
bit0 requested enable, bit1 quiescent, bit2 thumbnail AXI quarantine; remaining
bits zero. Reset disables admission. Enable is rejected while an on-demand
thumbnail command or lease owns the destination. On-demand thumbnail commands
are rejected while enabled or draining. RGB commands may share the delivery
master. Disable does not cancel announced AW/W/B obligations. Host must write
0 and observe quiescent before using on-demand thumbnails or treating banks
as stable. A missing external response prevents quiescence and requires a
coordinated fabric reset. Bad B invalidates the affected attempt and quarantines
background writes; RAW remains independent. Disable preserves completed records.
Before an accepted legacy on-demand thumbnail command can write its destination,
that bank's record generation increments and valid/busy both clear. Legacy jobs
do not publish autonomous records. This prevents disabled background metadata
from validating payload later overwritten by an on-demand job.

Twelve 32-byte records start at base+0x200, last at base+0x360 (second beat
0x370). Physical camera 1..6 maps to record 2*(camera-1)+bank. Each has:

| Offset | Value |
| --- | --- |
| 0 | guard: bit0 busy, bit1 valid, bits31:2 generation |
| 4 | physical camera (1..6) |
| 8 | bank (0..1) |
| 12 | thumbnail destination in HMIC bus address units |
| 16 | corresponding RAW publication sequence, including zero after wrap |
| 20 | payload bytes (153600 for 320x240 RGB565) |
| 24 | width=320 in low16, height=240 in high16 |
| 28 | tag bus address |

Generation increments modulo 2^30 BEFORE the first payload write on reuse;
valid clears and busy sets in that same transition. Failed attempts remain
invalid after their writes drain. Valid sets only after a full admitted source
frame, successful retirement of every thumbnail payload burst and final tag,
and matching successful RAW publication. Thumbnail banks are independent of
RAW ping-pong banks. A producer may drop whole attempts on overflow/deadline;
it must never backpressure RAW. Even source x and y select unchanged RGB565.

Host reads guard, requires valid and !busy, reads both record beats and payload
and tag, then rereads guard. Accept only identical guards and matching record
sequence/tag (zero is a legitimate sequence). Retry if guard changed. No lease
or capture hold is required. Reuse may race reads; payload alone is insufficient.

Destinations retain the existing allowlist: base 0x0a200000, camera slot order
C5,C1,C2,C3,C4,C6, slot stride 0x80000, bank stride 0x40000. Payload is 16-beat
bursts with bus-address stride 256. HMIC uses 16-bit-word addresses within a
burst (8 units per 128-bit beat); the deployed host layout deliberately leaves
the existing gaps between bursts. Do not substitute byte-linear beat addresses.
Tag starts at destination+ceil(payload_bytes/256)*256, as in the RAW gap
convention; host DMA requests use the deployed bus-address convention.

PCIe singlebeat extension is limited to aligned record beats 0x200..0x370 and
control 0x180; the existing 0x000..0x120 snapshot window is unchanged. All other
addresses retain the existing burst policy. Board deployment and timing
acceptance remain parent-owned and have not been performed for this candidate.
