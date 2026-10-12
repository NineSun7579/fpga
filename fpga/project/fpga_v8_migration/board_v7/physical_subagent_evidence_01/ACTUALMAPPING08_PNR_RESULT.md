# 真实 PNR 收据与未完成验收

`fixed_06/physical_exact_09/pnr_result.json` 确认 Compile/Synthesize/Device Map/Place & Route 均 started/done，placed and routed successfully，exit_code=0，errors=[]（包括无 Timing-4003）。路由DB SHA256 `4b19b478080da9b5306b5c8c4875387c80697b7059efd427ad8cfd0a1c7c0ee7` 已再次对实际 `source_diagnostics_route_02/place_route/v7_sdt_top_pnr.adf` 文件验证一致。

验收尚未完成：exact09 controller 的 `failure.txt` 为 `Acceptance gates open; no bit`；`acceptance_gates.json` 和 `evidence/mailbox_routed_audit.json` 均未生成。最终导出已有真实全角 STA 报告，Slow Setup 1486 failing endpoints、Slow Recovery 132 failing endpoints。这些数字不等于 mailbox target 结果，不能把缺失的1320对Slow/Fast覆盖报告解释为通过。不得生成/放行bit或放宽空报告、全对覆盖、zero Timing-4003门槛。

actualmapping旧320数量阻挡已修复并已实际继续、完成PNR；接下来父会话需要定位audit_fixed/raw_gate_reuse中断并补齐routed mailbox/reset/sync与IO/HSST验收。旧native08 failure及exact09 failure均保留，本子代理未修改运行工程或并发启动PDS。完整数量与结构证明见ACTUALMAPPING08_HANDOFF.md及actualmapping_local_audit.json。
