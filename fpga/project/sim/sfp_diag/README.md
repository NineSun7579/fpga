# Optional SFP diagnostic register test

From this directory run `vsim -c -do run.do` (ModelSim).
Expected: `SFP_DIAG_PASS: 21 paired reads, default/enabled mapping and original writes`.

Two instances share AXI-Lite traffic: one omits SFP_DIAG_EN to test its default,
the other sets it to 1. Distinct 32-bit diagnostic inputs verify aligned reads
at BAR offsets 0x120, 0x130, 0x140, 0x150, 0x160, 0x170, and 0x180.
The test also checks read backpressure, separated AW/W handshakes, LED writes,
button W1C, timestamp capture/clear, threshold byte strobes, injection address
writes, unaffected adjacent registers, and unmapped reads. Failure or timeout
returns a nonzero exit code. Generated simulator files stay in this directory.
