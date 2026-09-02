# H2-M1 PCIe PG2L100H 恢复尝试

日期：2026-09-02

## 结论

本批已完成 PCIe 设计与 Questa 仿真资产的恢复核对，并实际尝试使用 PDS
`2022.2-SP6.4` 生成 `Logos2 / PG2L100H / FBG484 / -6` 的 staging IP。

- RTL、厂商 PCIe wrapper、RC/EP 模型、testbench、`.f/.do` 和 FDC 在外部
  `fpga_demo_100h` 资料与本仓库之间没有发现缺失或差异；无需重复复制生成物。
- Questa Sim-64 `2021.1` 已重新运行项目级 S2-A、S2-B、S2-C 入口并通过。
  这些入口使用当前活动 `pcie_test.idf`（metadata 仍为 PG2L50H），因此只
  能作为仿真入口/设计恢复证据，不能作为 PG2L100H 硬件验收。
- PDS `iplist.xml` 登记 Logos2 PCI Express `1.4/1.5/1.6`，并列出
  `PG2L100H` 与 `FBG484` 支持；但实际安装目录没有对应 `index.xml` 或
  `ips2l_pcie_gen2_v1_*.iar` 实例包。`regenerate_pg2l100h_staging.ps1 -Execute`
  在 IP Compiler 入口处按预期失败闭合，canonical IDF 未被修改。

## 外部资产核对

只读比较目录：

```text
Z:/FPGA_Resource/RK3568_MES2L50H_100H开发板资料/05-开发资料/02-FPGA开发/fpga_demo_100h/pcie_dma_test_100h
```

核对范围：`hdl/`、`ipcore/pcie_test/example_design/`、
`ipcore/pcie_test/sim/modelsim/`、`fdc/`。逐项比较结果为仓库文件与外部文件
一致；外部 PCIe `pcie_test.idf` 同样是 `1.2c / PG2L50H / FBG484 / -6`，
所以该资料不能直接升格为 100H IP。

## `parallel_driver` 分支搜索

远端分支：`origin/parallel_driver`，当前提交为
`485f3bba71e4b57fb8bb49cec30e9d331b952be3`。

该分支的 `ipcore/pcie_test/` 共 114 个文件，包含 IDF、PCIe wrapper、DMA
RTL、厂商 RC/EP 仿真模型、ModelSim filelist/DO 和示例 testbench。逐文件映射
到当前项目后，114 个文件均已存在；当前项目 `pcie_test.v` 的唯一差异是已审核
加入 `trgt1_radm_pkt_halt[2:0]` 流控端口，不能用旧分支文件覆盖。

分支 PCIe IP metadata 为：

```text
IP ID    : 042004
Version  : 1.2c
Device   : PG2L50H
Package  : FBG484
Speed    : -6
```

分支没有 `.iar`、`index.xml` 或可供 IP Compiler 重生成的完整实例包。外层
`prj/project.pds` 虽设置 `PG2L100H`，但同一分支的编译证据仍报告 PCIe IDF
器件不一致（`Flow-4058`）；因此不能把该分支的 PDS 工程、网表、SDF 或位流
作为 PG2L100H PCIe 恢复输入。分支中的 PG2L100H `ddr3_ip.idf` 是独立 DDR3
资产，与 PCIe IP 恢复无关。

## 100H IP 生成尝试

入口：`scripts/regenerate_pg2l100h_staging.ps1`

脚本只把活动 IDF 复制到 `build/ipgen/pcie_pg2l100h/` 并替换 device 字段，
不会覆盖 `ipcore/pcie_test/`。本次 `-Execute` 结果：

```text
IPGEN_RESULT=BLOCKED_MISSING_PCIE_INDEX_XML
```

失败发生在调用 `ip_generate.exe` 之前；因此没有生成候选 wrapper、RTL、仿真
模型或 100H 端口/资源证据。不得手工把 `PG2L50H` IDF 改名为 100H，也不得
把 staging 或历史 50H 产物写入 canonical 输入。

## Questa 重新验证

使用本机外部 Questa `2021.1` 和 PDS 根目录参数运行，许可证配置未写入仓库。
运行态仅写入 `build/`：

| 入口 | 本次 run id | 结果 | 边界 |
|---|---|---|---|
| S2-A `sim-behav` | `d9d3892b8b2d4c8ca5d668072778fcc6` | 退出 0，唯一 `TEST PASS` | 受控 PCIe 边界、复位和 LED，不含真实 LTSSM/DMA |
| S2-B `sim-link` | `da83a4fe9a5840dd84b57c40272cdcf1` | 唯一 `S2B_REAL_LINK_UP`、唯一 `TEST PASS`，Errors 0，Warnings 26，退出 0 | 厂商 RC 与项目 EP 仿真链路，不含 RK3568 实板 |
| S2-C `sim-dma` | `7c8bb5f4637543ae90e39823505f935f` | 唯一 `S2C_DMA_WRITE_READBACK_OK`、唯一 `TEST PASS`，Errors 0，Warnings 26，退出 0 | BAR0 固定 DWORD 诊断；BAR1 仍禁用，不是 Endpoint 主动 DMA 闭环 |

S2-B/S2-C 的厂商模型编译日志会包含本机 PDS 安装路径；这些日志属于 ignored
运行态，不得复制到文档或提交到版本库。

## 关闭条件与下一步

H2-M1 仍为 **blocked**。关闭前必须取得与 PDS SP6.4 兼容的 PCIe 实例包（或
批准的 1.4/1.5/1.6 新版本完整导出），然后在 `build/ipgen/pcie_pg2l100h/`
重新生成并审核：IDF metadata、wrapper 端口、HSSTLP 资源、仿真模型、FDC、
compile、dev_map、PNR、STA、SDF、位流及 provenance。匹配 IP 到位前，当前
Questa 通过结果继续标记为 50H 活动输入的历史/结构证据。
