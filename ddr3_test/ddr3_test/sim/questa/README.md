# DDR3 Questa 仿真工程

本目录用于归档 DDR3 项目自有的 Questa 工程定义。当前尚未建立项目集成顶层的行为级、综合后、PNR 后功能或 SDF 时序入口。

现有 `ip_core/ddr3/sim/modelsim/` 只属于厂商 DDR3 IP 示例资产，不能替代 `ddr3_test_top` 的项目级自检 testbench。后续 D3-A/D3-B/D3-C 与 PG2L50H canonical 升格完成后，在本目录加入项目 `.f`、`.do` 和脱敏验证摘要。

后续只在本目录归档项目自有 `.f`、`.do`、testbench、仿真模型和说明，不提交 `.mpf`。Questa 安装位置和许可证配置保持在仓库外；`work` 库、`modelsim.ini`、transcript、日志和波形写入本工程 `build/`，不提交 Git。
