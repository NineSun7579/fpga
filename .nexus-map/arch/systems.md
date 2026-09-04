> generated_by: Codex manual bootstrap
> verified_at: 2026-09-04
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

## 当前平台覆盖规则

- platform: `RK3568_MES2L100H`（FPGA + ARM）
- fpga: `PG2L100H-6IFBG484`
- pds_target: `Logos2 / PG2L100H / FBG484 / -6`
- status: 当前 100H 目标已写入文档、构建入口和门禁；活动 PCIe IDF 仍为旧 50H metadata，不能验收。
- legacy_boundary: `main_ov5640_pcie` 中 `pg2l50h` 命名的 RTL/TB 仅为旧 50H 行为切片，待 100H 迁移复核。

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`, `docs/SIMULATION_READINESS_MATRIX.md`, `scripts/check_repo_consistency.ps1`, `scripts/compile_simlib.tcl`, `scripts/compile_simlib.ps1`
- evidence_gap: Questa Sim-64 2021.1 工具、Logos2 USIM/VSIM、最小 `V_BUF` 和 PCIe S2-A 历史受控 smoke 均有通过证据；当前 S2-A/S2-B 静态门禁通过，但动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS。摄像头产品目标为 OV5640，C0/C1/C2/C3/S3 尚未完成。
- responsibility: 定义 PDS 2022.2-SP6.4 的实现流程、ModelSim/QuestaSim 四级仿真流程及活动工程整改门槛。
- s0_environment_review: `2026-09-01`；Questa Sim-64 2021.1 最小 SystemVerilog已通过，PDS SP6.4 Logos2 USIM/VSIM 均已成功编译。
- s0_0_status: historical_environment_review_superseded_by_actual_questa_execution
- s0_1_status: completed; logos2_usim_and_vsim_compiled; minimal_post_primitive_smoke_passed
- s0_1_entry: `scripts/compile_simlib.ps1` 参数化 Simulator（ModelSim/QuestaSim）、Library（USIM/VSIM/BOTH）、Family、Language、PdsBin、SimulatorExecPath 与 OutputDirectory，并通过环境变量调用 `scripts/compile_simlib.tcl` 的 PDS `compile_simlib`；默认输出 `build/simlib`，工作目录 `build/pds-simlib`，日志 `build/logs/compile-simlib.log`。入口不再定义仿真器预检绕过参数。
- s0_1_gate: 调用 PDS 前无条件检查 `pds_shell.exe`、Tcl 入口和 `vsim.exe`/`vlog.exe`/`vlib.exe`；任一缺失立即非零失败。PDS 后检查退出码、日志 `^E:` 及所选 `usim`/`vsim` 库目录存在。
- s0_1_result: Logos2 VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 目录非空；最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- ci_0_status: committed_as_85d9b64
- ci_0_scope: 检查根指南/TODO/VSCS、三个项目 README、`build.tcl`、`run.ps1`、`check_build.ps1`、顶层声明、七阶段入口、可配置 PDS 路径、进程退出码、显式 baseline 开关、产物/时序检查接口、`build/` 忽略与未跟踪生成物状态；拒绝活动 Tcl 的 `simulate` 命令和反斜杠绝对路径。
- ci_0_result: `scripts/check_repo_consistency.ps1` 退出码 0，并输出 `INFO: repository consistency gate passed`；三个项目 README 缺口已修正，全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- ci_2_status: committed_as_677808d
- ci_2_scope: 为 DDR3、PCIe 配置板级证据清单路径和项目关键词；要求项目 README 链接对应清单，并要求清单包含“当前工程事实”“必须提供的资料”“关闭条件”三个统一章节。
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
- ci_6_status: committed_as_a5d1785
- ci_6_scope: 静态交叉核对 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md` 的模块、参数宽度、128-bit 数据、28-bit 地址、`I_ips_ddr_top` 层级、AXI-like 握手字段及 core 不含 `axi_rready`。
- ci_6_result: 2026-08-30 在 HEAD `a5d1785`（52 个 Git 提交）复验仓库一致性门禁、8 个 PowerShell AST 与 `git diff --check` 均通过。
- ci_6_boundary: 仅保护当前 D3-0-R 静态契约不漂移；PG2L100H DDR3 IP/FDC/RCF 版本核验或重生成后必须重新核对并审核，不能把当前通过解释为动态验证通过。
- ci_7_scope: `docs/PDS_TCL_ENTRYPOINT_INVENTORY.json` 覆盖全部 13 个 tracked Tcl；逐项记录角色、`set_arch` 次数、器件集合、绝对路径事实和 `run_ps1_entry`。
- ci_7_roles: 角色集合固定为 `canonical_project_build`、`migration_blocked_project_build`、`canonical_support_tool`、`historical_gui`、`vendor_generated_internal`、`vendor_sim_internal`；只有三个项目 `scripts/build.tcl` 可由对应 `run.ps1` 调用。
- ci_7_target_boundary: 三个项目 `scripts/build.tcl` 均以 `Logos2 / PG2L100H / FBG484 / -6` 为当前目标；PCIe 因活动 IDF 仍带 50H metadata 而 migration-blocked。历史 GUI、厂商内部和厂商仿真脚本的混合器件/绝对路径不构成当前器件或实现证据。
- ci_7_result: 正向 `check_pds_tcl_entrypoints.ps1` 退出 0；删除任一清单项的负向测试退出 1。M2/M3 升格时必须同步清单角色与器件集合。
- h2_b0_scope: PCIe 历史 PG2L50H baseline 将五类问题归一化为 16 个唯一签名、42 次原始记录；该多重集只保留为旧产物审计证据。当前 PG2L100H gate 必须把活动 IDF 的 50H family/device metadata 作为迁移硬失败。
- h2_b0_result: 历史 50H fixture 正向退出 0、strict 退出 1；当时将 IDF 改为 PG2L100H 的变异也被旧规则拒绝，说明该 fixture 不能沿用为当前门禁。当前只批准 PG2L100H，且本批无 RTL、活动 IDF、FDC、厂商 IP 或生成物修改。
- h2_b1_boundary: lane/refclk/PERST#/SCBV/UART/I/O timing 仍需板级资料与决策；H2-B0 不解除发布阻断。
- ci_8_status: PCIe 的 partial/stale evidence 风险已由 CI-8A manifest 关闭；CI-8B 等待 DDR3 与 OV5640 各自建立 PG2L100H canonical 输入和最终构建入口后迁移，不使用时间戳容差或隐式假设。
- ci_8a_status: PCIe provenance pilot completed on 2026-08-31。
- ci_8a_inputs: `scripts/pds_sources.f` 是 37 个 HDL 的单一有序清单；与 `run.ps1`、`build.tcl`、`build_provenance.ps1`、活动 IDF/FDC 等合计形成 43 项 canonical 输入。
- ci_8a_manifest: 每次 build 以 32 位小写十六进制 `run_id` 原子替换固定 `build/provenance/pds-build.json`；状态为 `running/partial/failed/complete`，只有 `complete` 且 `valid=true` 可进入最终 gate。
- ci_8a_binding: 43 项输入与 full log、timing report、PNR 网表、slow SDF、`.sbit`、`.bin`、`bgr.db` 七项最终证据均绑定相对 POSIX path、length、SHA-256；日志中的唯一开始/完成标志必须与 manifest run_id 一致。
- ci_8a_result: partial compile、PDS executable 缺失、run-id 漂移、产物漂移和 FDC 输入漂移均 gate=1；历史完整 PG2L50H run `c24bc06b5d0643eeb6c9cb2878e7ace5` 为 `gen_bit_stream/complete/valid=true`，绑定 43 inputs/7 artifacts，full build=0、baseline=0、strict=1、slack=`0.100 ns`，H2-B0 16/42 多重集不变。该 run 只证明旧产物可审计，不是当前 PG2L100H 输入或发布证据。
- ci_8b_boundary: DDR3 与 OV5640 仅在各自 PG2L100H canonical IP/约束和最终构建入口升格后迁移 provenance；先按项目真实源清单和产物布局独立实现，不抽公共模块。
- ci_9_status: 2026-09-01 implemented_and_verified_sensitive_diff_gate
- ci_9_entry: `scripts/check_sensitive_diff.ps1`；契约文档为 `docs/SENSITIVE_DIFF_GATE.md`，并由 `scripts/check_repo_consistency.ps1` 调用规则自检、`-FullTree` 当前树扫描和 PR merge-base 差异扫描。
- ci_9_scope: 全树模式检查当前 tracked/untracked 工作树，PR 模式检查 merge-base 之后的 changed paths 与 added lines；严格占位符白名单之外，拒绝许可证文件名、Windows/UNC/Unix 绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名及 host id。
- ci_9_self_test: 2 个允许新增行、5 个拒绝新增行、1 个允许文件名、1 个拒绝文件名均按预期判定。
- ci_9_result: 68 个 tracked 日志中的 143 处许可证绝对路径已替换为 `<license-path>`；当前树 `-FullTree` 扫描和 PR 差异扫描均通过。
- ci_9_boundary: 保护当前版本并阻止后续重新引入，不读取或输出实际许可证配置；本批不改写 Git 历史，历史清理和任何历史重写必须独立审核。
- hardware_target_decision: 用户于 2026-09-04 确认三个项目共用 `RK3568_MES2L100H` 平台，实际 FPGA 为 `PG2L100H-6IFBG484`；统一 PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。
- legacy_50h_boundary: 全部旧 PG2L50H PDS/STA/网表/位流仅保留为历史证据，不得烧录或作为实板验收；三个项目必须分别建立 PG2L100H 当前版本基线。
- ci_0_boundary: 仅为仓库结构与文档静态一致性门禁，不启动或替代 PDS 构建、STA、项目严格 gate 或四级仿真。
- simulation_readiness_status: Questa 2021.1 tools and Logos2 USIM/VSIM verified historically; PCIe S2-A historical controlled smoke PASS retained; current S2-A/S2-B static gates pass but dynamic revalidation exits 4 on external license checkout; DDR3 and OV5640 project suites remain pending
- simulation_asset_boundary: `ipcore/`、`ip_core/`、`ip_backup/` 内的 DDR3、PLL、FIFO 和 PCIe RC/EP testbench/filelist/DO 均为厂商示例，只能作为模型与接口参考；不得直接计入 OV5640 产品顶层、`ddr3_bringup_top` 或 `pcie_dma_test` 的集成覆盖。
- simulation_common_gap: PCIe S2-A 保留项目自有 TB、相对路径 filelist/DO 与历史唯一 `TEST PASS`；当前动态复验未产生新 PASS。DDR3/S1 与 OV5640/S3 仍缺项目级入口，PCIe S2-B 动态/S2-C 及三项目后级网表/SDF 仿真仍未完成。
- next_step: 恢复仓库外许可证后以新 run id 复验 S2-A，再进入 S2-B 动态和 S2-C；摄像头产品按 C0/C1/C2/C3/S3 推进 OV5640。
- s0_0_recheck: 2026-08-30 的未发现仿真器结论已被 2026-09-01 的实际 Questa 执行、USIM 编译与 PCIe S2-A 动态 PASS 取代。

## Verilog/SystemVerilog 注释规范

- implementation_status: documented
- code_path: null
- evidence_path: `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`
- evidence_gap: 现有厂商代码和历史 RTL 尚未进行全量合规检查。
- responsibility: 约束后续手写 RTL 的意图、接口、FSM、复位、CDC/RDC 和风险注释。

## main OV5640→PCIe 板级一手资料

- implementation_status: primary_documents_registered_board_facts_partially_closed
- evidence_path: `docs/MAIN_OV5640_PCIE_BOARD_EVIDENCE.md`, `docs/MAIN_OV5640_PCIE_BOARD_INPUT_CHECKLIST.md`, `docs/MAIN_OV5640_PCIE_CLOCK_RESET_CONTRACT.md`
- external_source_boundary: 两份 PDF 保持在本机 Downloads，仅记录文件名、版本、页数、SHA-256 和关键 PDF 页码；不复制入仓、不作为构建依赖。
- rk_board_evidence: RK3568 与 FPGA 通过 PCIe x2、FSPI、I2C0 和 GPIO 相连；FPGA PCIe RX0/1=`D9/C9/B10/A10`、TX0/1=`D7/C7/B6/A6`，100 MHz refclk=`F6/E6`，25 MHz 系统时钟=`V4`，DDR 参考时钟=`R4/T4`。
- ddr3_board_evidence: 一片 `F60C1A0004-M79W`，x16、512 MByte、最大 1066 Mbps；有效地址为 `ddr3_addr[14:0]`，完整物理映射见板卡手册 PDF 第 13 页。
- ov5640_reference_evidence: 外置 OV5640 为 DVP；8-bit 输出使用 `D[9:2]`，RESETB 低有效、PWDN 高有效，SCCB 需上拉，并有供电、电平转换及上电/复位时序参考。
- evidence_gap: OV5640 实际排线/连接器、FPGA Bank 电压和管脚仍暂定；还缺完整原理图/BOM、PCIe PERST#/链路时序、DDR3 IP 用户口、full PCIe TX/DMA 接入、RK3568 驱动/缓存协议及冻结 RGB565 模式。
- stop_condition: 未关闭上述缺口前，不修改 canonical IP/FDC/RCF，不把行为模型解释为真实板级闭环。

## main 独立 OV5640→PCIe M1-A

- implementation_status: m1a_capture_behavior_verified
- project_path: `main_ov5640_pcie/`
- branch: `codex/main-ov5640-pcie`
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_capture.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_dvp_rgb565_capture.sv`
- evidence_path: `main_ov5640_pcie/README.md`, `docs/MAIN_OV5640_PCIE_CAPTURE_CONTRACT.md`, `TODO.md`
- responsibility: 只在 `cam_pclk` 域采样源同步 DVP，在有效 HREF 窗口内配对两个 8-bit 字节，输出 RGB565 像素、零基坐标和帧/行事件；不负责 SCCB、MCLK、RESET/PWDN、CDC/FIFO、图像处理、DDR3 或 PCIe。
- vscs_contract: 手写 RTL/TB 记录文件/接口、时钟复位、假设、意图、不变量和 hazard；不代表历史或厂商 RTL 已完成全量 VSCS 审核。
- timing_contract: `cam_vsync`、`cam_href`、`cam_data` 必须在模块输入处满足 `cam_pclk` 源同步时序；`rst_n` 异步断言，释放约束由集成设计负责。
- vsync_contract: VSYNC 进入配置的有效电平时关闭已观察帧并武装下一帧；首个标记不产生 `frame_end`，标记后的首个完整像素产生一次 `frame_start`。
- href_contract: HREF 有效时接收字节；每行首个完整像素产生 `line_start`，窗口关闭后在该行已有完整像素时产生 `line_end`；未配对尾字节被丢弃并产生 `protocol_error`。
- byte_order_contract: 默认首字节是 RGB565 高字节，`FIRST_BYTE_IS_HIGH` 可选择反向拼接。
- behavior_tb_coverage: 两个 HREF 行、每行三个像素；检查 6 个像素及坐标、帧/行起止事件、下一 VSYNC 的 `frame_end`、奇数字节错误和 watchdog。
- questa_evidence: 主代理提供的 Questa Sim-64 2021.1 证据为编译 0 error/0 warning、运行成功且日志唯一 `TEST PASS`；仓库不记录本机工具路径或许可证信息。
- uncovered_boundaries: SCCB/寄存器与 sensor ID、板级 DVP 电气/相位/管脚、CDC/FIFO/逐域复位、DDR3、128-bit PCIe DMA、主机协议、PDS/STA、综合后/PNR/SDF 均未覆盖。
- reference_boundary: `parallel_driver` 仅只读参考；未导入其 RTL、IP、FDC/RCF、PDS 产物或验收证据。

## main 独立 OV5640→PCIe M2-A

- implementation_status: m2a_rgb565_grayscale_behavior_verified
- project_path: `main_ov5640_pcie/`
- branch: `codex/main-ov5640-pcie`
- code_path: `main_ov5640_pcie/rtl/rgb565_grayscale.sv`, `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_dvp_rgb565_pipeline.sv`
- evidence_path: `main_ov5640_pcie/README.md`, `docs/MAIN_OV5640_PCIE_PROCESS_CONTRACT.md`, `TODO.md`, `docs/IMPLEMENTATION_LOG.md`, `main_ov5640_pcie/scripts/run_m2a.ps1`
- responsibility: `rgb565_grayscale` 只负责 RGB565 到灰度 RGB565 的处理；wrapper 只连接 M1-A 采集与该处理模块；两者均运行在 `cam_pclk` 域，不负责 SCCB、MCLK、RESET/PWDN、CDC/FIFO、DDR3、PCIe 或主机协议。
- grayscale_contract: RGB565 的 R/G/B 分量分别按 `R[15:11]`、`G[10:5]`、`B[4:0]` 扩展到 8 bit，计算 `Y=(77*R+150*G+29*B)>>8`，并把同一 `Y` 复制回 RGB565 三个字段。
- latency_contract: `pixel_valid`、灰度像素、坐标、帧/行事件和 `protocol_error` 均相对输入延迟一拍 `cam_pclk`；无背压；输出无效周期 `pixel_data=16'h0000`。
- behavior_tb_coverage: 公开 DVP 输入驱动两行四像素（黑、红、绿、蓝），检查灰度数据、零基坐标、帧/行事件保持和奇数字节协议错误；watchdog 与失败 `$fatal`，成功日志要求唯一 `TEST PASS`。
- questa_evidence: `docs/IMPLEMENTATION_LOG.md` 记录 Questa Sim-64 2021.1 的 4 个 RTL/TB 模块编译 `0 error/0 warning`、管线行为仿真返回 0；`run_m2a.ps1` 对日志中的 `TEST PASS` 做恰好一次校验。Nexus 不记录模拟器安装路径、许可证或凭证。
- uncovered_boundaries: SCCB/寄存器与 sensor ID、板级时钟/电气时序/管脚、CDC/FIFO/逐域复位、DDR3、PCIe/主机协议、PDS/STA、综合后/PNR/SDF 均未覆盖。
- reference_boundary: `parallel_driver` 仍仅只读参考；未导入其 RTL、IP、FDC/RCF、PDS 产物或验收证据。

## main 独立 OV5640→PCIe M3-A

- implementation_status: m3a_rgb565_128bit_word_packing_behavior_verified
- project_path: `main_ov5640_pcie/`
- branch: `codex/main-ov5640-pcie`
- code_path: `main_ov5640_pcie/rtl/rgb565_word_packer.sv`, `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_word_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_word_packer.sv`, `main_ov5640_pcie/tb/tb_ov5640_dvp_rgb565_word_pipeline.sv`
- evidence_path: `docs/MAIN_OV5640_PCIE_WORD_PACKER_CONTRACT.md`, `docs/MAIN_OV5640_PCIE_FRAME_PROTOCOL.md`, `docs/IMPLEMENTATION_LOG.md`, `main_ov5640_pcie/README.md`, `main_ov5640_pcie/scripts/run_m3a.ps1`
- responsibility: `rgb565_word_packer` 只把 M2-A 输出的同域灰度 RGB565 像素组织为内部 128-bit 图像字；wrapper 只连接既有采集/灰度 pipeline 与 packer，不负责 SCCB、CDC/FIFO、DDR3、PCIe TLP 或主机协议。
- layout_contract: 像素 0..7 按接收顺序依次位于 `word_data[15:0]` 到 `word_data[127:112]`；8 像素完整字的 `word_keep=16'hffff`。
- partial_contract: 行尾不足 8 像素时补零输出；N 个有效 RGB565 像素只置 `word_keep` 低 `2N` 位，其余 `word_data` 位和 keep 高位为 0。
- control_contract: `frame_start/line_start` 随包含首像素的字输出；payload 判定为 `word_valid && word_keep!=0`；纯控制事件统一为 `word_valid=1`、`word_keep=0`，覆盖无 payload 的 `line_end/frame_end/protocol_error`。
- behavior_tb_coverage: 单元 TB 覆盖 8 像素完整字、3 像素补零行尾字、空载帧尾与协议错误；DVP 集成 TB 覆盖采集→灰度→打包及奇字节错误传播，失败 `$fatal`，成功日志唯一 `TEST PASS`。
- questa_evidence: `docs/IMPLEMENTATION_LOG.md` 记录 2026-09-03 使用 Questa Sim-64 2021.1 编译 6 个 RTL/TB 模块为 `0 error/0 warning`、集成行为仿真返回 0；`run_m3a.ps1` 校验日志中的 `TEST PASS` 恰好一次。
- uncovered_boundaries: 内部布局不等同于 DDR3 地址单位、PCIe AXIS `tkeep`、PCIe TLP payload 或主机字节序；SCCB、板级、CDC/FIFO、DDR3/PCIe 集成、PDS/STA 和后级仿真均未覆盖。

## main 独立 OV5640→PCIe M3-B staging adapter

- implementation_status: behavior_verified_staging_only
- project_path: `main_ov5640_pcie/`
- code_path: `main_ov5640_pcie/rtl/rgb565_word_to_axis4_adapter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_word_to_axis4_adapter.sv`
- evidence_path: `docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`, `docs/IMPLEMENTATION_LOG.md`, `main_ov5640_pcie/scripts/run_m3b.ps1`
- responsibility: 将 M3-A 128-bit/16-byte 内部字按低 byte lane 顺序拆为最多四个 32-bit staging beat，并按当前片段产生 4-bit keep；不接入 PCIe/DDR3 IP。
- event_contract: 首帧/首行事件附着首 beat，行尾/帧尾/协议错误附着末 beat；无 payload 控制事件使用 keep=0、last=1。
- verification: Questa Sim-64 2021.1 编译 2 个 RTL/TB 模块为 0 error/0 warning，行为返回 0，唯一 TEST PASS；覆盖完整字、部分字、控制事件和背压。
- uncovered_boundaries: staging `out_user` 不是厂商 PCIe `tuser` 编码；PCIe TLP/最大 payload/4 KB、DDR3 地址与 burst、CDC/FIFO、主机协议和 PDS/STA 均未覆盖。

## main 独立 OV5640→PCIe M3-B frame accounting

- implementation_status: behavior_verified_staging_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_frame_accounting.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_frame_accounting.sv`
- evidence_path: `main_ov5640_pcie/scripts/run_m3b_accounting.ps1`, `docs/IMPLEMENTATION_LOG.md`
- responsibility: 累计 staging beat 的有效字节、有效 beat 和协议错误，在帧尾输出固定统计描述符；不分配 DDR3/主机地址。
- verification: Questa Sim-64 2021.1 编译 2 个 RTL/TB 模块为 0 error/0 warning，行为返回 0，唯一 TEST PASS；覆盖 5-byte/2-beat、空载帧尾、错误传播和描述符背压。
- uncovered_boundaries: 描述符未定义 DDR3 地址单位、burst、PCIe TLP/最大 payload、CDC/FIFO 或主机协议。

## main 独立 OV5640→PCIe normalized MWR descriptor

- implementation_status: behavior_verified_vendor_independent_descriptor_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_mwr_descriptor.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_mwr_descriptor.sv`
- responsibility: 将 4-byte staging beat 规范化为 vendor-independent PCIe Memory Write request descriptor；payload request 输出实际 DWORD 数 `req_length_dw=1`，按 payload 有效字节递增地址并转发 keep/last/frame_end。
- verification: TB 覆盖实际 DWORD 数、地址递增、`keep`、`last`、`frame_end` 与 4KB 边界标志；`keep=0` 在 descriptor 本地接受，不拉高 `req_valid` 且不推进 PCIe 字节地址。
- boundary: 仅验证规范化描述符字段与 4KB 边界指示；partial keep 仍未映射为 canonical vendor TX byte enable，不定义完整 TLP/DMA、DDR3 地址或主机协议。

## main 独立 OV5640→PCIe normalized DDR3 write record

- implementation_status: behavior_verified_record_layout_and_canonical_adapter_input
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_ddr3_write_descriptor.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_ddr3_write_descriptor.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ddr3_write_descriptor.ps1`
- responsibility: 按帧接收 slot table 分配的 `slot/base/capacity`，生成单 beat 128-bit 数据、16-bit strobe 的 normalized DDR3 write record；低 4 byte 保存 payload，第 5 byte 保存 `keep/last/frame_end/protocol_error`。
- allocation_contract: allocation 的 slot id、槽基 opaque token 与记录容量在握手时装载；slot table 是容量单一事实源，writer 只执行所分配容量的地址约束。
- integration_contract: writer 在背压期间保持记录稳定；新流水顶层在 writer 外执行“DDR write 接受后再向 frame commit 提交”的两阶段交付。
- address_contract: `write_addr` 从本帧 allocation base 起步，按 opaque `ADDR_STEP` 推进；该步长不解释为任何物理地址单位。
- storage_contract: `write_data[31:0]` 保存 payload，`write_data[35:32]/[36]/[37]/[38]` 保存 `keep/last/frame_end/protocol_error`；`write_strb[3:0]=keep`、`write_strb[4]=1`，零 payload 控制记录也写入元数据 byte。
- regression_2026_09_03: Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 `TEST PASS`，仿真至 251 ns；覆盖 allocation 的 slot/base/capacity、背压字段保持、容量边界与恢复。
- boundary: 不假定正式地址单位、物理槽范围、初始化行为或 AXI4 burst 语义；记录已接入项目自有 canonical adapter，但尚未通过加密 DDR core、PDS/STA 或实板验证。

## main 旧 50H 文件名行为切片：DDR3 write adapter

- implementation_status: behavior_verified_canonical_aw_w_adapter_only
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_ddr3_write_adapter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_ddr3_write_adapter.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_ddr3_write_adapter.ps1`
- responsibility: 旧 50H 文件名行为切片，把一条 normalized 128-bit 写记录映射到待 PG2L100H 复核的非标准 AW/W 用户口，并在真实写数据拍被 `axi_wready` 消费前保持地址、数据和 strobe；不构成 50H 平台批准。
- contract: `ddr_init_done` 在 `io_clk` 域两拍同步后才准入；单 outstanding、`axi_awlen=0`、固定 request id、`axi_awuser_ap=0`；支持 AW 与 W 同拍完成，上游 `in_ready` 只在 W consume 时拉高。
- evidence: 2026-09-03 Questa Sim-64 2021.1：专项 write adapter 221 ns，writer→adapter path 196 ns；均 0 error/0 warning、日志唯一 `TEST PASS`。
- boundary: canonical 接口没有 B channel，`in_ready` 只证明用户写数据拍已被 core 端口消费，不证明物理 DDR 持久化；正式地址单位/槽范围、加密 core、PDS/STA/板级均未关闭。

## main 旧 50H 文件名行为切片：DDR3 read adapter

- implementation_status: behavior_verified_canonical_ar_r_adapter_only
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_ddr3_read_adapter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_ddr3_read_adapter.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_ddr3_read_adapter.ps1`
- responsibility: 旧 50H 文件名行为切片，把单条 frame scheduler 读命令映射到待 PG2L100H 复核的 AR/R 用户口，并把 128-bit 返回拍还原为 32-bit payload 与第 5 byte 元数据；不构成 50H 平台批准。
- contract: `ddr_init_done` 两拍同步后准入；单 outstanding、`axi_arlen=0`、固定 request id、`axi_aruser_ap=0`；由于 core 无 `axi_rready`，R 拍必须先进入本地缓冲再等待下游，AR/R 同拍返回也必须正确捕获。
- fault_contract: RID 不匹配或 RLAST 缺失并入 `out_protocol_error`；无命令、AR 尚未握手或本地响应缓冲已占用时出现 RVALID，产生 `port_fault_pulse`。
- evidence: 2026-09-03 Questa Sim-64 2021.1：专项 read adapter 191 ns，0 error/0 warning、日志唯一 `TEST PASS`。
- boundary: 不解释 28-bit 地址单位、物理槽布局、刷新/仲裁或加密 core 行为；端口 fault 是接口违规诊断，不等价于 ECC 或物理内存错误。

## main 独立 OV5640→PCIe MWR bridge

- implementation_status: behavior_verified_audited_pin_bridge_provisional
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_pcie_mwr_bridge.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_pcie_mwr_bridge.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pcie_mwr_bridge.ps1`
- responsibility: 将规范化请求映射到已审计的 `mwr32_req/ack`，锁存实际 DWORD 数、地址、数据与事件字段，并在 canonical ACK 前保持请求稳定。
- evidence: 2026-09-03 Questa Sim-64 2021.1 独立 bridge TB 为 0 error/0 warning、唯一 TEST PASS、76 ns；旧 50H 文件名行为切片 `tb_rgb565_pg2l50h_mwr32_tx_integration.sv` 直接实例化未修改 `ips2l_pcie_dma_mwr_tx_ctrl`，为 136 ns、0 error/0 warning、唯一 TEST PASS，仍待 PG2L100H IP 边界复核。
- canonical_tx_contract: 隔离动态集成验证 req 保持至 ACK、header length=`1`、DWBE=`8'h0f`、4 字节对齐地址 `0x1000`、用户数据低 DWORD=`0x44332211` 以及 bridge/vendor busy 最终释放。
- boundary: 只证明单 DWORD、`keep=4'hf`、4 字节对齐的 vendor TX 仿真边界。项目自有第二请求源仲裁和异步 CDC 另有独立证据，但 partial keep、完整 TX 顶层实例化、PCIe link training、RK3568/主机内存写入仍未关闭。

## main 旧 50H 文件名行为切片：PCIe TX native/camera 请求仲裁器

- implementation_status: behavior_verified_pcie_domain_request_arbiter_with_ack_release_barrier
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_tx_request_arbiter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_tx_request_arbiter.sv`, `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_tx_arbiter_integration.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_tx_request_arbiter.ps1`, `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_tx_arbiter_integration.ps1`
- responsibility: 旧 50H 文件名行为切片，在同一 TX 时钟域内原子仲裁完整 native `MWR32/MWR64/MRD32/MRD64` 请求 bundle 与 camera MWR32；native bundle 包含四类 request、MWR user-defined mode、length/address/data，camera bundle 包含 MWR32、length/address/data。该行为需在 PG2L100H Endpoint/IP 下复核。
- arbitration_contract: 空闲且两源同时请求时按上次完成 owner 轮转，复位后 native 先行；owner 与被选字段保持到匹配 TX ACK，未授权源不得看到 ACK。
- ack_release_contract: 匹配 ACK 后撤销下游请求并进入 `WAIT_ACK_LOW`；只有观察到 vendor ACK 拉低，才允许换 owner 或发布下一事务，防止保持型 ACK 被下一请求误消费。
- mwr_mode_contract: MWR user-defined 模式只在 native/camera MWR ACK 时更新；native MRD 不得改变该模式，锁存值保持到下一次 MWR handshake，使 vendor MWR TX 在 ACK 后仍看到正确 RAM-data 或 user-defined 模式。
- evidence: 2026-09-04 Questa Sim-64 2021.1：增强 arbiter 专项 265 ns；native RAM-data 与 camera user-defined 依次经过未修改 `ips2l_pcie_dma_mwr_tx_ctrl` 的集成测试 205 ns；均 0 error/0 warning、日志唯一 `TEST PASS`。
- boundary: ACK 只表示 TX controller 接受请求，不表示 TLP 完成或主机写入。异步 camera 请求由独立 CDC wrapper 接入；本节两个仲裁专项不实例化完整 `ips2l_pcie_dma_tx_top`，该请求到完整 TX top AXIS 输出的独立行为集成由下述 adapter 专项覆盖。partial keep/byte enable、LTSSM、串行链路和 RK3568 主机内存仍未关闭。

## main 旧 50H 文件名行为切片：PCIe MWR32 异步 mailbox

- implementation_status: behavior_verified_single_outstanding_async_mailbox
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_mwr32_async_mailbox.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_mwr32_async_mailbox.ps1`
- responsibility: 旧 50H 文件名行为切片，将一笔保持型 camera MWR32 的 length/address/data 从 DDR3 应用 `core_clk` 域传到 PCIe `pclk_div2` 域，并只在目标端真实 ACK 后向源端完成；placed-design 只面向 PG2L100H 签核。
- cdc_contract: 单 outstanding toggle handshake；online/fault 电平保持两级同步，request/ACK token 使用三级同步，确保 peer-offline 先于事务 token 到达事务逻辑；目标检测 token 后额外等待一拍，再采样源端持续稳定的 bundled-data MCP；目标寄存 payload 并保持请求到 ACK，ACK token 返回源域。
- reset_contract: 在线 reset handshake 在双方 channel-ready 前禁止新请求；idle 单域复位可重新对齐；在途任一域复位产生 pulse/sticky fault，事务结果定义为不确定且不自动 replay，要求上层作废当前 frame/slot 并协调 flush。
- ack_release_contract: 源 ACK 保持到源请求撤销；目标进入 `WAIT_ACK_LOW`，vendor ACK 拉低前不接收下一 token。
- evidence: 2026-09-04 Questa Sim-64 2021.1：源快/目标慢与源慢/目标快、连续 token、payload 稳定、ACK 延迟/保持、idle 与在途复位回归 2296 ns，0 error/0 warning、日志唯一 `TEST PASS`。
- boundary: RTL 行为仿真不证明亚稳态或位间 skew；placed-design 必须对源 payload holding registers→目标 capture registers 签核 max-delay/bus-skew，并完成 CDC/RDC 与 STA。单纯 false-path 整条 payload 总线不可接受。

## main 旧 50H 文件名行为切片：PCIe TX CDC/仲裁集成

- implementation_status: behavior_verified_async_camera_and_native_tx_boundary
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_tx_cdc_arbiter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_tx_cdc_arbiter_integration.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_tx_cdc_arbiter_integration.ps1`
- responsibility: 旧 50H 文件名行为切片，组合异步 MWR32 mailbox 与现有 PCIe 域 native/camera 请求仲裁器，不修改厂商 MWR TX RTL；该组合必须在 PG2L100H IP 下复核。
- evidence: 2026-09-04 Questa Sim-64 2021.1：native RAM-data 与异步 camera user-defined 请求各形成且仅形成一条正确单 DWORD TLP，385 ns，0 error/0 warning、日志唯一 `TEST PASS`。
- boundary: 只关闭事务 CDC、ACK 隔离和 PCIe 域仲裁行为；本节专项不实例化完整 `ips2l_pcie_dma_tx_top`，该请求到 AXIS 输出的独立集成由下述 adapter 专项覆盖。partial keep、LTSSM、串行链路、RK3568 主机协议、真实 DDR3 IP 或板级实现仍未关闭。

## main 旧 50H 文件名行为切片：PCIe 完整 TX top adapter

- implementation_status: behavior_verified_camera_native_requests_to_complete_tx_top_axis
- code_path: `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_tx_top_adapter.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_tx_top_adapter.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_tx_top_adapter.ps1`
- responsibility: 旧 50H 文件名行为切片，在项目自有边界内组合 `rgb565_pg2l50h_pcie_tx_cdc_arbiter` 与未修改的完整 `ips2l_pcie_dma_tx_top`，把异步 camera MWR32 和 PCIe 域 native `MWR32/MWR64/MRD32/MRD64` bundle 接入厂商 TX 顶层，并透传三路 AXIS TX、BAR0/BAR2 读口及 CPLD 输入；不构成 50H 平台批准，正式集成只面向 PG2L100H。
- evidence: 2026-09-04 Questa Sim-64 2021.1：非谐波 camera/PCIe 双时钟下，native user-defined MWR 与 camera MWR 依次形成正确 header/data，共 4 个 AXIS beat；专项仿真至 385 ns，0 error/0 warning、日志唯一 `TEST PASS`。
- closure: 关闭 camera/native CDC/仲裁请求到完整 `ips2l_pcie_dma_tx_top` AXIS 输出的行为集成缺口，且不修改厂商 PCIe RTL。
- boundary: 不代表 LTSSM、PCIe 串行链路、真实 DDR3 IP、RK3568 主机内存或产品板级闭环；也不替代 placed-design CDC/RDC/STA 与 partial keep/byte-enable 签核。

## OV5640 摄像头 HDMI 产品目标

- implementation_status: target_scoped_pending_reference_audit
- code_path: null
- evidence_path: `docs/OV5640_TARGET_SCOPE.md`
- product_boundary: 产品摄像头为 OV5640，当前唯一板卡与器件为 `RK3568_MES2L100H` / `PG2L100H-6IFBG484`。
- c0_boundary: 只读导入并审计参考工程的源、IP、约束、顶层、器件元数据和绝对路径，不覆盖 canonical。
- c1_boundary: 冻结单/双摄、模组料号、MCLK、RESET/PWDN、I/O 电压、管脚、DVP 位宽/极性、输出格式、分辨率、帧率与字节序。
- c2_boundary: 设计新的项目目录与顶层，形成 OV5640 SCCB/寄存器配置、读 ID 自检、采集、DDR3 帧缓存和 HDMI 输出迁移方案。
- c3_boundary: 所有 IP/约束按 `Logos2 / PG2L100H / FBG484 / -6` 重新审核或生成，完成七阶段 PDS 与严格 gate；任何旧 50H 产物不可继承。
- s3_boundary: 建立 OV5640 项目级自检 TB、相对路径 filelist/DO，并依次关闭行为级、综合后、PNR 功能和 PNR 时序仿真；公共 Questa/USIM/VSIM 证据不等于产品通过。
- next_step: 先完成 C0 参考工程可访问性与只读审计，再由 C1 冻结产品范围；C0/C1 未完成前不修改活动 RTL、IP 或约束。
- high_attention: `i2c_dri_clk` 逻辑生成时钟、`cam_pclk`/DDR `ui_clk`/`pixel_clk` 间业务 CDC、FIFO 分侧复位，以及 `ddr3_init_done` 参与的复位释放。

## DDR3 外层工程

- implementation_status: bringup_full_implementation_baseline
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/scripts/regenerate_ip.ps1`, `ddr3_test/ddr3_test/doc/M2_IP_REGENERATION.md`, `ddr3_test/ddr3_test/doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`, `ddr3_test/ddr3_test/build/logs/pds-gen_bit_stream.log`, `ddr3_test/ddr3_test/build/pds/report_timing/test_ddr.rtr`, `ddr3_test/ddr3_test/scripts/check_build.ps1`
- evidence_gap: M2-B1 的 50H staging 只保留为历史错误假设下的参数/资产差异审计，旧自动生成入口已硬阻断。活动 IP/FDC/RCF 当前为 PG2L100H，但仍需依据板级 DDR3 参数审核 28 项 FDC pin 差异、核验或重生成 100H IP、完成 canonical 升格、CI-6、100H 空目录七阶段、D3-0-R 与 D3-A/B/C；未完成前现有 STA、网表、SDF 和位流不得用于实板。
- responsibility: 当前以厂商 `test_ddr` 作为临时 DDR3 board bring-up 顶层；后续必须明确真正产品顶层和板级功能范围。
- hardware_target: `RK3568_MES2L100H` / `PG2L100H-6IFBG484` / `Logos2 / PG2L100H / FBG484 / -6`
- m2_active_input_audit: 活动 `ip_core/ddr3/ddr3.idf` 为 `PG2L100H`、生成器 `2022.2-SP6.4`；canonical FDC/RCF 为 `ip_core/ddr3/pnr/ddr_test.fdc` 与 `ip_core/ddr3/pnr/ddr3.rcf`；`ip_core/ddr_test.fdc` 是旧外层参考，不能直接升格。项目自有 `scripts/build.tcl` 与 `scripts/check_build.ps1` 当前也按 `PG2L100H`，仍需完成板级和产物核验。
- m2_legacy_50h_audit: `ip_backup/20250108100125/ddr3/ddr3.idf` 为 `PG2L50H`，但生成器是 `2022.2-SP6.1`；它是旧产物，仅可作为参数/硬宏差异 oracle，禁止恢复、复制、生成或升格到活动输入。
- m2_a_staging: `2026-08-30` 曾使用旧 `scripts/regenerate_ip.ps1` 在 `build/ipgen/pg2l50h` 调用 SP6.4 build 146967 生成 `Logos2/PG2L50H/FBG484/-6` staging，结果 `0 error(s), 0 warning(s)`；这是历史错误假设下的旧产物，脚本现已硬阻断，canonical IDF 未被替换。
- m2_b1_derived_parameter: PDS SP6.4 `ui.tcl` 定义 `DEVICE_100H_EN` 为隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`；直接 `-device` 覆盖旧 100H IDF 会错误保留 `true` 并生成不一致分支，故 50H override 和生成路径已明确禁止。
- m2_b1_seed_regeneration: 活动 100H IDF 与 SP6.1 旧 50H seed 的历史参数比较仅发现 `DEVICE_100H_EN` 不同；旧脚本曾由 SP6.4 build 146967 生成 50H staging，该结果只作迁移阻断证据，现不得继续执行或升格。
- m2_b1_diff: 历史 50H staging 与当前 100H 资产的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均不同；wrapper 端口 `21 → 26`，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，FDC 有 28 项 pin 差异。这些差异用于 PG2L100H 复核，不指导生成 50H。
- m2_status: seed_parameter_validation_and_sp6_4_staging_verified_pending_board_evidence_and_canonical_promotion
- m2_gate: 取得原理图/BOM并锁定板级 DDR3 颗粒/组织/PCB 参数 → 审核 28 项 FDC pin 差异及 wrapper/PHY/filelist/IDF → 升格 canonical → 重跑 CI-6 → 清空 `build/` 完成七阶段与器件交叉检查 → 重审 D3-0-R，获审后才可进入 D3-A。M2-B1 未授权 canonical 替换、D3-A 或烧录。
- d3_0_read_only_review: `2026-08-30` 已确认活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`；公开端口包含 `ddr_init_done`、`core_clk` 和自定义 AXI-like AW/W/AR/R 接口。`test_ddr.v` 的物理 board wrapper 实例名 `I_ips_ddr_top` 必须保持不变。
- d3_0_status: legacy_contract_review_complete; PG2L100H IP/FDC/RCF verification_or_regeneration_and_D3-A_re-review_required
- d3_0_handshake_contract: 写地址以 `axi_awvalid && axi_awready` 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读请求以 `axi_arvalid && axi_arready` 接受，核心用 `axi_rvalid`/`axi_rlast` 返回且没有 `axi_rready`。D3-A 按该非标准 AXI-like 契约实现；若 IP 重生成后语义、地址单位或层级变化则停止并重新审核。
- d3_0_boundary: 只更新文档和评审事实；D3-0 不修改 RTL、活动 IP、FDC/RCF 或构建脚本。
- d3_0_r_port_map: 提交 `2fd7c51` 新增 `D3A_PORT_MAP.md`，提交 `a5d1785` 的 CI-6 进一步静态交叉核对 core/wrapper/document；该契约属于旧 IP 事实，PG2L100H IP 核验或重生成后必须重新运行门禁并审核，D3-A 之前不得修改厂商 IP 或物理端口。
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
- next_step: M2-B1 的旧 50H staging 只保留为历史差异证据，不能升格。先依据原理图/BOM审核 28 项 FDC pin 差异和新增 wrapper 状态端口，再在 PG2L100H 目标下核验或重生成 IP/FDC/RCF；100H staging 通过后重新核对握手、地址单位、端口和 `I_ips_ddr_top` 层级，重新审核 D3-A 后才可按 D3-A → D3-B → D3-C 实现项目自有 RTL。

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
- evidence_gap: 项目自有 build/PDS/gate 已按 PG2L100H 管理，但活动 `pcie_test.idf` 仍错误带有 PG2L50H metadata，旧 50H 产物只作历史证据且一致性门禁应失败；S2-A 保留历史动态 PASS，当前 S2-A/S2-B 静态门禁通过。当前动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS；真实 RC/EP、DMA、板级证据和 PG2L100H 后级网表/SDF 仍缺失。
- responsibility: 集成 PCIe x2 IP、DMA、RAM/FIFO 与 UART2APB 管理路径。
- build_entry: `pcie_dma_test_100h/scripts/run.ps1`
- build_definition: `pcie_dma_test_100h/scripts/build.tcl`
- build_gate: `pcie_dma_test_100h/scripts/check_build.ps1`
- h2a_read_only_evidence: `2026-08-30`；顶层端口为 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；FDC 映射 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。
- h2a_status: completed_read_only_evidence_matrix; H2-B 仍待板级资料和审核
- h2a_constraint_gaps: FDC 未提供 lane 极性、板级拓扑、I/O delay 或 SCBV；当前目标为 `Logos2 / PG2L100H / FBG484 / -6`，但 `pcie_test.idf` metadata 仍为旧 PG2L50H，HSSTLP 资源和新产物需重新按 100H 核验。
- h2a_uart_gap: UART2APB 使用隐式 `rxd/txd` 网络，当前 `rxd` 被绑 0；该功能缺口不因 PDS/STA 成功而关闭。
- h2a_boundary: 器件型号已获用户审核；活动 PCIe IDF 仍需重新生成/核验为 PG2L100H。旧 M1 build/gate、HSSTLP 资源和生成物只作历史证据；RTL/FDC 其余内容仍受 UART 与板级证据审核约束。
- s2a_status: historical_controlled_dynamic_smoke_pass_retained; current_static_gate_passed; current_dynamic_revalidation_blocked_external_license_checkout_exit_4; no_new_test_pass
- s2a_assets: `tb/tb_pcie_dma_test.sv` 实例化真实 `pcie_dma_test`，全局复位实例名为厂商要求的 `GRS_INST`；`tb/pcie_test_smoke_model.sv` 只替代生成 PCIe IP 边界，两个时序过程恰好使用两个 `always_ff`；`sim/behav.f` 复用 `scripts/pds_sources.f` 的 37 个 canonical HDL，并单独补入仿真所需 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`。`scripts/pds_sources.f` 不修改，因为该源在实现侧由 IDF 管理。
- s2a_log_contract: 每次动态运行使用随机 32 位小写十六进制 `SIM_RUN_ID`；DO 通过 `echo` 将 marker 写入 transcript，并为本次运行创建独立 work。PowerShell 只接受同一 run id marker 恰好一次且 `TEST PASS` 恰好一次，任一失败由 `$fatal` 或非零退出传播。
- s2a_reset_contract: button reset 只拥有 PCIe core/pclk 域；TB 在断言后先确认 ref counter 没有被清零，再跨额外 8 个 refclk 周期确认 link 撤销期间严格保持原值。随后 button reset 完整重新释放并恢复 model link，PERST# 才单独断言以复位两组 LED 域，再独立释放并重新通过 debounce/link 检查。
- s2a_coverage_boundary: 只覆盖产品顶层展开、外部/同步复位、上述 reset ownership、两组 LED 计数门控及 TX/LED 未知态；受控 `smlh_link_up/rdlh_link_up` 只是激励，不证明 LTSSM、TLP、DMA、x2 lane、电气 refclk/PERST# 或 RK3568 Root Complex。
- s2a_dynamic_result: Questa Sim-64 2021.1；`vlog` 0 errors/0 warnings；`vsim` elaboration 成功并运行到 `1476105 ns`；Errors 0/Warnings 2；唯一 `TEST PASS`；PowerShell 同 run-id/唯一 PASS 门禁通过。
- s2a_current_revalidation: 当前版本静态 gate 通过；Questa 动态启动因仓库外许可证 checkout 失败返回 4，未产生新的 run marker 或 `TEST PASS`，历史日志不得复用为当前结果。
- s2b_static_status: 厂商 RC/项目 EP 双库、双向 x2 lane、双端 link/LTSSM L0、32 周期稳定、6 ms watchdog 和唯一 PASS 静态契约门禁通过；动态真实链路证据尚未生成。
- s2a_warning_todo: 两条 warning 均为 `pcie_dma_test.v` 中 `u_ips2l_pcie_dma` 缺少输出 `o_trgt1_radm_pkt_halt` 连接；作为独立 RTL hygiene TODO，不影响本层受控 smoke PASS。
- s2_next_layers: S2-B 使用厂商 `pango_pcie_top_sim` RC 与项目 `pcie_dma_test` EP 验证真实链路；S2-C 在 S2-B 后执行固定地址/长度/数据的基础 DMA 回读。S2-A 边界模型不得进入这两层或后级网表验收。
- h2b_stop_conditions: 板级 lane 极性/拓扑、I/O delay 或 SCBV 缺失，IDF/PDS 器件元数据不一致，或 UART2APB `rxd/txd` 归属未决时，H2-B 不得收紧 gate；不得用 waiver 掩盖缺口。
- next_step: 保持 H2-B1 strict gate 阻断并等待 lane/refclk/PERST#/SCBV 与 UART 决策；独立处理 `o_trgt1_radm_pkt_halt` RTL hygiene TODO，再进入真实 RC/EP 的 S2-B、S2-C DMA 与项目后级网表/SDF 仿真

## main OV5640→PCIe M3-B 联合 staging

- implementation_status: behavior_verified_same_clock_only
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_dma_staging_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_dvp_rgb565_dma_staging_pipeline.sv`
- contract_path: `docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`
- evidence: 2026-09-03 Questa 2021.1 编译 9 个 RTL/TB，0 error/0 warning，唯一 TEST PASS
- boundary: 不包含 DDR3/PCIe IP、CDC/FIFO、SCCB、板级时钟/管脚或主机协议；frame_end_pending 仅为同域 staging 验证策略

## main OV5640→PCIe M3-B 两槽 word skid 与帧中止恢复

- implementation_status: behavior_verified_two_slot_word_skid_abort_recovery
- project_path: `main_ov5640_pcie/`
- branch: `codex/main-ov5640-pcie`
- code_path: `main_ov5640_pcie/rtl/rgb565_word_skid_buffer.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_word_skid_buffer.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_word_skid_buffer.ps1`
- contract: 位于无背压 RGB565 word packer 与 4-byte adapter 之间；两槽 FIFO 按先入先出保存 128-bit word 及 5 个事件位。满队列且无同拍出队时，拒收触发 word 并置位 sticky `overflow`，保留溢出前已经排队的完整前缀，随后丢弃当前帧余量，并在此前缀后恰好排入一个 `keep=0/frame_end=1/protocol_error=1` 的空载中止记录。只有已经观察到原帧尾且中止记录已经排队，才允许后续携带 `frame_start` 的输入恢复；在两个条件同时满足前到达的新帧整帧跳过。正常状态仍允许满队列同拍出队/入队替换尾槽，输出未接收期间字段保持；`in_ready` 仅作诊断，不能向无背压 packer 提供反向流控。
- evidence: 2026-09-03 Questa Sim-64 2021.1 编译 2 个 RTL/TB，0 error/0 warning，日志唯一 TEST PASS，仿真至 526 ns；扩展 TB 验证两条前缀 word 顺序保持、满队列同拍 pop/push、第三条触发溢出、原帧余量丢弃、原 `frame_end` 与 abort 入队同拍、过早新帧整帧跳过、连续两个损坏帧各自产生唯一 abort 且顺序正确、下一 `frame_start` 恢复，以及 drop/abort 状态异步复位。
- boundary: 已关闭该行为切片中的 overflow 帧中止和恢复合同，但两槽缓存仍不保证持续满载无损；持续背压可以丢弃多个完整帧。该证据不定义下游 DDR3 无效帧回收，不替代真实帧缓存、最终 CDC/RDC 复位审核、PDS/STA 或真实 DDR3/PCIe 集成。

## main OV5640→PCIe M3-B rgb565_axis4 CDC bridge

- implementation_status: behavior_verified_dual_clock_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_cdc_bridge.sv`
- wrapped_module: `rgb565_axis4_async_fifo`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_cdc_bridge.sv`
- contract: 上游/下游独立时钟 ready/valid 边界；staging beat 携带 32-bit data、4-bit keep、last、5-bit user 事件。
- evidence: 2026-09-03 Questa Sim-64 2021.1，独立 3 ns/5 ns 时钟，5 beat 顺序、首末事件、keep/last、ready、最终 drain；0 error/0 warning，唯一 TEST PASS，155 ns。
- defect_fix: FIFO entry 41 bit/实际 42 bit导致 `user[4]` 截断，已修正为完整 42-bit entry。
- boundary: 尚未完成静态 CDC/RDC、RAM 推断、复位释放、三时钟约束、真实 DDR3/PCIe IP 集成。

## main OV5640 M3-B 双时钟 CDC staging 与溢出帧中止

- implementation_status: behavior_verified_dual_clock_staging_abort_recovery_only
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_cdc_staging_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_dvp_rgb565_cdc_staging_pipeline.sv`
- contract: 串接 DVP→灰度→128-bit pack→两槽 word skid→4-byte adapter→双时钟 CDC bridge；staging beat 跨域携带 data、keep、last 与首/末事件。正常期输出 2 个 payload beat 加 1 个 `keep=0` 空载帧尾事件且无 overflow。压力期输入 64 像素并暂停下游，满队列溢出后保留已排队前缀、丢弃当前帧余量，并输出唯一 `keep=0/frame_end=1/protocol_error=1` 中止记录；只有观察原帧尾且中止记录排队后，后续 `frame_start` 才恢复，在此之前到达的新帧整帧跳过。
- evidence: 2026-09-03 联合 TB 使用 5 ns `cam_pclk` 与 7 ns `out_clk`，Questa Sim-64 2021.1 编译 11 个 RTL/TB，0 error/0 warning，日志唯一 TEST PASS，仿真至 2863 ns；压力输出 20 个 beat（含恰好 1 个中止记录），下一帧恢复输出 2 个 beat。
- source_overflow: `source_overflow` 直接绑定两槽 word skid 的 sticky `overflow`，记录本次复位周期曾发生输入损失；它与唯一中止记录共同让损坏帧可识别，但不表示无损，也不自动清除。
- boundary: 仅覆盖该 staging/CDC 行为切片、溢出帧中止和下一帧恢复；未证明中止记录经真实 DDR3/PCIe/主机协议保存或触发无效帧回收，也未证明静态 CDC/RDC、复位释放、RAM 推断、PDS/STA 或 SDF，不等同真实 DDR3/PCIe 闭环通过。

## main OV5640→PCIe M3-B 规范化 PCIe MWR 组合路径

- implementation_status: behavior_verified_combinational_path_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_pcie_mwr_path.sv`
- contract: 串接 staging beat、`rgb565_axis4_mwr_descriptor` 与保持型 `mwr32_req/ack` bridge；`req_length` 是实际 DWORD 数，payload request 固定为 `1`。`keep=0` 控制记录在 descriptor 本地接受，不生成 MWR，不推进 PCIe 字节地址。
- evidence: 2026-09-03 专项 descriptor/path TB 验证 length=`1`、保持型请求和空控制记录本地完成；bridge 与未修改 canonical vendor TX 的隔离动态集成为 136 ns、0 error/0 warning、唯一 TEST PASS。
- boundary: vendor TX 证据只覆盖单 DWORD、`keep=4'hf`、4 字节对齐；该组合路径未实例化新增仲裁器。partial keep、DDR→PCIe 跨域、完整 TX 顶层实例化、PCIe link training、RK3568/主机内存写入未关闭。

## main OV5640→PCIe M3-B 行为级 DDR3/PCIe loopback

- implementation_status: behavior_verified_model_loopback_only
- test_path: `main_ov5640_pcie/tb/tb_ov5640_ddr3_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_pcie_loopback.ps1`
- behavior_path: OV5640 DVP→`ov5640_dvp_rgb565_cdc_staging_pipeline`→`rgb565_axis4_ddr3_write_descriptor`→TB 内 DDR3 数组模型→`rgb565_axis4_pcie_mwr_path`。
- scenario: 正常 3 像素帧形成 2 个 payload 记录和 1 个空载帧尾记录；复位后阻塞 DDR writer，64 像素压力帧形成 21 条记录，唯一 `keep=0/frame_end=1/protocol_error=1` abort 位于索引 20；随后 1 像素恢复帧形成 2 条正常记录。DDR3 模型保存并按序回读全部字段到 PCIe MWR。
- pcie_addresses: 正常帧地址仍为 `0x0ffc/0x1000/0x1002`；压力 epoch 中 abort 和恢复 payload 均从 `0x104c` 发起，证明空载控制记录不推进按有效字节计数的 PCIe 地址。
- evidence: 最新 Questa Sim-64 2021.1 编译为 0 error/0 warning，日志唯一 TEST PASS，仿真至 3858 ns；DDR3 模型在 posedge valid/ready 握手边沿采集写事务，空控制记录不产生 MWR。
- boundary: 已覆盖 overflow 中止记录和恢复帧在 vendor-independent DDR3 模型与 PCIe MWR 路径中的保存、顺序和地址语义；不证明真实 DDR3 地址单位、初始化、AW/W 握手或读口时序，不证明厂商 PCIe IP、TLP、byte-enable、链路、DMA/主机写入，也不证明管脚、电气或板级时序。

## main OV5640→PCIe M3-B vendor-independent 帧提交决策

- implementation_status: behavior_verified_frame_commit_decision_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_frame_commit.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_frame_commit.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_frame_commit.ps1`
- contract: 正常帧输出 committed 描述符；累计协议错误帧输出不可提交描述符。描述符保留该帧第一条记录的 opaque token 与 slot id，并携带 bytes、records 和错误状态；同帧后续记录切换 slot id 会并入协议错误并拒绝提交。模块不产生 drop pulse，后续正常帧仍可恢复。
- tdd_red: 槽号场景先在旧 RTL 上于 47 ns 失败，证明首 slot id 保存与同帧 slot mismatch 检查并非测试既有行为。
- evidence: Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 240 ns；覆盖单记录/多记录首槽号、同帧槽不一致拒绝、半帧统计和待消费描述符的运行中复位。
- boundary: 首 token 仅为 vendor-independent opaque 索引；slot id 已由新顶层连接到分配、读调度和回收，但仍不生成真实 DDR3 物理地址，不实例化 vendor IP，也不证明 DDR3 数据持久化。

## main OV5640→PCIe M3-B 双槽帧控制面

- implementation_status: behavior_verified_double_slot_control_plane_and_pipeline_integration
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_frame_slot_table.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_frame_slot_table.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_frame_slot_table.ps1`
- lifecycle_contract: 正常槽只允许 `FREE→WRITING→QUEUED→READING→FREE`；错误帧从 `WRITING→FREE`，不进入 committed FIFO。
- allocation_contract: `write_alloc_valid` 在 `write_alloc_ready` 前保持 slot id、槽基 opaque token 与记录容量稳定；只有 FREE 槽可被分配为 WRITING。slot table 是容量单一事实源。
- queue_contract: committed 描述符按提交顺序进入深度 2 FIFO；内部 `reader_active` 阻止第二个描述符在首帧 READING 期间出队，任一时刻最多一个槽为活动读者。
- release_contract: `read_done_pulse` 只有在 slot id 匹配 active reader 且目标槽处于 READING 时才释放；错槽、重复或迟到完成只置 `fault_pulse`，不改变槽所有权。
- capacity_contract: `SLOT_RECORD_CAPACITY` 非零且作为单槽记录上限；`records==0`、记录超限或提交策略字段不一致均 fault-drop，不能进入另一槽空间。
- tdd_red: 专项测试先因目标 RTL 不存在而编译失败；加入 reader 独占场景后，旧控制逻辑在连续 `read_desc_ready` 下于 126 ns 错误开放第二描述符。
- evidence: 最终 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 436 ns；覆盖 allocation 的 slot/base/capacity、两槽排队、单 reader、带槽完成、错误帧回收、容量超限 fault-drop 与复用。
- integration_path: 新顶层 `ov5640_dvp_rgb565_ddr3_pcie_pipeline` 已把 slot table 接入 writer、frame commit、带槽 scheduler/done 与 committed MWR 路径。
- boundary: 槽基值仍是 opaque token；不证明真实 DDR3 容量、地址单位、持久化、仲裁/刷新、vendor DDR3 IP、PCIe TLP/DMA/链路、主机内存或板级时序。

## main OV5640→PCIe M3-B frame read scheduler

- implementation_status: behavior_verified_single_outstanding_scheduler_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_frame_read_scheduler.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_frame_read_scheduler.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_frame_read_scheduler.ps1`
- contract: 消费带 slot id 的 committed 描述符，以首 opaque token 为起点、按 records 顺序生成读命令；统一 `read_response_ready/read_response_accepted` 配对和帧完成语义，任一时刻最多一个 response outstanding。命令握手与零延迟响应允许同拍；提前 `frame_end` 或最终计数响应缺失 `frame_end` 时均把该响应归一化为帧尾、置 protocol fault 并完成；`committed && records=0` 不发命令，直接产生 fault-complete。
- completion_outputs: 正常和恢复性协议 fault 均产生单周期 `frame_done_pulse` 与对应 `frame_done_slot_id`；协议归一化或零记录 committed 描述符同时产生 `frame_fault_pulse`。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 346 ns。
- boundary: 命令地址仍是 opaque token，不是 DDR3 物理地址；不实现控制器读事务、仲裁、物理双槽切换或 vendor IP。

## main OV5640→PCIe M3-B committed frame readout gate

- implementation_status: behavior_verified_readout_qualification_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_frame_readout_gate.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_frame_readout_gate.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_frame_readout_gate.ps1`
- contract: 错误帧的单周期 `drop_frame_pulse` 不打开 DDR 读窗口；正常提交帧打开窗口后，只有 scheduler 给出 `read_accept_enable` 才接受并透传响应，统一由 `frame_done_pulse` 关闭当前窗口。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 211 ns；覆盖命令响应配对、完成脉冲关闭窗口和运行中复位。
- boundary: 该 gate 只产生读取资格/窗口语义，不生成 DDR3 读地址或真实读事务，不证明 DDR3 持久化、初始化、仲裁、突发或时序。

## main OV5640→PCIe M3-B committed PCIe MWR 路径

- implementation_status: behavior_verified_committed_mwr_path_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_committed_pcie_mwr_path.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_committed_pcie_mwr_path.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_committed_pcie_mwr_path.ps1`
- parameters: `BASE_ADDR` 定义 vendor-independent MWR 起始地址；`TOKEN_ADDR_STEP` 显式传入 frame read scheduler，仅控制 opaque token 递增。
- contract: 串接 frame commit、单 outstanding frame read scheduler、readout gate 与 MWR path；支持命令/零延迟响应同拍，scheduler 归一化提前或缺失帧尾；错误帧只产生 1 次 `drop_frame_pulse`，不发读命令且不产生 PCIe MWR。
- status_outputs: wrapper 向集成层显式暴露单周期 `frame_done_pulse` 与 `frame_fault_pulse`，正常完成只置 done，恢复性协议 fault 与 committed 零记录同时置 done/fault。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 656 ns；空控制响应不产生 MWR但完成 scheduler/槽回收。
- boundary: wrapper 已传递 slot id 并以带槽 frame done 驱动释放；地址仍为数组模型 opaque token，输出仍为规范化 MWR。不实例化 DDR3/PCIe vendor IP，不证明 DDR3 持久化、PCIe ACK/主机接收、TLP/byte-enable/DMA/链路、RK3568 DMA 或板级时序。

## main OV5640→DDR3模型→PCIe 双槽流水顶层

- implementation_status: behavior_verified_double_slot_model_pipeline_only
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_ddr3_pcie_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_ddr3_committed_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_committed_pcie_loopback.ps1`
- behavior_path: OV5640 DVP→CDC staging→slot table allocation(`slot/base/capacity`)→DDR writer→TB 数组模型→写接受后的 frame commit→双槽提交 FIFO→带槽 scheduler/read done→规范化 PCIe MWR。
- ordering_contract: DDR write 先被下游接受，下一阶段才提交记录；slot table 是每槽容量单一事实源。
- queue_and_reuse: slot0 token `0..2` 与 slot1 token `64..65` 两帧可同时排队；slot0 读完后可重新分配并复用。
- error_recovery: 错误帧在 slot0 产生一次 drop，0 read command、0 MWR；slot1 后续正常恢复并输出。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 4194 ns。
- boundary: DDR3 仅为 TB 数组 token，PCIe 仅为规范化 MWR；不证明 vendor DDR3/PCIe IP、PCIe ACK 或主机接收、RK3568 DMA、链路、电气、时序或板级闭环。

## main OV5640→DDR3模型→已提交 PCIe 单一回归

- implementation_status: behavior_verified_committed_model_loopback_only
- test_path: `main_ov5640_pcie/tb/tb_ov5640_ddr3_committed_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_committed_pcie_loopback.ps1`
- behavior_path: 通过 `ov5640_dvp_rgb565_ddr3_pcie_pipeline` 串接 OV5640 DVP、CDC staging、双槽分配/写入/提交、TB 数组模型、带槽单 outstanding 读调度与规范化 PCIe MWR。
- normal_scenario: slot0 写/读 token `0..2`，slot1 写/读 token `64..65`；两帧按提交顺序排队，slot0 完成后可复用。
- pressure_scenario: 错误帧占用 slot0 后只产生 1 次 drop、0 条 read command 和 0 条 MWR。
- recovery_scenario: slot1 在错误帧后恢复正常读出与 MWR。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 4194 ns。
- boundary: TB 数组仅以 opaque token 建模双槽，PCIe 输出仅为规范化 MWR；不证明 vendor DDR3/PCIe IP、PCIe ACK/主机接收、RK3568 DMA、真实链路或板级时序。

## main OV5640→旧 50H 文件名行为切片：DDR3→PCIe 流水顶层

- implementation_status: behavior_verified_canonical_ddr_to_async_pcie_tx_boundary
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_pg2l50h_pcie_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_pg2l50h_ddr3_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_pg2l50h_ddr3_pcie_loopback.ps1`
- behavior_path: 旧 50H 文件名行为切片，OV5640 DVP→CDC staging→双槽 allocation/write record→待 PG2L100H 复核的 AW/W adapter→公开端口 DDR 模型→AR/R adapter→frame scheduler/readout gate→`core_clk`/`pclk_div2` 异步 mailbox→native/camera 仲裁→未修改 vendor MWR TX。
- metadata_contract: DDR record 第 5 byte 保存 `keep/last/frame_end/protocol_error`，且 `WSTRB[4]=1`；读适配器从相同 bit 位置恢复 sideband，使控制记录和 partial payload 语义跨 DDR 存储边界保留。
- evidence: 2026-09-04 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 `TEST PASS`、仿真至 1086 ns；覆盖 canonical AW/W→AR/R、异步 mailbox、双源仲裁和 vendor MWR TX 的两组 TLP header/data，以及 `ddr_read_port_fault_pulse=0` 的正常链路。
- retained_regressions: 旧 806 ns 同时钟 canonical 边界、双槽数组模型 4194 ns、canonical MWR32 TX 隔离 136 ns、同域 TX 请求仲裁专项/集成 265/205 ns、mailbox 专项 2296 ns、CDC 仲裁集成 385 ns、完整 TX top adapter 专项 385 ns。
- boundary: 未实例化或解密 DDR core。该 1086 ns 流水回归本身未串接完整 TX top；独立 adapter 专项只覆盖请求到 AXIS 输出，不能与本回归拼接外推为真实 DDR3 IP、正式地址单位/物理槽范围、placed-design payload max-delay/bus-skew、CDC/RDC/STA、产品顶层、LTSSM/串行链路、RK3568 主机内存或板级闭环。

## main OV5640→旧 50H 文件名行为切片：DDR3→完整 PCIe TX top 流水顶层

- implementation_status: behavior_verified_single_tb_canonical_ddr_to_complete_tx_top_boundary
- code_path: `main_ov5640_pcie/rtl/ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline.sv`
- test_path: `main_ov5640_pcie/tb/tb_ov5640_pg2l50h_ddr3_pcie_tx_top_pipeline.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_pg2l50h_ddr3_pcie_tx_top.ps1`
- clock_domains: `cam_pclk/cam_rst_n` 采集域、`io_clk/io_rst_n` canonical DDR 与请求策略域、`pcie_clk/pcie_rst_n` 完整 TX top 域；TX adapter 的 camera 源域绑定 `io_clk`，三域独立复位。
- responsibility: 旧 50H 文件名行为切片，组合 `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline` 与 `rgb565_pg2l50h_pcie_tx_top_adapter`，在单一 wrapper 中把 DVP→待 PG2L100H 复核的 DDR AW/W→AR/R→异步 mailbox→完整 `ips2l_pcie_dma_tx_top` AXIS2 MWR 行为串联起来；不构成 50H 平台批准。
- admission_contract: 仅当 `req_keep=4'hf`、`req_length=10'd1`、`req_protocol_error=0` 且 `cross_4kb_boundary=0` 时向 TX adapter 发布 camera MWR32 请求。
- fail_stop_contract: 非法请求不传给 adapter、不获得 ACK、不自动重放；请求保持使路径停住，首次命中产生一个 `tx_policy_fault_pulse`，`tx_policy_fault_sticky` 保持到 `io_rst_n`，恢复要求 camera/IO/PCIe 协调复位。
- completion_contract: `frame_done_pulse` 只表示 DDR 记录读出/请求路径接受，不表示完整 TX top 已发完 TLP，更不表示 PCIe 链路或 RK3568 主机内存完成。
- evidence: 2026-09-04 Questa Sim-64 2021.1：统一 TB 至 1996 ns，0 error/0 warning、日志唯一 `TEST PASS`；覆盖两个帧的 canonical DDR 元数据存取、3 条 full-DWORD MWR32 的 header/data/TLAST、Requester ID、地址连续性、AXIS0/1 静默，以及 partial-DWORD 请求无 ACK fail-stop、policy pulse/sticky 和协调复位清除。
- boundary: DDR 仍是 TB canonical 端口行为模型，PCIe 仍止于完整 TX top 的 AXIS 输出；不覆盖加密 DDR core、正式地址单位/物理槽、placed-design CDC/RDC/STA、LTSSM、串行链路、RK3568 DMA/缓存一致性、主机完成协议、产品顶层或板级闭环。
## PCIe Endpoint AXIS 边界（2026-09-04）

- 项目自有实现：旧 50H 文件名行为切片 `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv`；必须在 PG2L100H Endpoint/IP 下复核。
- 接入合同：`docs/MAIN_OV5640_PCIE_ENDPOINT_INTEGRATION_CONTRACT.md`，冻结时钟/复位所有权、AXIS 方向、配置来源和 camera-only 关断规则。
- 接口事实来自 `pcie_test.v`/`pango_pcie_top.v`：Endpoint 产生 `pclk_div2/core_rst_n`，输出三路 AXIS ready，接收项目 valid/data/last/user；AXIS2 为 MWR。
- camera-only 边界关闭 native、MRD、CPLD、BAR-read 和 restart；bus/device、最大读请求和最大 payload 从产品 Endpoint 配置侧输入。
- 链路状态只透传为观察信号。专项 stub/TB 证明 AXIS 接线与背压，不代表真实 PHY、LTSSM、RX/DBI/APB 或板级闭环。
