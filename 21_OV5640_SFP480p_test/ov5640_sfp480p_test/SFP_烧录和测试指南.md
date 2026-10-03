# 50K 板烧录和测试指南

## 比特流文件信息
- **文件路径**: `ov5640_sfp480p_test/ov5640_sfp480p_test/generate_bitstream/hdmi_ddr_ov5640_top.sbit`
- **文件大小**: ~2.1 MB
- **生成日期**: 2026-10-01（带 CTC 修复）

## 修改内容回顾
- 在 `sfp_video_tx.v` 中添加了 GE CTC skip 序列支持
- 每 8 拍在第 6 拍插入 skip 有序集 (32'h28BC_28BC)
- 添加 FIFO 弹出门控，防止像素丢失

## 一、烧录步骤

### 方法 1: 使用 PDS GUI 烧录

1. **打开 PDS Programmer**
   ```
   开始菜单 → Pango Design Suite → PDS Programmer
   ```

2. **配置烧录器**
   - Device: 选择 PGL50H (PANGO)
   - File: 浏览选择 `hdmi_ddr_ov5640_top.sbit`
   - 连接烧录器到 50K 板的 JTAG 接口

3. **烧录**
   - 点击 "Program"
   - 等待进度条完成
   - 看到 "Program Successful" 提示

### 方法 2: 使用命令行烧录

```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test/generate_bitstream

# 使用 pds_pgm 命令行工具
C:/pango/PDS_2022.2-SP6.4/bin/pds_pgm.exe \
  -device PGL50H \
  -operation program \
  -file hdmi_ddr_ov5640_top.sbit
```

## 二、LED 状态检查

烧录完成后，观察 50K 板上的 LED：

| LED | 引脚 | 信号名 | 含义 | 预期状态 |
|-----|------|--------|------|---------|
| - | F8 | led_sfp_pll | HSST PLL 锁定 | ✓ 亮 (1) |
| - | F7 | led_sfp_ready | PLL 锁定 + TX lane done | ✓ 亮 (1) |
| - | A5 | led_sfp_rxsync | 收到 100H 回传 + RX PCS 同步 | ✓ 亮 (1) ⚠️ **关键** |
| - | A3 | led_sfp_pcs | 诊断用（TX PCS 同步） | ✓ 亮 (1) |

### 关键指标
- **led_sfp_rxsync (A5)** 必须点亮！
- 修复前：此 LED 不亮（50K 收不到 100H 的回传）
- 修复后：此 LED 应该亮（双向通信建立）

## 三、100H 板状态检查

### 3.1 读取 SFP 状态寄存器

在 100H 主机上运行：

```python
# 假设你有 FPGA 寄存器读取工具/API
# 基地址: 0x20000000
# SFP 状态寄存器偏移: +0x144

sfp_status = read_reg(0x20000144)

# 解析各个位
pll_lock      = (sfp_status >> 0) & 1  # bit[0]
txlane_done   = (sfp_status >> 1) & 1  # bit[1]
rxlane_done   = (sfp_status >> 2) & 1  # bit[2] ⚠️ 关键
pcs_synced    = (sfp_status >> 3) & 1  # bit[3] ⚠️ 关键

print(f"100H SFP Status Register: 0x{sfp_status:02X}")
print(f"  [0] PLL Lock:      {pll_lock}     (预期: 1)")
print(f"  [1] TX Lane Done:  {txlane_done}  (预期: 1)")
print(f"  [2] RX Lane Done:  {rxlane_done}  (预期: 1) ⚠️ 修复前为 0")
print(f"  [3] PCS Synced:    {pcs_synced}   (预期: 1) ⚠️ 修复前为 0")
```

### 3.2 预期结果

**修复前**:
```
100H SFP Status: 0x03
  [0] PLL Lock:      1
  [1] TX Lane Done:  1
  [2] RX Lane Done:  0  <- CDR 未对齐
  [3] PCS Synced:    0  <- PCS 未同步
```

**修复后**:
```
100H SFP Status: 0x0F
  [0] PLL Lock:      1  ✓
  [1] TX Lane Done:  1  ✓
  [2] RX Lane Done:  1  ✓ 成功！
  [3] PCS Synced:    1  ✓ 成功！
```

## 四、视频流功能测试

### 4.1 检查摄像头图像接收

在 100H 主机上读取 DDR 中的帧数据：

```python
# cam5 = 50K 的 cam1 (前 640 列)
# cam6 = 50K 的 cam2 (后 640 列)

# 读取一帧 cam5 数据
frame_cam5 = read_camera_frame(cam_id=5, width=640, height=480, format='RGB565')

# 读取一帧 cam6 数据
frame_cam6 = read_camera_frame(cam_id=6, width=640, height=480, format='RGB565')

# 保存为图像文件
save_image(frame_cam5, "test_cam5_from_50k.png")
save_image(frame_cam6, "test_cam6_from_50k.png")
```

### 4.2 图像质量检查清单

- [ ] **图像无花屏/雪花** - 像素数据完整
- [ ] **色彩正确** - RGB565 解码正确，无色偏
- [ ] **无撕裂/错位** - VS/HS 同步正常
- [ ] **帧率稳定** - 640x480@60fps（或配置的帧率）
- [ ] **cam5 和 cam6 内容对应** - 分别对应 50K 的 cam1 和 cam2

### 4.3 长时间稳定性测试

```bash
# 运行 1 小时以上，记录：
# - 丢帧次数
# - 图像是否漂移/错位
# - LED 是否持续点亮
# - 无异常日志
```

## 五、故障排查

### 情况 1: led_sfp_pll (F8) 不亮
**原因**: HSST PLL 未锁定
**检查**:
- 参考时钟 sfp_refckp/n 是否连接正确
- 参考时钟频率是否为 125MHz
- HSST IP 配置是否正确

### 情况 2: led_sfp_ready (F7) 不亮
**原因**: TX lane 未 ready
**检查**:
- PLL 是否锁定（检查 led_sfp_pll）
- TX lane 复位序列是否正常
- 光模块是否插好

### 情况 3: led_sfp_rxsync (A5) 不亮（关键）
**原因**: 收不到 100H 回传或 RX PCS 未同步

**可能原因 A - 100H 未发送**:
- 检查 100H 的 TX lane 是否 ready（寄存器 bit[1]）
- 检查光纤连接是否正常
- 使用光功率计测量 100H TX 光功率

**可能原因 B - 50K RX 问题**:
- 检查 50K 的 RX CDR 是否锁定（需要额外诊断寄存器）
- 检查光模块接收灵敏度

**可能原因 C - CTC 修复不生效**:
```bash
# 验证 CTC 代码是否真的被编译进去
cd ov5640_sfp480p_test/ov5640_sfp480p_test
grep -n "ctc_phase\|SKIP_WORD" source/rtl/sfp_video_tx.v

# 检查综合报告
grep "ctc_phase" synthesize/ov5640_sfp480p_test_syn.rpt
```

### 情况 4: 100H rxlane_done=0 (bit[2])
**原因**: CDR 未对齐

**诊断步骤**:
1. 确认 50K TX 是否在发送数据（led_sfp_ready 亮）
2. 确认光纤连接正常
3. 使用逻辑分析仪抓取 50K TX 输出：
   - 信号: `i_txd_2[31:0]`, `i_txk_2[3:0]`
   - 确认每 8 个字中有 1 个 skip (28BC28BC, txk=0101)
   - 确认 skip 位置在第 6 拍

### 情况 5: 100H pcs_synced=0 (bit[3])
**原因**: PCS 未同步，但 CDR 已对齐

**诊断步骤**:
1. 确认 skip 有序集格式正确：
   ```
   SKIP_WORD = 0x28BC28BC
   SKIP_K    = 0b0101
   
   解析:
   byte0 = 0xBC (K28.5) - K码
   byte1 = 0x28 (D28.2) - D码
   byte2 = 0xBC (K28.5) - K码
   byte3 = 0x28 (D28.2) - D码
   ```

2. 检查 100H RX 配置：
   ```
   RXPCS_CTC = "GE"          <- 必须
   RXPCS_ALIGN = "GE_MODE"
   RXPCS_COMMA_SEL = "K28.5"
   ```

3. 如果以上都正确但仍不同步，尝试调整 skip 拍的相位：
   ```verilog
   // 当前: 第 6 拍插入 skip
   if (ctc_phase == 3'd6) begin
   
   // 尝试: 第 0 拍
   if (ctc_phase == 3'd0) begin
   ```

### 情况 6: 图像有问题但链路正常
**原因**: skip 拍插入影响了像素流

**检查**:
```verilog
// 确认 FIFO 弹出门控正确使用
wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);

// skip 拍时 pix_pend 保持不变
if (ctc_phase == 3'd6) begin
    txd <= `UD SKIP_WORD;
    txk <= `UD SKIP_K;
    // pix_pend 和 pix0 不变
end
```

**诊断**:
- 统计接收到的像素数是否正确: 640×480 = 307,200
- 检查 FIFO 是否溢出
- 检查帧同步信号 (VS/HS) 是否正常

## 六、性能验证

### 6.1 带宽测试
```
理论带宽: 5 Gbps × 87.5% (skip 开销) = 4.375 Gbps
实际需求: 640×480@60fps × 16bpp × 2 cam = 18.43 Mbps
带宽占用率: 0.42% ✓ 充足
```

### 6.2 延迟测试
```
Skip 拍延迟: 8ns/拍 × 1/8 = 1ns 平均延迟
帧延迟增加: ~307µs/帧 (< 1ms) ✓ 可接受
```

### 6.3 时序裕量
从编译报告:
```
p_clk2core_tx_2 (125MHz, SFP TX 时钟域):
  Setup WNS: 3.933 ns ✓ 良好
  Hold WHS:  0.339 ns ✓ 良好
```

## 七、回滚方案

如果修复后仍无法通信，回滚到原版本：

```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl

# 恢复原始文件
cp sfp_video_tx.v.bak_before_ctc_fix sfp_video_tx.v

# 重新编译
cd ../..
# 使用 PDS GUI 重新编译
```

## 八、成功标志总结

- [x] 50K 编译成功，无 Error/Critical Warning
- [ ] 50K 烧录成功
- [ ] 50K LED: led_sfp_pll=1, led_sfp_ready=1, **led_sfp_rxsync=1**
- [ ] 100H 寄存器 +0x144 = **0x0F** (bit[3:0] 全部为 1)
- [ ] 100H 能接收到 cam5/cam6 视频流
- [ ] 图像质量正常，无花屏/撕裂
- [ ] 长时间运行稳定 (>1 小时)

## 相关文档
- `SFP_修复总结.md` - 完整技术说明
- `SFP_验证清单.md` - 详细验证步骤
- `SFP_100H_50K_对比分析.md` - 问题诊断报告
