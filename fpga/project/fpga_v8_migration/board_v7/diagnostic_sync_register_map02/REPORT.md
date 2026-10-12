# Independent diagnostic register mapping experiment

Result: FAIL. Actual compile/synthesis/device-map graphs were exported and re-read. This experiment stops at device map; routed timing acceptance is not claimed.

| Stage | Independent sync / 28 | Independent reset / 32 | Endpoint result | ADF SHA256 | Native DB SHA256 |
|---|---:|---:|---|---|---|
| compile | 28 | 32 | PASS | 0a0be4b0f0a375693c0779e071770a1b128b78dbd35d340082d87ab90109cccb | ebebeac59be997fdeea7d237a4fc1bd9b9958ff8d981833c17e4a5989ea7655c |
| synthesis | 28 | 32 | PASS | bb26cb3141880fe37053bc0aa688186415d491840b1bfcca8e39cc20f3e2b60a | 3b829e1d1e612e80edbc4ca56431a2af5f685e72fad3029805f8911e66b38825 |
| mapping | 4 | 0 | FAIL | 863916ca699d2142e45dc315227d66657cb9f11a57718ce950b087feaa00cf3a | d2a076cd3d17401f415688eb45c37856462a1759fc8bcc4eed396fbc49272373 |

A compact 32-bit stimulus wrapper drives four original 32-bit inputs through a 128-bit host-clock register; this is an isolated structural experiment. The real four-camera v7_sdt_bus and exact primitive candidate source bytes are retained. All 17 output groups connect to top outputs. Five roots: host 7.619 ns; cameras 11.905/11.905/20.833/20.833 ns. No timing exceptions or multicycle constraints. Required integer devmap_remove_dups=0, devmap_const_prop=0, devmap_control_set_num=0 are checked against the actual executed command. Options proven: True. Actual DB/constraint-context launch/result logs are retained.

Detailed physical cell types, parameter maps, real D/CLK/reset pin names, driver cones, logical Q aliases and per-stage predecessors are in evidence/*_topology.json and *_endpoint_details.json. Shared reset nets are allowed; shared storage cells are not. Compile/synthesis and mapped structure results are separate from official tool completion.

Protected production/old-IP guard: 1022 files checked; active integrated run stable inputs: 741 files unchanged. No remote, programming, old IP changes, PNR, or bitstream generation. Input hashes are in evidence/input_hashes.json; copies preserve source GBK bytes.

Mapped physical independence FAIL. Explicit primitives did not establish all 60 independent storage/endpoints. Exact failed bindings:

- source_diagnostics/cameras[0].source/ack_sync[0]: source_diagnostics/cameras[0].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/ack_sync[1]: source_diagnostics/cameras[0].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/req_sync[0]: source_diagnostics/cameras[0].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/req_sync[1]: source_diagnostics/cameras[0].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/overrun_sync[0]: source_diagnostics/cameras[0].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/overrun_sync[1]: source_diagnostics/cameras[0].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[0].source/cr[0]: ; output drivers []
- source_diagnostics/cameras[0].source/cr[1]: source_diagnostics/cameras[0].source/cr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[0].source/hr[0]: ; output drivers []
- source_diagnostics/cameras[0].source/hr[1]: source_diagnostics/cameras[0].source/hr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[0].reset_pipe[0]: ; output drivers []
- source_diagnostics/cameras[0].reset_pipe[1]: source_diagnostics/cameras[0].reset_pipe_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[0].reset_pipe[2]: source_diagnostics/cameras[0].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[0].reset_pipe[3]: source_diagnostics/cameras[0].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[1].source/ack_sync[0]: source_diagnostics/cameras[1].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/ack_sync[1]: source_diagnostics/cameras[1].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/req_sync[0]: source_diagnostics/cameras[1].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/req_sync[1]: source_diagnostics/cameras[1].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/overrun_sync[0]: source_diagnostics/cameras[1].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/overrun_sync[1]: source_diagnostics/cameras[1].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[1].source/cr[0]: ; output drivers []
- source_diagnostics/cameras[1].source/cr[1]: source_diagnostics/cameras[1].source/cr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[1].source/hr[0]: ; output drivers []
- source_diagnostics/cameras[1].source/hr[1]: source_diagnostics/cameras[1].source/hr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[1].reset_pipe[0]: ; output drivers []
- source_diagnostics/cameras[1].reset_pipe[1]: source_diagnostics/cameras[1].reset_pipe_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[1].reset_pipe[2]: source_diagnostics/cameras[1].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[1].reset_pipe[3]: source_diagnostics/cameras[1].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[2].source/ack_sync[0]: source_diagnostics/cameras[2].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/ack_sync[1]: source_diagnostics/cameras[2].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/req_sync[0]: source_diagnostics/cameras[2].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/req_sync[1]: source_diagnostics/cameras[2].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/overrun_sync[0]: source_diagnostics/cameras[2].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/overrun_sync[1]: source_diagnostics/cameras[2].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[2].source/cr[0]: ; output drivers []
- source_diagnostics/cameras[2].source/cr[1]: source_diagnostics/cameras[2].source/cr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[2].source/hr[0]: ; output drivers []
- source_diagnostics/cameras[2].source/hr[1]: source_diagnostics/cameras[2].source/hr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[2].reset_pipe[0]: ; output drivers []
- source_diagnostics/cameras[2].reset_pipe[1]: source_diagnostics/cameras[2].reset_pipe_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[2].reset_pipe[2]: source_diagnostics/cameras[2].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[2].reset_pipe[3]: source_diagnostics/cameras[2].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[3].source/ack_sync[0]: source_diagnostics/cameras[3].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/ack_sync[1]: source_diagnostics/cameras[3].source/ack_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/req_sync[0]: source_diagnostics/cameras[3].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/req_sync[1]: source_diagnostics/cameras[3].source/req_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/overrun_sync[0]: source_diagnostics/cameras[3].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/overrun_sync[1]: source_diagnostics/cameras[3].source/overrun_sync_ff0/opit_0_srl (gopSRL2_Cell_2); output drivers []
- source_diagnostics/cameras[3].source/cr[0]: ; output drivers []
- source_diagnostics/cameras[3].source/cr[1]: source_diagnostics/cameras[3].source/cr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[3].source/hr[0]: ; output drivers []
- source_diagnostics/cameras[3].source/hr[1]: source_diagnostics/cameras[3].source/hr_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[3].reset_pipe[0]: ; output drivers []
- source_diagnostics/cameras[3].reset_pipe[1]: source_diagnostics/cameras[3].reset_pipe_ff1/opit_0_L6QQ (gopLUT6QQ); output drivers []
- source_diagnostics/cameras[3].reset_pipe[2]: source_diagnostics/cameras[3].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []
- source_diagnostics/cameras[3].reset_pipe[3]: source_diagnostics/cameras[3].reset_pipe_ff2/opit_0_srl (gopSRL2_Cell_1); output drivers []

Next step: use these new ADF/graph/parameter records for vendor-supported packing control guidance. Do not guess packingdisable or integrate this candidate as a physical fix. A controlled topology change that inhibits packing must preserve mailbox/ACK/request cycles and asynchronous reset behavior, pass the same real-model regression, and then repeat isolated mapping. The documented attribute candidate may be a controlled comparison, but syn_srlstyle is not proof against SRL2 physical packing.

This map02 already tests syn_noprune=1 on all 60 instances. Inspect actual propagation and packing witnesses. UCE PDF page 94 states FF packing ignores PAP_DONT_TOUCH; installed official docs provide no demonstrated anti-FF-pack fix.

Real-model baseline/candidate regression was completed in ../diagnostic_sync_register_timing_candidate/evidence/primitive_results.json. This mapping experiment does not repeat or broaden that regression. Detailed endpoint check failures: {'compile': 0, 'synthesis': 0, 'mapping': 60}.
