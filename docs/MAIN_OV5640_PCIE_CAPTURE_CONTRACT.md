# main OV5640 DVP RGB565 采集合同

更新日期：2026-09-02

## 范围

`main_ov5640_pcie/rtl/ov5640_dvp_rgb565_capture.sv` 只负责在 `cam_pclk` 域采集源同步 DVP 数据，并把连续两个 8-bit 样本拼成一个 RGB565 像素。它不负责 SCCB、RESET/PWDN、MCLK 生成、CDC、FIFO、图像处理、DDR3 或 PCIe。

## 输入语义

- `cam_pclk`：采样时钟，输入数据在上升沿被采样。
- `cam_href`：高有效行数据窗口；窗口关闭时丢弃数据并清除半像素状态。
- `cam_vsync`：可配置有效电平的帧边界标记。有效沿到来时，当前已观察帧产生 `frame_end`，下一条有效像素开始新帧。
- `cam_data[7:0]`：每个 `cam_pclk` 携带一个字节；默认第一个字节为 RGB565 高字节。

## 输出语义

- `pixel_valid`：在第二个字节采样后的一个时钟周期脉冲；同周期 `pixel_data`、`pixel_x`、`pixel_y` 有效。
- `frame_start`：首个有效像素与 `pixel_valid` 对齐，只在帧首像素产生一次。
- `line_start`：每个 HREF 行的首个有效像素与 `pixel_valid` 对齐。
- `line_end`：HREF 关闭后的一个时钟周期脉冲；若行没有完整像素则不产生该事件。
- `frame_end`：下一帧 VSYNC 有效沿到来的时钟周期脉冲；首个 VSYNC 标记不关闭前一帧。
- `protocol_error`：HREF 关闭时仍有未配对字节，或坐标计数达到 16-bit 上限。

## 验证边界

行为级 TB 必须检查 RGB565 字节拼接、像素坐标、帧/行起始、行结束、下一帧结束和半字节错误。该 TB 不证明 OV5640 寄存器配置、板级电气时序、跨时钟域安全或 PDS 时序收敛。
