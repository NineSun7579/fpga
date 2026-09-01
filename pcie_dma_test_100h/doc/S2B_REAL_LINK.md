# PCIe S2-B 真实 RC/EP 仿真入口

## 1. 目标与边界

S2-B 使用厂商 `pango_pcie_top_sim` 作为仿真 Root Complex，使用项目真实
`pcie_dma_test` 作为 Endpoint。入口用于检查两端 PCIe IP 能否完成 LTSSM
训练并稳定进入 L0。

该入口不代表 RK3568 实板验收，也不证明实际协商为 x2、5.0 GT/s，不覆盖
PCB lane/polarity、AC 耦合、refclk/PERST# 电气或 DMA 数据闭环。H2-B1 板级
资料和严格构建 gate 仍是独立发布闸门。

## 2. 编译架构

仿真使用两个库：

- `pcie_vendor`：10 个厂商加密 DWC 头文件，以及厂商 DO 中保持原始顺序的
  DWC/HSST/GTP 安装模型。
- 每次运行独立的 `work`：50 个审核后的厂商本地 PCIe/RC 源、项目 canonical
  37 个 HDL、真实 EP wrapper 和项目 TB。

`sim/questa/link_vendor_local.f` 从厂商 filelist 派生，但排除厂商 TB、厂商 EP top
和重复 UART/DMA example RTL。厂商文件保持只读，安装路径由
`PANGO_PDS_ROOT` 参数化，不复制模型到仓库。

Pango RAM 仿真模型通过固定顶层层级 `GRS_INST.GRSNET` 解析全局复位，因此
项目 TB 必须将唯一的 `GTP_GRS` 实例命名为 `GRS_INST`。这是厂商模型的
层级契约，不是项目 RTL 的功能接口。

项目源按厂商 PCIe DO 的约定统一使用 `1ns/10ps` 编译时间尺度，避免同一
hard-control 模块在 elaboration 时产生不一致的时间精度。

## 3. 拓扑与通过条件

- 两端共用 100 MHz 差分 refclk。
- RC lane `[1:0]` TX 直连 EP lane `[1:0]` RX，EP TX 反向直连 RC RX；P/N
  不互换。
- `button_rst_n` 在 100 ns 后释放，再等待 10 个 refclk 周期释放 PERST#。
- RC 和 EP 的 `smlh_link_up`、`rdlh_link_up` 均为 1。
- RC 和 EP 的 `smlh_ltssm_state` 均为 `5'h11`，并连续稳定 32 个 refclk
  周期。
- 6 ms watchdog 到期或信号出现未知值均执行 `$fatal`；训练或速率切换中离开 L0 会将连续稳定计数清零。
- 成功日志只允许一个 `INFO: S2B_REAL_LINK_UP` 和一个 `TEST PASS`。

EP link/LTSSM 未由项目顶层导出，TB 当前依赖 `u_dut.smlh_link_up`、
`u_dut.rdlh_link_up` 和 `u_dut.smlh_ltssm_state` 私有层级。项目顶层或 IP
wrapper 变化时必须重新审核该入口。

## 4. 执行与审核

静态门禁不需要仿真器：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_link_sim.ps1
```

动态运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action sim-link
```

审核者必须区分两种状态：

- 静态门禁通过：只证明源清单、拓扑、自检和执行入口满足合同。
- 动态真实链路通过：必须由同一 `SIM_RUN_ID` 的 `sim-link.log` 同时证明
  S2-B marker 与唯一 `TEST PASS`。

Questa Sim-64 `2021.1` 最新 run `30bad6e164be4a4b8284a00f1e96bd87` 已完成厂商
模型与项目 RTL 编译/elaboration。首次 L0 后 RC 进入速率重训练，随后两端
link/LTSSM L0 连续稳定 32 个周期；`702175 ns` 输出唯一成功 marker 和唯一
`TEST PASS`，`Errors: 0, Warnings: 26`，PowerShell 退出 0。

PowerShell 为每次运行在 `build/sim/launcher/<run-id>/` 创建并显式绑定
`modelsim.ini`，通过仅在子进程内存在的 `SIM_PROJECT_ROOT` 返回工程根执行
归档 DO；work、vendor library、日志、transcript 和波形全部保留在 `build/`。
S2-A/S2-B 最新回归后，工程根运行文件计数为 0。

该通过证据不代表 RK3568 实板、实际协商 x2/5.0 GT/s、PCB 电气或 DMA 数据
闭环已经通过；这些边界仍分别由 H2-B1 和 S2-C 验收。
