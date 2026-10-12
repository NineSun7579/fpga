evidence_hashes.json / probe_failure_audit.json / timing_reload_gaps.json 是已完成 help01、mapped_reload01、ta_help01、ta_mapped01、ta_diagnostic01、diagnostic_reload01（mutex busy，未启动）、diagnostic_reload02 的负证据快照，不是物理门禁 PASS。

queue_followup.py 的 ta_diagnostic02 与 mapped_graph01 在本地全局调度下补充运行；这两个目录若在快照索引中仍正在生成，不能把快照里的工作中日志哈希作为最终绑定。补充完成后另写 evidence_hashes_followup.json / followup_summary.json，不覆盖上述失败或快照。正式门禁九项全为 verified=false，measured=false，gate_eligible=false。
