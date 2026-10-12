Isolated 50K-only TX guard/GE-skip experiment. Production 50K color-bar
sources, every 100H source, vendor IP and PDS projects are untouched.
prepare.py creates original_sfp_video_tx.v, candidate_sfp_video_tx.v,
byte-preserving integration.patch and production/IP hash manifest.
guard_only_sfp_video_tx.v is the same candidate with dedicated skips disabled
by parameter default; compile exactly one TX variant, never both modules.

Problem addressed in the symbol stream, not claimed as the physical cause:
an existing control ends BC(K); a following RGB565 word can start 50(D).
That cross-word BC(K)/50(D) matches the configured skip symbol literals.
If a PCS deletes it, it removes a payload byte and recovery is impossible.
Removing BC/28 from the last control likewise exposes mixed-K payload words
which the old receiver discards. Replicating BC/28 controls alone does not
eliminate either boundary vulnerability.

Candidate preserves the existing control signature and all pixel values.
It adds three-word lookahead to the final wire output; FIFO pop/read timing
and the producer's pixel pairing/recovery state are unchanged. The final
redundant BC/28 control immediately before a pixel word is replaced by
BC(K),FF(D),BC(K),FF(D): 0xFFBCFFBC, K=0101. The old decoder discards this
guard word; its D-byte ending prevents a trailing K28.5 from touching payload.
0xFF is a valid D31.7 data symbol, not a reserved invalid 8b10b character.
The guard is not represented as two fake pixels and does not change image
count. A state-changing control is never replaced by a guard.

With TX_GE_SKIP_ENABLE=1 (default), sufficiently early redundant blanking
controls are replaced, at 1/32 phase, by 0x50BC50BC/K=0101: two configured
BC(K)/50(D) skip pairs. Three following unchanged controls are required by
lookahead; after subsequent guard replacement, at least two intact BC/28
controls remain before payload. This gives the old rotation selector time
to reacquire phase after a two-byte skip insertion/deletion. SOF-high controls
are not skip candidates. TX_GE_SKIP_ENABLE=0 selects guard-only operation,
which can isolate guard effect from dedicated-skip availability in a board
experiment. On low captured readiness, queued wire words are flushed to the
producer's current control, preventing delayed payload leakage after loss.

This is not an Ethernet frame transmitter. The vendor's GE automatic-mode
transformation and deletion predicate are unverified. The local IP guide
documents configured K/D skip defaults BC/50 and example BC50BC50 skip sets;
it does not establish how arbitrary BC/FF guards or BC/28 status records are
processed by GE automatic mode. Therefore compatibility tests here model
post-PCS byte/K insertion/deletion only. No statement that GE will leave the
guard untouched, or that present board loss comes from CTC, is justified.

run_tests.py compiles actual candidate TX + production FIFO and captures one
1280x480 merged frame. A pixels are the saved real CAM5 RGB565 frame; B rows
alternate zero, 0x50BC and a 16-bit scan. Captured wire structure must show
307200 payload words, 307200 guards, and BC(K)/50(D) matches ONLY inside
explicit skip words. Mutation replay uses both archived pre-same-cycle-fix
RX and current production RX, all four initial byte offsets, and isolated
two-byte insertions/deletions alternating first/second skip pair. It compares
all 614400 pixel values/order, SOF and overflow, not just quotas. The archived
receiver is a conservative old selector test, not a verified byte-exact copy
of the currently burned 192245 bitstream's source.

Run from this directory:

    python prepare.py
    python run_tests.py
    python check_guard_only.py
    python check_recovery.py
    python verify.py

Final results: all 24 full-frame replays pass with exactly 614400 original
pixels in order, one SOF and zero overflow. Every edited replay makes
128 isolated pair edits and observes at least 128 phase reacquisitions,
including the archived old rotation selector. Guard-only also preserves
all 614400 pixels and eliminates every BC(K)/50(D) match in this captured
frame. The separate readiness-loss regression verifies unchanged FIFO drain,
queued-wire-payload flush and exact next-frame recovery. validation.json
records these results and the tested candidate SHA256
29a637f725a48323b8f8351221183cf823afa5917a41098bc748cd61969793cc.

Do not apply integration.patch to the live project while its parent build
is running. The output pipeline adds latency and logic; no PDS synthesis,
resource fit or timing check is performed here. An eventual 50K build must
check STA and preserve physical pin mapping/color-bar configuration.

Board experiment recommendation, only after regressions pass and parent
review: keep the old 100H bitstream, build this isolated 50K candidate with
the current pin/color-bar baseline, then compare full-frame counts and saved
CAM5 bar-edge slope against the existing 80->24 pixel drift. A guard-only
variant can distinguish cross-boundary protection from providing actual skip
opportunities. Better counts without correct image geometry are insufficient.
Retain both raw RGB565 and RK screenshot. No build/burn was performed here.

Saved-data observation: ambient CAM5 capture contains 49 pixels with low byte
0x50 (4 with high byte 0x50); current color-bar CAM5 capture has neither.
This is consistent with fewer BC(K)/50(D) opportunities but is not source-B
evidence or a physical deletion measurement. Color bars still show a 56-pixel
edge drift and short CAM6 input, so BC/50 matching alone is not established
as a complete explanation. Frame-wide splitter routing can conceal loss in
CAM5 quota while corrupting its row geometry.
