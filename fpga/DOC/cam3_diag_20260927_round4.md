# cam3 诊断 第4轮 — 读通路清白 / 采样相位（2026-09-27）

## 本轮结论（硬证据）

### 1. F2H 读通路完全清白 —— 排除了 dump/读回这一大类怀疑

零编译实验（`tools/cam3_freeze_test.py`）：彩条开启后先跑 3 次 dump，再把 cam3
`REG_CAM_EN(0x20000440)=0` 冻结写引擎，对**同一块 DDR** 再 dump 3 次：

| 对比 | mean\|diff\| | max | corr |
|---|---|---|---|
| 运行中 dump a/b/c（帧在变） | 83 ~ 99 | 248 | +0.06 ~ +0.16 |
| **冻结后 dump a/b/c（同一内存）** | **0.00** | **0** | **+1.0000** |

冻结后三次读**逐字节相同** → 读通路（驱动 ioctl + RX mmap + dump 工具）无任何
不确定性。因此「运行中连续 dump 不一致」只能来自 **DDR 里被写入的内容本身每帧不同**，
而不是读数或竞态。板端计数确认冻结生效：`0x200004F0` 帧计数停在 125676 不动。

### 2. cam1（已知正常）vs cam3 原始 DVP 边沿计数（`tools/_camcmp.py`）

同一时刻读三路基址 `0x2000_0000 / _0200 / _0400` 的 `+0x10 pclk / +0x90 href_raw /
+0xE0 vsync_raw / +0x20 vsyncs / +0xF0 frames`：

| 指标（每次采样增量） | cam1 | cam3 |
|---|---|---|
| pclk | ~116 M | ~116 M（一致） |
| href_raw | 59 681 | 59 953（**干净，差 0.45%**） |
| **vsync_raw** | **125** | **2777 ~ 2983（≈22×一个真实脉冲！）** |
| vsyncs（滤波后） | 125 | 125（一致） |

**cam3 的 VSYNC 引脚每个真实脉冲有 ~22 个跳变（振铃/回弹），而 cam1 干净。**
href / pclk 正常。cam3 是唯一带 `VSYNC_STABLE_CYCLES=64` 去抖旁路的那一路
（`ov5640_top.v` 的 cam3 实例），说明之前就有人观测到 cam3 的 vsync 异常。

### 3. 损坏形态 = 字节配对滑移，不是纯位移

对冻结帧 `tp/frz_frozen_a.ppm` 数值分析（`tools/_look.py`）：

- 每行竖直边沿数均值 6.8，直方图 `[..., 6:53, 7:225, 8:151]` → **约 78% 的行是
  正确的 8 彩条结构**（干净行占多数）。
- 但只有 **10.8%** 的行与第 240 行 luma 接近（<6）→ 其余行被水平**错位**。
- 部分行段（如 r300~r320）整体亮度/色相明显不同（L=82 vs 140）→ 这**不是纯整数位移**
  （纯位移不改变周期图样的行均值），而是 **16-bit 像素字节配对被打乱**（奇数字节滑移）。

**结论：DVP 数据在 PCLK 上被采到的相位处于亚稳态边缘** → 偶发整字节配对滑移，
表现就是「颜色基本对、位置/行均值偶发跳变、逐帧不同」。这也解释了
`cmos_capture` 的 `temp_cnt` 按 href 清、却仍出现奇字节错位。

## 根因判断

- DDR 写通路（仲裁器/DMA/FIFO/IP）已被前几轮证明背靠背 burst 会加剧，
  但本轮证明**读侧无嫌疑、且损坏形态是字节级采样滑移**，指向 **cam3 的 DVP
  采样相位（IODELAY）**。
- 三路共用固定 `IODELAY_STEP=40`（cam1 显式 40；cam2/cam3 默认 40）。
  cam1 在此值下正常，cam3 因板级走线/连接器差异（vsync 网振铃即为旁证）处于
  亚稳相位 → 需要不同的采样延时。
- `GTP_IODELAY_E2` 支持 `DELAY_STEP_SEL("PORT")`（DDR3 PHY 即用 PORT 做运行时扫延），
  因此可以实现**运行时扫延时**，一次编译即可在板上找出最佳相位。

## 本轮改动（源码，已备份）

备份：`ov5640_reg.v.bak_cam3dly_20260927`、`ov5640_top.v.bak_cam3dly_20260927`

1. `source/ov5640/ov5640_reg.v`
   - 新增参数 `DLY_STEP_DEF = 8'd40`、输出 `dly_step[7:0]`。
   - 新增写寄存器 `REG_DLY_STEP = BASE_ADDR + 0x30`（0x30 原本只读 CAM_WORDS，
     写入原本是 no-op，故安全）；复位值 40。
2. `source/ov5640/ov5640_top.v`
   - 新增 `reg_dly_step` 线网，接到 `ov5640_reg` 的 `.dly_step`。
   - 3 处 `GTP_IODELAY_E2`（vsync / href / data[7:0]）由
     `DELAY_STEP_SEL("PARAMETER") + .DELAY_STEP(8'b0)`
     改为 `DELAY_STEP_SEL("PORT") + .DELAY_STEP(reg_dly_step)`。
   - 默认值 40 与改前完全一致，故 cam1/cam2/cam3 行为在写入寄存器前不变。

## 下一步（编译后）

1. 烧写新 bitstream（`tools/build_cam3_verified.ps1` 产物 `bitstream_cam3_verified_*/top.sbit`）。
2. `python tools/cam3_dly_sweep.py`：彩条开启，写 `0x20000430` 扫
   0/8/…/255，各取 ping 连续两帧 dump，按 `mean|diff|` 打分；取最优延时。
3. 用最优延时复验：背靠背帧相关≈1、逐行 shift 恒 0。
4. 关闭彩条回正常模式，确认 cam3 画面干净且持续更新。

工具：`tools/cam3_dly_sweep.py`（扫描+打分）、`tools/cam3_freeze_test.py`（读数清白证明）、
`tools/_camcmp.py`（三路原始边沿对比）、`tools/_look.py`（帧结构数值分析）。
