> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: existing PDS logs/reports, new DDR3 full-build log, timing report, artifact gate runs, and static audit; no simulator execution in this repository session

# Test Coverage

## 证据等级

- 已验证：当前文件或报告直接证明。
- 静态发现：源码、工程配置或日志可直接观察，但本轮没有重新运行工具。
- 未验证：缺少可执行资产、工具环境或运行记录。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| OV7725 HDMI | 历史工程已有综合网表和非零 `.sbit`；O0-A CDC/RDC 静态审计已完成，O0-B SP6.4 重建待执行 | 失败：裸 `rd_load` CDC WNS `-7.056 ns`，read FIFO 指针路径 WNS `-2.279 ns`，`ddr3_init_done` 到 pixel reset recovery WNS `-4.857 ns` | 未就绪 | 未就绪 | 未就绪 | 未就绪，无 SDF |
| DDR3 外层 | 从空 `build/` 完成 SP6.4 七阶段全流程，日志无 `E:`；综合网表 `5,914,586`、PNR 网表 `9,734,239`、SDF `9,130,393`、`.sbit` `3,791,112`、`.bin` `3,789,476` 字节 | `All Constraints Met`；慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`、recovery `4.578 ns`、removal `0.351 ns` | 示例资产失配，未运行 | 综合网表已生成，未运行 | PNR 网表已生成，未运行 | SDF 已生成，未标注验证 |
| PCIe DMA | 新 SP6.4 全流程完成，日志无 `E:`；新网表、SDF、`.sbit/.bin` 非零 | 新最终报告通过：慢角 setup WNS `0.584 ns`、TNS `0`，hold WHS `0.138 ns` | 仅 IP 示例 | 顶层未闭环 | 生成网表但未运行 | SDF 已生成但未标注验证 |

## 已知功能与覆盖缺口

- OV7725：`41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md` 已记录七类时钟域、`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和分侧复位风险，以及三条旧 STA 失败路径。
- OV7725：整改顺序是逐域复位、单点事件同步、FIFO 分侧复位，再对结构已验证的厂商路径添加精确例外；O0-B SP6.4 构建基线是下一步。现有位流不能作为验收结果。
- DDR3：临时 `test_ddr` bring-up 已完成全流程与内部 STA/产物基线。严格 gate 因 7 类问题返回 1：BIST error-data 位宽不匹配、BIST dangling cleanup、`rst_board` 使用 share pin、BANKR4 VCCIO 3.3 不兼容、UART I/O 约束缺失、顶层输入 timing 缺失、顶层输出 timing 缺失。显式 baseline 放行返回 0，但明确标记不可发布。
- DDR3：本次完整构建日志没有 SCBV 命中；这不替代板级批准参数清单。DDR3 颗粒/组织、VCCIO/VREF、ODT、拓扑、走线、UART/ADC 决策等仍缺少审核依据。
- DDR3：testbench 端口仍失配，BIST 无天然有限完成状态，缺少可靠 `$fatal`、超时、唯一 `TEST PASS` 和四级仿真证据；当前结果只验收可重复实现基线，不验收板级功能或产品状态。
- PCIe：现有 ModelSim 资产只覆盖 PCIe IP 示例，不覆盖 `pcie_dma_test` 集成顶层；UART2APB 的无驱动输入属于已知功能缺陷。
- PCIe 与 DDR3 新流程均已生成顶层 PNR SDF，但尚未由 QuestaSim 验证实例层级；OV7725 仍无顶层 SDF。
- 本机未找到 ModelSim/QuestaSim，因此本轮未运行任何仿真。
- PDS 可能在日志含 `E:` 时仍返回退出码 0；新 PowerShell 入口必须同时检查退出码和错误日志。
- PCIe 位流阶段报告 SCBV 未配置，这是当前发布阻断项。

## 统一验收门槛

1. 行为级 testbench 自检通过，失败使用 `$fatal`，成功只输出一个 `TEST PASS`。
2. PDS 各阶段退出码为 0，并对最终时序强制 `WNS >= 0`、`TNS = 0`。
3. 综合后、PNR 后功能和 PNR 后时序仿真均使用集成顶层，而非仅 IP 示例。
4. 时序仿真确认 SDF 实例层级匹配，日志无标注错误和未批准的 timing violation。
5. 最终位流文件存在且大小非零；关键未约束 I/O 必须修复或进入有依据的白名单。
