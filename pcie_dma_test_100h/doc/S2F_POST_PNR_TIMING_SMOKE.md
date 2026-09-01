# PCIe S2-F PNR 后时序 smoke 阻断报告

更新日期：2026-09-01

## 状态与结论

S2-F 的项目内 Questa 工程入口已经形成，slow-corner SDF 也已成功标注到真实
`pcie_dma_test` DUT；但当前动态运行存在两个自然复现的正 setup/hold error，且
Pango `V_FFASYN` 模型不能完整表达负 timing check 语义。因此 S2-F 仍为阻断状态，
不得勾选为通过。

```text
Status: blocked
```

准确结论是：

> GLS 与 STA 冲突，且负时序模型语义不完整；既不能宣称仿真通过，也不能据此断言
> 硅上时序失败。

## 工程归档与输入

版本库只保存以下可复现工程源：

```text
sim/questa/
├─ post_pnr_timing.f
├─ run_post_pnr_timing.do
└─ tb/
   └─ tb_pcie_dma_post_pnr_timing.sv
```

静态合同位于 `scripts/check_post_pnr_timing_sim.ps1`，独立启动器为
`scripts/run_post_pnr_timing_sim.ps1`。运行库、`modelsim.ini`、transcript、
日志、波形、网表和 SDF 仍只位于项目 `build/`，不进入 Git。Questa 安装位置与
许可证配置始终作为仓库外输入；`-QuestaBin` 可指向安装根或其 `win64` 目录。

本批没有修改 RTL、活动 IP、FDC 或 PDS provenance，也没有重跑 PDS。使用的
canonical PDS run 为 `9952da4164f040d5924a558baa5cd8ca`，manifest 状态为
`complete/valid`，包含 43 项输入和 9 项产物。时序输入固定为
`build/pds/generate_netlist/pcie_dma_test_sim.v` 和同目录的
`pcie_dma_test_sta.sdf`；网表拥有唯一的内嵌相对路径 SDF 标注请求。

S2-F 使用独立 PowerShell 启动器，是为了让仿真入口和日志规则的修改不改变
canonical PDS 输入 `scripts/run.ps1`。当前 baseline provenance gate 仍返回 0，
无需为本批仿真归档重跑 PDS。

## 动态证据

Questa Sim-64 `2021.1` run：

```text
7fc77a7ec8db479db7332e8037426d6c
```

仓库外运行日志位于 `build/logs/sim-post-pnr-timing.log`。可审核结果为：

- `SDF Backannotation Successfully Completed` 恰好出现一次；
- 项目 reset 路径释放，且 TB 后续输出了功能 marker 和唯一 `TEST PASS`；
- simulator 终态为 `Errors: 2, Warnings: 1591, Suppressed Warnings: 340`；
- PowerShell 入口汇总五类失败并返回 1，正确拒绝了该次运行。

两个 error 在 testbench 不使用任何设计信号 `force/release` 时自然复现：

```text
Setup:
instance CLMA_267_624/FF0/FF
D posedge 492657518 ps
CK posedge 492657521 ps
required setup 97 ps

Hold:
instance CLMA_267_612/FF0/FF
CK posedge 492657524 ps
D negedge 492657548 ps
required hold 25 ps
```

网表注释将两者映射到 HSST reset debounce 路径：

```text
u_ips2l_pcie_wrap/.../hsst_pciex4_rst/ext_rstn_debounce
```

其中 setup error 对应 `cnt_rst[5]`，hold error 对应 `rstn_sync`。两者发生于自然
状态转换，不是 TB 强制链路状态或局部 mapped net 造成的伪事件。

`TEST PASS` 只表示 TB 自身功能断言走到成功路径，不能覆盖 simulator 已累计的
两个 error。S2-F 的接受条件由启动器、日志门禁和 simulator 退出码共同决定。

## Pango timing model 边界

PDS `2022.2-SP6.4` 提供的 `V_FFASYN`：

- 功能逻辑直接采样原始 `CK`、`D`；
- `$setuphold` 与 `$recrem` 均只有四个实参；
- 没有 delayed reference/data、notifier 或 delayed copy。

本次运行记录 1 条 `vsim-8756` 和 1590 条 `vsim-3004`。Questa 因无法求解模型中的
负 timing limit 而把相关负限制清零，说明负 timing check 覆盖不完整。当前 DO 保留：

```text
+delayed_timing_checks
+ntc_warn
-glsnegtchk level2
```

禁止通过 `+notimingchecks`、`+no_notifier`、`+nospecify`、`+no_neg_tchk` 或
`-glsnegtchk level3` 隐藏问题。上述模型缺陷不能豁免本次两个正 setup/hold error。

## STA 对照

同一 canonical PDS run 的 slow-corner STA 没有失败 endpoint：

| Clock | Setup WNS | Setup TNS | Hold WHS | Hold THS |
|---|---:|---:|---:|---:|
| `pclk` | 0.273 ns | 0 | 0.299 ns | 0 |
| `pclk_div2` | 0.606 ns | 0 | 0.145 ns | 0 |
| `ref_clk` | 5.655 ns | 0 | 0.165 ns | 0 |

因此当前证据只能证明 GLS 与 STA 对该 HSST reset debounce 转换给出冲突结果。不能
在缺少器件厂商确认或修正模型的情况下，将 GLS error 写成硅上失败；同样不能用 STA
全正裕量把 GLS error 当作可忽略 warning。

## 关闭条件

S2-F 只有同时满足以下条件才可勾选：

1. 使用厂商确认与当前 PDS/器件/Questa 组合兼容的 timing model，或取得可审核的
   模型修复/解释；
2. 用相同 canonical timing netlist、slow-corner SDF 和无 force TB 重新运行；
3. SDF 标注成功且层级匹配，simulator 为 0 errors；
4. 不出现未解决的 `vsim-8756`、`vsim-3004` 或其他 timing-model 退化；
5. 日志只有一个 run marker、一个功能 marker 和一个 `TEST PASS`，PowerShell 返回 0；
6. 任何 GLS/STA 差异均形成精确到模型、实例、检查类型和厂商依据的审核结论。

本阻断不关闭 PCIe link、Endpoint 主动 DMA、H2-B1、RK3568 实板或发布 gate。
