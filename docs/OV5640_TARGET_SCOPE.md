# OV5640 产品目标与迁移边界

更新日期：2026-09-02

目标开发板：紫光盘古100Pro；目标器件：`PG2L100H-6IFBG484`；PDS：`Logos2 / PG2L100H / FBG484 / -6`。

## 决策


双 OV5640 参考实现现可从以下远端分支只读审核：

```text
origin/parallel_driver@485f3bb
```

已确认该分支包含双 OV5640 RTL、顶层 `top_dual_ov5640_hdmi`、DDR3、HDMI、PCIe 数据路径、约束和 4 个项目级 TB。参考 HDMI 顶层为两路摄像头分别提供独立 SCCB、RESET、PWDN、PCLK/VSYNC/HREF 和 8-bit DVP，按每路 960×1080 半幅输入形成 1920×1080 输出。README 自述双路 RGB565 采集环路及 RGB565→AXI128/BAR2 数据面通过。上述内容尚未选择性导入当前分支，分支自述 PASS 也没有 canonical `.f/.do`、run marker 和日志门禁支撑，不能直接作为本仓库验收结果。

C0 只读审计已经完成，逐文件登记、PDS/IP/FDC 冲突、生成物排除和 VSCS/CDC/RDC 缺口见 [`OV5640_C0_REFERENCE_AUDIT.md`](OV5640_C0_REFERENCE_AUDIT.md)。C1-A 已在 [`59_top_dual_ov5640_hdmi/doc/BOARD_EVIDENCE.md`](../59_top_dual_ov5640_hdmi/doc/BOARD_EVIDENCE.md) 建立产品级证据入口，但没有导入任何 HDL/IP/FDC/TB；板级和产品接口输入冻结后再另开选择性导入批次。

参考分支的根 `prj/project.pds` 与 DDR3 PDS 元数据均为 `PG2L100H / FBG484 / -6`，只有 PCIe IP 元数据为 `PG2L50H / FBG484 / -6`；其工程生成物、STA、SDF 和位流不得直接用于当前产品签核或烧录。参考分支还跟踪了 `sim_*` Questa 编译库和含本机绝对路径的生成文件，这些都不是可移植源码资产。

## 禁止直接继承

- 不整体复制任何未经审核的参考 RTL、IP、FDC、PDS 工程、仿真库或运行产物。
- 不把参考分支的管脚、电压、时钟、分辨率、帧率或时序例外直接当作产品参数。
- 所有进入产品目录的文件必须有来源、用途、依赖和独立验证记录。


## 迁移任务

1. **C0 参考工程只读审计（已完成）**：已在 [`OV5640_C0_REFERENCE_AUDIT.md`](OV5640_C0_REFERENCE_AUDIT.md) 登记全部候选源、IP、约束、顶层、器件元数据、绝对路径、VSCS 和 CDC/RDC 风险；未创建产品目录或导入文件。
2. **C1 产品范围冻结（C1-A 清单已建立，输入未关闭）**：双摄拓扑已经确认；项目 README 与板级证据清单已落入 `59_top_dual_ov5640_hdmi/`。继续审核两只模组料号、每路 MCLK、I/O 电压、实际管脚、DVP 位宽和极性、输出格式、每路 960×1080 与最终 1920×1080 是否为产品要求、帧率和字节序。
3. **C2 项目边界设计**：固定项目目录 `59_top_dual_ov5640_hdmi/` 与顶层，形成双 OV5640 独立 SCCB/寄存器配置、双路读 ID 自检、双路采集/左右半幅拼接、DDR3 帧缓存和 HDMI 输出的源/IP/FDC 迁移方案。
4. **C3 PG2L100H 实现**：所有 IP 在 `Logos2 / PG2L100H / FBG484 / -6` 下重新审核或生成，完成七阶段 PDS 构建和严格 gate；旧 50H 迁移产物和未经复验的历史 100H 产物均不可直接继承。
5. **S3 Questa 验证**：使用已确认的 Questa Sim-64 `2021.1`，把经审核的参考 TB 和新增集成 TB 归档在 `59_top_dual_ov5640_hdmi/sim/questa/`，补相对路径 filelist/DO，依次关闭行为级、综合后、PNR 后功能和 PNR 后时序仿真。所有运行态只写 `59_top_dual_ov5640_hdmi/build/`。

## 仿真与保密门槛

- 公共 Questa、Logos2 USIM/VSIM 和原语 smoke 已通过，不等于 OV5640 项目通过。
- 每级测试必须有 watchdog、失败 `$fatal`、非零失败退出和唯一 `TEST PASS`。
- PNR 后时序仿真必须确认 SDF 真实标注到项目 DUT 层级。
- 不提交参考分支的 `sim_*`、`work`、`.mpf`、`modelsim.ini`、transcript、日志、波形或公共仿真库。
- 仿真器安装目录通过运行参数提供；许可证路径、服务器、feature、内容和许可证文件不得进入 tracked 文件或日志证据。
