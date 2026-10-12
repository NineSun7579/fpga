# SFP 光口通信修复总结 (50K ↔ 100H)

## 修复日期
2026-10-01

## 问题描述
- **现象**: 50K 板回环测试正常，但与 100H 板之间无法通信
- **根本原因**: 
  1. 50K TX 未按 GE CTC 标准发送 skip 有序集
  2. 100H RX 配置为 `RXPCS_CTC="GE"` 模式，要求每 8 拍接收一次 skip
  3. 参考时钟频率不匹配（50K: 125MHz, 100H: 100MHz）

## 修复方案

### 方案概述
由于 100H 的参考时钟（F6/E6）与 PCIe 共用 100MHz 差分对，物理上无法改为 125MHz，因此采用：
- **修复 50K TX 侧**：添加 GE CTC skip 序列支持
- **保持 100H RX 配置不变**：继续使用 GE CTC 模式

### 修改的文件
```
ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl/sfp_video_tx.v
```

### 备份文件
```
sfp_video_tx.v.bak_before_ctc_fix           # 手动备份
sfp_video_tx.v.bak_before_ctc_20261001_095004  # 自动备份
```

## 详细修改内容

### 1. 增加 8 拍相位计数器 (第 86-94 行)
```verilog
//--------------------------------------------------------------------------
// [CTC FIX] GE mode 8-beat phase counter (insert skip at beat 6)
//--------------------------------------------------------------------------
reg [2:0] ctc_phase;
always @(posedge fab_clk or negedge fab_rst_n) begin
    if (!fab_rst_n)
        ctc_phase <= `UD 3'd0;
    else if (!tx_go)
        ctc_phase <= `UD 3'd0;
    else
        ctc_phase <= `UD ctc_phase + 3'd1;  // 0..7 cycle
end
```

**说明**: 
- `ctc_phase` 在 fabric 时钟域 (125MHz) 循环计数 0→7
- 链路未就绪时复位为 0

### 2. 定义 Skip 有序集常量 (第 97-98 行)
```verilog
// Skip ordered set: {D28.2, K28.5, D28.2, K28.5} (GE CTC standard)
localparam [31:0] SKIP_WORD = 32'h28BC_28BC;
localparam [3:0]  SKIP_K    = 4'b0101;
```

**说明**:
- `SKIP_WORD`: 符合 GE 标准的 skip 有序集
  - byte0 = K28.5 (0xBC)
  - byte1 = D28.2 (0x28)
  - byte2 = K28.5 (0xBC)
  - byte3 = D28.2 (0x28)
- `SKIP_K = 4'b0101`: 表示 byte0 和 byte2 是 K 码

### 3. 修改 last_vs/last_hs 更新逻辑 (第 124 行)
```verilog
// 原代码:
else if (fifo_pop) begin

// 修改后:
else if (fifo_pop_gated) begin
```

**说明**: skip 拍时不更新 `last_vs/last_hs`，避免状态不一致

### 4. 添加 FIFO 弹出门控信号 (第 132 行)
```verilog
// [CTC FIX] FIFO pop control: pause at skip beat
wire fifo_pop_gated = fifo_pop && (ctc_phase != 3'd6);
```

**说明**: 
- 在相位 6 (skip 拍) 时暂停 FIFO 弹出
- 避免 skip 拍插入导致像素丢失

### 5. 主状态机：插入 skip 拍处理 (第 145-150 行)
```verilog
else begin
    // [CTC FIX] Phase 6: force skip ordered set, pause normal packing
    if (ctc_phase == 3'd6) begin
        txd <= `UD SKIP_WORD;
        txk <= `UD SKIP_K;
        // pix_pend and pix0 remain unchanged, continue next beat
    end
    else if (!tx_go) begin
        ...
```

**说明**:
- 相位 6 强制发送 skip 有序集
- `pix_pend` 和 `pix0` 保持不变，下一拍继续处理
- 优先级: skip 拍 > 链路未就绪 > 正常打包

### 6. 正常打包逻辑使用门控信号 (第 156 行)
```verilog
// 原代码:
else if (fifo_pop) begin

// 修改后:
else if (fifo_pop_gated) begin
```

**说明**: 确保 skip 拍期间不执行正常打包

## GE CTC 时序示例

```
拍序号:    0    1    2    3    4    5    6    7    0    1    ...
相位:      0    1    2    3    4    5    6    7    0    1    ...
发送内容:  data idle idle data idle idle SKIP data idle idle ...
txk:       0000 1001 1001 0000 1001 1001 0101 0000 1001 1001 ...
```

- **拍 0-5, 7**: 正常打包（数据字或控制字）
- **拍 6**: 强制发送 skip 有序集 (32'h28BC_28BC, txk=0101)
- **周期**: 每 8 拍重复一次

## 协议兼容性

### TX 端 (50K)
- 每 8 拍在相位 6 插入 skip 有序集
- 符合 GE (千兆以太网) CTC 标准
- 与 100H RX 配置匹配

### RX 端 (100H)
- `RXPCS_CTC = "GE"` 模式
- `RXPCS_ALIGN = "GE_MODE"`
- `RXPCS_COMMA_SEL = "K28.5"`
- 自动识别并处理 skip 有序集，补偿时钟容差

## 验证步骤

### 1. 编译 50K 工程
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test
# 使用 PDS 2022.2-SP6.4 编译
```

### 2. 检查编译结果
- 综合报告：确认新增寄存器 `ctc_phase[2:0]`
- 时序报告：确认 125MHz fabric 时钟域无违例

### 3. 上板测试
**50K 侧**:
- 烧录新比特流
- 观察 LED:
  - `led_sfp_pll` (F8): HSST PLL 锁定
  - `led_sfp_ready` (F7): PLL 锁定且 TX lane done
  - `led_sfp_rxsync` (A5): 收到 100H 回传光且 RX PCS 同步

**100H 侧**:
- 无需重新编译
- 读取寄存器 `+0x144` (SFP 状态):
  ```
  bit[0]: pll_lock       - 应为 1
  bit[1]: txlane_done    - 应为 1
  bit[2]: rxlane_done    - 应为 1 (关键)
  bit[3]: pcs_synced     - 应为 1 (关键)
  ```

### 4. 功能验证
- 100H 应能接收到 50K 发送的双摄视频流 (1280x480)
- cam5 (前 640 列) = 50K 的 cam1
- cam6 (后 640 列) = 50K 的 cam2
- 检查帧率、图像完整性、色彩准确性

## 预期结果

### 修复前
- 100H RX 状态: `rxlane_done=0` 或 `pcs_synced=0`
- 原因: CDR 未对齐或 PCS 未同步（缺少 skip）

### 修复后
- 100H RX 状态: `rxlane_done=1` 且 `pcs_synced=1`
- 双向通信建立，视频流正常接收

## 性能影响分析

### 带宽利用率
- **原设计**: 100% 数据/控制字
- **修复后**: 每 8 拍插入 1 个 skip = 87.5% 有效负载
- **实际影响**: 
  - 640x480@60fps RGB565 = 18.43 Mbps (像素流)
  - 链路速率 5 Gbps × 87.5% = 4.375 Gbps 有效带宽
  - 带宽占用率: 18.43 / 4375 = 0.42%
  - **结论**: 带宽充足，skip 开销可忽略

### 延迟影响
- Skip 拍 FIFO 暂停 1 拍 = 8ns (@125MHz)
- 每 8 拍累积 1 拍 = 平均延迟增加 12.5%
- 绝对延迟增加: 8ns × 帧像素数 / 8 ≈ 307µs/帧
- **结论**: 延迟增加 < 1ms，对实时性无影响

### 资源占用增加
- 新增寄存器: `ctc_phase[2:0]` = 3 个 FF
- 新增组合逻辑: 
  - 3-bit 加法器 (ctc_phase + 1)
  - 比较器 (ctc_phase == 6)
  - 门控逻辑 (fifo_pop_gated)
- **结论**: 资源增加 < 10 LUT/FF，可忽略

## 回滚方案

如果修复后仍有问题，回滚步骤：
```bash
cd ov5640_sfp480p_test/ov5640_sfp480p_test/source/rtl
cp sfp_video_tx.v.bak_before_ctc_fix sfp_video_tx.v
```

## 进一步优化建议

### 可选优化 1: 可配置 CTC 模式
增加参数控制是否启用 CTC：
```verilog
parameter CTC_EN = 1;  // 1=GE CTC mode, 0=bypass (原协议)
```

### 可选优化 2: 动态相位对齐
如果 100H RX 仍有问题，可能需要调整 skip 拍的相位偏移。

### 可选优化 3: 100H RX 禁用 CTC (备选)
如果无法修改 50K TX，100H 可以：
- 重新生成 `hsst_sfp` IP: `CH2_RXPCS_CTC = "Bypassed"`
- **风险**: 失去时钟容差补偿，长时间运行可能累积误差

## 相关文档

- `SFP_100H_50K_对比分析.md` - 问题诊断报告
- `UG041004_HSSTLP_IP.pdf` - 紫光 HSSTLP IP 手册
- `project/DOC/FPGA_RK3568_传输协议_v1.md` - 100H 协议文档
- `ov5640_sfp480p_test/.../sfp_video_tx.v` - 本次修改的文件

## 修改记录

| 日期 | 修改人 | 说明 |
|------|--------|------|
| 2026-10-01 | Claude Code | 初始修复：添加 GE CTC skip 序列支持 |

## 技术支持

如遇问题，检查：
1. 50K 编译是否成功（无错误/警告）
2. 100H 寄存器 +0x144 的 bit[2:3] 状态
3. 使用逻辑分析仪抓取 50K TX 输出，确认 skip 序列
4. 参考 `SFP_100H_50K_对比分析.md` 中的诊断步骤
