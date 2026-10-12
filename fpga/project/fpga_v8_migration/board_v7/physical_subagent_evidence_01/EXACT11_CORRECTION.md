# exact11 最小修正及实际运行证据

修正仅在独立 `source_diagnostics_route_03` 实施。生产源、旧 V7 与 IP 的 1022 个保护文件 SHA256 已离线复核不变；没有 remote/program。旧 exact09、epoch10 和原 audit 档案均保留。

`generate_exact11.py` 从原冻结 clock.fdc 的全部时钟与单组 asynchronous 语义重建有向 U。冻结 V7 的真实 `synthesize_report_timing_clock_summary` 递归展开为 20 时钟，已验证与 FDC 一致。U 共 368 有向时钟对，364 对以逐对显式 false-path 继承；四个 CMOS→DDR 对被完整时钟叶节点补集及 mailbox B 替换。没有加入任何同域 false-path，没有恢复全局 asynchronous，也没有 wildcard。

compile 图从真实 CMOS 顶层根网出发，双向穿过已知透明 buffer/inverter，遇未知接收者报错。真实 compile 四路叶节点为 214/214/216/216，扣除各 17 个 mailbox 向量后的补集为 197/197/199/199；旧 src_snapshot、raw debug 和 FIFO 向量均已纳入。synthesis 四路叶节点为 1080/1080/1087/1087。实际物理 mailbox B 共 1320 对，只设置 15.238ns datapath-only max-delay 和 hold false-path。ACK 首级保存 ack Q→ack_sync[0] D、ack_sync[0] Q→ack_sync[1] D 的直接连线证据及精确 CLK→D0 例外；后级同域依旧接受 STA。没有扩大 reset 例外。

未知时钟接收者注入实测已被拒绝，证据为 `fixed_06/physical_exact_11/offline_validation.json`。详细集合、透明边、旧 U 与保留关系为 `coverageproof_offline.json`，保护证据为 `protected_offline.json`。

已授权实际控制器 `run_exact11.py` 在原 audit 75608 和已排队工具查询 51608 自然结束后启动；实际 route03 PDS dev_map 父进程 17980、compile 子进程 52608 已观察到。中文控制日志为 `fixed_06/physical_exact_11/controller.log`。不再启动另一个 PDS；本次实际运行的约束输入已冻结，不可修改。

控制器串行完成 dev_map、新 compile/synthesis 图逐项覆盖复核、PNR、十组 STA、1320 mailbox 双角、HSST、IO、reset 和同步器后级验收。所有失败原始日志保留，不能依据 shell exit0 宣称工具通过。`summarize_exact11.py` 已排队等待本控制器退出后只读复核实际工具 clock interaction 与冻结 connected async pairs，并汇总双角预算和全部门禁。

物理 routed DB 使用 gop primitive 和 `/opit_0` 等物理子实例，不能直接复用 GTP synthesis resolver。`verify_routed11.py` 按每个精确逻辑祖先绑定唯一物理 pin，逐对验证真实 Q→D net，并记录全部 synthesis CMOS 时钟叶节点到 routed 的绑定。若当前已加载的控制器仍执行旧 synthesis resolver，原错误保留在 failure.txt；排队的汇总器会完成正确物理绑定，最终应以 `coverageproof_routed.json` 与 `review_result.json` 判定。控制器磁盘版本已修正为正确物理解析，未修改运行工程。

本文件记录已实施修正和已观察实际启动，尚不宣称 PNR 或时序通过。最终可审阅结果为 `runtime_clockpair_and_budget_proof.json`、`review_result.json`、`acceptance_gates.json`、`coverageproof_compile.json`、`coverageproof_synthesis.json`、`coverageproof_routed.json`；任何未通过同域 setup/recovery 都是仍需修复的真实失败，不能用本次 CDC 修正豁免。

实际更新：Compile/Synthesize/Device Map 全部 done，真实 mapped DB receipt 已落盘；实际工具旧 clockpair 继承通过。首次控制器停止在综合叶节点与旧 exact09 whitelist 的严格比较：每路旧 src_snapshot[64..95] 被完整 compile 约束保留，额外 32 个物理 CLK，并非时钟网遍历遗漏。原 failure.txt 原样保留。`resume_exact11.py` 已增加真实 CDBENTRY 解析，要求每个额外 CLK 恰为对应旧 src_snapshot 位且 CDB HIER 精确回指 compile src_snapshot[95:0]、PINNAME=CLK、文件及行号为本次补集 false-path，随后必须核对 mailbox 仍是原 1320 对；任一失败禁止 PNR。本次约束不改。

首次 resume 被另一会话 map_audit14 PDS 单实例保护阻止，未启动并发构建。已后台等待该父控制器69560自然结束，再执行 resume_exact11，日志 `resume_after_map_audit14.log`。尚不宣称续跑、PNR 或预算通过。

接续更新：resume 控制器59772已进入实际 PNR 请求（父PDS81460），PDS 在该请求中触发 synthesize 子进程76872；不能把请求等同于PNR完成。真实 synthesis CDB 解析已通过：364 个有向 clockpair 均有 SU=1/HD=1，四个 MMD 均 DELAY=15238ps、DATAPATH_ONLY=1，全部 CMOS 非mailbox synthesis CLK 均逐个证实继承精确 compile 补集 CDBENTRY，见 actual_cdb_synthesis_proof.json。

主会话在 audit_fixed.py genbit 前增加 exact11 routed coverage 门禁。运行中控制器加载顺序可能仍为 audit→export，因此已落实独立 `finalize_exact11.py`，后台等待59772自然退出后复核。它先完成 routed 物理绑定、综合和routed CDB全部364关系、1320双角预算，再检查所有已有实际验收 gates；只在全部通过且 audit 唯一错误为新增 coverage 门禁时补做最终 genbit。原失败 receipt 保留。不重开并发PDS，不修改当前运行约束，不修改 timing candidate integration。

最后中文实际报告为 fixed_06/physical_exact_11/FINAL_ACTUAL_RESULT.md；结果为 result.json/review_result.json，完整真实十组counts为 final_ten_sta_counts.json，同域/剩余跨域/未知时钟负路径逐条为 negative_path_classification_exact11.json。finalize_controller.log 是当前后台收尾日志。候选约束可采用与全流程timing通过分开判定，不以例外迁移成功宣称硬件或时序全部通过。

实际PNR已完成：pnr_result.json确认Compile/Synthesize/Device Map/Place & Route全done，利用率49%，routed DB=source_diagnostics_route_03/place_route/v7_sdt_top_pnr.adf，34407390字节，SHA256=b0700dc056eccfb31eeaa66793fd6e13789e03f478670109674f41f2524d1a83。保护1022文件再次实测零漂移。

PNR后的审计入口出现控制器路径bug：audit_fixed import时从cf.OUT追加attempt，原resume已将cf.OUT设为attempt，结果重复追加 physical_exact_11。audit_failure/resume_failure保留该真实失败；没有执行STA或bit。finalize现已修正为audit import前cf.OUT=fixed_06，断言其实际OUT/HERE，然后先补完物理CDB覆盖，再进行全部audit。首次finalize被另一会话mapped_timing15占用PDS挡住；已等待其父23760自然结束，实际继续日志为finalize_correct_path.log。不可再并发启动；STA完成仍以工具通知与真实receipt为准。

按 newtargetfilterauditnotes/HANDOFF.md 实证修正后续入口：exact11 的 audit_fixed 改用当前route哈希对应的 coverageproof_routed 物理 pairs/reset_bindings/sync_bindings。先 single_pair（nworst2/max_path8），逐实际记录确认目标、15.238ns datapath-only、Slow/Fast与零ignored，再四相机各330对完整查询。每个target shell/run.log及report_timing/run.log逐行拒绝Timing-4006、STA-3016、unknown arguments/options；不以exit0放行。全球负路径诊断限制max_path512，十组摘要仍从工具报告读取；详细路径仅为工具返回样本，不冒充全设计枚举。

stream_timing11 从Slack行提交record，corner仅从当前Path Type取，check仅从行首Recovery/Removal/Setup/Hold time取。真实旧reset.snr全读得到32条Slow记录（Recovery16、Removal16），真实旧mailbox run.log识别2642条无效目标警告并拒绝，见stream_parser_real_report_validation.json；这是解析器真实报告复核，绝不是route03时序通过。

route03 routed拓扑证明现为1320对、错误0：两条物理数据连接经gopCLKROUTE，已验证单一M输入、CR输出及INITA/C=0、INITB/D=全1恒等配置；12个旧无同名寄存器逐个遍历全部消费者，证明封闭无顶层/物理可观察输出锥，完整证据在eliminated_sinkless_registers。32个逻辑reset按GTP_DFF_P、ASYNC/LRS_EN/LRS_POL及SET参数和相同reset_any网语义绑定20个物理RS，SRL合并仅接受邻级D/Q直连且同CLK/异步网/类型/INIT。不会机械P->RS。8个同步器内部级打包于gopSRL2，缺外部D查询端口，记录sync_packed_internal并保持sync_later门禁失败，尚不宣称其内部STA通过。

后续串行收尾已等待当前integration构建父57416自然结束，日志finalize_physical_targets.log；不改当前运行FDC，不并行PDS，不修改integrationagent文件。真实1320双角逐对budget覆盖和slack验收仍需实际查询完成；bit保持受coverage与全部实际门禁约束。

最终实际完成：singlepair及四相机full1320/角查询已done，所有target日志ignored/unknown计数0。Slow1320/1320、Fast1320/1320，每对15.238ns datapath-only有效，最差Slack分别+13.507/+14.177ns，全部2640条记录已验收。十组STA仅Slow Setup有4失败（cmos2_pclk同域2、ddrphy_sysclk同域2），Slack=-0.749/-0.167/-0.030/-0.014ns；其余九组失败端点0，返回跨域负路径0。reset双角Recovery/Removal仅12/20实际RS有记录，8个cr[0]/cr[1]缺记录，门禁失败；同步器外部8对双角Setup/Hold完整非负，8个打包内部级仍缺STA证据，门禁失败。HSST/112 IO/1022保护和输入哈希均通过。

audit末段在离线classify前被另一会话PDS busy检查挡住，原audit_failure保留；close_actual11.py只读现有真实报告补齐acceptance_gates/runtime proof/result，未再启动PDS。此前candidate_constraints_can_be_used=true过于宽松，已更正false；clockpair/mailbox迁移证据单列true。最终FINAL_ACTUAL_RESULT.md给出完整counts及rootfail；无bit/remote/program，不可作为最终签核或烧录候选。
