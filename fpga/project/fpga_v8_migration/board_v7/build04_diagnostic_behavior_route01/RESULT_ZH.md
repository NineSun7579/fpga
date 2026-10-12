# Diagnostic PNR / official behavior export 结果

仅新建 build04_diagnostic_behavior_route01。PNR / gen_netlist / switch_db 均实际退出 0；官方 PNR 和 Generate Netlist 均 done。原 build04/03/02、review02、export01 固定输入保护检查见 protection_after_all.json；新增并发文件不参与假冲突判定。

实际 PNR PID 60168；功能导出 PID 40812；图导出 PID 65580。最终 route 为 work/place_route/v7_sdt_top_pnr.adf，原生 prr.db / .prr / logs 和 PLC ADF 全部保留。官方功能网表 functional/generate_netlist/v7_sdt_top_sim.v 为真实 V_* 网表，完整官方模型库编译通过。全部模型及 UDP 依赖 hashes、选择记录和 ModelSim 契约见 official_library_binding.json、official_library_hashes_after.json 与 *_contract.json。

60 storage / 60 site / 60 V_FFASYN 精确绑定见 official_model_binding60_refined.json。32 个 reset storage 的 SR 锥均通过 16 组合边界真值表。60 clock identity、逐级 D/reset-release 契约见 stage_and_boundary_contract_evidence.json。PNR 改动包含 12 个 _L6Q_perm 重命名与 INIT 输入位重排、11 个 RSMUX_SEL LOCAL→CHAIN（包含 3 个重命名 storage）；完整 mapped→routed cell+site / endpoint / alias 差异见 mapped_routed_endpoint_delta60.json。不能把 route 冒称 MAP 同图。

仍阻断：19 行 SR 物理网与 graph alias 的独立确认；上游 reset 边界 GTP→packed L5Q/L6Q/inv 变换语义审查；STA 的 setup/hold/removal 负 slack；IO 最终 bank/electrical 与 timing/reload 验收。逐条交接见 independent_review_handoff.json。原始 STA 摘要和 hold-fix 日志数值可能不同，均原样保存，不以较好值覆盖。工具 raw/native PNR fatal/unknown/unresolved/Timing-4006/STA-3016 检出为 0。

首次控制器把 PLC 与 PNR ADF 同计为两个候选而误停；failure.json 原样保留。continue_export.py 只选择明确最终 _pnr.adf 并执行 gen_netlist / switch_db，无 PNR 或 compile/synth/dev_map 重跑。初轮分析的严格同名拒绝及后续精确修正证据均保留。

source741 / registration186 / full copy ledger / copyhash before+after / submitted tool script hashes / protection after / raw logs / native receipts 齐全。本结果仅模型诊断，不作最终 timing/reload 验收；未执行 bit、remote 或 Flash。
