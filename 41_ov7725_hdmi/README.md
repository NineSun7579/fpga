# OV7725 HDMI 工程状态

## 当前定位

本工程采集 OV7725 RGB565 数据，经两个异步 FIFO 和 DDR3 帧缓存后，以 1024×768 时序输出 HDMI/TMDS。

当前器件审计目标为：

```text
Logos2 / PG2L100H / FBG484 / -6
```

`prj/impl.tcl` 含历史绝对路径和旧器件操作，只作为现状证据。当前可重复构建入口为 `scripts/build.tcl` 和 `scripts/run.ps1`。

## 当前状态

- 已从空 `build/` 在 PDS 2022.2-SP6.4 下完成七阶段实现，退出码为 0，日志无 `E:`。
- 构建固定 16 个手写 RTL、4 个活动 IDF 和唯一 FDC，不依赖 `prj/impl.tcl`、`ip_backup/**` 或 IP 内部生成 RTL。
- 最终报告仍为 `Some Constraints Violated`：慢角 setup 最差 WNS `-7.344 ns`、TNS `-132.832 ns`；read FIFO 指针路径 WNS `-2.275 ns`、TNS `-24.111 ns`；recovery 最差 WNS `-4.263 ns`、TNS `-202.445 ns`。
- 完整日志包含 81 条 critical 和 4105 条 warning；其中有 39 条手写 RTL 端口位宽告警、88 条 `STA-3011`、4 条 `SDC-2025`、3 条 `Route-2036` 和 72 条 share-pin critical。
- 已生成非零综合网表、PNR 网表、slow-corner SDF、`.sbit` 和 `.bin`。
- 严格 gate 会因已知发布阻断返回非零；显式 baseline 模式仅证明当前失败基线可重复，并明确标记不可发布。
- 本机尚无 ModelSim/QuestaSim，因此项目级四级自检仿真未运行。

## 构建与检查

```powershell
# 从空生成目录执行完整实现。
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
    -Action clean-build
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
    -Action build `
    -RunTo gen_bit_stream

# 严格模式：当前预期返回非零。
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
    -Action check-build `
    -RunTo gen_bit_stream

# 基线模式：预期返回 0，但明确不可发布。
powershell.exe -ExecutionPolicy Bypass -File .\scripts\run.ps1 `
    -Action check-build `
    -RunTo gen_bit_stream `
    -AllowKnownBaselineIssues
```

## CDC/RDC 决策

完整清单见 [CDC/RDC 审计与整改契约](doc/CDC_RDC_AUDIT.md)。后续实现必须遵守：

1. 每个时钟域独立进行异步置位、同步释放。
2. `ddr3_init_done` 作为同步状态/使能，不直接组合到异步复位脚。
3. `wr_load`、`rd_load` 各自只建立一个跨域接收点，再在 `ui_clk` 域扇出。
4. 两个厂商异步 FIFO 保持原样，分别处理读写侧复位；只对核验后的内部同步路径添加精确例外。
5. 不使用覆盖整个模块或时钟域的宽泛 `false_path`。

## 下一步

下一批 O1-A 只做 RTL 卫生修复方案评审：逐条归属 39 条位宽告警、隐式网络和 `serializer_10_to_1.reset_n` 问题，形成最小修改清单后提请审核。

未经审核不进入 O1-B，也不修改 RTL/IP/FDC/RCF。后续新增或修改的手写 RTL/TB 必须遵守根目录 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`。
