# main OV5640→PCIe 板级证据清单

更新日期：2026-09-04

## 一手资料登记

| 资料 | 外部文件位置 | 版本/页数 | SHA-256 | 仓库边界 |
|---|---|---|---|---|
| RK3568+PG2L50H/100H 硬件使用手册 | `C:\Users\Epsilon\Downloads\RK3568_MES2L50H_100H_硬件使用手册_v1.1.pdf` | v1.1，34 页 | `FE7017CC64FDAD56ECE2BED92391A9071B2D0B8FB92BDC195BAEA0D987B395F5` | 仅登记本机外部资料，不复制入仓、不作为构建依赖 |
| OV5640 自动对焦照相模组应用指南（DVP 接口） | `C:\Users\Epsilon\Downloads\OV5640_自动对焦照相模组应用指南(DVP_接口)__R2.13C.pdf` | 2.13，63 页，2011-11-04 | `D709BDF8DC26AD2608759B4DFB4BC083DA409F7D3DC7074C47C6B6BFA9D81AD8` | 仅登记本机外部资料，不复制入仓、不作为构建依赖 |

页码均指 PDF 页码。手册中的参考连接、时序和示例寄存器不能替代实际模组、原理图、网表、IP 用户手册或实测记录。

## 已确认的工程事实

| 类别 | 当前事实 | 来源 | 状态 |
|---|---|---|---|
| FPGA 目标 | 板卡系列支持 `PG2L50H-6IFBG484 / PG2L100H-6IFBG484`；本工程实物目标由 owner 确认为 `PG2L50H-6IFBG484` | RK 手册 PDF 第 4、7 页；owner 器件确认 | 已确认 |
| PCIe 结构 | `main` 有 PCIe x2 Endpoint/DMA 基础 | `pcie_dma_test_100h/hdl/pcie_dma_test.v` | 已确认 |
| OV5640 | `main` 尚无产品级 OV5640 RTL/顶层 | `main` 文件树 | 已确认 |
| RK↔FPGA 总线 | RK3568 与 FPGA 之间连接 PCIe、FSPI、I2C0 和部分 GPIO | RK 手册 PDF 第 4、26–27 页 | 已确认 |
| PCIe 物理宽度 | 实际连接两条 lane：RK TX0/1→FPGA RX0/1，FPGA TX0/1→RK RX0/1 | RK 手册 PDF 第 27 页 | x2 已确认；协商 Gen 等级待实测 |
| PCIe lane 管脚 | FPGA RX0 P/N=`D9/C9`，RX1 P/N=`B10/A10`；TX0 P/N=`D7/C7`，TX1 P/N=`B6/A6` | RK 手册 PDF 第 27 页 | 已确认 |
| PCIe refclk | PI6C557-05BLE 由 25 MHz 倍频生成 100 MHz 差分时钟，同时供 FPGA HSST 和 RK PCIe；FPGA refclk P/N=`F6/E6` | RK 手册 PDF 第 11 页 | 来源、频率和 FPGA 管脚已确认 |
| 板载系统时钟 | `MAIN_CLK_25M` 接 FPGA `V4` | RK 手册 PDF 第 9 页 | 已确认 |
| DDR3 参考时钟 | `GCLK_DDR_133_P/N` 接 FPGA `R4/T4` | RK 手册 PDF 第 10 页 | 已确认 |
| DDR3 颗粒 | FPGA BANK R4/R5 接一片 `F60C1A0004-M79W`，x16、512 MByte、最大 1066 Mbps | RK 手册 PDF 第 12 页 | 器件、位宽和容量已确认 |
| DDR3 地址宽度 | 实际有效地址为 `ddr3_addr[14:0]`；`ddr3_addr[15]` 为预留脚，完整 DDR3 管脚映射见手册第 13 页 | RK 手册 PDF 第 13 页 | 板级映射已确认；IP 用户口语义仍待确认 |
| I2C0 | FPGA `P19/R19` 分别连接 `I2C_SCL/I2C_SDA` | RK 手册 PDF 第 26 页 | 板级连接已确认 |
| FSPI | FPGA CLK/CS0n/D0/D1/D2/D3 分别为 `L19/L20/N22/M22/M18/L18` | RK 手册 PDF 第 26 页 | 板级连接已确认 |
| 控制 GPIO | `CFG_DONE=G11`、`RSTN=N12`、`INIT_FLAG_N=U12`，另有 RK GPIO 接 FPGA `P20/U22` | RK 手册 PDF 第 26 页 | 板级连接已确认；方向和产品用途需在顶层合同冻结 |
| OV5640 数据接口 | 用户指定外置 OV5640 使用 DVP；8-bit YUV/RGB/RGB565 输出使用传感器 `D[9:2]`，接口还包括 PCLK、HREF/HSYNC、VSYNC、XCLK、SCCB、RESETB、PWDN | OV5640 指南 PDF 第 5–6 页 | 参考接口已确认；实际接入位置/管脚待定 |
| OV5640 控制极性 | `RESETB` 低有效且内部上拉；`PWDN` 高有效且内部下拉 | OV5640 指南 PDF 第 5–6 页 | 已确认 |
| OV5640 供电与电平 | AVDD 2.6–3.0 V（推荐 2.8 V），DVDD 1.5 V±5%，DOVDD 1.7–3.0 V（建议 1.8 V）；主机与模组 IO 电压不同时，视频和 RESETB 可能需要电平转换 | OV5640 指南 PDF 第 5、7–8 页 | 参考要求已确认；实际 FPGA Bank 电压待定 |
| OV5640 SCCB | SIO_C/SIO_D 需要外部上拉，指南标准值 5.1 kΩ；示例使用 8-bit 写地址 `0x78` | OV5640 指南 PDF 第 6、56 页 | 上拉要求已确认；7-bit 地址和实际模组需读 ID/实测确认 |
| OV5640 上电时序 | 初始 RESETB=0、PWDN=1；AVDD 稳定至少 5 ms 后 PWDN 拉低，至少 1 ms 后 RESETB 拉高，再等待至少 20 ms 开始 SCCB 初始化 | OV5640 指南 PDF 第 10 页 | 参考最小时序已确认；板级电源控制实现待定 |
| OV5640 复位/休眠 | 硬件复位低脉冲至少 1 ms；进入 power-down 后 XCLK 至少保持 0.1 ms，唤醒先提供 XCLK 再等待 0.1 ms 拉低 PWDN | OV5640 指南 PDF 第 11–12 页 | 参考最小时序已确认 |
| OV5640 模式示例 | 指南给出 24 MHz 输入、VGA/YUV 等示例；示例不能直接作为本工程 RGB565 冻结寄存器表 | OV5640 指南 PDF 第 14–15、53 页 | 仅参考，不关闭产品模式 |
| 主机输出 | 目标为 PCIe Memory Write 到主机内存 | 产品合同 | 协议待确认 |

## 当前仍缺的一手资料

- 板卡准确硬件版本、完整原理图/BOM/网表，以及实际焊接 FPGA 与 DDR3 的可归档身份记录。
- PCIe PERST#/CLKREQ#/WAKE# 的独立连接、有效电平、上电/释放时序、AC 耦合与实板链路协商结果。
- 当前 PG2L50H DDR3 IP 的生成配置、匹配版本用户手册、地址单位、初始化、AW/W/AR/R 和 RLAST/RVALID 正式语义。
- 完整 PCIe DMA/TX 产品顶层接入点、请求仲裁后的 full bundle、partial DWORD byte enable、ACK/发送完成/错误/中断语义。
- RK3568 OS、设备树与驱动合同：BAR/iATU、DMA 缓冲、IOMMU/SMMU、缓存一致性、目标地址、槽所有权、完成通知和错误恢复。
- 外置 OV5640 模组准确料号、24-pin 排线/连接器实际定义、FPGA 接入连接器和具体管脚；当前位置明确保持“暂定”。
- OV5640 所接 FPGA Bank 的 IO 电压、DOVDD、SCCB 上拉电压与是否需要视频/RESETB 电平转换。
- 产品首版冻结模式：XCLK、宽高、帧率、PCLK、RGB565 字节序、VSYNC/HREF 极性、PCLK 采样边沿、SCCB 7-bit 地址、芯片 ID 期望值和完整初始化表。
- 若启用自动对焦：可合法使用且与实际模组匹配的 AF 固件来源、下载流程和验收方法。

## 关闭条件

每个条目必须关联到具体版本的一手资料或实际测量记录。历史工程命名、参考分支注释、示例寄存器表、行为级模型或已有位流均不能单独关闭板级证据。
