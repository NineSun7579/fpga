# PDS Tcl 入口清单与执行边界

日期：2026-08-30

## 目的

仓库保留了 PDS GUI 操作记录、厂商 IP 内部脚本、仿真辅助脚本和项目自有构建脚本。文件扩展名相同不代表用途相同，旧脚本中的 PG2L50H、PGL25G 或绝对路径也不能被当作当前 PG2L100H 发布输入。

机器可读事实位于 [`PDS_TCL_ENTRYPOINT_INVENTORY.json`](PDS_TCL_ENTRYPOINT_INVENTORY.json)，检查入口为：

```powershell
powershell.exe -ExecutionPolicy Bypass `
    -File .\scripts\check_pds_tcl_entrypoints.ps1
```

仓库级 [`check_repo_consistency.ps1`](../scripts/check_repo_consistency.ps1) 会自动调用该门禁。

## 角色

| 角色 | 含义 | 可由项目 `run.ps1` 调用 |
|---|---|---|
| `canonical_project_build` | 当前项目自有、相对路径、目标器件正确的构建入口 | 是 |
| `migration_blocked_project_build` | 项目自有可重复入口，但器件迁移尚未完成，只能复现历史基线 | 是，但不得声明发布 |
| `canonical_support_tool` | 仓库或项目支持工具，不是 canonical 项目实现入口 | 否 |
| `historical_gui` | PDS GUI 操作记录或 compile screen，仅作历史证据 | 否 |
| `vendor_generated_internal` | 厂商 IP 内部生成/PNR 记录，不代表外层工程 | 否 |
| `vendor_sim_internal` | 厂商单 IP 仿真辅助脚本，不代表集成仿真 | 否 |

`canonical_project_build` 只表示入口身份正确，不代表功能、板级约束、STA、仿真或位流已经发布通过。

## 当前项目入口

| 项目 | `run.ps1` 实际入口 | 当前角色 | 器件事实 |
|---|---|---|---|
| DDR3 bring-up | `ddr3_test/ddr3_test/scripts/build.tcl` | `canonical_project_build` | 原生 PG2L100H；等待板级参数复核 |
| PCIe DMA | `pcie_dma_test_100h/scripts/build.tcl` | `migration_blocked_project_build` | 已恢复 100H 目标，但活动 IP 仍为 PG2L50H |

两个现有项目 `run.ps1` 均只调用同目录 `scripts/build.tcl`。仓库没有 canonical 调用链引用任何历史 `impl.tcl`、parse-design screen 或 IP 内部脚本。

DDR3 的 `scripts/build_staging_compile.tcl` 是 M2-B2 compile-only 支持工具：只验证 PG2L50H staging 的 18 个示例 RTL 与一个 IDF 能完成 `compile`，不加载 FDC/RCF，不执行实现后级，也不改变 DDR3 canonical 项目入口仍受 M2 升格阻断的事实。

## 历史与厂商脚本

以下事实必须保留，而不是文本替换：

- PCIe 根 `impl.tcl` 同时记录 PG2L50H 与 PG2L100H，并含旧机器绝对路径。
- DDR3 IP 内部 `pnr/impl.tcl` 同时记录 PG2L50H 与 PG2L100H；它只能证明厂商 IP 历史，不能证明外层工程目标。
- DDR3 根 `impl.tcl`、三份 parse-design screen 和两份 `ctrl_phy_sim.tcl` 虽无 `set_arch`，仍包含旧绝对路径，因此同样必须分类。
- `scripts/compile_simlib.tcl` 的 `C:/questasim64/win64` 是可由环境变量覆盖的默认值，不属于项目源码或器件绑定。

历史/厂商脚本不得用于以下任何证据：

1. 当前器件身份。
2. 当前项目输入清单。
3. STA、SDF、网表或位流签核。
4. 集成级 ModelSim/QuestaSim 通过声明。

## CI-7 门禁

门禁执行以下检查：

1. Git 当前 tracked Tcl 与 JSON 清单必须完全相等；新增或漏登记文件均失败。
2. 每个文件的角色、`set_arch` 次数、器件集合和绝对路径事实必须与清单一致。
3. 只有 DDR3 与 PCIe 两份项目 `scripts/build.tcl` 可标记 `run_ps1_entry=true`。
4. `canonical_project_build` 必须只使用 `PG2L100H`，且不得包含盘符或 UNC 绝对路径。
5. `migration_blocked_project_build` 必须仍明确包含 PG2L100H，并不得被误写成发布入口。
6. 历史 GUI 与厂商内部脚本不得标记为 `run_ps1` 入口。
7. 公共 `compile_simlib.tcl` 必须继续通过环境变量提供外部仿真器路径覆盖。
