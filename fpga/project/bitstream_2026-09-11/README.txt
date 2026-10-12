bitstream_2026-09-11/
======================
新比特流: prep_regs 寄存器集成 + upsample 行终止修复 + Route-0008 根因修复
(相对 09-10 的 RTL 变更: top.v 集成 ovreg_axil_decode+prep_regs、
 scale_mul_unsign_s3.v 去除误复制属性、upsample_in_buf.v 行终止修复、
 23+15 个 NPU 文件 [sim-compat] 声明前移)

  top.sbit       烧录文件 (2026-09-11 23:06 生成, 全流程 46 分钟, 布线成功)
  top.smsk       掩码文件
  top_timing_summary_after_hold_fix.txt  时序摘要

时序: **全部时钟域收敛** (pclk +1.157 / pclk_div2 +0.775 / ddrphy +0.683 /
clk_150m +0.808 等, 09-10 的 pclk -0.192 违例消失)

主机可见变化 (相对 09-10 比特流):
- PREP/INJ 寄存器组上线: AXI 地址 0x2000_0000+0x100 ~ +0x17C, 经 DMA 读写
  (值放 16 字节传输 byte0~3)。寄存器级实现: 回读位精确, 阈值图像功能待
  像素通路集成 (第二阶段)。
- upsample 输出行终止修复 (NPU 内部, 主机无感)

注意:
- 主工程 project/project.pds 尚差一行注册 (PDS GUI 当时开启, 为避免回写未改;
  GUI 关闭后把 project_build/project.pds 中 ovreg_axil_decode.v 的 _file 块
  抄入主工程即可)。
- 构建复现: project_build/ 下 pds_shell -run gen_bit_stream
