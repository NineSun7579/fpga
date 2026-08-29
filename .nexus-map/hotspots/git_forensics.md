> generated_by: Codex manual bootstrap
> verified_at: 2026-08-29
> provenance: `git status`, `git log`, current worktree, and static project audit

# Git Forensics

## 当前基线

- 分支为 `main`。
- 根提交为 `1a2d493`，保存三个原始工程、已有 PDS 产物和整改文档。
- O1-B 最终批次提交后，仓库累计十二个提交。样本仍不足以计算可信的 churn、共同变更或历史热点；本文件不提供伪统计。

## 人工高关注区

以下仅来自当前缺陷证据，不是 Git 统计热点：

- `41_ov7725_hdmi/rtl/ov7725_hdmi.v`：视频链路顶层、跨域控制和复位组合点。
- `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`：O0-A CDC/RDC 事实、旧/新 STA 映射和后续整改契约的首要证据；O1-B 不得顺带修改该结构。
- `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`：O1-A 的 39 条告警归属、38 条确定修复、`mem_a` H3/O1-C 阻断、隐式网络和 serializer reset 契约的首要证据。
- `41_ov7725_hdmi/rtl/ov7725_dri/ov7725_dri.v`、`rtl/ddr3_ctrl_top/ddr3_ctrl_top.v`、`rtl/ov7725_hdmi.v`、`rtl/hdmi_top/serializer_10_to_1.v`、`rtl/hdmi_top/dvi_transmitter_top.v`：O1-B 已完成 38 条确定修复；其中 serializer 两文件直接关联新增八个 OSERDES recovery 端点，后续 O2-B 必须保持独立边界。
- `41_ov7725_hdmi/scripts/build.tcl`：固定 16 RTL、4 IDF、1 FDC 和 PG2L100H 器件目标的七阶段相对路径实现定义。
- `41_ov7725_hdmi/scripts/check_build.ps1`：严格模式因负时序返回非零；baseline 模式只证明产物与流程可重复，并明确标记不可发布。
- `41_ov7725_hdmi/rtl/ddr3_ctrl_top/ctrl_fifo.v`：`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和跨两侧复位分发点。
- `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`：时钟、CDC 例外和板级 I/O 约束入口。
- `ddr3_test/ddr3_test/scripts/build.tcl`：当前临时 bring-up 的可重复七阶段实现定义，仍依赖厂商 `test_ddr` 而非产品顶层。
- `ddr3_test/ddr3_test/scripts/check_build.ps1`：严格模式拦截 7 类已知阻断；baseline 放行只证明历史设计可重复实现，不表示可发布。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`：存在 BIST error-data 位宽不匹配及后续 dangling cleanup，是当前严格 gate 阻断项。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_main_ctrl_v1_0.v`、`axi_bist_top_v1_0.v` 与旧 `ddr3_test_top_tb.v`：D2 已确认其持续运行、无稳定 done 契约、端口失配及外部仿真依赖；均保持厂商原样，只作为静态证据。
- `ddr3_test/ddr3_test/rtl/ddr3_bringup_top.sv`、`ddr3_test/ddr3_test/rtl/ddr3_finite_bist.sv`：D2 规划的项目自有实现热点，当前文件尚不存在，D3 未审核前不得标记为已实现。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`：UART2APB 隐式 `rxd/txd` 连接与 PCIe DMA 集成入口。
- `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`：PCIe 专用资源、复位和普通 I/O 约束入口。

## 后续更新

只有积累足够多、内容独立的提交后，才适合增加真实 churn 与共同变更分析。O1-B RTL 卫生实现、O2-A/O2-B/O2-C、O1-C `mem_a` 板级决策、D3 有限自检实现和约束修改必须保持独立提交；下一步为 O2-A → O2-B → O2-C，与 D3 一次只进入一条 RTL 泳道。
