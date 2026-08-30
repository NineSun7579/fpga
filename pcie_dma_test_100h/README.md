# PCIe DMA 工程

## 当前状态

- PDS 版本：`2022.2-SP6.4`
- 实际器件：`PG2L50H-6IFBG484`；PDS 目标：`Logos2 / PG2L50H / FBG484 / -6`
- 开发板：`RK3568+PG2L50H100H`；三个项目均使用这块实际焊接 PG2L50H 的板卡。
- 顶层：`pcie_dma_test`
- 当前有效输入：37 个用户 RTL、`ipcore/pcie_test/pcie_test.idf`、`fdc/pcie_dma_test.fdc`
- 历史实现内部时序通过，但该结果不能替代新脚本的重建验证。
- UART2APB 当前连接隐式 `rxd/txd`，其中 `rxd` 被编译器绑为 0；硬件接口决策前不修改该功能。
- PCIe IDF 已由 SP6.4 为 PG2L50H 生成，与实际器件一致；需要修正的是旧 PG2L100H 顶层构建目标和 gate，不需要仅为器件型号重生成 IP。
- 集成顶层 testbench 和四级仿真尚未完成。
- 已从空 `build/` 以 PG2L50H 完成 SP6.4 七阶段重建，生成新的网表、SDF 和位流；旧 PG2L100H 结果仍只作为历史证据。
- 严格发布 gate 已验证仍会失败；UART 死通道、未约束端口、lane/refclk/PERST# 和 SCBV 继续阻断发布。
- H2-A 已完成只读证据收口，详见 [PCIe 板级证据与 IP 目标契约](doc/PCIE_BOARD_EVIDENCE.md)。活动 IDF 保持只读；FDC 在原理图资料闭合前不修改。
- H2-B0 已将 baseline 收紧为 [16 个对象签名、42 次原始记录](doc/H2B_BASELINE_GATE.md)；对象新增、消失、改名、换 pin、次数或 IP metadata 漂移均失败。H2-B1 板级闭环仍未完成。

## 构建

检查 PDS 与 QuestaSim 环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action env-check
```

仅执行 compile，用于快速验证源码清单：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action build `
  -RunTo compile
```

执行完整 PDS 流程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action build
```

执行严格产物和时序检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action check-build
```

仅用于确认当前历史基线可复现时，可以显式允许已知问题：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action check-build `
  -AllowKnownBaselineIssues
```

允许已知问题不代表发布验收通过。该模式必须精确匹配
[`doc/H2B_BASELINE_FINGERPRINT.json`](doc/H2B_BASELINE_FINGERPRINT.json)，
不会放行器件 metadata、PG2L100H、负时序、PDS `E:` 或缺失产物。

全部新生成物位于本目录的 `build/` 下，不应提交版本库。

## 仿真命令接口

PowerShell 入口已经预留以下动作：

- `sim-behav`
- `sim-post-syn`
- `sim-post-pnr-func`
- `sim-post-pnr-timing`

对应集成 testbench 和 DO 脚本尚未实现；当前调用会明确失败，不会误用 PCIe IP 自带的示例仿真冒充顶层验证。

## 验收条件

- 新构建日志不存在未批准的关键 warning。
- UART 通道被正式接入或完整删除。
- 时序满足 `WNS >= 0`、`TNS = 0`，关键外部未约束端口得到处理。
- PNR 网表和 SDF 成功生成。
- 集成 testbench 四级仿真输出唯一 `TEST PASS`，失败路径返回非零退出码。
- 位流文件存在且非零。

## H2-A/H2-B0 边界

当前顶层为 `pcie_dma_test`，使用 x2 PCIe lane、差分 `ref_clk_p/n`、`perst_n` 和两枚状态 LED。FDC 已固定 `ref_clk_p/n=F6/E6`、`perst_n=M16`、`button_rst_n=M15`、LED 为 `M17/J16`；PG2L50H HSSTLP 资源已依据 PDS SP6.4 模板固定为 `HSSTLP_292_612`。仍未给出 lane 极性/PCB 拓扑、I/O delay 或 SCBV 的板级依据。活动 `pcie_test.idf`、PDS 目标和新产物均为 `PG2L50H`。UART2APB 的 `rxd/txd` 仍为隐式网络，`rxd` 被绑为 0。

H2-A 只做证据矩阵，不修改 RTL、IDF 或厂商 IP。器件迁移批次已将 build/gate 改为 PG2L50H，并依据 PDS SP6.4 模板更新 HSSTLP 资源坐标后从空 `build/` 重建；活动 SP6.4 PCIe IDF 不因型号再次重生成。H2-B0 只锁定当前失败基线，任何 lane、refclk、PERST#、UART 或 SCBV 不确定仍触发发布停止。
