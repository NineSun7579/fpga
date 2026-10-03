# TX head pipeline: applied and verified

Only production `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v` changed. `candidate.diff` gives the production patch; `archived_original/sfp_video_tx.v` preserves every original byte. Candidate and production are now byte-identical. The edit was applied only after candidate recovery and full-frame tests passed. Existing FIFO, FDC, top, decoder, splitter and protected IP were not edited. No PDS or timing-report commands were launched for this task.

The stage captures the pre-pop 19-bit FIFO head, pop-valid and readiness. The packer consumes the captured head on the following fabric edge; FIFO pop still occurs on every nonempty edge. Control bits, pixel pairing, recovery authorization and last VS/HS all use the staged consumption. `payload_go = tx_go && head_go_q` prevents a current sampled readiness drop from emitting queued payload and prevents a word captured while readiness was low from authorizing recovery on readiness rise. `txd` resets to constant `32'hBC0028BC`. Latency increases by one fabric cycle (8 ns).

Candidate and direct-production ModelSim compilation/tests both PASS:

- Original 43 recovery cases, zero errors/forbidden words/startup pixels.
- One additional readiness-phase case (44 total), with 8 ns phase shift; verifies a queued word captured while readiness was low when current readiness is high. `STAGE_GO low_now_queued_active=20378 high_now_captured_low=1`; coverage checks require both to occur. All 44 cases pass with unchanged first/last pixel, order, complete recovered-frame, overflow, continuous-drain and discarded-control checks.
- Two full 1280x480 merged frames through the actual decoder and camera splitter: 1,228,800 matching decoded pixels, 614,400 matching pixels per camera, 614,400 payload words, zero errors.

The recovery monitor independently models the one-cycle delay using raw FIFO pop/head and sampled readiness, not the DUT head-stage registers or wait_frame. The existing full-frame TB/configuration is reused unchanged. Original recovery tests/logs remain in `../sfp_tx_recovery`; this directory contains isolated libraries/logs. The first extra coverage attempt revealed that the original stimulus lacked the readiness-rise queued-word phase; the 8 ns shifted case covers it without changing RTL or weakening assertions.

SHA-256 (audited before/after production simulation):

```
TX before: 4da7d9cdc620e42143c18135f51b7ac8177284bce4c09b61cf9a1e397a46c76d
TX after:  79236044f0302db5227201b542aa073f778656672ef447f9731a50af79f4d230
FIFO:      17c2892ddc2f707fce1ff78fcb736528f7cd6d72b9efeccda52fa8f8706475b5
```

Reproduce:

```powershell
& project/sim/sfp_tx_head_pipeline/run.ps1 candidate
& project/sim/sfp_tx_head_pipeline/run_full.ps1 candidate
& project/sim/sfp_tx_head_pipeline/run.ps1 production
& project/sim/sfp_tx_head_pipeline/run_full.ps1 production
python project/sim/sfp_tx_head_pipeline/apply_and_audit.py final
```

Do not rerun `../sfp_tx_recovery/prepare_head_pipeline.py`: it is intentionally guarded against replacing the baseline archive. The copied runner's `original` expected-failure mode predates this pipeline and is not an appropriate negative control for this archived recovery-correct baseline; it was not run.

Timing closure remains unproven. The head register separates the depth-512 RAM selection from packing but does not establish that the read mux meets 8 ns, fix related-domain 4 ns paths by itself, or justify any CDC exception. Full synthesis/PnR/STA rebuild belongs to the parent; the preexisting damaged work route cannot validate this edit. Parallel RTL transport tests do not model HSST/PCS or metastability.
