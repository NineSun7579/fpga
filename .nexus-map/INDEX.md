> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: current worktree, PDS project files, implementation reports, root audit notes, and manual inspection; no AST extraction or Git-history statistics

# Embedded Completion Nexus Map

本仓库汇集三个 Pango FPGA 工程，并以根目录文档约束后续整改方式：

- `41_ov7725_hdmi/`：OV7725 采集、DDR3 帧缓存与 HDMI/TMDS 输出；已有实现和位流，但最终时序失败。
- `ddr3_test/`：外层工程目前只是 DDR3 IP 壳；真正完成实现的是 IP 自带 `test_ddr` 示例。
- `pcie_dma_test_100h/`：PCIe x2 DMA 集成顶层；实现和时序通过，但 UART2APB 通道存在未连接顶层端口的功能缺口。

三个工程当前有效器件目标均按 `Logos2 / PG2L100H / FBG484 / -6` 审计。PDS 负责实现，外部 ModelSim/QuestaSim 负责仿真；本机当前未发现 `vsim.exe`，所以本地图只记录静态证据，不声称仿真已运行。

## 当前基线

- Git 分支：`main`。
- Git 基线提交：`1a2d493`（三个原始工程、已有报告和整改文档）。
- 现有 PDS 生成物位于各 GUI 工程目录中，尚未统一隔离到 `build/`。
- PCIe 工程已新增相对路径构建入口，正在以新 `build/` 产物验证。
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

1. 先验证 PCIe 相对路径构建入口，再建立集成仿真并处理 UART2APB 死通道。
2. 明确 DDR3 外层板级顶层，不能把 IP 示例结果当作产品工程结果。
3. 修复 OV7725 工程的真实 CDC、复位释放和负时序。
4. 三个工程统一补齐顶层四级仿真、PNR 功能网表、SDF 与 CI Gate。

## 更新规则

当顶层、器件、IP 边界、时钟域、约束、测试结果或 Git 基线发生变化时，应同步更新本目录。人工推断必须继续标明证据缺口；未执行的工具流程不得记录为通过。
