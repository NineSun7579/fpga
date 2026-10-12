# Isolated capture ARM correction

Use `fpga_v8_capture_control_axil_arm_v2.v` in place of the original controller,
and rename the controller instance's module reference. All parameters and ports
remain identical. Leave the original capture manager and camera wrapper bound
to their pinned bytes. No production file is edited here.

Read `REPORT.md`, `ARM_STAGING_SEMANTICS.md`, `control.diff`, and
`bindings_manifest.json` before integrating. `artifacts/review_receipt.json`
contains the final simulation, API, immutability and mapped-loop review evidence.

The generated standalone `component_01` includes actual endpoint, controller,
manager, camera/FIFOs and DMA, with virtual IO and 131.25 MHz common clock.
It supports compile/synthesis only. Do not register this verification wrapper
as the whole-board top. The production integration uses the single controller
replacement above.

Harness clones in `core`, `core_revision`, `core_priority`, `core_final_b`,
`endpoint`, and `lease` keep independent results. `prepare.py` documents exact
byte-level transformations and skips completed clone directories. Regression
commands are saved in each result receipt. Component sources and tool commands
are pinned in `component_01/expected_inputs.json` and `run_results.json`.
