# 实际 replacement-clock PNR / STA 交接

结论：实际 PNR 完成；功能时序验收失败，不具备 bit 资格。没有 bit、program、Flash、远程或板卡访问。没有调用 final runtime locked controller/main_enable，没有修改任何 gate。

## 实际执行

独立 `work/` 使用 build04 的真实 mapADF（SHA256 `3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419`）和同目录 native PCF；约束是 final runtime 的 replacement clock 与五个 nonclock FDC 的哈希相同副本。脚本没有登记旧 clock 或 LCF，没有 compile/synthesis/devmap。原 MAP CDB 的旧 timing 记录仍被工具继承，这正是实际失败原因之一。

实际命令为官方 `pnr -force_to_run -input_db_file ..._map.adf -optimize_multi_corner_timing -fix_hold_violation -report_timing`。官方 PNR 返回 0，耗时 650.720 秒；日志明确 `Process "Place & Route" done.`。新 PLC、PNR、RTP ADF 与 native prr/rtr 均保留。开始/结束、PID、全机空闲检查、`Global\ov56401_PDS_single_instance` 的非阻塞 mutex、工具/script/source/stage 哈希见 `*_toolcmd.json`、`*_rawreceipt.json`、`*_idle.json`、`protection_*.json`。

原 collector 错把三个合法阶段 ADF 视为“不唯一”；`failure.json` 保留，后续明确选择 `_pnr.adf`，见 `route_selection_correction.json`。一个在导出完成前复制的 partial dump 解析失败也保留；正式绑定使用已完成官方导出 receipt 及 `routed02/analysis/graph.json`。这些收集错误没有被当成工具 PNR 失败或验收成功。

## 原生 STA 实数（ns）

独立 `reports/global10/report_timing/v7_sdt_top.rtr` 与 PNR 原生最终 `.rtr` 一致；下表为各完整原生 summary 的最小 slack。

| 检查 | Slow | Fast |
|---|---:|---:|
| Setup | -0.071 | 1.905 |
| Hold | -1.711 | -0.965 |
| Recovery | 0.780 | 2.355 |
| Removal | -0.038 | 0.067 |
| Minimum Pulse Width | 0.011 | 0.011 |

PNR 的 `v7_sdt_top_timing_summary_after_hold_fix.txt` 和 hold-fix stdout 有不同的中间数值，全部原样保留；没有用更有利数值覆盖报表。工具明确报告 hold fix unsuccessful。

真实 critical paths 与完整路径、坐标、arrival/required、skew 见 `native_STA_actual.json` 和 `fresh_STA_target_receipts.json`：

* Setup -0.071：`cam2_ov5640_top/ov5640/cmos_frame_vsync_r/opit_0_inv/CLK` → `source_diagnostics/cameras[1].source/mailbox[49]/opit_0/CE`。起点 CLMA_165_510，CE 终点 CLMA_117_978；中间 N10 在 CLMA_63_876、N458_2 在 CLMA_75_852，clock skew -1.392。
* Hold -1.711：`source_diagnostics/cameras[1].source/prev_odd[4]/opit_0/CLK` → `.../mailbox[356]/opit_0/D`。起点 CLMA_27_900，终点 CLMA_21_882；捕获 clock branch 使用 CLKROUTE_944（CLMA_21_1080），clock skew 2.085，arrival 4.688、required 6.399。
* Removal -0.038：`source_diagnostics/cameras[1].source/cr_ff1/opit_0/CLK` → `.../mailbox[177]/opit_0/RS`。起点 CLMA_57_523，终点 CLMS_87_919，clock skew 1.897。

这些是同域真实违例，没有增加豁免。最小修正建议：保持已对应的 60 个 native PCF sites，局部调整未锁定的 camera2 CE 组合锥/相关 mailbox 与 prev_odd 的布局及 clock branch，使 CE 路由至少缩短 0.071 ns，并减少上述 2.085 ns 捕获偏斜；hold data path 需要增加至少 1.711 ns（另加工程余量）或获得等量有效 skew 改善；reset RS 路由需要至少 0.038 ns 延迟改善，并复查 recovery。官方已支持的后续工具策略是 `-fix_hold_violation_in_route TRUE` 与增加 `-fix_hold_violation_iterations`，仍须实测 setup/hold/removal，不承诺这些选项单独必然收敛。在新 timing CDB 未真正落入 PNR 前，不用再次旧约束 PNR 冒充 replacement-clock 修复。

## 约束 reload 与真实 coverage

`native_CDB_raw.txt` 是新 routed dump 内的完整原生 CDB 字节，绑定见 `native_CDB_binding.json`。实际 global10、single-pair、mailbox1280 报告仍显示四个 cmos pclk 全域 asynchronous；原生 CDB 和报告都没有 replacement MaxDelay 15.238。DDR 原生 requested frequency 保持 131.2500 MHz。

`fresh_mailbox_pairs_v2.json` 从本次新路由连接重新绑定全部 1280 unique pairs，五个工具插入的 identity CLKROUTE 已沿真实 M→CR 连接追踪，errors=0，corner targets=2560。随后实际执行 native single-pair 和完整 1280 target-set STA；两份报告没有 scored Startpoint/Slack 路径，15.238 实测覆盖为 **0/2560**，不是 PASS。没有使用 no_check，也没有替换/修饰报告。

官方帮助证实 PNR 只有 input_db_file 等选项，没有 SDC override；`.switch_db` 只转换格式；TA 支持 `-sdc/-rtr/-tcl`，但其实际命令集合没有 save_adif，不能把 TA 加载成功推定为写回 PNR CDB。TA native-pins single-pair 小实测加载 free/cmos1/DDR 三个相关时钟及 15.238 成功，在真正 report_timing 时出现 Timing-0081、V_GRS/V_START_E1/V_UDID/V_EFUSECODE/V_IPAL_E2/V_JTAGIF 缺物理 timing model，并以 **3221225477 / 0xC0000005** 崩溃。原始日志/命令/约束/receipt 见 `TA_native_single_actual*`。这不是全约束 reload PASS，也不替代失败的 native route coverage。原 `build04_timing_reload_probe01` 全部冻结未改。

下一步的具体工具问题是：在保持这个 mapADF/source 身份且不重新 compile/syn/devmap 的条件下，取得官方支持的完整 timing CDB replacement + 保存/PNR 接口，并解决 TA 物理模型崩溃。需由能实际写回/消费该 CDB 的工具版本或厂商支持接口完成，当前帮助和实测尚未提供成功通路；禁止人工改 DB phase/CDB 字节或凭 add_constraint 成功登记放行。

## 基本工程保留检查

`fresh_distinct60_sites_v3.json`：60 distinct actual storage、60 distinct native PLACE sites、60/60 native PCF site 对应；没有要求新内部形式证明才能 PNR。

`native_IO112_raw.xml` 是原生 prr 内 IO table 的完整字节。112/112 与 build01 `place_route/prr.db` 的该表逐字节一致；与 qualified `route_attempt_03/place_route/prr.db` 的电气字段、pin、direction 全部一致，仅原生 BANK label 有 112 个差异，原样记录，不推算 bank、不改报告。

`HSST_motion_native_retention_v3.json`：五个 HSST lane/PLL 实际 PLACE 都为 HSSTLP_364_918，映射/路由参数一致；32 个 motion history DRM 的原生参数（包含 36K geometry、READ_BEFORE_WRITE）和接口均保留。741 源文件清单及 186 登记由实际当前文件再次校验；阶段/source 哈希 drift=0。

最终机器交接为 `actual_review_handoff.json`、`official_TA_native_single_failure.json`、`fresh_STA_target_receipts.json` 和 `evidence_hashes_final.json`。结论是明确真实失败，尚无 bit 资格。
