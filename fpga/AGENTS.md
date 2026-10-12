# AGENTS.md — ov56401 工作区指南

紫光 Logos2 FPGA 工程（PDS 2022.2-SP6.4，器件 PG2L100H-6FBG484）：OV5640 摄像头（FMC 双目）+ 自研 NPU(YOLO 加速器) + PCIe(对接 RK3568 主机) + 预处理 IP（锐化/中值/时域卡尔曼 `vip_kf`）。无 git 仓库——历史靠 `.bak*` 文件、`_attic/` 和按日期命名的 `bitstream_*` 快照保护。

## 目录

- `project/` — **主工作区，先读 `project/AGENTS.md`**（硬性陷阱、架构铁律、文档索引都在那里）。其内：`project/project/project.pds` 是主 PDS 工程文件；`project_kf/`、`project_build/` 是并行 PDS 工程副本；`source/` 全部 RTL；`ipcore/` 保护勿动；`DOC/` 报告与协议；`_attic/` 归档勿删；`tools/` 上板探针/补丁脚本。
- `sim/ov5640_tb/` — 工作区根级 ModelSim TB（`tb_cam_sharpen.v` + `run_sharpen.do`）。`run_sharpen.do` 以 `../../project/source/...` 相对路径编译源码，**勿移动这两个目录的相对位置**。

## 关键命令

```bash
# 预处理 IP 回归（从 project/ 起）
cd project/sim/preprocess && ./run_all.sh [W H]        # 默认 64x36

# 锐化 TB（从工作区根起，ModelSim 默认 C:\modeltech64_10.6e\win64）
cd sim/ov5640_tb && vsim -c -do run_sharpen.do

# pds_shell 批处理编译（约 33 分钟全流程；详细陷阱见 project/AGENTS.md）
cd project && C:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe \
  -project <abs>/project/project/project.pds -run pnr -work_dir <abs>/project/project
```

KF（卡尔曼）仿真黄金比对走 **PowerShell 直调** ModelSim 的 vlib/vlog/vsim.exe + `C:\Users\NineSun\anaconda3\python.exe project/sim/ov5640_tb/vip_kf_compare.py`，不走 WSL bash。

## 工作区级陷阱

1. **GBK 编码**：source 下多数 .v 含 GBK 中文注释，git bash grep 静默漏匹配——文本搜索/替换一律用 Python **字节级**操作（全工作区适用，含根 `sim/`）。
2. **PDS 单实例**：启动 pds_shell 前确认无 pds_shell/pds.exe 进程；GUI 打开工程时勿改 project.pds（退出会回写覆盖）。
3. **多个 .pds 并存**：`project/project/`（主）、`project/project_kf/`、`project/project_build/` 各自独立，确认目标后再 `-project`；产物目录跟工程走，勿混用。
4. 新比特流验证前先看 `project/DOC/KF_上板验证报告.md`（2026-09-25，最新基线：cam1 KF 滤波 + cam2 旁路对照；隔离开关 `KF_EN`/`KF_RD_EN`）。
