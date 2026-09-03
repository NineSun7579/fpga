# 仓库知识图谱

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual refresh after removal of obsolete camera project

当前产品边界只有三个方向：DDR3、PCIe 和双 OV5640 HDMI。目标开发板为紫光盘古100Pro，器件为 `PG2L100H-6IFBG484`，PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。

## 系统入口

- DDR3：`ddr3_test/ddr3_test/`
- PCIe：`pcie_dma_test_100h/`
- 双 OV5640：`59_top_dual_ov5640_hdmi/`（当前仅文档型产品边界）
- 公共仿真库脚本：`scripts/compile_simlib.tcl`、`scripts/compile_simlib.ps1`

## 关键文档

- `TODO.md`：任务队列与验收门槛
- `docs/BOARD_IDENTITY.md`、`docs/BOARD_INPUT_REQUEST.md`：板级事实和外部输入
- `docs/SIMULATION_READINESS_MATRIX.md`：Questa 四级仿真状态
- `docs/PDS_TCL_ENTRYPOINT_INVENTORY.md`：PDS Tcl 入口分类
- `docs/CONSTRAINT_EXCEPTION_INVENTORY.md`：约束例外清单

## 验证边界

运行态、仿真库、日志、波形、许可证配置和本机安装路径不得进入版本库。PCIe 已有项目内 Questa 归档；DDR3 和双 OV5640 仍需建立项目级自检入口。静态门禁不替代 PDS、Questa、STA、SDF、位流或实板验证。

## [操作指南]

执行跨模块任务前，先阅读 `arch/systems.md`、`arch/dependencies.md`、`arch/test_coverage.md`、`hotspots/git_forensics.md` 和 `concepts/domains.md`。
