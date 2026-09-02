# DDR3 D3-0-M：PG2L50H staging 接口复核

状态：审计完成；D3-A 继续 blocked。更新日期：2026-09-02。

本批复核 PDS `2022.2-SP6.4` 为实际 `PG2L50H-6IFBG484` 生成的 DDR3 staging，确认 D3-A 能否继续沿用旧 canonical core/wrapper 合同。范围只包含生成资产的只读比较、门禁和文档，不升格 `ip_core/ddr3`，不修改 RTL、FDC、RCF 或 IP。

## 输入与验证入口

- 目标：`Logos2 / PG2L50H / FBG484 / -6`。
- staging：`build/ipgen/pg2l50h/`，由 `scripts/regenerate_ip.ps1` 生成且不提交。
- 动态 compile 基线：M2-B2 run `1d4b8c264ba940f0bb0e2517b8c36c07`。
- 门禁：`scripts/check_d3a_staging_contract.ps1`。

```powershell
powershell -ExecutionPolicy Bypass -File `
  .\scripts\check_d3a_staging_contract.ps1 -SelfTest
```

该命令只读取 canonical 和 staging 文件。`-StaticOnly -SelfTest` 可在没有生成目录的 clone 中验证文档、canonical 边界和负向探针。

## 复核结果

### DDR3 core 用户接口

canonical 与 PG2L50H staging 的 `ddr3.v` whole-file SHA-256 均为：

```text
FC62AE63F96F45F602D26E7967FF17A236AD66825844ECBA13383428D166A697
```

因此当前生成器没有改变公开 core module header、参数或用户接口：

- `MEM_ROW_WIDTH=15`、`MEM_COLUMN_WIDTH=10`、`MEM_BANK_WIDTH=3`、`MEM_DQ_WIDTH=16`、`MEM_DQS_WIDTH=2`；
- `CTRL_ADDR_WIDTH=28`、用户数据宽度 128 bit；
- 保留 `axi_wready`、`axi_wusero_last`、`axi_rvalid/axi_rlast`、`ddr_init_done` 和 `core_clk`；
- 仍不存在 `axi_rready`。

源码一致只证明端口和结构未漂移，不能证明地址单位、`axi_wready` 完成语义、`axi_wusero_last` 必要性或初始化稳定时序已经由厂商文档确认。

### 物理 wrapper 差异

旧 canonical `test_ddr.v` 有 21 个顶层端口，PG2L50H staging 有 26 个。staging 只新增以下五个端口，没有删除旧端口：

| 方向 | 新端口 | 观察到的用途 | 审核状态 |
|---|---|---|---|
| input | `ref_clk_p` | `GTP_INBUFDS.I` | 板级差分时钟来源、频率、电压和管脚未确认 |
| input | `ref_clk_n` | `GTP_INBUFDS.IB` | 同上 |
| output | `pll_lock` | DDR core 状态 | 是否成为物理调试输出未决定 |
| output | `ddrphy_cpd_lock` | DDR PHY 状态 | 是否成为物理调试输出未决定 |
| output | `ddr_init_done` | DDR 初始化状态 | 是否成为物理调试输出未决定 |

staging 新增：

```text
GTP_INBUFDS refclk_inbuf
  ref_clk_p/ref_clk_n -> ref_clk
```

`I_ips_ddr_top` 名称和除参考时钟外的连接集合保持一致；唯一连接变化为：

```text
canonical: .ref_clk(free_clk)
staging:   .ref_clk(ref_clk)
```

这说明 50H staging 的物理参考时钟拓扑发生了真实变化，不能把 `free_clk`、`ref_clk_p/n` 或新增状态输出视为可互换命名。

## 决策

D3-0-M 审计完成，但结论是停止 D3-A，而不是授权编码。继续实施前必须关闭：

1. 实板是否向 FPGA 提供 DDR 专用差分 `ref_clk_p/ref_clk_n`，以及频率、管脚、bank VCCIO、标准和时钟能力。
2. `free_clk` 在产品顶层中的真实来源、频率和职责；不得再默认同时作为 DDR core `ref_clk`。
3. `pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done` 是保留为内部状态，还是占用实际 FPGA 输出管脚。
4. 根据最终时钟拓扑重建 PG2L50H FDC/RCF，并重新执行 compile、CI-6、综合和 STA。
5. 取得 IP 文档或等价一手证据，确认地址单位和 `axi_wready`/`axi_wusero_last` 事务语义。

在上述事项关闭并单独审核前，不新增 `ddr3_bringup_top.sv` 或 `ddr3_finite_bist.sv`，不修改 canonical PDS 顶层，也不把 M2-B2 compile 结果外推为板级、BIST、Questa 或发布证据。

## VSCS 边界

本批未修改 Verilog/SystemVerilog，VSCS 代码注释检查不适用。未来项目自有 top/BIST 必须按 VSCS 1.0.0 记录 DDR reference clock、`core_clk`、复位链、初始化前置、AXI-like 事务假设和 watchdog hazard；厂商生成 wrapper 中的旧作者/History 注释不作为项目自有合规模板。
