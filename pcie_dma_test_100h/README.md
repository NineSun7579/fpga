# PCIe DMA 工程

## 当前状态

- 器件：`Logos2 / PG2L100H / FBG484 / -6`
- 顶层：`pcie_dma_test`
- 当前有效输入：37 个用户 RTL、`ipcore/pcie_test/pcie_test.idf`、`fdc/pcie_dma_test.fdc`
- 历史实现内部时序通过，但该结果不能替代新脚本的重建验证。
- UART2APB 当前连接隐式 `rxd/txd`，其中 `rxd` 被编译器绑为 0；硬件接口决策前不修改该功能。
- PCIe IDF 由 PG2L50H 配置生成，与当前 PG2L100H 顶层工程不一致，需重新生成或评审偏离。
- 集成顶层 testbench 和四级仿真尚未完成。
- 新相对路径脚本已完成一次完整 SP6.4 重建：最终 STA WNS `0.584 ns`、TNS `0`，并生成 PNR 仿真网表、SDF、`.sbit` 和 `.bin`。
- 严格发布 gate 当前仍会失败，因为器件不匹配、UART 死通道、未约束端口和未设置 SCBV 尚未关闭。
- H2-A 已完成只读证据收口，详见 [PCIe 板级证据与 IP 目标契约](doc/PCIE_BOARD_EVIDENCE.md)；在板级资料、SCBV、UART 决策和 PG2L100H IP 重生成前，不修改 RTL/IDF/FDC。

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

允许已知问题不代表发布验收通过。

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

## H2-A 只读边界

当前顶层为 `pcie_dma_test`，使用 x2 PCIe lane、差分 `ref_clk_p/n`、`perst_n` 和两枚状态 LED。FDC 已固定 `ref_clk_p/n=F6/E6`、`perst_n=M16`、`button_rst_n=M15`、LED 为 `M17/J16`，但尚未给出 lane 极性/PCB 拓扑、I/O delay 或 SCBV 的板级依据。活动 `pcie_test.idf` 仍标识 `PG2L50H`，而 PDS 目标为 `PG2L100H`；UART2APB 的 `rxd/txd` 仍为隐式网络，`rxd` 被绑为 0。

H2-A 只做证据矩阵和 IP 再生成契约，不修改 RTL、IDF、FDC、RCF 或 gate。完成板级审核后，H2-B 才能用 SP6.4 IP Compiler 重生成 PG2L100H IP 并收紧精确 baseline；任何 lane、refclk、PERST#、UART、SCBV 或器件目标不确定都触发停止。
