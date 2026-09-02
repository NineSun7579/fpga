# main OV5640→PCIe 板级证据清单

更新日期：2026-09-02

## 已确认的工程事实

| 类别 | 当前事实 | 来源 | 状态 |
|---|---|---|---|
| FPGA 目标 | 新项目按 `Logos2 / PG2L100H / FBG484 / -6` 规划 | 项目恢复决策 | 待一手资料闭合 |
| PCIe 结构 | `main` 有 PCIe x2 Endpoint/DMA 基础 | `pcie_dma_test_100h/hdl/pcie_dma_test.v` | 已确认 |
| OV5640 | `main` 尚无产品级 OV5640 RTL/顶层 | `main` 文件树 | 已确认 |
| PCIe refclk | 设计要求独立差分参考时钟 | `pcie_dma_test_100h/fdc/pcie_dma_test.fdc` | 频率/管脚待确认 |
| 主机输出 | 目标为 PCIe Memory Write 到主机内存 | 产品合同 | 协议待确认 |

## 必须补充的一手资料

- FPGA 完整丝印、封装和速度级。
- OV5640 模组完整料号、连接器定义、供电电压和 DVP 电平。
- OV5640 的 MCLK/XCLK 来源、频率和容差。
- `cam_pclk`、VSYNC、HREF、数据位序和采样边沿。
- SCCB 地址、RESET、PWDN 和两线连接方式。
- DDR3 颗粒料号、容量、位宽、byte lane、VREF、bank 电压和 PCB 拓扑。
- 板载 25 MHz 晶振网络、`sys_clk` 实际来源及外部倍频链。
- PCIe 100 MHz refclk 来源、P/N 管脚、极性、AC 耦合和 PERST# 连接。
- 主机/RK3568 的目标地址分配、帧长度、帧通知和错误处理方式。

## 关闭条件

每个条目必须关联原理图、BOM、器件手册、主机协议或实际测量记录。仅凭历史工程命名、参考分支注释或已有位流不能关闭板级证据。
