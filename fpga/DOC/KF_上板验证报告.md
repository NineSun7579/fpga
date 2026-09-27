# OV5640 时域卡尔曼（自适应简化/固定增益 IIR）端到端验证报告

日期：2026-09-25
范围：`vip_kf.v`（像素通路 3×3 中值之后的时域滤波）→ 仿真黄金比对 → PyTorch/ONNX 推理验证 → 上板（cam1 滤波、cam2 旁路对照）实时监测与截图。
结论一句话：**三阶段全部通过**；仿真逐位精确，模型侧 PSNR/检测稳定性有正收益，板上滤波链路稳定运行且**上一帧 DDR 回读被证明确实送回真实数据**（非 0）。

---

## 0. 方案与实现摘要

| 项 | 值 |
|---|---|
| 形式 | 自适应简化卡尔曼（4 档固定增益 IIR），仅 cam1 |
| 状态 x | 上一帧滤波后像素（存 DDR 另一乒乓 bank，片上 BRAM 不够整帧） |
| 新息 d = \|z − x\| | `d<T0` → K=1/4；`T0≤d<T1` → 1/2；`T1≤d<T2` → 3/4；`d≥T2` → 1 |
| 阈值（6bit 通道） | T0/T1/T2 = 3 / 8 / 20 |
| 输出 | `(3x+z)>>2`、`(x+z)>>1`、`(x+3z)>>2`、`z`（纯无符号整数+移位，无除法，位精确可复现） |
| 首帧 | `apply = en & ~first_frame`，首帧 passthrough 建状态 |
| 旁路 | `en=0` 纯 wire bypass；cam2 用 `KF_EN=0` |
| 集成 | median 之后插 `vip_kf_stream` → `ov5640_ddr`；`top.v` 侧 cam1 `.KF_EN(1'b1)` |
| 读通路 | crossbar 空闲从口 **S05**（`M00_CONNECT_READ=7'b1111101`）+ `axi_dma_read.v` 按行预取上一 bank；写路径不变 |
| 读回约束 | `LAT=1`；128-bit beat = 8 像素小端，像素 j 在 `bits[16j +: 16]` |
| 关键修复 | DDR 读桥**单未决门**：`ar_latch_now` 增加 `&& !rd_inflight`，避免第二条 AR 在第一条 RLAST 前锁存导致 R 路由高位 ID 错误 → crossbar M00 读永久 wedge |
| 隔离开关 | `vip_kf_stream.RD_EN` / `ov5640_top.KF_RD_EN`（默认 1）；`tools/patch_rden.py` 字节级贯通 |

---

## 1. 阶段一：ModelSim 仿真 + 黄金逐位比对（PASS）

命令（PowerShell 直调，规避 WSL bash）：
```
C:\modeltech64_10.6e\win64\{vlib,vlog,vsim}.exe
C:\Users\NineSun\anaconda3\python.exe sim/ov5640_tb/vip_kf_compare.py
```
黄金模型 = `vip_kf_compare.py` 内的位精确 Python 参考实现（与 RTL 同阈值、同移位）。

| 用例 | 帧 | 像素 | 失配 | 增益档命中（每通道） | 结果 |
|---|---|---|---|---|---|
| `tb_vip_kf`（核心体） | 7 | 224 | **0** | K1/4:377 K1/2:98 K3/4:48 K1:53 | `VIPKF_COMPARE_PASS` |
| `tb_vip_kf_stream` 16×8 | 7 | 896 | **0** | K1/4:1831 K1/2:299 K3/4:48 K1:126 | `VIPKF_COMPARE_PASS` |
| `tb_vip_kf_stream` **640×2（全行宽 80-beat）** | 7 | 8960 | **0** | K1/4:19291 K1/2:2711 K3/4:48 K1:990 | `VIPKF_COMPARE_PASS` |

- 四档增益在仿真中被**全部命中**，说明阈值分档逻辑被真实覆盖，而非退化到单档。
- 日志：`sim/ov5640_tb/kf_sim.log`、`kf_stream_sim.log`、`kf_stream_sim_wide.log`（RTL 侧 `Errors: 0`，`*_DUMP_OK`）。

## 2. 阶段二：PyTorch / RKNN 侧推理验证（正收益，自适应档正确）

脚本：`sim/ov5640_tb/vip_kf_yolo_check.py`（ONNX，真实 YOLO26 头，`nc=80`，std 头 + class-aware NMS）；
`sim/ov5640_tb/rknn_kf_check.py`（rknn-toolkit2 2.3.2，target=rk3568，`std_values=[[255,255,255]]` 对齐 [0,1] 输入）。

**（a）真实 ONNX，`calib/img00.ppm`，8 帧独立高斯噪声：**

| 配置 | PSNR(noisy→filt) | 检测框 | 相邻帧同类别最优 IoU |
|---|---|---|---|
| σ=8 auto（板上同款） | 15.87 → 16.54 dB（**+0.67**） | 1 → 1（保持） | 0.979 → 0.975（≈中性） |
| σ=12 auto | — | — | 0.980 → **0.987**（提升） |
| σ=8 固定 K=1/4 | 15.87 → 17.82 dB（+1.95） | 1 → **0–1 丢失** | 0.979 → **0.423（崩）** |

**（b）真实 RKNN(int8, rk3568 simulator)，σ=12：**
```
clean  boxes=6 maxScore=0.842
noisy  boxes/frame mean 5.8      filt mean 6.5
adjacent-frame best same-class IoU: noisy=0.986  filt=0.989
```
日志：`sim/ov5640_tb/rknn_kf_auto_s12.log`。

> **结论**：自适应档在保 PSNR 的同时**保住检测**（σ=12 还提升时序 IoU）；**固定 K=1/4 虽然 PSNR 更高，却把检测框过度平滑到丢失**，因此板上选用自适应档是正确的工程取舍。逐位一致性由阶段一保证（ONNX 黄金用同一 Python 位精确模型）。

## 3. 阶段三：上板（cam1 滤波 / cam2 旁路对照 + 实时监测 + 截图）

### 3.1 构建与实现质量
- 工程副本 `project_kf/`（不动 GUI 打开的 `project/`）；无模块重名（158 模块 0 duplicate）。
- 资源：LUT **11096 / 66600 (16.66%)**、FF 11928、DRM 25.5 / 155；**KF 增量仅 +144 LUT / +227 FF / +2 DRM**。
- 时序：`project_kf/place_route/top_timing_summary_after_hold_fix.txt` = **Design Summary : All Constraints Met.**
  - pclk setup WNS **+1.102 ns**、hold **+0.288 ns**，**0 failing endpoints**（setup/hold/recovery/removal 全 0）。
  - pnr 2m2s + gen_bit_stream（4m47s 总计），无 `E:`。
- 现役 bitstream：`bitstream_2026-09-26_kf_gate/top.sbit`（`flash_kf_gate.tcl`）——RD1（读使能）+ 读桥单未决门。

### 3.2 实时监测（现役 KF 构建，真帧推送通路）
```
frame=1798 sync=TAG-SYNC disp=6.5fps pre=88.0ms infer=88.4ms boxes=0
--- summary ---
sync=TAG-SYNC  frames=65  disp=6.5fps  infer=84.6ms avg  pre=0.0ms avg
SELFTEST PASS
```
- `sync=TAG-SYNC`：读到 FPGA 写的帧计数标签，帧完整（非 `STBL-FALLBACK`）。
- 早前同构建 RD1 长跑：`frames=103 disp=10.3fps`；RD0（读禁用隔离）：`frames=104 disp=10.3fps`。
- 场景为**凌晨暗室**（两路相机均暗），YOLO 无真值目标，故 `boxes=0`；模型本身在板上可加载并推理（`infer≈85ms`），静图推理 `--image` 亦能出框（见 3.5 说明）。

### 3.3 关键：上一帧 DDR 回读**确实送回真实数据**（不是 0）

直接证据 = **同相机、同构建族、仅"读使能"不同、且场景亮度匹配**的两组采集：

| 采集 | 构建 | cam1 meanG6 | cam2 raw meanG6（照度参照） | cam1/cam2 |
|---|---|---|---|---|
| `FINAL_cam1_RD0_x0.ppm` | RD0（`RD_EN=0` ⇒ x 强制为 0） | **3.073** | 4.507 | 0.682 |
| `FINAL_cam1_KF.ppm` | RD1（读使能，现役） | **4.252** | 4.433 | **0.959** |

- 两次 `cam2 raw` 亮度仅差 1.7%（4.433 vs 4.507）⇒ 场景可比。
- 若回读恒为 0，RD1 输出应**等于** RD0；实测 RD1 比 RD0 高 **+38.4%** ⇒ **回读链路送回了非零、且把输出向输入拉回的数据**（正确/上一帧语义）。
- 独立佐证（自洽、不跨相机）：`host/detview/frame_source.h` 用 cam1 bank `0x00800000/0x00A00000`，与回读基址一致；`ov5640_ddr_w_ctrl.v` 中 `w_ping` 仅在 `frame_done` 翻转、`prev_frame_base = w_ping?addr1:addr2` 在整个帧内稳定；跨帧核对 `rd_inflight` 置/清（`ar_latch_now`↑ / `ddr_rvalid&rlast`↓）逻辑与仿真一致。

### 3.4 cam1（滤波）对 cam2（旁路）同刻对照
同一时刻双口采集（见 `board_dualcap.py`，走 bulk descriptor 通路；cam1 base `0x00800000`、cam2 base `0x00C00000`）：

| 采集 | cam1 meanG8 | cam2 raw meanG8 | 比值 |
|---|---|---|---|
| 现役 KF 构建 | 17.01 | 17.73 | **0.959** |

- **亮度被保持**（早前由跨 3 小时 detview PPM 得到的"压暗到 0.42"是**跨时间/跨渲染的误判**，同一时刻实测为 0.96）。
- 空间高频噪声代理 `hf_std`：cam1 KF = 3.12、cam2 raw = 1.88；**注意两相机视角/传感器不同**（降采样互相关仅 0.47），跨相机噪声对比仅作参考，不作结论。
- 交付图：`sim/ov5640_tb/board/FINAL_cam1_KF.ppm`、`FINAL_cam2_RAW.ppm`、`FINAL_cam1_RD0_x0.ppm`，以及无滤波基线 `cam1_base.ppm/cam2_base.ppm`。

### 3.5 RK3568 截图
X 在跑（`Xorg :0`），Qt 截图工具 `host/qshot` 可用：
- `sim/ov5640_tb/board/rk_desktop.png`（1024×576，桌面）
- `sim/ov5640_tb/board/rk_detview.png`（1024×576，`DISPLAY=:0` 前台运行 `detview` 的实时画面窗口 + HUD）

> 说明：`detview --image <ppm>` 在域外静图上会给出坐标退化的框（如 `(310,492)-(332,231)`，y 越界），属**既有模型解码/域外输入问题**，与本次滤波改动无关，此处仅记录不追。

---

## 4. 复现步骤

```powershell
# 阶段一（PowerShell 直调 ModelSim + Python 黄金比对）
$MS="C:\modeltech64_10.6e\win64"; $LIB="sim/ov5640_tb/work_kfstr"
& "$MS\vlib.exe" $LIB
& "$MS\vlog.exe" -quiet -work $LIB source/axi_dma/stream_pipe.v
& "$MS\vlog.exe" -quiet -work $LIB source/axi_dma/axi_dma_read.v
& "$MS\vlog.exe" -quiet -work $LIB source/ov5640/vip_kf.v
& "$MS\vlog.exe" -quiet -work $LIB source/ov5640/vip_kf_stream.v
& "$MS\vlog.exe" -quiet -work $LIB sim/ov5640_tb/tb_vip_kf_stream.v
& "$MS\vsim.exe" -c -lib $LIB tb_vip_kf_stream -do "run -all; quit -f" -l sim/ov5640_tb/kf_stream_sim.log
& "$MS\vsim.exe" -c -lib $LIB tb_vip_kf_stream -do "run -all; quit -f" -l sim/ov5640_tb/kf_stream_sim_wide.log -gW=640 -gH=2
& "C:\Users\NineSun\anaconda3\python.exe" sim/ov5640_tb/vip_kf_compare.py

# 阶段二
& "C:\Users\NineSun\anaconda3\python.exe" sim/ov5640_tb/vip_kf_yolo_check.py --img calib\img00.ppm --nframes 8 --sigma 8 --gain auto

# 阶段三：清目录 -> pnr -> gen_bit_stream（一次约 5-6 分钟，勿并发）
cd project
C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe -project <abs>/project/project_kf/project.pds -run pnr -work_dir <abs>/project/project_kf
C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe -project <abs>/project/project_kf/project.pds -run gen_bit_stream -work_dir <abs>/project/project_kf
```

**烧录顺序（关键，违反必静默死锁）**：先让 PCIe 链路 DOWN → 再 JTAG 烧录 → 再 rescan+insmod。
```bash
# 板上
pkill -x detview; rmmod pango_pci_driver
echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove      # 确认 lspci 无 0002:21
# 主面：burn_now.py flash_kf_gate.tcl
echo 1 > /sys/bus/pci/rescan; insmod /root/ov5640/pango_pci_driver.ko
cd /root/ov5640 && QT_QPA_PLATFORM=offscreen ./detview/detview --selftest 15 --model 0
```

---

## 5. 交付物清单

| 类别 | 文件 |
|---|---|
| 仿真日志 | `sim/ov5640_tb/kf_sim.log`、`kf_stream_sim.log`、`kf_stream_sim_wide.log` |
| 逐位比对 | `sim/ov5640_tb/vip_kf_compare.py`（`VIPKF_COMPARE_PASS`，224/896/8960 像素 0 失配） |
| 模型侧 | `sim/ov5640_tb/vip_kf_yolo_check.py`、`rknn_kf_check.py`、`rknn_kf_auto_s12.log` |
| 现役比特流 | `bitstream_2026-09-26_kf_gate/top.sbit` + `flash_kf_gate.tcl` |
| 对照比特流 | `bitstream_2026-09-25_kf_rd0/top.sbit` + `flash_kf_rd0.tcl`（x=0 参照） |
| 时序 | `project_kf/place_route/top_timing_summary_after_hold_fix.txt`（All Constraints Met） |
| 板上图像 | `sim/ov5640_tb/board/FINAL_cam1_KF.ppm`、`FINAL_cam2_RAW.ppm`、`FINAL_cam1_RD0_x0.ppm`、`cam*_base.ppm` |
| RK3568 截图 | `sim/ov5640_tb/board/rk_desktop.png`、`rk_detview.png` |
| 板端脚本 | `tools/board_dualcap.py`（双口回读）、`tools/board_gui_shot.sh`、`tools/burn_now.py`、`tools/sshx.py`、`tools/fetch.py` |
| 补丁 | `tools/patch_ddr_rd_gate.py`（读桥单未决门）、`tools/patch_rden.py`（KF_RD_EN 贯通） |

---

## 6. 已知限制 / 未决项

1. **照度漂移**：场景 AEC 在本次会话内让 cam2 raw meanG6 在 4.4～26.3 间波动，**跨时间的亮度比较必须匹配场景**；本报告已用"同刻 cam2 参照 + 匹配亮度对"规避。若需严格的"无滤波 vs 滤波"同亮度对照，应再烧基线并在与滤波帧相近照度下成对采集。
2. **跨相机对比仅参考**：cam1/cam2 为两颗传感器、视角略异（降采样互相关 0.47），噪声绝对值不可直接比较；滤波正确性已由仿真位精确 + RD1/RD0 同相机对照确定。
3. `detview --image` 域外静图框坐标退化——既有问题，未修。
4. 板上场景真实目标缺失（暗室），Live 检测框为 0，属场景而非链路问题。
5. 未向用户确认项：是否接受"时域替代空间形式"；阈值走顶层参数还是 `prep_regs` 寄存器；是否先修 DDR 写缺陷（双摄 2–15s wedge / 引擎两帧未 ACK 停写 / free-running `xdma_req` stuck 2'b11）再上帧存读取。
