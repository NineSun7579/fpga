# V7 bitstream delivery

Objective achieved: compile and independently verify a local PG2L100H-6FBG484 bitstream; no programming performed.

Artifact: `bitstream_01/generate_bitstream/fpga_v8_cooperative_top_v2_rfg01.sbit`

Bytes: 3791112

SHA256: `dfd84258a8db6fa35268d9348b61134efad28eedae0d01925c9a7514c742cf60`

Companion mask: `bitstream_01/generate_bitstream/fpga_v8_cooperative_top_v2_rfg01.smsk`, 3791112 bytes, SHA256 `6a63633f15df2b1f3e0dbbac7464275778b85df46a5575a19e931444bb4c47e4`.

| Requirement | Verified evidence |
| --- | --- |
| TC05 functional correction | Original detector results and 17 artifacts copied in `regression_receipts/tc05_detector/`; source/artifact/protected hashes checked. Five paired geometries, eight stress geometries, three adapter cases and full-resolution four-camera integration passed. |
| Retained behavior | TC04 six candidate hashes and inherited TC03 adapter, motion baseline, transport, DMA, FIFO/reset receipts checked against originals by `verify_delivery.py`. |
| Isolated build and binding | `binding_audit.json`, `exact_binding_verification.json`, `actual_elaboration.json`; frozen inputs, full project registrations/options and intended TC05 parent substitution checked. |
| Build success | `flow_result.json`: compile/synthesize/pnr each exit 0; `baseline_guard.json` and `baseline_before.json` preserve V6 failure evidence. |
| Final routed timing | `evidence/final_sta_summary.json`, original final `.rtr`, `acceptance_audit.json`: ten nonempty groups, zero failing endpoints/negative paths; minimum setup slack +0.266 ns. |
| Structure and physical interfaces | `parent_handoff.json`, raw report, stage tables, HSST audit: structure passed, 112 physical pin rows preserved, HSST sites and dedicated connections equal baseline. |
| Motion resources | `evidence/motion_routed_resource_proof.json`: 32 actual routed history DRM36K cells, 614400 logical bits, read-before-write parameters and connections checked. |
| Generation and integrity | `bitstream_result.json`, generator completion log, `delivery_manifest.json`, `delivery_verification.json`: nonempty declared output, unchanged route, source/project/evidence/artifact hashes verified. |
| Completed pipeline | `finish_pipeline_result.json`: export/generate/verify each exit 0; independent `acceptance_audit.json` passed. |
| No programming | Manifest, generation result, verification and audit all record programming_performed=false. |

Final direct recheck verified all manifest evidence hashes, source inventory, artifact bytes/SHA256 and audit-to-manifest binding after the completion event. No FPGA programming, online viewer replacement or board operation verification occurred.

Limitations: 1674 unscored IO paths remain. Board operation, loaded FPGA identity, coordinated physical reset, exclusive driver ownership, H2F/F2H response and visibility, physical RAW correctness and cooperative inference FPS remain unverified. Runtime reset fault recovery requires FPGA reconfiguration. This delivery establishes local compilation and the stated functional/physical/timing gates, not board certification.
