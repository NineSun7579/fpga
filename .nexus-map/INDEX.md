> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: current worktree, PDS project files, implementation reports, root audit notes, and manual inspection; no AST extraction or Git-history statistics

# Embedded Completion Nexus Map

本仓库汇集三个 Pango FPGA 工程，并以根目录文档约束后续整改方式：

- `41_ov7725_hdmi/`：OV7725 采集、DDR3 帧缓存与 HDMI/TMDS 输出；已有实现和位流，但最终时序失败。
- `ddr3_test/`：已用厂商 `test_ddr` 临时 bring-up 顶层完成 SP6.4 全流程实现、STA、网表/SDF、位流与构建 gate 验证；严格 gate 仍被板级和 RTL 已知问题阻断，它不是已验收的产品顶层。
- `pcie_dma_test_100h/`：PCIe x2 DMA 集成顶层；实现和时序通过，但 UART2APB 通道存在未连接顶层端口的功能缺口。

三个工程当前有效器件目标均按 `Logos2 / PG2L100H / FBG484 / -6` 审计。PDS 负责实现，外部 ModelSim/QuestaSim 负责仿真；本机当前未发现 `vsim.exe`，所以本地图只记录静态证据，不声称仿真已运行。

## 当前基线

- Git 分支：`main`。
- Git 基线提交：`1a2d493`（三个原始工程、已有报告和整改文档）。
- 原始 PDS 生成物仍位于各 GUI 工程目录中；新增流程统一输出到被忽略的 `build/`。
- PCIe 已完成新 `build/` 全流程、STA、网表/SDF/位流和严格 gate 验证。
- DDR3 已从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，日志无 `E:`；最终报告为 `All Constraints Met`，慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`、recovery `4.578 ns`、removal `0.351 ns`。
- DDR3 已生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`；严格 gate 因 7 类已知阻断返回 1，显式 baseline 放行返回 0 但明确不可发布。日志没有 SCBV 命中，板级批准参数清单仍缺失，功能与四级仿真仍未验收。
- 根目录 [README](../README.md) 是 PDS 外部实现与仿真指南。
- 根目录 [TODO](../TODO.md) 是当前整改顺序和验收门槛。
- 新增或修改 Verilog/SystemVerilog 时必须遵循 [VSCS](../VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md)。

## 先读路由

进行工程修改前，按任务读取：

- [系统边界](arch/systems.md)
- [依赖关系](arch/dependencies.md)
- [测试与时序证据](arch/test_coverage.md)
- [领域概念](concepts/domains.md)
- [Git 基线与高关注区](hotspots/git_forensics.md)
- [机器可读概念模型](concepts/concept_model.json)

## 当前优先级

1. 为 OV7725 建立 CDC/RDC 清单和 SP6.4 可重建基线，再分批修复复位与业务 CDC。
2. 评审 DDR3 有限自检契约；板级批准参数到位后再关闭 BIST、share pin、VCCIO、UART 和 I/O timing 等严格 gate 阻断。
3. PCIe 等待板级资料关闭 IDF、UART、share pin、HSST 约束和 SCBV 阻断项。
4. QuestaSim 可用后，三个工程分别补齐集成顶层四级仿真和 SDF 标注验证。

## 更新规则

当顶层、器件、IP 边界、时钟域、约束、测试结果或 Git 基线发生变化时，应同步更新本目录。人工推断必须继续标明证据缺口；未执行的工具流程不得记录为通过。
