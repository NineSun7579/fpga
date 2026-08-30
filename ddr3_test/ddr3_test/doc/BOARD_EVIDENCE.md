# DDR3 Bring-up 板级证据清单

状态：待板级资料与审核。更新日期：2026-08-30。

本文件服务于 `test_ddr` bring-up 和后续项目自有有限 BIST。`test_ddr` 是当前示例顶层，不等同于产品顶层；板级资料闭合前不得修改厂商 DDR3 IP、FDC、RCF 或物理端口。

## 当前工程事实

| 项目 | 当前建模值 | 证据 | 结论 |
|---|---|---|---|
| PDS 目标 | `Logos2 / PG2L100H / FBG484 / -6` | `README.md`、`scripts/build.tcl` | 需与 FPGA 丝印核对 |
| 活动 IP | `ddr3`，IDF 标识 `PG2L100H/FBG484/-6` | `ip_core/ddr3/ddr3.idf` | 元数据已与 PDS 目标一致 |
| 当前示例顶层 | `test_ddr` | `ip_core/ddr3/example_design/rtl/test_ddr.v` | 仅用于 bring-up |
| DDR3 配置 | x16、2 个 DQS、目标 1066 MT/s，当前约 1050 MT/s | `README.md`、活动 IP 参数 | 需用颗粒料号确认 |
| 参考时钟 | `free_clk`，FDC 周期 40 ns、管脚 `V4`、LVCMOS15 | `ip_core/ddr_test.fdc` | 需确认实际时钟源/容差 |
| 板级复位 | `rst_board`，管脚 `M15`、LVCMOS18 | `ip_core/ddr_test.fdc` | share pin/电压待审核 |
| DDR 地址 | FDC 当前包含 `mem_a[14]` | `ip_core/ddr_test.fdc` | 需核对颗粒 row address |
| 用户接口 | Pango AXI-like，非完整 AXI4 | `doc/FINITE_SELF_TEST_CONTRACT.md`、D3-0 评审 | D3-A 必须保持该语义 |

## 必须提供的资料

| 证据项 | 用户需提供 | 验收条件 |
|---|---|---|
| 板卡身份 | 板卡型号、原理图版本、BOM、FPGA 完整丝印 | 与 `PG2L100H/FBG484/-6` 可追溯一致 |
| DDR3 颗粒 | 完整料号、数量、容量、rank、x16/x32 组织、目标速率 | 与活动 IDF 参数一致，或触发重新生成审核 |
| 地址/容量 | row/column/bank 地址位数及 `mem_a[14]` 是否真实连接 | 关闭 14/15 bit 分支，RTL/IP/FDC 三方一致 |
| 走线拓扑 | A/BA/CK/DQ/DQS/DM byte-lane 映射、bit/byte swap、PCB 延迟 | 可形成 PHY 参数和 I/O timing 依据 |
| 电气参数 | VCCIO、VREF、ODT、终端、驱动、SSTL 标准 | 与 FDC 和颗粒数据手册一致 |
| 时钟/复位 | `free_clk` 频率、来源、精度、`rst_board` 极性和上电时序 | 可验证 40 ns 约束及 reset 语义 |
| UART/ADC | 是否保留；如保留，管脚、电压、波特率和外部连接 | 决定示例调试通道是否进入发布 gate |
| Bank/Share pin | `M15` 等复用管脚、配置 bank 电压和启动模式 | 关闭 share-pin/VCCIO/SCBV 阻断 |

## 关闭条件

1. 资料必须以原理图、BOM、芯片丝印、数据手册或受控测试记录为来源。
2. `mem_a[14]` 不得依据当前 FDC 单独决定；必须由实际 DDR3 颗粒和布线确认。
3. D3-A 只能新增项目自有 top/BIST，保留 `I_ips_ddr_top`、物理端口和厂商 IP 原样。
4. 在资料闭合前，内部 STA `All Constraints Met` 仅代表当前建模路径通过，不代表板级验收。
