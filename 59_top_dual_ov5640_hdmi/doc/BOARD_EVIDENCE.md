# 双 OV5640 HDMI 板级证据清单

状态：C1-A 证据入口已建立；C1/H3 仍受原理图、BOM、模组和时序资料阻断。更新日期：2026-09-02。

本清单只区分“已审核实物事实”“参考设计事实”和“待提供输入”。参考分支、旧 OV7725 工程、历史 FDC 或生成 IP 中的值不能自动升级为实际板卡事实。

## 当前工程事实

| 证据项 | 当前事实 | 证据来源 | 审核状态 |
|---|---|---|---|
| 产品传感器 | 产品固定使用两只 OV5640，不再使用 OV7725 | owner 决策、根 TODO | 已确认传感器数量与型号族；模组完整料号待提供 |
| 开发板 | 紫光盘古100Pro | owner 于 2026-09-02 确认 | 原理图版本和 BOM 待归档 |
| FPGA 目标 | `PG2L100H-6IFBG484`（待丝印/原理图/BOM归档） | owner 目标修订、参考工程 metadata | 后续所有 canonical IP、FDC、网表、SDF 和位流必须一致 |
| PDS 产品目标 | `Logos2 / PG2L100H / FBG484 / -6`，PDS `2022.2-SP6.4` | 当前恢复边界 | 不得混入 50H staging 或旧混合工程产物 |
| 当前项目状态 | 目录只含 README 与本清单；无 RTL、IP、FDC、PDS、TB 或构建入口 | 当前 Git 树 | C1-A 文档型骨架，不构成 compile 或仿真证据 |
| 参考来源 | `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3` | C0 审计 | 只读参考，不整体导入 |
| 参考顶层 | `top_dual_ov5640_hdmi` | 参考分支 `rtl/top_dual_ov5640_hdmi.v` | 仅为候选产品顶层名，尚未导入 |
| 参考双摄接口 | 每路独立 SCCB、RESET、PWDN、PCLK/VSYNC/HREF、8-bit DVP | C0 审计 | 需逐项对照实板原理图和模组手册 |
| 参考图像合同 | 每路 960×1080 半幅，组合为 1920×1080；RGB565 | C0 审计 | 不是已批准产品合同；分辨率、帧率、极性和字节序待确认 |
| 参考视频时序 | 顶层按 1920×1080/2200×1125 建模，内部 `video_driver` 却为 1280×720/1650×750 | C0 审计 | 存在内部冲突，不能据此生成 PLL 或 HDMI 约束 |
| 参考 DDR3 | PG2L100H IP，DDR3 800 MT/s、x32 | C0 审计 | 可作为 100H 候选参考；颗粒、拓扑和参数仍待实板证据确认 |
| 参考 Camera FDC | 假设两路 `cam_pclk=25 MHz`、camera LVCMOS33，无 camera input delay | C0 审计 | 只作管脚候选表；不得直接进入 canonical 工程 |
| 仿真环境 | 公共 Questa Sim-64 `2021.1`、Logos2 USIM/VSIM 已验证 | S0 公共环境证据 | 不等于本项目行为级或后级仿真通过 |
| OV7725 目录 | `41_ov7725_hdmi/` 只保留 legacy 风险和历史证据 | 根 TODO、legacy README | 禁止改名、复制寄存器表或作为产品验收入口 |

## 必须提供的资料

| 证据项 | 必须提供 | 用途与验收条件 |
|---|---|---|
| 板卡版本 | 原理图版本、BOM、PCB 版本和可归档 FPGA 丝印照片或等价一手记录 | 所有管脚、电压、器件和约束必须能追溯到同一硬件版本 |
| 两只 OV5640 模组 | 每只模组完整料号、连接器定义、板载晶振/稳压/上拉情况 | 确认两路接口是否真正对称以及哪些资源位于模组侧 |
| 供电与 I/O 电压 | AVDD/DOVDD/DVDD、DVP/SCCB/MCLK/RESET/PWDN 电平及 FPGA bank VCCIO | 决定 I/O standard、电平兼容性和是否需要电平转换 |
| MCLK/XCLK | 两路来源、频率、容差、是否共享、FPGA 管脚和专用时钟能力 | 决定 PLL、时钟树、generated clock 和复位释放关系 |
| SCCB | 两路 SCL/SDA 管脚、上拉电压/阻值、地址选择、是否共享总线 | 决定独立或共享控制器、仲裁、ACK/超时和双路读 ID 合同 |
| RESET/PWDN | 两路管脚、有效极性、上电默认电平和上电/配置时序 | 决定板级复位序列和可重复初始化策略 |
| DVP | 两路 D[7:0]、PCLK、VSYNC、HREF 管脚与极性、采样边沿 | 形成输入接口、时钟约束和 input delay 的一手依据 |
| 图像格式 | RGB565 字节序、有效位、分辨率、帧率、blanking、裁剪/缩放方式 | 冻结采集模型、帧长度、FIFO 深度和 DDR 布局 |
| 双摄产品策略 | 左右路定义、960×1080 半幅是否保留、帧同步容差、单路失效、不同步帧和丢帧策略 | 冻结拼接、帧切换、错误状态和 testbench 验收条件 |
| DDR3 | 完整料号、颗数、容量、rank、x16/x32、速率、row/column/bank、DQ/DQS/DM 映射与 swap | 为 PG2L50H 重生成 DDR3 IP/FDC/RCF，并决定帧地址布局 |
| DDR3 电气/PCB | VCCIO/VREF、ODT、终端、拓扑和可用走线时延 | 决定 PHY 参数、时序约束和板级签核边界 |
| HDMI/TMDS | 输出模式、分辨率、刷新率、像素时钟、连接器、差分极性、终端和 sink 要求 | 冻结 video timing、PLL、serializer、TMDS 管脚和 output delay |
| Share pin/配置 | 配置 bank 电压、启动模式、SCBV 和 camera/DDR/HDMI share-pin 使用 | 确保 FDC、配置参数和启动流程与实板一致 |

资料可以保存在仓库文档或外部受控证据库；若放在外部，必须在本清单记录文件名、版本、来源、审核人和摘要，不得提交包含密钥、许可证或受限数据的文件。

## 允许范围与停止条件

C1-A 只允许维护本目录的产品范围、证据清单和静态门禁。以下条件未关闭前必须停止 HDL/IP/约束实施：

1. 不从 `origin/parallel_driver` 导入 RTL、生成 IP、FDC、PDS、TB 或运行产物。
2. 不从 `41_ov7725_hdmi/` 继承 `7'h21` SCCB 地址、8 位寄存器地址、640×480 RGB565、管脚或时序假设。
3. 不把参考 FDC 的 LVCMOS33、25 MHz camera clock、dedicated-route override 或 `PAP_IO_UNUSED` 当作批准值。
4. 不为缺失的板级时序虚构 input/output delay、`false_path`、multicycle 或 waiver。
5. 不直接使用参考 PG2L100H DDR3/PLL/FIFO IP、STA、网表、SDF 或位流；须按产品合同逐项审核后纳入 100H canonical 工程。
6. 后续选择性导入的每个手写 RTL/TB 必须先符合 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`，否则不得进入 canonical source manifest。

## 关闭条件

1. “必须提供的资料”逐项记录来源、版本、审核状态和明确结论，没有以参考设计值代替缺失事实。
2. 两路 OV5640 的 MCLK、SCCB、RESET/PWDN、DVP、供电、电压和管脚均与原理图/BOM/模组资料一致。
3. 双摄分辨率、帧率、RGB565 字节序、同步/丢帧/单路失效和左右拼接合同获得 owner 审核。
4. DDR3 颗粒、组织、地址宽度、速率、byte lane、电气和 PCB 拓扑可支持 PG2L100H IP 参数审核。
5. HDMI 模式、像素时钟、TMDS 管脚/极性/电气和外部时序要求已经冻结。
6. 项目 README、根 TODO 和仓库门禁与本清单一致；所有仍未关闭的条目继续显示为阻断。
7. 只有上述条件全部满足，才允许另开 C1-B/C2 选择性导入 PR；建立清单本身不等于 C1/H3 完成。
