# Independent mapping experiment

当前恢复入口为 `recover.py` → `recover_mapping.py`，仅恢复 mapping，不重新调用 compile/synthesis。先等待本 map01 已启动恢复入口与全机 PDS/TA 空闲；等待 map01 gate 的 build02 controller 不作为前置依赖。最终以 `evidence/final_result.json` 和 `independent_audit_result.json` 为准。

The active integrated recovery controller was PID 57416; existing dependent finishers were PowerShell PID 38488 (`run_export_fdc17.py`) and PID 52364 (`finalize_exact11.py`). Previously named integrated PID 9432 was no longer present at initial inspection. The queue checks the full lifetime of the named controllers/finishers, plus all PDS/TA processes, rather than starting between tool invocations. This experiment's scripts are not blockers in existing controllers' queue policies.

`evidence/offline_check.json` verifies the byte-preserving primitive source copies, all 43 real bus connections, four distinct module definitions including the existing counter helper, all 60 target instances, five roots, zero timing exceptions, and a balanced isolated project. `evidence/input_hashes.json` stores source/project/constraint hashes. Host period is 7.619 ns; camera periods are 11.905/11.905/20.833/20.833 ns. All 17 output groups connect to top outputs. There are no new attributes or undocumented packing options.

真实执行接口依据本仓库 `physical_subagent_evidence_01/fixed_06/stage_map13/map.tcl` 及同版本 dev_map help：显式加载合成 ADF 与 clock.fdc，执行 `dev_map -force_to_run -input_db_file ... -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0`。不使用无效 open_project；不同时传 -file 与 -project。独立 audit 必须从真实执行日志证明三个整数选项。没有 PNR 或 bitstream 调用。

The 1022-file production/old-IP guard is checked before and after each tool operation. A further 741 stable input files from source_diagnostics_timing_build_01 are frozen for post-check. No existing project, RTL, constraint, IP, controller, or queued follow-up is edited by this experiment.

Actual stage evidence, once completed: `evidence/{compile,synthesis,mapping}_artifact.json` for ADF/native DB identities and SHA256; `*_export_hashes.json` for graph/dump hashes; `*_topology.json` and `*_endpoint_details.json` for real storage and pins. `audit_final.py` re-reads the actual exported graphs with the current calibrated resolver, emits `evidence/final_result.json`, and writes `REPORT.md`. The controller's initial topology snapshots are provisional until this final re-read completes.

Calibration against old real graph evidence: synthesis 60 independent registers (28 sync + 32 reset), PASS; routed graph all 60 logical stages bound, 20 independent registers (12 sync + 8 reset), FAIL. Calibration records have explicit `calibration_old_*` labels and must never be treated as results from this experiment.

Mapping PASS requires 60 distinct actual storage cells with real D/CLK/reset endpoints; explicit GTP RTL alone is insufficient. SRL2 evidence must be reported as FAIL for independence even if its internal stage parameters preserve the RTL function. This small experiment is not routed timing signoff. Any later full integration requires a fresh isolated run and new U-B/mailbox/complement derivation from its actual graphs whenever mapping names change. The original real-model regression remains documented in the candidate directory.

恢复过程保留旧失败及日志于 attempts。另一入口此前因 no-IO 顶层 DRC 改用了 compact stimulus wrapper，并通过项目流程重新生成部分 DB；旧 receipt 与新 DB 的 hash 差异不得静默忽略。当前恢复会保留旧 receipt/export 与当前 DB 副本，依据真实 stage 完成日志重新导出实际 DB，不改写源 RTL。候选两个模块 hash 与最初 primitive 源字节一致，详见 candidate_scope_review.json；包装顶层变化见 compact_stimulus_receipt.json。

未进行远程或烧录。原源文件 GBK 字节保留；中文独立报告写入 REPORT_zh.md（UTF-8）。若实际 packing 不满足 60 独立单元，输出 FAIL 与具体绑定，不放行 gate。最小文档支持的原语实例保护对照方案须与已验证修复区分。
