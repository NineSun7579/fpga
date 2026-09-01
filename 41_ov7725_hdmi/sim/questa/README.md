# 摄像头 HDMI Questa 仿真工程

本目录用于归档摄像头 HDMI 产品的项目级 Questa 工程定义。`41_ov7725_hdmi` 当前仅是 OV7725 legacy 基线，产品目标已经校正为 OV5640。

现有 `prj/ipcore/ddr3_ip/sim/modelsim/` 只属于厂商 DDR3 IP 示例资产，不能替代 OV5640 摄像头采集、帧缓存和 HDMI 输出的项目级自检 testbench。完成 C0/C1 范围冻结和 C2/C3 新项目实现后，在本目录加入 OV5640 行为级、综合后、PNR 后功能和 SDF 时序入口。

Questa 安装位置和许可证配置保持在仓库外；`work` 库、transcript、日志和波形写入 `build/`，不提交 Git。
