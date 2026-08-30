# OV7725 HDMI 板级证据清单

状态：待板级资料与审核。更新日期：2026-08-30。

本文件只记录可追溯的板级输入，不把当前 FDC 或历史工程中的猜测当作硬件事实。资料闭合前不得修改 `mem_a` 位宽、DDR3 IP 参数、I/O delay 或 HDMI 时序约束。

## 当前工程事实

| 项目 | 当前建模值 | 证据 | 结论 |
|---|---|---|---|
| PDS 目标 | `Logos2 / PG2L100H / FBG484 / -6` | `README.md`、`scripts/build.tcl` | 需与 FPGA 丝印核对 |
| 顶层 | `ov7725_hdmi` | `rtl/ov7725_hdmi.v` | 已确认 |
| 摄像头输入 | `cam_pclk`、`cam_vsync`、`cam_href`、`cam_data[7:0]` | `rtl/ov7725_hdmi.v` | 格式/频率待确认 |
| 摄像头 I/O | `cam_scl`、`cam_sda`、`cam_rst_n`、`cam_sgm_ctrl` | `rtl/ov7725_hdmi.v`、`prj/source/ov7725_hdmi.fdc` | 需核对模块电源和电平 |
| HDMI 输出 | TMDS 时钟及 3 路差分数据 | `rtl/ov7725_hdmi.v`、`prj/source/ov7725_hdmi.fdc` | 需核对连接器和模式 |
| DDR3 数据宽度 | `mem_dq[31:0]`、4 个 DQS/DM | `rtl/ov7725_hdmi.v` | 需核对颗粒组织 |
| DDR3 地址 | 手写顶层/FDC 使用 `mem_a[14:0]`；活动 IP 的 `MEM_ADDR_WIDTH`、`DDR3_MEM_ROW_WIDTH` 和 `MEM_ROW_WIDTH` 均为 14 | `rtl/ov7725_hdmi.v`、`prj/ipcore/ddr3_ip/ddr3_ip.idf:443-445,649-650,1919-1920`、`prj/source/ov7725_hdmi.fdc:462-468` | H3/O1-C 阻断 |
| DDR3 IP 生成版本 | 活动 `ddr3_ip.idf` 由 PDS `SP4.2` 生成，当前重建基线为 `SP6.4` | `prj/ipcore/ddr3_ip/ddr3_ip.idf`、项目 README | 需在 IP 重生成审核中确认 |
| 时钟 | `sys_clk` 20 ns、`cam_pclk` 40 ns；像素时钟由 PLL 产生 | `prj/source/ov7725_hdmi.fdc`、PLL IDF | 需提供实际时钟源与容差 |

## 必须提供的资料

| 证据项 | 用户需提供 | 验收条件 |
|---|---|---|
| 板卡身份 | 板卡型号、原理图版本、BOM、FPGA 完整丝印 | 每项可回溯到文件版本或照片 |
| OV7725 模组 | 传感器/模块料号、供电、I/O 电压、晶振来源 | 与 `cam_*` 管脚和 LVCMOS 电平一致 |
| 输入格式 | RGB565 字节序、有效位、行/场极性、分辨率、帧率、`cam_pclk` 范围 | 可形成摄像头模型和 input delay 依据 |
| HDMI 模式 | 输出分辨率、像素时钟、TMDS 连接器、差分极性和终端 | 与 video timing、TMDS 管脚及电气标准一致 |
| DDR3 颗粒 | 完整料号、数量、容量、rank、x16/x32 组织、目标速率 | 与 32-bit IP 配置和 800 MT/s 建模一致 |
| DDR3 拓扑 | A/BA/CK/DQ/DQS/DM 映射、bit/byte swap、PCB 走线时延、VREF/ODT | 可决定 `mem_a[14]` 分支和 I/O delay |
| 时钟/复位 | `sys_clk`、摄像头时钟、板级复位来源、频率容差和极性 | 可形成可靠的 clock/reset 约束 |
| Bank/Share pin | 摄像头、TMDS、DDR3 所在 bank 电压及复用条件 | 与 FDC/RCF、SCBV 和器件电气规则一致 |

## 关闭条件

1. 所有资料保存到项目文档或外部受控证据库，并记录版本/来源。
2. 当前已确认存在具体冲突：活动 IP 为 14 bit，而手写顶层/FDC 为 15 bit；最终采用哪一侧仍只能由 DDR3 料号和原理图决定，未决定前保持 O1-C 阻断。
3. 只有证据闭合后，才允许更新 IDF/FDC、补 `cam_pclk` input delay 或进入 O4 最终时序闭环。
4. 任何无法追溯的管脚、电压、时延或格式值都必须保留为阻断，不能用 baseline 放行替代。
