# cam3 诊断记录 — Round 6（2026-09-27）

## 本轮目标
用户假设：把 cam3 的 PCLK 从 84 MHz 降到 **54 MHz** 也许能解决 cam3 图像损坏。

## 0. 前置事故与恢复（重要）

用户断电后再上板，发现一切读写都失败。根因链条：

1. FPGA 的比特流是 **JTAG 配置进 SRAM**（`cfg_program`），**不是固化到 flash**。
   → 断电后 FPGA 从 flash 载入的是**旧设计**。
2. 旧设计能枚举 PCIe（`0002:21:00.0` 0755:0755），但**不符合 pango 驱动的寄存器协议**：
   `dmesg` 里 `pango_pci_driver: probe of 0002:21:00.0 failed with error -22`。
3. 驱动 probe 失败 → 设备未 bind → 后续 F2H ioctl 解引用未初始化状态 →
   **内核 oops**（`pc : pango_cdev_ioctl`），表现为用户进程 SIGSEGV。
   （此前"MAP 门禁间歇可用 / MAP 只能开一次"其实都是这个背景。）

**恢复方法（已验证）**：
```
# 板端：先停看门狗再停 camview，然后 link down
pkill -9 -x run_camview.sh; pkill -9 -x camview
rmmod pango_pci_driver; echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove
# PC 端：JTAG 烧录已验证比特流
python tools/burn_now.py flash_verified_cam3.tcl     # -> BURN OK
# 板端：rescan + insmod
echo 1 > /sys/bus/pci/rescan; sleep 3; insmod /root/ov5640/pango_pci_driver.ko
```
烧录后 `dmesg` 无 -22，`.../0002:21:00.0/driver -> pango_pci_driver`（已绑定），
计数器读写全部恢复。

> ⚠️ **结论：每次 FPGA 断电（掉电/彻底重启电源）后都必须重新 JTAG 烧录**
> `bitstream_cam3_verified_20260927_002538/top.sbit`
> （SHA256 `00AF85B9C348F983EC211AB27E3CD099889454A7EA6EB0A662A983523095FA0F`），
> 否则驱动 probe 失败，一切上板工具不可用。已备好 `flash_verified_cam3.tcl`（3 行 TCL）。

## 1. 54 MHz A/B 实验（单进程单次 open）

运行 `tools/cam3_ab_run.py`（板端 `/tmp/_abrun.py`）。

| 状态 | PCLK 实测 | VSYNCS/s | FRAMES/s |
|---|---|---|---|
| 84 MHz 基线 | 84.04 MHz | 45 | **45** |
| 写 `0x3035=0x11,0x3036=0x36,0x3037=0x13` 后 | **54.03 MHz** | 29 | **3** ⚠️ |

- PCLK 确实降到了 54.03 MHz（FPGA 计数器实测，写通路可靠）。
- VSYNCS 29/s = 45×54/84（传感器确实在按 54 MHz 出帧）。
- **但 FRAMES/s 从 45 掉到 3**，抓取的 3 帧里 a/b 两次 dump **逐字节相同**（时间噪声 0.050）
  → **帧采集卡死/冻结**。

## 2. 图像对比（`tp/pclk/pclk84_*.ppm` vs `pclk54_*.ppm`）

| 指标 | 84 MHz | 54 MHz |
|---|---|---|
| 帧间 mean\|A-B\|（整体） | 11.895 | **0.050**（冻结） |
| 帧间 暗区 | 10.064 | 0.054 |
| 帧间 亮区 | 21.853 | 0.000 |
| 绿椒盐代理（暗区） | 0.53~0.95% | 0.52~0.58% |

- 84 MHz：图像活的、有帧间噪声（已知的绿椒盐 + 亮边彩色横纹）。
- 54 MHz：图像**冻结**（同一帧），无法评估噪声。
- **两种 PCLK 下，那条"横向彩色条纹带"+ 彩虹/绿斑的**结构性损坏**完全一样**
  （见 `tp/pclk/png/pclk84_a.png` / `pclk54_a.png`）。

## 3. 附带的严重问题：运行时改 PLL 会让采集 FSM 锁死

把 `0x3036` 写回 `0x54`（PCLK 恢复 84.03 MHz）后，
**FRAMES/s 仍然是 2**，无法自恢复；camview 显示的是冻结画面。
→ 只有 **重新 JTAG 配置 FPGA**（复位采集 FSM + 重跑传感器 init）才恢复：
恢复后 `PCLK=84.06 MHz, VSYNCS/s=45, FRAMES/s=45`，画面重新活动。

**含义**：运行时改 PCLK 的路子是脏的（会让 cam3 采集锁死），
"干净的 54 MHz" 必须改 init 表 + 重编 + 重新配置才能测。

## 4. 结论

**PCLK 54 MHz 不能解决 cam3 损坏。**
- 横向彩色条纹带 + 彩虹/绿斑在 84 和 54 MHz 下**完全相同** → **与 PCLK 频率无关**。
- 54 MHz 反而让帧采集冻结（45→3 fps），且不可自恢复。

因此 cam3 的损坏更像是**数据/同步链路问题**（与 PCLK 频率无关），
怀疑方向：cam3 VSYNC 引脚振铃（raw 117/s vs 滤波后 45/s）+ 引脚驱动属性偏弱
（scl/sda 无 PULLUP/DRIVE/SLEW；rst_n DRIVE 4，cam1/cam2 为 DRIVE 8 + PULLUP + SLEW FAST）。

## 5. cam3 当前引脚表（`source/constraints/ov5640.fdc` 255–342 行）

| 信号 | 方向 | 引脚 | 电平/标准 | 附加属性 |
|---|---|---|---|---|
| cmos3_pclk | INPUT | E13 | LVCMOS33 @3.3 | PAP_CLOCK_DEDICATED_ROUTE=FALSE, IO_NONE=TRUE |
| cmos3_vsync | INPUT | B13 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_href | INPUT | A16 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_rst_n | OUTPUT | C19 | LVCMOS33 @3.3 | **DRIVE 4** |
| cmos3_scl | OUTPUT | C13 | LVCMOS33 @3.3 | **DRIVE 4**（无 PULLUP/SLEW） |
| cmos3_sda | INOUT | A15 | LVCMOS33 @3.3 | **无 PULLUP/DRIVE/SLEW** |
| cmos3_data[7] | INPUT | E14 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[6] | INPUT | B15 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[5] | INPUT | B16 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[4] | INPUT | D20 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[3] | INPUT | C20 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[2] | INPUT | F18 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[1] | INPUT | E18 | LVCMOS33 @3.3 | IO_NONE=TRUE |
| cmos3_data[0] | INPUT | C18 | LVCMOS33 @3.3 | IO_NONE=TRUE |

全表已核对与其余 .fdc **无引脚冲突**。

## 6. 本轮结束时的板端状态

- 已验证比特流已重新 JTAG 烧录；驱动已绑定；camview 正常运行。
- cam3：PCLK 84.06 MHz，45 fps，**画面活动但仍有结构性损坏**（非本次目标）。
- cam1/cam2 画面正常（cam1 偏绿为已知遗留）。
- 产物：`tp/pclk/png/`（对比图）、`tp/pclk/recovered_rec2.png`（恢复后三路截图）。
