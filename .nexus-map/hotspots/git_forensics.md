> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: `git status`, `git log`, current worktree, and static project audit

# Git Forensics

## 当前基线

- 分支为 `main`。
- 根提交为 `1a2d493`，保存三个原始工程、已有 PDS 产物和整改文档。
- CI-1 至 CI-7、H2-B0、板级证据门禁、仿真器复核、M0/M1、M2-A 与 M2-B1 均按小批次记录；H2-B0 后累计 59 个提交。样本仍不足以计算可信的 churn、共同变更或历史热点。

## 人工高关注区

以下仅来自当前缺陷证据，不是 Git 统计热点：

- `41_ov7725_hdmi/rtl/ov7725_hdmi.v`：视频链路顶层、跨域控制和复位组合点。
- `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`：O0-A CDC/RDC 事实、旧/新 STA 映射和后续整改契约的首要证据；O1-B 不得顺带修改该结构。
- `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`：O1-A 的 39 条告警归属、38 条确定修复、`mem_a` H3/O1-C 阻断、隐式网络和 serializer reset 契约的首要证据。
- `41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md`：记录旧 PG2L100H O2-A/O2-B/O2-D1 证据、`/5` generated-clock、状态机和 reset 分权。状态机与验证纪律可复用，但 `+0.192 ns` 裕量、七组时序指纹和 endpoint 数必须在 PG2L50H 新 baseline 后重新审核。
- `41_ov7725_hdmi/doc/M3A_IP_MIGRATION_AUDIT.md`：记录四 IP 活动/安装版本断层、`IPCompiler 0037/0057` 探针、GUI new-instance/staging-only 规则、DDR3/PLL 隐藏派生参数、FIFO 资源上限、RCF 对象命中缺口和 canonical 升格条件。
- `41_ov7725_hdmi/rtl/ov7725_dri/ov7725_dri.v`、`rtl/ddr3_ctrl_top/ddr3_ctrl_top.v`、`rtl/ov7725_hdmi.v`、`rtl/hdmi_top/serializer_10_to_1.v`、`rtl/hdmi_top/dvi_transmitter_top.v`：O1-B 的 38 条确定修复保留；O2-B 对 `dvi_transmitter_top.v` 的失败实验已完整回退，O2-D1-R 已完成，O2-D1-G 仅收口契约，用户审核前不得再修改 serializer RTL。
- `41_ov7725_hdmi/scripts/build.tcl`：仍固定 16 RTL、4 个 PG2L100H 活动 IDF、1 FDC 和 PG2L100H 工程目标；M3 必须用 SP6.4 为 PG2L50H 重生成四个 IP 并重建 baseline，禁止手改 IDF。
- `41_ov7725_hdmi/scripts/check_build.ps1`：严格模式因负时序返回非零；baseline 模式只证明产物与流程可重复，并明确标记不可发布。
- `41_ov7725_hdmi/rtl/ddr3_ctrl_top/ctrl_fifo.v`：`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和跨两侧复位分发点。
- `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`：时钟、CDC 例外和板级 I/O 约束入口。
- `ddr3_test/ddr3_test/scripts/build.tcl`：当前临时 bring-up 定义仍指向 PG2L100H 活动 IP/FDC/RCF；活动 `ip_core/ddr3/ddr3.idf` 为 SP6.4/PG2L100H，canonical `ip_core/ddr3/pnr/ddr_test.fdc` + `ddr3.rcf`，外层 `ip_core/ddr_test.fdc` 仅作旧参考。M2 必须用 SP6.4 重生成 PG2L50H 输入，旧 SP6.1 50H backup 仅作参数和差异证据。
- `ddr3_test/ddr3_test/scripts/regenerate_ip.ps1`、`doc/M2_IP_REGENERATION.md` 与 `doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`：M2-B1 已证明 `DEVICE_100H_EN` 是器件派生参数，禁止直接 `-device` 覆盖 100H IDF；脚本现以 SP6.1 50H seed 做参数一致性验证后交由 SP6.4 重生成，输出 flag=false、PPLL `TRUE/CLKOUT4` 且不改 canonical。审查重点已转为 wrapper `21 → 26` 端口、DDR PHY/filelist/IDF 差异与 FDC 28 项 pin 差异；原理图/BOM 缺失时禁止升格。
- `ddr3_test/ddr3_test/scripts/check_build.ps1`：严格模式拦截 7 类已知阻断；baseline 放行只证明历史设计可重复实现，不表示可发布。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`：存在 BIST error-data 位宽不匹配及后续 dangling cleanup，是当前严格 gate 阻断项。
- `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 与 `.../example_design/rtl/test_ddr.v`：CI-6 已保护旧活动 IP 的非标准 AXI-like 握手和 `I_ips_ddr_top` 边界；PG2L50H 重生成后必须重跑门禁并重新审核 D3-A。
- `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_main_ctrl_v1_0.v`、`axi_bist_top_v1_0.v` 与旧 `ddr3_test_top_tb.v`：D2 已确认其持续运行、无稳定 done 契约、端口失配及外部仿真依赖；均保持厂商原样，只作为静态证据。
- `ddr3_test/ddr3_test/rtl/ddr3_bringup_top.sv`、`ddr3_test/ddr3_test/rtl/ddr3_finite_bist.sv`：D2 规划的项目自有实现热点，当前文件尚不存在，D3 未审核前不得标记为已实现。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`：UART2APB 隐式 `rxd/txd` 连接与 PCIe DMA 集成入口。
- `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`：PCIe 专用资源、复位和普通 I/O 约束入口。
- `pcie_dma_test_100h/hdl/pcie_dma_test.v`、`pcie_dma_test_100h/ipcore/pcie_test/pcie_test.idf`：活动 PCIe IDF、build/PDS/gate 和新主产物已统一匹配 PG2L50H；M1 还依据 PDS 模板将 HSSTLP 资源迁移到 `HSSTLP_292_612`，RTL/FDC 其余内容继续受板级审核约束。
- `scripts/check_repo_consistency.ps1`：CI-0 至 CI-6、M0 与 M3-A 静态门禁入口；现强制三项目 README/板级证据包含已批准的器件事实，以 XML 解析确认活动 PCIe IDF 为 PG2L50H，并保护 OV7725 四个 canonical IDF 哈希及 M3-A 迁移契约。当前退出码为 0，但不能替代 PDS、STA、板级审核或仿真。
- `scripts/compile_simlib.tcl`、`scripts/compile_simlib.ps1`：S0-1 参数化 Pango USIM/VSIM 编译入口；支持模拟器、库类型、family、语言、PDS/仿真器路径与输出目录覆盖，并校验工具、退出码、`E:` 记录和库目录。当前因缺少 `vsim.exe`/`vlog.exe`/`vlib.exe` 未执行实际库编译。
- `docs/PDS_TCL_ENTRYPOINT_INVENTORY.json`、`scripts/check_pds_tcl_entrypoints.ps1`：CI-7 的 13 项 tracked Tcl 分类与入口事实；仅三个 `scripts/build.tcl` 属于项目 `run.ps1` 链，其余为公共支持、历史 GUI、厂商内部或厂商仿真脚本。canonical 只接受 PG2L50H/FBG484/-6 且无绝对路径，历史/厂商脚本不得作为器件或 STA 证明。
- `pcie_dma_test_100h/doc/H2B_BASELINE_GATE.md`、`H2B_BASELINE_FINGERPRINT.json`：H2-B0 的 16 签名/42 原始记录精确多重集和五个变异 fixture；metadata 漂移永久硬失败。partial run 复用旧 full-build 证据的风险已转入 CI-8 provenance/freshness。
- `docs/SIMULATION_READINESS_MATRIX.md`：三项目 S1/S2/S3 项目级资产缺口、厂商示例边界、四级共同门槛和 PG2L50H 迁移依赖的首要证据。
- `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`：S0 复核确认存在的唯一已发现实现工具；外部仿真器可执行文件缺失是当前动态验证阻塞点。

## 后续更新

只有积累足够多、内容独立的提交后，才适合增加真实 churn 与共同变更分析。后续按 M1 PCIe 50H 重建 → M2 DDR3 50H IP/FDC/RCF → M3 OV7725 四 IP/新 baseline 推进；M2/M3 后分别重新审核 D3-A/O2-D2。S0 与其余板级证据持续并行，缺少一手资料时不修改对应功能 RTL或物理约束。
