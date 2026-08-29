# 实施记录

## 2026-08-29：建立基线

- 创建根提交 `1a2d493`，保存三个原始 PDS 工程、现有报告、指南和整改 TODO。
- 本机 PDS：`2022.2-SP6.4 build 146967`。
- 默认位置未找到 ModelSim/QuestaSim，外部仿真暂不可执行。
- 明确以 PCIe 工程作为公共流水线基准，因为其现有内部时序已通过。
- 明确 PCIe 的 `impl.tcl` 是 GUI 操作历史，不作为重建入口。
- 明确 PCIe 有效输入为 37 个用户 RTL、`pcie_test.idf` 和 `pcie_dma_test.fdc`。
- PCIe IP 的 IDF 仍记录旧器件 PG2L50H，而顶层工程为 PG2L100H；后续需重新生成或形成有证据的偏离记录。
- PCIe UART2APB 使用未声明顶层端口的隐式 `rxd/txd`；在硬件接口决策前不猜测管脚，也不修改功能 RTL。

## 当前下一步

1. 建立 PCIe 相对路径 `build.tcl` 和 PowerShell 入口。
2. 先执行 compile-only 重建，验证输入清单与脚本语法。
3. 再执行完整 PDS 流程并从新 `build/` 目录读取时序、网表和位流证据。
4. QuestaSim 可用后再实现并放行四级集成仿真。

## 2026-08-29：PCIe 首次 compile-only 探测

- 新相对路径脚本成功加载 37 个用户 RTL、PCIe IDF 和 FDC，并完成 compile。
- 新日志再次确认两个已知阻断项：PCIe IDF 的器件仍为 PG2L50H；UART `rxd` 无驱动并被绑为 0。
- PDS 在读取 Tcl 时会预解析未执行的后续命令。本次发现 `max_parallel_jobs`、synthesis/dev_map 的 `top_module`、`verilog_2001` 和 `number_of_router_thread` 对当前器件不受支持。
- 更重要的是，上述预解析错误出现时，`pds_shell.exe` 最终仍返回 0。PowerShell 入口因此增加日志 `E:` 扫描，不能只信任进程退出码。
- 删除不支持选项并增加 `E:` 门禁后，已清理 `build/` 并重新执行 compile-only；新日志没有 `E:`，compile 在约 12 秒内完成。
- 当前仍保留并明确暴露 PG2L50H IDF 与无驱动 UART `rxd` 两项 warning。compile-only 通过不构成完整构建或功能验收。

## 2026-08-29：PCIe 完整重建

- 使用新相对路径脚本完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，总耗时约 3 分 30 秒，日志无 `E:`。
- 新最终时序报告为 `All Constraints Met`；慢角 setup 最差 WNS `0.584 ns`、TNS `0`，慢角 hold 最差 WHS `0.138 ns`。
- 新生成 `pcie_dma_test_sim.v`（约 10.6 MiB）和 `pcie_dma_test_sta.sdf`（约 8.2 MiB），关闭了“没有 PNR 网表/SDF”的构建资产缺口；尚未用 QuestaSim 验证 SDF 层级。
- 新生成 `pcie_dma_test.sbit` 和 `pcie_dma_test.bin`，均非零。
- 新发现位流关键配置缺口：PDS 报告 SCBV 未设置。必须依据 PCB 配置 bank 电压后才能把位流视为发布候选。
- 新增严格 `check_build.ps1`：检查日志 `E:`、时序、SDF/网表/位流，并把 PG2L50H IDF、UART死通道、未约束 I/O、share pin 和 SCBV 列为发布阻断项。
- 提供 `-AllowKnownBaselineIssues` 仅用于确认旧设计可重复构建；该模式不得作为发布 gate。
- 已验证 gate 的两个分支：严格模式因 6 类已知阻断项返回非零；显式允许历史问题时，时序与四类非零产物检查通过并返回 0。
- gate 首次执行暴露 PowerShell 续行符误用；修正后重新验证两个分支，未保留未经测试的实现。
