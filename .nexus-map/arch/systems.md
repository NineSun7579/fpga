> generated_by: Codex manual bootstrap
> verified_at: 2026-09-02
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

- repository_delivery: PR #27 已于 2026-09-02 合并；活动目标保持 `PG2L100H-6IFBG484` / 紫光盘古100Pro。下一工作批次以新堆叠 PR 推进，不把合并 PR 的历史 50H 证据当作当前发布证据。

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`, `docs/SIMULATION_READINESS_MATRIX.md`, `scripts/check_repo_consistency.ps1`, `scripts/compile_simlib.tcl`, `scripts/compile_simlib.ps1`
- evidence_gap: PCIe S2-E run `927abae8ed7d40aeb5d6f706b3723e0a` 已动态通过。S2-F 工程已在项目内归档并成功标注 SDF，但当前 run `7fc77a7ec8db479db7332e8037426d6c` 因 2 个 timing error、GLS/STA 冲突和 `V_FFASYN` 负时序语义不完整而 blocked。PCIe link/DMA、H2-B1、实板、发布及 DDR3/OV5640 套件仍未完成。
- responsibility: 定义 PDS 2022.2-SP6.4 的实现流程、ModelSim/QuestaSim 四级仿真流程及三工程整改门槛。
- s0_environment_review: `2026-09-01`；Questa Sim-64 2021.1 最小 SystemVerilog已通过，PDS SP6.4 Logos2 USIM/VSIM 均已成功编译。
- s0_0_status: historical_environment_review_superseded_by_actual_questa_execution
- s0_1_status: completed; logos2_usim_and_vsim_compiled; minimal_post_primitive_smoke_passed
- s0_1_entry: `scripts/compile_simlib.ps1` 参数化 Simulator（ModelSim/QuestaSim）、Library（USIM/VSIM/BOTH）、Family、Language、PdsBin、SimulatorExecPath 与 OutputDirectory，并通过环境变量调用 `scripts/compile_simlib.tcl` 的 PDS `compile_simlib`；默认输出 `build/simlib`，工作目录 `build/pds-simlib`，日志 `build/logs/compile-simlib.log`。入口不再定义仿真器预检绕过参数。
- s0_1_gate: 调用 PDS 前无条件检查 `pds_shell.exe`、Tcl 入口和 `vsim.exe`/`vlog.exe`/`vlib.exe`；任一缺失立即非零失败。PDS 后检查退出码、日志 `^E:` 及所选 `usim`/`vsim` 库目录存在。
- s0_1_result: Logos2 VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 目录非空；最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- ci_0_status: committed_as_85d9b64
- ci_0_scope: 检查根指南/TODO/VSCS、三个项目 README、`build.tcl`、`run.ps1`、`check_build.ps1`、顶层声明、七阶段入口、可配置 PDS 路径、进程退出码、显式 baseline 开关、产物/时序检查接口、`build/` 忽略与未跟踪生成物状态；拒绝活动 Tcl 的 `simulate` 命令和反斜杠绝对路径。
- ci_0_result: `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`；三个项目 README 缺口已修正，全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- ci_2_status: committed_as_677808d; expanded_2026-09-02_for_dual_ov5640_document_skeleton
- ci_2_scope: 为 OV7725 legacy、DDR3、PCIe、双 OV5640 四个目录配置板级证据清单路径和项目关键词；要求对应 README 链接清单，并要求清单包含“当前工程事实”“必须提供的资料”“关闭条件”三个统一章节。
- ci_2_result: 2026-08-30 在 HEAD `677808d` 完成原始三目录门禁；2026-09-02 在当前工作树复验双 OV5640 扩展，退出码 0，并输出 `INFO: dual OV5640 C1-A product boundary checked` 与 `INFO: repository consistency gate passed`。
- ci_2_boundary: 只验证四份清单文件、章节结构、关键词与 README 导航存在；双 OV5640 目录仍只有文档骨架，不含 RTL/IP/FDC/TB。不验证原理图/BOM/板卡实物，不解除 H0/H1/H2/H3 外部阻断，也不替代 PDS、STA、SCBV 或仿真。
- ci_3_status: committed_as_5bfaae9
- ci_3_scope: 三项目 README 元数据完整性门禁；除既有 PDS 版本和顶层检查外，按项目特征要求 README 明确记录器件目标、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断。
- ci_3_result: 2026-08-30 在 HEAD `5bfaae9` 复验 `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`。
- ci_3_boundary: 只验证 README 中已有事实的可追溯表达和项目入口，不验证器件/板级参数真实性，不解除 H0/H1/H2/H3、S0 或功能实现阻断，也不替代 PDS、STA、SCBV 或仿真。
- ci_4_status: committed_as_66356aa
- ci_4_scope: 三项目 PDS 构建 gate 契约完整性；`run.ps1` 必须检查 PDS 退出码、`^E:` 错误记录和阶段完成标记，`check_build.ps1` 必须覆盖阶段/最终构建入口、时序摘要、`throw` 失败路径、非零产物检查和显式 baseline 开关。
- ci_4_result: 2026-08-30 在 HEAD `66356aa`（44 个 Git 提交）复验 `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`。
- ci_4_boundary: 只验证 gate 代码路径和静态契约存在，不执行或替代真实 PDS、STA、位流生成、严格构建 gate 或外部仿真；baseline 开关仍不得被解释为发布通过。
- ci_5_status: committed_as_5769d8f
- ci_5_scope: 仓库门禁递归解析全部非 `build/`、`.git/` 的 `.ps1` 文件，使用 PowerShell Parser 报告具体语法错误文件、行号和消息。
- ci_5_result: 2026-08-30 当前 HEAD `5769d8f` 上共发现 8 个 PowerShell 脚本，AST 解析错误数为 0；仓库一致性门禁通过。
- ci_5_boundary: 只验证 PowerShell 脚本可解析及错误定位，不执行或替代 PDS、STA、位流生成、ModelSim/QuestaSim 或项目动态仿真。
- ci_6_status: committed_as_a5d1785
- ci_6_scope: 静态交叉核对 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md` 的模块、参数宽度、128-bit 数据、28-bit 地址、`I_ips_ddr_top` 层级、AXI-like 握手字段及 core 不含 `axi_rready`。
- ci_6_result: 2026-08-30 在 HEAD `a5d1785`（52 个 Git 提交）复验仓库一致性门禁、8 个 PowerShell AST 与 `git diff --check` 均通过。
- ci_6_boundary: 仅保护当前 D3-0-R 静态契约不漂移；PG2L50H DDR3 IP/FDC/RCF 重生成后必须重新核对并审核，不能把当前通过解释为新器件实现或动态验证通过。
- ci_7_scope: `docs/PDS_TCL_ENTRYPOINT_INVENTORY.json` 覆盖全部 14 个 tracked Tcl；新增 DDR3 `scripts/build_staging_compile.tcl` 归为非发布 `canonical_support_tool`，逐项记录角色、`set_arch` 次数、器件集合、绝对路径事实和 `run_ps1_entry`。
- ci_7_roles: 角色集合固定为 `canonical_project_build`、`migration_blocked_project_build`、`canonical_support_tool`、`historical_gui`、`vendor_generated_internal`、`vendor_sim_internal`；只有三个项目 `scripts/build.tcl` 可由对应 `run.ps1` 调用。
- ci_7_target_boundary: PCIe `scripts/build.tcl` 已是 `Logos2 / PG2L50H / FBG484 / -6` canonical；OV7725 与 DDR3 `scripts/build.tcl` 仍是 PG2L100H migration-blocked。历史 GUI、厂商内部和厂商仿真脚本的混合器件/绝对路径不构成当前器件或实现证据。
- ci_7_result: 正向 `check_pds_tcl_entrypoints.ps1` 退出 0；删除任一清单项的负向测试退出 1。M2/M3 升格时必须同步清单角色与器件集合。
- h2_b0_scope: PCIe 当前 PG2L50H baseline 将五类问题归一化为 16 个唯一签名、42 次原始记录；baseline 比较完整多重集，新增、消失、改名、share-pin 位置或次数漂移均失败，活动 IDF family/device/package/speedgrade 漂移永久硬失败。
- h2_b0_result: canonical fixture 正向退出 0、strict 退出 1；缺失 UART、重复 UART、Timing 端口改名、share pin 改位和 IDF 改为 PG2L100H 五个变异均退出 1。本批无 RTL、活动 IDF、FDC、厂商 IP 或生成物修改。
- h2_b1_boundary: lane/refclk/PERST#/SCBV/UART/I/O timing 仍需板级资料与决策；H2-B0 不解除发布阻断。
- ci_8_status: PCIe 的 partial/stale evidence 风险已由 CI-8A manifest 关闭；CI-8B 等待 DDR3/双 OV5640 各自 PG2L100H canonical 升格后迁移，不使用时间戳容差或隐式假设。
- ci_8a_status: PCIe provenance pilot completed on 2026-08-31。
- ci_8a_inputs: `scripts/pds_sources.f` 是 37 个 HDL 的单一有序清单；与 `run.ps1`、`build.tcl`、`build_provenance.ps1`、活动 IDF/FDC 等合计形成 43 项 canonical 输入。`run.ps1` 中 build-scoped Questa launcher 属于该输入集合，launcher 逻辑变更必须重新绑定完整构建证据。
- ci_8a_manifest: 每次 build 以 32 位小写十六进制 `run_id` 原子替换固定 `build/provenance/pds-build.json`；状态为 `running/partial/failed/complete`，只有 `complete` 且 `valid=true` 可进入最终 gate。
- ci_8a_binding: 最新 manifest 绑定 43 项输入与 9 项产物；产物包含独立无 SDF 的 PNR 功能网表，以及 timing/SDF/bitstream 证据。
- ci_8a_result: 最新完整 PG2L50H run `9952da4164f040d5924a558baa5cd8ca` 为 `gen_bit_stream/complete/valid=true`，43 inputs/9 artifacts，baseline=0、strict=1；仍不可发布。
- ci_8b_boundary: DDR3 与 `59_top_dual_ov5640_hdmi/` 仅在各自 PG2L50H canonical IP/约束和最终构建入口升格后迁移 provenance；OV7725 legacy 不再升格，也不抽公共模块。
- ci_9_status: 2026-09-01 implemented_and_verified_sensitive_diff_gate
- ci_9_entry: `scripts/check_sensitive_diff.ps1`；契约文档为 `docs/SENSITIVE_DIFF_GATE.md`，并由 `scripts/check_repo_consistency.ps1` 调用规则自检、`-FullTree` 当前树扫描和 PR merge-base 差异扫描。
- ci_9_scope: 全树模式检查当前 tracked/untracked 工作树，PR 模式检查 merge-base 之后的 changed paths 与 added lines；严格占位符白名单之外，拒绝许可证文件名、Windows/UNC/Unix 绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名及 host id。
- ci_9_self_test: 2 个允许新增行、5 个拒绝新增行、1 个允许文件名、1 个拒绝文件名均按预期判定。
- ci_9_result: 68 个 tracked 日志中的 143 处许可证绝对路径已替换为 `<license-path>`；当前树 `-FullTree` 扫描和 PR 差异扫描均通过。
- ci_9_boundary: 保护当前版本并阻止后续重新引入，不读取或输出实际许可证配置；本批不改写 Git 历史，历史清理和任何历史重写必须独立审核。
- ci_10_entry: `.github/workflows/repository-gates.yml`；触发条件为所有 `pull_request`、`main` push 和手动 `workflow_dispatch`。
- ci_10_runner: Windows `pwsh`，job/check 名为 `Static repository gates`；工作流权限仅为 `contents: read`。
- ci_10_checkout: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`（v7.0.1），`fetch-depth: 0`，`persist-credentials: false`。
- ci_10_scope: 只执行根 `scripts/check_repo_consistency.ps1`，不读取 secrets。
- ci_10_boundary: 当前仅记录工作流配置事实；实际远端 check 状态须由对应 PR 运行确认。该 job 不运行或证明 PDS、Questa、STA、SDF、位流或实板通过。
- hardware_target_decision: 用户于 2026-09-02 将三个活动产品项目的开发板名称修正为“紫光盘古100Pro”，目标 FPGA 修正为 `PG2L100H-6IFBG484`；统一 PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。`41_ov7725_hdmi` 仅为 legacy，不属于活动 TODO。
- hardware_identity_boundary: 开发板名称与 FPGA 器件型号是两个独立字段；板名不得替代完整器件料号，工程目录名和历史器件 metadata 也不得反推板名。
- hardware_evidence_status: 当前目标来自 owner 声明，仍须归档当前板卡 FPGA 丝印照片、原理图和 BOM 并交叉核对；关闭前不得授权烧录或实板验收。
- superseded_target_boundary: 此前的 `RK3568+PG2L50H100H / PG2L50H-6IFBG484` 与 PG2L50H staging/build 只保留为历史迁移证据；既有 PG2L100H 资产也必须确认版本、输入、约束和板级匹配后才能恢复为当前 baseline。
- ci_0_boundary: 仅为仓库结构与文档静态一致性门禁，不启动或替代 PDS 构建、STA、项目严格 gate 或四级仿真。
- simulation_readiness_status: Questa 2021.1 tools and Logos2 USIM/VSIM verified; PCIe S2-A controlled smoke, S2-B real RC/EP link and S2-D limited post-synthesis smoke PASS; DDR3 and OV5640 project suites remain pending
- simulation_asset_boundary: `ipcore/`、`ip_core/`、`ip_backup/` 内的 DDR3、PLL、FIFO 和 PCIe RC/EP testbench/filelist/DO 均为厂商示例，只能作为模型与接口参考；不得改名或直接计入 `ov7725_hdmi`、`ddr3_bringup_top` 或 `pcie_dma_test` 的集成覆盖。
- simulation_common_gap: 三个项目的可复现仿真工程分别保留在各自工程内独立 `sim/questa/`，运行态只进入对应 `build/`。PCIe S2-E 已通过；S2-F 已执行但被 GLS/STA 冲突和仿真模型语义阻断。link/DMA、H2-B1、实板与发布仍未关闭。
- next_step: 保持 S2-E 受限覆盖边界；先解决或取得可审核依据处理 S2-F 的 HSST timing-model 冲突，再继续 S2-C DMA。
- s0_0_recheck: 2026-08-30 的未发现仿真器结论已被 2026-09-01 的实际 Questa 执行、USIM 编译与 PCIe S2-A 动态 PASS 取代。

## Verilog/SystemVerilog 注释规范

- implementation_status: documented
- code_path: null
- evidence_path: `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`
- evidence_gap: 现有厂商代码和历史 RTL 尚未进行全量合规检查。
- responsibility: 约束后续手写 RTL 的意图、接口、FSM、复位、CDC/RDC 和风险注释。

## OV7725 HDMI Legacy 顶层

- implementation_status: legacy_evidence_with_timing_failures
- code_path: `41_ov7725_hdmi/rtl/`
- entry_path: `41_ov7725_hdmi/rtl/ov7725_hdmi.v`
- project_path: `41_ov7725_hdmi/prj/ov7725_hdmi.pds`
- constraint_path: `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`
- evidence_path: `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`, `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`, `41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md`, `41_ov7725_hdmi/doc/M3A_IP_MIGRATION_AUDIT.md`, `docs/IMPLEMENTATION_LOG.md`, `41_ov7725_hdmi/build/logs/pds-gen_bit_stream.log`, `41_ov7725_hdmi/build/pds/report_timing/ov7725_hdmi.rtr`, `41_ov7725_hdmi/scripts/check_build.ps1`
- evidence_gap: O1-B 的 38 条确定修复、七阶段回归和 O2-D1-G 契约均只描述 OV7725 legacy，且建立在旧 PG2L100H 目标上。它们不得改名或直接继承为 OV5640 产品实现、板级签核或 S3 结果。
- responsibility: 将 OV7725 像素流经异步 FIFO 和 DDR3 帧缓存送往 HDMI/TMDS 输出。
- clock_domains: `sys_clk`, `i2c_dri_clk`, `cam_pclk`, `pixel_clk`, `pixel_clk_5x`, `clk_50m/ref_clk`, `ui_clk`
- cdc_findings: `wr_load`/`rd_load` 被多个逻辑独立采样；write FIFO 为 `cam_pclk → ui_clk`，read FIFO 为 `ui_clk → pixel_clk`
- rdc_findings: 两个异步 FIFO 的帧复位从单一源域同时驱动两侧；`ddr3_init_done` 和组合顶层复位未逐域同步释放
- build_inputs: 16 个手写 RTL、4 个活动 IDF、1 个顶层 FDC；当前文件仍是旧 `Logos2 / PG2L100H / FBG484 / -6` 基线，已被实物确认否决，目标应迁移到 `Logos2 / PG2L50H / FBG484 / -6`
- m3a_version_gap: 四个活动 SP4.2 IP 与 SP6.4 安装定义均断层：DDR3 `1.12 → 1.10`、PLL `1.3 → 1.5`、rd/wr FIFO `1.8 → 1.10`；隔离探针分别被 `IPCompiler 0037` 和 `IPCompiler 0057` 拒绝，旧 IDF CLI override 与手改版本均禁止。
- m3a_staging_contract: 只允许用 SP6.4 IP Compiler GUI 在 `Logos2/PG2L50H/FBG484/-6` 下创建当前版本的新实例，并只输出 `build/ipgen/pg2l50h/**`；四个 canonical IDF 由仓库门禁做 SHA-256 保护，板级审核前不得升格。
- m3a_derived_parameters: DDR3 必须得到 `DEVICE_100H_EN=false`，PLL 必须得到 `DEVICE_PG2L50H=true`；两个异步混宽 FIFO 必须满足 PG2L50H 的 85 个 DRM36K/170 个 DRM18K 资源上限。
- m3a_constraint_gap: 旧 `ddr3_ip.rcf` 层级与当前集成层级不一致，历史记录只处理 0 条 net；M3-B 已取消，该缺口保留为双 OV5640 新项目必须独立证明 RCF/FDC 对象命中的反例。
- build_status: O2-D1-R 已从空 `build/` 完成 SP6.4 七阶段且日志无 `^E:`；baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 后返回 0，严格 gate 仍返回 1，五类产物非零并继续标记不可发布
- timing_findings: O2-D1-R 报告中 Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均为 `53/53`，Removal 均为 `0/53`；53 个 endpoint 分类为 `26+8+17+1+1`。O2-B 的 `54` 来自 video-driver endpoint 从 17 增至 18；新增 serializer reset 同步器属于另一 clock pair，不修改旧 baseline
- artifact_evidence: synthesis netlist `6,873,482` bytes; PNR netlist `11,604,756` bytes; SDF `8,898,464` bytes; `.sbit` `3,791,112` bytes; `.bin` `3,789,476` bytes
- rtl_hygiene_findings: 39 条 `Verilog-2019` 中 38 条确定性告警已在 O1-B 消失；仅保留活动 DDR3 IP `mem_a[13:0]` 与顶层/FDC `mem_a[14:0]` 冲突的 1 条，综合网表仍将 `mem_a[14]` 绑 0
- rtl_hygiene_result: 已显式声明 `rst_n`、删除无消费者 `sys_init_done`、修复定宽连接，并使用高有效 reset 驱动四个 serializer 内的八个 OSERDES；未修改 `mem_a`、厂商 IP、FDC 或 CDC/RDC
- serializer_reset_contract: O2-A 已完成；O2-B 曾按 `pixel_clk` 两级后级联 `pixel_clk_5x` 两级释放并只驱动八个 OSERDES，但真实 STA 将失败转移到 `OCLKDIV` 的 `pixel_clk_5x → pixel_clk` 并保留慢角 `OCLK` 同域负裕量，因此方案已否决且 RTL 已回退
- remediation_contract: 动态 `GTP_IOCLKBUF` 门控已否决；唯一待验证候选使用 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位控制输出和每 serializer 本地 reset 复制。`pixel_clk` 必须显式且唯一地建模为 `/5` generated clock：源为 `u_pll_clk/clkout1`，目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形 `-edges {1 5 11} -edge_shift {0 0 0}`；master 只能是唯一 `CLKOUT1_Inferred`，旧 `CLKOUT0_Inferred` 对 pixel 域必须零消费者，divider 不得接 post-buffer。
- reset_state_contract: `HARD_HOLD`（`!sys_rst_n || !pll_lock` 异步保持，清 divider/pixel/business/四路本地 serializer reset 与计数）→ `QUALIFY`（连续 4 个 `control_clk` 周期）→ `ARM`（释放 `/5`、pixel 同步释放、encoder 强制 `CTRLTOKEN0` 条件，3 个 pixel 周期 warm-up 后 `arm_req` 双触发器同步）→ `SER_RELEASE`（下一个 control 周期清除四个本地 reset，驻留 2 个完整 control 周期）→ `RUN`（撤销 encoder 强制）。计数表示已完成周期且饱和，阈值统一使用 `N-1`。
- reset_ownership: 旧契约规定 `sys_rst_n`/`pll_lock`、business reset、OSERDES 本地 reset 与 `ddr3_init_done` 分权，FIFO reset/flush 独立处理；O2-C2 已取消，双 OV5640 必须在 C2/C3 重新定义并验证。
- first_valid_tmds_symbol: 首个有效 symbol 定义为 serializer reset 下降后、首个 `OCLKDIV` 上升沿采入的四路同时确定的完整 TMDS 并行字，而非首个活动视频像素；RUN 至少延后两个 control 周期，确保该 symbol 完整串行发送。
- o2d2_stop_conditions: O2-D2 已取消；generated-clock 唯一性、waveform/取点、OSERDES recovery/removal 覆盖与禁止 waiver 的原则仅作为双 OV5640 C2/C3 审核清单。
- next_step: 保留 OV7725 legacy 证据不改名且不再实现；双 OV5640 C0 已完成，只有 C1/H3 输入冻结后，才能于 C2 逐项审核哪些 DDR3/HDMI、CDC/RDC 或复位结构值得重写，新产品 IP/约束必须在 C3 独立建立。

## 双 OV5640 摄像头 HDMI 产品目标

- implementation_status: documented_project_skeleton_blocked_by_c1_h3
- code_path: `59_top_dual_ov5640_hdmi/`（当前无 RTL/IP/FDC/TB）
- evidence_path: `59_top_dual_ov5640_hdmi/README.md`, `59_top_dual_ov5640_hdmi/doc/BOARD_EVIDENCE.md`, `docs/OV5640_TARGET_SCOPE.md`, `docs/OV5640_C0_REFERENCE_AUDIT.md`, read-only `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3`
- product_boundary: 产品固定双 OV5640；`59_top_dual_ov5640_hdmi/` 已建立文档型项目骨架，目标板卡与器件分别为“紫光盘古100Pro”与 `PG2L100H-6IFBG484`。`41_ov7725_hdmi` 及其 `sim/questa/` 只作 legacy。
- reference_top: `top_dual_ov5640_hdmi`；两路独立 SCCB/RESET/PWDN/DVP，每路 960x1080 半幅，双写 DDR3 后组成 1920x1080。
- reference_device_boundary: 参考根 PDS 与 DDR3/PLL/读写 FIFO 为 PG2L100H；PCIe IP 为 PG2L50H 且 BAR1/BAR2 均禁用。参考资产与当前器件系列相同不等于板级适配完成；混合工程、旧阶段产物和参考 README PASS 均不得直接作为紫光盘古100Pro 产品证据。
- c0_boundary: 已完成只读审计；登记 17 个 HDMI 明文 RTL、83 个生成/受保护依赖、4 个 TB、4 个 PCIe video 参考文件、4 个 PG2L100H 生成 IP、FDC/PDS 冲突及 VSCS/CDC/RDC 风险。C0 批次 Import=none，当时未创建产品目录、未运行 PDS/Questa。
- c1_boundary: blocked_by_h3；双 OV5640 数量与 960x1080×2 → 1920x1080 参考组合已知，但模组料号、MCLK、电压、DVP/字节序/帧率、DDR3、HDMI 和板级管脚证据仍需 owner 闭合。
- c2_boundary: 只向 `59_top_dual_ov5640_hdmi/` 选择性导入所需 RTL/IP/约束，建立项目自有双摄 SCCB、复位、采集、DDR3 与 HDMI 边界。
- c3_boundary: 所有 IP/约束按当前 `Logos2 / PG2L100H / FBG484 / -6` 重新审核或生成，完成七阶段 PDS 与严格 gate；旧 100H 产物只有在输入、版本、约束、provenance 与板级证据全部匹配后才能选择性恢复。
- reference_tb_boundary: 参考仓库 4 个 TB 尚未选择性导入；`tb_dual_ov5640_dri.v` force `cam_init_done`，成功字符串不是 canonical `TEST PASS`，不能计为产品自检通过。
- s3_boundary: 可复现仿真源只进入 `59_top_dual_ov5640_hdmi/sim/questa/`，运行态只进入其 `build/`。不导入 `sim_*`、`work`、`.mpf`、`modelsim.ini`、日志、波形、绝对路径生成物或许可证配置。
- next_step: 先用项目内 BOARD_EVIDENCE 关闭 C1/H3 产品输入；随后另开 PR，从 C0 登记候选中选择性导入，并建立 PG2L100H PDS/IP/FDC 与项目内 Questa 入口。
- high_attention: 组合全局复位跨域释放、`ddr3_init_done` CDC/RDC、frame event CDC、FIFO 双侧复位、serializer reset 未使用、1080p/720p 模式冲突、camera init 未纳入系统完成条件，以及关键 FSM/UTF-8/VSCS 缺口。

## DDR3 外层工程

- implementation_status: bringup_full_implementation_baseline
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/scripts/regenerate_ip.ps1`, `ddr3_test/ddr3_test/scripts/build_staging_compile.tcl`, `ddr3_test/ddr3_test/scripts/run_staging_compile.ps1`, `ddr3_test/ddr3_test/scripts/check_staging_compile.ps1`, `ddr3_test/ddr3_test/scripts/check_d3a_staging_contract.ps1`, `ddr3_test/ddr3_test/doc/M2_IP_REGENERATION.md`, `ddr3_test/ddr3_test/doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`, `ddr3_test/ddr3_test/doc/M2B2_STAGING_COMPILE.md`, `ddr3_test/ddr3_test/doc/D3A_PG2L50H_STAGING_REVIEW.md`, `ddr3_test/ddr3_test/build/logs/pds-gen_bit_stream.log`, `ddr3_test/ddr3_test/build/pds/report_timing/test_ddr.rtr`, `ddr3_test/ddr3_test/scripts/check_build.ps1`
- evidence_gap: M2-B2 已证明 PG2L50H staging 可独立 compile，D3-0-M 已证明 core 用户接口不变但物理 wrapper/refclk 变化；canonical IP/FDC/RCF 仍为旧 PG2L100H。仍需 H1 原理图/BOM确认差分 reference clock、`free_clk`、三个状态输出、28 项 FDC pin 差异，再完成 canonical 升格、50H 空目录七阶段、地址/完成语义审核和 D3-A/B/C。
- responsibility: 当前以厂商 `test_ddr` 作为临时 DDR3 board bring-up 顶层；后续必须明确真正产品顶层和板级功能范围。
- hardware_target: 开发板“紫光盘古100Pro” / FPGA `PG2L100H-6IFBG484` / PDS `Logos2 / PG2L100H / FBG484 / -6`
- hardware_target_evidence_conflict: owner 已于 `2026-09-02` 修正板名和目标器件；此前 PR #21 商品截图 `RK3568+PG2L100H` 与旧输入 `PG2L50H-6IFBG484` 保留为历史冲突。当前仍必须以板卡丝印、原理图或 BOM 归档关闭，50H staging 和旧 100H 产物在此之前都只作候选证据。
- board_input_contract: `docs/BOARD_INPUT_REQUEST.md` 统一登记 M0/H1/C1/H3 所需的一手输入及验收方式；资料须附来源、版本或照片编号并映射项目证据表，冻结后才允许 PG2L100H IP/FDC/RCF、PDS 七阶段、STA、Questa 四级仿真和产物器件交叉检查。
- m2_active_input_audit: 活动 `ip_core/ddr3/ddr3.idf` 为 `PG2L100H`、生成器 `2022.2-SP6.4`；canonical FDC/RCF 为 `ip_core/ddr3/pnr/ddr_test.fdc` 与 `ip_core/ddr3/pnr/ddr3.rcf`；`ip_core/ddr_test.fdc` 是旧外层参考，不能直接升格。项目自有 `scripts/build.tcl` 与 `scripts/check_build.ps1` 也仍按 `PG2L100H`，待 50H 资产落地后再修正。
- m2_legacy_50h_audit: `ip_backup/20250108100125/ddr3/ddr3.idf` 为 `PG2L50H`，但生成器是 `2022.2-SP6.1`；仅可作为参数/硬宏差异 oracle，禁止直接恢复或复制到活动输入。
- m2_a_staging: `2026-08-30` 使用 `scripts/regenerate_ip.ps1` 在 `build/ipgen/pg2l50h` 调用 SP6.4 build 146967，目标 `Logos2/PG2L50H/FBG484/-6`，结果 `0 error(s), 0 warning(s)`；canonical IDF SHA-256 保持 `6CB70BF0954100B4797197A47F20496AD74945995E12B30FA040870EE3366C47`。
- m2_b1_derived_parameter: PDS SP6.4 `ui.tcl` 定义 `DEVICE_100H_EN` 为隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`；直接 `-device` 覆盖旧 100H IDF 会错误保留 `true` 并生成 PPLL `FALSE/CLKOUTF` 分支，已明确禁止。
- m2_b1_seed_regeneration: 活动 100H IDF 与 SP6.1 50H seed 的参数仅 `DEVICE_100H_EN` 不同；更新后的 `scripts/regenerate_ip.ps1` 先验证 seed 参数一致，再由 SP6.4 build 146967 重生成，结果 `DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，canonical 哈希保持不变。
- m2_b1_diff: 正确 PG2L50H staging 的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均不同；wrapper 端口 `21 → 26`，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`；FDC 有 28 项 pin 差异。
- m2_b2_entry: `scripts/build_staging_compile.tcl`、`run_staging_compile.ps1` 与 `check_staging_compile.ps1` 是项目内 compile-only 归档；Tcl 角色为 `canonical_support_tool`，不是 canonical project build。
- m2_b2_result: run `1d4b8c264ba940f0bb0e2517b8c36c07` 固定 `Logos2/PG2L50H/FBG484/-6`、18 RTL + 1 IDF、26 端口 `test_ddr`；PDS 退出 0、`E:` 为 0、warning 272，三个 compile 产物非零，四个 canonical 哈希不变。
- m2_b2_negative_gates: 错误目标、零长度核心产物和日志错误记录三项动态负向测试均退出 1；运行证据只保留脱敏许可证类别，不记录本机配置。
- m2_b2_boundary: 不加载 FDC/RCF，不做 synthesize/dev_map/PNR/STA/netlist/SDF/bitstream；不授权 canonical 升格、D3-A、Questa、实板或烧录。
- m2_status: pg2l50h_staging_compile_only_verified_pending_h1_board_evidence_and_canonical_promotion
- m2_gate: 取得原理图/BOM并锁定板级 DDR3 颗粒/组织/PCB 参数 → 审核 28 项 FDC pin 差异及 wrapper/PHY/filelist/IDF → 升格 canonical → 重跑 CI-6 → 清空 `build/` 完成七阶段与器件交叉检查 → 重审 D3-0-R，获审后才可进入 D3-A。M2-B2 仅关闭 compile-only，不授权 canonical 替换、D3-A、仿真或烧录。
- d3_0_read_only_review: `2026-08-30` 已确认活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`；公开端口包含 `ddr_init_done`、`core_clk` 和自定义 AXI-like AW/W/AR/R 接口。`test_ddr.v` 的物理 board wrapper 实例名 `I_ips_ddr_top` 必须保持不变。
- d3_0_status: canonical_core_contract_matches_pg2l50h_staging; physical_wrapper_refclk_change_requires_h1_review
- d3_0_handshake_contract: 写地址以 `axi_awvalid && axi_awready` 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读请求以 `axi_arvalid && axi_arready` 接受，核心用 `axi_rvalid`/`axi_rlast` 返回且没有 `axi_rready`。D3-A 按该非标准 AXI-like 契约实现；若 IP 重生成后语义、地址单位或层级变化则停止并重新审核。
- d3_0_boundary: 只更新文档和评审事实；D3-0 不修改 RTL、活动 IP、FDC/RCF 或构建脚本。
- d3_0_r_port_map: 提交 `2fd7c51` 新增 `D3A_PORT_MAP.md`，CI-6 静态交叉核对 core/wrapper/document；D3-0-M 进一步动态比较 PG2L50H staging，确认 `ddr3.v` whole-file 相同、连接集合相同且无 `axi_rready`。
- d3_0_m_staging_contract: `check_d3a_staging_contract.ps1` 只允许 wrapper 新增 `ref_clk_p/ref_clk_n/pll_lock/ddrphy_cpd_lock/ddr_init_done`、新增 `GTP_INBUFDS`，以及 core `.ref_clk(free_clk)` 改为 `.ref_clk(ref_clk)`；错误 refclk、删除 `ref_clk_n`、core 新增 `axi_rready` 三项负向探针均失败。
- d3_0_m_boundary: D3-0-M 不升格 canonical，不修改 HDL/FDC/RCF，不启动 D3-A 或 Questa；必须先确认差分 DDR reference clock、`free_clk` 职责、三个状态输出及板级管脚。
- provisional_build_entry: `ddr3_test/ddr3_test/scripts/run.ps1`
- build_definition: `ddr3_test/ddr3_test/scripts/build.tcl`
- build_gate: `ddr3_test/ddr3_test/scripts/check_build.ps1`
- provisional_top: `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`
- constraint_baseline: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr_test.fdc`, `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.rcf`
- timing_evidence: `All Constraints Met`; slow-corner setup WNS `0.678 ns`, TNS `0`; hold `0.137 ns`; recovery `4.578 ns`; removal `0.351 ns`
- artifact_evidence: synthesis netlist `5,914,586` bytes; PNR netlist `9,734,239` bytes; SDF `9,130,393` bytes; `.sbit` `3,791,112` bytes; `.bin` `3,789,476` bytes
- strict_gate_blockers: BIST error-data width mismatch, BIST dangling cleanup, `rst_board` share pin, BANKR4 VCCIO 3.3 incompatibility, UART I/O constraints missing, input timing missing, output timing missing
- scbv_status: 当前 DDR3 完整构建日志无 SCBV 命中

## DDR3 有限自检契约

- implementation_status: designed_pending_implementation
- code_path: planned `ddr3_test/ddr3_test/rtl/ddr3_bringup_top.sv`, `ddr3_test/ddr3_test/rtl/ddr3_finite_bist.sv`
- evidence_path: D2 只读评审决策；厂商 `test_ddr`、BIST 和 testbench 源码静态证据
- evidence_gap: 两个项目自有 RTL 文件尚未创建；公共 Questa/USIM/VSIM 已验证，但 DDR3 行为级、综合后和 PNR 后项目仿真均未执行；D3-A/B/C 尚待用户审核与实现。
- responsibility: 在不修改厂商 `test_ddr`、持续运行 BIST 和旧 testbench 的前提下，提供有限、确定且可由 CI 判定的 DDR3 写读比较测试。
- transaction_contract: 16 个单 beat 写读比较 pair；控制器地址 `0x0..0x78`、步长 8；每 pair timeout 4096 周期；整次 run timeout 131072 周期。
- result_contract: 稳定公开 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs`，并提供首错地址/期望值/实际值等首错信息。
- ownership_boundary: 厂商 `ip_core/ddr3/**` 保持原样；新增项目自有 RTL 必须遵循根目录 VSCS。
- next_step: M2-B2/D3-0-M 已确认正确 50H staging 可 compile、core 不变但 wrapper/refclk 变化；先依据原理图/BOM审核差分 reference clock、`free_clk`、三个状态输出和 28 项 FDC pin 差异。升格后重新核对地址单位与 `axi_wready/axi_wusero_last` 完成语义，审核 D3-A 后才可实现项目自有 RTL。

## DDR3 IP 示例

- implementation_status: implemented_example_only
- code_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/`
- entry_path: `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`
- project_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.pds`
- evidence_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/place_route/test_ddr_timing_summary_after_hold_fix.txt`
- evidence_gap: 外层重建已生成当前 `test_ddr` 的 PNR 网表与 SDF，但示例 testbench 仍与顶层失配，SDF 尚未由外部仿真器标注验证，板级 I/O 时序覆盖不足。
- responsibility: 厂商 DDR3 Controller/PHY 的参考写读测试设计，不等同于外层产品工程。

## PCIe DMA 顶层

### H2-M1 PG2L100H IP 恢复边界

- PDS SP6.4 元数据登记 PCIe 1.4/1.5/1.6 支持 `PG2L100H/FBG484`，但实际安装缺少 IP 包与 `index.xml`，故当前不能生成匹配的 100H IP。
- 状态：`blocked_at_ipcompiler_entry`。登记信息仅为候选能力证据，不是可用 IP 或 canonical 恢复证明。
- staging 生成脚本如新增，必须将全部输出隔离到 `build/`，并在门禁中禁止覆盖 canonical IDF/RTL/FDC。

- implementation_status: implemented_with_known_functional_gap
- code_path: `pcie_dma_test_100h/hdl/`
- entry_path: `pcie_dma_test_100h/hdl/pcie_dma_test.v`
- project_path: `pcie_dma_test_100h/pcie_dma_test.pds`
- constraint_path: `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`
- evidence_path: `pcie_dma_test_100h/place_route/pcie_dma_test_timing_summary_after_hold_fix.txt`
- evidence_gap: 活动 `pcie_test.idf`、build/PDS/gate 与产物已统一为 PG2L50H；S2-A/S2-B/S2-D/S2-E 有动态通过证据。S2-F 的 timing netlist/SDF 工程已归档且 SDF 标注成功，但动态运行被 2 个 HSST reset timing error、GLS/STA 冲突和负时序模型语义不完整阻断。`o_trgt1_radm_pkt_halt[2:0]` 已贯通至 hard-IP；DMA、RK3568 实板、电气与板级证据仍缺失。
- responsibility: 集成 PCIe x2 IP、DMA、RAM/FIFO 与 UART2APB 管理路径。
- build_entry: `pcie_dma_test_100h/scripts/run.ps1`
- build_definition: `pcie_dma_test_100h/scripts/build.tcl`
- build_gate: `pcie_dma_test_100h/scripts/check_build.ps1`
- h2a_read_only_evidence: `2026-08-30`；顶层端口为 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；FDC 映射 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。
- h2a_status: completed_read_only_evidence_matrix; H2-B 仍待板级资料和审核
- h2a_constraint_gaps: FDC 未提供 lane 极性、板级拓扑、I/O delay 或 SCBV；`pcie_test.idf` metadata、build/PDS/gate 与新产物已与实物目标 `Logos2 / PG2L50H / FBG484 / -6` 一致，HSSTLP 资源为 PDS 模板指定的 `HSSTLP_292_612`。
- h2a_uart_gap: UART2APB 使用隐式 `rxd/txd` 网络，当前 `rxd` 被绑 0；该功能缺口不因 PDS/STA 成功而关闭。
- h2a_boundary: 器件型号已获用户审核；活动 PCIe IDF 不需仅因型号重生成。M1 已修改项目自有 build/gate，并依据 PDS 模板迁移 HSSTLP 资源后重建生成物；RTL/FDC 其余内容仍受 UART 与板级证据审核约束。
- s2a_status: current_controlled_dynamic_smoke_passed; current_static_gate_passed; current_run_id_add7efa39f644384af9929e8a9366739; exit_0; errors_0; warnings_0; unique_test_pass
- s2a_assets: `sim/questa/tb/tb_pcie_dma_test.sv` 实例化真实 `pcie_dma_test`，全局复位实例名为厂商要求的 `GRS_INST`；`sim/questa/tb/pcie_test_smoke_model.sv` 只替代生成 PCIe IP 边界，两个时序过程恰好使用两个 `always_ff`；项目自有 Questa 定义集中在 `sim/questa/`，其中 `behav.f` 复用 `scripts/pds_sources.f` 的 37 个 canonical HDL，并单独补入仿真所需 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`。`scripts/pds_sources.f` 不修改，因为该源在实现侧由 IDF 管理。
- s2a_log_contract: 每次动态运行使用随机 32 位小写十六进制 `SIM_RUN_ID`；启动器在 `build/sim/launcher/<run-id>/` 创建并显式绑定 run-scoped `modelsim.ini`，PowerShell 通过进程内 `SIM_PROJECT_ROOT` 让 DO 切回项目根；DO 通过 `echo` 将 marker 写入 transcript，并为本次运行创建独立 work。PowerShell 只接受同一 run id marker 恰好一次且 `TEST PASS` 恰好一次，任一失败由 `$fatal` 或非零退出传播。
- s2a_reset_contract: button reset 只拥有 PCIe core/pclk 域；TB 在断言后先确认 ref counter 没有被清零，再跨额外 8 个 refclk 周期确认 link 撤销期间严格保持原值。随后 button reset 完整重新释放并恢复 model link，PERST# 才单独断言以复位两组 LED 域，再独立释放并重新通过 debounce/link 检查。
- s2a_coverage_boundary: 只覆盖产品顶层展开、外部/同步复位、上述 reset ownership、两组 LED 计数门控及 TX/LED 未知态；受控 `smlh_link_up/rdlh_link_up` 只是激励，不证明 LTSSM、TLP、DMA、x2 lane、电气 refclk/PERST# 或 RK3568 Root Complex。
- s2a_dynamic_result: Questa Sim-64 2021.1 当前 run `add7efa39f644384af9929e8a9366739`；运行至 `1476105 ns`；0 errors/0 warnings；唯一 `TEST PASS`；退出码 0；PowerShell 同 run-id/唯一 PASS 门禁通过。
- s2a_questa_archive: 三项目均建立项目内 `sim/questa/` 归档目录；PCIe `.f/.do` 已迁入并由 run/gate 唯一引用。work/vendor library、日志、transcript、波形与 ini 只写入 `build/`；最新 S2-A/S2-B 运行后项目根 `modelsim.ini`、transcript、`vsim.wlf` 计数均为 0。DDR3/摄像头当前仅记录项目入口缺口，不把厂商示例当作集成验证。
- s2a_current_revalidation: 当前版本 S2-A/S2-B 静态 gate 通过，S2-A 动态复验与 S2-B 真实 RC/EP 链路均已通过；S2-A 受控模型仍不证明真实 RC/EP 链路、TLP 或 DMA。
- s2b_static_status: 厂商 RC/项目 EP 双库、双向 x2 lane、双端 link/LTSSM L0、32 周期稳定、6 ms watchdog 和唯一 PASS 静态契约门禁通过。
- s2b_runtime_contract: `work` 与物理 vendor library 均按 `SIM_RUN_ID` 隔离；启动器显式绑定 run-scoped `modelsim.ini`，PowerShell 以进程内 `SIM_PROJECT_ROOT` 将 DO 切回项目根；唯一全局复位实例固定为 `GTP_GRS GRS_INST` 以满足 `GRS_INST.GRSNET`；项目源按 `1ns/10ps` 编译；DO 用 `echo` 将 run marker 写入 transcript。首次 L0 后允许 RC 合法进入 `0x0d` Recovery/速率重训练；TB 在 6 ms 总窗口内寻找连续 32 周期双端 link-up/L0，任何中断将计数归零。
- s2b_dynamic_result: Questa Sim-64 2021.1 run `30bad6e164be4a4b8284a00f1e96bd87` 编译/elaboration 成功；输出唯一 `INFO: S2B_REAL_LINK_UP` 与唯一 `TEST PASS`，Errors 0、Warnings 26、PowerShell 退出 0。
- s2b_coverage_boundary: 只证明仿真模型中的真实 RC/项目 EP 达到连续 32 周期双端 link-up/L0；不证明 DMA、RK3568 实板、协商 x2/5.0 GT/s、PCB/时钟/PERST# 电气或后级网表。
- s2a_rx_halt_contract: `o_trgt1_radm_pkt_halt[2:0]` 接口分别对应 posted、non-posted 与 completion/CPLD halt；当前 bit0/bit1 有效、bit2 源端恒为 0，三位接口路径已由项目顶层贯通活动 `pcie_test` wrapper 至 hard-IP。wrapper 原 3'b0 tie-off 已删除；生成资产重生成会覆盖该修正，静态 gate 检测该已知接口漂移并要求重新审核。
- s2a_warning_status: 原两条未连接端口 warning 已消失；PDS 仍保留 bit2 恒 0 引起的两条优化/清理 warning，不影响 S2-A 受控 smoke。
- s2_next_layers: S2-B 使用厂商 `pango_pcie_top_sim` RC 与项目 `pcie_dma_test` EP 验证真实链路；S2-C 在 S2-B 后执行固定地址/长度/数据的基础 DMA 回读。S2-A 边界模型不得进入这两层或后级网表验收。
- s2c_bar1_staging: `2026-09-01` 静态合同只允许 `BAR1_Enable: false→true`、`BAR1_Size: 256→512 Bytes`，必须保持 `BAR1_MASK_EN=false`、`BAR1_MASK=31'h0`；旧 dry-run 会生成非法 `BAR1_MASK=31'h0(`，已禁止。`check_s2c_bar1` 动态生成/解析 XML，验证唯一差异及 canonical IDF/wrapper SHA 不变；损坏 mask 和缺 `index.xml` 的负向测试均失败。
- s2c_bar1_source_gap: 17 个实时 origin 分支、完整历史/reflog、工作区和 SP6.4 安装均无匹配 PCIe 1.2c `index.xml`。可接受的原始完整实例必须匹配 IP ID `042004`、build `146967`、`PG2L50H/FBG484/-6`；若只能取得新版本，迁移必须另立批次。canonical BAR1 仍关闭，S2-C 未通过。
- s2c_archived_diagnostic: run `d1d25d3f23384590918f26abbfd2e839` 由 RC 主动访问 EP BAR0，在 `710535 ns` 完成写入/读回，0 errors、26 vendor warnings、唯一 `INFO: S2C_DMA_WRITE_READBACK_OK`、唯一 `TEST PASS`、PowerShell 退出 0。该 run 不是 Endpoint 主动 MRd/CplD/MWr DMA 闭环，不解除 BAR1 禁用与 `index.xml` 阻断。
- s2f_archive: `sim/questa/post_pnr_timing.f`、`sim/questa/run_post_pnr_timing.do` 与 `sim/questa/tb/tb_pcie_dma_post_pnr_timing.sv` 保存在 PCIe 项目内；检查入口为 `scripts/check_post_pnr_timing_sim.ps1`，运行库、ini、日志、transcript 与波形只进入 `build/`。
- s2f_pds_provenance: 未重跑 PDS；继续绑定 run `9952da4164f040d5924a558baa5cd8ca`，状态 `complete/valid=true`，43 inputs/9 artifacts。
- s2f_dynamic_result: Questa 当前 run `7fc77a7ec8db479db7332e8037426d6c` 成功标注 SDF 且层级匹配，未对设计信号使用 force/release；自然复现 setup `cnt_rst[5]` 与 hold `rstn_sync` 两个 HSST `ext_rstn_debounce` timing error，Errors 2，独立脚本汇总 5 类失败并退出 1。
- s2f_model_boundary: `vsim-3004` 归属 `V_DRM18K_E1` 的负 `$setuphold/$recrem` 求解失败，`vsim-8756` 归属 `V_FFASYN` 缺少 delayed reference/data copy；slow-corner STA setup/hold 均为正。当前状态为 `blocked_gls_sta_conflict_and_incomplete_negative_timing_semantics`，TB 后续出现 `TEST PASS` 不能覆盖仿真器 error/退出码。
- s2f_negative_timing_diagnostic: Questa 2021.1 最终 run `f79dc238c12949b7b67db2ef0d0ddd0b` 的 level1/2/3 进程均退出 0，SDF/功能/PASS marker 均唯一；3004=`3624/1590/1590`、8756=`1/1/1`、3316/3616=`0/0/0`，三档均保持同一 setup/hold error 与 `Errors=2`。level3 只作非 canonical 诊断；canonical level2 未改，S2-F 仍 blocked。网表、SDF、TB、`V_FFASYN`、`V_DRM18K_E1` SHA-256 已归档；逐档 work/launcher 清理，日志/JSON 只写 `build/`。
- h2b_stop_conditions: 板级 lane 极性/拓扑、I/O delay 或 SCBV 缺失，IDF/PDS 器件元数据不一致，或 UART2APB `rxd/txd` 归属未决时，H2-B 不得收紧 gate；不得用 waiver 掩盖缺口。
- next_step: 保持五类 strict gate 阻断（UART RX tied low、顶层 I/O 未约束、PCIe serial I/O、share pin、SCBV）；S2-F 保持 blocked，取得可信 timing-model/工具解释后再决定修复或重验，同时继续解决 S2-C DMA 前置条件
