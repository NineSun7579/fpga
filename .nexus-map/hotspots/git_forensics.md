> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: `git status`, `git log`, current worktree, and static project audit

# Git Forensics

## 当前基线

- 分支为 `main`。
- 根提交为 `1a2d493`，保存三个原始工程、已有 PDS 产物和整改文档。
- 当前历史只有一个基线提交，尚不足以计算可信的 churn、共同变更或历史热点；本文件不提供伪统计。

## 人工高关注区

以下仅来自当前缺陷证据，不是 Git 统计热点：

- `41_ov7725_hdmi/rtl/ov7725_hdmi.v`：视频链路顶层、跨域控制和复位组合点。
- `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`：时钟、CDC 例外和板级 I/O 约束入口。
- `ddr3_test/ddr3_test/ddr3_test.pds`：外层工程边界不完整。
- `ddr3_test/ddr3_test/ip_core/ddr3/pnr/example_design/rtl/test_ddr.v`：可能升级为板级基线的厂商示例顶层。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`：UART2APB 隐式 `rxd/txd` 连接与 PCIe DMA 集成入口。
- `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`：PCIe 专用资源、复位和普通 I/O 约束入口。

## 后续更新

只有积累足够多、内容独立的提交后，才适合增加真实 churn 与共同变更分析。构建脚本、RTL 功能修改和约束修改应保持独立提交，便于形成可靠历史。
