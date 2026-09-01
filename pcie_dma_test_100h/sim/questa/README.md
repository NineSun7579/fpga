# PCIe Questa 仿真工程

本目录是 PCIe 项目自有的 Questa 工程定义归档，也是动态仿真的唯一脚本来源。

## 已归档入口

- `behav.f`、`run_behav.do`：S2-A 受控行为级 smoke。
- `link.f`、`link_vendor_local.f`、`compile_vendor_link.do`、`run_link.do`：S2-B 厂商 RC 与项目 EP 真实链路入口。
- `dma.f`、`run_dma.do`、`tb/tb_pcie_dma_s2c.sv`：S2-C 诊断入口；当前尚未形成最终 Endpoint 主动 DMA 通过证据。
- 项目自有 testbench 和仿真模型统一保留在 `tb/`；canonical 实现源清单仍位于 `../../scripts/pds_sources.f`，避免维护重复 RTL 清单。

## 运行边界

- 从 `pcie_dma_test_100h` 工程根目录通过 `scripts/run.ps1` 启动，不直接依赖当前工作目录之外的工程路径。
- Questa 安装位置和许可证配置由仓库外参数或环境提供，不写入本目录。
- 版本库只归档 `.f`、`.do`、testbench、仿真模型和本说明，不提交 `.mpf`。
- `work` 库、`modelsim.ini`、transcript、日志和波形写入 `build/`，不作为 Git 归档内容。
- 当前 S2-A 与 S2-B 均已动态通过；S2-B 只证明厂商 RC 与项目 EP 可形成连续 32 周期的双端 link-up/L0，不证明 DMA 或 RK3568 实板链路。
- S2-C 诊断入口已动态通过 RC 主动 BAR0 写入/读回；活动 BAR1 禁用，不能据此声明 Endpoint 主动 DMA 闭环通过。

迁移后的历史验证 run 为 `26db7d3206c542218634caff2c6e71ea`：Questa Sim-64 `2021.1` 编译 0 errors/0 warnings，运行至 `1476105 ns`，唯一 `TEST PASS`，退出码 0。

运行态归档边界复验中，S2-A run `add7efa39f644384af9929e8a9366739` 为 0 errors/0 warnings、`1476105 ns`、唯一 `TEST PASS`、退出 0；S2-B run `30bad6e164be4a4b8284a00f1e96bd87` 在首次速率重训练后取得连续 32 周期稳定窗口，运行至 `702175 ns`，唯一 `INFO: S2B_REAL_LINK_UP`、唯一 `TEST PASS`、`Errors: 0, Warnings: 26`，PowerShell 退出 0。

`scripts/run.ps1` 为每次运行在 `build/sim/launcher/<run-id>/` 创建并显式绑定 `modelsim.ini`，DO 通过进程内 `SIM_PROJECT_ROOT` 定位工程根。两次回归后工程根 `modelsim.ini`、transcript 与波形计数均为 0。

S2-C 归档诊断 run `d1d25d3f23384590918f26abbfd2e839` 运行至 `710535 ns`，唯一 `INFO: S2C_DMA_WRITE_READBACK_OK`、唯一 `TEST PASS`、`Errors: 0, Warnings: 26`，PowerShell 退出 0。运行态仍只写入 `build/`。
