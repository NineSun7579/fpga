> generated_by: Codex manual bootstrap
> verified_at: 2026-09-03
> provenance: `git status`, `git log`, current worktree, and static project audit

# Git Forensics

## 当前基线

- 分支为 `main`。
- 根提交为 `1a2d493`，保存三个原始工程、已有 PDS 产物和整改文档。
- CI-1 至 CI-7、H2-B0、CI-8A、PCIe S2-A、板级证据门禁、仿真器复核、M0/M1、main OV5640 M2-A/M3-A 与 DDR3 M2-B1 均按小批次记录；样本仍不足以计算可信的 churn、共同变更或历史热点。

## 人工高关注区

以下仅来自当前缺陷证据，不是 Git 统计热点：

- `docs/OV5640_TARGET_SCOPE.md`：摄像头产品目标、OV7725 legacy 边界与 C0/C1/C2/C3/S3 关闭条件的首要入口；参考工程未审计前不得先改名或迁移 RTL。
- `main_ov5640_pcie/rtl/rgb565_word_packer.sv`、`ov5640_dvp_rgb565_word_pipeline.sv`：M3-A 内部 128-bit 图像字布局与控制事件边界；后续 DDR3/PCIe 适配不得直接把 `word_keep` 当作厂商 AXIS `tkeep` 或主机字节序。
- `main_ov5640_pcie/rtl/rgb565_word_skid_buffer.sv`、`main_ov5640_pcie/rtl/ov5640_dvp_rgb565_cdc_staging_pipeline.sv` 及对应 TB：M3-B overflow 合同的首要入口。评审必须保持“保留前缀、丢弃当前帧余量、唯一空载错误中止、原帧尾与中止排队后从后续 frame_start 恢复、此前新帧整帧跳过”五项语义。word skid 专项 Questa 证据已扩展为 526 ns，并覆盖满队列同拍 pop/push、原 `frame_end` 与 abort 入队同拍、连续两个损坏帧各唯一 abort 且顺序正确、drop/abort 状态异步复位；联合 DVP→CDC 证据保持 2863 ns，压力输出 20 个 beat（含 1 个中止）并恢复 2 个 beat。不得将其升格为真实 DDR3/PCIe/主机或板级时序证明。
- `main_ov5640_pcie/tb/tb_ov5640_ddr3_pcie_loopback.sv`、PCIe MWR bridge/path 及对应脚本：M3-B 行为级闭环和请求字段保持入口。当前 Questa 证据覆盖 21 条压力记录、末尾唯一 abort、恢复帧、abort 与恢复 payload 共用 `0x104c`，以及 bridge busy 时预取下一记录仍保持当前事件元数据；loopback/path/bridge 分别为 3844/115/76 ns。必须保留模型边界，禁止升格为真实 DDR3、PCIe 链路/主机或板级时序证明。
- `main_ov5640_pcie/rtl/rgb565_axis4_frame_commit.sv`、`rgb565_axis4_frame_readout_gate.sv`、`rgb565_axis4_committed_pcie_mwr_path.sv` 及对应 TB/脚本：M3-B 已提交帧回送切片的首要入口。评审必须保持“frame commit 只形成提交决策；错误描述符由 readout gate 产生单周期 `drop_frame_pulse`，不打开 DDR 读窗口、不产生 MWR；后续正常帧恢复；payload/空载帧尾地址为 `0x2000/0x2004`；运行中复位清除旧状态”语义。Questa 证据分别为 210/171/366 ns，均 0 error/0 warning、唯一 `TEST PASS`。不得将其升格为真实 DDR3 读地址、DDR3 持久化、vendor IP、PCIe TLP/DMA/链路、主机内存或板级时序证明。
- `41_ov7725_hdmi/rtl/ov7725_hdmi.v`：OV7725 legacy 视频链路顶层、跨域控制和复位组合点，只能作为 OV5640 C2 的候选结构参考。
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
- `scripts/check_repo_consistency.ps1`：CI-0 至 CI-9、M0 与 M3-A 静态门禁入口；现强制三项目 README/板级证据包含已批准的器件事实，以 XML 解析确认活动 PCIe IDF 为 PG2L50H，并保护 OV7725 四个 canonical IDF 哈希及 M3-A 迁移契约。当前退出码为 0，但不能替代 PDS、STA、板级审核或仿真。
- `scripts/check_sensitive_diff.ps1`、`docs/SENSITIVE_DIFF_GATE.md`：CI-9 当前树与 PR 差异门禁。68 个 tracked 日志中的 143 处本机许可证引用已替换为 `<license-path>`；评审重点是 `-FullTree`、merge-base diff、严格占位符白名单和“不改写历史”的边界。
- `scripts/compile_simlib.tcl`、`scripts/compile_simlib.ps1`：S0-1 参数化 Pango USIM/VSIM 编译入口；支持模拟器、库类型、family、语言、PDS/仿真器路径与输出目录覆盖，并校验工具、退出码、`E:` 记录和库目录。Questa Sim-64 2021.1 下 Logos2 USIM/VSIM 均已完成实际编译验证。
- `docs/PDS_TCL_ENTRYPOINT_INVENTORY.json`、`scripts/check_pds_tcl_entrypoints.ps1`：CI-7 的 13 项 tracked Tcl 分类与入口事实；仅三个 `scripts/build.tcl` 属于项目 `run.ps1` 链，其余为公共支持、历史 GUI、厂商内部或厂商仿真脚本。canonical 只接受 PG2L50H/FBG484/-6 且无绝对路径，历史/厂商脚本不得作为器件或 STA 证明。
- `pcie_dma_test_100h/doc/H2B_BASELINE_GATE.md`、`H2B_BASELINE_FINGERPRINT.json`：H2-B0 的 16 签名/42 原始记录精确多重集和五个变异 fixture；metadata 漂移永久硬失败。partial run 复用旧 full-build 证据的风险已由 PCIe CI-8A 关闭。
- `pcie_dma_test_100h/scripts/pds_sources.f`、`build_provenance.ps1`、`doc/CI8A_BUILD_PROVENANCE.md`：CI-8A 的 37 HDL 单一清单、43 输入/7 证据 SHA-256 manifest 与 32 位 run_id 状态机；partial/failed 和输入/产物漂移均拒绝。CI-8B 必须等待 DDR3/OV7725 canonical 升格并分别实现。
- `pcie_dma_test_100h/tb/tb_pcie_dma_test.sv`、`tb/pcie_test_smoke_model.sv`、`sim/behav.f`：S2-A 项目级行为 smoke 的真实顶层、自检 TB、受控 PCIe 边界、DMA RAM init include 与 37 HDL 嵌套 filelist。`sim/behav.f` 另补仿真所需 `ips2l_pcie_apb_cross_v1_0.v`，不得为此修改由 IDF 管理实现侧源的 `scripts/pds_sources.f`；TB 全局复位实例保持 `GRS_INST`。评审时禁止把受控 link 当作 LTSSM/TLP/DMA 或板级链路证据。
- `pcie_dma_test_100h/scripts/run_behav.do`、`scripts/check_sim.ps1`、`scripts/check_link_sim.ps1`、`scripts/run.ps1`：S2-A/S2-B 静态门禁当前通过；S2-A 历史动态运行保留唯一 `TEST PASS`。当前动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS；旧日志不得复用。
- `docs/SIMULATION_READINESS_MATRIX.md`：三项目 S1/S2/S3 项目级资产缺口、厂商示例边界、四级共同门槛和 PG2L50H 迁移依赖的首要证据。
- `scripts/compile_simlib.ps1`、`scripts/compile_simlib.tcl`：Questa Sim-64 2021.1 下 Logos2 USIM/VSIM 均已验证；VSIM 编译退出 0、日志无 `^E:`、库目录非空，`V_BUF` 原语 smoke 运行 `2 ns` 且 0 errors/0 warnings、唯一 `TEST PASS`。三个项目真实网表/SDF 仍待验证。

## 后续更新

只有积累足够多、内容独立的提交后，才适合增加真实 churn 与共同变更分析。main OV5640 M3-A 已关闭采集、灰度处理到 128-bit 内部图像字的板级无关行为切片；后续必须分别审核 CDC/FIFO、DDR3、PCIe/主机协议与 PDS/STA，且不得把历史仿真日志冒充当前结果。
