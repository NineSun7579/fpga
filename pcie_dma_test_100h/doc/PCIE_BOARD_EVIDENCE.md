# PCIe H2-A 板级证据与 IP 目标契约

状态：只读评审，待板级资料与用户审核。更新日期：2026-08-30。

## 1. 当前工程事实

| 项目 | 当前事实 | 证据 |
|---|---|---|
| PDS 目标 | `Logos2 / PG2L100H / FBG484 / -6` | `scripts/build.tcl` |
| PCIe 顶层 | `pcie_dma_test`，x2 `rxn/rxp/txn/txp` | `hdl/pcie_dma_test.v` |
| 参考时钟 | 差分 `ref_clk_p/n`，FDC 管脚 `F6/E6`，约束周期 `10 ns` | `fdc/pcie_dma_test.fdc` |
| PERST# | `perst_n`，FDC 管脚 `M16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 板级复位 | `button_rst_n`，FDC 管脚 `M15`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 状态灯 | `ref_led=M17`、`pclk_led=J16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 活动 IP metadata | `Logos2 / PG2L50H / FBG484 / -6` | `ipcore/pcie_test/pcie_test.idf:10-13` |
| UART | `pgr_uart2apb_top` 使用隐式 `rxd/txd`；顶层没有对应端口，`rxd` 当前被工具绑为 0 | `hdl/pcie_dma_test.v`、SP6.4 compile 日志 |

IDF 的 `PG2L50H` 与当前 PDS 目标 `PG2L100H` 不一致。内部 STA 通过只能证明当前建模输入下的实现结果，不能替代器件一致性或板级签核。

## 2. 约束现状与缺口

当前 FDC 建立 `pclk=4 ns`、`pclk_div2=8 ns`、`ref_clk=10 ns` 三个时钟对象，并把三个时钟分别置于异步 clock group。FDC 没有顶层输入/输出 delay、PCIe lane 极性/拓扑证据或 SCBV 配置；lane 的物理位置和参考时钟连接仍需原理图、BOM 和芯片丝印确认。

不得仅通过新增 `false_path`、clock group 或虚构 I/O delay 关闭这些缺口。任何新增约束必须能追溯到板级资料、官方 IP 模板或明确审核记录。

## 3. H2-A 证据矩阵

| 证据项 | 当前状态 | H2-A 关闭条件 |
|---|---|---|
| FPGA 完整型号与封装 | 目标为 PG2L100H/FBG484；IP 仍为 PG2L50H | 板卡丝印与原理图确认，并用 SP6.4 IP Compiler 生成 PG2L100H IP |
| PCIe lane 数、映射与极性 | 顶层只有 x2 端口，FDC 未给出板级 lane 映射 | 原理图/PCB 明确 lane 0/1、P/N 极性、连接器方向和 AC 耦合位置 |
| 100 MHz refclk | RTL/FDC 使用 10 ns 差分时钟 | 确认来源、频率容差、共模/终端和 F6/E6 连接 |
| PERST# | `perst_n=M16`，有同步/去抖逻辑 | 确认电平、来源、上电时序和 M16 share pin 使用 |
| button reset | `button_rst_n=M15`，与 share pin 相关 | 确认是否与其他功能复用及电压条件 |
| UART2APB | `rxd/txd` 为隐式网络，`rxd` 绑 0 | 决定保留或删除；保留时补管脚、电气标准和波特率 |
| SCBV/config bank | 当前构建日志提示 SCBV 未设置 | 提供配置 bank 电压和启动模式，确认 bitstream 参数 |
| LED | 仅用于人眼状态观察 | 确认无需外部时序；否则建立正式 I/O timing |

## 4. 允许范围与停止条件

H2-A 只允许新增/更新本证据文档、README、TODO、实施日志和 `.nexus-map/**`。不得修改 RTL、活动 IDF、FDC、RCF 或 gate，也不得把历史 `impl.tcl` 当作重建入口。

只有在证据矩阵闭合后，才可进入 H2-B：用 SP6.4 IP Compiler 重生成 PG2L100H PCIe IP，随后单独审核 RTL/FDC 变更和精确 baseline 指纹。若 lane/refclk/PERST#、UART、SCBV 或 IP 目标仍有任一不确定项，停止在 H2-A，不启动 IP/RTL 修改。
