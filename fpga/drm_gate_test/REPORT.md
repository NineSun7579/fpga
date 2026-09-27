# DRM read gate verification

Only production change: `source/ov5640/ov5640_ddr/ov5640_ddr_w.v:230`

```verilog
wire rd_en_drm = !(empty_drm | almost_full_out);
```

The original file was backed up before modification as `ov5640_ddr_w.v.bak_drm_gate` in the same directory. `fix_drm_gate_bytes.py` performs the single byte replacement and checks backup equality. Final audit confirmed exactly 18 bytes removed, with all other bytes, encoding and line endings preserved.

- Before SHA256: `36b22e89dd1dc96f7fd5c250857603f800b8a2af475b6ba913ec5a0ac6e03852`
- After SHA256: `edf70b410aad864b5fe085b3815e744abca2aa43d7081b2f01fd946bcdfe0e98`

Run from project directory: `python drm_gate_test/run_test.py`

ModelSim SE-64 10.6e compiles the actual old backup and fixed module into separate local libraries, with both actual generated FIFO IPs and the installed vendor `GTP_DRM36K_E1` and `GTP_GRS` simulation models. No PDS executable is invoked; its installed Verilog model files are only read by ModelSim.

Results:

- Old: after injecting 1023 32-bit write words under backpressure, actual DRM almost-full asserted. After removing downstream backpressure, no DRM read occurred for 64 cycles: original deadlock reproduced.
- Fixed: same 1023-word threshold reached. Releasing forced downstream backpressure permitted reads despite self almost-full. With AXI ready still low, the actual output FIFO filled and its own almost-full stopped further reads (16 reads including the pending pipeline word). No output FIFO overflow.
- Enabling AXI ready produced 255 ordered 128-bit beats. The remaining three 32-bit words cannot form a complete read beat. Adding word 1024 produced beat 256 and emptied both FIFOs. All 1024 words were checked for value and order.
- Assertions check downstream almost-full always inhibits new DRM reads, empty inhibits reads, and no pending output write encounters full. 1090 sampled backpressure cycles include both the forced fill phase and the actual downstream stall.
- Both compile logs: zero errors/warnings. Simulation logs: zero errors; four warnings from inherited no-optimization configuration and generated output IP's unused water-level ports. Two additional Tcl notices concern onerror/onbreak outside a macro; pass markers and error scanning also determine runner success.

Evidence: `old_sim.log`, `fixed_sim.log`, `old_compile.log`, `fixed_compile.log`; testbench: `tb_drm_gate.sv`.

Scope: functional FIFO-chain verification within the actual `ov5640_ddr_w` module. Testbench forces `wr_en`/`din` to inject known words after the pixel packer, and temporarily forces downstream almost-full during initial filling. It then releases this force to exercise actual downstream FIFO backpressure. Pixel packing, full camera frames, DDR controller, PCIe, third-output host display, timing closure and hardware behavior are not verified. No other production RTL, top, constraints, decoder or IP files were modified. No board access, PDS run, or cam1 color-artifact work was performed. This result does not claim third-output hardware success.
