# main OV5640 RGB565 图像处理合同

更新日期：2026-09-02

## 范围

`rgb565_grayscale` 只负责把输入 RGB565 像素转换为灰度 RGB565；`ov5640_dvp_rgb565_pipeline` 只负责连接 M1-A 采集模块和该处理模块。两者均运行在 `cam_pclk` 域，不负责 SCCB、MCLK、RESET/PWDN、CDC/FIFO、DDR3、PCIe 或主机协议。

## 算法与时序

- RGB565 分量先扩展为 8 bit：R[15:11]、G[10:5]、B[4:0]。
- 灰度值使用整数近似 `Y=(77*R+150*G+29*B)>>8`。
- `Y` 复制到 R/G/B 字段，输出仍为 RGB565。
- `pixel_valid`、像素坐标、帧/行事件和 `protocol_error` 均延迟一个 `cam_pclk`；不提供背压。
- `pixel_data` 在输出无效周期为 `16'h0000`。

## 验证边界

M2-A TB 从公开 DVP 输入驱动两行四像素，检查黑、红、绿、蓝样本的灰度结果、坐标、帧/行事件保持和奇数字节错误。系数、分量扩展或寄存器级数变化必须同步更新 TB 参考值。该 TB 不证明传感器配置、板级时钟、电气时序、跨域、DDR3 或 PCIe。
