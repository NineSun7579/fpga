# 预处理 IP 集成指南 (下一步操作, PDS GUI 侧执行)

本文描述把 `source/preprocess/` 9 个模块接入现有工程的接线路径。
RTL 已通过 7/7 双分辨率回归, 集成本身只是连线 + 登记文件。

## 1. 文件登记 (PDS Sources 窗口)

Add Source 加入:
```
source/preprocess/rgb2gray.v  colorize.v  sobel_edge.v  align16.v
source/preprocess/prep_sync_fifo.v  preprocess_top.v  button_debounce.v
source/preprocess/prep_regs.v  lane_detect.v
```
新模块均为纯 RTL (无 IP 依赖, 无锁定的原语), 直接综合。

## 2. 视频通路接线 (top.v, 像素时钟域)

现有读出路径: `DDR3 → ddr_fifo16_r (读 FIFO) → hdmi_top`
插入点: `ddr_fifo16_r` 读出数据 → **preprocess_top.s_*** → 处理图写回
`ddr_fifo16_w` (新增一路写端口或独立 ping-pong 区 0x0A000000) → CH0 DMA。

```
ddr_fifo16_r.rd_data[15:0] ──→ preprocess_top.s_rgb565
(读出 valid)             ──→ preprocess_top.s_valid     (单拍语义!)
ov5640 vsync 同步脉冲    ──→ preprocess_top.s_frame_sync
preprocess_top.m_rgb565  ──→ ddr_fifo16_w 写数据 (处理图, 0x0A000000)
preprocess_top.m_valid   ──→ ddr_fifo16_w 写使能
preprocess_top.s_ready   ──→ (反压) 读 FIFO 的 rd_en 门控
```
注意:
- **NPU 通路完全不动**: npu_cdc_top 继续吃 RAW (协议铁律, PREP_CTRL.bypass 不影响 NPU)。
- 首帧契约: 每帧像素数 = H×W+1 (帧尾多给 1 哑像素, 消隐期第 1 个像素)。
- 行宽寄存器 `prep_img_width` 必须与实际分辨率一致 (640/1280/1920)。

## 3. 寄存器组接线 (AXI-Lite 时钟域)

`prep_regs` 挂在 PCIe BAR0 的 AXI-Lite 总线上, 与现有 `axi_lite_reg` (NPU 指令
寄存器) 地址译码并存: 现有译码命中 0x000~0x0FF 段不变, `prep_regs` 只响应
0x100~0x17C (模块内部取 addr[7:0] 译码, 高位由外部地址译码器使能)。

```
pcie AXI-Lite master ──→ [地址译码] ──0x000段──→ axi_lite_reg (现有)
                                  └─0x100段──→ prep_regs.s_axi_*
```

按键/LED: `button_debounce` ×4 接板级按键 (时钟用 50M clk_50m), 事件脉冲经
2FF 同步进 prep_regs 时钟域; `led_ctrl[3:0]` 输出接板级 LED。

打点脉冲 (已同步到 prep_regs 时钟域后接入):
- `ts_cap_pulse`  ← ov5640 帧采集完成
- `ts_prep_pulse` ← preprocess_top.out_frame_start (帧首) 或帧尾脉冲
- `ts_npu_pulse`  ← NPU done (现有 calculate_reg 完成脉冲)
- `ts_dma_pulse`  ← CH0 DMA 帧搬运完成中断

## 4. 车道线 (可选级联)

`lane_detect` 串联在 `preprocess_top` 的边缘流出口:
```
preprocess_top.edge_stream_{edge,center,valid} → lane_detect.s_*
lane_detect.m_* → prep_regs LANE_RESULT 输入
```
ROI/门限经 PREP_LANE (+0x10C) 板级标定。

## 5. 集成后回归

1. PNS: 全编译 → 时序 (新增像素域路径短, 重点看 pclk 域跨时钟)
2. RTL 仿真: `sim/preprocess/run_all.sh` (单元已绿) + 系统级联仿 (可选)
3. 板级: PREP_CTRL 旁路=1 点亮 RAW 直通 → 切模式 0 验证色化 → 上位机读打点

## 6. 已知限制 (诚实声明)

- `lane_detect` 是固定梯形 ROI + 行投影启发式, 非完整 IPM; 虚实判别阈值
  需要板级实测标定 (寄存器可调)。
- `prep_thr_low` 与 `prep_thr_val` 目前共用一个标定值 (PREP_THR[31:24]),
  若黄灯误判可拆分为独立寄存器 (RTL 已留注释位)。
- timestamp 打点在 FPGA 时钟域, 跨域读数由主机换算, 未做快照锁存
  (四节点各自最新覆盖, 读到的可能有 µs 级撕裂, 对 <100ms 测量无影响)。
