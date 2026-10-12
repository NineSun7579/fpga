# Bitstream acceptance checklist

Objective: compile a usable local bitstream for PG2L100H-6FBG484 without programming hardware.

This checklist defines required evidence; it does not assert completion.
Paths below are relative to `../whole_candidate_v4_route_01/` unless stated otherwise.

| Requirement | Artifact and acceptance condition |
| --- | --- |
| Whole build completed | `flow_result.json`: compile, synthesize and pnr stages each exit 0; stage logs retained. |
| Tested RTL actually used | `actual_elaboration.json` and `compile/run.log`: corrected FIFO, DMA, guard, motion and decoder modules elaborated; replaced originals excluded. |
| Sources and constraints preserved | `binding_audit.json`, `inputs_before.json`, `inputs_after.json`, `baseline_guard.json`: intended instance replacements only; frozen files and constraints unchanged. |
| No structural timing defects | `structural_gate.json` and `parent_handoff.json`: loops, latchs, latch_loops, no_clock and unexpandable_clocks each 0. |
| Final routed timing | `evidence/final_sta_summary.json` and referenced `.rtr`: ten nonempty slow/fast setup, hold, recovery, removal and minimum pulse width groups; zero failing endpoints; zero negative paths; detailed path count reconciles with summaries. |
| Physical interfaces preserved | `evidence/stage_tables.json`: PCB pin rows match V3 baseline; `evidence/hsst_actual_phy_audit.json`: sites and dedicated connections identical to historical baseline. |
| Motion retained | `evidence/motion_routed_resource_proof.json`: 32 placed history DRM36K cells, 614400 logical bits; cell parameters, connections and routed dump hashes retained. |
| PCIe transport regression | `regression_receipts/transport.json`: 50 cases, 46 normal outcomes and four expected fault outcomes with no completion MSI or final B credit; `fifo_binding.json` candidate hash matches built RTL. |
| DDR DMA regression | `regression_receipts/dma.json`: 160 differential scenarios across WAIT_FOR_DATA=0/1; public outputs and beat counts match; tested candidate hash matches built RTL. |
| Reset and FIFO integration | `regression_receipts/reset_guard.json`: nine guard cases; `guarded_fifo.json`: five integration cases and unchanged tested source hashes. |
| Bitstream generated successfully | `bitstream_result.json` and `bitstream_01/bitgen.log`: exit 0, generation completion messages, nonempty `.sbit`/`.bit` files matching declared paths, unchanged routed ADF. |
| Delivery integrity | `delivery_manifest.json` and `delivery_verification.json`: bitstream size and SHA256, source/evidence/route hashes independently verified; `BITSTREAM_DELIVERY.md` records delivery details. |
| Independent acceptance audit | Run `python audit_acceptance.py` after delivery verification; `acceptance_audit.json` requires raw report row checks, actual pin rows compared with baseline, preserved constraints, and copied regression receipts bound to built RTL hashes. |
| No programming | Runner scripts contain build/export/generation/file verification operations only; receipts explicitly record programming_performed=false. No hardware programming step is part of this pipeline. |
| Honest limitations | Delivery retains unscored IO count and states physical board operation has not been verified. Scored closure must not be presented as board IO signoff. |

Execution order: `run_whole.py` completed compile, synthesis and route; attached `finish_when_ready.py` runs `export_whole.py`, `generate_bitstream.py` and `verify_delivery.py` sequentially. The attached `audit_when_ready.py` waits on that pipeline's process completion event, requires all three steps to succeed, then runs `audit_acceptance.py`. A failed step stops its sequence and leaves evidence for correction. No failed attempt is overwritten. Attachment alone does not establish acceptance; `acceptance_audit.json` must report `passed=true`.
