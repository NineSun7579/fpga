# PCIe Questa 仿真工程

本目录是 PCIe 项目自有的 Questa 工程定义归档，也是动态仿真的唯一脚本来源。

## 已归档入口

- `behav.f`、`run_behav.do`：S2-A 受控行为级 smoke。
- `link.f`、`link_vendor_local.f`、`compile_vendor_link.do`、`run_link.do`：S2-B 厂商 RC 与项目 EP 真实链路入口。
- 项目 testbench 保留在 `../../tb/`，canonical 实现源清单保留在 `../../scripts/pds_sources.f`，避免维护重复 RTL 清单。

## 运行边界

- 从 `pcie_dma_test_100h` 工程根目录通过 `scripts/run.ps1` 启动，不直接依赖当前工作目录之外的工程路径。
- Questa 安装位置和许可证配置由仓库外参数或环境提供，不写入本目录。
- `work` 库、transcript、日志和波形写入 `build/`，不作为 Git 归档内容。
- 当前 S2-A 已动态通过；S2-B 仍只有静态入口，不能据此声明真实链路或 DMA 通过。

迁移后的当前验证 run 为 `26db7d3206c542218634caff2c6e71ea`：Questa Sim-64 `2021.1` 编译 0 errors/0 warnings，运行至 `1476105 ns`，唯一 `TEST PASS`，退出码 0。
