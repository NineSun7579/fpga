# PCIe H2-A 板级证据与 IP 目标契约

状态：目标恢复为 PG2L100H；紫光盘古100Pro 的 lane、参考时钟和配置资料仍待复核。更新日期：2026-09-02。

用户已确认开发板为紫光盘古100Pro；当前 PCIe 恢复目标为 `Logos2 / PG2L100H / FBG484 / -6`。完整 FPGA 丝印、原理图/BOM 和 PCIe 连接资料仍需归档。

## 1. 当前工程事实

| 项目 | 当前事实 | 证据 |
|---|---|---|
| FPGA 目标 | `PG2L100H-6IFBG484`（待一手资料确认完整料号） | 用户目标修订、历史 PDS 工程/产物 |
| 当前 PDS 目标 | 恢复为 `Logos2 / PG2L100H / FBG484 / -6` | 现有 `.pds`、历史 timing report；canonical build 尚待恢复 |
| PCIe 顶层 | `pcie_dma_test`，x2 `rxn/rxp/txn/txp` | `hdl/pcie_dma_test.v` |
| 参考时钟 | 差分 `ref_clk_p/n`，FDC 管脚 `F6/E6`，约束周期 `10 ns` | `fdc/pcie_dma_test.fdc` |
| PERST# | `perst_n`，FDC 管脚 `M16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 板级复位 | `button_rst_n`，FDC 管脚 `M15`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 状态灯 | `ref_led=M17`、`pclk_led=J16`，LVCMOS18 | `fdc/pcie_dma_test.fdc` |
| 活动 IP metadata | 当前文件曾为 `Logos2 / PG2L50H / FBG484 / -6` | `ipcore/pcie_test/pcie_test.idf:10-13`；与 100H 恢复目标不一致 |
| HSSTLP 资源位置 | 50H staging 使用 `HSSTLP_292_612` | 仅作 50H 历史证据；100H 资源位置需按匹配 IP 重新确认 |
| UART | `pgr_uart2apb_top` 使用隐式 `rxd/txd`；顶层没有对应端口，`rxd` 当前被工具绑为 0 | `hdl/pcie_dma_test.v`、SP6.4 compile 日志 |

50H IDF、PDS 目标和新生成产物属于前一轮错误器件目标的历史证据；恢复 100H 前不得用于紫光盘古100Pro 验收或烧录。

H2-B0 已新增 [`H2B_BASELINE_GATE.md`](H2B_BASELINE_GATE.md) 与机器指纹 [`H2B_BASELINE_FINGERPRINT.json`](H2B_BASELINE_FINGERPRINT.json)。当前五类阻断被归一化为 16 个对象签名、42 次原始记录；baseline 只允许精确复现，IP metadata 不再可被放行。该静态门禁不替代本文件要求的板级资料。

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

恢复批次必须取得匹配 PG2L100H 的 PCIe IP，或明确接受 IP 重生成及完整回归；不能只改 `set_arch`。旧 50H H2-B0 指纹和 `HSSTLP_292_612` 位置只作历史差异证据。lane/refclk/PERST#、UART 和 SCBV 仍由 H2-B1 闭合，在资料到位前不把任何构建描述为可发布。

## 5. 必须提供的资料

| 证据项 | 用户需提供 | 验收条件 |
|---|---|---|
| 板卡与器件 | 紫光盘古100Pro 已确认；仍需原理图/BOM 和可归档丝印照片或等价记录 | 与 PG2L100H PDS 目标和匹配 IP metadata 一致，版本可追溯 |
| PCIe 连接 | lane 映射/极性、参考时钟、PERST#、AC 耦合和连接器拓扑 | x2 lane、100 MHz refclk、PERST# 约束可由一手资料确认 |
| 电气与配置 | bank 电压、SCBV、启动模式、share pin 使用 | FDC、配置参数与板级电压/复用关系一致 |
| UART/LED | UART2APB 保留或删除决策、RX/TX 管脚；LED 外部时序要求 | 不再存在未决隐式网络或未经约束的外部时序接口 |

## 6. 关闭条件

1. 资料来源、版本和审核状态已记录，且覆盖证据矩阵全部条目。
2. build、活动 PCIe IP、时序报告和 bitstream 数据库均为 `PG2L50H/FBG484/-6`，且不存在 `Flow-4058` 器件不一致；该条件已由 M1 重建验证。
3. UART、SCBV、lane/refclk/PERST# 和 share pin 的处理均有明确决策与可追溯约束依据。
4. H2-B1 严格 gate 在不带 baseline 放行参数时返回 0；否则继续保持发布阻断。
