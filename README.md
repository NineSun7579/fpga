已完成的项
- 双 OV5640
- DDR3 控制器和 DDR3 IP
- RGB565 到 128-bit 打包
- BAR2 视频数据窗
- PCIe DMA 控制器
- PCIe x2 Endpoint
- HSSTLP PHY
- PCIe 外部 RAM
- UART-to-APB 控制路径
当前没有 Compile error。
已验证的数据面
PASS: dual OV5640 RGB565 capture loop complete
PASS: RGB565 to AXI128 and BAR2 frame buffer verified
当前仍未完成的项
完整的 OV5640 -> DDR3 -> PCIe Memory Write 联合 ModelSim 尚未完成。
原因是现有 PCIe DMA 需要通过 BAR1 写入以下控制寄存器才会发出 Memory Write：
BAR1 + 0x100 : DMA 命令与长度
BAR1 + 0x110 : 目标物理地址低 32 位
BAR1 + 0x120 : 目标物理地址高 32 位
现阶段硬件数据路径已经接通，但没有给 DMA 自动配置这些寄存器。按你的要求，RK3568 协议暂不处理，所以目前没有定义最终的目标物理地址和帧分段传输策略。
下一步可以建立 ModelSim 集成 testbench，模拟 BAR1 寄存器写操作，驱动一次小尺寸帧的 PCIe Memory Write，并检查：
DDR3 read data
-> RGB565 packer
-> BAR2 window
-> PCIe DMA MWR TLP
PDS 工程当前已经能继续进入 Synthesize，但在没有补齐 RK3568 板级 PCIe/DDR3/摄像头实际引脚约束之前，不应生成可烧录的最终 bitstream。
