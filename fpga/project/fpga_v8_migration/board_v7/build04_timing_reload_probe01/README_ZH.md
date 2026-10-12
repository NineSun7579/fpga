# 独立 timing reload/no-remap 实测 probe01

所有写入只在本目录。没有修改 build04/03/02、final runtime 或另 agent 输入。inputs/device_map 是实际生产 mapADF/native 文件的逐文件 hash-bound 副本，inputs/constraints 是最终 runtime 全新 replacement clock + 五个非 clock FDC 完整副本。copy_manifest.json 记录来源、bytes、SHA256。inputs/diagnostic_only 是已结束的另一 agent 诊断 PNR 的冻结副本，严格只用于加载语义，不能代替生产 mapped graph 身份。

probe.py 每次只创建新 probes/<label>，保留 stdout、rc、失败、工具/script hash、全机进程、互斥记录、输入前后 SHA256 和所有原始产物。采用 Global\\ov56401_PDS_single_instance、WaitForSingleObject(...,0)，全机 PDS/GUI/TA 及现诊断 controller 空闲才启动；mutex 忙立即退出，不持锁等待。queue_short_reports.py / queue_followup.py 只做本地全局短工具调度，等待期间不持 mutex，不检查子 agent 状态，不执行长 PNR。

真实帮助位于 probes/help01/stdout.log 与 probes/ta_help01/stdout.log。官方 Timing Analyzer PDF 已提取到 official_docs/Timing_Analyzer_User_Guide.txt，原 PDF 和 QCH hash 可追溯。官方手册第5/6页明确 TA 仅支持 PNR/PLC/Syn DB，SDC 输入覆盖 DB 内约束；MAP 不在支持列表。实际 MAP report_timing 返回 Flow-0013，要求 PNR phase。未修改 DB phase、未猜测 DB 写接口。

diagnostic_reload02 虽然 rc=0，但官方 Timing-4006 / STA-3016 明确拒绝合成端点，忽略 single-pair 筛选。实际 .rtr 的 Clock Groups 仍包含 cmos1/2/3/4_pclk 全域 asynchronous，完全没有 15.238 或 MaxDelay。因此 add_constraint 登记成功不能证明实际 CDB reload，此探针按失败处理，不能签 PASS。

本目录没有 main_enable，没有执行 compile/synthesis/dev_map/PNR/bit/remote/Flash。若需 replacement clock 诊断 PNR，必须由主会话另起独立执行目录；本任务不会自动执行。当前证据提供 MAP phase 具体限制、现存旧 clock groups 的 native 报告、真实生产 mapped graph/CDB 导出、冻结输入和无前序重跑记录。九项 coverage 的正式结论见 timing_reload_gaps_final.json；所有 verified=false、measured=false、gate_eligible=false。不能解除 timing_reload 门禁。

全部本地队列已完成。mapped_graph01 真正导出了 69,094,576 bytes graph，mapped_native_CDB_raw.txt 是其中完整原始 CDB 字节；仍含四个 cmos_pclk async 和原 DDR MCP 条目。ta_mapped01、ta_diagnostic01/02、ta_commands01 均 rc=1，未执行 inventory，不能把帮助支持 SDC 当实测生效。diagnostic_cdb01 对报告 RTP ADF 的 .switch_db 虽 rc=0，但没有生成要求的 dump 文件；此失败也保留，不当 CDB 证据。protected_binding_check.json 校验最终 runtime 冻结集合 2710 项，drift=0。

最终原始证据索引为 evidence_hashes_final.json；evidence_hashes.json 是先前负证据快照，evidence_hashes_followup.json 是补充完成时快照。不要采用旧索引中工作中或随后编辑的文件哈希。followup_summary.json 保留真实 probe rc 与输出缺失记录。
