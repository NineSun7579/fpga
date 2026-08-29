# OV7725 HDMI 工程状态

## 当前定位

本工程采集 OV7725 RGB565 数据，经两个异步 FIFO 和 DDR3 帧缓存后，以 1024×768 时序输出 HDMI/TMDS。

当前器件审计目标为：

```text
Logos2 / PG2L100H / FBG484 / -6
```

现有 PDS 工程和报告由较旧的 PDS/IP 版本生成，且 `prj/impl.tcl` 含历史绝对路径；它们只作为现状证据，不是后续可重复构建入口。

## 当前状态

- 旧实现生成了非零 `.sbit`，但最终报告为 `Some Constraints Violated`。
- 慢角 setup 最差 WNS 为 `-7.056 ns`，对应 `pixel_clk → ui_clk` 的 `video_vs/rd_load` 业务跨域。
- read FIFO 内部指针路径 WNS 为 `-2.279 ns`，需要按厂商异步 FIFO 方法学核验。
- 慢角 recovery 最差 WNS 为 `-4.857 ns`，对应 `ui_clk` 域 `ddr3_init_done` 进入 pixel 域异步复位。
- 尚未建立 PDS 2022.2-SP6.4 相对路径构建脚本，也未运行项目级四级自检仿真。

## CDC/RDC 决策

完整清单见 [CDC/RDC 审计与整改契约](doc/CDC_RDC_AUDIT.md)。后续实现必须遵守：

1. 每个时钟域独立进行异步置位、同步释放。
2. `ddr3_init_done` 作为同步状态/使能，不直接组合到异步复位脚。
3. `wr_load`、`rd_load` 各自只建立一个跨域接收点，再在 `ui_clk` 域扇出。
4. 两个厂商异步 FIFO 保持原样，分别处理读写侧复位；只对核验后的内部同步路径添加精确例外。
5. 不使用覆盖整个模块或时钟域的宽泛 `false_path`。

## 下一步

下一批 O0-B 将建立：

- 相对路径 `scripts/build.tcl`；
- PowerShell 构建入口和日志 gate；
- 明确的 15 个手写 RTL、4 个 IP 和唯一 FDC 输入清单；
- 从干净 `build/` 执行的 SP6.4 compile 基线。

O0-B 不修改功能 RTL。进入 O1 后，新增或修改的手写 RTL/TB 必须遵守根目录 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`。
