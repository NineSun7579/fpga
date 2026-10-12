# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

紫光 Logos2 FPGA 工程（PDS 2022.2-SP6.4，器件 PG2L100H-6FBG484）：双目 OV5640 摄像头（FMC）+ 自研 NPU(YOLO 加速器) + PCIe(对接 RK3568 主机) + 预处理 IP（锐化/中值/时域卡尔曼/Sobel）。

**无 git 仓库** —— 历史靠 `.bak*` 文件、`_attic/` 和按日期命名的 `bitstream_*` 快照保护。

## 目录结构

- `project/` — **主工作区**，详见 `project/AGENTS.md`
  - `project/project.pds` — 主 PDS 工程文件（s-expression 格式）
  - `project_kf/project.pds` — 卡尔曼滤波并行工程
  - `project_build/project.pds` — 构建专用工程副本
  - `source/` — 全部 RTL（子目录：ov5640/npu/axi_crossbar/axi_dma/pcie_dma/pcie2npu/HDMI/preprocess/constraints/sfp）
  - `ipcore/` — PDS 生成 IP（DDR3/PCIe/PLL），**保护勿动**
  - `sim/` — ModelSim 仿真（preprocess/ov5640_tb/npu/cdc_pixel_repro/dma_timeout_repro 等）
  - `DOC/` — 协议、集成指南、调优记录、YOLO26 参数清单、验证报告
  - `_attic/` — 归档，**勿删**，可整体回滚
  - `tools/` — 上板探针/补丁脚本
- `sim/ov5640_tb/` — 工作区根级 ModelSim TB（`tb_cam_sharpen.v` + `run_sharpen.do`）

## 关键命令

### 仿真

```bash
# 预处理 IP 回归（从 project/ 起，默认 64x36，需 ModelSim + Python3）
cd project/sim/preprocess && ./run_all.sh [W H]

# 锐化 TB（从工作区根起，ModelSim 默认 C:\modeltech64_10.6e\win64）
cd sim/ov5640_tb && vsim -c -do run_sharpen.do

# 卡尔曼滤波仿真（PowerShell 直调，规避 WSL bash）
C:\modeltech64_10.6e\win64\vlib.exe work
C:\modeltech64_10.6e\win64\vlog.exe <sources>
C:\modeltech64_10.6e\win64\vsim.exe -c -do "run -all; quit"
C:\Users\NineSun\anaconda3\python.exe project/sim/ov5640_tb/vip_kf_compare.py
```

### 编译

```bash
# pds_shell 批处理编译（约 33 分钟全流程；启动前确认无 pds_shell/pds.exe 进程）
cd project && C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe \
  -project <absolute_path>/project/project/project.pds \
  -run pnr \
  -work_dir <absolute_path>/project/project

# 重编译前清空产物目录
rm -rf project/{compile,synthesize,device_map,place_route}
```

产物在 `project/{synthesize,place_route}/`。全流程 ≈33 分钟（synth 5.8 + pnr 23.6）。

### 可达性检查

```bash
cd project && python _attic/reachability_check.py top
```

## 硬性陷阱（违反必出事故）

1. **GBK 编码**：`source/` 下多数 `.v` 含 GBK 中文注释。git bash grep 对这些文件**静默漏匹配**（纯 ASCII 内容也漏）。**一切文本搜索/替换用 Python 字节级操作**（全工作区适用，含根 `sim/`）。

2. **PDS 单实例**：两个 pds_shell 并发写同一 project 目录 → DB 相位冲突（Flow-0013）。启动前 `tasklist` 确认无 pds_shell/pds.exe；重编译前清空 `project/{compile,synthesize,device_map,place_route}`。

3. **PDS 打开时勿改工程**：GUI 退出会回写 project.pds，覆盖你的编辑。改 project.pds/移动源文件前必须先关 PDS。

4. **多个 .pds 并存**：`project/project/`（主）、`project/project_kf/`、`project/project_build/` 各自独立，确认目标后再 `-project`；产物目录跟工程走，勿混用。

5. **模块重名**：PDS 报 duplicate module。新增 RTL 前用重名扫描确认（曾因 sync_fifo 与 `npu/common/sync_fifo.v` 撞名返工；preprocess 的 FIFO 已更名为 `prep_sync_fifo`）。

6. **删源文件三件套**：移动文件 + 删 project.pds 中对应 `(_file ...)` 块 + 可达性复查（`reachability_check.py`）。死文件判定必须做字节级反引号引用扫描——config.v 88 个宏中 27 个是死宏（CONV33_*/FOCUS_* 全系等），改了无效。

7. **free_clk 是根时钟**（PLL + DDR3 ref_clk，25MHz@V4/LVCMOS15），约束里 UNUSED=TRUE 是正常的 IO 属性，不是未使用。

8. **相对路径依赖**：`sim/ov5640_tb/run_sharpen.do` 以 `../../project/source/...` 相对路径编译源码，**勿移动工作区根与 project/ 的相对位置**。

## 架构铁律

- **NPU 恒喂 RAW 帧**；preprocess IP 输出只走显示/判别旁路（0x0A000000），与 YOLO 链路解耦。
- **NPU_LAYER 同步三处**：`npu_cdc_top.v`、`pcie2npu/instruction_buf.v`、`pcie2npu/npu_ctl.v`（当前 88，YOLO26 定型后按 DOC/YOLO26_FPGA参数变更清单.md 改）。
- **preprocess 流水线契约**：s_valid 单拍语义（禁止原地保持）；每帧 H*W+1 像素（帧尾 1 哑像素）；sobel/align16 移位结构必须严格同构（含中心列 fire 条件）。
- **无符号运算先判大小再相减**（色化引擎曾因 g>r 下溢误判红色）；`{2'b0,w}` 是拼接不是 2×。
- **PCIe 通路**：相机→DDR(S01)→主机读(S00)；FPGA 主动推送 DMA 在 `pcie_fifo.v`（TX FIFO 数据源=axi_rdata rid==0）。

## 地址映射（FPGA 视角）

| 地址 | 大小 | 内容 | 写者 | 读者 |
|---|---|---|---|---|
| 0x02000000 | 1MB/层 | NPU 权重 | RK3568 | NPU |
| 0x06000000 | ≤2MB | NPU 输入帧 (RAW) | CH1 注入 DMA / 采集 | NPU |
| 0x07000000 | 64KB | NPU 推理结果 | NPU | RK3568 |
| 0x0A000000 | 2×帧 | 处理图/实时帧 ping-pong | 采集/预处理 | CH0 DMA |
| 0x20000000+offset | - | 寄存器窗口（AXI-Lite）| RK3568 | FPGA 各模块 |
| 0x40000000 | - | NPU 指令队列基址 | RK3568 | NPU |
| 0x50000000 | - | 层数寄存器 | RK3568 | NPU |

## 寄存器访问

- **BAR1 DMA 描述符寄存器**（直写，只写）：BAR1+0x100/0x110/0x120/0x1E0/0x200
- **AXI 窗寄存器**（经 DMA 间接访问）：把 0x1E0 设为目标 AXI 地址即可读写
  - XDMA_ACK: 0x20000000+0x00
  - CAM_EN: 0x20000000+0x40
  - CAM_ADDR_1/2: 0x20000000+0x80/0xC0
  - PREP_CTRL: 0x20000000+0x100（预处理控制寄存器）
  - PREP_THR/SIZE/LANE/INJ_*/BUTTON/LED/LANE_RESULT/TS: +0x104~0x17C
  - CAM3/CAM4 I2C: 0x20000400/0x20000600（SCCB 主机直通寄存器）

详见 `project/DOC/FPGA_RK3568_传输协议_v1.md`。

## 约束文件（5 个 .fdc）

位于 `project/source/constraints/`：

- `clock.fdc` — 时钟约束
- `cdc.fdc` — 跨时钟域约束
- `ddr3.fdc` — DDR3 控制器约束
- `ov5640.fdc` — 相机接口约束
- `pcie.fdc` — PCIe 接口约束
- `sfp.fdc` — SFP 光口约束

## 关键文档

改敏感区前先读：

- `project/AGENTS.md` — 工程级陷阱、架构铁律、文档索引
- `project/_attic/任务0_清理报告.md` — 工程瘦身记录与判定方法
- `project/DOC/夜间优化报告.md` — 性能扫描结论（v5 推荐配置、NPU Fmax 数据、死宏清单）
- `project/DOC/性能调优记录表.md` — 基线资源/时序/用时 + 调优纪律（单变量）
- `project/DOC/FPGA_RK3568_传输协议_v1.md` — 地址映射/寄存器表/通道定义
- `project/DOC/预处理IP集成指南.md` — preprocess 接入 top.v 的接线方法
- `project/DOC/KF_上板验证报告.md` — 卡尔曼滤波（2026-09-25，最新基线：cam1 KF 滤波 + cam2 旁路对照）
- `project/sim/preprocess/README.md` — 仿真契约与历史 bug 表

## 仿真验证规范

- **ModelSim 默认路径**：`C:\modeltech64_10.6e\win64`（可用环境变量 `MODELSIM_BIN` 覆盖）
- **Python 依赖**：Python 3（用于 golden 生成）
- **预处理 IP 回归**：7 用例 (rgb2gray/colorize/sobel_edge/preprocess_top×4模式/button_debounce/prep_regs)，支持分辨率参数化（64x36 快速/640x360 完整/1920x1080 压力）
- **卡尔曼滤波仿真**：PowerShell 直调 ModelSim（规避 WSL bash GBK 问题），Python 黄金比对
- **覆盖点**：定向激励、功能覆盖、断言（FIFO 无溢出、无 X 传播、valid-only 契约）

## 资源与时序基线

- **资源**：LUT 11096/66600 (16.66%)、FF 11928、DRM 25.5/155、APM 196
- **时序**：pclk setup WNS +1.102ns、hold +0.288ns、0 failing endpoints
- **编译用时**：synth 5.8min + pnr 23.6min ≈ 33min 全流程
- **NPU Fmax**：≈174MHz（提频至 180MHz 需先收敛路径）
- **推荐配置**：v5 (MAX_IN=416 + CONV11_PAR=4)

## 工具链

- **FPGA 工具**：Pango Design Suite (PDS) 2022.2-SP6.4
- **仿真工具**：ModelSim 10.6e
- **Python**：Anaconda3（路径：`C:\Users\NineSun\anaconda3\python.exe`）
- **目标器件**：紫光 Logos2 PG2L100H-6FBG484

## 注意事项

- 新比特流验证前先看 `project/DOC/KF_上板验证报告.md`（最新基线与隔离开关 `KF_EN`/`KF_RD_EN`）
- 修改 RTL 后必须运行对应的 ModelSim 回归
- 修改约束后必须全流程编译验证时序
- 上板前必须确认资源占用未超限且时序全过
- 备份重要比特流到 `bitstream_*` 目录（按日期命名）
