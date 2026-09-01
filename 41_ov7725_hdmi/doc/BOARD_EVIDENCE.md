# 摄像头 HDMI 板级证据清单（OV7725 legacy / OV5640 目标）

状态：器件目标已审核；现有内容记录 OV7725 legacy，产品目标已校正为 OV5640，待 C0/C1 和 50H IP 审核。更新日期：2026-09-01。

用户已确认本工程最终运行在 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`；PDS 参数统一为 `Logos2 / PG2L50H / FBG484 / -6`。

本文件只记录可追溯的板级输入，不把当前 FDC 或历史工程中的猜测当作硬件事实。现有 `cam_*`、SCCB、寄存器表和 RGB565 参数均只描述 OV7725 legacy；资料闭合前不得用于推定 OV5640，也不得修改 `mem_a` 位宽、DDR3 IP 参数、I/O delay 或 HDMI 时序约束。

## 当前工程事实

| 项目 | 当前建模值 | 证据 | 结论 |
|---|---|---|---|
| 实际 FPGA | `PG2L50H-6IFBG484` | 用户于 2026-08-30 明确确认 | 已审核，待归档一手照片/原理图 |
| 当前 PDS 目标 | 仍为 `Logos2 / PG2L100H / FBG484 / -6` | `README.md`、`scripts/build.tcl` | 与实物不符，必须迁移为 50H |
| legacy 顶层 | `ov7725_hdmi` | `rtl/ov7725_hdmi.v` | 只作为 OV7725 历史事实 |
| legacy 摄像头输入 | `cam_pclk`、`cam_vsync`、`cam_href`、`cam_data[7:0]` | `rtl/ov7725_hdmi.v` | 不得作为 OV5640 接口依据 |
| legacy 摄像头 I/O | `cam_scl`、`cam_sda`、`cam_rst_n`、`cam_sgm_ctrl` | `rtl/ov7725_hdmi.v`、`prj/source/ov7725_hdmi.fdc` | OV5640 的 MCLK/RESET/PWDN/电压/管脚需重新审核 |
| HDMI 输出 | TMDS 时钟及 3 路差分数据 | `rtl/ov7725_hdmi.v`、`prj/source/ov7725_hdmi.fdc` | 需核对连接器和模式 |
| DDR3 数据宽度 | `mem_dq[31:0]`、4 个 DQS/DM | `rtl/ov7725_hdmi.v` | 需核对颗粒组织 |
| DDR3 地址 | 手写顶层/FDC 使用 `mem_a[14:0]`；活动 IP 的 `MEM_ADDR_WIDTH`、`DDR3_MEM_ROW_WIDTH` 和 `MEM_ROW_WIDTH` 均为 14 | `rtl/ov7725_hdmi.v`、`prj/ipcore/ddr3_ip/ddr3_ip.idf:443-445,649-650,1919-1920`、`prj/source/ov7725_hdmi.fdc:462-468` | H3/O1-C 阻断 |
| 活动 IP | DDR3、PLL、读 FIFO、写 FIFO 均由 SP4.2 为 PG2L100H 生成 | `prj/ipcore/*/*.idf` | 四个 IP 均须用 SP6.4 为 PG2L50H 重生成 |
| 历史备份 | `ip_backup/20231227094911` 为 `Logos/PGL25G/MBG324` | `prj/ip_backup/**` | 不是 50H 备份，不可用于迁移 |
| 时钟 | `sys_clk` 20 ns、`cam_pclk` 40 ns；像素时钟由 PLL 产生 | `prj/source/ov7725_hdmi.fdc`、PLL IDF | 需提供实际时钟源与容差 |

## 必须提供的资料

| 证据项 | 用户需提供 | 验收条件 |
|---|---|---|
| 板卡身份 | 板卡/FPGA 已确认；仍需原理图版本、BOM、丝印照片或等价记录 | 每项可回溯到文件版本或照片 |
| OV5640 模组 | 完整料号、单摄或双摄、供电、I/O 电压、MCLK、RESET/PWDN | 与新项目端口、管脚和电平一致 |
| 输入格式 | DVP 位宽、输出格式、字节序、有效位、行/场/像素时钟极性、分辨率和帧率 | 可形成 OV5640 模型和 input delay 依据 |
| HDMI 模式 | 输出分辨率、像素时钟、TMDS 连接器、差分极性和终端 | 与 video timing、TMDS 管脚及电气标准一致 |
| DDR3 颗粒 | 完整料号、数量、容量、rank、x16/x32 组织、目标速率 | 与 32-bit IP 配置和 800 MT/s 建模一致 |
| DDR3 拓扑 | A/BA/CK/DQ/DQS/DM 映射、bit/byte swap、PCB 走线时延、VREF/ODT | 可决定 `mem_a[14]` 分支和 I/O delay |
| 时钟/复位 | `sys_clk`、摄像头时钟、板级复位来源、频率容差和极性 | 可形成可靠的 clock/reset 约束 |
| Bank/Share pin | 摄像头、TMDS、DDR3 所在 bank 电压及复用条件 | 与 FDC/RCF、SCBV 和器件电气规则一致 |

## 关闭条件

1. 所有资料保存到项目文档或外部受控证据库，并记录版本/来源。
2. 当前已确认存在具体冲突：活动 IP 为 14 bit，而手写顶层/FDC 为 15 bit；最终采用哪一侧仍只能由 DDR3 料号和原理图决定，未决定前保持 O1-C 阻断。
3. 四个活动 PG2L100H IP、100H STA/网表/SDF/位流全部不适用于实际板卡；必须建立独立 PG2L50H baseline。
4. DDR3、PLL 和 FIFO 通过 SP6.4 IP Compiler 重生成，禁止手改 IDF 或生成 Verilog；DDR FDC/RCF 必须随实际 DDR 组织和新 IP 重建。
5. C0/C1 未闭合前，不得把 OV7725 SCCB、寄存器表、640x480 RGB565 或 `cam_*` 约束复制为 OV5640 设计依据。
6. 只有 OV5640 与板级证据闭合后，才允许补摄像头 input delay 或进入 C2/C3；任何无法追溯的值都继续作为阻断。
