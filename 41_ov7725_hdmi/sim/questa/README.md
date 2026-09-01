# OV7725 legacy Questa 仿真归档

本目录只用于归档 `41_ov7725_hdmi` 的 OV7725 legacy Questa 工程定义。产品目标已经固定为双 OV5640，新产品工程不会把仿真资产放在本目录。

现有 `prj/ipcore/ddr3_ip/sim/modelsim/` 只属于厂商 DDR3 IP 示例资产，不能替代 OV7725 legacy 或双 OV5640 的项目级自检 testbench。双 OV5640 参考资产选择性导入后，其 `.f`、`.do`、testbench、模型和说明统一归档在 `59_top_dual_ov5640_hdmi/sim/questa/`。

若继续研究 OV7725 legacy，只在本目录归档该 legacy 项目自有 `.f`、`.do`、testbench、仿真模型和说明，不提交 `.mpf`。Questa 安装位置和许可证配置保持在仓库外；`work` 库、`modelsim.ini`、transcript、日志和波形写入本工程 `build/`，不提交 Git。
