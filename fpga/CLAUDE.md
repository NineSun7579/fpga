# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

工程根目录：`C:\Users\NineSun\Desktop\ov56401`（`project/` 是 PDS 编译工作目录，不是仓库根）。

`AGENTS.md` 是同目录下的旧版指南，仍可参考其中的陷阱清单，但**架构描述已过时**（它按 NPU 还在的前提写；NPU 已于 2026-09-12 物理删除，编译时间从 33 分钟降到约 7 分钟）。两者冲突时以本文件为准。

## 系统概览

紫光同创 Logos2 FPGA 工程（PDS 2022.2-SP6.4，器件 PG2L100H-6FBG484），当前形态是一条**相机显示链路**：

```
OV5640 (DVP, RGB565) → FPGA 采集/写卡 → DDR3 乒乓缓冲 → PCIe Gen2 x2 DMA → RK3568 (Qt5 camview) → X11 → HDMI
```

NPU(YOLO 加速器)、`pcie2npu/`、`axi_crossbar/npu_to_core_cdc_bridge.v` 等已归档至 `_attic/unreachable_npu/`（保留原相对路径，可整体回滚）。`source/preprocess/` 的 9 个模块仍注册在 `project.pds` 中并可综合，但**像素通路在 top.v 中被显式禁用**（见下）。

## 常用命令

**全流程编译**（compile → synthesize → dev_map → pnr → gen_bit_stream，约 7 分钟）：

```bash
cd project && C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe \
  -project C:/Users/NineSun/Desktop/ov56401/project/project.pds \
  -run gen_bit_stream -work_dir C:/Users/NineSun/Desktop/ov56401/project
```

`-run` 合法取值只有：`compile / synthesize / dev_map / pnr / report_timing / report_power / gen_bit_stream / gen_netlist`。产物：`project/generate_bitstream/top.sbit`，资源/时序报告在 `project/{synthesize,place_route,report_timing}/`。

**编前必做**（见陷阱 2、3）：`tasklist | grep -i pds` 确认无进程；清空 `project/{compile,synthesize,device_map,place_route}`。

**ModelSim 回归**（需 Python3；ModelSim 默认 `C:\modeltech64_10.6e\win64`，`MODELSIM_BIN` 可覆盖）：

```bash
cd sim/preprocess && ./run_all.sh [W H]     # 默认 64x36 快速；640 360 全分辨率
```

`sim/npu/run_all.sh` 引用 `../../source/npu/`，**该目录已归档，此回归当前跑不起来**；要用需先把 NPU 从 `_attic/unreachable_npu/` 取回。

**可达性/死文件检查**（增删源文件后必跑，参数是 top 模块名）：

```bash
python _attic/reachability_check.py top
```

**JTAG 烧录**（易失性，掉电即失）：`cdt_js.exe -port 65422` 起服务，再用 `cdt_cfg.exe -ip 127.0.0.1 -port 65422 -file flash_jtag.tcl` 执行；`flash_jtag.tcl` 内是 `cfg_scan_chain` + `cfg_assign_file` + `cfg_program`。`recover_display.py` 把整套流程（烧录→驱动重载→重启 camview）做成了看门狗。

**板端操作**：板子经 `COM9@1500000` 连本机。`sh.py "<bash>"` 执行片段，`_pull.py`/`pull2.py` 拉文件，`xfer_hex.py` 推文件（均 base64/HEX 编码，原因见陷阱 7）。

## 架构要点

### top.v（`source/top.v`，约 1950 行）

单文件顶层，把五块拼起来：

| 块 | 来源 | 说明 |
|---|---|---|
| 相机 + 写卡 | `source/ov5640/` | `ov5640_top` 内含 SCCB 配置 FSM、DVP 采集、`ov5640_ddr*` 写引擎 |
| DDR3 | `ipcore/ddr3/` | PDS 生成，控制器 + PHY；`axi_clk` 即 ddrphy sysclk |
| PCIe | `ipcore/pcie_test/` + `source/pcie_dma/` | 硬核 + `ips2l_pcie_dma_*` 参考 DMA 引擎 |
| 寄存器窗 | `source/ov5640/ovreg_axil_decode.v` + `ov5640_reg.v` + `preprocess/prep_regs.v` | 见下 |
| 交叉开关 | `source/axi_crossbar/` | `axi_crossbar_7x3`：7 主 3 从 |

**AXI 地址段**（由 crossbar 译码，实测确认）：`M00=DDR3 0x0~0x1FFF_FFFF`、`M01=寄存器 0x2000_0000~0x3FFF_FFFF`、`M02=NPU 0x4000_0000~0x5FFF_FFFF`（NPU 已删，端口 tie-off，地址段保持不变）。

`M01` 内部再由 `ovreg_axil_decode` 按 `addr[8]` 二分：`0x2000_0000~0x00FF` → `ov5640_reg`（相机/诊断寄存器），`0x2000_0100~0x01FF` → `prep_regs`（预处理/注入寄存器）。

**时钟**：`free_clk`(V4, 25MHz LVCMOS15) 是根时钟，同时喂 `ipcore/ov5640_clk`（PLL，出 `clk_50m`/`clk_150m`/`clk_10m`）和 DDR3 ref_clk。约束里 `free_clk` 的 `UNUSED=TRUE` 是 IO 属性，不是"未使用"。

### 寄存器契约

以 `DOC/FPGA_RK3568_传输协议_v1.md` 为唯一同源依据（v1.1，含实现状态列）。两类访问通道：

- **BAR1 直写描述符**（只写不可读）：`+0x100` CMD、`+0x110/0x120` HOST_ADDR_L/H、`+0x1E0` FPGA_AXI_ADDR、`+0x200` TOTAL_LEN。写入 `+0x110` 即触发传输。
- **AXI 地址窗**（经 DMA 间接读写，值放 16 字节传输的 byte0~3，小端）：`0x2000_0000+0x00` XDMA_ACK、`+0x40` CAM_EN、`+0x80/0xC0` CAM_ADDR_1/2。

诊断寄存器（`_attic/…` 与交付说明中有表）：`+0x30` words、`+0x34` vsyncs、`+0x38` xdma_req 帧就绪、`+0x3C` NACK/相机 ID、`+0x44` pclk 计数、`+0x48` I2C 事务数、`+0x4C` clk_50m 计数/locked。**读这些值时注意陷阱 6——寄存器读回存在已定位缺陷。**

### 预处理 IP（`source/preprocess/`）

`rgb2gray → colorize → sobel_edge` 流水线，配 `align16`/`prep_sync_fifo`/`preprocess_top`，另有 `lane_detect`、`button_debounce`、`prep_regs`（AXI-Lite 寄存器）、`cam_prep_link`（相机流 tap）。

**当前 top.v 状态：像素通路禁用**。`cam_prep_link` / `preprocess_top` 的例化被整块注释（标注 `[OptionB 2026-09-12]`），预处理写引擎 `prep_wr_*` 被常量 tie-off，相机原始流直接 `assign cam_s_data = cam_tap_data`（标注 `[2026-09-12] RAW camera path restored`）。原因：`cam_prep_link` 的 TB 未通过，其 dummy-inject 会反压/卡住相机。恢复像素通路是下一阶段工作，需要先把 `cam_prep_link` 的 TB 校准（`sim/preprocess/tb_cam_prep_link.v` 已在仓库里）。

流水线契约（改任何一级都要维持，详见 `sim/preprocess/README.md`）：`s_valid` 单拍语义、每帧 `H*W+1` 像素（帧尾 1 哑像素）、灰度 `Y=(77R+150G+29B)>>8`、`sobel`/`align16` 移位结构严格同构（含中心列 fire 条件）。

## 硬性陷阱

1. **GBK 编码**：`source/` 下多数 `.v` 含 GBK 中文注释。git bash 的 grep 对这些文件**静默漏匹配**（纯 ASCII 内容也漏）。一切文本搜索/替换用 Python **字节级**操作（`_attic/overnight_sweep.py` 的 `apply_edit()` 是范例）。
2. **PDS 单实例**：两个 `pds_shell` 并发写同一工程目录 → DB 相位冲突（Flow-0013）。启动前 `tasklist` 确认无 `pds_shell.exe`/`pds.exe`；编译前清空 `project/{compile,synthesize,device_map,place_route}`（防增量流程相位冲突）。
3. **PDS GUI 打开时勿改工程**：GUI 退出会回写 `project.pds`，覆盖你的编辑。改 `project.pds` 或移动源文件前必须先关 PDS。另：`project/project.pds.lock` 是残留锁文件，崩溃退出后可能留下（内容形如 pid + hostname），确认无进程后可直接删。
4. **`project.pds` 是源文件登记表**：新增 RTL 必须在此登记 `_file` 条目，否则不参与综合。删除源文件是"三件套"——移动文件 + 删 `_file` 块 + 跑 `reachability_check.py` 复查。
5. **模块重名**：PDS 报 duplicate module 就整个工程编译失败。新增 RTL 前先扫重名（曾因 `sync_fifo` 与 `npu/common/sync_fifo.v` 撞名返工）。
6. **寄存器读回不可信**：已定位两个 RTL 缺陷——`prep_regs.v` AW/W 背靠背写失步（`axi_to_axi_lite` 把 16B DMA 拆 4 拍连写时丢写/错位，之后读通道退化为全 0），以及寄存器窗 b2b 读返回上一次数据（`tb_ovreg_axil_decode` 仿真失败即为实证）。`prep_regs` 的 v2 修复已在源码但**未出比特流**。当前板载比特流的诊断寄存器读数要按"可能是上一次的值"来解读。
7. **板端串口**：连续传输 >~115s 会触发 RK FIQ 调试器截获控制台（与内容无关）；数据里出现字面量 `fiq` 三个字符也会立即触发。恢复办法：发 `console\r\n`。这是 `xfer_hex.py`/`pull2.py` 改用 HEX 编码的原因。
8. **JTAG 烧录后必须重载驱动**：`cfg_program` 会复位 FPGA PCIe 核，不做 PERST 复位 + `remove`/`rescan` + `rmmod`/`insmod`，则一切总线主控 DMA 静默死锁（MMIO 却正常，极具迷惑性）。另：`cdt_js` 服务器一次会话后即失效，每次烧录前 `taskkill /F /IM cdt_js.exe` 并重新起端口；驱动侧任一 DMA ioctl 超时后 `g_dma_flag` 残留，后续 DMA 全部 800ms 超时，必须 `rmmod; insmod`。

## 已知不一致（读文档时留意）

- **相机分辨率与帧长**：`ov5640_top.v` 里 `H_CMOS_DISP=640 / V_CMOS_DISP=480`，这两个参数直接写进 OV5640 的 `0x3808~0x380b` 输出尺寸寄存器，且 `CAM_DATA_LEN` 由它们推导 → 当前 DDR 帧区应为 **640×480×2 = 0x96000 字节**。但 `DOC/交付说明_OV5640_QT显示_2026-09-13.md`、`DOC/FPGA_RK3568_传输协议_v1.md`、`host/camview/main.cpp` 的 `IMG_W/IMG_H` 备注仍写 1280×720 / `0x1C2000`。改分辨率或读帧长前先确认这一项。
- **`clk_50m` 未受约束**：`ipcore/ov5640_clk/ov5640_clk.idf` 按 `CLKIN_FREQ=50.0` / `CLKOUT0_REQ_FREQ=50.0` 生成，但实际 `clkin1` 接的是 25MHz `free_clk`（这正是 [CLKFIX] 记录的"VCO 不锁定→I2C 从未发出→整条链路无图"根因，当时的结论是改用旁路）。仿真 `clock.fdc` 里 `clk_50m` 是按 25MHz 输入 ÷2 描述的，而综合后 `place_route/clock_utilization.txt` 显示它仍由 `ov5640_clk/u_gpll` 的 CLKOUT0 驱动（该 pll_inst 接了 22 个负载）。**`clk_50m` 在 `bitstream_2026-09-13_final/top_timing_summary_after_hold_fix.txt` 中 0 次出现**——即它没有传播成时钟约束，"All Constraints Met" 不覆盖这个域。`top.v` 里 `clk_50m_rst_n` 接的是 `locked`（注释标 `[48M]`，而 IP 申请值写的 50）。动这个域之前先把 IDP/仿真模型和设计目标对齐。
- **无版本控制**：仓库没有 git。历史靠 `.bak_<tag>` / `.bak2` 副本文件和 `bitstream_<日期>*/` 目录保留，改文件前请沿用这个约定先备份。

## 文档索引（改敏感区前先读）

- `DOC/交付说明_OV5640_QT显示_2026-09-13.md` — **最新交付说明**：NPU 删除、I2C 时钟域根因、诊断寄存器表、MSI 风暴修复、已知野场问题
- `DOC/FPGA_RK3568_传输协议_v1.md` — 地址映射/寄存器表（含实现状态列）/通道定义/点亮流程/运维发现/已定位未修缺陷
- `DOC/RK3568_新比特流点亮指南.md` — 板上点亮分步流程与排障分界
- `DOC/性能调优记录表.md` — 基线资源/时序/用时 + 调优纪律（**单变量**）
- `DOC/夜间优化报告.md` — 性能扫描结论、死宏清单、编译时间对比
- `DOC/预处理IP集成指南.md` — preprocess 接入 top.v 的接线方法
- `DOC/NPU图像处理一致性验证报告.md` — NPU 算子位精确契约（NPU 已归档，保留作参考）
- `sim/preprocess/README.md` — 仿真契约与历史 bug 表（含 9 条回归价值记录）
- `_attic/任务0_清理报告.md` — 工程瘦身记录与死文件判定方法
