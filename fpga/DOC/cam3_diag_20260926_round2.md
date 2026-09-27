# cam3 诊断报告（2026-09-26 第二轮上板）

比特流：`bitstream_cam3_verified_20260926_204817/top.sbit`
SHA256：`B691C6D705B50C7CD143645CBB08D120F4C8F9CBE13606F687CDC1127CEC4147`
（含 VSYNC 去毛刺 + 帧控制器修复 + I²C 直通）

## 1. 结论摘要

- **I²C 主机直通可用**（已实测）。
- cam3 相机侧信号正常：PCLK≈86MHz、行率与 cam1/cam2 一致（比值 3887/3887/3860，差 0.7%），三路 VSYNC 均 ≈48fps。
- **cam3 的两个 DDR 缓冲内容不同**：ping `0x01000000` 基本干净，pong `0x01200000` 大面积损坏。
- cam3 帧**数据体写入被大量丢弃**（帧 tag 仍在推进，约 3 帧/s，而采集 48fps）。
- 本构建时序全部收敛（All Constraints Met，cmos3_pclk WNS +4.809ns，0 failing endpoints），排除时序违例。

## 2. I²C 直通验证（任务完成）

用 `tools/cam3_i2c_pt.py`（板端 `python3 /tmp/cam3_i2c_pt.py`）：

| 操作 | 结果 |
|---|---|
| `rd 0x503d` | 0x00 |
| `wr 0x503d 0x80` → `rd 0x503d` | 0x80（**回读精确**，高半字节保留） |
| `wr 0x503d 0x00` → `rd 0x503d` | 0x00 |
| `testpat on` | cam3 画面出现**彩条测试图**（青/绿/黑/白/品红/红…） |
| `id`（0x300A/0x300B） | 0x06 / 0x00（非 0x56/0x40，见下） |

- 传感器对 SCCB **有 ACK**，写后回读一致 → **I²C 读写通路正常**。
- 内部诊断（`BASE+0x50 = {NACK, ID_H, ID_L}`）：cam3 = 0x0000_0600，cam1/cam2 = 0。
  内部路径与直通路径**结果一致**（都 0x06/0x00），说明直通读回忠实。
- cam3 I²C 事务数 274 = 264（初始化）+ 10（本轮直通），**再次印证直通生效**。
- 0x300A/0x300B 返回 0x06/0x00（而非 0x56/0x40）**待查**：可能是读采样位数问题（两条路径共用 `i2c_dir.v`，其 st_data_rd 在 SCL 低电平采样），也可能是该模组 ID 区特殊。不影响写通路。

## 3. cam3 画面损坏定位

方法：停显示后用 `tools/dump_cam3_frame.py` 直接把 DDR 帧 dump 成 PPM 比对。

- `0x01000000`（ping）：基本干净的竖直彩条，逐帧稳定。
- `0x01200000`（pong）：**大面积斜向绿/品红条纹**，仅底部约 15 行有真实彩条。

重复采样（静态彩条）：
- A1/A2/A3（同一地址）：差异 0.15–0.34% → **稳定**。
- B1/B2/B3：差异 0.18–0.34% → **稳定**。
- A vs B：差异 **81.6%** → 两缓冲**系统性不同**（非随机噪声）。

→ 损坏是**确定性/与缓冲相关**的，不是信号完整性噪声。

帧 tag 检查（`base+0x96000`，2s 采样）：
| 通道 | ping tag | pong tag |
|---|---|---|
| cam1 | 13941→13947 | 13942→13948 |
| cam2 | 13941→13947 | 13942→13948 |
| cam3 | 13943→13947 | 13942→13948 |

→ **cam3 两个缓冲的 tag 都在推进**（FPGA 确实在写），但**帧完成率仅约 3 帧/s**，而采集 48fps → 帧数据体大量丢弃。cam3 DDR 内容因而长时间停留在旧的彩条帧（显示冻结）。

相机侧计数器：三路 VSYNC 均 49145→49241（2s，≈48/s），cam3 与 cam1/cam2 一致 → 采集侧正常。

## 4. 补光灯

- 按 `0x3016/0x301c/0x3019 = 0x02` 写入并回读，**回读均为 0x00**。
- 查初始化表 `ov5640_i2c_rgb565_cfg.v`：`0x3016=0x02, 0x301c=0x02` 属上电序列，
  `0x3019=0x02` 注释为 “enable clocks while finalizing”，`0x3019=0x00` 才是 stream-on。
  → 这三条**不是**独立 LED/闪光寄存器，**原补光灯寄存器假设可能不成立**，需重新确认。
- OV5640 闪光/频闪（FREX）为独立功能，需确认该模组 LED 的实际控制脚与寄存器。

## 5. 板端状态与工具

新增工具（本机 `tools/`，板端 `/tmp/`）：
- `tools/board_peek.py`  — 任意 AXI 地址 32bit 读
- `tools/board_poke.py` — 任意 AXI 地址 32bit 读/写
- `tools/dump_cam3_frame.py` — dump cam3 DDR 帧为 PPM
- `tools/ddr_marker_probe.py` — 各通道 ping/pong 标记探针

**已知板端问题**：向 AXI **寄存器**写（H2F，cmd4）在本轮多次调用后**超时挂死**
（读 cmd5 正常，DDR 读正常）。此状态会使 H2F 写永久阻塞，需 **重新烧录 FPGA** 清除。

## 6. 下一步

1. **重新烧录**清除 H2F 挂死与传感器彩条状态，恢复三路实时显示。
2. 关彩条后重新双截图，确认 cam3 是否仍冻结 / 损坏。
3. 重点查 **cam3 帧数据体写入被丢弃**：`ov5640_ddr_w_ctrl.v` / `ov5640_ddr.v` 的
   `frame_active`、`WAIT_TAG_DONE`、以及在 DDR 仲裁 AW 背压下的 payload 保持
   （与已知“仲裁器 AW 背压 payload 不稳定”一致）。
4. 复核 cam3 的 DVP 引脚/输入延时约束与 I²C 读采样。
5. 补光灯寄存器需重新确认（当前 0x3016/0x3019/0x301c 假设存疑）。

## 7. 重烧后的复测（2026-09-26 21:10）

重烧同一比特流后（清除 H2F 挂死 + 传感器彩条状态），`validate_cam3_display.py`：

| 区域 | changed_pixels_gt8 / 68265 | 结论 |
|---|---|---|
| cam1 | 19963 | 实时、正常场景 |
| cam2 | 19117 | 实时、正常场景 |
| cam3 | **66889** | 几乎全画面在变 → 撕裂/条纹，非有效画面 |

截图 `cam3_verify_20260926_211043_b.png`：cam3 为严重斜向撕裂，仅能隐约辨认亮斑，**未通过验收**。

### 关键量测（重烧后）
- 三路 VSYNC 均 ≈48fps；三路帧 tag 均约 3/s → **3fps 帧完成率是全局现象，非 cam3 独有**。
- 因此 cam3 的问题**不是**帧完成率，而是**帧内容损坏**（cam1/cam2 在同样 3fps 下画面正常）。
- 未解之谜：ping `0x01000000` 基本干净、pong `0x01200000` 大面积损坏，
  而两者地址生成路径对称。需查 0x01200000 区域是否与其它主设备/主机访问冲突。

## 8. 根因确认与修复（2026-09-26 22:00）

### 8.1 根因：`ddr_w_arb.v` 的 AW 选择在背压下漂移（AXI 违例）
- 旧实现由**组合**授权直接驱动从口 AW 载荷，授权条件随当前 `m*_awvalid` 变化，
  选择只在 `s_awready` 接受时（旧 167–172 行）才锁存。
- 后果：当某主设备的 AW 已在等 `AWREADY`（下游背压）时，另一个（更高优先级）主设备拉起
  `AWVALID`，共享的 `s_awvalid` 保持高，但 `s_awaddr/s_awid` **在同一握手内改变**
  → 违反 AXI4（AW 载荷在 AWVALID 有效期间必须稳定）。
- DDR3 IP 可能锁存撕裂/错误的描述符 → 丢弃或错配整数个 beat → **cam2 整帧旋转、cam3 逐帧撕裂**；
  cam1 为最高优先级、基本不被抢占 → 干净。
- 仿真已**独立复现**（`sim/cam3_arb_test`，mode2）：`AW_STABILITY_FAIL` @56ns，与板上现象一致。

### 8.2 修复
- `source/axi_crossbar/ddr_w_arb.v`（标记 `[WARBFIX 2026-09-26]`）：新增 `sel/sel_valid`，
  把轮询选择**锁存**；`eff_sel = sel_valid ? sel : pick_sel`，`eff_valid = ~busy & (sel_valid | pick_v)`。
  被选中主设备的载荷被冻结，直到 `AWREADY` 接受；接受时才推进 RR 并清除 `sel_valid`。
- 备份：`source/axi_crossbar/ddr_w_arb.v.bak_warbfix_20260926`。
- 仿真复验（`sim/cam3_arb_test/run.py`）：
  - mode0 / mode1：**PASS THROUGHPUT**（RR 公平性、吞吐、背压覆盖均保持）。
  - mode2：由 `AW_STABILITY_FAIL` → **`AW_STABILITY_PASS`**（修复生效）。

### 8.3 本轮重编译
- 编排：`tools/build_cam3_verified.ps1`（清理 project_kf 产物 → `-run pnr` → `-run gen_bit_stream` → 快照，
  快照新增 `ddr_w_arb.v`）。
- 产物：`bitstream_cam3_verified_<ts>/top.sbit`，烧录后做双截图 + 三路 DDR dump 复验。
- 验收标准：三路均为真实场景且持续更新；cam3 不再撕裂。
