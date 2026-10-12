Receiver candidate investigation, 2026-10-03. All files are isolated fixtures.

Concrete current-receiver defect:

The byte sequence before removal is control `BC(K),28(D),st(D),BC(K)` then
`p0lo(D),p0hi(D),p1lo(D),p1hi(D)` then another control. Removing only the
control prefix leaves `st,BC(K),p0lo,p0hi` (K mask 2) and then
`p1lo,p1hi,BC(K),28` (K mask 4). The current decoder accepts only K=0 data
and K=9 controls. Both pixels are discarded even though all four pixel bytes
are present. Realignment occurs at the next intact control and cannot recover
these prior symbols; the aligner may also overlap/skip bytes when switching
its four-byte window. A decoder placed after that aligner cannot assume a
continuous symbol stream. Recovery must consume the raw HSST byte/K stream.

rx_symbol_candidate.sv bypasses the word aligner for parsing; the existing
wrapper still provides clock/reset/link acquisition in the fixture. The parser
retains a short byte/K reservoir, recognizes exact BC/28/status/BC controls,
recognizes status/BC suffixes after prefix deletion, recognizes an inserted
BC/28 prefix before another K-started control, and emits K=0 byte pairs as
little-endian RGB565. Payload value does not influence these K-qualified
rules. Control changes and payload share an ordered two-bank event FIFO.
Unknown fragments raise sticky o_malformed and stop payload admission until
the next intact control. The malformed indicator must participate in eventual
frame validity; a corrupted frame must not be published merely because counts
look plausible. Startup similarly waits for an intact control.

This grammar is uniquely decodable for the tested mutation model: complete
controls, two-byte K=0 pixels, control-prefix pair insertion/deletion, initial
offset 0..3, and no payload loss. It is NOT a general GE automatic-mode parser.
It does not recover missing payload bytes, arbitrary byte errors, standalone
GE idle sets, arbitrary K symbols, or simultaneous edits that remove both
prefix and suffix. Link interruptions must clear state. The candidate uses a
small variable-index combinational parser; timing/resource fit is unmeasured.
Its inferred two-bank memory must be checked before production use. No PDS
build or production module replacement has been performed.

Full actual-TX results are candidate_summary.json: original baseline and both
120-event BC/28 deletion cases preserve 614400 pixels exactly, one SOF, zero
overflow and zero malformed. Forced 424-event BC/50 deletion is unrecoverable:
613552 pixels, malformed=1. This confirms a limitation rather than a repair.
test_boundaries.py exercises initial offsets and edits at SOF and payload.
All 36 cases passed: exact 64 pixels, exactly one SOF, 64 frame pixels and
zero overflow. Cases include prefix deletion inside the single SOF-high
control, repeated SOF-high controls, deletion immediately before payload,
and insertion before SOF or payload, each at offsets 0,1,2,3.
Boundary vectors end with a partial control prefix where four-byte packing
requires padding. Arbitrary D-byte padding would be real payload under this
grammar and must not be used as a supposedly invisible terminator.

Vendor evidence:

Local UG041004_Logos2_HSSTLP_IP.pdf, PDF page 25, documents 9-bit SKIP
symbols with bit 8 identifying K (1) versus D (0). Page 29 gives the GE defaults
110111100 and 001010000 (K28.5/0xBC and D16.2/0x50). Page 35 defines the
example GE skip stream s0,s1,s0,s1 from those registers. Thus BC/50 is an
intentional documented GE default, not merely an unexplained literal.
Page 41 documents o_rxstatus: 001=SKIP add, 010=SKIP delete,
100=Bridge overflow, 101=CTC FIFO overflow, 110=CTC FIFO underflow,
111=Bridge underflow. This is a PIPE-described interface; verify status pulse
behavior in the selected GE configuration before converting pulse counts to
deleted-symbol counts. The wrapper already connects rxstatus_2 internally.
The generated wrapper parameter comment says GE_AUTO_EN changes C to I2 for
CTC, but neither that comment nor this IP guide specifies the complete
automatic substitution/deletion predicate. Physical board deletion is unproved.
The detailed referenced UG040008 HSSTLP user guide was not found in the
installed document scan. vendor_ctc_extract.txt preserves extracted pages.

Recommended next action: build diagnostics before promoting this parser.
Expose rxstatus histogram, raw error and phase-change counts, per-frame raw /
aligned / decoded payload counts and CRCs, and an event-triggered raw trace.
Correlate status 010 with rotation changes and count deficit on the board.
Compare against 50K emitted data count/CRC on the same frame. A diagnostic
candidate build should establish the actual symbol grammar seen by RX; only
then integrate a receiver tested against that captured stream.

TX protocol recommendation (design only): do not simply change BC/28 controls
to BC/50, since CTC would then be eligible to delete video-control bytes and
the receiver must also tolerate inserted SKIPs. For a coordinated protocol
revision, reserve standalone BC(K)/50(D) SKIP ordered sets, keep video status
in a distinct K-qualified record, and prevent a video-control trailing BC(K)
from touching unconstrained payload. A changed control record ending in a D
byte, or an independently delimited non-removable guard, can eliminate that
cross-boundary match. A guard made from arbitrary K=0 bytes is insufficient:
the old receiver treats it as pixels. The revised grammar must define guard
semantics, validate how GE automatic mode transforms records, and test all
SKIP insertion/deletion boundaries plus state transitions. No wire change is
safe to select from the present board count evidence alone.
