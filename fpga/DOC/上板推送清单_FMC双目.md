# FMC 双目 · 上板推送清单

适用比特流：`bitstream_2026-09-16_dualcam/top.sbit`（已同步到 `generate_bitstream/top.sbit`，供 `flash_jtag.tcl` 使用）
主机应用：`host/camview/`（双路版，已同步到 `usb_deploy/camview/`）

---

## 0. 前提

- FPGA 板 PCIe 接 RK3568；串口 `COM9 @ 1500000`。
- 本机已装 `pyserial`（已确认 3.5）。
- 上板顺序固定为：**烧 bitstream → PERST/rescan → 装驱动 → 起 camview**；任一 DMA ioctl 超时后需 `rmmod/insmod`。

## 1. 烧录 bitstream（JTAG，人工执行）

```powershell
# 1) 关掉可能残留的 JTAG 会话
taskkill /F /IM cdt_js.exe 2>$null; taskkill /F /IM cdt_cfg.exe 2>$null
# 2) 起 server
C:/pango/PDS_2022.2-SP6.4/bin/cdt_js.exe -port 65422
# 3) 另开一个终端下载（flash_jtag.tcl 指向 generate_bitstream/top.sbit）
C:/pango/PDS_2022.2-SP6.4/bin/cdt_cfg.exe -ip 127.0.0.1 -port 65422 -file C:/Users/NineSun/Desktop/ov56401/project/flash_jtag.tcl
```

> 每次 JTAG 下载都会复位 FPGA PCIe 核；**必须**做 §3 的 PERST + rescan，否则总线主控 DMA 静默死锁。

## 2. 探测（不推送）

```powershell
python push_dualcam.py probe
```

应看到：`/dev/pango_pci_driver` 存在、`lspci` 有 `0755`、`camview` 进程数。

## 3. 推送 camview 并启动

```powershell
python push_dualcam.py push
```

内部依次：
1. HEX 分片传输 `host/camview/main.cpp` → `/root/ov5640/camview/main.cpp`（md5 校验）
2. 板上 `qmake && make -j4` 重编（Qt5 已离线装好）
3. PERST(`gpio144`) + `remove/rescan` + `rmmod/insmod pango_pci_driver`
4. `run_camview.sh` 启动显示，回读窗口状态

仅传源码不重编：`python push_dualcam.py push --no-rebuild`

## 4. 验收

- HDMI 上应出现**左右并排**两路画面（左 cam1 / 右 cam2），各 1280×720。
- 窗口标题含 fps；热键：`B` 字节序、`C` 红蓝、`F` 全屏、`Q` 退出。
- 若只有左半有图 → cam2 未出帧，查 §5-3。

## 5. 排障

1. **无图/全黑**：确认已烧新 bitstream、已 PERST/rescan、驱动已 insmod；`dmesg | tail` 看 MSI/DMA。
2. **DMA 超时**：`rmmod pango_pci_driver; insmod /root/ov5640/pango_pci_driver.ko`，再起 camview。
3. **只有 cam1**：cam2 引脚来自 fdc 中被注释的厂商表，核对 FMC 实际走线；可读 cam2 DDR 区（0x00C0_0000）看 tag 是否递增。
4. **画面噪点/位偏**：调 `source/ov5640/ov5640_top.v` 的 `IODELAY_STEP`（两路各一份，默认 40），重出比特流。
5. **串口出现字面量 `fiq` 会触发 FIQ 调试器**：工具已用 HEX 编码规避；如卡住串口发 `console\r\n`。

## 6. U 盘备选（无串口时）

把 `usb_deploy/` 拷到 U 盘根，板子桌面终端：

```bash
bash /media/*/*/install_from_usb.sh
```

## 7. 回滚

- 源码：`_attic/dualcam_backup_2026-09-16_1904/`
- 旧比特流：`_attic/generate_bitstream_top.sbit.bak_2026-09-16_2116`、`bitstream_2026-09-15_*/top.sbit`
- 回滚：还原 `generate_bitstream/top.sbit` 重烧 + 还原 `host/camview/main.cpp` 重推。
