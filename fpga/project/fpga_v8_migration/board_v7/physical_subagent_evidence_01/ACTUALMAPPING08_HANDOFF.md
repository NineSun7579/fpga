# native08 actualmapping 修复与串行续跑

旧失败仍在 `fixed_06/physical_fixed_native_08/finish_failure.txt`、`new_derive_exact_complement.log`；原脚本和日志另按 SHA256 归档到 `actualmapping_failure_archive/`。没有删除或豁免断言。

本地真实 ADIF / exhaustive LUT manifest 审计通过：四路共 2048 logical bits，无 errors；每路 330 register bits + 182 constant zero bits。旧每路 10 个逻辑位合并到 mailbox/host_bank[240]，现在各自保留为 480、490、494、497、498、502、504、505、508、510，对应 word15 的 0x53464401 十个置位。word7 bit16 (logical240) 同样在快照时写1；旧综合合并这些相同复位、时钟、使能、D输入的状态，新实际综合保留各自的寄存器。`canonical_equivalence.json` 对40个额外物理对逐一验证 primitive type、parameters、default parameters、ports、所有输入连接；canonical 1280 classes 对应真实1320 pairs，所有物理对均必须被约束。

| camera | mailbox DFF old→new | host DFF old→new | host pairs old→new | complement old→new | all launch new |
|---|---|---|---|---|---|
| 0 | 320→330 | 320→330 | 320→330 | 748→750 | 1080 |
| 1 | 320→330 | 320→330 | 320→330 | 748→750 | 1080 |
| 2 | 320→330 | 320→330 | 320→330 | 755→757 | 1087 |
| 3 | 320→330 | 320→330 | 320→330 | 755→757 | 1087 |

每路补集新增 href_d[0]/CLK 与 href_d[1]/CLK，无删减。361/362/362/362 是所有 mailbox 名字开头的 primitive 数量，包含LUT，不能作为 mailbox DFF 数量。源码/input SHA256与 fixed06 相同，mailbox/host primitives attributes 均为空；RTL mailbox/host 没有新增 syn_preserve。这是新约束导入触发重新综合后实际合并/保留的变化，不能归咎于新加的 RTL preserve。clock provenance 与旧记录逐项相同：各自 cmosN_pclk 输入缓冲 → mailbox；DDR GPLL CLKOUT0 → sysclk_bufg → host。

本地 `derive_exact_complement.py` 已用全2048位唯一覆盖、实际全部 host D 集合相等、launch/capture 一对一、mailbox Q 唯一 host D sink、完整时钟遍历、补集/预算集合无交叠且并集等于全部 launch 的验证替换旧固定320假设。unknown clock sinks 继续阻断验收。`audit_actualmapping08.py` 验证上述证据、1022 protected hashes 与全部输入哈希，并只在证据目录生成 staged FDC。它与当前串行构建 `physical_constraints_exact_09/` 的全部6份FDC逐字节相同（`staged_vs_running_constraint_audit.json`）。预算仍是15.238ns、datapath_only与hold-only豁免；没有扩展成全clock false path。

旧成功导出对应 syn DB SHA256 `647fdb604df44521ad48ad7badfd048907e04253ec88806738e85cd2819b05d1`，dump SHA256 `330a5953ab0d9a9aa50720c6f2280506389be0238cffa787f02320976ca62fa4`。manifest/objects都与dump hash一致。当前父会话已开始重建DB，所以历史导出复用仅用于本地拓扑证明，不授权当前PNR；当前构建必须按新DB重新导出并重新等价/补集验证。

父会话在match_epoch09结束后已启动 `resume_exact09.py`，独占 `source_diagnostics_route_02/standard_flow_exact09.pds`。本子代理发现进程后没有再启动PDS，也没有改运行的project/FDC/RTL/DB或resume_exact09/audit_fixed脚本。修改后的 `finish_native08.py` 已后台运行，复用旧导出，跟随现有exact09 controller；不会重复map/export/PNR。阶段、零Timing-4003、真实route artifact hashes和全部1320 pairs的Slow/Fast full coverage仍由真实流水线验收；空报告不能通过。当前门槛以 `physical_exact_09/{dev_map_result,new_syn_validated,pnr_result,pnr_artifact,acceptance_gates}.json` 为准；没有这些收据时不能声称成功。

下一阶段日志是 `fixed_06/physical_exact_09/dev_map.log` → `export_new_syn.log` → `new_derive_exact_complement.log` → `pnr.log` → `target_mailbox.log` 与 `evidence/mailbox_routed_audit.json`。native08 的跟随记录是 `serial_continuation.json`。生产/IP/build01保护未改；没有remote/program。

后台阶段通知已确认真实 PNR 启动：`physical_exact_09/pnr.log` 包含 `Process "Place & Route" started.`。`dev_map_result.json` 的 exit_code=0、errors=[]，Compile/Synthesize/Device Map 均 started/done，synthesis 与 map 有 successfully 标记。`new_syn_validated.json` 记录重 map 后 syn DB SHA256 `d846c51b9dd1834e891e36ad83d861c50bb77e768a6f814cdfa03903911c2a66`，physical_pairs=1320、canonical_pairs=1280、complements=[750,750,757,757]。该新DB已重新导出和验证，未复用历史DB来授权PNR。PNR started 不代表 routed STA 或 full pair coverage 已通过，仍等待真实路由收据与各角覆盖报告；没有放宽门槛。
