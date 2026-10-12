# TC04 isolated camera candidate

`rtl/ov5640_cdc_tc04.v` uses seven registered lower-prefix all-ones flags
for each source statistics counter. The flags describe the current counter,
not a delayed increment. High nibble enables combine valid/full directly with
these flags. Each flag's next value is computed from the old lower prefix:
`AND(old upper prefix bits) AND (old bit 0 XOR increment)`.
Asynchronous reset and frame start clear every flag. Frame start writes 0/1
to the low nibble, clears high nibbles, and snapshots the old counters exactly
as TC03 does. Counters retain 32-bit modulo behavior.

The V5 evidence contains 25 failing paths. Camera paths 1/2 run from the falling
edge `cmos_frame_valid_r` to `src_drop[29/31]` CE, slack -0.554 ns, clock skew
-1.663 ns. Their four logic levels include drop-carry nodes for slices 1, 4,
and 6; the reported data-path logic/route delays are 0.667/3.899 ns. TC04 removes
the valid-dependent wide prefix reduction from high counter enables. Routed
improvement remains unverified; this regression does not invoke PDS.

Run `python project/fpga_v8_migration/timing_correction_04/camera_regression.py`
from the repository root. This camera-only script compiles the frozen V5
`ov5640_cdc_tc03.v` reference and the explicitly bound TC04 candidate in its own
ModelSim library, with the actual frozen V4 FIFO IP and PANGO simulation
primitives. It reuses TC03's three clock pairs and four seeds (12 scenarios).
No existing runner, production RTL, V5 or TC03 files are edited.

Checks cover all eight public outputs at clock edges, source state, FIFO
controls, an independent 32-bit counter oracle, and all predictor invariants.
Directed deposits initialize both counters and every added predictor and then
exercise hold/increment transitions around 4-bit through 32-bit boundaries,
including modulo wrap. Frame-first and asynchronous-reset cases start with
all predictors asserted. The 74,000-cycle real-FIFO overflow phase starts from
reset without force/deposits, inserts stalls, and requires natural 16-bit
carries in both counters. Random stimulus and resets follow.

`camera_artifacts/results.json` is written only after all 12 simulations finish
with PASS markers and byte-level SHA256 checks verify protected input files.
Compile and simulation logs, input hashes and original full camera path details
are retained alongside it.
