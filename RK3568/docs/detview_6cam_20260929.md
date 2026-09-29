# detview 六路采集 / 显示 / 推理吞吐 工程记录（2026-09-29）

本文归档 2026-09-29 这一轮把 `detview_tdm` 从"四路 + GPU 合成"推进到"六路 + CPU 显示 + RGA 缩放 + 推理提交解耦"的全部决策、实测数据、踩过的坑与待办，作为可复查的工程记录。使用说明见 `RK3568/detview_tdm/README.md`。

## 0. 结论摘要

- 采集：六路相机（C1–C6）各自一个采集线程，帧标签轮询 + DMA 整帧读，共用一条 PCIe DMA；按"帧代（gen）变化 + 33ms 节流"合成 **3×2 RGB888（1920×960）**。
- 显示：**纯 CPU（QWidget/QPainter）+ RGA 硬件缩放**。板端没有合成器在跑，GL 方案（`QOpenGLWidget` / `QOpenGLWindow + createWindowContainer`）都会出现陈旧区域与双份绘制（画面闪、留残影），因此放弃 GL。
- 推理提交与显示节流解耦：由"选中那一路"的采集线程直接提交，避免整体吞吐被 `DETVIEW_MIN_MS` 一起节流。
- 单路模式（`--camera N`）停采其余五路。
- 实测（两款模型轮换：zebra-merged-v3-rm8 + tt100k-anneal-c12）：
  | 配置 | 单路采集 | 显示 | paint | 整体推理 | 每款 |
  | --- | --- | --- | --- | --- | --- |
  | 6 路 3×2 | 21–23 fps | 19–21 fps | 17 ms | 15.4–16.5 /s | 7.7–8.2 /s |
  | 单路 C1 | 28–29 fps | 22–24 fps | 13.9 ms | 16.5 /s | 8.2 /s |
- 上界：按单次均值 52ms 推算轮换 **19.2 /s**；单跑 zebra 23.8 /s、TT100K 17.6 /s（严格轮转理想 20.2 /s）。当前 ~86% 于上界，差的约 12% 是每轮 ~7ms 的管线开销（六个采集线程共用一条 DMA 的轮询/读帧排队）。

## 1. 环境与硬件现状

- FPGA 位流：六路相机版本，PCIe 枚举 **BAR0 8K / BAR1 4K / BAR2 4K**，`pango_pci_driver` 正常 probe 并绑定。
- 相机 DDR 乒乓缓冲（帧 640×480 RGB565，标签在 `base + 0x96000`）：

  | 路 | ping | pong |
  | --- | --- | --- |
  | C1 | `0x00800000` | `0x00A00000` |
  | C2 | `0x00C00000` | `0x00E00000` |
  | C3 | `0x01000000` | `0x01200000` |
  | C4 | `0x01400000` | `0x01600000` |
  | C5 | `0x01800000` | `0x01A00000` |
  | C6 | `0x01C00000` | `0x01E00000` |

- 板端 `/root/ov5640/camview/main.cpp`（SHA-256 `82c46f20…`）已是**六路 3×2**实现（含 `CAM5/CAM6`），但正在运行的 camview 二进制是 06:44 编的**四路**版本（截图 HUD 为 `Quad FPS … C1:OK C2:OK C3:OK C4:OK`）——即源码改了没重编。
- 板端环境：X 屏幕 1920×1080，窗口管理器 xfwm4 且**没有合成器**（`_NET_WM_CM_S0` 不存在，xfwm4 的合成也起不来：本机 GLX 只有 llvmpipe 软件实现）；Qt 5.15，Mali-G52；`/dev/rga` 驱动 `rga2 hw_version:3.2.63318`，`/dev/dma_heap/{system,system-uncached}` 可用。

## 2. 显示路径的三次尝试（决策记录）

| 方案 | 结果 | 数据 |
| --- | --- | --- |
| `QOpenGLWidget`（Mali EGL/ES2 纹理直传） | 不支持：无合成器时出现陈旧区域 + 双份绘制（用户可见"新旧界面交替闪"、屏幕上多出一个小窗） | 四路时期显示 23.13 fps、轮换 17.77 /s、paint 2.29 ms（性能最好但画面不可用） |
| 顶层 `QOpenGLWindow` + `createWindowContainer` | 更糟：native 子窗口的 EGL 表面尺寸不跟随窗口，按旧尺寸绘制并留残影 | — |
| **纯 CPU（QWidget/QPainter）+ RGA 缩放** | 采用：不依赖 GL 与合成器，无闪烁、无残影 | 见 §5；paint 从 31ms 降到 17ms（单路 13.9ms） |

补充：camview 之所以在同样环境下正常，是因为它用**顶层** `QOpenGLWindow`（画面就是它自己的窗口，不需要合成器）。它的代价是 UI 必须自绘成 HUD、不能挂 QWidget 工具栏，因此 detview 选了 CPU 路径。另一个副作用：`XGetImage`（`xwd`/`ffmpeg x11grab`）抓不到顶层 GL 窗口的 GL 画面，只能抓到它的 HUD 文字——远程判读 camview 画面不可行。

## 3. 采集、合成与推理提交结构

- **采集**：`CameraWorker` × 6，每路独立线程。每轮读本路两个帧标签（`base + 0x96000`），标签变化才 DMA 读整帧（614400B）并存入 `LatestFrames`（互斥保护）。轮询间隔 20ms（放宽到 20ms 对吞吐无净收益，见 §5）。
- **共用 DMA**：六个线程与显示线程共用 `/dev/pango_pci_driver` 的一条 DMA 通道，`PangoDev` 内部用互斥串行化（`tx_/rx_` 缓冲与 ioctl 都在锁内）；单次等待上限 2s（丢 MSI 时不至于整块卡住）。
- **合成**：显示循环按 `gen` 变化推进，只把**有新帧的那几格**做 RGB565→RGB888 就地写入 3×2 合成缓冲（双缓冲轮换，零每帧分配）。单选某一路时该格仍按 3×2 组织，RGA 用 `imcrop` 取该格。
- **推理提交**：由"选中那一路"的采集线程在读到新帧后就地转成 640×640 letterbox 并 `emit inferReady`。**不能**放在显示循环里：实测把 `DETVIEW_MIN_MS` 放到 200ms（显示 4.55 fps）时，整体推理从 ~16/s 塌到 **5.9/s**（提交跟着显示节流走）。
- **单路停采**：`mode != 6` 时，非选中路的采集线程不再轮询标签、不再发 DMA（`setModePtr`）。效果：C1 采集 21–23 → 28–29 fps。
- **缩放缓冲**：合成缓冲与 RGA 输出缓冲放 **dma-heap**（RGA 只能操作 dma-buf）；输出按控件内容尺寸（letterbox 后）分配，`QImage` 只做包装；dma-heap 不可用时自动退回 Qt 缩放（`ox<0` 约定）。

## 4. 帧率口径

- 工具栏：`轮换 N 款 | 整体 X fps | <短名> a  <短名> b fps | 本次 M ms | 检测 Z`；状态栏以 `整体 X fps | …每款耗时/检测数/该款 fps/结果年龄` 呈现。
- **整体 fps** = 1 秒窗口内完成推理的次数 / 实际跨度（任意一款完成即计一次）；**每款 fps** = 同窗口内按模型分别计数。严格轮转时整体 ≈ 各款之和。
- 不能用"相邻两次完成的时间戳求倒数"：GUI 线程每帧绘制十几毫秒，会把排队的完成信号挤在一起处理（相邻时间戳只差 1ms → 1000fps），出现"几百 fps"的假值。窗口计数对处理抖动不敏感。
- `本次 M ms` 是单次推理墙钟（`rknn_inputs_set → run → outputs_get` + DFL 解码 / NMS），不参与帧率计算。

## 5. 实测数据（本次全部）

模型：`det-yolov8n-zebra-merged-v3-rm8-…raw-dfl6-int8` 与 `det-yolov8n-tt100k-anneal-c12-…raw-dfl6-int8`，严格轮转。

| 项目 | 数值 |
| --- | --- |
| 6 路 3×2：显示 / paint / 整体 / 每款 / 单次 | 19–21 fps / 17 ms / 15.4–16.5 /s / 7.7–8.2 /s / 44 & 63 ms |
| 单路 C1：采集 / 显示 / paint / 整体 / 单次 | 28–29 fps / 22–24 fps / 13.9 ms / 16.5 /s / 43 & 61 ms |
| 推理线程探针 `[infer-diag]`（单路） | 平均运行 53ms + 平均等帧 7ms = 60ms/轮 |
| 单跑参考（视频源，早期测量） | zebra rm8 23.76 /s（42ms）；TT100K anneal 17.55 /s（57ms）→ 两款轮换理想 20.2 /s |
| 慢显示对照 | 无提交线程、`DETVIEW_MIN_MS=200`：整体 5.9 /s；有提交线程：16.48 /s |
| 轮询间隔 10ms → 20ms | 整体 15.5 → 15.4 /s（无净收益，取 20ms 以减少 DMA 小事务） |

RGA 探针（`docs/probes/rga_probe.cpp`，dma-heap + im2d）：

| 操作 | 耗时 |
| --- | --- |
| `imresize` 1280×960 → 1900×1006 RGB888 | 4.97 ms/次 |
| `imcvtcolor` 640×480 RGB565 → RGB888 | 0.886 ms/次 |
| `imfill` 1900×1006 | 4.30 ms/次 |

约束：`RK_FORMAT_RGB_888` 的**行 stride 必须 4 字节对齐**（1898 会报 `dst unsupport width stride`）；`RK_FORMAT_RGB_565` 的 R/B 顺序与 CPU 侧转换**相反**（实测互换），若用 RGA 做 565→888 需改用 BGR565 或做通道交换。

DMA 探针（`docs/probes/dma_probe.cpp`）：

| 操作 | 耗时 |
| --- | --- |
| 读整帧 614400 B | 1.039 ms（564 MB/s） |
| 读 16 B 帧标签 | 0.015 ms |
| 四路各读一帧 | 4.053 ms/轮 → 仅 DMA 上限 247 fps |
| 上轮运行中 >30ms 的 ioctl | 0 次 |

结论：**PCIe 传输不是瓶颈**（当前 47ms/帧里约占 9%）；"在驱动端做差分压缩"既改不动方向（数据是 FPGA→主机，压缩必须在传输前发生），收益上限也只有 ~9%。

## 6. 踩过的坑与恢复流程

1. **无合成器 + QOpenGLWidget** → 陈旧区域、双份绘制、屏幕多出小窗；`QOpenGLWindow + createWindowContainer` 亦然。显示走 CPU 或顶层 GL 窗口。
2. **驱动 TX buffer 残留**：应用被强杀、或自写探针跑完后，驱动内部 TX/RX 映射残留（dmesg `TX Buffer already allocated!`），后续 `map` 失败、一帧都读不到、`/proc/interrupts` 里 MSI 计数也不再增长。**这不是 FPGA 故障**：MSI 为 0 只说明主机侧没发起 DMA。恢复：杀干净所有实例后 `rmmod pango_pci_driver && insmod /root/ov5640/pango_pci_driver.ko`，或重启。
3. **位流与驱动必须匹配**：只枚举 64K BAR0 的位流会让 probe 失败（`-22/EINVAL`），此时任何 ioctl 都会触发内核 Oops（dmesg 有 call trace）。判断依据用 `lspci -vv` 的 Region 布局 + probe 日志，不要凭现象猜。
4. **不要对大块做未验证的 DMA 读**：按 2MB 整块读 DDR 时把驱动读挂死在不可中断等待（只能 kill/重启）。只用已验证的 614400B 粒度，换地址布局先问接口/地址表。
5. **`pkill -f run_camview.sh` 会杀掉执行它的 SSH shell**（cmdline 含同一字符串）。要停 camview 用 `pkill -x camview` + 用 `pgrep -f 'run_camview[.]sh'` 的括号技巧杀守护脚本。
6. **中断的 make 会留下半截 `main.o`**（如编译中重启），表现为 `undefined reference to main`。`touch main.cpp` 强制重编。
7. **不要用 PowerShell 整文件读写来改源码**：会把 UTF-8 中文注释按 ANSI 解码成乱码且不可逆；用 edit 工具做局部替换。
8. **XFCE 窗口缩放 1.25x**：Qt 逻辑尺寸与 X 实际窗口不一致，全屏时画面只铺满左上角。程序启动固定 `QT_SCALE_FACTOR=1` 并关闭自动屏幕缩放。
9. **`XGetImage` 抓不到顶层 GL 窗口的画面**（camview 截图只有 HUD 文字），远程验证 GL 画面不可行。
10. **板端根分区吃紧**：截图/日志别都堆在 `/tmp`（根分区只有约 170MB 余量）；本次产生的约 172MB 素材已挪到 `/userdata/linaro/scratch_trash_20260929`。

## 7. 待办与已确认限制

- **C5/C6 无活动帧**：`[panes] have=111100`、`err=0`——对 `0x01896000/0x01A96000`、`0x01C96000/0x01E96000` 的读不报错但标签值不变，说明这些地址上没有写入。camview 六路源码给的 C5/C6 地址尚未被验证过（它的六路二进制从未跑起来）。需要确认：C5/C6 的 DDR 基址对、是否需要寄存器使能（类似 C3/C4 的 `R_CAM2_*` 窗口），或这版位流其实只有 4 路在流。
- **推理吞吐还差 ~12%**：每轮约 7ms 等帧。候选优化：把"一个线程轮询六路标签 + 分发读帧"代替六个线程各自轮询；RGA 输出直接用 RGB32 省掉 Qt 每帧的 RGB888→窗口格式转换；或换更快的模型组合（单跑 23.8 /s 的 zebra rm8 明显快于 17.6 /s 的 tt100k-anneal）。
- **C5/C6 与单路模式的显示**：单路 C1 已验证；C5/C6 单路因无数据未验证。
- 正式 `/root/npu/detview/detview` **未替换**，本目录产物仍在隔离构建 `/userdata/linaro/detview-tdm-build-20260928`。

## 8. 复现、命令与文件清单

构建与自检（板端）：

```sh
cd /userdata/linaro/detview-tdm-build-20260928
qmake detview.pro && make -j2
./detview --dfl-selftest && ./detview --lane-selftest
```

运行（六路 3×2 + 两款轮换；单路用 `--camera 1..6`）：

```sh
sudo env DET_BENCH=1 DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 \
  ./detview --fullscreen --rotate-model zebra-merged-v3-rm8,tt100k-anneal-c12
```

环境变量：`DETVIEW_MIN_MS`（显示节流，默认 33ms，0=不限速）、`DETVIEW_GEO=1`（每秒打印窗口几何）、`DET_BENCH=1`（打印 `[panes]`、`[tdm_bench]`、`[infer-diag]`、`[stats]` 日志）。

本目录文件：

| 文件 | 说明 |
| --- | --- |
| `RK3568/detview_tdm/main.cpp` | 六路采集 + CPU 显示 + RGA 缩放 + 轮换推理（提交与显示解耦、单路停采） |
| `RK3568/detview_tdm/README.md` | 使用说明与帧率口径 |
| `RK3568/docs/detview_6cam_20260929.md` | 本文档 |
| `RK3568/docs/tdm_efficiency_20260928.md` | 早前（四路/视频源）时分复用效率实测 |
| `RK3568/docs/probes/rga_probe.cpp` | dma-heap + RGA 缩放/转换探针（含 stride 与字节序约束） |
| `RK3568/docs/probes/dma_probe.cpp` | PCIe DDR 读代价探针（整帧/标签/四路） |
| `RK3568/docs/probes/ddr_scan.cpp` | DDR 活动缓冲扫描（仅用于换位流后对地址；注意大块读会挂驱动） |
| `RK3568/docs/probes/detview_profile.cpp` | 早期分段耗时剖析版 detview（静态图 220 帧口径） |

相关提交：`7391c13`（可选时分复用）→ `01a52ce`（TDM 时间戳插桩）→ `6530a2a`（GPU 合成四路）→ `6a1ea21`（轮换帧率 + 全屏缩放修正）→ `cf91f32`（六路 + CPU 显示 + 窗口帧率）→ `4c69b5c`（提交解耦 + RGA + 单路停采）。
