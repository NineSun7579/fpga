# 50K 硬件 CTC 版本编译最终状态

## 编译进度

### ✅ 已完成
1. **编译（Compile）**: 36秒 ✓
2. **综合（Synthesize）**: 51秒 ✓
3. **布局布线（PNR）**: 完成 ✓
   - 布局: 45.62秒（WNS=2432, TNS=0）
   - 布线: 完成，所有网络已布线

### 🔄 进行中
4. **比特流生成（Bitstream）**: 正在进行
   - 当前: Placement 阶段
   - 预计: 5-10 分钟完成

## 关键配置修改总结

### HSST IP 核 CTC 配置
| 配置项 | 修改前 | 修改后 | 状态 |
|--------|--------|--------|------|
| CH2_RXPCS_CTC | Bypassed | GE | ✓ |
| PCS_CH2_BYPASS_CTC | 1 (旁路) | 0 (启用) | ✓ |

### sfp_video_tx.v 代码清理
- ✅ 移除 CTC 相位计数器 (`ctc_phase`)
- ✅ 移除 SKIP 序列定义 (`SKIP_WORD`, `SKIP_K`)
- ✅ 移除 skip 插入逻辑
- ✅ 恢复正常 FIFO 读取流程

### 100H vs 50K 配置一致性
| 项目 | 100H (RX) | 50K (TX) | 状态 |
|------|-----------|----------|------|
| RXPCS_CTC | GE | GE | ✓ 匹配 |
| BYPASS_CTC | - | 0 (不旁路) | ✓ 正确 |
| 手动 CTC | 无 | 已移除 | ✓ 一致 |

## 编译日志
- **文件**: `build_hw_ctc.log`
- **大小**: ~80,000 行
- **错误**: 0 个 ERROR
- **警告**: 仅有常规警告（未驱动信号、时序约束等）

## 比特流文件信息

编译完成后的比特流：
```
文件: generate_bitstream/hdmi_ddr_ov5640_top.sbit
预计大小: ~3-5 MB
```

## 备份文件清单

### 配置备份
- `hsst_test.idf.bak_before_ge_ctc` - 原始 IDF（CTC=Bypassed）

### 代码备份
- `sfp_video_tx.v.bak_with_manual_ctc` - 手动 CTC 版本
- `sfp_video_tx.v.bak_before_ctc_fix` - 最初版本（无 CTC）

### 如需恢复到手动 CTC 版本
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test
cp source/rtl/hsst_test/hsst_test.idf.bak_before_ge_ctc source/rtl/hsst_test/hsst_test.idf
cp source/rtl/sfp_video_tx.v.bak_with_manual_ctc source/rtl/sfp_video_tx.v
# 然后重新编译
```

## 下一步操作（编译完成后）

### 1. 验证比特流文件
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test
ls -lh generate_bitstream/hdmi_ddr_ov5640_top.sbit
# 应该显示 3-5 MB 的文件
```

### 2. 烧录到 50K 板
```bash
# 使用 Pango Programmer
pgp_programmer \
  -device PGL50H \
  -file generate_bitstream/hdmi_ddr_ov5640_top.sbit \
  -mode program
```

### 3. 测试与 100H 的通信

#### 在 100H 上验证
1. **LED 检查**:
   - `led_sfp_rxsync` 应该亮起（绿色）

2. **寄存器检查**:
   ```bash
   # 读取 SFP RX 状态寄存器
   devmem 0x40000144
   # 预期: bit[2]=1 (rxlane_done), bit[3]=1 (pcs_synced)
   ```

3. **视频流测试**:
   - 启动 cam5/cam6
   - 100H 应该能接收到视频流
   - `/dev/video5` 和 `/dev/video6` 应该有数据

## 技术原理说明

### 为什么需要修改 HSST IP 配置

**问题根源**:
- 50K 的 HSST IP 配置为 `Bypassed`，不插入 GE CTC skip
- 100H 的 HSST IP 配置为 `GE`，期望接收 GE CTC 协议数据
- **协议不匹配** 导致 100H 无法同步

**手动实现的局限**:
虽然我们在 `sfp_video_tx.v` 中手动添加了 skip 插入，但：
1. GE CTC 不仅是插入 skip，还包括 PCS 状态机配置
2. 8B/10B 编码需要符合 GE 标准
3. 时钟补偿 FIFO 需要正确控制
4. IP 核内部可能有其他 GE 模式相关的配置

**硬件实现的优势**:
- 完全符合 GE CTC 标准（IEEE 802.3）
- 时序精确，硬件处理
- 与 100H RX 硬件完美匹配
- 无需担心遗漏的协议细节

### GE CTC 协议简介

**Clock Tolerance Compensation (CTC)**:
- 目的: 补偿 TX 和 RX 时钟频率差异（±100 ppm）
- 方法: 每隔一定周期插入/删除 SKIP 序列
- SKIP 序列: `{D28.2, K28.5, D28.2, K28.5}` = `0x28BC28BC`
- 周期: GE 模式下约每 8 拍插入一次

## 预期测试结果

### 成功标志
- ✅ 100H `led_sfp_rxsync` 亮起
- ✅ 寄存器 `+0x144` bit[2:3] = 0b11
- ✅ 能接收 cam5/cam6 视频流
- ✅ 视频质量正常，无花屏

### 如果仍然失败
可能的原因和排查：
1. **IP 核未正确重新生成**: 
   - 手动用 GUI 重新生成 HSST IP 核
   - 检查 `hsst_test.v` 的时间戳

2. **其他 HSST 配置不匹配**:
   - 对比 100H 和 50K 的完整 HSST 配置
   - 检查 ALIGN、COMMA_SEL 等参数

3. **物理层问题**:
   - 检查光模块状态
   - 测试光纤连接
   - 使用示波器查看差分信号

## 编译时间统计

| 阶段 | 耗时 | 备注 |
|------|------|------|
| Compile | 36秒 | ✓ |
| Synthesize | 51秒 | ✓ |
| Place | 45秒 | WNS=2432 ✓ |
| Route | ~20分钟 | 全部布通 ✓ |
| Bitstream | ~5-10分钟 | 进行中 |
| **总计** | **~30-40分钟** | 预计 |

## 相关文档
- `HSST_CTC_配置对比分析.md` - 详细技术分析
- `50K_CTC_配置最终确认.md` - 配置确认
- `SFP_烧录和测试指南.md` - 测试步骤
- `SFP_修复总结.md` - 之前的修改记录
