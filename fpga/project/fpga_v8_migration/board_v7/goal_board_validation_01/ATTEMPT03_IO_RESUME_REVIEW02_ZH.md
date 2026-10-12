# attempt03 定向查询续跑的 IO 结论边界

当前实际进程 resume_attempt03_reports.py 继续采集 reset/sync 报告。其第34–38行写入 evidence/evidence/io_audit.json 的 passed=True、matches_frozen_v7=True，同时明确 bank_report_labels_identical=False 及 bank_label_inconsistency_requires_independent_review=True。其第43行跳过已经失败的 global_reports 行比较。

此续跑可提供有用的定向时序原始证据，但不能关闭当前 IO bank 门禁。保留 LOC、电气字段和 IOB/IOL site 是必要证据，不足以排除内部已用 IO bank 状态异常。原生112行完整比较仍失败；原生prr.db、pinout与封装功能名的矛盾仍未解决。

因此，本次独立审查不接受该 io_audit.json 的 passed=True 为完整 IO 验收，也不依据它生成或烧录该候选。续跑文件及原始失败均保留，不改写正在运行的脚本或证据。生产候选仍需查清内部 bank 状态、原生报告生成机制，并通过独立完整112行验收。

此前取消的是 clock_epoch25 旧1280对预算实验，其 cancelled_for_current_goal01.json 保存取消理由、进程身份、终止回执及部分工件哈希；不是实际 PASS，不替代当前1320对预算证明。
