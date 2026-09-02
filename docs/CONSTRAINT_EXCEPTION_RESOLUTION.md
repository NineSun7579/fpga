# PCIe 约束对象解析审计

本批 CI-10A 只验证 `pcie_dma_test_100h/fdc/pcie_dma_test.fdc` 中对象是否能被 PDS 解析：三只时钟对象、三组异步时钟组，以及 `report_exceptions` 的可执行性。它不批准任何 timing exception，也不改变 FDC、RTL、IP 或 gate。

## 运行方式

在已加载 PCIe 工程并完成 `compile` 的 `pds_shell` 会话中执行：

```powershell
$env:PCIE_CONSTRAINT_PROBE_OUT = 'build/logs/pcie-constraint-object-probe.txt'
& 'E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe' `
  -file 'pcie_dma_test_100h/scripts/probe_constraint_objects.tcl' `
  -work_dir 'pcie_dma_test_100h/build/pds-constraint-probe' `
  -project_name pcie_constraint_probe
```

若工具版本不提供 `get_clock_groups`，日志必须明确记录命令不支持；不得以空结果解释为对象未命中。运行时许可证和安装路径只通过本机环境提供，不写入仓库。

## 审核判据

- `CLOCK ... COUNT` 对 `pclk`、`pclk_div2`、`ref_clk` 均为 1，且对象路径与 FDC 的 `get_pins` 目标一致。
- 三个 `CLOCK_GROUP` 均能解析；输出为空、数量异常或命令错误均为阻断。
- `report_exceptions` 能执行并产生文本；报告中的 exception 仍需结合 CDC/RDC、STA 和板级资料单独审核。
- 仅当上述证据、完整 PDS 构建和时序分析均通过后，才可讨论例外是否需要保留；本批不提供 waiver。

## 当前状态

仓库已提供可复现 probe，但尚未在本机生成新的 PDS 解析结果。CI 静态门禁不具备 PDS license 和工程数据库，因此不会伪造动态通过证据。
