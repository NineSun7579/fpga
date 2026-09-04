# PCIe DMA 工程

## 当前状态

- PDS 版本：`2022.2-SP6.4`
- 当前平台：`RK3568_MES2L100H`（FPGA + ARM）；目标器件：`PG2L100H-6IFBG484`；PDS 目标：`Logos2 / PG2L100H / FBG484 / -6`
- RK 手册文件名含 `MES2L50H_100H`，但不改变当前平台选择；50H 资产只作历史错误假设或待迁移参考。
- 顶层：`pcie_dma_test`
- 当前有效输入：37 个用户 RTL、`ipcore/pcie_test/pcie_test.idf`、`fdc/pcie_dma_test.fdc`
- 历史实现内部时序通过，但该结果不能替代新脚本的重建验证。
- UART2APB 当前连接隐式 `rxd/txd`，其中 `rxd` 被编译器绑为 0；硬件接口决策前不修改该功能。
- 当前 PCIe IDF 仍由旧批次按 PG2L50H 生成，与当前 PG2L100H 目标不一致；必须用匹配版本的 SP6.4 IP 重新生成或取得可审计的 100H IP 证据，禁止手改 IDF metadata。
- S2-A 已用 Questa Sim-64 `2021.1` 动态通过：真实 `pcie_dma_test` 顶层配合受控 PCIe 边界模型，覆盖复位链、LED 域、同一 run id 和唯一 `TEST PASS`；该结果不代表真实 LTSSM、DMA 或板级链路通过。
- S2-B 已建立真实 RC/EP 静态入口：厂商 `pango_pcie_top_sim` 对接项目真实 Endpoint，检查两端 link/LTSSM L0 和 32 周期稳定窗口；厂商加密模型的动态链路训练仍待执行。
- 旧批次曾从空 `build/` 以 PG2L50H 完成七阶段重建；这些网表、SDF 和位流均降级为历史证据，不得用于当前 PG2L100H 板卡。
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
不会放行器件 metadata、PG2L50H、负时序、PDS `E:` 或缺失产物。

全部新生成物位于本目录的 `build/` 下，不应提交版本库。
`build/provenance/pds-build.json` 只由 canonical `run.ps1` 维护，不应手工编辑或按“最新时间”挑选证据。

## 仿真命令接口

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

该入口使用唯一 `SIM_RUN_ID` 绑定 `build/logs/sim-behav.log`，并要求日志只出现一次 `TEST PASS`。2026-09-01 的动态运行已通过；elaboration 仍报告项目 RTL 实例 `u_ips2l_pcie_dma` 未连接输出 `o_trgt1_radm_pkt_halt` 的两条 warning，该 RTL hygiene 项留待独立批次处理。详细范围和停止条件见 [S2-A 项目级行为 smoke 契约](doc/S2A_BEHAVIOR_SMOKE.md)。边界模型产生的 link indication 不是 LTSSM、TLP、DMA 或板级链路证据。

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

PowerShell 入口还预留以下后级动作：

- `sim-post-syn`
- `sim-post-pnr-func`
- `sim-post-pnr-timing`

对应三个网表后级 testbench/DO 尚未实现；当前调用会明确失败。基础 DMA 回读属于 S2-C，不会用 S2-A 受控模型或 S2-B link-up 冒充通过。

## 验收条件

- 新构建日志不存在未批准的关键 warning。
- UART 通道被正式接入或完整删除。
- 时序满足 `WNS >= 0`、`TNS = 0`，关键外部未约束端口得到处理。
- PNR 网表和 SDF 成功生成。
- 集成 testbench 四级仿真输出唯一 `TEST PASS`，失败路径返回非零退出码。
- 位流文件存在且非零。

## H2-A/H2-B0 边界

当前顶层为 `pcie_dma_test`，使用 x2 PCIe lane、差分 `ref_clk_p/n`、`perst_n` 和两枚状态 LED。FDC 已固定 `ref_clk_p/n=F6/E6`、`perst_n=M16`、`button_rst_n=M15`、LED 为 `M17/J16`；100H HSSTLP 资源、lane 极性/PCB 拓扑、I/O delay 和 SCBV 仍需按当前器件重新核验。活动 `pcie_test.idf` 仍为旧 `PG2L50H` metadata，UART2APB 的 `rxd/txd` 仍为隐式网络，`rxd` 被绑为 0。

H2-A 只做证据矩阵，不修改 RTL、IDF 或厂商 IP。当前纠偏批次将 build/gate 恢复为 PG2L100H；活动 50H PCIe IDF 在重新生成/核验前保持硬阻断。H2-B0 旧指纹不能直接继承，任何 lane、refclk、PERST#、UART 或 SCBV 不确定仍触发发布停止。
