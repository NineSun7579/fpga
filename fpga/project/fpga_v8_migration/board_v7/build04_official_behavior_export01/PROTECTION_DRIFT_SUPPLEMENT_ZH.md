封存后保护核验补充（不得忽略）

protection_final.json 的 unchanged=false 是真实发现：初始快照到封存期间，build04_mailbox_clock_review01/seal_review.py 的 hash 改变，该目录新增 13 项产物。来源未在本子任务中独立归因；所有本任务工具和脚本的写路径均限制于 build04_official_behavior_export01，没有恢复、覆盖或改写该邻接目录。

因此不能宣称整个扩展守护集合全程不变，外部 review03 必须单独核验此漂移。最终 final_result.json 已如实记录 protection_unchanged=false。本轮 native02 自身前后保护检查是 true，说明此导出窗口未观察到额外变化。

原 source_diagnostics_timing_build_04（含 actual mapped ADF 和原 FAIL）、source_diagnostics_timing_build_03、source_diagnostics_timing_build_02、diagnostic_sync_register_map02、build04_mapped_endpoint_review02、build04_route_prepare01 的完整树初始到最终均不变。review02 原 3430 项保护输入再核验均不变。分目录复核见 protection_root_detail.json。

review03_bundle_hashes.json 是第一批封存的 80 项 hash 清单，已逐项复核一致。补充文件由 review03_supplement_hashes.json 单独绑定，不改写已封存清单和结果。
