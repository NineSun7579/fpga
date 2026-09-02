# DDR3 bring-up 实现基线

## 当前定位

外层历史工程只引用 DDR3 IP，没有明确产品顶层。本目录的新脚本暂以 IP 自带当前版 `test_ddr` 作为板级 bring-up 顶层，用于建立可重复实现基线；它不是最终产品顶层。

当前配置：

- PDS 版本：`2022.2-SP6.4`
- 开发板：紫光盘古100Pro；恢复器件与 PDS 目标：`PG2L100H-6IFBG484` / `Logos2 / PG2L100H / FBG484 / -6`
- DDR3 IP：Controller + PHY，x16、2 个 DQS、目标 1066 MT/s，当前配置约 1050 MT/s
- 示例顶层：`ip_core/ddr3/example_design/rtl/test_ddr.v`
- 厂商 IP：只通过 `ip_core/ddr3/ddr3.idf` 展开
- 厂商示例约束基线：`ip_core/ddr3/pnr/ddr_test.fdc`
- 优先路由约束：`ip_core/ddr3/pnr/ddr3.rcf`

板级资料收集入口见 [DDR3 Bring-up 板级证据清单](doc/BOARD_EVIDENCE.md)。

当前活动 DDR3 IDF/FDC 原本就是 PG2L100H，可作为紫光盘古100Pro 的恢复候选。外层旧 `ip_core/ddr_test.fdc` 中的 50H 硬宏位置和 staging 资产仅作历史差异证据，不得混入 100H canonical 输入。

## M2-A staging 重生成

使用项目自有入口把活动 DDR3 IP 复制到忽略目录并为 PG2L50H 重生成：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\regenerate_ip.ps1
```

默认输出为 `build/ipgen/pg2l50h`，日志为 `build/logs/ipgen-pg2l50h.log`。脚本以大小写敏感的参数名和值多重集验证 SP6.1 50H seed 与活动 IDF 除隐藏器件参数外一致，再由 SP6.4 重生成；随后检查 IDF header、`DEVICE_100H_EN=false`、50H PPLL 分支和关键 wrapper/FDC/RCF/sim 资产，并验证 canonical `ddr3.idf` 的 SHA-256 在生成前后不变。执行说明见 [M2-A DDR3 PG2L50H IP 重生成](doc/M2_IP_REGENERATION.md)，参数源码与差异矩阵见 [M2-B1 参数与差异审计](doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md)。

当前 staging probe 已成功生成 PG2L50H header、`DEVICE_100H_EN=false` 和 50H PPLL 分支。wrapper 新增 `ref_clk_p/ref_clk_n` 及三个状态输出，FDC 有 28 项管脚差异并使用 `DDRPHY_CPD_297_4`。因此 M2-B1 只证明“参数语义已关闭且可正确重生成”，不代表 canonical IP、板级参数或位流已获批准。

## M2-B2 staging compile-only

[`M2B2_STAGING_COMPILE.md`](doc/M2B2_STAGING_COMPILE.md) 已建立独立 PG2L50H compile 入口。runner 每次先重生成 staging，只加入 18 个示例 RTL 与 staging `ddr3.idf`，不加载 FDC/RCF，也不执行 synthesize、dev_map 或 PNR：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_staging_compile.ps1
```

最终 run `1d4b8c264ba940f0bb0e2517b8c36c07` 以 19 项 staging 输入完成 PDS compile，退出码 0、`E:` 为 0、warning 为 272、26 个顶层端口与三个核心产物均通过 gate；四个 canonical 关键输入哈希未变化。许可证 checkout 详情只保留脱敏状态文本。该结果只关闭生成资产的 compile 闭包，不授权 canonical 升格、板级约束、实现、仿真或烧录。

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

已在旧 PG2L100H 目标下从空 `build/` 执行到 `compile`：

- PDS 退出码为 0，日志没有 `E:`。
- 成功加入 18 个示例 RTL、`ddr3.idf`、FDC 和 RCF。
- 日志共有 272 条 warning；其中 `test_ddr.v:855` 有两条 BIST 错误数据端口位宽不匹配，其余告警按厂商 IP 基线保留并等待完整实现 gate 分类。

已在旧 PG2L100H 目标下继续完成完整实现：

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

这些 PG2L100H 结果与实际 PG2L50H 不一致，所有 STA 数值、网表、SDF 和位流均仅为历史证据。严格 gate 实测返回非零；显式 baseline 返回 0 也不得用于实际板卡验收。

当前仿真状态：本机已具备 Questa Sim-64 `2021.1`；DDR3 项目级行为级、综合后、PNR 后功能和 PNR 后时序仿真仍未运行。公共仿真器与 Pango 库可用性不等于 DDR3 项目验收通过。

## 当前阻断项

- 未根据实际板卡核对 DDR3 颗粒、容量、byte lane、VREF、终端、电源和 PCB 拓扑。
- 缺少经审核的板级参数清单，严格 gate 尚不能核对 IDF/FDC 与原理图的一致性。
- `rst_board` 使用 M15 share pin，且 BANKR4 的 3.3 V VCCIO 与当前放置不兼容。
- UART RX/TX 没有板级引脚和 I/O 标准约束；顶层输入/输出时序也未完整约束。
- 当前 testbench 仍连接旧版顶层已经删除的 5 个端口，无法直接 elaboration。
- 当前 BIST 持续随机读写，没有天然有限 `done`；`bist_run_led` 是翻转指示而不是完成信号。
- `test_ddr.v:855` 的 `err_data_pre`、`err_data_aft` 与 BIST 模块端口位宽不一致。
- PG2L50H staging wrapper 新增差分 `ref_clk_p/ref_clk_n` 和三个状态输出，并把 DDR core `ref_clk` 从 `free_clk` 改接差分缓冲输出；实板时钟来源和物理端口尚未确认。
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

D2 是文档决策批次，没有修改 RTL、TB、IDF、FDC 或 RCF。D3 功能实现需先完成 D3-0 的 core/wrapper、非标准 Pango DDR UI 握手和 `I_ips_ddr_top` 层级评审；D3-A 在 D3-0-M1 板级时钟拓扑关闭前不得启动。

## D3-0 只读评审结果

2026-08-30 已从旧 canonical IP 确认用户接口；2026-09-02 的 [PG2L50H staging 复核](doc/D3A_PG2L50H_STAGING_REVIEW.md) 补充了器件迁移差异：

- 公开 core 是 `ip_core/ddr3/ddr3.v` 的 `ddr3` 模块，提供 `core_clk`、`ddr_init_done`、PLL/PHY 状态以及 128-bit 用户数据通路；生成文件保持不改。
- canonical 与 staging 的 `ddr3.v` whole-file 相同；用户参数、128-bit 数据通路、AXI-like 端口和 `I_ips_ddr_top` 名称没有变化。
- 物理 wrapper 不同：staging 在旧 21 个端口上增加 `ref_clk_p/ref_clk_n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，增加 `GTP_INBUFDS`，并把 core `ref_clk` 从 `free_clk` 改接差分缓冲后的 `ref_clk`。
- 用户接口是 Pango 定制的 AXI-like 端口，而不是完整 AXI4：写地址用 `axi_awvalid & axi_awready`，写数据完成由 core 输出 `axi_wready` 表示；`axi_wusero_id`、`axi_wusero_last` 为返回标记。读地址用 `axi_arvalid & axi_arready`，读数据由 `axi_rvalid`/`axi_rlast` 返回，接口没有 `axi_rready`。
- 当前示例控制器把写 outstanding 计数与 `axi_wready` 接受次数比较，把读请求计数与 `axi_rvalid` 返回次数比较；D3-A 必须将这些事实转换为有限 BIST 的明确握手/超时契约，不得假设标准 `AWREADY/WREADY/BVALID/ARREADY/RREADY` 语义。

D3-0-M gate 已锁定上述 core/wrapper 差异及负向探针。由于 reference-clock 和物理输出合同已变化，D3-A 保持 blocked；必须先依据原理图/BOM 确认差分参考时钟、`free_clk` 职责、状态输出和 FDC/RCF，再重新审核 product wrapper、地址单位与 `axi_wready/axi_wusero_last` 语义。本次审计不等同于 D3-A 编码授权。
