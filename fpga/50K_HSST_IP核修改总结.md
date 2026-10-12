# 50K HSST IP 核配置修改总结

## 已完成的修改

### 1. HSST IP 核配置文件 ✅
- **文件**: `source/rtl/hsst_test/hsst_test.idf`
- **修改**: `CH2_RXPCS_CTC: "Bypassed" → "GE"`
- **备份**: `hsst_test.idf.bak_before_ge_ctc`

### 2. sfp_video_tx.v 手动 CTC 代码移除 ✅
- **文件**: `source/rtl/sfp_video_tx.v`
- **移除内容**:
  - CTC 相位计数器 (`ctc_phase`)
  - SKIP 序列定义 (`SKIP_WORD`, `SKIP_K`)
  - Skip 插入逻辑 (`if (ctc_phase == 3'd6)`)
- **备份**: `sfp_video_tx.v.bak_with_manual_ctc`

## ⚠️ 尚未完成：HSST IP 核重新生成

### 问题
IDF 配置文件已修改为 `GE`，但 **Verilog 文件 (`hsst_test.v`) 尚未重新生成**。

当前 `hsst_test.v` 仍然是基于旧的 `Bypassed` 配置生成的。

### 解决方案

#### 方法 1: 使用 GUI（推荐）
```bash
# 1. 打开 IP Compiler
C:/pango/PDS_2022.2-SP6.4/bin/ip_compiler.exe

# 2. 在 GUI 中：
#    File → Open IP Instance
#    浏览选择: source/rtl/hsst_test/hsst_test.idf
#
# 3. 验证配置显示为 CH2_RXPCS_CTC = GE
#
# 4. 点击 "Generate" 或 "Build" 按钮
#
# 5. 等待生成完成（10-30秒）
```

#### 方法 2: 检查是否已自动更新
某些情况下，PDS 在编译时会自动重新生成 IP 核。可以先尝试直接编译：

```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test

# 清理并重新编译
C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe \
  -project "$(pwd)/ov5640_sfp480p_test.pds" \
  -run compile \
  -work_dir "$(pwd)"
```

如果编译时没有报错，说明 IP 核可能已正确处理。

#### 方法 3: 手动触发 IP 核重新生成（实验性）
```bash
cd source/rtl/hsst_test

# 删除生成的 Verilog 文件，强制重新生成
rm -f hsst_test.v

# 使用 PDS 重新编译整个工程
# 编译时会检测到缺失的 IP 核文件并重新生成
```

### 验证 IP 核是否正确生成

生成后检查：
```bash
# 1. 检查文件时间戳（应该是最新的）
ls -lh source/rtl/hsst_test/hsst_test.v
# 预期: 修改时间为今天/刚刚

# 2. 检查文件大小
wc -l source/rtl/hsst_test/hsst_test.v
# 预期: 约 2000-3000 行

# 3. 搜索 CTC 相关配置（如果 IP 核暴露了参数）
grep -i "ctc\|GE" source/rtl/hsst_test/hsst_test.v | head -10
```

## 下一步：重新编译 50K 工程

IP 核重新生成后，需要：

1. **清理旧的编译产物**:
   ```bash
   cd ov5640_sfp480p_test/ov5640_sfp480p_test
   rm -rf compile_* synthesize pnr generate_bitstream/*.sbit
   ```

2. **重新完整编译**:
   ```bash
   # 综合
   pds_shell -project ov5640_sfp480p_test.pds -run synthesize
   
   # 布局布线
   pds_shell -project ov5640_sfp480p_test.pds -run pnr
   
   # 生成比特流
   pds_shell -project ov5640_sfp480p_test.pds -run gen_bit_stream
   ```

3. **预计时间**: ~1.5 小时（完整流程）

## 关键对比：修改前 vs 修改后

### 修改前（手动实现）
- HSST IP: `CH2_RXPCS_CTC = "Bypassed"`
- sfp_video_tx.v: 手动插入 skip（软件实现）
- 风险: 协议可能不完整，时序可能不精确

### 修改后（硬件实现）
- HSST IP: `CH2_RXPCS_CTC = "GE"` ✓
- sfp_video_tx.v: 无手动 CTC 代码 ✓
- 优点: 符合标准，硬件自动处理，与 100H 匹配

## 备份文件列表

如需恢复到任何版本：
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test

# 恢复到 Bypassed + 手动 CTC 版本
cp source/rtl/hsst_test/hsst_test.idf.bak_before_ge_ctc source/rtl/hsst_test/hsst_test.idf
cp source/rtl/sfp_video_tx.v.bak_with_manual_ctc source/rtl/sfp_video_tx.v

# 恢复到最初版本（无 CTC 修改）
cp source/rtl/sfp_video_tx.v.bak_before_ctc_fix source/rtl/sfp_video_tx.v
```

## 测试建议

### 选项 1: 先测试旧的手动实现版本
如果你已经有了昨天编译的比特流（带手动 CTC），可以先烧录测试：
- 如果成功 → 说明手动实现可行
- 如果失败 → 说明需要硬件 CTC

### 选项 2: 直接编译新的硬件 CTC 版本（推荐）
- 更符合标准
- 与 100H 配置匹配
- 理论上成功率更高

## 相关文档
- `HSST_CTC_配置对比分析.md` - 详细技术对比
- `HSST_IP核重新生成步骤.md` - GUI 操作指南
- `SFP_烧录和测试指南.md` - 测试流程

## 当前状态总结

| 项目 | 状态 | 备注 |
|------|------|------|
| IDF 配置修改 | ✅ 完成 | CTC = GE |
| sfp_video_tx.v 清理 | ✅ 完成 | 已移除手动代码 |
| HSST IP 核重新生成 | ⏳ **待完成** | **需要手动操作** |
| 重新编译工程 | ⏳ 待完成 | IP 核生成后进行 |
| 烧录测试 | ⏳ 待完成 | 编译后进行 |
