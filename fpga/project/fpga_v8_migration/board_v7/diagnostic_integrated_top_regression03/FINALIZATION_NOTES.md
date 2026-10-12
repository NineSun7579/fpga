# 收尾门禁记录

首轮真实 run.py 已完成两侧 ModelSim：每侧 TOP_FOUR_RESET_PASS checks=14668、Errors: 0、Warnings: 633。首次收尾因冻结保护输入变化而停止，未标记整体 PASS。

后续仅运行 audit/seal，不重新编译或仿真，不改变黄金、激励、原 monitor 或候选 RTL。所有 trace 使用首次实际仿真的原始输出。冻结门禁保留最初 frozen_before.json，独立记录全部实际变化；唯一观察例外精确限定 source_diagnostics_timing_build_02/STATUS.md。

冻结失败项为 diagnostic_sync_register_map02 下四个 Python 文件（audit_comparison.py、audit_final.py、controller.py、run.py）及 evidence/queue_latest.json。这些变化发生于本回归之外，本子会话未写入这些文件。它们均不属于 regression03 实际编译的 RTL/IP/model 闭包，但仍作为保护输入失败保留，不能扩大状态观察例外、重写初始哈希或宣告整体冻结 PASS。

最终实际 trace counts、哈希、X/Z、绑定、源闭包核验及交付结论以 results.json、freeze_audit.json、audit.json、REPORT_ZH.md 为准。该记录本身不代表最终审计已通过。

实际逐记录比较已完成：comparison.trace 6792条、integrated.trace 8323690条、boolean.trace 14332607条，黄金/候选均完全相同。boolean.trace 全文件的12个X/Z字符均已在开头5000条内定位：首次host采样（日志原始timestamp=5000000），四路diag各1个、四路CDC各2个。initial_unknown_locations.json 保留记录号、组名及原始四态payload；没有过滤未知值。原976项integrated trace存在相同的18397994个X/Z字符，且整体哈希与regression02封存结果一致。
