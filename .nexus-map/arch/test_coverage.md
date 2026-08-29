> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: existing PDS logs/reports, new DDR3 compile-only log, and static audit; no simulator execution in this repository session

# Test Coverage

## 证据等级

- 已验证：当前文件或报告直接证明。
- 静态发现：源码、工程配置或日志可直接观察，但本轮没有重新运行工具。
- 未验证：缺少可执行资产、工具环境或运行记录。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| OV7725 HDMI | 已有综合网表和非零 `.sbit` | 失败：慢角 setup WNS `-7.056 ns`，recovery WNS `-4.857 ns` | 未就绪 | 未就绪 | 未就绪 | 未就绪，无 SDF |
| DDR3 外层 | 临时 `test_ddr` bring-up 顶层的 SP6.4 compile-only 已通过，日志无 `E:`、有 272 条 warning；完整实现未运行 | 仅旧 IP 示例内部通过，不证明新 bring-up 或最终板级工程 | 示例资产失配，未运行 | 未运行 | 未运行、无新网表 | 未运行、无新 SDF |
| PCIe DMA | 新 SP6.4 全流程完成，日志无 `E:`；新网表、SDF、`.sbit/.bin` 非零 | 新最终报告通过：慢角 setup WNS `0.584 ns`、TNS `0`，hold WHS `0.138 ns` | 仅 IP 示例 | 顶层未闭环 | 生成网表但未运行 | SDF 已生成但未标注验证 |

## 已知功能与覆盖缺口

- OV7725：现有实现报告暴露真实 CDC/复位与时序风险，不能以位流存在作为验收结果。
- DDR3：新脚本已能重建临时 `test_ddr` bring-up 的 compile-only 基线，但日志仍有 272 条 warning；该结果不验收 synthesis/PNR/STA/位流、板级参数与约束或功能。testbench 端口失配，且 BIST 无天然有限完成状态，缺少可靠 `$fatal`、超时、`TEST PASS` 和 CI 退出码。
- PCIe：现有 ModelSim 资产只覆盖 PCIe IP 示例，不覆盖 `pcie_dma_test` 集成顶层；UART2APB 的无驱动输入属于已知功能缺陷。
- PCIe 新流程已生成顶层 PNR SDF，但尚未由 QuestaSim 验证实例层级；另外两个项目仍无顶层 SDF。
- 本机未找到 ModelSim/QuestaSim，因此本轮未运行任何仿真。
- PDS 可能在日志含 `E:` 时仍返回退出码 0；新 PowerShell 入口必须同时检查退出码和错误日志。
- PCIe 位流阶段报告 SCBV 未配置，这是当前发布阻断项。

## 统一验收门槛

1. 行为级 testbench 自检通过，失败使用 `$fatal`，成功只输出一个 `TEST PASS`。
2. PDS 各阶段退出码为 0，并对最终时序强制 `WNS >= 0`、`TNS = 0`。
3. 综合后、PNR 后功能和 PNR 后时序仿真均使用集成顶层，而非仅 IP 示例。
4. 时序仿真确认 SDF 实例层级匹配，日志无标注错误和未批准的 timing violation。
5. 最终位流文件存在且大小非零；关键未约束 I/O 必须修复或进入有依据的白名单。
