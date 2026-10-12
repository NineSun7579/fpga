# FPGA inference RGB888 before/after result

Evidence: rgb888_trial_1791561582715191600/trial.json and paired_*.jsonl.
Both modes passed 10 warmups plus240 alternating frozen-frame pairs with exact
1,228,800-byte input parity and all native RKNN output bytes equal. No stderr.
Model: pinned V8 square640 input; source default C5. RGB565 display stayed on
the established RAW route. Frequencies and thermal snapshots were recorded.

| Measurement | CPU conversion path | FPGA path | Change |
|---|---:|---:|---:|
| Conventional inputs_set: stage wall ms |39.0023|49.6157|slower|
| Conventional inputs_set: stage throughput /s |25.6395|20.1549|-21.391%|
| Conventional inputs_set: process CPU ms |13.5256|16.3684|higher|
| DMA-BUF: stage wall ms |40.2422|39.7634|slightly faster|
| DMA-BUF: stage throughput /s |24.8495|25.1488|+1.204%|
| DMA-BUF: process CPU ms |14.0020|6.1835|-55.839%|

Conventional candidate submits a borrowed coherent RX mapping, whereas CPU
baseline submits ordinary memory. inputs_set takes11.379ms versus0.720ms;
this is not an isolated arithmetic conversion benchmark. The borrowed pointer
submission is the main measured regression. Shared candidate submission/lease
takes0.028ms versus CPU inputs_set0.703ms. CPU RAW DMA/copy plus preprocessing
is7.149+3.235=10.384ms; FPGA conversion plus RGB transfer is10.231ms. Transport
largely offsets the saved conversion wall time. Square padded RGB payload is
twice the full640x480 RGB565 RAW payload.

Conclusion: current implementation substantially saves per-path process CPU
when DMA-BUF is used, with only a small stage-throughput gain. Conventional
submission from coherent RX should not be deployed as a speed improvement.
These standalone stage rates are not live MVP viewer completion/display FPS.
Live MVP uses480-high input and requires same-frame analytics integration.

Original imagefcb2e44d… and viewer73613d52… restored; verified PID5650.
Post-restoration health: mean C1/2/3/4/5/6 delivered capture FPS
41.92/43.17/25.70/25.70/39.38/39.48, RKNN mean completed3.905/s.
New-paint FPS34.04 versus original baseline38.62; swap35.02 versus41.03.
Restoration checks pass configured85% ratio, but display means are11.85%/14.63%
below baseline, so exact equal display performance is not claimed. This is a
post-restoration observation, not an enabled-live-FPGA before/after comparison.
SPI Flash unchanged; previous receipts and rollback image retained.
