# Shared SOF / CAM6 end-frame experiment

Run from this directory with `python run.py`. Uses ModelSim SE-64 10.6e at
`C:/modeltech64_10.6e/win64`. All generated files, libraries and logs stay here.
No PDS build, source patch, board access or flashing is involved.

The test compiles these production modules directly:

- `source/sfp/sfp_rx_cam_if.v` and `video_async_fifo.v` (actual split and CDC).
- `source/ov5640/ov5640_ddr/ov5640_ddr.v`, `_w.v`, `_w_en.v`, `_w_ctrl.v`
  (actual SOF admission, capture validity, packing, FIFO control and publication).

The only IP replacements are the existing behavioral FIFO contracts from
`sim/dma_timeout_repro/fifo_models.sv`. They model registered 32-to-128 reads
and the FWFT output FIFO with reduced capacity. The test asserts no overflow.
The DMA model accepts the actual camera commands and every stream beat,
then returns a successful completion after a configurable tail. It also
accepts the tag command and tag beat, delaying its completion 16 AXI cycles.
It checks every payload pixel, the tag sequence, `frame_good` at payload
completion, no capture fault, and one publication per admitted frame.

RX runs at 125 MHz; AXI runs at 200 MHz. Each row contains 640 CAM5 pixels
then 640 CAM6 pixels. Both outputs receive exactly the same SOF. Thus CAM5's
last pixel precedes CAM6's by 640 RX cycles = 5.12 us = 1024 AXI cycles.
The full cases send six actual 1280x480 merged frames. A 3920-cycle gap
between rows gives approximately 50 offered frames/s. SOF width and
following setup are 8 and 24 RX cycles. `BLANK` is the idle interval from
the final pixel to the next SOF; the delayed case uses 12500 RX cycles
(100 us). This delays both cameras' SOF, not just CAM6's.

`TAIL` is counted after the final payload AXI beat is accepted; the real
packing pipeline adds its own delay after the last pixel. `DONE` log lines
report both the observed last-pixel and last-beat ages in AXI cycles.
`SOF` log lines report the actual busy state, flush state, capture completion,
and admission/drop counts at the production admission decision.

Read `results.log` for the compact result matrix and each named `.log` for
frame-by-frame evidence. Full cases require identical six-frame counts for
CAM5 and CAM6 with delayed SOF; the short-blank baseline requires CAM5=6,
CAM6=3. Reduced-height cases test fast DMA and the delay limits separately.

Interpretation is conditional: this tests whether the proposed timing can
cause the observed half-rate behavior in the actual receiver wrappers. It
does not measure the hardware's blank interval or DMA latency. The HSST,
wire decoder, sensor, merge/transmit path, DDR arbitration and AXI DMA burst
engine are not simulated. A 100-us blank only suffices if payload retirement,
tag retirement and local flush finish within that interval. The long-tail
negative control intentionally violates that requirement. Hardware source
tag rates of at least 40 fps still require the parent's sensor/merge change
and board verification.

Production admission points: `_w_en.v:44,94` gate on engine idle and
capture stop; `_w_ctrl.v:172` discards busy SOF; `_w_ctrl.v:56,58,237` move
from successful payload completion to tag completion and publication.
`ov5640_ddr.v:121` keeps a four-cycle local flush after tag retirement.
`sfp_rx_cam_if.v:60,61` places the same VS in both CDC FIFOs.

`source_hashes_before.json` and `source_hashes_after.json` audit all compiled
production modules and the reused external stub. They must match.
