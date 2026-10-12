# Verified installation into a routed DB

Native interactive `pds_shell` is the working installation route. Batch `-file` defers action execution and cannot be used for this load/source/save sequence. Feed these Tcl commands through stdin, synchronously, using Python subprocess.run; no GUI is required:

```tcl
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
mpnr -input {<NEW DISPOSABLE COPY OF ROUTED ADF>}
source {<audited post-route candidate FDC>}
save_adif
exit
```

**save_adif saves the loaded ADF in place.** Its advertised `-file_name` did not create a new file in the test; the loaded disposable DB changed instead. Always copy the ADF to a new path before loading. `project/tools/apply_sta50k_postmap_interactive.py` implements this rule, requires the full audit and FDC hash, checks input preservation, and rejects native diagnostics. Its full four-reset-pin run remains pending the parent's new routed DB; the underlying stdin load/apply/save sequence was tested on actual baseline objects.

Then report the saved copy using a separate batch script:

```tcl
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
report_timing -input_db_file {<INSTALLED COPY>} -force_to_run -delay_type min_max -nworst 1 -max_path 400 -input_pins TRUE -report_exception TRUE
```

The backend initializes Production timing models successfully. Standalone TA reporting is unnecessary for this flow and remains broken with Timing-0081 / missing V_LUT5/V_MUX2; TA enumeration alone works.

## Actual fresh-report evidence

Isolated directory: `C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated/phase_install_probe/`.

- `mpnr_interactive_stdout.txt`: synchronous native DB load, 288 WCLK, 288 RD, 288 head I pins, ten first-stage D pins per direction, and two sys reset RS pins; all timing commands accepted and DB saved.
- `mpnr_s_alias_stdout.txt`: 198 additional head-mux S pins enumerated and WCLK-through-RD-only exception installed and saved.
- `installed_report/final_report_stdout.txt`: independent fresh backend report completes successfully.
- `installed_report/report_timing/hdmi_ddr_ov5640_top.rtr`: final report with Production timing models, both corners, and explicit exception annotations.

Final report proves:

1. Write Gray bits 0..9: ten destinations per corner carry `MaxDelay Path 16.000ns -datapath_only`. Read Gray bits 0..9: ten destinations per corner carry `MaxDelay Path 8.000ns -datapath_only`. Both binary-MSB source aliases wbin[9] and rbin[9] are included. There are 40 max-delay path records total across the two corners.
2. mrg->fab setup now has **ten endpoints, zero violations**: slow worst slack +14.911 ns, fast +15.235 ns. Original baseline had 298 failing endpoints.
3. No negative storage-WCLK path remains. The 288 WCLK/RD/I collection was insufficient alone: 72 extra endpoint checks terminate on physical head mux S pins. Adding S destinations, while retaining WCLK origins and mandatory RD throughpoints, removes those aliases. This does not broaden the origin to a clock family or the throughpoint beyond storage RD.
4. **576 actual RAD->RD head max paths remain**, 288 per corner; minimum slack +4.247 ns, matching the saved baseline. The final report contains 850 local WADM min-path records, including cmos1_pclk_16bit paths in u_cam2_merge/u_afifo. The 0.200 ns hold uncertainty remains explicitly present.
5. cfg->sys functional setup remains: 50 endpoints. Recovery endpoints decrease from four to two after excluding only sys_rst_sync[0..1]/RS; the remaining functional-reset recovery violations remain visible. No sys_rst_sync RS endpoint appears in the final report. The old DB contains zero diag_rst_sync pins; no four-pin success is claimed. Parent must audit sys=2 and diag=2 on its new routed DB.

External count audit now also requires **198 head S aliases**, in addition to 288 I pins. This deliberately fails if a new implementation uses a different mapped mux topology; review the changed mapped identities before changing that expected count. The emitter produces two storage false paths with exact identities, plus both Gray bounds and the four dedicated-reset RS exception.

## Phase behavior and limits

- Compile/synthesis never sees the post-route FDC, so mapped objects cannot fail early compilation. Audit and installation occur only after route.
- `mpnr -input <DEVMAP>` rejects with Flow-0013 requiring PNR/PLC. `mpnr -input <PLC>` rejects with DesignEditor-0024, so the advertised PLC phase cannot be used in this installed release.
- `pnr -input_db_file <installed PNR DB>` rejects with Flow-0013 requiring DEVMAP. Do not claim this post-route method controls normal PNR optimization.
- A full isolated PNR run using original DEVMAP plus newly registered candidate FDC succeeded physically but retained 298 mrg->fab failures. Registering FDC before PNR therefore **does not install these new constraints**.
- A clean DevMap-only test against the copied synthesis DB also completed successfully with newly registered candidate FDCs. Converting its output with supported `.switch_db` showed the CDB contains only the original FDC filename and baseline records; neither candidate FDC nor new max-delay records was installed. Evidence: `devmap_trial/devmap_install_clean_stdout.txt`, `devmap_trial/dump_map_candidate_stdout.txt`, and `devmap_trial/candidate_cdb.txt`.
- Post-route installation is verified and useful for final STA classification, separate from the parent's physical hold repair. **No supported pre-PNR installation route was demonstrated in this release:** newly registered files were ineffective in both DevMap and PNR, raw map loading is disallowed by mpnr, placed loading is explicitly rejected, and routed input is disallowed by normal PNR. This is a concrete phase/API limitation established by executed tests, not an inferred unsupported collection guard. A vendor-supported import into DEVMAP, or a documented phase-aware original-FDC load during mapping, is required to control normal PNR with these exceptions.

## Integrity

Production FDC remains unchanged at SHA-256 `85a63909d5702ca09076aa85f92f61f3da47e5d26b54b179ba3df1b958bae938`. No original PDS/build/RTL/IP invocation or mutation occurred. Integrity comparison covered 296 isolated source/IP/build/map/route files; only the deliberately edited disposable routed ADF changed. No production append is justified by this post-route proof alone.
