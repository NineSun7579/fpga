# HSST IP 核重新生成步骤

## 当前状态
- ✅ IDF 配置已修改：`CH2_RXPCS_CTC = "GE"`（从 "Bypassed" 改为 "GE"）
- ⏳ 需要重新生成 IP 核 Verilog 文件
- ⏳ 需要移除 sfp_video_tx.v 中的手动 skip 逻辑

## 方法 1: 使用 GUI 重新生成（推荐）

### 步骤
1. **打开 IP Compiler**
   ```
   开始菜单 → Pango Design Suite → IP Compiler
   或直接运行: C:\pango\PDS_2022.2-SP6.4\bin\ip_compiler.exe
   ```

2. **加载 IDF 文件**
   - 点击菜单: File → Open IP Instance
   - 或使用参数: `-i "C:\Users\NineSun\Desktop\ov56401\ov5640_sfp480p_test\ov5640_sfp480p_test\source\rtl\hsst_test\hsst_test.idf"`
   - 浏览选择: `hsst_test.idf`

3. **验证配置**
   - 打开后，导航到 HSST IP 配置界面
   - 找到 CH2 的 PCS 配置
   - 确认 `RXPCS_CTC = GE`（应该已经是，因为我们修改了 IDF）

4. **重新生成**
   - 点击 "Generate" 或 "Build" 按钮
   - 等待生成完成（通常 10-30 秒）
   - 确认 `hsst_test.v` 文件被更新

5. **验证生成时间**
   ```bash
   ls -lh source/rtl/hsst_test/hsst_test.v
   # 检查文件修改时间是否为刚刚
   ```

## 方法 2: 命令行重新生成（备选）

如果 GUI 不可用，可以尝试：

```bash
cd /c/Users/NineSun/Desktop/ov56401/ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hsst_test

# 方法 A: 使用 ip_compiler 命令行模式
C:/pango/PDS_2022.2-SP6.4/bin/ip_compiler.exe -i hsst_test.idf -c

# 方法 B: 如果有 ipcore_generator 工具
C:/pango/PDS_2022.2-SP6.4/bin/ipcore_generator.exe -build hsst_test.idf
```

## 备份文件
在重新生成前已创建：
- `hsst_test.idf.bak_before_ge_ctc` - 修改前的配置（CTC=Bypassed）
- 如需恢复：
  ```bash
  cp hsst_test.idf.bak_before_ge_ctc hsst_test.idf
  # 然后重新生成
  ```

## 验证 IP 核是否正确生成

生成后检查：
```bash
# 1. 检查文件时间戳
ls -lh source/rtl/hsst_test/hsst_test.v

# 2. 检查是否有错误日志
cat source/rtl/hsst_test/*.log 2>/dev/null

# 3. 验证生成的文件完整性
wc -l source/rtl/hsst_test/hsst_test.v
# 应该有几万行代码
```

## 下一步：移除手动 skip 逻辑

IP 核重新生成后，需要修改 `sfp_video_tx.v`，移除手动插入的 skip 逻辑。

详见：`移除手动CTC逻辑步骤.md`
