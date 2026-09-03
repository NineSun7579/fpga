# main OV5640→PCIe 帧协议草案

更新日期：2026-09-02

## 目标

定义首版固定单帧传输，使 FPGA 和主机可以独立校验数据；具体地址和寄存器编码在 M0 板级/主机资料闭合后冻结。

## 暂定传输结构

```text
OV5640 RGB565 pixel stream
  → image processing pixel stream
  → DDR3 frame buffer
  → 128-bit AXIS packetizer
  → PCIe DMA Memory Write
```

## 必须冻结的字段

- 图像宽、高、帧率和有效像素数。
- RGB565 字节序与 128-bit 打包顺序。
- 帧头、帧号、有效字节数和帧尾编码。
- PCIe DMA 启动、停止、完成和错误寄存器。
- 主机目标地址、4 KB 边界拆包和最大 TLP payload。
- 主机接收超时、丢帧和重复帧处理。

## M3-A 已冻结的内部字布局

在主机协议、DDR3 地址单位和厂商 PCIe AXIS 转换规则闭合前，仅冻结以下
模块内部布局：像素 0 放在 `word_data[15:0]`，像素 1 放在 `word_data[31:16]`，
依次到像素 7 的 `word_data[127:112]`；`word_keep` 低 2N 位表示 N 个有效
RGB565 像素。该布局不代表 PCIe TLP 的 payload 字节序，也不代表主机端地址
或缓存布局。

## 首版验证要求

- 先使用固定目标地址和固定帧长度。
- 先传输单帧或固定小 ROI，不以连续视频代替基础闭环。
- TB 必须检查帧长度、帧边界、像素顺序、数据内容和 DMA 完成状态。
- 成功只输出一次 `TEST PASS`；超时、格式错误和数据错误必须以 `$fatal` 及非零退出码结束。
