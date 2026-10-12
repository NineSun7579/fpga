# Existing endpoint/controller netlist functional simulation

PASS: the existing connected mapped top matches the unchanged RTL wrapper and the independent cooperative-endpoint ownership oracle for all 654 planned operations. Each run completed 3,913 public events in 13,430 clock cycles (134,300 ns). All three comparisons have 2,208 passing operation/channel groups and zero failing groups or operations. This is local functional evidence for the frozen synthesis output, with no board or timing acceptance.

Results and exact transaction counts are in [REPORT.md](REPORT.md), [results.json](results.json), and [evidence_audit.json](evidence_audit.json). Exact executable argument arrays and working directories are in [commands.json](commands.json). Official model identities, hashes, and mapped primitive counts are in [official_models.json](official_models.json).

The only authored files are this README, REPORT.md, run_simulation.py, audit_evidence.py, and tb_endpoint_wrapper.sv, all inside this new directory. The runner creates fixtures, comparison JSON, logs, traces, and ModelSim libraries only here. It refuses to overwrite completed results or either simulation directory. Existing regression `main()` is never executed; its Suite/Oracle classes are imported with bytecode generation disabled.

Commands executed from `C:\Users\NineSun\Desktop\ov56401`:

```powershell
& 'C:\Users\NineSun\anaconda3\python.exe' -B 'project\fpga_v8_migration\component_synthesis\endpoint_netlist_sim_01\run_simulation.py'
& 'C:\Users\NineSun\anaconda3\python.exe' -B 'project\fpga_v8_migration\component_synthesis\endpoint_netlist_sim_01\audit_evidence.py'
```

The audit reads saved evidence and rechecks source, protected-file, official-model, trace, and command identities without another simulation or synthesis invocation. The simulation runner is intentionally single-use in this completed evidence directory.

Both runs instantiate only `fpga_v8_endpoint_ctrl_synth dut` from the public-port testbench. The RTL run compiles the existing controller, endpoint, and wrapper; the mapped run compiles official Pango cell files and the existing `.vm` only. Internal hierarchy is never accessed, driven, forced, replaced, or patched. Public AXI response, command, and source-release stability checks run during backpressure; public outputs are checked for X/Z values.
