# Final independent review

Overall result: FAIL for the requested 60 independent mapped storage cells/endpoints. Actual compile, synthesis, device map and all three graph exports completed. Three supported integer options were explicitly executed as 0 in the final device-map command. No routed signoff is claimed.

| Stage | ADF SHA256 | Native DB SHA256 | Independent endpoints |
|---|---|---|---|
| compile/v7_sdt_top_comp.adf + compile/cmr.db | 67ec0288a20cbe0f64b3710730eb7ad2b0ee29f083d177fe4273cae5c203ba9d | 162e6a8eafbbe25010d841c992cf752d05454660d27350a1e5f738f25ccc8972 | 28 sync + 32 reset, structure PASS |
| synthesize/v7_sdt_top_syn.adf + synthesize/snr.db | 8e34dd51dd98fd199f44dc80cff75ef21a7ecaa56c2eaa908b2402ca3fe3f028 | 98dd1ce31df85e3a0b6e78eb711adbe276bba5487c648d2dc8676128452e3097 | 28 sync + 32 reset, structure PASS |
| device_map/v7_sdt_top_map.adf + device_map/dmr.db | d3193901f35f90633e255efb5e87d29ff381ed3c73f7401d9bbb5753da065067 | 730cc0591c256ec935b0431c0214ab321c54c0001e3ef93a4c76ef8dc6c4b066 | only 4 independent sync endpoint bindings confirmed, FAIL |

All six current DB hashes were independently rechecked against bytes after completion. Final result records also verify each graph/export against its exact stage DB. Earlier project-mode continuations regenerated upstream DB serialization; old receipts/graphs are preserved under attempts and must not be treated as current results.

Concrete mapped structure examples for camera 0 (same pattern is recorded for cameras 1-3):

- source_diagnostics/cameras[0].source/req_sync_ff0/opit_0_srl: gopSRL2_Cell_2, shared D/CLK/RS, FF0_RS=RESET, FFAPP0_RS=RESET, FF0_INIT=0, FFAPP0_INIT=0, RS_MODE=ASYNC. The two internal stages do not supply two independent external D/reset endpoints.
- source_diagnostics/cameras[0].source/req_sync_ff2/opit_0: gopQ_Cell_4, real D/CLK/RS/Q, FF_RS=RESET, FF_INIT=0, RS_MODE=ASYNC.
- source_diagnostics/cameras[0].source/cr_ff1/opit_0_L6QQ and cameras[0].reset_pipe_ff1/opit_0_L6QQ: gopLUT6QQ, LUT inputs I0-I5, common CLK/RS, L6Q/L6QQ outputs, FF_RS=SET, FFAPP_RS=SET, FF_INIT=1, FFAPP_INIT=1, FFAPPMUX_SEL=SRQ. These are packed storage structures rather than separately bound original D pins.
- cameras[0].reset_pipe_ff2/opit_0_srl: gopSRL2_Cell_1.

Mapped endpoint count is a count of proved independent bindings, not a claim that only four FF bits exist. Unresolved logical stages and packed internal stages remain explicit failures. The synthesis detail audit retains 24 unresolved first-input/constant provenance checks although all 60 synthesis cells/endpoints are structurally distinct; no semantic connectivity PASS is claimed for these unresolved checks. Full rows, actual parameters and net evidence are retained in evidence/*_topology.json and *_endpoint_details.json.

Final map invocation is recorded verbatim in evidence/final_result.json and mapping.log: dev_map -force_to_run -input_db_file <this experiment's actual syn.adf> -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0. Its script sets the exact architecture and imports the five-root clock constraint context with add_constraint. It does not rely on unsupported open_project or on silently dropped project options.

The final wrapper keeps all 17 bus output groups exposed. A 32-bit input feeds a 128-bit host-clock stimulus register to supply the original four 32-bit bus inputs while staying within package IO capacity (226 IO reported). The candidate bus and source RTL bytes remain unchanged; stimulus is an experiment harness, not production integration. Five clock rates are unchanged and no false paths, clock groups or multicycle exceptions were added.

Protection: 1022 production/old-IP files checked and 741 active integrated-run stable inputs unchanged. No remote access, programming, PNR, or old-IP edits. Generated review text is ASCII and thus valid GBK; original source bytes remain intact.

Next step: retain the final mapped ADF, graph and parameter evidence for vendor-supported anti-packing guidance. A minimal documented isolated comparison can apply syn_noprune=1 only to the 60 connected primitive instances (ADS guide PDF pages 90-91 supports instance scope). This is only a synthesis-preservation candidate, not a proven physical anti-packing control; repeat real-model regression and device mapping before relying on it. Do not guess packingdisable. Do not integrate map01 as a physical fix. Any later full isolated integration with changed mapping names must derive U-B and mailbox/complement constraints again from its actual graphs and prove routed setup/hold/recovery/removal and existing budgets.

Primary evidence: REPORT.md, evidence/final_result.json, independent_audit_result.json, mapping_artifact.json, mapping_topology.json, packing_failure.json, mapping_recovery_receipt.json, and preserved attempts.
