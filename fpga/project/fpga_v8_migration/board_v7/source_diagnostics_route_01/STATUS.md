# Route01 物理诊断

最新实际状态：route01 尚无 mapped/routed DB。direct_pnr 启动被全局单实例门槛阻止；进程5372/79684正在运行 source_diagnostics_route_02/standard_flow.pds 的 dev_map/compile。不得与该流程并发启动PDS。route01全部失败保留，物理验收OPEN，未生成bit/未烧录/无remote。

首次 -run pnr 返回0，但综合前置约束检查失败，未进入实际PNR，未产生routed DB。完整失败记录保留 failed_physical_01；正在修正只在实际综合DB阶段加载物理对象约束的启动方式。

28同步/32独立reset实际保护/拓扑审核通过；完整物理验收OPEN，未生成bit/未烧录/无remote。目标仍CAM1根因诊断。
