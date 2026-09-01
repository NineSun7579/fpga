# PCIe S2-D 综合后受限 smoke 契约

更新日期：2026-09-01

## 目标

使用 PDS `2022.2-SP6.4` 生成的 canonical 综合网表
`build/pds/synthesize/pcie_dma_test_syn.vm`，在 Questa Sim-64 `2021.1`
中确认以下最小事实：

- PG2L50H 综合网表能够结合 Logos2 USIM 与 PCIe/HSST 厂商模型完成编译和展开；
- 项目的按键复位 debounce/sync 与 PERST# sync 路径能够释放并再次响应复位；
- 综合后保留的 PCIe link 观察网络能够驱动 reference-clock LED counter 路径。

## 工程留档

可复现仿真工程随 PCIe 项目保存在 `sim/questa/`：

- `post_syn.f`：canonical 综合网表与项目自检 TB 清单；
- `run_post_syn.do`：独立库、厂商模型编译、elaboration 和运行入口；
- `tb/tb_pcie_dma_post_syn.sv`：有界、自检的综合后 testbench。

运行生成的 `work`、`pcie_vendor`、`modelsim.ini`、transcript、日志和波形只写入
`build/`，不作为工程档案提交。Questa 安装位置与许可证配置由仓库外参数或环境提供。

## 通过条件

- `scripts/check_post_syn_sim.ps1` 静态合同通过；
- 综合网表和 TB 编译为 0 errors；
- elaboration 成功加载 USIM 与 PCIe/HSST 厂商模型；
- 仿真在 watchdog 前结束，且日志仅出现一次
  `INFO: POST_SYN_RESET_PATH_OK` 和一次 `TEST PASS`；
- PowerShell 入口返回 0。

当前动态证据为 run `41135fd3fadd4c51a70508a6fa5af3e3`：运行至
`491965 ns`，`Errors: 0, Warnings: 1`，成功标记与 `TEST PASS` 均只出现一次，
PowerShell 退出 0。唯一 warning 是厂商 HSST 受保护模型中的无驱动隐式 wire，
不来自项目 RTL/TB。

## 明确不覆盖

本 smoke 强制控制综合后保留的 link 观察网络，只验证结构和复位/计数路径，因此不证明：

- PCIe LTSSM、真实链路训练、协商宽度或速率；
- Endpoint 主动 DMA、BAR1、MRd/CplD/MWr 数据闭环；
- PNR 后功能、布局布线资源或板级电气；
- SDF 标注、setup/hold/recovery/removal 或任何时序签核；
- RK3568 实板通信或发布条件完成。

后续 PNR 功能和 PNR 时序仿真必须使用各自网表/SDF 与独立合同，不能复用本 smoke
作为通过证据。
