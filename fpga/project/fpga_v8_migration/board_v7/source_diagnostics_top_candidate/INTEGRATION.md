# V7 顶层旁接候选接线

硬件候选入口为 `v7_sdt_top.v`（模块 `v7_sdt_top`），从冻结
`whole_candidate_v7_route_01/rtl/fpga_v8_cooperative_top_v2_rfg01.v` 派生。
仅替换 camera parent 为 `v7_sdt_camera`、binding 为 `v7_sdt_binding`。
`sources.json` 是冻结工程登记源加上述三项替换及两个诊断模块的完整清单。
没有生成/修改 PDS 工程；没有引入 `cdc_boundary*`。

**实际集成发现并修正 bus 候选缺陷**：原 v7_sdb 先等 AWREADY 再发 WVALID，
但冻结 ov5640_reg 的 AWREADY/WREADY 都等 AWVALID && WVALID，会使旧 CAM 写死锁。
本目录 `v7_sdt_bus.v` 从原件字节派生，收齐上游 AW/W 后同时发出下游 AWVALID/WVALID，
两通道各自握手后撤销；B 仍等两个通道完成。冻结 decoder 第64行在 AWVALID 时使用
aw_live，之后使用 aw_saved，故同时发送不会串相机。原文件不改；diff 保存这一必要修正。

冻结 top 的 M00 写通道已经退役（AWREADY/WREADY 固定0），但其 BVALID/BID/
BRESP/BUSER 输入悬空。完整顶层首笔 CAM 写观测到适配器与 M01 bridge 的 BVALID=1，
上游 BVALID=X，无法完成返回仲裁。本地 top 派生将这四个闲置输入接0；不改变
M00 读通道或原独立写仲裁路径。这是额外的冻结接线缺陷修正，包含在 top diff 中。

COOP 首次访问还观测到 M02 ARLEN=z0。S00 的 PCIe LEN 为4位、crossbar 输入为8位；
候选对 S00 AWLEN/ARLEN 显式拼接4位0，避免端口折叠时高位悬空。没有改变 burst 长度。
COOP/CAPL 实际 DMA 地址为 0x40010000/0x40010400：端点将 DMA 偏移右移2位。

## 实际总线

`axi_crossbar_7x3` S00 → M01 → `axi_to_axi_lite` → `source_diagnostics`
→ `ovreg_axil_decode_u` → 原 CAM1/PREP/CAM2/CAM3/CAM4 端点。
M01 默认 BASE=0x20000000，ADDR_WIDTH=29，顶层 CONNECT_READ/WRITE=7'b0000001。
因此 0x20001000..0x200013ff 从 S00 可达 M01，不需改 crossbar 地址表。
COOP/CAPL 保留 M02 原路径。新增适配器仅精确匹配 `[31:10]==22'h080004`；
区间内非法偏移 SLVERR；区间外保持旧低位 decoder 语义，包括旧地址别名。

每相机 stride=0x100，STATUS/COMMAND/INDEX/DATA/EPOCH 偏移为
0x00/0x10/0x20/0x30/0x40。DMA 单拍 128-bit，数据低32位。
必须检查主机地址16字节对齐；原 DMA 先清低4位，不能靠适配器检出上游丢失的低位。
burst 不在冻结 bridge 的支持合同内。

## 四路实际旁接

| bit | 顶层 camera 实例 | binding 相对实例 |
|---|---|---|
| 0 | ov5640_top | ov5640 |
| 1 | cam2_ov5640_top | ov5640 |
| 2 | cam3_ov5640_top | ov5640 |
| 3 | cam4_ov5640_top | ov5640 |

每个 binding 导出 7 个只读输出：

| 导出端口 | 实际来源 |
|---|---|
| diag_clk | cam_pclk |
| diag_reset | !ov_rst_n OR !cam_rst_n |
| diag_raw_vsync | capture_vsync，实际 cmos_capture 输入 |
| diag_raw_href / diag_raw_byte_accept | cam_href，不门控 VSYNC |
| diag_capture_vsync | cmos_frame_vsync_r，原 negedge 寄存器 |
| diag_capture_valid | cmos_frame_valid_r，原 negedge 寄存器 |

原 negedge 寄存器**没有 reset**；候选不修改它们。诊断会话采用 capture reset 和
源 CDC reset 的合并请求，复位恢复后重新建窗，不能把 negedge 残值当新快照。
数据 payload、RAW、FIFO、DDR、motion、6cam SFP、COOP/CAPL 接线及复位原封保留。
保持 DATA_WIDTH=16、capture DELAY=2；CAM1/2 的 VSYNC_STABLE_CYCLES=0，
CAM3/4 冻结参数为64。四路 diag_raw_vsync 均接实际 capture 输入（后两路为资格化后信号），
测试 VSYNC 高低均保持80 PCLK，以经过真实资格化逻辑。

## 复位合同

诊断 bus 的 `clk/rst` 与原 bridge/decoder 一样接 `axi_clk/axi_rst`；
`axi_rst=~ddr_init_done`。camera reset 不清 AXI 状态，不取消已接受 AR，
不撤销 stalled R/B。结果承诺前会话失效产生 SLVERR，已承诺响应保持到握手。
每路 reset_pipe 异步置位、四拍释放，epoch 记录 invalid 进入；短脉冲可被捕获。
epoch 饱和 fail-closed；只有整个 AXI reset 清零 epoch，驱动须丢弃旧上下文。

camera_ctrl_rst_n 保留冻结独立上电计数器：65536 个 clk_50m 边沿后释放，
不因 camera reset 或 AXI reset 自动重新计数。诊断没有向 camera_ctrl 反向连接。
主机读取仍需 lease 独占、INDEX/DATA 串行、前后 STATUS/EPOCH 一致校验。
原 source 候选文档“取消待处理响应”不适用；采用 bus 候选修订合同。

## 仿真清单与边界

`compile.f` 为实际 ModelSim 清单，过滤冻结顶层不实例化的旧 RTL；加载全部活动实例。
DDR 用冻结 IP 中官方 sim_lib，primitive 用 PDS 安装内 ModelSim 官方模型。
`ip_duplicates.json` 记录重复官方模块的选择，audit 对去注释 token 完全一致性断言。

`sim_views/` 仅供 ModelSim：原 top 及四个 PCIe parent 的前向声明上移；
wire initializer 保留为原位置 assign；显式声明四个继承的隐式1位 net；
移除 top 重复 wire prep_frame_cnt，保留实际8位 reg；展开 USE_OV5640 的活动分支。
不改变状态机、赋值表达式、端口、复位或数据路径。原件和硬件候选保持不动，差异可审阅。

`tb_elab` 仅提供厂商要求的 `GRS_INST`，实例化完整候选 top。
`tb_sdt` 在 PCIe DMA 输出 AXI 边界注入单拍访问，驱动四路顶层 DVP 输入，
用 force 提供 AXI 时钟/DDR init、I2C 完成与 camrun；不 force capture/诊断内部计数器。
这不验证 PCIe 链路训练、DDR PHY 实际校准、远程驱动或板级模拟采样。
