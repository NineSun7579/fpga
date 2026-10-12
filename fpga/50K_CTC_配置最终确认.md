# 50K HSST IP 核 CTC 配置最终确认

## ✅ 所有配置已正确修改

### 1. HSST IP 核配置（IDF 文件）
- **CH2_RXPCS_CTC**: `Bypassed` → `GE` ✓
- **PCS_CH2_BYPASS_CTC**: `1` → `0` ✓（关键！之前被旁路了）

### 2. sfp_video_tx.v 清理
- 已移除所有手动 CTC 代码 ✓
- 现在由 HSST IP 硬件自动处理 CTC

### 3. 配置对比：100H vs 50K

| 配置项 | 100H (RX端) | 50K (TX端) | 状态 |
|--------|-------------|-----------|------|
| CH2_RXPCS_CTC | GE | GE | ✓ 匹配 |
| PCS_CH2_BYPASS_CTC | - | 0 (不旁路) | ✓ 正确 |

## 备份文件
- `hsst_test.idf.bak_before_ge_ctc` - 修改前配置
- `sfp_video_tx.v.bak_with_manual_ctc` - 带手动 CTC 的版本
- `sfp_video_tx.v.bak_before_ctc_fix` - 最初版本

## ⚠️ 重要：需要重新生成 IP 核

IDF 配置已改，但 `hsst_test.v` 还未重新生成。

### 选项 1: 使用 PDS GUI 重新生成 IP 核
```bash
C:/pango/PDS_2022.2-SP6.4/bin/ip_compiler.exe
# File → Open IP Instance → hsst_test.idf
# Generate/Build
```

### 选项 2: 直接重新编译（可能自动重新生成）
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test

# 完整流程
pds_shell -project ov5640_sfp480p_test.pds -run compile
pds_shell -project ov5640_sfp480p_test.pds -run synthesize  
pds_shell -project ov5640_sfp480p_test.pds -run pnr
pds_shell -project ov5640_sfp480p_test.pds -run gen_bit_stream
```

## 下一步
1. 重新生成 IP 核（如果需要）
2. 重新编译工程
3. 烧录到 50K 板
4. 验证与 100H 的双向通信

## 预期结果
- 100H LED: `led_sfp_rxsync` 亮
- 100H 寄存器 `+0x144`: bit[2]=1, bit[3]=1
- 能接收到 cam5/cam6 视频流
