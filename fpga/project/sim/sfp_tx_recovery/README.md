# Sim-only actual50K TX recovery candidate

## Subsequent production verification

Parent applied the candidate to production. Direct production compilation
passes both regressions: `production.log` has 43 cases, zero errors and zero
forbidden payload words; `full_production.log` has two full merged frames,
1,228,800 matching decoded pixels and 614,400 pixels per camera, zero errors.
Production differs from the candidate only by removing `only ` in the
`wait_frame` comment (`production_vs_candidate.diff`); executable tokens
match exactly. Production FIFO remains byte-identical.

`archived_original/sfp_video_tx.v` preserves the original negative control.
It was reconstructed by reversing the known candidate edits, then verified
against the SHA-256 captured before production changed:
`7dd844ad6fd0989abf98c965e972028a78d7abd24efccf68d708d3fb63632f11`.
The original runner now always compiles this archive, not live production.
Its rerun confirms 8,824 forbidden post-fault words and expected failure.

Production TX SHA-256:
`4da7d9cdc620e42143c18135f51b7ac8177284bce4c09b61cf9a1e397a46c76d`.
`production_verification_hashes.json` contains all production and archive
hashes; the audit verified them unchanged before and after simulations.
No production mutation, PDS launch, or build polling occurred. The active
PDS build uses older archived TX and needs a subsequent build.

```powershell
python project/sim/sfp_tx_recovery/verify_production.py
& project/sim/sfp_tx_recovery/run.ps1 production
& project/sim/sfp_tx_recovery/run.ps1 original
& project/sim/sfp_tx_recovery/run_full.ps1 production
python project/sim/sfp_tx_recovery/verify_production.py
```

Do not rerun `make_candidate.py` after the production change: the existing
candidate and original source-hash manifest preserve the initial baseline.
The remaining text records the earlier isolated-candidate validation.

Production RTL and PDS projects are untouched. `candidate/sfp_video_tx.v` is
derived byte-for-byte from the actual50K TX except for `candidate.diff`.
`candidate/video_async_fifo.v` is an exact copy of the actual50K FIFO, with
its original depth of 512. No FIFO logic change is required.

The TX continues popping the FIFO on every nonempty fabric clock even when
`tx_go` is low. Reset or a sampled low `tx_go` sets `wait_frame` and clears
the pending pixel. While waiting, consumed input controls still propagate,
but payload cannot be paired or emitted. A consumed `head_vs && !head_de`
symbol with `tx_go` high clears the gate. Any subsequent sampled readiness
drop sets it again. Readiness must remain high to retain that authorization.
This intentionally accepts a high VS level during the pulse, rather than
requiring its rising edge. The next active frame is complete when readiness
returns during VS; otherwise the remaining partial frame is discarded until
the next VS pulse.

The frame interrupted before readiness dropped can already have a prefix
at the receiver. This candidate prevents further partial payload after
recovery; it does not retract already transmitted pixels. Startup active
data without a consumed VS is similarly discarded.

Run from workspace root in PowerShell:

```powershell
python project/sim/sfp_tx_recovery/make_candidate.py
& project/sim/sfp_tx_recovery/run.ps1 candidate
& project/sim/sfp_tx_recovery/run.ps1 original
& project/sim/sfp_tx_recovery/run_full.ps1
```

`original` is an expected-failure negative control: the runner succeeds only
if the unmodified production TX fails and emits payload after a readiness
fault before the required VS boundary. Separate ModelSim libraries bind the
actual50K TX to its own FIFO. Recovery uses the existing100H RX decoder;
the full-size continuous test also uses its existing splitter and FIFO.
All libraries and logs are local to this directory.

Recovery coverage: 43 cases, including two reset/startup baselines; odd/even
midrow, horizontal blank, just before VS, VS rising/high/falling; low periods
of 1, 3, 17, 600 and 2200 source clocks; and readiness falling again after an
accepted VS and rising midrow. Source/fabric clocks are 62.5/125 MHz, matching
the existing actual-merge full test. Geometry is reduced to two contiguous
64-pixel camera rows, six rows per frame. Symbols embed frame and pixel
identity. Checks cover forbidden payload, control propagation while discarding,
first pixel/order/last pixel, complete first recovered frame, steady frames,
TX FIFO full and100H decoder overflow. Long outages exceed FIFO depth and
span multiple VS pulses. The monitor uses consumed symbols and synchronized
readiness, never the candidate's recovery register.

Verified with ModelSim SE-64 10.6e:

- `candidate.log`: `TB_PASS recovery`, 43 cases, zero errors/forbidden words.
  Every final accepted recovery frame has 768 pixels in order. Peak measured
  TX occupancy 1; peak decoder occupancy 2; no overflow.
- `original.log`: expected `TB_FAIL recovery`; demonstrates startup leakage
  and post-fault partial payload, with the same unchanged decoder and TB:
  8,824 forbidden post-fault payload words, 2,122 startup pixels, 22,309
  total check failures across the same 43 cases.
- `full.log`: `TB_PASS full`, two 1280x480 merged frames, 1,228,800 decoded
  pixels and 614,400 pixels per split camera, all matching, zero errors.
  This reuses `../sfp_full/tb_sfp_full.sv` and its configuration read-only.

`source_hashes.json` records SHA-256 of the production TX/FIFO and100H decoder
used to generate the candidate. Candidate generation preserves original
comment bytes and CRCRLF newlines. This is parallel RTL simulation with ideal
word transport, not a PCS/HSST, independent-reset, or hardware validation.
