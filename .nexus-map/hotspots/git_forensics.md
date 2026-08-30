> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: `git status`, `git log`, current worktree, and static project audit

# Git Forensics

## 当前基线

- 分支为 `main`。
- 根提交为 `1a2d493`，保存三个原始工程、已有 PDS 产物和整改文档。
- CI-2 板级证据清单完整性门禁已作为提交 `677808d` 落地；当前 HEAD 累计 40 个提交，本次 `.nexus-map` 尚未提交，提交后需再次校正计数。样本仍不足以计算可信的 churn、共同变更或历史热点。

## 人工高关注区

以下仅来自当前缺陷证据，不是 Git 统计热点：

- `41_ov7725_hdmi/rtl/ov7725_hdmi.v`：视频链路顶层、跨域控制和复位组合点。
- `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`：O0-A CDC/RDC 事实、旧/新 STA 映射和后续整改契约的首要证据；O1-B 不得顺带修改该结构。
- `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`：O1-A 的 39 条告警归属、38 条确定修复、`mem_a` H3/O1-C 阻断、隐式网络和 serializer reset 契约的首要证据。
- `41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md`：记录 O2-A 契约、O2-B 否决/回退、动态门控路线否决、`CLKOUT3=65.0026 MHz/+0.192 ns` 唯一待验证候选，以及 O2-D1-G 的 `/5` generated-clock、`HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`、reset 分权、首个 TMDS symbol 和 O2-D2 一次性停止条件的首要证据。
- `41_ov7725_hdmi/rtl/ov7725_dri/ov7725_dri.v`、`rtl/ddr3_ctrl_top/ddr3_ctrl_top.v`、`rtl/ov7725_hdmi.v`、`rtl/hdmi_top/serializer_10_to_1.v`、`rtl/hdmi_top/dvi_transmitter_top.v`：O1-B 的 38 条确定修复保留；O2-B 对 `dvi_transmitter_top.v` 的失败实验已完整回退，O2-D1-R 已完成，O2-D1-G 仅收口契约，用户审核前不得再修改 serializer RTL。
- `41_ov7725_hdmi/scripts/build.tcl`：固定 16 RTL、4 IDF、1 FDC 和 PG2L100H 器件目标的七阶段相对路径实现定义。
- `41_ov7725_hdmi/scripts/check_build.ps1`：严格模式因负时序返回非零；baseline 模式只证明产物与流程可重复，并明确标记不可发布。
- `41_ov7725_hdmi/rtl/ddr3_ctrl_top/ctrl_fifo.v`：`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和跨两侧复位分发点。
- `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`：时钟、CDC 例外和板级 I/O 约束入口。
- `ddr3_test/ddr3_test/scripts/build.tcl`：当前临时 bring-up 的可重复七阶段实现定义，仍依赖厂商 `test_ddr` 而非产品顶层。
- `ddr3_test/ddr3_test/scripts/check_build.ps1`：严格模式拦截 7 类已知阻断；baseline 放行只证明历史设计可重复实现，不表示可发布。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`：存在 BIST error-data 位宽不匹配及后续 dangling cleanup，是当前严格 gate 阻断项。
- `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 与 `.../example_design/rtl/test_ddr.v`：D3-0 已完成活动 IP、非标准 AXI-like 握手和 `I_ips_ddr_top` board wrapper 边界评审；D3-A 按审核后的契约实现，接口语义、地址单位或层级变化即停止并重新审核。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_main_ctrl_v1_0.v`、`axi_bist_top_v1_0.v` 与旧 `ddr3_test_top_tb.v`：D2 已确认其持续运行、无稳定 done 契约、端口失配及外部仿真依赖；均保持厂商原样，只作为静态证据。
- `ddr3_test/ddr3_test/rtl/ddr3_bringup_top.sv`、`ddr3_test/ddr3_test/rtl/ddr3_finite_bist.sv`：D2 规划的项目自有实现热点，当前文件尚不存在，D3 未审核前不得标记为已实现。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`：UART2APB 隐式 `rxd/txd` 连接与 PCIe DMA 集成入口。
- `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`：PCIe 专用资源、复位和普通 I/O 约束入口。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`、`pcie_dma_test_100h/ipcore/pcie_test/pcie_test.idf`：H2-A 顶层 x2/lane、UART2APB 隐式端口及 IDF/PDS 器件不一致的首要证据；H2-A 只读，不修改 RTL/IDF/FDC。
- `scripts/check_repo_consistency.ps1`：CI-0/CI-1/CI-2 仓库级静态门禁入口；除根文档、构建入口和仿真矩阵外，现强制检查三项目板级证据清单、统一章节、项目关键词和 README 链接。当前退出码为 0，但不能替代 PDS、STA、板级审核或仿真。
- `scripts/compile_simlib.tcl`、`scripts/compile_simlib.ps1`：S0-1 参数化 Pango USIM/VSIM 编译入口；支持模拟器、库类型、family、语言、PDS/仿真器路径与输出目录覆盖，并校验工具、退出码、`E:` 记录和库目录。当前因缺少 `vsim.exe`/`vlog.exe`/`vlib.exe` 未执行实际库编译。
- `docs/SIMULATION_READINESS_MATRIX.md`：三项目 S1/S2/S3 项目级资产缺口、厂商示例边界、四级共同门槛和依赖顺序的首要证据；当前矩阵仍在工作区，HEAD 提交分析计数保持 27。
- `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`：S0 复核确认存在的唯一已发现实现工具；外部仿真器可执行文件缺失是当前动态验证阻塞点。

## 后续更新

只有积累足够多、内容独立的提交后，才适合增加真实 churn 与共同变更分析。后续仍按 TODO 队列保持独立批次：S0-1、H0/H1/H3、单次 O2-D2、D3-A/B/C、H2-B、S1/S2/S3，以及 O1-C/O3/O2-C/O4 最终闭环；用户审核或外部资料未到位时不修改对应功能 RTL/IP/约束。
