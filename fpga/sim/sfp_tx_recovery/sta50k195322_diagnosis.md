# 50K build195322 TX/FIFO timing diagnosis

## Report-export incident: parent action required

I incorrectly launched `pds_shell -project ov5640_sfp480p_test.pds -run report_timing -work_dir <same50Kwork>`. Although the vendor documents this command, `-run` runs prerequisites up to the requested step. The legacy project was not the successful build's `build.pds`. It started compile/synthesis and invalidated subsequent outputs. The shell timed out after 60 seconds. No new PnR completed. No RTL, FDC, protected IP, or successful build.pds was edited by me.

Before launch I recorded SHA-256 for all existing compile/synthesize/device_map/place_route files in `C:/Users/NineSun/AppData/Local/Temp/sta50k_route_hashes.json`. I restored every available backup whose hash matched its original file. The original placement database, PnR netlist, PRR, PRR database, pin report and clock utilization report are restored and hash-identical. **The original hdmi_ddr_ov5640_top_pnr.adf was removed by flow invalidation and has no hash-matching copy found anywhere in this workspace.** Original compile/synthesis/map ADFs were also replaced. Do not treat the current work directory as an intact routed build, or use the replacement synthesis database with the old placement database. I did not substitute an older route. Full STA export is blocked by this incident.

The last process check found no pds.exe/pds_shell.exe. It found lkads.exe PID 8108, parent PID 1844; stopping it returned access denied. Its relationship to this invocation is unconfirmed. Check processes before any further PDS launch.

## Verified existing timing evidence

`place_route/hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt` survived unchanged and describes the successful route ending 2026-10-02 19:58:20. The restored PRR identifies PGL50H fabric resource usage: 32013 FF, 17448 total reported LUT usage across CLMA/CLMS, 1376 distributed RAM, 91% of both CLMA and CLMS sites.

| Setup domain pair | Slow WNS ns | Slow TNS ns | Failing / total | Fast WNS ns | Fast failing / total |
| --- | ---: | ---: | ---: | ---: | ---: |
| mrg_clk -> p_clk2core_tx_2 | -6.132 | -872.860 | 336 / 336 | -2.868 | 164 / 336 |
| p_clk2core_tx_2 -> itself | -0.483 | -2.046 | 7 / 646 | +1.920 | 0 / 646 |
| mrg_clk -> itself | +4.086 | 0 | 0 / 85077 | +7.533 | 0 / 85077 |
| p_clk2core_tx_2 -> mrg_clk | +6.480 | 0 | 0 / 10 | +5.449 | 0 / 10 |

The saved summary rounds slack to 3 decimals. The requested -6.132336 and -0.4837 figures are not independently recovered at full precision. There is no full per-path report for this route available, and I cannot name the actual seven failing endpoints or assign worst slack to a guessed endpoint.

One exact endpoint is identified by the successful route log, for a separate hold-threshold warning: `u_sfp_video_tx/u_fifo/mem_3_4/ram32x1dp/WADM4`, 104 ps fast-corner hold slack versus the 200 ps router threshold. This is a write-address timing endpoint, not a read-data CDC endpoint; do not cut it.

The restored clock report has global mrg clock driver `mrg_clk/opit_0_inv:Q`, site `CLMA_74_52`, feeding `clkbufg_0/gopclkbufg`, site `USCM_84_116`, 31216 clock loads. Fabric is driven by `u_hsst/U_GTP_HSST_WRAPPER/U_GTP_HSST/hsst:TCLK2FABRIC[2]`. This supports the parent's observation that the mrg clock is globally distributed after its fabric divider.

## Domain relationship and path classification

FDC defines fab as 8 ns, waveform {0 4}; mrg is generated from fab with `-edges {2 4 6}`. Thus mrg has a 16 ns period, rising edges 4,20,... and falling edges 12,28,... . A mrg launch at 4 ns is followed by fab capture at 8 ns: only 4 ns nominal setup budget, before insertion delay/skew/setup effects. The two clocks remain in one related clock family. Never use asynchronous clock groups between them or broad mrg->fab false paths.

`video_async_fifo.v` is a standard Gray-pointer ownership FIFO with 512x19 asynchronous-read storage (`assign rd_data = mem[raddr]`). TX writes every vid/mrg cycle while not full, pops every nonempty fab cycle including link-down, and uses the combinational read head directly in pixel packing and control logic. Three distinct path classes must remain separate:

1. **Gray first-stage synchronization:** wptr[9:0] -> wptr_rd1[9:0], and rptr[9:0] -> rptr_wr1[9:0]. These endpoints have no functional fanout except their respective second stages. The second-stage -> empty/full and all local binary/Gray next-state logic are timed paths. The mapped top Gray bit aliases binary MSB: wptr[9] was merged with wbin[9], and rptr[9] with rbin[9]. Constraints using only wptr/rptr cell-name globs would miss that bit.
2. **Stored data ownership transfer:** write-clock -> dual-port RAM stored-data read output -> fab consumer. FIFO pointer synchronization prevents reading a just-written or unwritten slot; stored data is a bundled transfer, not 19 independently synchronized bits. This can justify a narrowly scoped exception across the actual memory storage/read-output arc only after ownership and reset assumptions are reviewed. That exception must not erase fab rbin/read-address -> RAM read mux -> consumer timing.
3. **Real fab combinational read path:** rbin[8:0] -> RAM read mux tree -> head bits -> pix0/txd/txk/pix_pend/wait_frame/last_vs. These paths need timing closure and are the pipeline target. Broad exceptions to TX registers would hide them.

The successful netlist contains `u_sfp_video_tx/u_fifo/mem_<bank>_<bit>/ram32x1dp` mapped as gopRAM16X1D, including 288 RAM instances (the constant HS bit is optimized away). This implies substantial read selection logic for depth 512. Do not assume block RAM or registered first-word-fall-through behavior.

Concrete mapped endpoints confirmed in the saved netlist (these are target identities, not proven failing endpoints):

```
u_sfp_video_tx/u_fifo/wptr_rd1[0..9]/opit_0_inv/D
u_sfp_video_tx/u_fifo/rptr_wr1[0..9]/opit_0_inv/D
u_sfp_video_tx/pix0[0..15]/opit_0_inv_MUX16TO1Q/{I0..I15,S*,CE}
u_sfp_video_tx/pix_pend/opit_0_inv_L5Q_perm/{L0..L4,CE}
u_sfp_video_tx/wait_frame/opit_0_inv_L5Q_perm/{L0..L4,CE}
u_sfp_video_tx/txd[20]/opit_0_inv_L5Q_perm/{L0..L4,CE}
u_sfp_video_tx/txd[31]/opit_0_inv_L5Q_perm/{L0..L4,CE}
```

Mapped registers can absorb LUT/mux logic, so their endpoint pins are not always named D. A full report should query cell collections to include every register input and inspect the actual path pins.

## Exact RTL pipeline recommendation (not applied; not simulated)

Add a one-entry, continuously replaceable read-head stage in sfp_video_tx, leaving FIFO storage and pop logic unchanged:

```verilog
reg [18:0] head_q;
reg head_valid_q;
reg head_go_q;
always @(posedge fab_clk or negedge fab_rst_n) begin
    if (!fab_rst_n) begin
        head_q       <= 19'b0;
        head_valid_q <= 1'b0;
        head_go_q    <= 1'b0;
    end else begin
        head_valid_q <= `UD fifo_pop;
        head_go_q    <= `UD tx_go;
        if (fifo_pop)
            head_q <= `UD fifo_rdata;
    end
end
wire consume_head = head_valid_q;
wire payload_go = tx_go && head_go_q;
```

Keep FIFO `.rd_en(fifo_pop)` and `fifo_pop = ~fifo_empty` exactly as now. The stage captures the **pre-increment** head on the same edge as the pop. On the next edge the packer consumes that captured word exactly once. It can capture the next head simultaneously; there is no one-cycle bubble for consecutive pops and no delayed-pop duplicate/skip.

In the packer and last_vs/last_hs block only, replace each fifo_pop use with consume_head, replace fifo_rdata uses with head_q, and define head_vs/head_hs/head_de from head_q[18:16]. Replace `if (!tx_go)` in the packer with `if (!payload_go)`. A current low tx_go immediately suppresses stale queued payload, while a word captured during low readiness cannot authorize frame recovery if readiness rises a cycle later. Preserve all existing pix_pend/pix0 pairing branches and the consumed VS blank condition. Use a constant reset word `32'hBC0028BC` for txd, not idle_word (idle_word includes another register's state and currently produces a dual asynchronous reset/set warning on txd[21]). The constant reset avoids that synthesis style; it does not by itself fix the head mux timing.

This pipeline adds one fab cycle of control/payload latency. All control state and idle status must follow the same staged consumption; delaying only RGB breaks first/last pixels and VS/DE ordering. On an empty cycle head_valid_q becomes zero; never consume stale head_q. Keep continuous drain during link loss. Existing even-width row pairing is preserved; the original design discards an unpaired pixel before a DE=0 blank, so this change does not add an odd-width-row protocol.

The stage separates RAM selection from packing, but a 512-entry read mux can still fail within 8 ns. If it does, evaluate a true registered-read dual-clock RAM/FIFO with an explicit request/response-valid and prefetch buffer contract. Do not simply change FIFO rd_data to a register while retaining the present combinational-head consumer/pop contract. A new PnR would be required to prove closure; none is authorized here.

## Narrow constraint recommendation

For a reviewed CDC implementation, constrain ONLY the exact source Gray registers (including the merged binary MSB alias) to first-stage data pins. Keep first->second stage, second->empty/full, and local pointer arithmetic timed. Because domains are related and these paths may already meet timing, first examine their reports before adding exceptions. Prefer a bounded data-path delay/skew appropriate to the fastest pointer update period where supported; do not erase the Gray bus physical skew requirement with an unconstrained false path. Read pointer can update each 8 ns, write pointer each 16 ns, so the respective bounds differ. Pin/cell collection counts should be checked explicitly (10 bits each direction).

For memory, first inspect primitive arc semantics. If the write-clock->read-output arc is represented as a cross-domain storage arc, a narrowly scoped exception through the **specific dual-port read data output pin** and from the **write clock** may be appropriate. Exempting all paths through RAM outputs without a write-side source restriction would also cut the real fab read-address path and is wrong. If PDS supports disabling only the write-clock->read-output internal arc, that is a clearer alternative, provided other write-port and read-address arcs stay timed. Do not cut WADM, write data, write enable, read address, or all paths to head_q/txd/pix0. Exact memory output pin names and exception syntax need the full timing model/report; I have not guessed a production FDC command.

## Vendor report support and verification limits

`C:/pango/PDS_2022.2-SP6.4/doc/Pango_Design_Suite_User_Guide.pdf`, PDF pages 166-167, documents `-run report_timing` as running **up to** Report Timing. Pages 211-212 document `report_timing -from -to -through -delay_type -nworst -max_path`. Page 255 lists `-input_pins`, `-slack_less_than`, and `-ignore_db_version`. Avoid `-run` for a strict report-only action. A Tcl file containing only a supported architecture/database setup and `report_timing` should be used against a disposable copy of a verified complete route, with no compile/synthesize/dev_map/pnr commands.

Suggested requested report content once a complete route is available: slow/fast setup+hold, mrg->fab nworst>=5/max_path>=1000; fab->fab max_path>=1000; targeted reports to every first-stage pointer bit, pix0, txd/txk, pix_pend, wait_frame, last_vs, empty and rbin. Report both input pins and clock insertion paths so source class and skew are visible. Preserve separate reports when a report action overwrites the default .rtr.

Existing production simulation logs were inspected, not rerun: production.log has 43 cases, zero errors and forbidden payload words; full_production.log reports two full merged frames, 1,228,800 matching decoded pixels, 614,400 per split camera. They validate existing recovery RTL only. They do **not** validate the recommended pipeline. For a pipeline trial copy the regression into an isolated directory and make its consumed-head/control monitor explicitly latency-aware; do not weaken pixel order, first/last, recovery authorization or forbidden-payload assertions.
