# 双 OV5640 HDMI 产品工程

状态：C1-A 板级证据入口已建立；C1/H3 仍受外部资料阻断。更新日期：2026-09-02。

本目录是双 OV5640 摄像头 HDMI 产品的唯一活动工程边界。目标开发板为紫光盘古100Pro，实际器件为 `PG2L100H-6IFBG484`，PDS 恢复目标为 `Logos2 / PG2L100H / FBG484 / -6`，工具版本为 `Pango Design Suite 2022.2-SP6.4`；完整 FPGA 丝印、原理图/BOM 仍需归档。

当前目录只归档产品范围和板级证据，不包含 RTL、IP、FDC、PDS 工程、testbench 或可烧录产物。候选顶层名为 `top_dual_ov5640_hdmi`，但在 C1/H3 关闭并完成选择性导入前，它不是本目录中可编译的模块。

## 当前证据入口

- [板级证据清单](doc/BOARD_EVIDENCE.md)：记录已确认事实、参考分支假设、必须提供的资料和关闭条件。
- [产品目标与迁移边界](../docs/OV5640_TARGET_SCOPE.md)：定义 C0/C1/C2/C3/S3 的职责和停止条件。
- [C0 参考工程审计](../docs/OV5640_C0_REFERENCE_AUDIT.md)：记录 `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3` 的逐文件事实与风险。
- [Verilog/SystemVerilog 注释规范](../VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md)：后续所有选择性导入或新增的手写 RTL/TB 必须先按 VSCS 补齐文件职责、接口、时钟/复位、CDC/RDC、FSM 和危险点说明。

## 产品范围

已确定产品使用两只 OV5640。参考设计提供两路独立 SCCB、RESET、PWDN、PCLK/VSYNC/HREF 和 8-bit DVP，并以每路 960×1080 半幅形成 1920×1080 输出；这些只属于待审核参考合同，不是实板事实。

未来产品工程计划覆盖：

1. 两路 OV5640 识别、配置和独立故障报告。
2. 两路 RGB565 采集、帧边界处理和左右半幅拼接。
3. PG2L100H 对应的 DDR3 帧缓存和 HDMI/TMDS 输出。
4. 逐时钟域复位、CDC/RDC、FIFO reset 与丢帧/欠流策略。
5. 项目内 `sim/questa/` 四级自检仿真及项目内 `build/` 运行态。

## 当前构建与仿真状态

- PDS：未建立 canonical `scripts/build.tcl`、`run.ps1` 或 `check_build.ps1`，未执行 compile、综合、PNR、STA、网表、SDF 或位流生成。
- IP/FDC：未导入参考 PG2L100H IP 或 FDC；必须依据紫光盘古100Pro 实板资料重新审核并建立 100H canonical 输入。
- Questa：公共 Questa Sim-64 `2021.1` 与 Logos2 USIM/VSIM 已验证，但本项目尚无 `.f/.do/TB`，因此没有项目级仿真通过证据。
- 实板：未执行摄像头、DDR3 或 HDMI bring-up。

参考分支中的 `PASS:` 文本、混合 PG2L100H/PG2L50H 构建、`sim_*`/`work` 编译库、日志、波形和绝对路径生成物均不得作为本项目证据。

## 停止条件

在 [板级证据清单](doc/BOARD_EVIDENCE.md) 的 C1/H3 输入关闭前：

- 不导入参考 RTL、IP、FDC、PDS 或 TB。
- 不猜测模组料号、MCLK、管脚、电压、DVP 极性、视频模式、DDR3 组织或 I/O delay。
- 不创建虚假的构建入口或用旧 OV7725 工程改名充当产品实现。
- 不提交许可证配置、公共仿真库、运行日志或生成物。
