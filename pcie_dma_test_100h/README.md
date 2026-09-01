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
- S2-A 已用 Questa Sim-64 `2021.1` 动态通过：真实 `pcie_dma_test` 顶层配合受控 PCIe 边界模型，覆盖复位链、LED 域、同一 run id 和唯一 `TEST PASS`；该结果不代表真实 LTSSM、DMA 或板级链路通过。
- S2-B 已用厂商 `pango_pcie_top_sim` RC 对接项目真实 Endpoint 动态通过：首次速率重训练后，两端 link/LTSSM L0 连续稳定 32 个周期；该结果仍不覆盖 DMA 或板级链路。
- S2-C 项目内归档诊断入口已用 Questa `2021.1` 完成 RC 主动访问 EP BAR0 的写入/读回；活动 BAR1 仍禁用，因此该结果不是 Endpoint 主动 DMA 闭环证据。
- 已从空 `build/` 以 PG2L50H 完成 SP6.4 七阶段重建，生成新的网表、SDF 和位流；旧 PG2L100H 结果仍只作为历史证据。
- 严格发布 gate 已验证仍会失败；UART 死通道、未约束端口、lane/refclk/PERST# 和 SCBV 继续阻断发布。
- H2-A 已完成只读证据收口，详见 [PCIe 板级证据与 IP 目标契约](doc/PCIE_BOARD_EVIDENCE.md)。活动 IDF 保持只读；FDC 在原理图资料闭合前不修改。
- H2-B0 已将 baseline 收紧为 [16 个对象签名、42 次原始记录](doc/H2B_BASELINE_GATE.md)；对象新增、消失、改名、换 pin、次数或 IP metadata 漂移均失败。H2-B1 板级闭环仍未完成。
- CI-8A 已完成 [单次 PDS 构建证据绑定](doc/CI8A_BUILD_PROVENANCE.md)：43 项 canonical 输入和 7 项最终证据由同一 `run_id` 与 SHA-256 manifest 绑定；partial/failed run 不再复用旧 full-build 产物。

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

该命令成功后 manifest 状态为 `partial`，因此 `check-build` 会返回非零；要重新获得可验收的 complete manifest，必须执行完整流程。

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
`build/provenance/pds-build.json` 只由 canonical `run.ps1` 维护，不应手工编辑或按“最新时间”挑选证据。

## 仿真命令接口

项目自有 Questa 工程定义集中归档在 [`sim/questa/`](sim/questa/README.md)。该目录保存可复现的 `.f/.do/TB` 和边界说明；运行生成的 `work`、`modelsim.ini`、日志、transcript 与波形仍位于 `build/`，不提交 `.mpf` 或运行态文件。

S2-A 静态契约检查不依赖仿真器：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_sim.ps1
```

QuestaSim 和 Logos2 USIM 就绪后，执行项目级行为 smoke：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action sim-behav `
  -QuestaBin '<Questa-win64-directory>'
```

该入口使用唯一 `SIM_RUN_ID` 绑定 `build/logs/sim-behav.log`，并要求日志只出现一次 `TEST PASS`。S2-A RTL hygiene 已将 `u_ips2l_pcie_dma.o_trgt1_radm_pkt_halt` 贯通到活动 `pcie_test` wrapper 的 hard-IP RX halt 输入，不再将 DMA tag/full 与 completion-ready 流控固定为 no-halt。该 wrapper 是生成资产，IP 重生成后必须通过静态 gate 重新确认接口。详细范围和停止条件见 [S2-A 项目级行为 smoke 契约](doc/S2A_BEHAVIOR_SMOKE.md)。边界模型产生的 link indication 不是 LTSSM、TLP、DMA 或板级链路证据。

S2-B 静态合同检查：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_link_sim.ps1
```

执行真实 RC/EP 链路训练：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action sim-link `
  -QuestaBin '<Questa-win64-directory>'
```

该入口使用参数化 PDS 安装根读取厂商加密模型，独立 `pcie_vendor`/`work` 库和唯一 `SIM_RUN_ID`。动态成功必须同时出现一次 `INFO: S2B_REAL_LINK_UP` 与一次 `TEST PASS`。详细审核边界见 [S2-B 真实 RC/EP 仿真入口](doc/S2B_REAL_LINK.md)。它不证明 RK3568 实板链路、x2/5.0 GT/s、PCB 电气或 DMA 数据闭环。

当前动态 run `30bad6e164be4a4b8284a00f1e96bd87` 在 `702175 ns` 输出唯一成功 marker 和唯一 `TEST PASS`，`Errors: 0, Warnings: 26`，PowerShell 退出 0。26 条 warning 来自厂商/生成模型端口与受保护模型，不应改写为零 warning。启动器在 `build/sim/launcher/<run-id>/` 创建并显式绑定 `modelsim.ini`；工程根不产生 ini、transcript 或波形。

S2-C 归档诊断 run `d1d25d3f23384590918f26abbfd2e839` 在 `710535 ns` 输出唯一 `INFO: S2C_DMA_WRITE_READBACK_OK` 和唯一 `TEST PASS`，`Errors: 0, Warnings: 26`，PowerShell 退出 0。该 TB 由 RC 主动访问 EP BAR0，只证明当前诊断路径可运行；Endpoint 主动 MRd/CplD/MWr 闭环继续等待 BAR1 staging 输入闭合。

PowerShell 入口还预留以下后级动作：

- `sim-post-syn`
- `sim-post-pnr-func`
- `sim-post-pnr-timing`

对应三个网表后级 testbench/DO 尚未实现；当前调用会明确失败。基础 DMA 回读属于 S2-C，不会用 S2-A 受控模型或 S2-B link-up 冒充通过。BAR1 staging 还需要同版本完整 IP Compiler 实例导出的 `index.xml`，取得前不覆盖 canonical IP。

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
