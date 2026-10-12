# Independent diagnostic register mapping experiment

Result: FAIL. Actual compile/synthesis/device-map graphs were exported and re-read. This experiment stops at device map; routed timing acceptance is not claimed.

| Stage | Independent sync / 28 | Independent reset / 32 | Endpoint result | ADF SHA256 | Native DB SHA256 |
|---|---:|---:|---|---|---|
| compile | 28 | 32 | PASS | a3c1f496e6b7243881379715cb5ce1d3a87641ae9a7fd0f8a1e5a47c9b140517 | c9007a5ae9cc778e8fe876578e917c0f412b54787188f4eb73a9b6ac3feaf221 |
| synthesis | 28 | 32 | PASS | 6c10853577a6628a2ae337239daadbd972b8bc73016e852e15c69ac22951eb0c | 4491f286d494499f98a6d5bc574b067562448d9979f51b1fb93238c926afd945 |
| mapping | 4 | 0 | FAIL | b0d70c0f02c47210e47e715ade4ffc0aa43fff2cc8a2def58e9f710bb71c4e1a | 951c457da946205c32ce54e1890475021a49121da02d20a0b9e6e97a1feab427 |

A compact 32-bit stimulus wrapper drives four original 32-bit inputs through a 128-bit host-clock register; this is an isolated structural experiment. The real four-camera v7_sdt_bus and exact primitive candidate source bytes are retained. All 17 output groups connect to top outputs. Five roots: host 7.619 ns; cameras 11.905/11.905/20.833/20.833 ns. No timing exceptions or multicycle constraints. Required integer devmap_remove_dups=0, devmap_const_prop=0, devmap_control_set_num=0 are checked against the actual executed command. Options proven: False. Actual DB/constraint-context launch/result logs are retained.

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

Apply syn_noprune=1 to only the 60 connected explicit GTP_DFF_CE/PE instances in a separate scoped comparison. ADS Synthesis User Guide PDF pages 90-91 supports instance scope. Preserve original evidence; recompile/synthesize/map and verify propagation plus all 60 unique storage endpoints. This is a candidate, not a proven anti-packing fix. syn_preserve is documented for module/port/register, not primitive-instance scope; syn_srlstyle concerns inferred shifts.

Real-model baseline/candidate regression was completed in ../diagnostic_sync_register_timing_candidate/evidence/primitive_results.json. This mapping experiment does not repeat or broaden that regression. Detailed endpoint check failures: {'compile': 0, 'synthesis': 24, 'mapping': 60}.
