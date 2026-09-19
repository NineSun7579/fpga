# bitstream_2026-09-16_dualcam

FMC 双目 OV5640（cam1/cam2，各 1280×720 RGB565）→ RK3568 HDMI 并排显示。

- `top.sbit` — FPGA 比特流（PG2L100H-6FBG484）
- `top_timing_summary.txt` — PDS 时序摘要（`Design Summary : All Constraints Met`）

关键时序（Slow corner）：
- `cmos1_pclk` WNS 9.369 ns（约束 20.833 ns / 48 MHz）
- `cmos2_pclk` WNS 9.288 ns（约束 20.833 ns / 48 MHz）
- `ddrphy_sysclk` WNS 0.948 ns

全流程编译耗时约 5m13s，无 `E:` 错误。

改动与上板步骤见 `DOC/交付说明_FMC双目_2026-09-16.md`；
寄存器/DDR 映射见 `DOC/FPGA_RK3568_传输协议_v1.md` §3.4。
