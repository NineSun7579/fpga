# Four-camera motion regression

This suite simulates four independent default 640x480 motion adapters and the
six-slot register bank, using the actual `motion_100h/source/motion` RTL. It
does not simulate the full FPGA top: vendor IP models are unavailable.

Run from this directory using ModelSim:

```powershell
& C:\modeltech64_10.6e\win64\vsim.exe -c -do run_four.do
python check_four_integration.py
$env:FOUR_MOTION_FAULT='1'
& C:\modeltech64_10.6e\win64\vsim.exe -c -do run_four.do
Remove-Item Env:FOUR_MOTION_FAULT
```

The main run must exit zero and print `PASS tb_four_motion`. The fault run flips
an expected frozen snapshot bit and must exit nonzero at the snapshot checker.
Run the two simulations sequentially; they use the same private four-camera
library. The distinct `four_motion_work`, `four_motion_modelsim.ini`, waveform,
and transcripts do not modify the six-camera suite or shared ModelSim mapping.

Ten frame phases cover reference seeding, static images, four different localized
motion blocks with eight changed samples, full-frame changes, and isolated
short-frame suppression/reseeding/recovery on camera index 2. Every publication
is checked against a packet oracle independent of detector work state. Additional
checks cover core end+2 publication, adapter end+3 atomic capture, publication
counts, no FIFO overflow, frozen ten-word captures spanning later updates for
all four active indices, and zero register captures for reserved indices 4/5.

`check_four_integration.py` reads the actual top and camera wrapper as bytes. It
requires four local camera instances with one motion adapter each, positive
CAM1-4 record connections, ABI record ordering, zero CAM5/6 records, and retained
CAM5/6 video DDR/DMA wiring. These are static integration checks, not full-top
simulation or FPGA resource/timing evidence.

Artifacts: `four_motion_results.log`, `four_motion_launch.log`,
`four_motion_fault.log`, `four_motion_fault_launch.log`, and
`four_motion_integration.log`.
