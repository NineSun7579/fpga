# Shorter selected-camera hold candidate

Local-only candidate derived from `candidate_fair_viewer`, excluding builds and
Python caches. No board access, deployment, driver edits or RTL edits.

## Production change

`PangoDev::cameraReadFpga` moves only the host RAW-slot CPU copy from before
converter start to after conversion completion, same-frame validation, verified
camera release and selector-default restoration. RAW F2H and its commit-tag
check remain inside the FPGA hold. Converter polling and its transport yields
remain unchanged. The copy still precedes construction/publication of Input and
the optional same-frame golden RGB. Sole admission stays occupied through the
copy, queues, deferred RGB DMA and consumer completion/cancellation.

The worker is the only caller for its camera slot and cannot start its next
capture until this call returns. Slots have stride `0x97000`, each RAW transfer
uses 614416 bytes; six slots finish before scratch `0x3ff000`. Deferred RGB uses
offset `0x400000`. `camera_dma.h` statically checks these boundaries. Register
traffic and the other five camera workers cannot overwrite the selected slot.
The FPGA camera bank may resume writes after release; it cannot alter the
already completed host RAW DMA. Display/analytics receive the same copied RAW
bytes, and native RGB inference retains the same source/tag/epoch.

## Source and log evidence

`fair_performance_cpu.json`: PID 13211, 30.0131 seconds, 204.8771% CPU.
`fair_performance_runtime.summary.json`: delivered camera rates
34.7614 / 44.5914 / 25.7686 / 25.7643 / 40.2171 / 40.3614; completed inference
3.2857 fps. These are seven logged windows, not a synchronized 30-second
camera/inference measurement. Original summary has eleven windows and reports
cam1 44.1336 and inference 3.9091 fps. Comparisons need matched future trials.

The seven cam1 `[capture]` windows report RAW-copy averages
7.208 / 6.844 / 6.929 / 7.092 / 7.031 / 7.069 / 7.088 ms. These mix ordinary and
selected captures; selected-copy duration and converter duration are not
separately measured. Moving the selected copy removes that operation from the
hold's critical path, but an exact millisecond saving or FPS improvement is not
proven. The logged `lease_hold_ms` (summary mean 44.76 ms, last 100 samples)
starts after deferred RGB F2H/PZ_BEGIN; it does not measure the FPGA camera hold
or conversion. A ~60 ms converter duration cannot be established from this log.

Copied `hardware_baseline/integrated_six_batch/source/delivery/delivery_rgb_ddr.v`
consumes one RGB565 pixel per ready cycle from buffered 16-beat bursts
(lines 149-161); output backpressure and DDR arbitration can extend runtime.
Successful done waits for the final AXI write response (183-186).
`delivery_regs.v` rejects hold release while core/command is busy or quarantined
(101), exposes completed/busy/frozen/held status (148), and counts completed jobs
(94-95). The viewer still waits for status `0x0b` plus the next job count and
validates the frozen source/tag/epoch before its existing release sequence.
There is no release while conversion is in progress.

## Request and pending limits

`vision_pipeline.cpp::request` checks stale input, effective interval, config and
pending BEFORE arming admission (539-563). The default tracking cadence is
250 ms; urgent requests use the minimum interval, and lane/tracking-disabled
paths intentionally bypass this cadence check. The log's interval rejects are
231-242 per five-second window. Pending rejects are 28 in the first window and
zero in the next six. These are request-loop counter increments, not counts of
converted inputs thrown away. Admission arm does nothing while occupied, claim
consumes one arm, and Input completion/cancellation retires it. One pending
analytics request and one admitted converter input already bound this path.
No request/cadence/pending policy was changed; source/model switches can still
cancel an admitted but unconsumed input as designed.

## Local validation and limits

Run in Linux with Qt5 development packages:

```
bash local_fair_check.sh
python3 local_short_hold_negative_check.py
```

The extracted actual PangoDev protocol fixture covers six cameras, both native
geometries, exact RAW/golden-RGB input bytes, deferred DMA/BEGIN/END, cancellation,
unpublished admission timeout, preflight allocation failures, disjoint traffic
during a consumer lease, and FPGA polling that yields to another caller.
The added copy-boundary probe requires successful conversion/release/default
restoration and intact sole admission, executes actual metadata and another
camera DMA while copying, and checks every selected RAW byte remains intact.
The negative fixture compiles the original fair PangoDev against the same
probe and must fail at its pre-release copy boundary. Native-output helper
fixtures and class syntax checking also pass. These fixtures model register
and DMA behavior; they do not prove real DDR timing, hardware ownership or
native RKNN results.

Before adoption, the parent must run fresh exact same-frame input and native
output parity (at least the prior 30 pairs), then matched performance trials
with verification disabled, measuring CPU, all six delivered camera rates,
completed inference, errors/unstable tags and display rates. Capture hold phase
timing if the remaining selected-camera loss needs attribution. No performance
claim or approval to persist a board owner follows from the local checks.
