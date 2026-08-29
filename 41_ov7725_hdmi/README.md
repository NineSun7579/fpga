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
- O1-B 已消除 38 条确定性手写 RTL 位宽告警；当前仅保留 `ddr3_ip.mem_a` 的 15→14 bit 板级冲突，等待 H3/O1-C。
- O1-B 已显式声明 `rst_n`、删除无消费者 `sys_init_done`，并把四个 serializer 内八个 OSERDES 接入高有效复位。
- 最终报告仍为 `Some Constraints Violated`：慢角 setup 两组失败分别为 `-6.965 ns / 20/20` 和 `-2.273 ns / 11/11`；原有 DDR/FIFO recovery 为 `-4.957 ns / 53/53`。
- 接入 OSERDES 复位后新增一组慢角 recovery：`pixel_clk → pixel_clk_5x`，WNS `-0.643 ns`、TNS `-4.191 ns`、8/8 端点；详细端点正好是八个 OSERDES，转入 O2/RDC 修复。
- O2-A 已完成 [Serializer Reset 联合释放契约](doc/SERIALIZER_RESET_CONTRACT.md)：首选 O2-B 保留 encoder 的 `pixel_clk` reset，再级联 `pixel_clk_5x` 两级释放，仅驱动八个 OSERDES；该结构尚未实施或通过 STA。
- 完整日志包含 81 条 critical 和 4067 条 warning；其中仅 1 条项目手写 RTL 位宽告警，另有 88 条 `STA-3011`、4 条 `SDC-2025`、3 条 `Route-2036` 和 72 条 share-pin critical。
- 已生成非零综合网表、PNR 网表、slow-corner SDF、`.sbit` 和 `.bin`。
- 严格 gate 会因已知发布阻断返回非零；显式 baseline 模式精确核对 7 组 `corner/check/clock pair/endpoints` 失败指纹，只证明当前失败基线可重复，并明确标记不可发布。
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

O1-B 已按 [RTL 卫生修复评审](doc/RTL_HYGIENE_AUDIT.md) 实现并完成七阶段回归。下一批拆为：

1. O2-A：已完成 [Serializer Reset 联合释放契约](doc/SERIALIZER_RESET_CONTRACT.md)，并将 `serializer_b/g/r/clk × master/slave` 八个 endpoint 唯一映射到 `opit_2/opit_2_com`。
2. O2-B：下一批仅修改 `dvi_transmitter_top.v`，保留 encoder 的 `pixel_clk` reset，再级联 `pixel_clk_5x` 两级释放生成 serializer reset；必须用完整 STA 同时证明 `OCLK`、`SERCLK`、`OCLKDIV` 检查非负。
3. O3-A → O2-C1：先同步 `ddr3_init_done` 作为 camera/pixel enable，再处理 sys、I2C、camera、pixel、DDR UI 等普通时钟域本地复位。
4. O2-C2：单独依据厂商 FIFO reset/flush 语义处理两个异步 FIFO 的读写侧复位。
5. O3-B → O4：修复两条帧事件 CDC；只有 O2-C2 与 O3-B 都完成后才进入约束和最终时序闭环。

O2 不修改 `mem_a`、DDR3 IP 或板级 FDC，不通过 `false_path` 掩盖 recovery。新增或修改的 RTL 注释必须遵守根目录 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`；QuestaSim 未就绪前不声明 HDMI 动态复位或串化功能通过。
