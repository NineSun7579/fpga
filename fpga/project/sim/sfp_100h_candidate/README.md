Isolated 100H diagnostics + selectable raw-symbol receiver integration.

No production files, PDS project files, 50K sources or vendor IP were changed.
No PDS process was launched. candidate/ contains generated production-source
copies; original/ contains byte-exact backups. manifest.json records original
source and vendor-IP SHA256. prepare.py checks every hash after generation.
integration.patch is a byte-preserving unified diff for review/application
after the parent build finishes; it is not applied to production here.
The unchanged production hsst_sfp IP remains referenced by the wrapper; only
the wrapper adds raw data/K/status/error/phase/link outputs. The simulation
uses an HSST port stub and establishes no physical CTC behavior.

candidate/top.v has SFP_NEW_PARSER=0 by default. Mode 0 uses the original
aligned word decoder and keeps the original status/counter ABI. Mode 1 uses
the raw HSST stream and raw synchronized lane enable, bypassing lossy word
realignment. The parser itself acquires an intact BC/28 control before
admitting payload. Link loss clears partial-byte and event-FIFO state.
Its sticky malformed flag is visible in diagnostic bank word 0. The existing
frame writer is NOT changed to veto malformed frames; this is a diagnostic
candidate, not a complete frame-integrity solution. A mode-1 production
promotion must establish actual board symbol grammar and frame-validity policy.

Register-map audit: ovreg_axil_decode.v routes reads at +0x190..+0x1C0 to
camera CDC registers, overriding PREP. Those addresses and every previous
SFP diagnostic (+0x120..+0x180) remain untouched. +0x1D0..+0x1F0 were unused
in prep_regs and retain PREP routing. The real PCIe ingress rounds down
addr[3:0]; all three new addresses are aligned and aliases are tested.

| Absolute address | Behavior |
| --- | --- |
| 0x200001D0 | Write bits 3:0=index; bit 8=capture current coherent bank. Byte 0 strobe required; capture also requires byte 1 strobe. Read index. |
| 0x200001E0 | Read indexed word from frozen bank. |
| 0x200001F0 | Read capture sequence; increments only on capture. |

Write 0x100 to +0x1D0 once, then write index 0..15 without bit 8 and read
+0x1E0 for each word. Values stay frozen while live counters advance. Use
read_snapshot.py with the parent's existing host read32/write32 functions;
the helper imports no board transport and performs no operation itself.
Do not run competing bank capture/read clients concurrently.

| Index | Meaning |
| ---: | --- |
| 0 | 0x52580000 OR parser mode at bit 8, sticky malformed bit 1, raw lane enable bit 0 |
| 1 / 2 | Cumulative status=010 delete / status=001 add cycles |
| 3 / 4 | Cumulative raw K-mask 2 / 4 words |
| 5 | Cumulative alignment rotation changes while raw lane enabled |
| 6 / 7 | Cycles with any raw disparity / decode error in the previous decoded SOF-to-SOF interval |
| 8 | DE pixel count in the previous decoded SOF-to-SOF interval |
| 9 | Raw K=0 words times two in the same decoded SOF-to-SOF interval |
| 10 / 11 | K-qualified BC/50 / BC/28 pair matches, within or across raw words |
| 12 | Cycles with raw status 4..7 (bridge/CTC FIFO errors) |
| 13 | Decoder/parser overflow cycles |
| 14 | Raw lane-enable falling edges |
| 15 | Decoded SOF rising edges |

All cumulative counters wrap at 32 bits. Error counters count cycles, not
individual bad bytes. Status counters also count cycles; do not assume one
status cycle equals one physical deletion without vendor/board evidence.
Raw K=0 accounting omits data bytes in mixed words and uses decoded SOF as
its interval boundary, delayed by the parser queue. Word 9 is a diagnostic
comparison, not a valid independent transmitted-pixel quota. Mode-0 malformed
is tied low. Counters continue across link loss except parser-local state.
RX reset clears counters. Host reset clears frozen capture/index state.

sfp_rx_diagnostics holds an entire 512-bit source bank for a request/ack
handshake. Host synchronizes ack and two data stages before accepting it.
The host periodically requests a fresh live bank; the register capture then
freezes that already-coherent bank. No running binary counter is sampled by
independent per-bit synchronizers. Physical CDC constraints/placement still
need review in the eventual PDS build; no timing exceptions were added here.

Validation commands, run in this directory:

    python prepare.py
    python run_tests.py
    python test_registers.py
    python audit_top.py

run_tests extracts the exact OLD/NEW generate branch from candidate/top.v
into a subsystem shell. It tests the actual candidate link wrapper, selected
parser, production splitter and both real async FIFO implementations.
The full frames use the actual TX capture from saved CAM5 RGB565 + synthetic
B zero/0x50BC/scan rows. CAM5 and CAM6 values are independently checked against
the complete source image, not merely quotas. It includes no-edit baseline,
120-event deletion immediately before B, 120-event insertion, earlier-control
deletion, link loss during a partial frame, and reset during a partial frame.
The BC/50 payload-deletion case checks malformed and both resulting split
counts; it cannot restore the deleted payload bytes. The default OLD branch
is separately tested for exact baseline identity on both camera outputs.
The earlier 36-case symbol-boundary regression is in sfp_payload_probe/.

test_registers runs the legacy dual-mode prep_regs ABI tests, independent
AW/W write timing, WSTRB behavior, frozen 16-word reads and R backpressure.
The production PCIe address-alignment expression, axi_to_axi_lite and
ovreg_axil_decode verify existing CDC/PREP/SCCB routes and all 16 low-bit
aliases of each new address. That routing test uses a PREP sentinel; actual
new register semantics are separately tested against candidate prep_regs.
A two-clock counter test verifies frame capture, status/errors, pair matches,
link loss, reset and bundled-data snapshots.

Full top ModelSim compilation does NOT pass: untouched baseline has 174
forward-declaration/implicit-net and duplicate-declaration diagnostics.
audit_top confirms candidate has exactly those same diagnostics, zero new.
The isolated datapath and register modules compile and simulate cleanly.
No full top elaboration, DDR/PCIe board test, synthesis, resource estimate or
timing-fit claim is made. The parser's variable shifts/indices and unrolled
combinational scan need synthesis/timing review before burning mode 1.
Static storage only: parser event RAM is 2048x19=38912 bits, the same nominal
event capacity as the original decoder; it has one explicit write per parity
bank per clock. Diagnostic state includes sixteen 32-bit counters and several
512-bit coherent/frozen banks. These source-level bit counts are not a PDS
resource estimate and do not establish block-RAM inference or LUT/register fit.

Build recommendation once the parent's PDS process is finished: first use
mode 0 diagnostic-only candidate, preserving existing decode behavior, and
capture status/mixed-K/phase/errors/frame counts during color bars. Compare
with 50K transmitted count/CRC. Only promote mode 1 after a raw board trace
matches its tested grammar. Add the two new .sv files to an isolated PDS copy
and use candidate top/link/prep paths; do not replace vendor IP or mutate the
live production project while another build is running.
