PASS - ModelSim SE-64 10.6e, 2026-10-03 01:00:11 through 01:01:25.

Mode 0, both actual top reg_config instance blocks, rounds 1 and 2:
357 START, 357 STOP, 357 completions, 1428 ACK bits per sensor per round.
All 32-bit serial payloads matched the independent production command table.

Mode 1, both actual top reg_config instance blocks, rounds 1 and 2:
358 START, 358 STOP, 358 completions, 1432 ACK bits per sensor per round.
The first 357 payloads matched production; final payload was 0x78503D80.

Enable gating, terminal done/index, no transactions after done, and camera
reset while configuration clock was stopped passed in both modes.
run.ps1 verified all four production file SHA256 values unchanged afterward.
Separate byte audit verified every original non-ASCII byte was preserved
in both patched RTL files. No PDS, bitgen, JTAG or hardware action was taken.

Logs: mode_0.log, mode_1.log. Compile errors: zero. Existing power_on_delay
duplicate initial_en declaration warning remained; ModelSim also warned about
the existing no-optimization simulation preference. Neither caused a failure.

Scope: initialization/SCCB regression only. Physical sensor ACKs, generated
bar palette, complete FPGA top synthesis, and RK3568 X11 screenshots remain
for the parent's authorized build and hardware validation workflow.
