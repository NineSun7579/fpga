# main OV5640→DDR3→PCIe 板级输入资料清单

更新日期：2026-09-04

## 目的

当前 RTL 已完成从 OV5640 DVP 激励、灰度处理、双槽帧管理到 PG2L50H canonical DDR3 AW/W、AR/R
用户口，并通过 `core_clk`→`pclk_div2` 异步 mailbox/仲裁进入 PCIe MWR TX 的应用边界闭环。以下资料用于把明文 canonical 用户口模型和 opaque 地址替换为
`PG2L50H-6IFBG484` 板上的真实 DDR3、PCIe 和 RK3568 主机接口；资料未关闭前，不得把模型回归
解释为上板闭环。

本地 canonical PCIe TX 源码已足以验证单 DWORD、full-byte-enable 的 MWR32 生成，但不能替代
完整 DMA 顶层注入/仲裁说明、板级链路资料和 RK3568 主机内存协议。以下清单仍以一手资料为准。

## 当前最小资料包

若希望下一批直接进入真实 IP/上板闭环，请优先提供以下五组资料：

1. 开发板准确型号/版本、原理图和 BOM，至少覆盖 FPGA、DDR3、PCIe、OV5640、时钟与复位页。
2. 当前 PG2L50H DDR3 IP 的 IDF/生成报告和匹配版本用户手册，尤其是 28-bit 地址单位、对齐、
   `RLAST/RVALID`、`AWREADY/WREADY`、初始化与 `core_clk` 合同。
3. PCIe DMA/TX 完整连接图或手册：项目仲裁后的完整 request bundle 应接入 `tx_top`/产品顶层的
   哪一层，partial DWORD byte enable 如何表达，以及 ACK、发送完成、错误与中断的区别。
4. RK3568 侧内核/设备树/驱动源码或冻结 API，包括 DMA 缓冲分配、IOMMU、缓存一致性、目标地址、
   槽所有权、完成通知和 golden frame 校验程序。
5. OV5640 模组资料与首版模式：SCCB 初始化表、MCLK、RESET/PWDN、DVP 极性、RGB565 字节序、
   宽高、帧率及是否保证整帧 DWORD 对齐。

## P0：开始真实顶层和 IP 连接前必须提供

1. **板卡身份与原理图**
   - 开发板准确型号、硬件版本和 FPGA 完整料号。
   - FPGA、OV5640、DDR3、PCIe、系统时钟和复位相关原理图页；最好同时提供网表或官方管脚表。
   - 25 MHz/其他系统时钟、PCIe 100 MHz refclk 的来源、频率、P/N 极性和管脚。
   - FPGA 复位、OV5640 RESET/PWDN、PCIe PERST# 的有效电平、上电顺序和最小时序。

2. **OV5640 模组与目标视频模式**
   - 模组型号、原理图/引脚定义、IO 电压、SCCB 上拉和 7-bit 地址。
   - XCLK/MCLK 要求，DVP `D[7:0]/PCLK/HREF/VSYNC` 管脚、极性、采样边沿和首字节顺序。
   - 可追溯到该模组的 OV5640 数据手册及 SCCB 初始化表，至少包含芯片 ID、RGB565、目标
     分辨率、帧率、blanking 和输出时钟配置。
   - 首版冻结值：宽、高、帧率、RGB565 字节序、当前灰度算法是否保留、允许的丢帧策略。

3. **DDR3 颗粒与 PG2L50H 控制器**
   - DDR3 颗粒完整料号/数据手册、数量、位宽、容量、rank/bank 和板级拓扑。
   - DQ/DQS/DM/address/control/clock 管脚映射，终端/参考电压信息，以及可用于当前板卡的
     完整 RCF/FDC。
   - 在 `Logos2 / PG2L50H / FBG484 / -6` 下生成的 DDR3 IP 工程、IP 版本和官方用户手册。
   - 用户口逐信号语义：地址单位、`awlen/arlen` 编码、写接受条件、写响应、读 valid/last、
     是否存在 read ready、读返回顺序、初始化/校准完成、复位和用户时钟要求。
   - 可用 DDR 地址范围及保留区域；双槽所需的槽大小、对齐和越界规则。

4. **PCIe IP 与板级拓扑**
   - FPGA 作为 Endpoint、RK3568 作为 Root Complex 的确认，lane 数、目标 Gen、参考时钟模式和
     PERST#/CLKREQ#/WAKE# 连接。
   - 当前 PG2L50H PCIe/DMA IP 的版本、配置导出、官方应用口手册和可运行 RC/EP 仿真模型。
   - `req_addr/req_length/req/ack/busy` 或 AXIS 接口的精确定义，包括长度单位、byte enable、
     `tkeep/tuser/tlast`、最大 payload、4 KB 边界、错误和完成语义。
   - BAR 尺寸/布局、MSI/MSI-X/INTx 选择，以及 FPGA 侧控制/状态寄存器需求。

5. **RK3568 主机软件与内存合同**
   - OS、内核版本、PCIe RC 配置、IOMMU/SMMU 是否启用及设备树片段。
   - DMA 目标地址来源：CMA/一致性 DMA/IOMMU IOVA/保留物理内存中的哪一种；地址宽度和对齐。
   - 缓存一致性模型和必要的 cache maintenance；禁止只给一个未经说明的物理地址。
   - 驱动源码或冻结接口：枚举/BDF、BAR/iATU、DMA 缓冲分配映射、启动、完成、中断、超时和
     错误恢复。
   - 帧缓冲协议：帧头/帧号、有效字节数、像素字节序、槽所有权、完成标志、错误帧和丢帧处理。

## P1：签核与实板验收前必须提供

- 可复现的 PDS/Logos2、IP 生成器和 programmer 版本，许可证和构建入口保留在仓库外部配置。
- 全量 FDC/RCF、CDC/RDC、综合、布局布线和 STA 报告要求；所有时钟和复位必须有约束来源。
- 板级调试入口：JTAG、UART、ILA/SignalTap 等片上观测方案和至少一个可识别的摄像头测试图。
- 主机端参考程序与 golden frame 校验方式，能区分链路失败、DMA 失败、帧协议失败和像素错误。
- 首版性能指标：可接受端到端延迟、持续帧率、DDR/PCIe 带宽余量和故障恢复时间。

## 收到资料后的工程顺序

1. 冻结板级管脚、时钟、复位和 OV5640 SCCB/DVP 合同。
2. 将已验证的 canonical 适配层接入实际 PG2L50H DDR3 core，先跑元数据记录单拍写读 BIST，再跑双槽帧。
3. 将 MWR32 请求边界接入完整 PCIe DMA/TX 顶层，完成仲裁、4 KB、最大 payload 和 byte-enable 回归。
4. 与 RK3568 驱动冻结目标缓冲和槽所有权协议，完成单帧 golden image 闭环。
5. 依次完成行为级、综合后、PNR 后功能、PNR 后时序和实板验收；每层保持独立失败退出契约。
