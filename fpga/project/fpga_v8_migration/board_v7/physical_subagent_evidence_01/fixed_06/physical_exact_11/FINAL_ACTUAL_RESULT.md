# route03 exact11 实际结果

实际PNR成功；最终验收未通过，无bit、remote/program。生产/旧V7/IP保护1022文件SHA256零漂移，运行输入零漂移。

完整364有向clockpair实际synthesis/routed CDB证明通过；compile/synthesis/routed覆盖通过。
单对max_path8探针及四相机物理查询完成；全部target shell/run/report日志Timing-4006、STA-3016、unknown选项计数为0。

|角|mailbox覆盖|预算逐对覆盖|最差裕量ns|
|---|---:|---:|---:|
|Slow|1320/1320|1320/1320|13.507|
|Fast|1320/1320|1320/1320|14.177|

全部2640条mailbox记录均已验收15.238ns datapath-only与非负Slack；missing/unexpected/bad_budget均为0。

|检查|Slow失败端点|Fast失败端点|
|---|---:|---:|
|Setup|4|0|
|Hold|0|0|
|Recovery|0|0|
|Removal|0|0|
|Minimum Pulse Width|0|0|

实际负路径全部为Slow同域setup；本次返回4条与十组摘要失败端点总数一致，跨域负路径0。

- cmos2_pclk → cmos2_pclk：cam2_ov5640_top/ov5640/cmos_frame_valid_r/opit_0_inv/CLK → cam2_ov5640_top/ov5640/ov5640_cdc/count_prefix[5]/opit_0_inv/D，-0.749ns。
- cmos2_pclk → cmos2_pclk：cam2_ov5640_top/ov5640/cmos_frame_vsync_r/opit_0_inv/CLK → source_diagnostics/cameras[1].source/cq/q[16]/opit_0/D，-0.167ns。
- ddrphy_sysclk → ddrphy_sysclk：u_v8_capture_control/aw_addr[9]/opit_0_inv/CLK → cam5_ov5640_ddr/diag_shorts[15]/opit_0_AQ_perm/CE，-0.03ns。
- ddrphy_sysclk → ddrphy_sysclk：u_v8_capture_control/aw_addr[9]/opit_0_inv/CLK → cam5_ov5640_ddr/dbg_fault_snapshot[12]/opit_0/CE，-0.014ns。

reset语义绑定32个逻辑入口→20个物理RS；实际Recovery/Removal双角均覆盖12/20，8个cr[0]/cr[1]缺报告记录，缺记录不当作负裕量也不当作通过。需逐项核验例外及实际检查可达性；不扩大reset例外。
已返回reset检查最差Slack：Slow 1.51ns / Fast 1.003ns。
同步器8个外部物理pair Setup/Hold双角完整且非负（Slow 0.473ns / Fast 0.322ns）；8个gopSRL2内部级尚缺内部STA证据，门禁失败。

HSST站点与专用连接、112个IO及保护文件门禁通过。原audit在离线classify前因另一会话PDS busy停止，失败receipt完整保留；本次仅从现有实际报告补齐门禁，未新启动PDS。

364 clockpair及1320双角mailbox预算迁移证据成立；reset检查覆盖和打包同步器内部STA仍未完整，且4条同域setup失败，不可作为最终签核/烧录候选。

证据：runtime_clockpair_and_budget_proof.json、physical_target_*_audit.json / *_logproof.json、evidence/*_routed_audit.json、final_ten_sta_counts.json、negative_path_classification_exact11.json、result.json。
