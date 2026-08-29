# OV7725 HDMI CDC/RDC 审计与整改契约

更新日期：2026-08-29

状态：O0-A 设计审计基线。本文只记录现状、风险和后续契约，不修改 RTL、厂商 IP 或 FDC，也不表示任何时序例外已获批准。

## 1. 范围与结论

审计范围覆盖手写顶层和数据通路、PLL/DDR/FIFO 的接口、现有 FDC 与旧 STA 报告。

当前设计包含以下独立或派生时钟域：

- 外部 `sys_clk`、`cam_pclk`；
- PLL 输出 `pixel_clk`、`pixel_clk_5x`、`clk_50m`；
- DDR IP 输出 `ui_clk` 及厂商 DDR PHY 内部时钟；
- 由逻辑分频产生并作为时钟使用的 `i2c_dri_clk`。

已确认的主要问题：

1. `video_vs`、`cmos_frame_vsync` 进入 `ui_clk` 域时没有统一的事件传输契约，并在多个位置分别采样。
2. `ddr3_init_done` 从 `ui_clk` 域直接参与 camera、pixel 和 AXI 逻辑的异步复位组合。
3. 两个异步 FIFO 的帧复位脉冲由单一时钟域产生，却同时驱动 FIFO 两侧的异步复位输入。
4. 顶层组合复位 `sys_rst_n & clk_locked` 被直接分发到多个时钟域，除部分 DVI 编码逻辑外没有逐域同步释放。
5. 旧 STA 已报告与上述结构直接相关的 setup 和 recovery 失败；不能用宽泛 `false_path` 掩盖。

## 2. 时钟域清单

| 时钟域 | 名义频率 | 来源与用途 | 当前约束状态 | 证据 |
|---|---:|---|---|---|
| `sys_clk` | 50 MHz | 外部输入；PLL 和 I2C 分频逻辑参考时钟 | 已创建 20 ns 时钟 | `rtl/ov7725_hdmi.v:25,103-109`；`prj/source/ov7725_hdmi.fdc:2` |
| `i2c_dri_clk` | 约 1 MHz | `sys_clk` 经寄存器翻转分频；I2C 配置状态机时钟 | FDC 未见显式生成时钟 | `rtl/ov7725_dri/i2c_dri.v:84-101` |
| `cam_pclk` | 当前约束 25 MHz | OV7725 源同步像素域；采集和 write FIFO 写侧 | 已创建 40 ns 时钟；外部 input delay 缺失 | `rtl/ov7725_hdmi.v:33,118,135`；`prj/source/ov7725_hdmi.fdc:3,48-53` |
| `pixel_clk` | 65.0026 MHz | HDMI 像素、read FIFO 读侧和 TMDS 编码域 | PDS 自动推断；FDC 中显式声明被注释 | `rtl/ov7725_hdmi.v:67,106,136,174`；`prj/source/ov7725_hdmi.fdc:6`；`prj/report_timing/ov7725_hdmi.rtr:23-24,56-57` |
| `pixel_clk_5x` | 325.0975 MHz | OSERDES 高速串行域 | PDS 自动推断；FDC 中显式声明被注释 | `rtl/ov7725_hdmi.v:68,107,175`；`prj/source/ov7725_hdmi.fdc:7`；`prj/report_timing/ov7725_hdmi.rtr:23,54-55` |
| `clk_50m` / `ref_clk` | 50 MHz | PLL 输出；DDR IP 参考时钟 | `ref_clk` 已创建 20 ns 时钟 | `rtl/ov7725_hdmi.v:69,108,134`；`prj/source/ov7725_hdmi.fdc:4` |
| `ui_clk` / `ddrphy_sysclk` | 100 MHz | DDR 用户接口、AXI 控制、FIFO DDR 侧 | 作为 DDR 生成时钟存在 | `rtl/ddr3_ctrl_top/ddr3_ctrl_top.v:59,106,128,156,317`；`prj/report_timing/ov7725_hdmi.rtr:28,53` |
| DDR PHY 内部时钟 | 800 MHz PHY、100 MHz 分频域等 | 厂商 DDR PHY | 已有厂商生成时钟和 multicycle/uncertainty | `prj/source/ov7725_hdmi.fdc:22-33` |

说明：PLL 生成文件仍记录 50 MHz 输入以及 65/325/50 MHz 输出配置，但 PLL IDF 中存在旧器件信息。器件一致性属于 O0-B 构建输入审计，不在本批改写厂商 IP。

## 3. CDC 清单

| 信号或数据通路 | 源域 → 目标域 | 类型 | 频率/保持事实 | 当前结构与风险 | 后续契约 |
|---|---|---|---|---|---|
| `cam_data[7:0]`、`cam_href`、`cam_vsync` | 外部摄像头 → `cam_pclk` | 源同步外部总线 | 实际 PCLK、帧率和相位待板级资料确认 | 在 `cam_pclk` 域打拍并拼为 RGB565；缺少板级 input delay | 获得传感器和 PCB 时序后补 input delay；在此之前不得伪造数值 |
| `wd_data[15:0]`、`wd_en` | `cam_pclk` → `ui_clk` | 数据流 | 有效像素期间连续传输 | Pango `wr_fifo` 异步 FIFO，16-bit 写、256-bit 读；复位跨域方式不安全 | 保留厂商异步 FIFO；分别同步写侧和读侧复位，并核验指针同步方法 |
| `cmos_frame_vsync` / `wr_load` | `cam_pclk` → `ui_clk` | 帧事件/电平边沿 | 每帧一次；脉宽和最大帧率待摄像头契约确认 | UI 域两拍采样并上升沿检测，camera 域另行处理；同一事件多点采样 | 源域采用 toggle 或握手；UI 域只同步一次、形成单周期事件后统一扇出 |
| `rfifo_wdata[255:0]`、`rfifo_wen` | `ui_clk` → `pixel_clk` | 数据流 | HDMI 有效区持续传输 | Pango `rd_fifo` 异步 FIFO，256-bit 写、16-bit 读；旧 STA 将指针路径当作普通同步路径并失败 | 不修改厂商 FIFO RTL；确认 PDS SP6.4 认证结构后，只豁免精确的内部同步路径 |
| `video_vs` / `rd_load` | `pixel_clk` → `ui_clk` | 帧事件/电平边沿 | 名义约 60 Hz；低电平保持 6 行，不是单周期脉冲 | 两个 UI 逻辑分别采样；已确认裸业务 CDC setup 失败 | `pixel_clk` 域采用 toggle 或握手；UI 域一次同步后形成单周期事件并扇出 |
| `rd_data[15:0]`、`rdata_req` | `ui_clk` ↔ `pixel_clk` | 数据流与读使能 | HDMI 有效区逐像素请求 | 数据经 `rd_fifo`；`rdata_req` 只驱动 FIFO 的 `pixel_clk` 读侧 | 验证空读、欠载和帧切换边界，不对数据总线逐位同步 |
| `ddr3_init_done` / `capture_start` | `ui_clk` → `cam_pclk` | 稳定状态电平 | 初始化后粘滞为高，理论上只上升一次 | 直接与 `rst_n` 组合后接采集模块异步复位 | 二级同步到 `cam_pclk` 后作为采集使能，不直接组合到异步复位脚 |
| `ddr3_init_done` | `ui_clk` → `pixel_clk` | 稳定状态电平 | 初始化后粘滞为高，理论上只上升一次 | 直接与 `rst_n` 组合为 HDMI 子系统复位；已确认 recovery 失败 | 二级同步到 `pixel_clk`；像素域复位独立同步释放，初始化完成只作业务使能 |
| `i2c_dri_clk` | `sys_clk` 派生时钟 | 逻辑生成时钟 | 约 1 MHz，I2C FSM 持续使用 | 由 fabric 寄存器翻转并作为时钟，增加时钟树、STA 和 CDC复杂度 | O1/O2 评审改为 `sys_clk + clock-enable`；若保留，必须建立精确 generated-clock 关系 |
| TMDS 编码数据 | `pixel_clk` → `pixel_clk_5x` | 相关时钟多速率数据 | 固定 1:5 关系 | 进入厂商 `GTP_OSERDES_E2`；reset 端口未生效 | 保持相关时钟关系并核验原语模板；不得把两域声明为异步 |

### 旧 STA 直接证据

- `video_vs → rd_load_d[0]`：`pixel_clk → ui_clk`，慢角 setup WNS `-7.056 ns`、TNS `-133.808 ns`，20/20 endpoints 失败。见 `prj/report_timing/ov7725_hdmi.rtr:62-86,2386-2459`。
- read FIFO 内部写指针同步：`ui_clk → pixel_clk`，慢角 setup WNS `-2.279 ns`、TNS `-23.941 ns`，11/11 endpoints 失败。见 `prj/report_timing/ov7725_hdmi.rtr:82-86,5608-5675`。

正 slack 也不能单独证明 CDC 合法。例如 `cam_pclk → ui_clk` 当前摘要为正，但仍需要协议、同步结构和约束对象三者同时成立。

## 4. RDC 清单

| 复位路径 | 涉及域 | 当前结构 | 风险判定 | 后续契约 |
|---|---|---|---|---|
| 顶层 `rst_n = sys_rst_n & clk_locked` | 全部域 | 组合后直接扇出 | PLL lock 和外部复位的释放未逐域同步；`rst_n` 还是隐式 net | 分别生成 sys、camera、pixel、UI 和 I2C 域的异步置位/同步释放复位 |
| `rst_n & ddr3_init_done` → `cmos_capture_data.rst_n` | `ui_clk` → `cam_pclk` | 跨域状态组合到异步复位 | 非受控释放，可能产生 recovery/removal 问题 | camera 复位只由 camera 域复位控制；同步后的 init 状态作为 capture enable |
| `rst_n & ddr3_init_done` → `hdmi_top.sys_rst_n` | `ui_clk` → `pixel_clk` | video driver/display 直接使用；DVI encoder 内部另有两级释放同步 | 同一子系统存在两种复位释放结构；旧 STA 已失败 | 整个 pixel 域统一使用 pixel reset；DVI同步器不得成为局部补丁 |
| `rst_n && ddr3_init_done` → `aq_axi_master.rst_n` | `ui_clk` | 同域状态组合到异步复位 | `ddr3_init_done` 在时钟边沿后改变，仍可能违反异步复位恢复时间 | AXI 控制器使用独立 UI 域复位；初始化完成作为同步 enable/状态条件 |
| `wfifo_rst_h` → write FIFO 两侧 | `cam_pclk`、`ui_clk` | 脉冲在 `cam_pclk` 产生，同时驱动两个异步 reset 端口 | UI 侧释放未同步 | 将帧清空请求转换为协议；分别在 `cam_pclk` 和 `ui_clk` 域生成满足 IP 要求的复位或 flush |
| `rdfifo_rst_h` → read FIFO 两侧 | `ui_clk`、`pixel_clk` | 脉冲在 `ui_clk` 产生，同时驱动两个异步 reset 端口 | pixel 侧释放未同步；旧 STA recovery 路径失败 | 分别在 `ui_clk` 和 `pixel_clk` 域生成满足 IP 要求的复位或 flush |
| `serializer_10_to_1.reset_n` | `pixel_clk`、`pixel_clk_5x` | 端口存在，但两个 OSERDES 的 `RST` 固定为 `0` | reset 输入无功能，且使用无位宽常量 | O1 核验厂商模板后连接真实复位，或经评审删除无效端口 |

旧 STA 的最差 recovery 路径从 `ui_clk` 域 `ddr3_init_done` 到 pixel 域 `reset_syn/reset_1`，WNS `-4.857 ns`、TNS `-214.054 ns`，53/53 endpoints 失败。见 `prj/report_timing/ov7725_hdmi.rtr:116-130,8272-8341`。

## 5. 整改设计契约

后续实现批次必须遵守以下设计边界：

1. 每个时钟域使用独立的异步置位、同步释放复位；复位同步器只在目标域释放。
2. `ddr3_init_done` 是状态/使能，不是跨域复位源。
3. `wr_load`、`rd_load` 各自只建立一个跨域接收点，目标域同步后再扇出。
4. 事件传输必须定义最小事件间隔、复位行为和“一次源事件对应一次目标脉冲”的断言。
5. 多位数据只通过经过核验的异步 FIFO或握手协议传输，不采用逐位二级同步。
6. FIFO 的写侧、读侧复位分别在各自时钟域释放；是否使用 reset 或 flush 以 Pango IP 文档为准。
7. 时序例外只能在结构整改后添加，并精确限定到同步器或厂商 FIFO内部路径。
8. 新增或修改的手写 RTL/TB 必须遵守根目录 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`；厂商生成文件保持原样。

## 6. 验收证据

O2/O3/O4 关闭前至少需要：

- CDC/RDC 结构审查不再发现裸脉冲、复位重汇聚或跨域状态直连异步复位脚；
- 每个事件同步器的源/目标计数断言通过，复位期间不产生伪事件；
- FIFO 指针同步和 reset/flush 行为符合对应 IP 版本文档；
- FDC 中所有生成时钟和例外对象均匹配，且不存在覆盖整个模块或整个时钟域的宽泛 `false_path`；
- PDS SP6.4 重跑后 setup、hold、recovery、removal 全部非负；
- 原 `-7.056 ns`、`-2.279 ns` 和 `-4.857 ns` 路径不再作为未批准的普通时序路径出现。

## 7. 仍需外部事实

以下问题不能由现有源码单独确认：

- OV7725 实际像素时钟范围、RGB565 字节序、分辨率和帧率；
- camera 输入相对 `cam_pclk` 的板级 setup/hold 与 PCB 延迟；
- `PAP_CLOCK_DEDICATED_ROUTE FALSE` 是否有原理图和布局依据；
- HDMI 输出模式和外部时序要求；
- DDR3 颗粒、32-bit 组织、速率、拓扑及 byte-lane 映射；
- PLL 和 FIFO IP 是否应使用 PDS SP6.4 重新生成。

这些信息缺失时，允许继续做构建基线和结构整改，但不得声称板级时序或产品功能通过。

补充边界：`cam_init_done` 和顶层隐式 `sys_init_done` 当前未被功能逻辑消费，不构成有效 CDC；`cam_sda` 属 SCCB/I²C 双向接口，应按总线采样相位验证，不能简单套用二级同步器。
