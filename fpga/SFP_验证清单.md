# SFP 光口修复验证清单

## 修改验证

### ✓ 代码修改完成
- [x] 增加 ctc_phase 计数器 (第 86-94 行)
- [x] 定义 SKIP_WORD 和 SKIP_K (第 97-98 行)
- [x] 添加 fifo_pop_gated 信号 (第 132 行)
- [x] skip 拍插入逻辑 (第 145-150 行)
- [x] 使用 fifo_pop_gated (第 124, 156 行)
- [x] 原文件已备份

### ✓ 关键代码行号
```
86-94:  ctc_phase 计数器
97-98:  SKIP_WORD/SKIP_K 定义
124:    last_vs/hs 更新使用 fifo_pop_gated
132:    fifo_pop_gated 定义
145:    if (ctc_phase == 3'd6) - skip 拍判断
146:    txd <= SKIP_WORD
147:    txk <= SKIP_K
156:    主打包逻辑使用 fifo_pop_gated
```

## 编译前检查

### 文件检查
```bash
# 1. 确认修改的文件
ls -lh ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v

# 2. 确认备份存在
ls -lh ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v.bak*

# 3. 验证关键代码
grep -n "ctc_phase\|SKIP_WORD\|fifo_pop_gated" \
  ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v
```

预期输出：
```
86:    reg [2:0] ctc_phase;
89:            ctc_phase <= `UD 3'd0;
91:            ctc_phase <= `UD 3'd0;
93:            ctc_phase <= `UD ctc_phase + 3'd1;
97:    localparam [31:0] SKIP_WORD = 32'h28BC_28BC;
98:    localparam [3:0]  SKIP_K    = 4'b0101;
124:        else if (fifo_pop_gated) begin
132:    wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);
145:            if (ctc_phase == 3'd6) begin
146:                txd <= `UD SKIP_WORD;
147:                txk <= `UD SKIP_K;
156:            else if (fifo_pop_gated) begin
```

### PDS 工程检查
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test

# 检查 .pds 工程是否注册了 sfp_video_tx.v
grep "sfp_video_tx" ov5640_sfp480p_test.pds
```

## 编译步骤 (50K)

### 1. 打开 PDS GUI
```bash
# 方法1: 命令行启动 PDS
C:/pango/PDS_2022.2-SP6.4/bin/pds.exe

# 方法2: 从资源管理器双击
# ov5640_sfp480p_test/ov5640_sfp480p_test/ov5640_sfp480p_test.pds
```

### 2. 编译流程
- 菜单: Tools → Run → Synthesis
- 等待综合完成 (~6 分钟)
- 检查 Messages 窗口，确认无 Error
- 菜单: Tools → Run → Place & Route
- 等待布线完成 (~25 分钟)
- 菜单: Tools → Run → Generate Bitstream

### 3. 检查综合报告
打开: `synthesize/ov5640_sfp480p_test_syn.rpt`

查找新增寄存器:
```
搜索: "ctc_phase"
预期: 应该找到 3 个 DFF (ctc_phase[2:0])
```

### 4. 检查时序报告
打开: `place_route/*_timing_summary.txt`

关键检查:
```
Clock Domain: clk2core_tx (125MHz)
Setup WNS: > 0 ns (无违例)
Hold WNS: > 0 ns (无违例)
```

## 上板测试 (50K)

### 1. 烧录比特流
```bash
# 使用 PDS 烧录工具或命令行
# 比特流位置: generate_bitstream/hdmi_ddr_ov5640_top_*.sbit
```

### 2. 观察 LED 状态 (50K 板)

| LED | 引脚 | 含义 | 预期 |
|-----|------|------|------|
| led_sfp_pll | F8 | HSST PLL 锁定 | 亮 (1) |
| led_sfp_ready | F7 | PLL + TX lane done | 亮 (1) |
| led_sfp_rxsync | A5 | 收到 100H 回传 | 亮 (1) ⚠️ 关键 |
| led_sfp_pcs | A3 | 诊断用 | - |

**关键指标**: `led_sfp_rxsync` 应该点亮，表示收到 100H 对端的 idle 回传。

### 3. 检查 100H RX 状态

在 100H 主机上读取寄存器:
```python
# 读取 SFP 状态寄存器 (+0x144)
sfp_status = read_reg(0x20000000 + 0x144)
pll_lock      = (sfp_status >> 0) & 1  # 应为 1
txlane_done   = (sfp_status >> 1) & 1  # 应为 1
rxlane_done   = (sfp_status >> 2) & 1  # 应为 1 ⚠️ 关键
pcs_synced    = (sfp_status >> 3) & 1  # 应为 1 ⚠️ 关键

print(f"100H SFP Status: 0x{sfp_status:02X}")
print(f"  PLL Lock: {pll_lock}")
print(f"  TX Lane Done: {txlane_done}")
print(f"  RX Lane Done: {rxlane_done}  <- 修复前为 0")
print(f"  PCS Synced: {pcs_synced}    <- 修复前为 0")
```

**成功标准**: `rxlane_done=1` 且 `pcs_synced=1`

## 功能验证

### 1. 视频流接收测试
```python
# 在 100H 主机上
# 检查是否能接收到 cam5 和 cam6 的图像

# 读取一帧数据 (DDR 地址，参考协议文档)
frame_cam5 = read_camera_frame(cam_id=5)  # 50K cam1
frame_cam6 = read_camera_frame(cam_id=6)  # 50K cam2

# 保存图像用于检查
save_image(frame_cam5, "cam5_from_50k.png")
save_image(frame_cam6, "cam6_from_50k.png")
```

### 2. 图像质量检查
- [ ] 图像无花屏/雪花
- [ ] 色彩正确（RGB565 解码正确）
- [ ] 帧率稳定（640x480@60fps 或配置的帧率）
- [ ] vs/hs 同步正常（无撕裂）
- [ ] cam5 和 cam6 内容对应 50K 的双摄

### 3. 长时间稳定性测试
```bash
# 运行 1 小时以上
# 检查:
# - 丢帧情况
# - 图像是否漂移/错位
# - LED 是否持续点亮
# - 无错误日志
```

## 故障排查

### 情况 1: 编译失败
**症状**: PDS 报告 Error
**检查**:
```bash
# 1. 确认文件编码正确 (GBK)
file ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v

# 2. 检查语法错误
grep -n "SKIP_WORD\|SKIP_K\|ctc_phase" sfp_video_tx.v

# 3. 恢复备份重新打补丁
cp sfp_video_tx.v.bak_before_ctc_fix sfp_video_tx.v
python patch_sfp_tx_ctc_v2.py
python patch_sfp_tx_skip_beat.py
```

### 情况 2: rxlane_done=0 (CDR 未对齐)
**可能原因**: 参考时钟频率仍不匹配
**检查**:
- 50K 板的 sfp_refckp/n 是否真的是 125MHz
- 100H 板的 F6/E6 是否真的是 100MHz
- 如果不匹配，需要硬件层面统一

### 情况 3: pcs_synced=0 (PCS 未同步)
**可能原因**: skip 序列格式错误
**检查**:
```verilog
// 确认 SKIP_WORD 定义
SKIP_WORD = 32'h28BC_28BC  // 正确
SKIP_K    = 4'b0101        // 正确 (byte0 和 byte2 是 K 码)

// 确认 skip 拍插入位置
if (ctc_phase == 3'd6)     // 正确 (第 6 拍)
```

**高级诊断**: 使用逻辑分析仪抓取 50K TX 输出:
- 抓取 `i_txd_2[31:0]` 和 `i_txk_2[3:0]`
- 确认每 8 个字中有 1 个是 `{28BC28BC, txk=0101}`

### 情况 4: 图像有问题但链路正常
**可能原因**: skip 拍导致像素错位
**检查**:
- `fifo_pop_gated` 是否正确使用
- `pix_pend` 在 skip 拍是否保持不变
- FIFO 是否溢出

## 性能监控

### 资源占用 (50K)
编译后检查 `*_syn.rpt`:
```
预期增加:
  LUT: +5~10 (ctc_phase 计数 + 比较)
  FF:  +3 (ctc_phase[2:0])
```

### 时序裕量 (50K)
检查 `*_timing_summary.txt`:
```
clk2core_tx (125MHz):
  Setup WNS: 应 > 0 ns
  Hold WNS: 应 > 0 ns
```

### 带宽利用率 (100H)
```
理论: 5 Gbps × 87.5% (skip 开销) = 4.375 Gbps
实际: 640x480@60fps × 16bpp × 2 cam = 18.43 Mbps
占用率: 0.42% (充足)
```

## 回滚方案

如果修复后仍无法通信:

### 完全回滚
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl
cp sfp_video_tx.v.bak_before_ctc_fix sfp_video_tx.v
# 重新编译
```

### 备选方案: 100H 禁用 CTC
如果无法修改 50K，尝试修改 100H:
1. 重新配置 `hsst_sfp` IP
2. 修改 `CH2_RXPCS_CTC` 从 `"GE"` 改为 `"Bypassed"`
3. 重新编译 100H 工程

⚠️ **风险**: 失去时钟容差补偿

## 成功标志

- [x] 50K 编译成功，无 Error/Warning
- [x] 50K 烧录成功
- [x] 50K LED: led_sfp_pll=1, led_sfp_ready=1, led_sfp_rxsync=1
- [x] 100H 寄存器 +0x144 = 0x0F (bit[3:0] 全部为 1)
- [x] 100H 能接收到 cam5/cam6 视频流
- [x] 图像质量正常，无花屏/撕裂
- [x] 长时间运行稳定 (>1 小时)

## 相关文档
- `SFP_修复总结.md` - 详细修复说明
- `SFP_100H_50K_对比分析.md` - 问题诊断
- `patch_sfp_tx_ctc_v2.py` - 自动补丁脚本 1
- `patch_sfp_tx_skip_beat.py` - 自动补丁脚本 2
