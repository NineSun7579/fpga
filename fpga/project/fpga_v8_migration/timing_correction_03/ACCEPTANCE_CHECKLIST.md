# V5 bitstream acceptance

Objective: generate and verify a local PG2L100H-6FBG484 bitstream, without programming hardware. A running process or a prepared script does not establish acceptance.

All whole-design evidence below belongs to `../whole_candidate_v5_route_01/`.

| Requirement | Evidence required |
| --- | --- |
| Functional corrections | `camera_artifacts/results.json`: 12 runs, eight outputs; `adapter_artifacts/adapter_results.json`: parameter boundaries and 29 outputs; `motion_acceptance.json`: reviewed five-geometry paired and four-stream integration receipts, matching candidate hashes. |
| Inherited regressions | Copied transport, FIFO binding, DMA, guarded FIFO and reset guard receipts in `regression_receipts/`; 50 transport cases including four expected faults, 160 DMA cases, five integration cases and nine guard cases. |
| Actual source binding | `actual_elaboration.json` and `compile/run.log`: TC03 camera, motion and adapter and inherited TC02 DMA/FIFO and guard elaborated; replaced originals excluded. |
| Preserved inputs | `binding_audit.json`, `inputs_before.json`, `inputs_after.json`, `baseline_guard.json`: 694 frozen input files and constraints unchanged; parent copies replace module names only. |
| Build | `flow_result.json`: compile, synthesis and pnr each exit zero; retained stage logs. |
| Structure | `structural_gate.json` and `parent_handoff.json`: loops, latches, latch loops, no_clock and unexpandable clocks all zero. |
| Routed timing | Raw `.rtr` plus `evidence/final_sta_summary.json`: ten nonempty slow/fast setup, hold, recovery, removal and minimum pulse groups, zero failures and negative paths, summary/path counts reconciled. |
| Physical interfaces | Exported pin rows equal actual V4 pin rows; HSST sites and dedicated connections match historical baseline. |
| Motion resources | 32 routed history DRM36K cells and 614400 logical bits with retained parameters, connections and dump hashes. |
| Generated files | `bitstream_result.json`, `bitstream_01/bitgen.log`: successful generation messages and exit zero, nonempty declared files, unchanged routed ADF. |
| Integrity | `delivery_manifest.json`, `delivery_verification.json`, `acceptance_audit.json`: source, route, evidence and file hashes checked; raw report reparsed and actual pin rows compared. |
| Delivery | `BITSTREAM_DELIVERY.md`: concrete files, bytes, SHA256, unscored IO count and unverified physical board operation. |
| No programming | Build/export/generation/verification operations only; programming_performed=false in receipts. |

The attached `finish_when_ready.py` waits on the existing V5 build process event and executes export, generation and verification sequentially. Verification also executes the independent acceptance audit. Any failed gate stops the sequence and preserves the attempt. Final completion requires review of all actual evidence above.
