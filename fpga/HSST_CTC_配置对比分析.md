# HSST IP 核 CTC 配置对比分析

## 问题发现

### 配置不匹配
- **100H (接收端)**: `CH2_RXPCS_CTC = "GE"` ✓ 正确
- **50K (发送端)**: `CH2_RXPCS_CTC = "Bypassed"` ❌ **错误配置**

## 问题分析

### 当前情况
1. **100H 的 RX 期望**: GE CTC 模式（需要每 8 拍插入 skip）
2. **50K 的配置**: 
   - HSST IP 设置为 `Bypassed`（不插入 skip）
   - 我们在 `sfp_video_tx.v` **手动**插入了 skip

### 为什么手动插入可能不够

虽然我们在 `sfp_video_tx.v` 中添加了 skip 逻辑，但：

1. **IP 核内部处理**: HSST IP 的 `CH2_RXPCS_CTC = "Bypassed"` 意味着：
   - TX PCS 不做 CTC 处理
   - 可能缺少 GE CTC 协议的其他配置
   - 8B/10B 编码可能不符合 GE 标准

2. **协议完整性**: GE CTC 不仅仅是插入 skip，还包括：
   - Skip 序列的精确定时
   - PCS 状态机配置
   - Comma 对齐配置
   - 时钟补偿 FIFO 控制

3. **100H RX 的期望**: 
   ```
   // 100H hsst_sfp IP 配置
   CH2_RXPCS_CTC = "GE"
   CH2_RXPCS_ALIGN = "GE_MODE"  (推测)
   CH2_RXPCS_COMMA_SEL = "K28.5"
   ```

## 正确的修复方案

### 方案 A: 修改 50K HSST IP 配置（推荐）

将 50K 的 HSST IP 核配置从 `Bypassed` 改为 `GE`，让硬件自动处理 CTC。

#### 优点
- 符合标准 GE 协议
- 硬件处理，时序精确
- 与 100H 配置匹配
- 不需要手动插入 skip

#### 缺点
- 需要重新配置 IP 核
- 需要重新编译（但只是参数变化，不影响其他逻辑）

#### 操作步骤
1. 打开 Pango IP 核配置工具
2. 修改 `hsst_test` IP 核
3. 设置 `CH2_TXPCS_CTC = "GE"` 或 `CH2_RXPCS_CTC = "GE"`
4. 重新生成 IP 核
5. **移除** `sfp_video_tx.v` 中手动插入的 skip 逻辑
6. 重新编译

### 方案 B: 保持当前手动实现（需验证）

如果手动实现的 skip 逻辑完全符合 GE CTC 标准，理论上也能工作。

#### 需要验证的点
1. Skip 序列格式: `0x28BC28BC` / k=`0101` ✓ 已验证
2. Skip 周期: 每 8 拍 ✓ 已实现
3. Skip 拍位置: 第 6 拍 ⚠️ 可能需要调整为第 0 或 7 拍
4. 8B/10B 编码: 需要确认是否符合 GE 标准
5. PCS 时钟域: 需要确认是否正确

#### 风险
- 手动实现可能遗漏协议细节
- 时序可能不够精确
- 可能与 100H RX 的硬件状态机不匹配

### 方案 C: 修改 100H 配置为 Bypassed（不推荐）

将 100H 的 `CH2_RXPCS_CTC` 也改为 `Bypassed`。

#### 缺点
- 100H 需要重新编译
- 失去 CTC 的时钟补偿功能
- 可能导致其他通信问题

## 当前代码状态回顾

### 50K `sfp_video_tx.v` 的手动实现
```verilog
// CTC 相位计数器 (8拍循环)
reg [2:0] ctc_phase;
always @(posedge clk) begin
    if (!rstn) 
        ctc_phase <= 3'd0;
    else
        ctc_phase <= (ctc_phase == 3'd7) ? 3'd0 : ctc_phase + 1'b1;
end

// Skip 序列定义
localparam [31:0] SKIP_WORD = 32'h28BC_28BC;  // D28.2 K28.5 D28.2 K28.5
localparam [3:0]  SKIP_K    = 4'b0101;         // byte1,3 是K码

// 第 6 拍插入 skip
wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);

always @(posedge clk) begin
    if (ctc_phase == 3'd6) begin
        txd <= `UD SKIP_WORD;
        txk <= `UD SKIP_K;
        // pix_pend 和 pix0 保持不变
    end else begin
        // 正常数据传输
        if (fifo_pop_gated && !fifo_empty) begin
            // ...
        end
    end
end
```

### 问题
1. **HSST IP 配置不匹配**: `Bypassed` vs `GE`
2. **可能缺少的配置**:
   - TX PCS 状态机可能不在 GE 模式
   - 8B/10B 编码可能不符合 GE 标准
   - Skip 的插入时机可能需要硬件协同

## 测试计划

### 阶段 1: 验证当前手动实现（已有比特流）
1. 烧录当前比特流到 50K
2. 检查 100H 的 `rxlane_done` 和 `pcs_synced`
3. 使用逻辑分析仪抓取 50K TX 输出，验证：
   - Skip 序列格式是否正确
   - Skip 周期是否为每 8 拍
   - Skip 位置是否稳定

**如果成功** → 说明手动实现可行，无需改 IP 配置
**如果失败** → 继续阶段 2

### 阶段 2: 修改 50K HSST IP 配置为 GE
1. 打开 IP 核配置工具
2. 修改 `hsst_test.idf`:
   ```xml
   <name>CH2_RXPCS_CTC</name>
   <value>GE</value>  <!-- 从 Bypassed 改为 GE -->
   ```
3. 重新生成 IP 核
4. **移除或注释掉** `sfp_video_tx.v` 中的手动 skip 逻辑
5. 重新编译
6. 烧录测试

### 阶段 3: 如果阶段 2 仍失败
1. 检查其他 HSST 配置参数：
   - `CH2_TXPCS_ALIGN`
   - `CH2_TXPCS_COMMA_SEL`
   - `CH2_TXPCS_RATE`
2. 对比 100H 和 50K 的完整 HSST 配置
3. 逐项对齐所有 PCS 相关参数

## 建议

### 优先级 1: 先测试当前比特流
- 已经编译好，立即可测
- 验证手动实现是否可行
- 如果可行，省去重新配置 IP 的工作

### 优先级 2: 如果失败，修改 HSST IP 配置
- 配置改为 `GE` 模式
- 移除手动 skip 逻辑
- 让硬件自动处理 CTC

### 优先级 3: 深入调试
- 使用逻辑分析仪
- 对比标准 GE 波形
- 调整 skip 相位和时机

## HSST IP 核配置文件位置

### 100H
- 配置文件: `project/ipcore/hsst_sfp/hsst_sfp.idf`
- Verilog: `project/ipcore/hsst_sfp/hsst_sfp.v`
- 使用位置: `project/source/sfp/sfp_rx_link.v` (line 108)

### 50K  
- 配置文件: `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hsst_test/hsst_test.idf`
- Verilog: `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hsst_test/hsst_test.v`
- 使用位置: `ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/hdmi_ddr_ov5640_top.v`

## 下一步行动

1. ✅ **立即**: 烧录当前比特流，测试手动实现
2. ⏳ **如果失败**: 备份当前配置，修改 HSST IP 为 GE 模式
3. ⏳ **如果仍失败**: 深入对比两边的完整 HSST 配置

## 相关文档
- `SFP_烧录和测试指南.md` - 测试步骤
- `SFP_修复总结.md` - 代码修改详情
