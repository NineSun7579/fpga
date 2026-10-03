# LED6修复验证指南 (2026-09-30)

## 修复内容

**问题**: 50K板LED6(A5)长灭，100H SFP TX有光但50K RX PCS LSM不同步

**根因**: 100H发送idle有序集 `32'hBC0028BC / txk=1001`，K28.5出现在byte0(偶)和byte3(奇)，
违反GE_MODE LSM要求(comma必须对齐偶数字节)

**修复**: `source/sfp/sfp_rx_link.v` line 80-83
```verilog
// 改前: wire [31:0] txd_2 = 32'hBC0028BC; wire [3:0] txk_2 = 4'b1001;
// 改后: 标准GE /I2/ 有序集
wire [31:0] txd_2 = 32'h50BC50BC;  // K28.5 + D16.2 重复
wire [3:0]  txk_2 = 4'b0101;       // K标记在byte0/2(偶数位置)
```

## 比特流信息

- 工程: `project_build/project.pds`
- 产物: `project_build/bit_stream/top.sbit`
- 编译时间: 2026-09-30 19:22 (pnr完成)
- 备份: `.bak_led6fix`

## 烧录步骤

1. **确认JTAG连接100H板** (USB Blaster → 100H JTAG口)

2. **执行烧录** (PDS Programmer或命令行):
   ```bash
   cd C:\Users\NineSun\Desktop\ov56401\project
   C:\pango\PDS_2022.2-SP6.4\bin\pds_programmer.exe flash_100h_led6fix.tcl
   ```
   或GUI: File → Run Tcl Script → `flash_100h_led6fix.tcl`

3. **上电复位**: 烧录完成后拔插100H板电源

## 验证清单

### 100H板LED检查
- [ ] LED4(A3) 亮 = PLL1锁定, SFP TX有光
- [ ] 心跳LED正常闪烁

### 50K板LED检查 (光纤对接后)
- [ ] **LED6(A5) 亮** ← 关键指标，证明RX PCS LSM同步成功
- [ ] LED4 亮 = 本地TX有光
- [ ] 心跳LED正常

### 视频验证
- [ ] RK3568 camview六宫格运行中 (pid 3521或重启)
- [ ] C5通道显示 = 对端CMOS1左半幅 (640x480)
- [ ] C6通道显示 = 对端CMOS2右半幅 (640x480)
- [ ] 帧率 ~30fps (RK端显示) / ~59.6fps (FPGA源)
- [ ] 断纤重接: LED6灭→亮, C5/C6数秒内恢复

### 应急回退
若LED6仍不亮或视频异常:
1. 确认50K板烧录的是 `ov5640_sfp480p_test/hdmi_ddr_ov5640_top_slim_rev32.sbit` (Rev3.2精简版)
2. 检查光纤物理连接: 50K SFP0 ↔ 100H SFP笼子
3. 若需回退100H: 烧录 `bitstream_sfp6_20260929/top.sbit` (旧版idle)

## 后续工作

若100H→50K反向链路也需修复(当前50K发送同样的非标idle):
- 修改50K工程 `sfp_video_tx.v` 控制字，K28.5对齐偶数字节
- 或100H设置 `force_rxfsm_lsm_2=1` (需重新生成hsst_sfp IP，约30分钟)

优先验证方案1(GE协议对齐)。
