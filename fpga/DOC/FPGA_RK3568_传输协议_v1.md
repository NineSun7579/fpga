# FPGA ↔ RK3568 传输协议 v1.0

状态: **v1.1 (2026-09-11)** ｜ 决策权全部在 RK3568 (主机), FPGA 为执行端
v1.1 变更: §3 寄存器表增加"实现状态"列并区分"已实现/待集成"; 新增 §3.0 当前比特流
已实现寄存器总表(含 BAR1 参考 DMA 描述符)与 §3.2 寄存器经 DMA 的访问方法;
主机驱动按"选项 1"(传输层走真实 RTL 协议 + 通道抽象, PREP 后端由 stub 转正式)实现。
配套 RTL: `source/preprocess/prep_regs.v` (寄存器扩展), `source/preprocess/*` (预处理 IP)

## 1. 系统角色

```
┌─────────────────────── FPGA (PG2L100H) ───────────────────────┐
│ OV5640 → 预处理IP(rgb2gray→色化→Sobel) ──→ CH0 处理图 ──┐      │
│            │(旁路时 RAW)                    实时帧 RAW ──┤ PCIe │
│ U盘解码帧 (RK3568 注入) ←─ CH1 注入通道 ───────────────┤ x4   │
│ NPU(YOLO26, 恒喂 RAW) ──→ CH2 结果/CH3 层输出          │      │
└────────────────────────────────────────────────────────┴──────┘
                           │ PCIe x4 Gen2 (~1.6GB/s 理论)
┌────────────────────── RK3568 (决策端) ────────────────────────┐
│ 收图 → 红绿灯识别(处理图) → 与 YOLO26 融合 → 决策状态机       │
│ 写指令/权重/注入帧 → FPGA                                     │
└───────────────────────────────────────────────────────────────┘
```

## 2. DDR 地址映射 (FPGA 视角)

| 地址 | 大小 | 内容 | 写者 | 读者 |
|---|---|---|---|---|
| 0x02000000 | 1MB/层 | NPU 权重(按层排布, 指令预取) | RK3568 | NPU |
| 0x06000000 | ≤2MB | NPU 输入帧 (RAW, 恒定) | CH1 注入 DMA / 采集 | NPU |
| 0x07000000 | 64KB | NPU 推理结果 | NPU | RK3568 |
| 0x0A000000 | 2×帧 | 处理图/实时帧 ping-pong | 采集/预处理 | CH0 DMA |
| 0x40000000 | - | NPU 指令队列基址 | RK3568 | NPU |
| 0x50000000 | - | 层数寄存器 | RK3568 | NPU |

魔数约定: 权重区头 4 字节 = 0xF0F0F0F0 (RK3568 写入; FPGA 侧校验权重版本)。

## 3.0 当前比特流已实现寄存器总表 (主机驱动以此为准)

两类访问通道:
- **BAR1 DMA 描述符寄存器** (直写, 只写): 传输层原语, 所有数据搬运的入口。
- **AXI 地址窗寄存器** (经 DMA 间接访问): 把 0x1E0 设为目标 AXI 地址即可读写。

| 访问方式 | 寄存器 | 偏移/AXI 地址 | 说明 | 状态 |
|---|---|---|---|---|
| BAR1 描述符 | CMD | BAR1+0x100 | [9:0]每次TLP的DW数 [16]=1用64位主机地址 [24]=0读主机/1写主机 | 已实现 |
| BAR1 描述符 | HOST_ADDR_L | BAR1+0x110 | 主机缓冲低 32 位 (写入触发传输) | 已实现 |
| BAR1 描述符 | HOST_ADDR_H | BAR1+0x120 | 主机缓冲高 32 位 ([16]=1 时有效) | 已实现 |
| BAR1 描述符 | FPGA_AXI_ADDR | BAR1+0x1E0 | **FPGA 侧 AXI 总线地址** (非 BAR 偏移) | 已实现 |
| BAR1 描述符 | TOTAL_LEN | BAR1+0x200 | 传输总字节数 (16B 对齐分拍) | 已实现 |
| AXI 窗 | XDMA_ACK | 0x2000_0000+0x00 | 写 bit[1:0]=帧完成应答 (自清) | 已实现 |
| AXI 窗 | CAM_EN | 0x2000_0000+0x40 | 写 bit0 启动相机写 DDR | 已实现 |
| AXI 窗 | CAM_ADDR_1/2 | 0x2000_0000+0x80/0xC0 | 相机帧乒乓缓冲基址 | 已实现 |
| AXI 窗 | PREP_CTRL | 0x2000_0000+0x100 | 见 §3 (读写回读) | **已实现(寄存器级)** |
| AXI 窗 | PREP_THR/SIZE/LANE/INJ_*/BUTTON/LED/LANE_RESULT/TS | +0x104~0x17C | 同上 | **已实现(寄存器级)** |
| AXI 窗 | NPU 寄存器 | 0x4000_0000~ | 指令队列/层数 | 已实现 |

注意:
1. AXI 窗寄存器的值放 16 字节 DMA 传输的 **byte0~3 (小端)**; 读回同理。reg 均为 16 字节对齐。
2. PREP/INJ 寄存器当前为**寄存器级实现**: 读写回读位精确 (sim 11/11 验证), 但阈值/注入
   的**图像功能**要等第二阶段像素通路集成 (preprocess_top tap 进 ddr_fifo16_r 读侧) 才生效
   —— 主机可先验证寄存器契约, 不要期望写 THR 立刻改变图像。
3. BAR0/BAR2 MMIO 直读是内部 RAM 窗口 (非寄存器), 不要用作状态回读。

### 3.0.1 相机 SCCB (I²C) 主机直通寄存器 (CAM3/CAM4, 2026-09-26/27)

相机 SCL/SDA 只接 FPGA, 主机没有直连相机的 I²C 通路。为验证 cam3/cam4 SCCB、并控制
模组补光灯, 在 **CAM3 窗口** (0x2000_0400) 与 **CAM4 窗口** (0x2000_0600) 各增加 3 个
16 字节对齐寄存器。M01 译码器把 addr[11:10]==01 的整页 (0x2000_0400~0x2000_07FF) 拆成两半:
`addr[9]==0` → cam3 寄存器块 (0x400/0x500), `addr[9]==1` → cam4 寄存器块 (0x600/0x700)。
因此 +0x100 对 cam3/cam4 都可达; cam1/cam2 的 +0x100 落在 prep_regs 窗口, 不可达
(不使用, 保持原行为)。

| 地址 | 名称 | 属性 | 位定义 |
|---|---|---|---|
| 0x2000_0500 | CAM3_I2C_CMD  | W | 写低 25 位触发一笔 SCCB: [24]=1读/0写 [23:8]=传感器寄存器地址 [7:0]=写数据 |
| 0x2000_0510 | CAM3_I2C_RD   | R | [7:0]=最近一次读回的数据字节 |
| 0x2000_0520 | CAM3_I2C_STAT | R | [0]=ack (1=NACK) [1]=done (命令完成, 写新命令自清) |
| 0x2000_0700 | CAM4_I2C_CMD  | W | 同 CAM3_I2C_CMD (cam4 窗口) |
| 0x2000_0710 | CAM4_I2C_RD   | R | 同 CAM3_I2C_RD (cam4 窗口) |
| 0x2000_0720 | CAM4_I2C_STAT | R | 同 CAM3_I2C_STAT (cam4 窗口) |

语义:

- 写 CMD 即发起一笔事务; 传感器初始化期间请求会被 FPGA 挂起, 初始化完成后自动补发, 不会丢。
- 主机轮询 STAT[1]==1 后读 RD/STAT; 再写 CMD 清 done 并触发下一笔。
- 读器件 ID: CMD 读 0x300A/0x300B, 期望 0x56/0x40。
- 补光灯 = OV5640 自带闪光/频闪控制: 写 0x3016=0x02、0x301C=0x02、0x3019=0x02(开)/0x00(关)。
- 彩条自检: 写 0x503D=0x80(开) / 0x00(关)。

板端用法: `python3 tools/cam3_i2c_pt.py id | flash on|off | testpat on|off | rd <a> | wr <a> <d>`。

顺带修复相机内建 ID 诊断锁存 (ov5640.v `i2c_was_read`): 原逻辑在第二笔读 (0x300B) 完成时
`i2c_rh_wl` 已翻 0, 导致 ID 低字节永远锁不进来。

## 3.1 推荐点亮流程 (与 DOC/RK3568_新比特流点亮指南.md 同源)

```
0) 枚举: 0755:0755, Gen2 x2, BAR 8K/4K/4K
1) DDR 回环自检: 主机→FPGA 写 16B 到 0x0B000000, 再 FPGA→主机推回比对
2) 写 CAM_ADDR_1/2 (0x2000_0080/0xC0, 值如 0x0A000000/0x0A1C2000, 两笔各16B)
3) 写 CAM_EN=1 (0x2000_0040)
4) 等 MSI(bit0/1=帧完成缓冲号) 或轮询
5) 推帧: 0x1E0=帧地址, 0x200=0x1C2000, 主机缓冲, CMD=[24]=1
6) 写 XDMA_ACK 应答 (0x2000_0000+0x00)
```

## 3.2 寄存器扩展 (BAR 0x2000_0000, 已实现于 prep_regs.v 并已接入 top.v M01 窗口)

| 偏移 | 名称 | 属性 | 位定义 |
|---|---|---|---|
| +0x100 | PREP_CTRL | RW | [0]旁路 [2:1]模式(0色化+白边/1色化/2灰度/3边缘) [3]边缘叠加使能 [4]色化使能 |
| +0x104 | PREP_THR | RW | [7:0]边缘门限 [15:8]色度门限 [23:16]色相分界 [31:24]黄灯亮度下限 |
| +0x108 | PREP_SIZE | RW | [11:0]行宽 [27:16]行高 (640/1280/1920 参数化) |
| +0x10C | PREP_LANE | RW | [7:0]ROI顶% [15:8]ROI底% [23:16]行命中门限 [31:24]虚实翻转门限 |
| +0x110 | INJ_ADDR | W | 注入帧 DDR 首址 (默认 0x06000000) |
| +0x114 | INJ_LEN | W | 注入帧字节数 |
| +0x118 | INJ_FRAME_ID | W | 注入帧序号 (RK3568 递增) |
| +0x11C | INJ_CTRL | W | bit0=启动注入(单拍) bit4=清注入完成(单拍) |
| +0x120 | INJ_STATUS | RO | [0]busy [1]done [31:16]最近完成 FRAME_ID |
| +0x130 | PIPE_STATUS | RO | [0]帧同步 [1]输出FIFO近满 [2]NPU忙 [15:8]输出帧计数 |
| +0x140 | BUTTON_STATUS | RO | 按键粘滞事件 (toggle 置位) |
| +0x144 | BUTTON_EDGE | W1C | 写 1 清粘滞位 |
| +0x150 | LED_CTRL | W | [3:0] LED |
| +0x160 | LANE_RESULT | RO | [1:0]左线型 [3:2]右线型 [4]左有效 [5]右有效 [6]本帧更新 |
| +0x170 | TS0 采集完成 | RO | 打点计数值 (TICK_DIV 分频节拍, 默认≈1µs@50MHz) |
| +0x174 | TS1 预处理完成 | RO | 同上 |
| +0x178 | TS2 NPU 完成 | RO | 同上 |
| +0x17C | TS3 DMA 完成 | RO | 写任意值清零全部打点 |

复位默认值: 非旁路、模式 0、1280×720、THR_EDGE=128 / THR_SAT=96 / THR_HUE=64 / THR_VAL=160。
线型定义: 00=无 01=实线 10=虚线 11=未定 (lane_detect.v, 阈值经 PREP_LANE 板级标定)。

## 4. 通道定义 (PCIe DMA)

| 通道 | 方向 | 内容 | 帧格式 | 带宽预算 |
|---|---|---|---|---|
| CH0 | FPGA→主机 | 处理图(默认)/实时RAW | RGB565 16bpp, 1280×720@30 | ≈53 MB/s |
| CH1 | 主机→FPGA | U盘解码帧注入 | RAW RGB565, 帧≤1.8MB | 突发 |
| CH2 | FPGA→主机 | NPU 检测结果 | 结构体(坐标+类别+置信度) | KB 级 |
| CH3 | FPGA→主机 | 逐层调试输出 (USE_DEBUG) | 层输出 INT8 | 调试 |
| CH4 | 双向 | 寄存器访问 (BAR0) | AXI-Lite | - |

延迟目标: CH0 显示链路 < 1 帧 (33ms); 感知链路(采集→NPU→结果) < 100ms。

## 5. 注入握手 (CH1, 决策全在 RK3568)

```
RK3568                          FPGA
  │ 1. 写 INJ_ADDR/INJ_LEN/FRAME_ID
  │ 2. 写 INJ_CTRL.bit0=1 ──────────→ 启动 DMA 搬运到 INJ_ADDR
  │                                   busy=1
  │ 3. 轮询 INJ_STATUS.done ←──────── done=1, FRAME_ID 回读校验
  │ 4. 写 INJ_CTRL.bit4=1 清完成
  │ 5. 写 NPU 指令/启动 (复用现有 pcie2npu 通路)
```

## 6. RK3568 红绿灯识别流水线 (基于 CH0 处理图)

预处理 IP 已将图像标准化为 {纯红 0xF800 / 黄 0xFFE0 / 绿 0x07E0 / 灰度}，
主机侧识别只需精确色匹配, 无需色彩判断:

1. **精确三色匹配**: 逐像素 ==0xF800 / 0xFFE0 / 0x07E0 (位精确, 无阈值)。
2. **连通域**: 对三张二值掩码做 4-连通域标记 (去噪: 面积 < 20px 剔除)。
3. **轮廓验证**: 面积 ∈ [20, 4000]; 圆形度 4πA/P² > 0.6; 长宽比 ∈ [0.6, 1.6];
   实心度 A/(外接矩形A) > 0.5。
4. **垂直位置裁决**: 同一连通域列带内 上红中黄下绿 → 置信度加权。
5. **3 帧去抖**: 连续 3 帧同色才切换状态 (防单帧噪声)。
6. **与 YOLO26 融合**: NPU 检测框类别(红/绿灯) ⊕ 色化统计结果 一致才输出;
   冲突时以 NPU 框内色化像素多数派为准。
7. **决策状态机**:停车让行/绿灯通行/黄灯减速 → 控制行为 + 上报。

## 7. 一致性注意事项

- 处理图逐像素定义以 `sim/preprocess/golden_gen.py` 为准 (FPGA/主机双侧同源)。
- 灰度 = BT.601 整数近似 Y=(77R+150G+29B)>>8, 5/6→8bit 高位复制。
- 帧同步: 处理图首像素跟随 vsync; 帧尾补 1 个哑像素 (Sobel 上游契约, 见模块头)。
- FRAME_ID 32 位循环; 主机校验 INJ_STATUS[31:16] 防乱序。


## 3.3 板级验证状态 (2026-09-12 凌晨, bitstream_2026-09-11 + 板端实测)

### 通道验证结果 (RK3568 实测)

| 通道/功能 | 状态 | 证据 |
|---|---|---|
| 相机→DDR→PCIe→主机 (CH0 数据面, op_type=1) | **PASS** | viewer 30.1~30.2fps 连续数小时; DDR 读回相机帧数据 (3900/4096 非零) |
| 相机寄存器配置 (CAM_ADDR_1/2, CAM_EN, op0→M01) | **PASS** | 16B DMA 写 byte0~3, 主机任意配置相机缓冲地址生效 (0x0B000000 实测) |
| PREP_CTRL (+0x100) / LED_CTRL (+0x150) 写读回环 | **PASS** | 写读位精确 (0x1E / 0x05) |
| BUTTON_STATUS (+0x140) 读 | PASS | 0 (无按键, 合理) |
| PREP_THR (+0x104) / SIZE / LANE | **BLOCKED** | 见下 "prep_regs 写通道 RTL corner"; 修复前主机无法验证 |
| GPIO / PWM ioctl (RK 本机经驱动) | **PASS** | dmesg 确认 GPIO0 置高 + PWM ch0 使能 |
| host→DDR 大数据面 (op_type=0 → M00, 回环自检 0x0B000000) | **FAIL(未通)** | 全新状态首笔即无完成 MSI; NPU 权重/指令上传通道被阻塞, 需 ILA 定位 pcie_dma 读请求方路径 |
| NPU 结果读取 (GET_NPU, 内核 read_npu, op1←M00) | 未测(依赖推理) | 通路与 CH0 同构, 数据面已证可用 |

### 运维关键发现 (每次上电/烧录必须遵守)

1. **JTAG 易失性烧录 (cfg_program) 后, FPGA PCIe 核复位, 必须做 PERST 复位 + PCIe 重扫, 否则一切总线主控 DMA 静默死锁** (MMIO 正常, 极具迷惑性):
   ```bash
   echo 0 > /sys/class/gpio/gpio144/value; sleep 0.3; echo 1 > /sys/class/gpio/gpio144/value
   echo 1 > /sys/bus/pci/devices/0002:21:00.0/remove; sleep 1; echo 1 > /sys/bus/pci/rescan
   ```
   之后才能 insmod。参考栈 run_car_qt.sh 每次先跑 reset_pcie.sh 即同一原理。
2. **cdt_js 服务器一次会话后即失效**: 每次烧录前 `taskkill /F /IM cdt_js.exe` + 全新端口启动。
3. **任一 DMA ioctl 超时后, 驱动 g_dma_flag 残留 1 (只有 vector0 中断能清), 后续全部 DMA 在 idle 检查 800ms 超时** → 必须 `rmmod; insmod`。
4. **驱动信号量缺陷**: PCI_MAP_ADDR_CMD 重复分配走 `return -EBUSY` 不做 up(&_sem) → 之后所有 ioctl 永久阻塞 (dmesg 刷 "pango_cdev_read interruptible")。缓冲每模块生命周期只能 alloc 一次。
5. 相机 DDR 双缓冲由 CAM_ADDR_1/2 指定 (实测 0x0 / 0x003F4800 均可), 帧尺寸 0x1C2000 (1280x720 RGB565)。

### 已定位未修的 RTL 缺陷

- **prep_regs.v AW/W 两段锁存背靠背失步**: `wr_fire` 清 aw_seen/w_seen 与下一笔 W 的接受脉冲同拍竞争 (非阻塞赋值顺序), 上游 axi_to_axi_lite 连续流 4 个 word 写 (一次 16B DMA) 时丢写/错位, 且之后该模块读通道退化为全 0 (复位默认值也读不到)。ModelSim tb_ovreg_axil_decode 未覆盖背靠背写入。修法: 把 `if (wr_fire) aw_seen/w_seen <= 0` 移到 accept 语句之前 (accept 后写覆盖), 并补背靠背 TB 用例。
- **op_type=0 → M00 (DDR) 不完成**: 与尺寸/地址无关 (16B/4KB/64KB, 0x01000000/0x0B000000 全试), 全新状态首笔即挂。怀疑 pcie_dma 引擎 host-read 请求方/completion 路径缺陷。viewer 只用 op1 不受影响。
- crossbar 译码窗口 (实测): M00=DDR3 0x0~0x1FFFFFFF, M01=寄存器 0x2000_0000~0x3FFFFFFF, M02=NPU 0x4000_0000~0x5FFFFFFF; addr[8]=1 段为 prep_regs (0x2000_0100~)。


### prep_regs 写通道缺陷修复状态 (2026-09-12 07:20)

- **缺陷已复现于仿真**: tb_ovreg_axil_decode.v 新增 `axi_wr_stream4` 背靠背用例 (复现 axi_to_axi_lite 把 16B DMA 拆成 4 个连续 AXI-Lite 写), 原始代码下 THR/LANE 读回错乱, 与板级 K/L 变体现象一致。
- **源码已改 (v2, 未出比特流)**: prep_regs.v AW/W 接受逻辑改 if/else 互斥 (`if (wr_fire) seen<=0; else if(...) accept`), 消除同拍竞争。间隔写场景 tb_prep_regs/tb_ovreg 全 PASS。
- **b2b 用例仍未全绿**: 残余问题在 TB 的 BFM (等待 AW/W ready 同拍, 与 v2 独立握手不匹配), 需要独立通道 BFM 才能真验。板级读通道退化 (K/L/M 全零) 的完整机理待波形确认。
- **决定**: 当前板载比特流不变 (display/DDR读/CAM配置/间隔寄存器写全部已验证), prep_regs v2 + 新 TB 留源码, 白天团队用独立 BFM 闭环后重出比特流。
- 主机侧临时规避: 写 PREP 寄存器每笔间隔 >1 个寄存器写周期 (当前 C 库/驱动路径天然满足), 不要对 0x2000_0100 块做背靠背 16B 连写。




## 3.4 CAM2 双路扩展（2026-09-16，FMC 双目）

第二轮相机（cam2）走与 cam1 完全相同的链路，仅独立时钟域/引脚/DDR 区/寄存器窗。

### DDR 分区（FPGA 视角）

| 区域 | 地址 | 说明 |
|---|---|---|
| cam1 ping | `0x0080_0000` | 640×480 RGB565，帧 0x96000；FRTAG 在 `+0x96000` |
| cam1 pong | `0x00A0_0000` | 同上 |
| cam2 ping | `0x00C0_0000` | 同上 |
| cam2 pong | `0x00E0_0000` | 同上 |
| cam3 ping | `0x0100_0000` | 同上（寄存器窗 0x2000_0400） |
| cam3 pong | `0x0120_0000` | 同上 |
| cam4 ping | `0x0140_0000` | 同上（寄存器窗 0x2000_0600） |
| cam4 pong | `0x0160_0000` | 同上 |

### cam2 寄存器窗（M01，基址 `0x2000_0200`，语义同 cam1）

| 偏移 | 名称 | 属性 | 说明 |
|---|---|---|---|
| `+0x00` | CAM2_ACK | RW(脉冲) | 写 `1<<buf` 释放该缓冲 |
| `+0x40` | CAM2_EN | RW | bit0 使能（复位默认 1） |
| `+0x80` | CAM2_ADDR_1 | RW | ping 基址（默认 0x00C0_0000） |
| `+0xC0` | CAM2_ADDR_2 | RW | pong 基址（默认 0x00E0_0000） |
| `+0x30/34/38/3C/44/48/4C` | CAM2 dbg | RO | 同 cam1 语义（读不可靠，建议只看 DDR tag） |

M01 译码扩展为 5 路：页 0 (`addr[11:10]==00`) 内 `addr[9:8]` = `00` cam1 寄存器 /
`01` prep_regs / `10` cam2 寄存器 / `11` 回落 prep（保持旧 `addr[8]=1` 行为）；
页 1 (`addr[11:10]==01`, 0x400~0x7FF) 内按 `addr[9]` 拆分：`0` → cam3 寄存器块 /
`1` → cam4 寄存器块。相机 CDC 诊断读 (+0x190/1A0/1B0/1C0) 按 `addr[11:9]` 直接路由到
cam1/cam2/cam3/cam4 对应寄存器块。

### AXI

- cam2 写引擎接 crossbar **S04**（`axi_dma_write`, `cmd_id=4'b0100`），`M00_CONNECT_WRITE=7'b0011111`。
- cam3 写引擎 `cmd_id=4'b0010`、cam4 写引擎 `cmd_id=4'b1000`；四路相机的 DDR 写路径统一经
  `axi_crossbar/ddr_w_arb.v`（4-master 轮询仲裁，单笔 outstanding，AW 赢家锁存）。
- 相机 `xdma_irq` 不接，MSI 维持关闭；帧同步一律用 DDR FRTAG 序号。

### 主机侧

- 传输层不变：`CAM2_ADDR_1/2` 直接落在 DDR，主机用 F2H 按地址读；`CAM2_ACK` 用 H2F 写。
- 参考实现：`host/camview/main.cpp`（四路左右并排合成 2560×480，每路 640×480，并各自显示 fps）。
---

## 3.9 CAM5/CAM6 光纤通道(2026-09-29,SFP 双路扩展)

第五/六路视频不是本地 DVP 相机,而是 **PGL50H(50K)开发板经 SFP 光纤送来的双摄合成流**:
50K 侧 cam2_merge 把两颗 OV5640 逐行拼接为 1280x480(左 640=对端 CMOS1,右 640=对端 CMOS2),
sfp_video_tx 经 HSST CH2/SFP0 以 5G/8B10B 发出;100H 侧 QR3(HSSTLP_364_918)CH2 接收,
sfp_video_rx 解包 + 按列拆分为 cam5(前 640 列)/cam6(后 640 列),各经 ov5640_ddr 写引擎
入 DDR(与 cam1~4 同构,FRTAG 机制相同)。无寄存器窗(常使能、固定地址),主机只轮询帧 tag。

### DDR 分区(FPGA 视角,续 3.4 节)

| 区域 | 地址 | 说明 |
|---|---|---|
| cam5 ping | `0x0180_0000` | 640x480 RGB565,帧 0x96000;FRTAG 在 `+0x96000`(光纤左半幅) |
| cam5 pong | `0x01A0_0000` | 同上 |
| cam6 ping | `0x01C0_0000` | 同上(光纤右半幅) |
| cam6 pong | `0x01E0_0000` | 同上 |

### 主机侧接入(camview)

`host/camview/main.cpp` 已扩展为 6 worker、3x2 六宫格(1920x960)。CAM5/CAM6 地址宏同上。
注意:光纤通道帧率跟随对端 30Hz 读出;链路断开时 tag 停更,画面停在最后一帧(WAIT 状态)。

### ddr_w_arb

写仲裁器由 4 主扩为 6 主(cam5=master4, cam6=master5,cmd_id 0011/1100),轮询逻辑不变。
