bitstream_2026-09-10/
======================
新比特流（当前源码原样编译，零 RTL 改动）——用于 RK3568 链路点亮。

  top.sbit                                  烧录文件 (PG2L100H, 2026-09-10 23:48 生成)
  top.smsk                                  掩码文件
  top_timing_summary_after_hold_fix.txt     时序摘要

要点:
- 编译: project_build/ 副本目录隔离编译, pds_shell -run gen_bit_stream, 24.5min, 退出码 0
- 时序: 除 PCIe IP 内部 pclk 域 2 端点 -0.192ns (IP 接收头 RAM, 基线 +0.923, 布线种子
  噪声) 外全部收敛; 链路点亮可用, 量产前建议 GUI 换 seed 重收敛
- 注意: 主工程 project/generate_bitstream/top.sbit 仍是【旧比特流】, 勿误烧!
- 主机侧点亮流程见 DOC/RK3568_新比特流点亮指南.md
