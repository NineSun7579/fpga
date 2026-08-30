# PCIe H2-A 板级证据与 IP 目标契约

状态：50H 器件目标与可重复实现已完成，待其余板级资料。更新日期：2026-08-30。

用户已确认：本工程与 DDR3、OV7725 HDMI 工程共用 `RK3568+PG2L50H100H` 开发板，实际焊接 FPGA 为 `PG2L50H-6IFBG484`。PDS 参数统一采用 `Logos2 / PG2L50H / FBG484 / -6`。

## 1. 当前工程事实

| 项目 | 当前事实 | 证据 |
|---|---|---|
| 实际 FPGA | `PG2L50H-6IFBG484` | 用户于 2026-08-30 明确确认并批准三项目统一迁移 |
| 当前 PDS 目标 | `Logos2 / PG2L50H / FBG484 / -6` | `scripts/build.tcl`、50H 构建日志 |
| PCIe 顶层 | `pcie_dma_test`，x2 `rxn/rxp/txn/txp` | `hdl/pcie_dma_test.v` |
| 参考时钟 | 差分 `ref_clk_p/n`，FDC 管脚 `F6/E6`，约束周期 `10 ns` | `fdc/pcie_dma_test.fdc` |
| PERST# | `perst_n`，FDC 管脚 `M16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 板级复位 | `button_rst_n`，FDC 管脚 `M15`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 状态灯 | `ref_led=M17`、`pclk_led=J16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 活动 IP metadata | `Logos2 / PG2L50H / FBG484 / -6` | `ipcore/pcie_test/pcie_test.idf:10-13` |
| HSSTLP 资源位置 | `HSSTLP_292_612`，x2 lane 与 PLL0 | PDS SP6.4 HSSTLP PG2L50H 模板、50H PNR 日志 |
| UART | `pgr_uart2apb_top` 使用隐式 `rxd/txd`；顶层没有对应端口，`rxd` 当前被工具绑为 0 | `hdl/pcie_dma_test.v`、SP6.4 compile 日志 |

IDF、PDS 目标、STA 和新生成位流数据库均已统一为 `PG2L50H/FBG484/-6`。旧 100H 内部 STA、网表、SDF、`.sbit` 和 `.bin` 不能用于实际板卡验收或烧录。

## 2. 约束现状与缺口

当前 FDC 建立 `pclk=4 ns`、`pclk_div2=8 ns`、`ref_clk=10 ns` 三个时钟对象，并把三个时钟分别置于异步 clock group。FDC 没有顶层输入/输出 delay、PCIe lane 极性/拓扑证据或 SCBV 配置；lane 的物理位置和参考时钟连接仍需原理图、BOM 和芯片丝印确认。

不得仅通过新增 `false_path`、clock group 或虚构 I/O delay 关闭这些缺口。任何新增约束必须能追溯到板级资料、官方 IP 模板或明确审核记录。

## 3. H2-A 证据矩阵

| 证据项 | 当前状态 | H2-A 关闭条件 |
|---|---|---|
| FPGA 完整型号与封装 | 已确认 `PG2L50H-6IFBG484`；活动 IP 为 PG2L50H | build、IDF、STA 和 bitstream 全部重建并交叉确认 PG2L50H |
| PCIe lane 数、映射与极性 | 顶层只有 x2 端口，FDC 未给出板级 lane 映射 | 原理图/PCB 明确 lane 0/1、P/N 极性、连接器方向和 AC 耦合位置 |
| 100 MHz refclk | RTL/FDC 使用 10 ns 差分时钟 | 确认来源、频率容差、共模/终端和 F6/E6 连接 |
| PERST# | `perst_n=M16`，有同步/去抖逻辑 | 确认电平、来源、上电时序和 M16 share pin 使用 |
| button reset | `button_rst_n=M15`，与 share pin 相关 | 确认是否与其他功能复用及电压条件 |
| UART2APB | `rxd/txd` 为隐式网络，`rxd` 绑 0 | 决定保留或删除；保留时补管脚、电气标准和波特率 |
| SCBV/config bank | 当前构建日志提示 SCBV 未设置 | 提供配置 bank 电压和启动模式，确认 bitstream 参数 |
| LED | 仅用于人眼状态观察 | 确认无需外部时序；否则建立正式 I/O timing |

## 4. 允许范围与停止条件

H2-A 只允许新增/更新证据文档，不修改 RTL、活动 IDF 或 FDC，也不得把历史 `impl.tcl` 当作重建入口。用户已经批准下一批将 build/gate 恢复为 PG2L50H。

器件迁移批次无需重生成已匹配实物的 SP6.4 PCIe IP；已修正 build/gate，并依据 PDS SP6.4 PG2L50H 模板将 HSSTLP 资源从旧 100H 坐标迁移到 `HSSTLP_292_612`。lane/refclk/PERST#、UART 和 SCBV 仍由后续 H2-B 闭合，在这些资料到位前不把 50H 构建成功描述为可发布。

## 5. 必须提供的资料

| 证据项 | 用户需提供 | 验收条件 |
|---|---|---|
| 板卡与器件 | 板卡已确认；仍需原理图/BOM 和可归档丝印照片或等价记录 | 与 PG2L50H PDS 目标和 IP metadata 一致，版本可追溯 |
| PCIe 连接 | lane 映射/极性、参考时钟、PERST#、AC 耦合和连接器拓扑 | x2 lane、100 MHz refclk、PERST# 约束可由一手资料确认 |
| 电气与配置 | bank 电压、SCBV、启动模式、share pin 使用 | FDC、配置参数与板级电压/复用关系一致 |
| UART/LED | UART2APB 保留或删除决策、RX/TX 管脚；LED 外部时序要求 | 不再存在未决隐式网络或未经约束的外部时序接口 |

## 6. 关闭条件

1. 资料来源、版本和审核状态已记录，且覆盖证据矩阵全部条目。
2. build、活动 PCIe IP、时序报告和 bitstream 数据库均为 `PG2L50H/FBG484/-6`，且不存在 `Flow-4058` 器件不一致；该条件已由 M1 重建验证。
3. UART、SCBV、lane/refclk/PERST# 和 share pin 的处理均有明确决策与可追溯约束依据。
4. H2-B 严格 gate 在不带 baseline 放行参数时返回 0；否则继续保持发布阻断。
