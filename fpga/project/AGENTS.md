# AGENTS.md — ov56401 工程指南

紫光 Logos2 FPGA 工程（PDS 2022.2-SP6.4，器件 PG2L100H-6FBG484）：OV5640 摄像头 + 自研 NPU(YOLO 加速器) + PCIe(对接 RK3568 主机) + 预处理 IP。

## 目录

- `project/project.pds` — **工程文件**（s-expression），登记全部源文件/IP/约束。GUI 打开的是它。
- `source/` — 全部 RTL。子目录：`ov5640`(相机)、`npu`(YOLO NPU)、`axi_crossbar`、`axi_dma`、`pcie_dma`、`pcie2npu`、`HDMI`、`constraints`(5 个 .fdc)、`preprocess`(**新 IP**：rgb2gray/colorize/sobel/lane_detect/prep_regs 等 9 模块)
- `ipcore/` — PDS 生成 IP（DDR3/PCIe/PLL），**保护勿动**
- `sim/preprocess/` — ModelSim 仿真（TB×6 + Python golden + run_all.sh）
- `DOC/` — 协议 v1、集成指南、调优记录表、YOLO26 参数清单、夜间优化报告
- `_attic/` — 归档（28 个已删文件、基线报告、pds_shell 脚本），**勿删**，可整体回滚

## 关键命令

```bash
# ModelSim 回归（需 Python3；ModelSim 默认 C:\modeltech64_10.6e\win64，可用 MODELSIM_BIN 覆盖）
cd sim/preprocess && ./run_all.sh [W H]      # 默认 64x36；640 360 为全分辨率

# 可达性/死文件检查
python _attic/reachability_check.py top

# pds_shell 批处理编译（勿与 GUI 同时；详见陷阱）
cd project && C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe \
  -project <abs>/project/project.pds -run pnr -work_dir <abs>/project
```

全流程 ≈33 分钟（synth 5.8 + pnr 23.6）。产物在 `project/{synthesize,place_route}/`。

## 硬性陷阱（违反必出事故）

1. **GBK 编码**：source 下多数 .v 含 GBK 中文注释。git bash grep 对这些文件**静默漏匹配**（纯 ASCII 内容也漏）。一切文本搜索/替换用 Python **字节级**操作。
2. **PDS 单实例**：两个 pds_shell 并发写同一 project 目录 → DB 相位冲突（Flow-0013）。启动前 `tasklist` 确认无 pds_shell/pds.exe；重编译前清空 `project/{compile,synthesize,device_map,place_route}`。
3. **PDS 打开时勿改工程**：GUI 退出会回写 project.pds，覆盖你的编辑。改 project.pds/移动源文件前必须先关 PDS。
4. **模块重名**：PDS 报 duplicate module。新增 RTL 前用重名扫描确认（曾因 sync_fifo 与 `npu/common/sync_fifo.v` 撞名返工）。
5. **删源文件三件套**：移动文件 + 删 project.pds 中对应 `(_file ...)` 块 + 可达性复查（`reachability_check.py`）。死文件判定必须做字节级反引号引用扫描——config.v 88 个宏中 27 个是死宏（CONV33_*/FOCUS_* 全系等），改了无效。
6. **free_clk 是根时钟**（PLL + DDR3 ref_clk，25MHz@V4/LVCMOS15），约束里 UNUSED=TRUE 是正常的 IO 属性，不是未使用。

## 架构铁律

- **NPU 恒喂 RAW 帧**；preprocess IP 输出只走显示/判别旁路（0x0A000000），与 YOLO 链路解耦。
- **NPU_LAYER 同步三处**：`npu_cdc_top.v`、`pcie2npu/instruction_buf.v`、`pcie2npu/npu_ctl.v`（当前 88，YOLO26 定型后按 DOC/YOLO26_FPGA参数变更清单.md 改）。
- preprocess 流水线契约：s_valid 单拍语义（禁止原地保持）；每帧 H*W+1 像素（帧尾 1 哑像素）；sobel/align16 移位结构必须严格同构（含中心列 fire 条件）。
- 无符号运算先判大小再相减（色化引擎曾因 g>r 下溢误判红色）；`{2'b0,w}` 是拼接不是 2×。
- PCIe 通路：相机→DDR(S01)→主机读(S00)；FPGA 主动推送 DMA 在 `pcie_fifo.v`（TX FIFO 数据源=axi_rdata rid==0）。

## 文档索引（改敏感区前先读）

- `_attic/任务0_清理报告.md` — 工程瘦身记录与判定方法
- `DOC/夜间优化报告.md` — 性能扫描结论（v5 推荐配置、NPU Fmax 数据、死宏清单）
- `DOC/性能调优记录表.md` — 基线资源/时序/用时 + 调优纪律（单变量）
- `DOC/FPGA_RK3568_传输协议_v1.md` — 地址映射/寄存器表(+0x100~0x17C)/通道定义
- `DOC/预处理IP集成指南.md` — preprocess 接入 top.v 的接线方法
- `sim/preprocess/README.md` — 仿真契约与历史 bug 表
