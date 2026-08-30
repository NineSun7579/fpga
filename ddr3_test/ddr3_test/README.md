# DDR3 bring-up 实现基线

## 当前定位

外层历史工程只引用 DDR3 IP，没有明确产品顶层。本目录的新脚本暂以 IP 自带当前版 `test_ddr` 作为板级 bring-up 顶层，用于建立可重复实现基线；它不是最终产品顶层。

当前配置：

- 器件：`Logos2 / PG2L100H / FBG484 / -6`
- DDR3 IP：Controller + PHY，x16、2 个 DQS、目标 1066 MT/s，当前配置约 1050 MT/s
- 示例顶层：`ip_core/ddr3/example_design/rtl/test_ddr.v`
- 厂商 IP：只通过 `ip_core/ddr3/ddr3.idf` 展开
- 厂商示例约束基线：`ip_core/ddr3/pnr/ddr_test.fdc`
- 优先路由约束：`ip_core/ddr3/pnr/ddr3.rcf`

禁止使用外层旧 `ip_core/ddr_test.fdc`，其中仍包含 PG2L50H 的硬宏位置。

## 构建

快速验证源码、IDF、FDC 和 RCF：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action build
```

执行完整 PDS 流程：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action build `
  -RunTo gen_bit_stream
```

严格检查完整构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action check-build
```

当前历史基线包含已知发布阻断。仅为了确认实现和产物可重复时，可显式运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
  -Action check-build `
  -AllowKnownBaselineIssues
```

baseline 放行不会把结果标记为发布候选。

生成物统一写入本目录的 `build/`，不提交版本库。

## 已验证基线

已从空 `build/` 执行到 `compile`：

- PDS 退出码为 0，日志没有 `E:`。
- 成功加入 18 个示例 RTL、`ddr3.idf`、FDC 和 RCF。
- 日志共有 272 条 warning；其中 `test_ddr.v:855` 有两条 BIST 错误数据端口位宽不匹配，其余告警按厂商 IP 基线保留并等待完整实现 gate 分类。

已从空 `build/` 继续完成完整实现：

- PDS 退出码为 0，完整日志没有 `E:`。
- 最终报告为 `All Constraints Met`。
- 慢角 setup WNS 为 `0.678 ns`、TNS 为 `0`；慢角 hold、recovery、removal 最差值分别为 `0.137 ns`、`4.578 ns`、`0.351 ns`。
- 资源约为 4820 个 LUT、5327 个 FF 和 55 个 I/O。
- 生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`。

产物基线：

| 产物 | 大小（字节） |
|---|---:|
| `test_ddr_syn.vm` | 5,914,586 |
| `test_ddr_sim.v` | 9,734,239 |
| `test_ddr_sta.sdf` | 9,130,393 |
| `test_ddr.sbit` | 3,791,112 |
| `test_ddr.bin` | 3,789,476 |

严格 gate 实测返回非零；显式使用 `-AllowKnownBaselineIssues` 时返回 0，并明确标记当前结果不可发布。`All Constraints Met` 只证明已建模的内部路径通过，不证明板级 I/O 时序、DDR 训练或功能仿真通过。

## 当前阻断项

- 未根据实际板卡核对 DDR3 颗粒、容量、byte lane、VREF、终端、电源和 PCB 拓扑。
- 缺少经审核的板级参数清单，严格 gate 尚不能核对 IDF/FDC 与原理图的一致性。
- `rst_board` 使用 M15 share pin，且 BANKR4 的 3.3 V VCCIO 与当前放置不兼容。
- UART RX/TX 没有板级引脚和 I/O 标准约束；顶层输入/输出时序也未完整约束。
- 当前 testbench 仍连接旧版顶层已经删除的 5 个端口，无法直接 elaboration。
- 当前 BIST 持续随机读写，没有天然有限 `done`；`bist_run_led` 是翻转指示而不是完成信号。
- `test_ddr.v:855` 的 `err_data_pre`、`err_data_aft` 与 BIST 模块端口位宽不一致。
- 行为级、综合后和两个 PNR 后仿真尚未建立可靠的 `$fatal`、超时、`TEST PASS` 和退出码。

在这些信息确认前，不修改 DDR3 IP 参数、FDC、顶层接口或 LED 语义。

## D2 有限自检决策

完整设计契约见 [DDR3 有限自检契约](doc/FINITE_SELF_TEST_CONTRACT.md)。D2 已确认：

- 不修改或复制 `ip_core/ddr3/**` 下的厂商示例 BIST/TB；
- 后续新增项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv`，直接实例化活动 DDR3 IP；
- 首版执行 16 个单 beat 写读比较 pair，地址为控制器地址单位 `0x0..0x78`、步长 8；
- 数据模式、131072 周期运行上限、稳定 `test_done/test_failed/failure_code/error_count/completed_pairs` 和首错信息已经固定；
- LED 只能显示公开状态，不能作为完成或 PASS/FAIL 的原始依据；
- 新 TB 必须使用公开端口、相对路径、Questa WLF、`$fatal` 和唯一 `TEST PASS`，FSDB 仅作为显式可选功能。

D2 是文档决策批次，没有修改 RTL、TB、IDF、FDC 或 RCF。D3 功能实现需先完成 D3-0 的 core/wrapper、非标准 Pango DDR UI 握手和 `I_ips_ddr_top` 层级评审；当前仓库的唯一功能主线仍为 OV7725 O2-D1 只读评审，D3-0 可作为独立只读泳道准备，但不得并行启动 D3-A 功能 RTL。

## D3-0 只读评审结果

2026-08-30 已从活动 IP、实例模板和示例 wrapper 唯一确认 D3-A 的接口边界：

- 公开 core 是 `ip_core/ddr3/ddr3.v` 的 `ddr3` 模块，提供 `core_clk`、`ddr_init_done`、PLL/PHY 状态以及 128-bit 用户数据通路；生成文件保持不改。
- 物理 board wrapper 是 `ip_core/ddr3/example_design/rtl/test_ddr.v`，保留现有 `free_clk`、`rst_board`、UART 和 DDR3 物理端口。它以实例名 `I_ips_ddr_top` 连接活动 `ddr3` core；FDC/RCF 与后续层级检查依赖该名字。
- 用户接口是 Pango 定制的 AXI-like 端口，而不是完整 AXI4：写地址用 `axi_awvalid & axi_awready`，写数据完成由 core 输出 `axi_wready` 表示；`axi_wusero_id`、`axi_wusero_last` 为返回标记。读地址用 `axi_arvalid & axi_arready`，读数据由 `axi_rvalid`/`axi_rlast` 返回，接口没有 `axi_rready`。
- 当前示例控制器把写 outstanding 计数与 `axi_wready` 接受次数比较，把读请求计数与 `axi_rvalid` 返回次数比较；D3-A 必须将这些事实转换为有限 BIST 的明确握手/超时契约，不得假设标准 `AWREADY/WREADY/BVALID/ARREADY/RREADY` 语义。

D3-A 允许的首批边界仅为新增项目自有 `ddr3_bringup_top.sv`、`ddr3_finite_bist.sv`，切换 PDS 顶层和输入清单，并完成 compile/elaboration。不得修改 `ip_core/ddr3/**`、FDC、RCF、物理端口或 `I_ips_ddr_top` 实例名。若重新生成 IP 后端口、地址单位、`axi_wready` 完成语义或层级不再唯一，立即停止并重新审核。
