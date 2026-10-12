Batch timing diagnosis
======================

The original default placement build returned 0 but its post-hold-fix summary
reported cmos2_pclk setup WNS -0.400 ns, TNS -0.818 ns, four endpoints.
The unchanged integrated_six baseline reports All Constraints Met.

The guarded command was:

    C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe -project <this>/project.pds -run report_timing -work_dir <this>

This PDS invocation reran compile through report_timing (13m5s), rather than
reporting only on the existing routed database. The rerun reproduced the
post-hold-fix summary. Its separate report_timing/top.rtr used the command
`report_timing` and reported WNS -0.458 ns, TNS -1.086 ns, five endpoints.
These are distinct reports: neither is evidence of timing closure.

The three worst detailed slow-corner setup paths are in
violating_camera_paths.txt. All launch from
cam2_ov5640_top/ov5640/cmos_frame_vsync_r on the falling edge and capture
ov5640_cdc/src_seq[31], [28], [24] clock enables on the rising edge.
Their detailed-report slacks are -0.458, -0.323, -0.189 ns.

Worst path: half-period is 5.953 ns; clock skew is -2.275 ns; data path
logic delay is 1.387 ns and route delay 2.471 ns. The path traverses
the duplicated N18 enable and seven CECO links. The launch clock route
has an additional local clock-routing hop (CLKROUTE_1095) with a 1.829 ns
net to the launch register. This is a physical placement/control-chain
and clock-skew problem on existing camera diagnostic sequence logic.

Byte-level RTL inspection confirms the falling-edge register in ov5640.v
and the posedge cam_clk `s_vsync && !src_vs_q` condition updating src_seq
in ov5640_cdc.v. Neither file differs from integrated_six. Only the
intended delivery_regs.v capability-bit and pcie_fifo.v register-read
burst changes exist. No camera source fix is justified before a seed retry.

`python rerun_seed.py 2` sets only gplace_seed=2 in this isolated project,
archives prior build products, guards against any active pds/pds_shell,
and rebuilds through report_timing. It records exact input hashes, command,
return code, duration and source preservation in seed_2_manifest.json.
An initial script attempt failed on CRLF marker detection before changing
project.pds or archiving build products; the marker handling was corrected.

`python audit_sources.py` passes and writes timing_source_audit.json.
`python rerun_engine_test.py` passes and writes timing_engine_test_receipt.json
and project-local timing_validation_sim logs. The candidate has zero errors
and SIX_BATCH_ENGINE_PASS. The baseline negative control has the expected
Fatal: register burst not single beat (ModelSim returns zero even for this
fatal with its existing script, so the marker is verified explicitly).

No board access, programming, host source edits, shared build-tool edits,
source edits, timing-constraint changes or commits were performed.

Seed 2 completed in 750.275 seconds with PDS return code 0 and unchanged
source hashes, but was rejected by verify_timing_closure.py (exit 1).
Post-hold-fix camera2 setup improved to +0.471 ns; DDR setup became -0.101 ns
and camera2 hold became -1.405 ns slow / -0.778 ns fast. Detailed report:

* Camera2 hold launch cmos_capture/temp_cnt[0], capture cmos_data_t[15]/D,
  +2.063 ns clock skew, 0.158 ns logic + 0.441 ns route, -1.417 ns slow
  and -0.788 ns fast slack.
* DDR setup launch cam6_ov5640_ddr/flush_count[2], capture
  cam6_axi_dma_write/wd_cnt[12]/RS: -0.161 ns slack, -0.203 ns skew,
  1.426 ns logic + 5.757 ns route. Other reported endpoints are
  wd_cnt[4]/RS (-0.038 ns) and wd_cnt[16]/RS (-0.025 ns).

Full paths are saved in seed_2_violating_paths.txt and rejected-build hashes
in seed_2_closure_receipt.json. These are deployment timing failures only;
camera5/6 image defects remain deferred and no related RTL changes were made.

Seed 3 retry uses the same guarded script and unchanged inputs. A single
background process wait is registered to run verify_timing_closure.py 3
after the runner exits, with automatic completion notification. Verification
requires both the post-hold-fix summary and separate detailed timing report
to say All Constraints Met; PDS return code 0 alone is insufficient.

FINAL: Seed 3 achieved timing closure. Build completed with return code 0
in 700.885577 seconds; verify_timing_closure.py 3 returned 0. Both reports
say All Constraints Met with no violating paths. Post-hold-fix slow setup
WNS: cmos2_pclk +1.206 ns, ddrphy_sysclk +0.070 ns. Separate detailed report
slow setup WNS: cmos2_pclk +1.191 ns, ddrphy_sysclk +0.026 ns. The DDR
margin is small but positive in both reports; no margin improvement is claimed.

Authoritative final receipt: seed_3_closure_receipt.json (source hashes,
project hash, report hashes, exact command, build duration, test receipts).
Build receipt: seed_3_manifest.json. Source audit: timing_source_audit.json.
Reproduction: generate the original isolated candidate with make_six_batch.py,
then run this project's rerun_seed.py 3 and verify_timing_closure.py 3.
The shared generator still produces the exact RTL; the isolated seed script
is the additional project recipe. Shared six_batch_pds_manifest.json describes
the original failing build and was intentionally not overwritten.

No RTL modification was needed. Capability bit3 and r_burst_len behavior
remain byte-exact generator transforms; 361 baseline hashes are preserved.
The fresh complete PCIe-engine simulation passed and its negative control
failed on the expected assertion. This is timing/source/test closure only:
no bitstream generation or board programming was performed in this task.
