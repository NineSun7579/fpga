# 双 OV5640 C0 参考工程审计

日期：2026-09-01

```text
Status: C0 complete; C1 blocked
Import: none
Reference: origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3
Product target: Logos2 / PG2L50H / FBG484 / -6
Physical FPGA: PG2L50H-6IFBG484
Future project: 59_top_dual_ov5640_hdmi/
```

## 结论

C0 只读审计完成。本批没有导入参考分支的 RTL、IP、FDC、PDS、TB 或生成物，也没有创建可综合或可烧录的新工程。

参考分支提供了可继续审核的双 OV5640、DDR3、HDMI 和 PCIe 数据面素材，但不能整体合并：

- HDMI 明文层级包含 17 个参考 RTL，另依赖 83 个 Pango 生成或受保护源。
- 根 PDS 目标为 PG2L100H，当前 top 却是 `top_dual_ov5640_pcie`，同时仍加载 HDMI FDC/PCF 和旧 HDMI 阶段产物。
- DDR3、PLL、读 FIFO、写 FIFO 均为 PG2L100H IP；PCIe IP 虽为 PG2L50H，但 BAR1/BAR2 均禁用，与参考 RTL 的控制窗和视频窗合同冲突。
- FDC 没有 camera input delay 或 HDMI output delay，包含 camera dedicated-route override、`PAP_IO_UNUSED` 和旧实例层级；只能作为管脚候选表。
- 参考 TB 只覆盖缩小的驱动级像素计数和独立 packer/RAM；它们没有形成双摄到 DDR3/HDMI 的项目集成证据。

C1 仍受 H3 板级资料阻断。只有两只模组、MCLK、DVP、时序、电压、管脚、DDR3 和 HDMI 模式全部冻结后，才允许另开选择性导入批次。

## 参考身份

| 字段 | 值 |
|---|---|
| 远端引用 | `origin/parallel_driver` |
| 审计提交 | `485f3bba71e4b57fb8bb49cec30e9d331b952be3` |
| 父提交 | `81c7601dcd31ec9f8a18f4e5665f51a73de274ee` |
| 提交主题 | `Update README with completed and pending tasks` |
| 参考顶层 | `rtl/top_dual_ov5640_hdmi.v` |
| 参考 PDS 当前 top | `top_dual_ov5640_pcie` |
| 目标产品顶层候选 | `top_dual_ov5640_hdmi`，后续必须在新工程重新审核 |

参考 README 的 `PASS:` 文本和 “Compile error=0” 都只是该分支自述；没有本仓库 canonical `.f/.do`、run marker、唯一 `TEST PASS`、错误汇总和退出码，因此不构成验收证据。

## HDMI 参考层级

```text
top_dual_ov5640_hdmi
├─ pll_clk                                      # PG2L100H 生成 IP
├─ ov5640_dri ×2
│  ├─ i2c_ov5640_rgb565_cfg
│  ├─ i2c_dri
│  └─ cmos_capture_data
├─ ddr3_ctrl_top
│  ├─ ddr3_rw_ctrl
│  ├─ aq_axi_master
│  ├─ ddr3_fifo_ctrl_top
│  │  └─ ctrl_fifo ×2
│  │     ├─ wr_fifo                            # PG2L100H 生成 IP
│  │     └─ rd_fifo                            # PG2L100H 生成 IP
│  └─ ddr3_ip                                  # PG2L100H 生成 IP
└─ hdmi_top
   ├─ video_driver
   ├─ hdmi_disply
   └─ dvi_transmitter_top
      ├─ asyn_rst_syn
      ├─ dvi_encoder ×3
      └─ serializer_10_to_1 ×4
```

PCIe video、PCIe DMA、PCIe IP 和 UART 文件虽然进入参考 PDS source set，但 HDMI 顶层不实例化它们。后续必须为 HDMI 建立独立 manifest，不能把混合工程 compile 结果当成 HDMI 闭包验证。

## 明文 RTL 候选登记

以下文件只登记为候选，不表示已批准导入。共同来源均为本文件顶部的参考提交。

| 文件 | Blob SHA-1 | 职责 | C1 后处置 |
|---|---|---|---|
| `rtl/top_dual_ov5640_hdmi.v` | `2fedba75e4a0f6c98d90519bf9b84bcf2cc7e286` | 双摄、DDR3、HDMI 顶层组合 | 条件导入；先重建产品接口和逐域 reset/CDC 合同 |
| `rtl/ov5640_dri/ov5640_dri.v` | `494d0f0f88ada727b6c46a7c3a136b6236218d0f` | SCCB 配置与采集包装层 | 条件导入；补双路读 ID、初始化完成和失败语义 |
| `rtl/ov5640_dri/cmos_capture_data.v` | `404cbf8522d3b4ea52f6eddcbf928afeb42a5ff1` | DVP 字节到 RGB565 采集 | 条件导入；先确认极性、字节序和帧契约 |
| `rtl/ov5640_dri/i2c_dri.v` | `cafa7f9f378512e42be6aab547aa7a82a4a5c725` | SCCB/I2C 主控制 | 条件导入；审核 FSM、ACK、超时和错误返回 |
| `rtl/ov5640_dri/i2c_ov5640_rgb565_cfg.v` | `1882ad966138eec52b7500a48731a277a0571eea` | OV5640 RGB565 寄存器配置 | 条件导入；必须由实际模组和模式资料复核 |
| `rtl/ddr3_ctrl_top/ddr3_ctrl_top.v` | `c8f1abfbb1f57b5601e204469446b4d35d8a2a47` | DDR3 controller/PHY 与业务控制包装 | 条件导入；先用 PG2L50H IP 和板级 DDR3 合同重建 |
| `rtl/ddr3_ctrl_top/ddr3_rw_ctrl.v` | `18af0ef6ad2b5c81ccdeefbdc6bc7c25795d21a1` | 双写/双读仲裁与地址状态机 | 条件导入；审核 FSM、帧布局和跨域事件 |
| `rtl/ddr3_ctrl_top/ddr3_fifo_ctrl_top.v` | `6f86b433bb5881585cad1bf0fe3171d1a98d18fe` | 两路 camera/DDR/pixel FIFO 组合 | 条件导入；先定义双侧复位和数据丢弃策略 |
| `rtl/ddr3_ctrl_top/ctrl_fifo.v` | `ac6277c7f85b3b4f00db80d6cf887b686c452e88` | 异步、混宽读写 FIFO 包装 | 条件导入；补 full/empty、ready/busy 和 reset 合同 |
| `rtl/ddr3_ctrl_top/aq_axi_master.v` | `4f26e66a45364469b5888a9970c215825ebc6434` | DDR 用户接口读写 master | 条件导入；审核读写 FSM、握手和错误处理 |
| `rtl/hdmi_top/hdmi_top.v` | `ebf0cdd3f4df61b5ad13713ddb4d1a56e67f79f6` | HDMI timing、读请求与 TMDS 包装 | 条件导入；先统一视频模式和 reset |
| `rtl/hdmi_top/video_driver.v` | `6b12983bc911127113f6b31ad3d2ded93f63278b` | HDMI raster timing | 条件导入；当前 1280×720 与顶层 1080p 冲突 |
| `rtl/hdmi_top/hdmi_disply.v` | `919f92af2cfd60ce25802cf783bbeea3ddfde65d` | DDR 读数据到 RGB 显示 | 条件导入；审核像素位置、延迟和欠流行为 |
| `rtl/hdmi_top/dvi_transmitter_top.v` | `be45f9af910a3e2e8908ed764f78385171900d8f` | TMDS 编码与四路 serializer 包装 | 条件导入；先修复 serializer reset 接口矛盾 |
| `rtl/hdmi_top/dvi_encoder.v` | `b24f413dd7197f1e8410a46b4610dd23b9a7f3b6` | TMDS 8b/10b 编码 | 暂缓；先核对文件头来源和再分发许可 |
| `rtl/hdmi_top/serializer_10_to_1.v` | `46f692f395f87e7e8735694f5b0718daafbdeacf` | Pango OSERDES/差分输出 | 暂缓；`reset_n` 未使用且 OSERDES reset 固定为 0 |
| `rtl/hdmi_top/asyn_rst_syn.v` | `7652218beca82658a0a42fd6c3ea597dad9e32b3` | pixel clock 域复位同步 | 条件导入；确认极性、级数和 5x 域关系 |

### VSCS 编码门槛

严格 UTF-8 解码确认以下 10 个文件不满足 VSCS-GEN-005：

```text
rtl/ov5640_dri/cmos_capture_data.v
rtl/ov5640_dri/i2c_dri.v
rtl/ov5640_dri/i2c_ov5640_rgb565_cfg.v
rtl/ddr3_ctrl_top/ddr3_fifo_ctrl_top.v
rtl/hdmi_top/asyn_rst_syn.v
rtl/hdmi_top/dvi_encoder.v
rtl/hdmi_top/dvi_transmitter_top.v
rtl/hdmi_top/hdmi_disply.v
rtl/hdmi_top/serializer_10_to_1.v
rtl/hdmi_top/video_driver.v
```

17 个候选文件都必须按 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md` 重新审核。导入前至少关闭：文件职责边界、端口时序/极性、逐域 reset、CDC/RDC 分类、FIFO 双侧复位、FSM 类型/编码/非法状态、外部假设、可观察延迟和最重要 hazard。文件头中的作者、日期、版本和 Revision History 不得继续手工维护。

## PCIe video 参考资产

这些文件不是 HDMI 最小闭包，只作为后续 PCIe/DDR 数据面研究输入：

| 文件 | Blob SHA-1 | 结论 |
|---|---|---|
| `rtl/pcie_video/rgb565_to_axis128.v` | `0281f8d1820983a69af97c6a4be8187dbb1cff5e` | 可作为 packer 参考；需独立接口/背压/帧边界合同 |
| `rtl/pcie_video/axis128_bar2_ram.v` | `165c8344cac5718f4ef9f338f076c4580f0f305a` | 可作为 RAM 参考；当前 BAR2 IP 配置未启用 |
| `rtl/pcie_video/pcie_video_endpoint.v` | `1cc6ff2e59f4ef8ea0dd37ea4265a914a55494a6` | 依赖 PCIe DMA/IP；不进入 HDMI 导入批次 |
| `rtl/pcie_video/top_dual_ov5640_pcie.v` | `fc88eabfbc937516b6fc616d7066b680195a2d78` | 当前参考 PDS top；不作为 HDMI 产品顶层 |

## Testbench 登记

| 文件 | Blob SHA-1 | 当前覆盖 | 处置 |
|---|---|---|---|
| `sim/tb/Video_Image_Simulate_CMOS.v` | `7ff258a6ec04b0a0e89d896f0dd6efdefbddf62f` | 缩小帧 DVP 输入模型 | 可作为素材；需审核极性、字节序和参数单位 |
| `sim/tb/tb_dual_ov5640_dri.v` | `f8d6804fe0cc9ce1976ef8dc874312477106c610` | 两路缩小帧像素计数 | 不直接导入；force 两路 init，未覆盖产品 960×1080 半幅 |
| `sim/tb/tb_ov5640_dri.v` | `2b46ce399d66e2c50451d2cccdc2ad779624cf08` | 单路驱动级多帧采集 | 仅作子模块参考；产品主线为双摄 |
| `sim/tb/tb_rgb565_to_axis128.v` | `f83eace45303daa034eee597b96065c70301b8d4` | 两个固定 BAR2 word | 仅作 packer/RAM 单元参考；不是集成数据面 |

四个 TB 都缺少本仓库 canonical `.f/.do` 和 run-scoped launcher。后续 S3 必须使用唯一 `TEST PASS`、有界 watchdog、失败 `$fatal`、错误汇总与非零退出；不得用 `force cam_init_done` 代替双路 SCCB 读 ID/配置验证。

## PDS 与 IP 审计

| 对象 | 参考事实 | C0 结论 |
|---|---|---|
| `prj/project.pds` | PDS SP6.4；PG2L100H；当前 top=`top_dual_ov5640_pcie`；混合 HDMI/PCIe/UART source set | 只作来源清单参考；新建干净 PG2L50H 工程 |
| `ddr3_ip.idf` | v1.10；PG2L100H；DDR3 800 MT/s、x32 | 不导入；依据实际 DDR3 重新生成 |
| `pll_clk.idf` | v1.5；PG2L100H；参考输出 75/375/50 MHz | 不导入；视频模式冻结后重新生成 |
| `wr_fifo.idf` | v1.10；PG2L100H；16→256 异步 FIFO | 不导入；按 PG2L50H 资源/复位合同重新生成 |
| `rd_fifo.idf` | v1.10；PG2L100H；256→16 异步 FIFO | 不导入；按 PG2L50H 资源/复位合同重新生成 |
| `pcie_test.idf` | v1.2c；PG2L50H；`BAR0_Enable=true`、`BAR1_Enable=false`、`BAR2_Enable=false` | 不进入 HDMI 批次；与参考 PCIe video 合同冲突 |

四个 HDMI 必需 IP wrapper 的参考 blob 仅用于防止来源混淆：

```text
ca8f8305a4c0b301aae82c4c093410d1717f60d4  ipcore/ddr3_ip/ddr3_ip.v
1f9bbb25b4f0c51dede661796a2a53bc0669aadc  ipcore/pll_clk/pll_clk.v
fde716bca6dfc99d911033468f73a14b642b7c30  ipcore/rd_fifo/rd_fifo.v
953eefba4b3d24aca1655acb83c3023fa4b61b37  ipcore/wr_fifo/wr_fifo.v
```

这些 wrapper 及其 83 个生成/受保护源都不得复制到新项目。PG2L50H IP Compiler 输出必须进入 `59_top_dual_ov5640_hdmi/build/ipgen/**` staging，完成参数、wrapper、FDC/RCF、仿真资产和资源差异审核后再决定是否升格。

## FDC 审计

参考文件：

```text
ed41a435b00b27013bd0c4a8613a08bbee3132b9  constraints/top_dual_ov5640_hdmi_pin.fdc
```

机械统计：

| 项目 | 数量 |
|---|---:|
| primary clock | 3 |
| generated clock | 6 |
| input delay | 0 |
| output delay | 0 |
| multicycle path | 2 |
| camera `PAP_CLOCK_DEDICATED_ROUTE FALSE` | 2 |
| camera `PAP_IO_UNUSED` | 4 |

FDC 假设 `sys_clk=50 MHz`、两路 `cam_pclk=25 MHz`、camera LVCMOS33、DDR SSTL15。像素/5x 时钟约束被注释，camera 与 HDMI 没有 I/O delay。DDR generated-clock 和物理位置还硬编码旧实例层级。因此该文件只能作为逐管脚候选表，不能直接进入 PG2L50H canonical 工程。

## 结构与文档阻断

1. `rst_n = sys_rst_n & clk_locked` 直接分发到 camera、DDR `ui_clk`、pixel/5x 等域，没有逐域同步释放合同。
2. `ddr3_init_done` 未同步就参与两个 camera 域 capture/reset 和 HDMI pixel 域 reset，形成 CDC/RDC 链。
3. camera frame event 与 HDMI `video_vs` 的跨域协议未说明脉宽、事件间隔、丢失/重复和复位期间行为。
4. 异步 FIFO 未说明双侧 reset 顺序、full/empty 延迟、ready/busy 和复位期间数据策略。
5. serializer `reset_n` 未使用，OSERDES reset 固定为 0；当前实现不能证明 TMDS 串行域正确复位。
6. 顶层 1920×1080/2200×1125 与 `video_driver` 1280×720/1650×750 冲突；75 MHz 也不是已签核的 1080p60 像素时钟合同。
7. 顶层声明 camera init 状态，但 `sys_init_done` 实际只等于 DDR init；注释与实现不一致。
8. `ddr3_rw_ctrl`、`aq_axi_master` 和 `i2c_dri` 的 FSM 缺少 VSCS 要求的类型、编码、非法状态与接口延迟说明。

以上缺口只能由 RTL、约束、CDC/RDC、仿真和 STA 证据关闭，不能靠补注释宣称安全。

## 禁止导入项

- `sim_dual_ov/**`、`sim_syntax/**`、`sim_video_path/**`、`sim_work/**` 和根 `transcript`。
- `prj/compile/**`、`prj/synthesize/**`、`prj/device_map/**`、`prj/place_route/**`、`prj/constraint_check/**`、所有阶段 backup/log/database。
- `prj/compile/parse_design/screen.tcl` 等带用户目录绝对路径的生成入口。
- `ipcore/ddr3_ip/sim/vcs/sim_file_list.f` 等带 PDS 安装绝对路径的 filelist。
- `ipcore/*/sim_lib/**`、`ipcore/*/pnr/**`、`ipcore/*/example_design/**`、`.last_generated`、`.settings` 和 `generate.log`。
- `.qdb`、`.qpg`、`.qtl`、`.mpf`、`modelsim.ini`、日志、波形、网表、SDF、bitstream 和公共 simlib。

审计 grep 在参考 RTL/IP/PDS/sim/constraints 范围内发现 4607 处绝对路径匹配；禁止通过批量替换路径把这些资产伪装成可移植源码。

## C1 必须由 owner 审核的输入

1. 两只 OV5640 模组完整料号、连接器定义和是否需要独立 XCLK/MCLK。
2. 每路 SCCB 上拉、电压、RESET/PWDN 极性和上电/配置时序。
3. DVP 位宽、PCLK/VSYNC/HREF 极性、RGB565 字节序、实际帧率和 blanking。
4. 每路 960×1080 半幅及最终 1920×1080 左右拼接是否为产品合同；是否允许不同步帧、丢帧或单路失效。
5. HDMI 输出分辨率、刷新率、像素时钟、TMDS 电气和外部 sink 时序要求。
6. DDR3 完整料号、颗数、x32 拓扑、row/column/bank、DQ/DQS/DM、VREF/ODT 和布线依据。
7. PG2L50H 全部 camera/DDR/HDMI 管脚、bank、VCCIO、专用时钟能力和 share-pin 约束。

任一输入未关闭时，C1 保持 blocked，不生成 canonical IP/FDC，不运行 PDS 发布流程，也不声明行为级或实板通过。

## 下一批入口

C1 输入冻结后，另开选择性导入 PR：

1. 创建 `59_top_dual_ov5640_hdmi/` 的最小目录和独立 source manifest。
2. 只导入经许可、严格 UTF-8、按 VSCS 补齐接口/复位/CDC/FSM 文档的明文 RTL。
3. 在 `build/ipgen/**` 为 PG2L50H 重新生成 DDR3、PLL、读写 FIFO，并原子审核。
4. 从实板事实重建 FDC/RCF，不复制参考 FDC。
5. 在项目内 `sim/questa/` 归档经审核的模型/TB 和相对 `.f/.do`；运行态只进入项目 `build/`。
