# cam3 诊断记录 — Round 7（2026-09-27）

## 本轮目标
用户裁决：把 cam3 的 PCLK 从 84 MHz 改成 **48 MHz**，看能否解决 cam3 损坏。

## 1. 48 MHz 实验（干净做法）

方法：先 JTAG 重新配置（确定性起点）→ `rescan`+`insmod` → **单进程单次 open** →
先 `CAM_EN=0`（放空写引擎，避免运行时切 PLL 半途咬死）→ 写 `0x3035=0x11, 0x3036=0x30, 0x3037=0x13`
→ `CAM_EN=1` → 测计数器 + dump 帧 → 再恢复 84 MHz。

| 状态 | 实测 PCLK | VSYNCS/s | FRAMES/s |
|---|---|---|---|
| 84 MHz 基线 | 84.05 MHz | 45 | **45** |
| `0x3036=0x30`（48M） | **48.04 MHz** | 25 | **2** ⚠️ |
| 恢复 84 MHz | 84.06 MHz | 45 | **45** ✓ |

- 传感器确实按 48 MHz 出帧（VSYNC 25/s = 45×48/84，PCLK 48.04 实测）。
- **但帧写入引擎再次咬死**（FRAMES=2/s），抓的两帧**逐字节相同**（temporal `mean|A-B|`=0.066）。
- **即使先用 `CAM_EN=0` 放空引擎也没用** —— 说明咬死不是"半途切 PLL"造成的，而是**在 48 MHz 下必然发生**。
- 恢复 84 MHz 后自动回到 45 fps（这次没有永久锁死）。

**结论：48 MHz 和 54 MHz 一样，会让 cam3 的帧采集坍缩到 ~2 fps。48M 不可行。**

## 2. 为什么低 PCLK 会咬死：写引擎无超时自恢复

读 RTL（`source/ov5640/ov5640_ddr/`）：

- `ov5640_ddr_w_ctrl.v`：写引擎 FSM
  `IDLE→ADDR→DATA→ADDR_TAG→DATA_TAG→WAIT_TAG_DONE→IDLE`
  - `frame_done = dma_done && (curr_state==DATA)`
  - **任何一步等不到 `dma_done` / `axi_cmd_ready` 就永久停在那一步**
  - `wd_cnt`（`dbg_wd_cnt`）**只是状态停留计数、不复位 FSM**
- `ov5640_ddr_w_en.v`：`engine_busy = (curr_state != IDLE)`，
  `IDLEGATE`：`if(axi_cam_en && !engine_busy)` 才准入新帧；
  引擎咬死时**只会在 vsync 丢弃帧，永不清 `engine_busy`** → 死锁。
- DMA 是**固定长度**（`CAM_DATA_LEN` 拍/帧）；帧字节数一旦对不上，永远等不到 `dma_done`。

在 48M 下读 debug 寄存器（`BASE+0x60 = {wd_cnt[7:0], dbg_state[7:0], cmd_cnt[15:0]}`）：
FSM 停在 `DATA_TAG/WAIT_TAG_DONE`，`AXI_NOW(+0xd0)` **完全不动**（0x420D / 0x42CD）。
→ 挂死点在 **帧内 ~44% 处（≈0x42CD0 字节）**，而且是 **tag 阶段**。

## 3. 更重要的发现：配置后三路会整体掉速（可复现，重烧可救）

在排查过程中出现一个**全新现象**：

| 观测 | cam1 | cam2 | cam3 | 现象 |
|---|---|---|---|---|
| 正常烧录后 | 45/s | 45/s | 45/s | 画面活动 |
| 某次烧录后 | **2.8/s** | **2.8/s** | **2.8/s** | **三路同时掉速、屏幕静止** |

- 掉速时三路 `AXI_NOW` 都卡在同一位置 `0x420D`；3000 次主机寄存器读**无影响**（不是主机读抢占）。
- 两张间隔 3s 截图几乎全同（cam1 `mean|diff|`=0.069、cam3=0.211）→ **显示冻结**；
  cam3 面板出现**网格/块状**（半写帧外观）。
- **重新 JTAG 配置后立即恢复 45/45/45 fps、画面活动**。

→ **每次 JTAG 配置的结果不稳定**：有时三路 45 fps，有时三路 ~2.8 fps。
共同资源是 DDR3/AXI（或每次配置的 DDR3 训练/校准）。这是本轮最有价值的线索：
**它和 cam3 的"横带/半写帧"损坏很可能是同一机制（写通路停顿 → 主机读到部分帧）。**

## 4. 结论

1. **48 MHz 不能解决 cam3**：帧采集坍缩到 2 fps，且损坏本就与 PCLK 无关（84/54/48 下那条横带一样）。
2. 写引擎**没有超时自恢复**，一次停顿就永久咬死（`engine_busy` 锁存 + IDLEGATE 只丢帧）。
3. 发现**配置级不确定性**：FPGA 配置后三路偶尔整体掉速到 ~2.8 fps，重烧可恢复。
4. 新主攻方向：**cam3 帧写入的间歇性停顿（半写帧）**，而不是传感器/PCLK。

## 5. 本轮结束时的板端状态

- 已重新 JTAG 烧录，三路 **45/45/45 fps**，`camview` 运行中，**显示活动**。
- cam3 画面仍带既有损坏（横向彩色条带；本次在画面下缘），**未解决**。
- 产物：`tp/pclk48/`（48M 对比图）、`tp/recover3/r3a.png` `r3b.png`（恢复后三路截图）。
- 新增工具：`tools/cam3_pclk48.py`、`tools/cam3_p48_where.py`、`tools/cam3_throughput.py`、`tools/cam3_recover3.py`。
