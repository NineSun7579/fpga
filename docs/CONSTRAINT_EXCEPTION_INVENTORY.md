# 约束例外精确清单

更新日期：2026-09-02

机器清单见 [`CONSTRAINT_EXCEPTION_INVENTORY.json`](CONSTRAINT_EXCEPTION_INVENTORY.json)，
漂移门禁见 [`check_constraint_exceptions.ps1`](../scripts/check_constraint_exceptions.ps1)。

## 1. 结论边界

当前三个入口 FDC 共有 15 条 timing exception，另有一条 OV7725 legacy
`PAP_CLOCK_DEDICATED_ROUTE FALSE`：

| 工程 | 入口角色 | Timing exception | Dedicated-route override | 审核状态 |
|---|---|---:|---:|---|
| DDR3 | canonical，但仍是旧 PG2L100H 输入 | 6 | 0 | vendor-generated / unreviewed |
| PCIe | 当前 PG2L50H canonical | 3 | 0 | vendor-derived / unreviewed |
| OV7725 | frozen legacy | 6 | 1 | legacy / not approved |
| 双 OV5640 | 尚未创建 canonical FDC | 0 | 0 | H3 blocked |

“已登记”只证明文件、命令、对象、来源与状态可追溯，不表示：

- 例外合理或已批准；
- PDS 能解析到预期对象；
- CDC/RDC 结构正确；
- STA、板级实现、位流或发布通过。

## 2. 纳入与排除

纳入：

- `set_multicycle_path`
- `set_clock_groups`
- `set_false_path`、`set_max_delay`、`set_min_delay`、`set_disable_timing`
  若后续出现也必须登记
- `PAP_CLOCK_DEDICATED_ROUTE`，但作为独立 override 类型

排除：

- 注释行和空章节；
- 普通 `PAP_IO_UNUSED`；
- DDR3 外层旧副本、PCIe IP example FDC 和 OV7725 constraint backup；
- `origin/parallel_driver@485f3bb` 的双 OV5640 参考 FDC。它只用于 C0 审计，
  不能计入当前产品清单。

## 3. 漂移门禁

门禁对当前入口执行以下检查：

1. 文件路径、LF 规范化 SHA-256 和 Git index blob 与清单一致，避免 Windows
   checkout 的 CRLF 差异造成误报；
2. 构建入口仍引用登记的 FDC；
3. 实际命令 multiset 与 JSON 的 `kind + normalized_command` 完全一致；
4. 双 OV5640 在 C1/H3 关闭前仍无 FDC、PDS 构建入口；
5. Tcl 续行、分号多命令或 `source` 会直接失败，避免简化解析器静默漏项。

`-SelfTest` 先证明仅 CRLF checkout 差异仍通过，再覆盖新增未登记 exception、修改
既有命令、双 OV5640 过早出现 FDC，以及 `source`、Tcl 续行、分号多命令的
fail-closed 样本。JSON 行号只用于诊断；稳定比较主键是命令类型与规范化命令，
同时由全文哈希锁定其余文件内容。

## 4. 后续审核

- DDR3 canonical 升格 PG2L50H 后，必须重新生成清单并以 PDS 报告确认对象命中；
  不能复制旧 100H 例外。
- PCIe 三条 async group 需要结合产品 CDC 与 PDS `report_exceptions` 等证据审核。
- OV7725 条目保持冻结，只作为双 OV5640 的反例和风险输入。
- 双 OV5640 必须在 H3 输入、PG2L50H IP/FDC 与时钟域冻结后独立建立清单；
  不继承 OV7725 或参考分支的 dedicated-route override。
