# Prepared installation probe — no runtime launched

Historical preparation record. Authorized runtime probes have since run; `sta50k201932_installation_proof.md` contains current evidence and the working post-route installation flow.

`project/tools/prepare_sta50k_phase_probe.py` prepared executable Tcl probes and review-only PowerShell commands under:

`C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated/phase_install_probe/`

The manifest is PREPARED_NOT_EXECUTED and pins the routed ADF hash to `dbf4a114f335e3f046c2a03544f0763953f1c09ae8bf4b69be75429692d36b98`. Wait for the physical-experiment completion notification. Do not launch the generated commands while it runs.

## New static findings

- TA supports DB, `-sdc`, `-rtr`, `-tcl`; its report command implementation must be inspected separately from pds_shell's. The generated ta_help.tcl does exactly that. The prior physical-library failures were from standalone TA's bare report_timing, not proof that documented DB+SDC analysis cannot work.
- TA binary contains `physical_timing_library`, `LoadCellTimingModel`, `Load Timing liberty fail`, and `FAB_INSTALL_PATH`. The current environment does not set FAB_INSTALL_PATH. Vendor installation contains PGL50H timing models and logos_gtp_sg6.lib, so files are present; this points to model initialization, not a proven missing installation. Do not invent a flag from these strings.
- Prepared baseline probes try native report's architecture-selection branches **only if help advertises them**: `-family Logos` or `-input_db_file <copy>`. These are hypotheses pending help, not verified accepted commands. If help exposes neither, skip them.
- Supported `.switch_db -input <ADF> -output <new text ADF>` is prepared as backend_dump_db.tcl. Runtime help was previously verified; execution is pending. Its purpose is inspect whether complete DB timing constraints can be exported without reconstructing clocks manually. It must never overwrite input ADF.
- Vendor Add Constraint template mentions `-sdc`, `-fdc`, `-logic`, and `-physical`, but installed runtime help lists only `-copy` plus filename. The template is stale evidence; do not use its flags without runtime proof.

## Concrete phase-flow candidate for proof

The stage guard can be an explicit caller-controlled phase, with external object-count audit, rather than an unsupported in-FDC collection count:

1. Compile/synthesize/dev_map with the ordinary production FDC only. Parent handles the build; this subagent does not launch prerequisites.
2. On the resulting isolated map, enumerate and audit exact WCLK/RD/head/Gray/reset pin sets using the supplied scripts. Emit postmap_only.fdc only on full success. This is the implemented stage-safe enforcement gate.
3. Apply that emitted file to a copied map/route DB through the documented TA DB+SDC override after baseline models initialize; preserve all DB constraints by exporting a full SDC first. Alternatively test backend registration after map plus force PNR, but only as a separate authorized physical experiment; its new constraint import must appear in logs. A report-only `add_constraint` is known not to demonstrate this.
4. Prove installation with an actual exception report: 16 ns and 8 ns Gray data bounds, exactly ten first-stage D destinations each; storage WCLK-origin paths excluded; fab RAD->RD and cmos1 write-address hold remain. Do not move to production on syntax acceptance alone.

This avoids mapped queries in compile/synthesis entirely. It is **a concrete pending phase-flow candidate**, not yet a working backend install API. The prepared help/model/DB conversion probes target the outstanding step without PNR or recompilation.

## Why catch does not prove a safe production block

Standard Tcl catch can consume a Tcl return error, but native PDS diagnostics may set persistent global error state even if the Tcl status is caught. TA logs already show `Public-4023: Error has occurred, please run command clean before running again` after the arc-installation error. A catch-only guard must not be adopted without a copied compile-phase proof showing no E: and an actual mapped report proving enforcement. Likewise populated and empty get_pins queries both return nonempty opaque handles, so string tests provide no stage discrimination.

Production FDC/build.pds/IP remain unchanged. No vendor runtime was started after the physical-experiment heads-up.
