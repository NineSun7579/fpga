# V6 local bitstream acceptance

Objective: compile a usable local PG2L100H-6FBG484 bitstream, verify the actual files and retained evidence, and perform no hardware programming. Prepared scripts and regression PASS alone do not establish completion.

Whole-design artifacts belong to `../whole_candidate_v6_route_01/`.

| Requirement | Direct acceptance evidence |
| --- | --- |
| Six TC04 corrections tested | `regression_acceptance.json`: camera predictor, lease, motion stream, cam5 wrapper, actual ov5640_ddr and DMA watchdog receipts/logs, all candidate and dependency hashes verified. |
| Inherited RAW/transport behavior retained | Unchanged inherited RTL and frozen inputs, tested FIFO/reset guard and TC03 detector/DDR adapter receipts; transport includes four expected fault/no-MSI cases. |
| Intended parent bindings only | `binding_audit.json` and `exact_binding_verification.json`: exact byte substitutions; all seven original ov5640_ddr instances redirected; frozen 694 inputs and constraints unchanged. The independent audit reconstructs expected source/constraint registrations, formats, part and build options from V5; generated stage outputs and timestamps are excluded from registration comparison. |
| Actual elaboration | `actual_elaboration.json` and compile log: six TC04 candidates and inherited corrected modules present, replaced originals absent. |
| Successful whole build | compile, synthesize and pnr exit zero in `flow_result.json`; all stage logs retained. |
| Structure | loops, latchs, latch_loops, no_clock and unexpandable_clocks all zero in synthesis and final routed checks. |
| Final timing | Original final routed `.rtr`, ten nonempty slow/fast groups, zero failing endpoints and negative paths, complete path/summary reconciliation. Stage summaries alone are insufficient. |
| Physical interfaces | Actual pin rows equal V5 baseline, HSST sites and dedicated connections equal historical baseline. |
| Motion retained | 32 routed history DRM36K cells and 614400 logical bits, actual parameters/connections and dump hashes. |
| Bitstream generation | Successful local generator return and completion messages, nonempty declared .sbit/.bit files, unchanged routed ADF. |
| Delivery integrity | Manifest and independent verifier bind source, final `project.pds`, route, regression, STA, physical and bitstream hashes; verify raw report rows and require the complete core evidence set. Every new copied regression receipt is compared byte-for-byte with its accepted original. |
| Concrete delivery | File paths, bytes, SHA256 and limitations in delivery document; final audit checks actual receipts rather than prepared gates. |
| No programming | Build/export/generation/verification only; programming_performed=false. Unscored IO and unverified board operation remain explicitly stated. |

The attached completion-event runner executes export, generation and verification sequentially after the existing V6 build exits successfully. A failed gate stops the sequence and preserves the attempt.
