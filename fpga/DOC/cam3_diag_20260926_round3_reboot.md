# cam3 / 三路显示 现场记录（2026-09-26 第三轮：reboot 复位与 cam2 掉线）

## 1. `reboot` 的作用边界（实测）
- `reboot`（软重启 RK3568）**确实会复位 FPGA**：重启后直接经 `/dev/pango_pci_driver` 读 FPGA 会 **MAP ioctl 超时 / 进程段错误**。
- 结论：Pango 的 bitstream 是 **易失（JTAG/SRAM）配置**，软重启后必须 **重新烧录 `top.sbit`**，再 `remove/rescan/insmod` 才能恢复读写。
- 因此标准恢复流程 = `reboot` → `flash_any.ps1` → `rmmod/remove/rescan/insmod` → 起 camview。

## 2. cam3 补光灯 / I²C 直通是显示挂死的诱因
- 本轮为做 cam3 静态彩条隔离，用 `tools/cam3_i2c_pt.py` 多次写 cam3 SCCB 直通寄存器。
- 之后 camview 出现「只在两张固定缓存间切换、DDR tag 仍在推进」的**主机侧显示冻结**——与项目已知「H2F 多次写后挂死」一致。
- 处置：`reboot` + 重烧 FPGA 恢复。
- **纪律：cam3 未解决前，不再使用 I²C 直通写寄存器。**

## 3. 已有定量结论（保留）
- DDR 帧 tag（`base+0x96000`）六缓冲均以 **~2.7 帧/s** 推进 → FPGA 采集/写引擎正常。
- cam2 的 DDR ping/pong 相关 0.676（实时、正常）；cam3 ping/pong **仍损坏**。
- cam3 损坏性质 = **像素级数据完整性**（行内自洽、行间不相似、16bit 比特分布与 cam1 一致、无卡位），**不是**行序/DMA 丢字。
- cam2/cam3 的 `ov5640_top` 实例逐字节同构；唯一 RTL 差异是 `VSYNC_STABLE_CYCLES=64`（仅延迟帧边界 0.762µs，**不会产生逐像素噪点**）。
- pin 约束三路齐全、`PAD` 属性一致，无 cam3 独有的错误配置。

## 4. 当前阻塞：cam2 掉线（软复位无法恢复）
`reboot` + 重烧后，cam2 寄存器块（BASE `0x20000200`）：
```
0x210 pclk=0  0x220 vsync=0  0x230 cam_words=0  0x290 href=0  0x2A0 beat=0
0x250 i2c_stat=0x00010000   0x260 i2cid=0x00010000   0x2D0 sys=0x8D
```
即 **cam2 的 PCLK 计数为 0** → 模组没有时钟输出。cam1/cam3 同一次读数正常非 0。
- cam2 在 14:45 之前还是正常的实时画面（人物），在 reboot 循环之后掉线。
- `reboot`/重烧（都会重跑三路 I²C 初始化）均**未能**唤回。
- 判断：cam2 模组进入锁死/无时钟状态，需要 **整机物理断电上电**（或重新插拔 cam2 FPC/模组）。

## 5. 下一步
1. **物理断电整机上电**（或重插 cam2 排线）→ 确认三路 `pclk/vsync` 全部非 0。
2. 重烧 `bitstream_cam3_verified_20260926_221855/top.sbit`（SHA256 `7DB33C…6ECF`）并起 camview。
3. 恢复「三路实时」验收证据（双截图 + DDR tag），再继续 cam3 像素级损坏定位。
4. cam3 剩余最可能方向：**DVP 采样相位 / 物理链路**（`IODELAY_STEP` 三路都是 40，从未按通道调过）——建议做单变量 IODELAY 对照实验。
