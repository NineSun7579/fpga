mapping60_01 失败诊断补充（未重跑工具）

dev_map和.switch_db export真实exit0；工具receipt无被拒绝日志行，dmr无原生error。
实际fulltop graph已导出；独立60端点审计在camera0 cr[0]失败：Unique actual Q driver required ... set()。

{"targets": 60, "sync_targets": 28, "reset_targets": 32, "one_actual_cell_targets": 60, "position_only_passed_targets": 60, "exact_types": {"gopQ": 28, "gopLUT6Q_Cell_139": 12, "gopQ_Cell_1": 20}}

这次图中实际类型按精确target层级逐项记录在failed_attempt_exact60_inventory.json；位置绑定只能作为位置诊断，不能替代被拒绝的完整端点语义证明。
生产60状态保持FAIL；不修改原parser/checker，不认未证实类型等价，不改源、不重跑、不PNR/bit/远程/program。
