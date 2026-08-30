> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`, `docs/SIMULATION_READINESS_MATRIX.md`, `scripts/check_repo_consistency.ps1`, `scripts/compile_simlib.tcl`, `scripts/compile_simlib.ps1`
- evidence_gap: 三项目均已建立 SP6.4 可重复全流程与严格/baseline gate 证据；2026-08-30 S0 复核仅确认 `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe` 存在，PATH、`C:/questasim64/win64` 和常见 ModelSim/QuestaSim 目录均未找到 `vsim.exe`、`vlog.exe`、`vlib.exe`，因此动态仿真及 USIM/VSIM 编译仍阻塞。
- responsibility: 定义 PDS 2022.2-SP6.4 的实现流程、ModelSim/QuestaSim 四级仿真流程及三工程整改门槛。
- s0_environment_review: `2026-08-30`；PDS shell 为唯一已发现工具，仿真器安装后才允许执行 `compile_simlib` 并编译 USIM/VSIM。
- s0_0_status: completed_read_only_environment_review; ModelSim/QuestaSim 安装与 USIM/VSIM 编译仍待外部环境
- s0_1_status: parameterized_entry_committed; library_compilation_blocked_external
- s0_1_entry: `scripts/compile_simlib.ps1` 参数化 Simulator（ModelSim/QuestaSim）、Library（USIM/VSIM/BOTH）、Family、Language、PdsBin、SimulatorExecPath 与 OutputDirectory，并通过环境变量调用 `scripts/compile_simlib.tcl` 的 PDS `compile_simlib`；默认输出 `build/simlib`，工作目录 `build/pds-simlib`，日志 `build/logs/compile-simlib.log`。入口不再定义仿真器预检绕过参数。
- s0_1_gate: 调用 PDS 前无条件检查 `pds_shell.exe`、Tcl 入口和 `vsim.exe`/`vlog.exe`/`vlib.exe`；任一缺失立即非零失败。PDS 后检查退出码、日志 `^E:` 及所选 `usim`/`vsim` 库目录存在。
- s0_1_result: `compile_simlib.ps1` 与 `check_repo_consistency.ps1` AST 错误数均为 0，CI-0 门禁退出 0；默认运行因 `C:/questasim64/win64/vsim.exe` 缺失而在 PDS 前返回 1，未执行实际 USIM/VSIM 编译。
- ci_0_status: committed_as_85d9b64
- ci_0_scope: 检查根指南/TODO/VSCS、三个项目 README、`build.tcl`、`run.ps1`、`check_build.ps1`、顶层声明、七阶段入口、可配置 PDS 路径、进程退出码、显式 baseline 开关、产物/时序检查接口、`build/` 忽略与未跟踪生成物状态；拒绝活动 Tcl 的 `simulate` 命令和反斜杠绝对路径。
- ci_0_result: `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`；三个项目 README 缺口已修正，全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- ci_2_status: committed_as_677808d
- ci_2_scope: 为 OV7725、DDR3、PCIe 配置板级证据清单路径和项目关键词；要求三个项目 README 链接对应清单；要求清单包含“当前工程事实”“必须提供的资料”“关闭条件”三个统一章节，PCIe H2-A 清单已按此结构统一。
- ci_2_result: 2026-08-30 在 HEAD `677808d` 复验 `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`。
- ci_2_boundary: 只验证清单文件、章节结构、关键词与 README 导航存在；不验证原理图/BOM/板卡实物，不解除 H0/H1/H2/H3 外部阻断，也不替代 PDS、STA、SCBV 或仿真。
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
- ci_0_boundary: 仅为仓库结构与文档静态一致性门禁，不启动或替代 PDS 构建、STA、项目严格 gate 或四级仿真。
- simulation_readiness_status: read_only_matrix_complete_in_worktree; project_level_tb_filelist_do_missing_for_all_three_projects
- simulation_asset_boundary: `ipcore/`、`ip_core/`、`ip_backup/` 内的 DDR3、PLL、FIFO 和 PCIe RC/EP testbench/filelist/DO 均为厂商示例，只能作为模型与接口参考；不得改名或直接计入 `ov7725_hdmi`、`ddr3_bringup_top` 或 `pcie_dma_test` 的集成覆盖。
- simulation_common_gap: S1/S2/S3 均缺项目自有集成 TB、相对路径 `.f`/`.do`、唯一 `TEST PASS`、超时/`$fatal`、可靠非零失败退出以及按实际 DUT 层级的 SDF 标注入口。
- next_step: 安装并验证有许可证的 ModelSim/QuestaSim，将实际路径传给 `compile_simlib.ps1`，随后编译 Logos2 USIM/VSIM；只有退出 0、日志无 `E:` 且所选库目录非空后才解除 S0-1 阻断。
- s0_0_recheck: 2026-08-30 再次检查 PATH、`C:/questasim64/win64`、常见安装目录和 `vsim.exe`/`vlog.exe`/`vlib.exe`，仍全部缺失；提交 `ef5cc9a` 仅记录证据，不运行库编译或动态仿真。

## Verilog/SystemVerilog 注释规范

- implementation_status: documented
- code_path: null
- evidence_path: `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`
- evidence_gap: 现有厂商代码和历史 RTL 尚未进行全量合规检查。
- responsibility: 约束后续手写 RTL 的意图、接口、FSM、复位、CDC/RDC 和风险注释。

## OV7725 HDMI 顶层

- implementation_status: implemented_with_timing_failures
- code_path: `41_ov7725_hdmi/rtl/`
- entry_path: `41_ov7725_hdmi/rtl/ov7725_hdmi.v`
- project_path: `41_ov7725_hdmi/prj/ov7725_hdmi.pds`
- constraint_path: `41_ov7725_hdmi/prj/source/ov7725_hdmi.fdc`
- evidence_path: `41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md`, `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`, `41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md`, `docs/IMPLEMENTATION_LOG.md`, `41_ov7725_hdmi/build/logs/pds-gen_bit_stream.log`, `41_ov7725_hdmi/build/pds/report_timing/ov7725_hdmi.rtr`, `41_ov7725_hdmi/scripts/check_build.ps1`
- evidence_gap: O1-B 的 38 条确定修复和七阶段回归已完成，仅剩 `mem_a` 1 条受 H3/O1-C 板级事实阻断；O2-B 已被 Slow/Fast Recovery 否决并回退，旧 baseline/gate 未放宽。O2-D1-R 已精确复现七组失败，Slow/Fast `ddrphy_sysclk → pixel_clk` 均恢复为 `53/53`；O2-D1-G 已冻结实现契约但尚未实现，S0 已确认外部仿真器缺失，用户审核和 QuestaSim/S3 尚未完成，当前结果不可发布。
- responsibility: 将 OV7725 像素流经异步 FIFO 和 DDR3 帧缓存送往 HDMI/TMDS 输出。
- clock_domains: `sys_clk`, `i2c_dri_clk`, `cam_pclk`, `pixel_clk`, `pixel_clk_5x`, `clk_50m/ref_clk`, `ui_clk`
- cdc_findings: `wr_load`/`rd_load` 被多个逻辑独立采样；write FIFO 为 `cam_pclk → ui_clk`，read FIFO 为 `ui_clk → pixel_clk`
- rdc_findings: 两个异步 FIFO 的帧复位从单一源域同时驱动两侧；`ddr3_init_done` 和组合顶层复位未逐域同步释放
- build_inputs: 16 个手写 RTL、4 个活动 IDF、1 个顶层 FDC；器件固定为 `Logos2 / PG2L100H / FBG484 / -6`
- build_status: O2-D1-R 已从空 `build/` 完成 SP6.4 七阶段且日志无 `^E:`；baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 后返回 0，严格 gate 仍返回 1，五类产物非零并继续标记不可发布
- timing_findings: O2-D1-R 报告中 Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均为 `53/53`，Removal 均为 `0/53`；53 个 endpoint 分类为 `26+8+17+1+1`。O2-B 的 `54` 来自 video-driver endpoint 从 17 增至 18；新增 serializer reset 同步器属于另一 clock pair，不修改旧 baseline
- artifact_evidence: synthesis netlist `6,873,482` bytes; PNR netlist `11,604,756` bytes; SDF `8,898,464` bytes; `.sbit` `3,791,112` bytes; `.bin` `3,789,476` bytes
- rtl_hygiene_findings: 39 条 `Verilog-2019` 中 38 条确定性告警已在 O1-B 消失；仅保留活动 DDR3 IP `mem_a[13:0]` 与顶层/FDC `mem_a[14:0]` 冲突的 1 条，综合网表仍将 `mem_a[14]` 绑 0
- rtl_hygiene_result: 已显式声明 `rst_n`、删除无消费者 `sys_init_done`、修复定宽连接，并使用高有效 reset 驱动四个 serializer 内的八个 OSERDES；未修改 `mem_a`、厂商 IP、FDC 或 CDC/RDC
- serializer_reset_contract: O2-A 已完成；O2-B 曾按 `pixel_clk` 两级后级联 `pixel_clk_5x` 两级释放并只驱动八个 OSERDES，但真实 STA 将失败转移到 `OCLKDIV` 的 `pixel_clk_5x → pixel_clk` 并保留慢角 `OCLK` 同域负裕量，因此方案已否决且 RTL 已回退
- remediation_contract: 动态 `GTP_IOCLKBUF` 门控已否决；唯一待验证候选使用 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位控制输出和每 serializer 本地 reset 复制。`pixel_clk` 必须显式且唯一地建模为 `/5` generated clock：源为 `u_pll_clk/clkout1`，目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形 `-edges {1 5 11} -edge_shift {0 0 0}`；master 只能是唯一 `CLKOUT1_Inferred`，旧 `CLKOUT0_Inferred` 对 pixel 域必须零消费者，divider 不得接 post-buffer。
- reset_state_contract: `HARD_HOLD`（`!sys_rst_n || !pll_lock` 异步保持，清 divider/pixel/business/四路本地 serializer reset 与计数）→ `QUALIFY`（连续 4 个 `control_clk` 周期）→ `ARM`（释放 `/5`、pixel 同步释放、encoder 强制 `CTRLTOKEN0` 条件，3 个 pixel 周期 warm-up 后 `arm_req` 双触发器同步）→ `SER_RELEASE`（下一个 control 周期清除四个本地 reset，驻留 2 个完整 control 周期）→ `RUN`（撤销 encoder 强制）。计数表示已完成周期且饱和，阈值统一使用 `N-1`。
- reset_ownership: `sys_rst_n` 下降或 `pll_lock` 丢失可异步回 `HARD_HOLD`；普通 video/business reset 只能撤销 RUN 并重新 warm-up，不得组合异步驱动 OSERDES 本地 reset；`ddr3_init_done` 不得参与 hard reset、QUALIFY、ARM、OSERDES reset 或状态转移，后续仅作为同步业务 enable/status；FIFO reset/flush 保留给 O2-C2。
- first_valid_tmds_symbol: 首个有效 symbol 定义为 serializer reset 下降后、首个 `OCLKDIV` 上升沿采入的四路同时确定的完整 TMDS 并行字，而非首个活动视频像素；RUN 至少延后两个 control 周期，确保该 symbol 完整串行发送。
- o2d2_stop_conditions: O2-D2 仅一次、经用户审核后执行；generated-clock 对象为 0/多对象、源计数非 1、自动/显式重名、waveform 不符、divider 取 post-buffer、任一八 OSERDES endpoint 的 Slow/Fast Recovery/Removal 未全覆盖或为负、出现新 baseline 失败签名、PDS/gate/产物失败，均立即停止并完整回退，不得扫描第二相位或新增 waiver。
- next_step: O2-D1-G 已完成，等待用户书面审核后单次执行 O2-D2；H3 与 O2-D2 闭合后按 O1-C → O3-A → O2-C1 → O2-C2 → O3-B → O4 推进。O2-D2 不扫描第二相位、不增加 waiver，失败即完整回退。
- high_attention: `i2c_dri_clk` 逻辑生成时钟、`cam_pclk`/DDR `ui_clk`/`pixel_clk` 间业务 CDC、FIFO 分侧复位，以及 `ddr3_init_done` 参与的复位释放。

## DDR3 外层工程

- implementation_status: bringup_full_implementation_baseline
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/build/logs/pds-gen_bit_stream.log`, `ddr3_test/ddr3_test/build/pds/report_timing/test_ddr.rtr`, `ddr3_test/ddr3_test/scripts/check_build.ps1`
- evidence_gap: SP6.4 全流程、STA、综合网表、PNR 网表、SDF 和位流已验证；严格 gate 因 7 类已知阻断返回 1，显式 baseline 放行返回 0 但不可发布。D2 与 D3-0 只读契约决策已完成，但项目自有有限 BIST 顶层尚未实现；D3-A/B/C 仍待用户审核，板级批准参数清单、产品功能和四级仿真仍未验收。
- responsibility: 当前以厂商 `test_ddr` 作为临时 DDR3 board bring-up 顶层；后续必须明确真正产品顶层和板级功能范围。
- d3_0_read_only_review: `2026-08-30` 已确认活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`；公开端口包含 `ddr_init_done`、`core_clk` 和自定义 AXI-like AW/W/AR/R 接口。`test_ddr.v` 的物理 board wrapper 实例名 `I_ips_ddr_top` 必须保持不变。
- d3_0_status: completed_read_only_review; D3-A implementation pending user review
- d3_0_handshake_contract: 写地址以 `axi_awvalid && axi_awready` 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读请求以 `axi_arvalid && axi_arready` 接受，核心用 `axi_rvalid`/`axi_rlast` 返回且没有 `axi_rready`。D3-A 按该非标准 AXI-like 契约实现；若 IP 重生成后语义、地址单位或层级变化则停止并重新审核。
- d3_0_boundary: 只更新文档和评审事实；D3-0 不修改 RTL、活动 IP、FDC/RCF 或构建脚本。
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
- evidence_gap: 两个项目自有 RTL 文件尚未创建；QuestaSim 缺失，行为级、综合后和 PNR 后仿真均未执行；D3-A/B/C 尚待用户审核与实现。
- responsibility: 在不修改厂商 `test_ddr`、持续运行 BIST 和旧 testbench 的前提下，提供有限、确定且可由 CI 判定的 DDR3 写读比较测试。
- transaction_contract: 16 个单 beat 写读比较 pair；控制器地址 `0x0..0x78`、步长 8；每 pair timeout 4096 周期；整次 run timeout 131072 周期。
- result_contract: 稳定公开 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs`，并提供首错地址/期望值/实际值等首错信息。
- ownership_boundary: 厂商 `ip_core/ddr3/**` 保持原样；新增项目自有 RTL 必须遵循根目录 VSCS。
- next_step: 等待用户审核 D3-0 握手语义与顶层边界后，按 D3-A → D3-B → D3-C 实现骨架、16 个有限 pair 与七阶段 PDS 回归；保持 `I_ips_ddr_top` 和厂商 `ip_core/ddr3/**` 原样

## DDR3 IP 示例

- implementation_status: implemented_example_only
- code_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/`
- entry_path: `ddr3_test/ddr3_test/ip_core/ddr3/example_design/rtl/test_ddr.v`
- project_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/ddr3.pds`
- evidence_path: `ddr3_test/ddr3_test/ip_core/ddr3/pnr/place_route/test_ddr_timing_summary_after_hold_fix.txt`
- evidence_gap: 外层重建已生成当前 `test_ddr` 的 PNR 网表与 SDF，但示例 testbench 仍与顶层失配，SDF 尚未由外部仿真器标注验证，板级 I/O 时序覆盖不足。
- responsibility: 厂商 DDR3 Controller/PHY 的参考写读测试设计，不等同于外层产品工程。

## PCIe DMA 顶层

- implementation_status: implemented_with_known_functional_gap
- code_path: `pcie_dma_test_100h/hdl/`
- entry_path: `pcie_dma_test_100h/hdl/pcie_dma_test.v`
- project_path: `pcie_dma_test_100h/pcie_dma_test.pds`
- constraint_path: `pcie_dma_test_100h/fdc/pcie_dma_test.fdc`
- evidence_path: `pcie_dma_test_100h/place_route/pcie_dma_test_timing_summary_after_hold_fix.txt`
- evidence_gap: 新 SP6.4 全流程、STA、PNR 网表、SDF 和位流已生成；顶层仍无四级集成仿真，UART2APB 的隐式 `rxd/txd` 连接中 `rxd` 被绑 0，SCBV 未配置，关键外部端口仍未约束；H2-A 还发现活动 IDF 为 PG2L50H 而 PDS 目标为 PG2L100H。
- responsibility: 集成 PCIe x2 IP、DMA、RAM/FIFO 与 UART2APB 管理路径。
- build_entry: `pcie_dma_test_100h/scripts/run.ps1`
- build_definition: `pcie_dma_test_100h/scripts/build.tcl`
- build_gate: `pcie_dma_test_100h/scripts/check_build.ps1`
- h2a_read_only_evidence: `2026-08-30`；顶层端口为 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；FDC 映射 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。
- h2a_status: completed_read_only_evidence_matrix; H2-B 仍待板级资料和审核
- h2a_constraint_gaps: FDC 未提供 lane 极性、板级拓扑、I/O delay 或 SCBV；`pcie_test.idf` metadata 为 `Logos2 / PG2L50H / FBG484 / -6`，与 PDS `Logos2 / PG2L100H / FBG484 / -6` 冲突。
- h2a_uart_gap: UART2APB 使用隐式 `rxd/txd` 网络，当前 `rxd` 被绑 0；该功能缺口不因 PDS/STA 成功而关闭。
- h2a_boundary: H2-A 仅更新文档、证据矩阵与 IP 重生成契约，不修改 RTL、IDF 或 FDC。
- h2b_stop_conditions: 板级 lane 极性/拓扑、I/O delay 或 SCBV 缺失，IDF/PDS 器件元数据不一致，或 UART2APB `rxd/txd` 归属未决时，H2-B 不得收紧 gate；不得用 waiver 掩盖缺口。
- next_step: H2-B 等待 H0/H2 板级资料、UART 保留/删除决策与 PG2L100H IP 重生成审核；证据齐全后再统一更新 IDF、约束和精确 gate，在此之前保持 PCIe RTL/IDF/FDC 只读
