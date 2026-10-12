# 源诊断物理构建 01

独立路径：`board_v7/source_diagnostics_build_01`。只复制冻结 V7 inputs/rtl，替换诊断 top/camera/binding，并登记候选 bus/source。保持原始全部六个 FDC、DDR 131.25 MHz、RAW 六路、motion、COOP/CAPL 和 PCB 引脚。没有登记 CDC boundary 候选，没有烧录或远程命令。

已执行：

```text
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/prepare.py
python project/fpga_v8_migration/board_v7/source_diagnostics_build_01/run_stages.py
```

阶段命令为 `C:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe -project <本目录>/project.pds -run compile|synthesize -work_dir <本目录>`。每次启动均保存 `Get-Process pds,pds_shell` 的空结果；禁止其他会话并行启动 PDS。

最初两次工程解析失败（Flow-0130）已分别封存于 `attempt_01_project_syntax_failure` 和 `attempt_02_project_timespec_failure`。PDS 文件项必须包含格式和 timespec；第三次启动修正该格式，没有修改任何 RTL/FDC。后台运行的阶段以 `flow_result.json`、`controller.log`、`compile_shell.log`、`synthesize_shell.log` 为准；本文件不预判结果。

仿真 600 warnings 的逐条内容及三项额外连接改动记录在 `connection_review.json`；LEN 相关消息另列 `warning_connection_risks.json`。AW/W 同时提交、M00 写返回接零、S00 LEN 零扩展来自已验证候选，没有额外修改。600 warnings 未整体豁免，真实 PCIe/DDR 数据流仍未物理证明。

物理约束门槛未关闭：`clock.fdc` 对四个 PCLK 和 ddrphy_sysclk 全局 asynchronous 分组。必须用实际综合 cells/pins 证明 mailbox→host_bank 的 max_delay（不大于两个 AXI 周期，15.238 ns）生效，且未被组间例外屏蔽；request/ack/overrun 首级、cr/hr/reset_pipe 异步置位同步释放和 negedge 半周期路径也须审查。官方手册仅明确 set_max_skew 能高于异步分组；skew 不能替代绝对最大延时。

`export_synthesis.py` 在综合完成、无 PDS 进程后只读导出综合 DB，供实际对象解析和命令支持审查。未通过约束门槛前，不进入 PNR。若通过，再运行 PNR、复用 V7 final-export 验证十组 Slow/Fast setup/hold/recovery/removal/min-pulse-width 全零失败，并比较 physical pin/HSST/motion 资源。当前未声明 bit/STA/PNR 通过。
