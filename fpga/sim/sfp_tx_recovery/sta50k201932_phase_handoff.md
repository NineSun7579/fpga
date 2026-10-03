# Phase-safe constraint application handoff

Superseded runtime status: see `sta50k201932_installation_proof.md`. Interactive backend post-route load/apply/save is now verified by fresh Production-model reports. The emitter also audits head S aliases, required by the actual routed report.

Production FDC/build.pds/IP unchanged by this work. No PDS/TA runtime was launched after the physical-experiment notification. Runtime work below is pending until its completion notification; do not poll or overlap that experiment.

## Concrete external count solution

`project/tools/sta50k_mapped_enumerate.tcl` enumerates only the seven required pin sets plus the three clocks, with no report/PNR/prerequisites. Use TA's already verified `-tcl` entry point against the **new mapped ADF**, capture stdout/stderr, and record the ADF SHA-256 before and after. The old 201932 database lacks diag_rst_sync and must not pass the full audit.

`project/tools/audit_sta50k_mapped_constraints.py` parses native PDS enumeration records, requires both reported counts and distinct identity counts to be 288 WCLK, 288 RD, 288 head inputs, ten D pins in each Gray direction, and two RS pins in each dedicated sys/diag chain. It verifies Gray bits 0..9 and identical RAM identity sets for WCLK/RD. It emits a separate ASCII **post-map-only** FDC and an audit JSON only after all checks pass. It does not launch PDS or edit production. ADB input hash must match the supplied pre-enumeration hash.

Example invocation after enumeration:

```powershell
& 'C:/Users/NineSun/anaconda3/python.exe' `
  'C:/Users/NineSun/Desktop/ov56401/project/tools/audit_sta50k_mapped_constraints.py' `
  --log '<isolated>/mapped_enumeration_stdout.txt' `
  --db '<isolated>/device_map/hdmi_ddr_ov5640_top_map.adf' `
  --expected-db-sha256 '<hash recorded before enumeration>' `
  --output '<isolated>/sta50k_postmap_only.fdc'
```

The emitter produces explicit pin-name lists for:

```tcl
set_false_path -from <288 WCLK pins> -through <288 RD pins> -to <288 head input pins>
set_max_delay 16.000 -datapath_only -from [get_clocks mrg_clk] -to <10 wptr_rd1 D pins>
set_max_delay 8.000 -datapath_only -from [get_clocks p_clk2core_tx_2] -to <10 rptr_wr1 D pins>
set_false_path -from [get_clocks cfg_clk] -to <sys_rst_sync[0..1]/RS and diag_rst_sync[0..1]/RS only>
```

No IP reset pins, functional RS pins, first->second synchronizer D paths, local reset-release data paths, RAD->RD paths, or WADM paths are selected. Top production f035...dd4c was read and verified to contain registered startup_ready and both reset chains. This does not establish post-build mapped identities until the full audit runs.

Static Python verification against saved actual TA stdout succeeded: counts 288/288/288/10/10; deliberately altered WCLK count rejected; missing sys/diag full enumeration rejected. `--fifo-only` can audit baseline logs but **cannot emit an FDC**. No synthetic full-map success is claimed.

## Unsupported guard API evidence

PDS and TA runtime probes rejected sizeof_collection, get_collection_size, get_object_name, foreach_in_collection, get_attribute, get_property, is_valid, check_object and query_objects. get_pins returns nonempty @tcicmdresultN for **both zero and ten objects**, so empty-string and llength guards are invalid. Shipped syn/lib/map.tcl defines sizeof_collection using get_object_name, but only inside the Synplify synthesis runtime; the backend lacks both APIs. Backend shipped Tcl/XML/templates and binary command catalog contain no get_object_names. Do not load Synplify map.tcl into the PDS backend: its object model is incompatible.

## Minimal pending phase-loading test

The external audit solves object-count validation, but **does not yet prove a supported backend constraint-installation flow**. Do not register its output for compile/synthesis, and do not append an environment-dependent guard to production based on assumptions.

After physical experiment completion, test on a copy only:

1. Determine a documented editor/TA DB+SDC override route that retains physical timing models. TA User Guide printed page 6 documents override; initial standalone TA reports failed with Timing-0081 and missing V_LUT5/V_MUX2. Enumeration and path-form constraint installation work, but analysis does not. Probe get_object_names only if parent has independent evidence; backend command discovery found none.
2. Prefer a report-only override test with the existing routed DB: export its full constraint set, append the audited block, then use the documented TA DB+SDC override. Full constraint preservation matters because SDC replaces DB constraints. Require a valid report showing ordinary 298 mrg->fab setup failures replaced by bounded Gray max-delay exceptions, and preserved fab RAD->RD and CMOS1 WADM checks.
3. For implementation, **do not assume** add_constraint after dev_map plus pnr -input_db_file reapplies a new timing FDC. Runtime pnr -help has input_db_file/input_place_db_file but no input_fdc_file/read_sdc option. pds_shell report_timing explicitly retained DB timing after add_constraint. Any split flow must prove FDC load/application in logs and final report before production adoption.

The existing general PDS shell report-then-get_pins probe gives no enumeration in the parent shell (the report is a child action); that is not a DB-loading API. Earlier source-FDC/constraint script in shell also terminated before reporting, whereas the stripped report-only script succeeded; do not promote it to a phase-loading solution.
