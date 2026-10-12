# Background tap timing boundary

The pre-change `integrated_six_background/project/report_timing/top.rtr`
reports DDR slow-corner setup WNS -0.592 ns at 131.25 MHz. The C6 path
starts at `u_sfp_rx_cam_if/u_fifo6/rbin[3]` and ends at
`delivery_u/background/cameras[5].producer/fifo_1/gopdrm_36k/DB0`.
The analogous C5 path has -0.385 ns slack. The passive asynchronous FIFO
read/capture path previously continued through background packing to DRM.

`background_six.v` registers all six `sof`, `pixel_valid`, `source_bad`,
`pixels`, `raw_publish`, and `source_sequence` inputs together on the AXI
clock. Every producer consumes that tuple one clock later. There is no
ready signal, clock enable, or source feedback: the stage accepts a tuple
each clock, including consecutive valid pixels. Reset clears the complete
tuple. The incoming RAW publication counter at SOF is sampled with SOF,
so the producer still predicts `source_sequence + 1`, including wrap to
zero. A later publication pulse carries its matching sampled counter.

`background_producer.v` captures pixel (0,0) when SOF and valid coincide;
previously admission discarded that pixel because `active` was still low.
The 2x2 minimum supported geometry immediately packs its sole selected
pixel. A constant synthesis-compatible admission guard rejects odd or
nonpositive width/height; supported dimensions are positive even values.

Only these two candidate RTL modules and their canonical copies change.
The generator continues to copy the canonical modules without moving the
tap or changing wrappers. Its project transformation is factored into a
read-only helper so verification can compare the entire PDS configuration
input prefix after a build updates command outputs. This check normalizes
only line endings, timestamps, and generated comments. All other existing
baseline/candidate source receipt hashes and RAW preservation checks remain
required. Neither project files nor constraints are rewritten by this fix.

Run `python verify_six_background.py`, then
`python verify_six_background_extra.py` using the installed ModelSim 10.6e.
The first suite includes all existing tests plus same-cycle SOF/pixel at
32x16, 10x6 and 2x2, and odd/zero geometry rejection. The second suite
compares every sampled producer input tuple against the preceding real
RAW tap tuple through successful/failed RAW publication, delayed tag B,
full-resolution frames and sequence wrap. Publication tags and all selected
pixels remain checked against the real RAW counter and CPU reference.

`background_timing_fix_receipt.json` records source hashes and pass logs.
Timing closure remains for the parent-owned PDS rebuild; the old report is
evidence for placement of the boundary, not post-change timing evidence.
No PDS, board operation, or commit is part of this task.
