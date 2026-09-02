# 系统边界

generated_by: nexus-mapper
verified_at: 2026-09-02
provenance: manual refresh from tracked tree

## DDR3

活动目录 `ddr3_test/ddr3_test/`，含 PG2L100H 目标的 PDS 入口、DDR3 IP 和板级证据。项目自有有限 BIST 与四级仿真尚未完成。

## PCIe

活动目录 `pcie_dma_test_100h/`，含 PDS 构建、约束、项目内 Questa 行为/链路/后级 smoke。活动 IP 元数据仍需与 PG2L100H 目标闭合。

## 双 OV5640 HDMI

活动目录 `59_top_dual_ov5640_hdmi/`，目前只含 README 和板级证据清单。RTL、IP、FDC、PDS、TB 必须在输入冻结后选择性导入。

## 公共边界

根脚本负责静态结构、敏感差异、仿真归档和约束清单门禁；不得读取或上传许可证实际值。
