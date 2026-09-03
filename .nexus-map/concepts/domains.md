# 领域概念

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual refresh after project-boundary cleanup

- **器件目标**：紫光盘古100Pro 上的 `PG2L100H-6IFBG484`，PDS 组合为 `Logos2/PG2L100H/FBG484/-6`。
- **时钟事实**：板载晶振为 25 MHz；DDR3、PCIe 参考时钟和双 OV5640 的 MCLK/PCLK 必须按原理图和模组资料分别确认，不能互相替代。
- **仿真归档**：项目源只进入项目自己的 `sim/questa/`；`work`、ini、日志、波形和库只进入 `build/`。
- **产品摄像头**：唯一摄像头方向为双 OV5640；当前项目尚未导入实现文件。
- **约束状态**：DDR3、PCIe 例外仍需对象解析和板级审核；双 OV5640 尚未创建 canonical FDC。
