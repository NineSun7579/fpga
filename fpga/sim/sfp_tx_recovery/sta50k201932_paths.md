# Build201932 isolated routed STA path diagnosis

Report-only STA succeeded on a verified disposable copy. No PDS command was run against the original project. No production RTL, IP, or FDC was edited. No compile, synthesize, dev_map, pnr, or bitstream action ran, even on the copy.

Original root: `C:/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test`.
Isolated root: `C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated`.

The copy contains 554 files / 262,875,250 bytes: complete current source/IP, build.pds, compile/synthesize/device_map/place_route, constraints, logs, and the build201932 archive. Older root bitstream archives and logbackup were excluded; no source/IP/current-flow subtree was excluded. Each copied file was checked against its original SHA-256 before tool execution. `isolation_manifest.json` records the exclusions. `original_hashes_before.json`, `original_hashes_after.json`, and `hash_audit.json` record the integrity audit: zero original changes, missing files, or added files in the copied scope; copied source/IP/build.pds/compile/synthesize/device_map/place_route also unchanged after reporting.

Original and copied routed ADF SHA-256:
`dbf4a114f335e3f046c2a03544f0763953f1c09ae8bf4b69be75429692d36b98`.

## Exact supported report-only invocation

Runtime `report_timing -help` exposed the correct option, **`-input_db_file`**, not `-input`. The vendor user guide PDF pages 166–167 describes `-file` Tcl execution and warns through its documented semantics that `-run report_timing` runs up to the reporting step. Pages 211–212 describe min/max/min_max and path limits. The current runtime help additionally documents `-force_to_run` and `-input_db_file`.

From the isolated root only:

```powershell
& 'C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe' `
  -file 'C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated/report_only.tcl' `
  -work_dir 'C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated' `
  -project_name report_only
```

The entire Tcl script is:

```tcl
set_arch -family Logos -device PGL50H -speedgrade -6 -package FBG484
report_timing -input_db_file {C:/Users/NineSun/AppData/Local/Temp/sta50k201932_isolated/place_route/hdmi_ddr_ov5640_top_pnr.adf} -force_to_run -delay_type min_max -nworst 1 -max_path 1000 -input_pins TRUE -slack_less_than 0
```

This creates a new reporting project; it does not open either the successful build.pds or the legacy PDS. It reads clocks/constraints from the routed database. The log explicitly says `Reading design from pnr DB`, followed only by Report Timing. Report version: Fabric Compiler 2022.2-SP6.4 build 146967; production timing models; multi-corner. No `-ignore_db_version` was needed. No prerequisites executed. No existing flow database changed.

The complete negative report is `full_negative.rtr` under the isolated root (625 path records). `paths.csv` and `paths.json` enumerate every exported negative path with exact startpoint, endpoint, through pins, corner, slack, launch/capture edges, and its line in that report. A supplemental report, `fab_local.rtr`, includes positive paths and multiple paths per endpoint. Its literal `-from {p_clk2core_tx_2} -to {p_clk2core_tx_2}` filters did **not** exclude other clock groups in this runtime; select its paths by their actual reported clocks, not by its filename. The negative export is exhaustive for the reported failing endpoints in fresh STA because each group contains fewer than 1000 endpoints and nworst=1.

## Saved router summary versus fresh report-only STA

The saved `place_route/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt` matches the parent's requested build201932 numbers. Fresh STA of the same hash-identical routed ADF differs slightly; the cause of these numerical differences has not been established. Do not attach saved router slack to an individual newly exported path as though they are the same analysis result.

| Check | Router slow WNS / endpoints | Fresh STA slow WNS / endpoints | Router fast WNS / endpoints | Fresh STA fast WNS / endpoints |
|---|---:|---:|---:|---:|
| cfg→sys setup | -2.534 / 50 | -2.561 / 50 | -1.762 / 50 | -1.787 / 50 |
| cfg→sys recovery | -2.698 / 4 | -2.749 / 4 | -1.888 / 4 | -1.923 / 4 |
| cfg→25M recovery | -5.195 / 84 | -5.293 / 84 | -3.522 / 84 | -3.584 / 84 |
| mrg→fab setup | -2.673 / 298 | -2.693 / 298 | -0.319 / 39 | -0.337 / 45 |
| CMOS1 DIV2 hold | -0.191 / 3 | -0.150 / 1 | -0.211 / 13 | -0.179 / 5 |

All numbers are ns. The other two saved slow hold endpoints and eight additional saved fast hold endpoints cannot be assigned from the saved summary alone. Fresh STA provides actual paths for its one slow and five fast failures.

## cfg→sys setup: synchronous watchdog-clear control, 50 input pins / 20 registers

All 50 slow and fast failing endpoints belong to `u_hsst/U_IPML_HSST_RST/AUTO_MODE.ipml_hsst_rst_pll/pll0_lock_wtchdg/{cnt_1[0..9],cnt_2[0..9]}`. These are 50 mapped register input pins, including CE and LUT inputs, on 20 counters bits; they are not 50 distinct registers or synchronizers.

Worst slow and fast path (`full_negative.rtr:291` / `:29587`):

```text
rstn_1ms[12]/opit_0_inv_A2Q21/CLK
  Q1
  -> N206_15/gateop_perm/L3 -> Z
  -> N206_14/gateop_perm/L2 -> Z
  -> u_hsst/U_IPML_HSST_RST/AUTO_MODE.ipml_hsst_rst_pll/pll0_lock_wtchdg/N34/gateop_perm/L4 -> Z
  -> .../pll0_lock_wtchdg/cnt_2[0]/opit_0_inv_L5Q_perm/CE
slow -2.561; fast -1.787
cfg launch 4819.591 ns; sys capture 4820.000 ns
```

Top RTL line 851 connects `i_wtchdg_clr_0(~rstn_int)`, while `i_free_clk` uses sys_clk. Watchdog RTL uses wtchdg_clr directly in synchronous counter clear/enable expressions. The startup counter comparator therefore crosses from cfg into synchronous sys control, bypassing the existing sys reset synchronizer. These clocks are generated from the same sys source and are related, with only 0.409 ns nominal edge separation in this check. This is a real control timing obligation, not a Gray-pointer or asynchronous reset-pin exception. A top-level candidate is to drive watchdog clear from the sys-domain reset state, after reviewing startup behavior, instead of the raw cfg comparator. No IP edit or broad cfg→sys cut is justified by these paths.

## cfg→sys recovery: reset synchronizer asynchronous pins, four endpoints

All four exact endpoints are:

```text
sys_rst_sync[0]/opit_0/RS
sys_rst_sync[1]/opit_0/RS
u_hsst/U_IPML_HSST_RST/AUTO_MODE.ipml_hsst_rst_pll/pll0_rstn_sync/sig_async_ff/opit_0/RS
u_hsst/U_IPML_HSST_RST/AUTO_MODE.ipml_hsst_rst_pll/pll0_rstn_sync/sig_synced/opit_0/RS
```

Worst slow path (`full_negative.rtr:21580`):

```text
rstn_1ms[10]/opit_0_inv_A2Q21/CLK
  Q1 -> N206_11/gateop_perm/L2 -> Z
     -> N206_13/gateop_perm/L1 -> Z
     -> N18/gateop_perm/L4 -> Z
     -> sys_rst_sync[0]/opit_0/RS
slow -2.749
```

Fast worst uses `rstn_1ms[0]/opit_0_inv_L5Q_perm/Q -> N206_8/L2,Z -> N206_12/L3,Z -> N18/L1,Z -> sys_rst_sync[0]/opit_0/RS`, -1.923 ns. The sys chain explicitly implements asynchronous assertion / two-edge release. These are candidate narrowly scoped asynchronous reset-synchronizer exceptions, conditional on reset integrity and synchronizer review. A binary counter equality comparator is combinational; its glitch-free behavior has not been proven here. Keep synchronizer data propagation and downstream local reset-release timing intact. Never cut all cfg→sys paths, because that would also hide the watchdog paths above.

## cfg→25M recovery: direct functional reset release, 84 endpoints

All 84 endpoints are RS pins in `u_sccb_diag1` and `u_sccb_diag2`: 42 each, including waitcnt, st_reg, ra, idx, start, and u_probe fsm/op/bitc/divcnt/ph/sda_low/scl/busy/rdata_valid. Complete identities are in paths.csv.

Worst slow (`full_negative.rtr:21880`):

```text
rstn_1ms[10]/opit_0_inv_A2Q21/CLK
  Q1 -> N206_11/L2,Z -> N206_13/L1,Z -> N18/L4,Z
  -> u_sccb_diag2/u_probe/ph[0]/opit_0_L5Q/RS
slow -5.293
cfg launch 4719.183 ns; clk_25M capture 4720.000 ns
```

Fast worst (`:36557`) uses rstn_1ms[0] through N206_8, N206_12 and N18 to `u_sccb_diag2/waitcnt[1]/opit_0_A2Q1/RS`, -3.584 ns. Top lines 292 and 309 supply raw rstn_out to both diagnostics. This is asynchronous deassertion directly into functional registers, not into a dedicated reset synchronizer. The related clocks have only 0.817 ns nominal separation. Treat these as genuine recovery violations; a local 25M asynchronous-assert/synchronous-release reset is the structural candidate. Cutting all 84 RS checks would conceal the release problem.

## mrg→fab setup: 288 storage paths + 10 Gray first-stage paths

The 298 slow failing input pins comprise exactly:

- 288 distinct RAM WCLK startpoints → 288 head_q input pins: 16 mapped inputs on each of bits 0..16 and 18. Bit 17 is optimized away.
- 10 Gray pointer first-stage D pins, bits 0..9.

Worst storage path (`full_negative.rtr:3998`):

```text
u_sfp_video_tx/u_fifo/mem_7_4/ram32x1dp/WCLK
  -> u_sfp_video_tx/u_fifo/mem_7_4/ram32x1dp/RD
  -> u_sfp_video_tx/head_q[4]/opit_0_inv_MUX16TO1Q/I15
slow -2.693; fast -0.337
mrg launch 4 ns; fab capture 8 ns
```

The model's storage output is **RD**, not a guessed Q pin. FIFO ownership/synchronized pointers can justify a reviewed storage-transfer exception limited to write-clock-originated paths through those RAM RD pins; preserve RAD→RD arcs, WADM timing, and all fab read-address paths. Disabling the primitive WCLK→RD arc may be cleaner if supported and reviewed; this session did not validate an exception command. Head_q inputs also accept real fab-local read-address paths, so a blanket false path to head_q or through RD would be wrong.

Gray first-stage worst (`:20990`): `u_sfp_video_tx/u_fifo/wptr[5]/opit_0_inv_L5Q_perm/CLK -> Q -> u_sfp_video_tx/u_fifo/wptr_rd1[5]/opit_0_inv/D`, -1.170 ns. Slow slack by bit: 0 -0.798; 1 -1.024; 2 -1.030; 3 -0.789; 4 -0.768; 5 -1.170; 6 -0.791; 7 -1.030; 8 -1.070; 9 -1.056. Bit 9 starts at `wbin[9]/opit_0_inv_A2Q21/CLK -> Q1`, because the Gray MSB aliases binary MSB. All ten fast first-stage checks meet. These are intended Gray ownership crossings; any narrow CDC treatment must include the MSB alias, retain a suitable bus delay/skew bound, and keep first→second-stage and second-stage→empty timing.

Both clocks remain related: fab 8 ns, mrg 16 ns waveform {4,12}. Do not declare them asynchronous as a whole. The supplemental report confirms a real fab-local read path with +4.247 ns slow slack:

```text
u_sfp_video_tx/u_fifo/rbin[3]/opit_0_inv_A2Q21/CLK
  Q0 (mapped rbin[2])
  -> u_sfp_video_tx/u_fifo/mem_11_16/ram32x1dp/RAD2
  -> u_sfp_video_tx/u_fifo/mem_11_16/ram32x1dp/RD
  -> u_sfp_video_tx/head_q[16]/opit_0_inv_MUX16TO1Q/I14
```

Overall fresh fab-local setup WNS is +3.351 ns; no fab-local setup failure appears in the complete negative report. The worst supplemental local path is the mrg divider's own feedback, not FIFO stored-data ownership. The head stage is already present in build201932 RTL.

## CMOS1 DIV2 hold: local RAM write address, do not cut

All fresh failing paths launch at `u_cam2_merge/u_afifo/wbin[5]/opit_0_inv_A2Q21/CLK`, data output Q0, and terminate directly at the following RAM WADM4 pins. Both launch and capture clocks are cmos1_pclk_16bit; edges are 0→0. These are local write-address hold checks, not asynchronous FIFO read ownership paths.

| Endpoint beneath u_cam2_merge/u_afifo | Slow slack | Fast slack |
|---|---:|---:|
| mem_20_6/ram32x1dp/WADM4 | -0.150 | -0.179 |
| mem_29_11/ram32x1dp/WADM4 | met | -0.036 |
| mem_29_14/ram32x1dp/WADM4 | met | -0.036 |
| mem_17_8/ram32x1dp/WADM4 | met | -0.018 |
| mem_29_8/ram32x1dp/WADM4 | met | -0.012 |

Worst full paths are at `full_negative.rtr:3921` and `:33217`; the CSV lists all five fast cases. Fix through physical hold repair / routing or a reviewed implementation change. Do not erase WADM checks or the existing 0.200 ns hold uncertainty merely to obtain a clean report.

The final SHA-256 audit passed after both report actions. Findings establish concrete path classes and safe report-only commands; they do not constitute timing closure or approval of any new timing exception.
