# TC05 detector history enable correction

Scope: isolated detector RTL, tests and receipts. No production/IP/old candidate edits, PDS runs, clock changes, timing exceptions or flashing. Whole construction and bitstream generation belong to the main session.

## Evidence and mechanism

V6 `evidence/all_reported_failing_paths.json` reports one slow setup failure: cam2 `core_start` to `history_4/gopdrm_36k/WEA[0]`, slack -0.037 ns, four LUT levels, routing 6.825 ns (92.706%). The old enable combines current frame markers, active, pixel-count limit and coordinate sampling predicates through `accept_pixel` and `accept_sample`.

TC05 registers only the state-dependent predicate:

`history_eligible = active && pixel_count < TOTAL_PIXELS && x % SAMPLE_STEP == 0 && y % SAMPLE_STEP == 0`.

The same-edge RAM enable is `rst_n && history_eligible && pixel_valid && !frame_start && !frame_end`. It depends on five one-bit inputs and can fit a LUT6; mapped levels, placement and route are not measured by this subagent. The original `accept_pixel` still controls pixel/coordinate progression. State qualification is calculated from the next state on the preceding edge, not by delaying an accepted pixel.

## State transition rationale

* Asynchronous reset clears eligibility with active; history and history_q remain unreset.
* Start takes priority over end, restores active and coordinates (0,0), and sets eligibility. Current start/end marker pixels are suppressed by combinational gating.
* End while active clears eligibility, including short/aborted frames. Inactive end holds false eligibility.
* An accepted pixel uses width-truncated next_x and next_y matching the original coordinate assignments. Eligibility is computed for these coordinates and `pixel_count < TOTAL_PIXELS-1`.
* The final pixel clears eligibility even though y saturates and x may wrap. Excess tail pixels cannot modify history. Stalls hold eligibility.
* SAMPLE_STEP=1 has no sample bubble: every accepted pixel still reads/writes history on its original edge. The last sample, read-first history_q, comparison/update stages and publication edge retain their original timing.

The reset base case and these transitions establish the predicate invariant by induction for positive legal geometry/step parameters. The RAM declaration, address progression, luma logic and RAM always block are unchanged. The rest of the TC03 detector is byte-identical aside from the new assignments and module/comment changes.

## Tests and bindings

Run `python project/fpga_v8_migration/timing_correction_05/tests/run_detector.py` from any directory. Each run creates a distinct receipts directory and an explicit compile_sources.json with input hashes. It compiles original, TC01, TC03 and TC05 detector modules under unique names. Generated test-only adapter `motion_stream_adapter_tc05_test` is the TC04 adapter with only its module name and detector binding changed; it is not a whole-design candidate dependency.

The test command explicitly passes `-vopt -voptargs=+acc`: this workstation's default simulator configuration disables optimization. The first compiled run (`detector_20261006_115520_515290`) timed out at 900 seconds in the five-geometry simulation without an acceptance result. Its compile log has zero errors/warnings; an independent audit confirmed all 563 protected inputs still match its pre-run hashes. Treat this directory as an incomplete attempt, not as a passing regression receipt.

Run `tests/check_monitor_fault.py` after the detector generator has created receipts to exercise the actual stress monitor with a forced stuck-low eligibility register. `monitor_fault_20261006_121215_129631/results.json` records PASS for the negative control: the HDL checker rejected the injected fault at 47 ns with `TC05 lookahead invariant`. This ModelSim setup can return exit code zero for HDL `$fatal`; tests therefore inspect the fatal diagnosis as well as process status. The passing negative control supports checker sensitivity, not candidate equivalence by itself.

An independent optimized positive stress preflight reused that directory's compiled checker with the force removed (fresh simulation invocation). `monitor_fault_20261006_121215_129631/positive_stress.log` records `PASS TC05 STRESS ALL`, errors 0, warnings 0, elapsed 3 seconds. All eight geometries completed; per-case cycle checks range from 24158 to 26484, history writes from 915 to 6007, and reset-edge checks are 44 per case. This preflight also confirmed optimization preserves hierarchical checker visibility before waiting for the full-resolution regressions.

The independent TC01 frame/history/literal oracle is reused by executing only its generator prefix with redirected paths. Five geometries include 640x480, packed 11-bit dimensions, sparse sampling, dense STEP=1 and 1x1. All eleven public outputs are compared on each clock, including reset, against original/TC01/TC03. Additional monitors compare same-edge history enable/address/luma, history_q, each written byte and complete retained history at markers/reset. Eight additional geometries exercise nonpower-of-two steps, one-row/column geometry, a step exceeding dimensions, all marker/valid combinations, repeated starts, stalls, tails, arbitrary input sequences and reset around end/publication phases. Asynchronous reset is also asserted between clock edges.

TC04 integration uses its robust paired adapter driver with the TC03 detector on the reference side and TC05 on the candidate side: two 640x480 seeds and one 64x48 seed. The full-resolution four-channel atomic register-record oracle binds all four adapters to TC05. Sources and generated bindings are recorded in receipts; old runners are not run or changed. Hashes of protected RTL, IP, tests, scripts and available project files are verified after the regressions.

For whole construction, register `rtl/block_motion_detector_tc05.v`, and bind every intended motion adapter detector instance to `block_motion_detector_tc05`. This detector has no new module dependencies or include files. Keep TC03 only if another still-bound instance requires it; never compile a renamed copy under the same TC05 module name. Test-only adapters/benches must not enter the PDS source list.

## Resource intent and risks

Default history remains 19200 bytes per detector with the original synchronous read-first inference template. The intended four-detector history budget remains 32 DRM, subject to actual synthesis verification. One new eligibility FF per detector and coordinate/count lookahead logic are introduced. No measured DRM total, post-map LUT depth, routed WNS, bitstream or board result is claimed here.

The baseline count is supported by V6 `evidence/motion_routed_resource_proof.json`: each of its four default detectors uses eight routed 1-bit DRM36K slices with a 15-bit address, read-first mode, logical depth 19200 and width 8; `routed_history_DRM36K_total` is 32 and logical_total_bits is 614400. This is baseline evidence only. Preserving the TC03 memory template gives TC05 the same inference intent, not a measured TC05 map result.

The new eligibility-D path includes accept_pixel, terminal-count lookahead and coordinate arithmetic; whole-design STA must check that this path does not become critical. For nonpower-of-two SAMPLE_STEP, modulo logic can cost more than default STEP=4. The current marker-to-RAM chain should shrink logically, but the V6 failure is routing-dominated, so fanout/placement can still defeat the intended improvement. RTL regression is evidence over the exercised traces, not a formal equivalence proof or physical timing acceptance.
