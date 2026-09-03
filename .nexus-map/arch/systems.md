> generated_by: Codex manual bootstrap
> verified_at: 2026-09-03
> provenance: current source tree, PDS project files, reports, and root audit notes

# Systems

## PDS 实现与外部仿真规范

- implementation_status: documented
- code_path: null
- evidence_path: `README.md`, `TODO.md`, `docs/SIMULATION_READINESS_MATRIX.md`, `scripts/check_repo_consistency.ps1`, `scripts/compile_simlib.tcl`, `scripts/compile_simlib.ps1`
- evidence_gap: Questa Sim-64 2021.1 工具、Logos2 USIM/VSIM、最小 `V_BUF` 和 PCIe S2-A 历史受控 smoke 均有通过证据；当前 S2-A/S2-B 静态门禁通过，但动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS。摄像头产品目标为 OV5640，C0/C1/C2/C3/S3 尚未完成；OV7725 只作 legacy。
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
- ci_6_status: committed_as_a5d1785
- ci_6_scope: 静态交叉核对 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md` 的模块、参数宽度、128-bit 数据、28-bit 地址、`I_ips_ddr_top` 层级、AXI-like 握手字段及 core 不含 `axi_rready`。
- ci_6_result: 2026-08-30 在 HEAD `a5d1785`（52 个 Git 提交）复验仓库一致性门禁、8 个 PowerShell AST 与 `git diff --check` 均通过。
- ci_6_boundary: 仅保护当前 D3-0-R 静态契约不漂移；PG2L50H DDR3 IP/FDC/RCF 重生成后必须重新核对并审核，不能把当前通过解释为新器件实现或动态验证通过。
- ci_7_scope: `docs/PDS_TCL_ENTRYPOINT_INVENTORY.json` 覆盖全部 13 个 tracked Tcl；逐项记录角色、`set_arch` 次数、器件集合、绝对路径事实和 `run_ps1_entry`。
- ci_7_roles: 角色集合固定为 `canonical_project_build`、`migration_blocked_project_build`、`canonical_support_tool`、`historical_gui`、`vendor_generated_internal`、`vendor_sim_internal`；只有三个项目 `scripts/build.tcl` 可由对应 `run.ps1` 调用。
- ci_7_target_boundary: PCIe `scripts/build.tcl` 已是 `Logos2 / PG2L50H / FBG484 / -6` canonical；OV7725 与 DDR3 `scripts/build.tcl` 仍是 PG2L100H migration-blocked。历史 GUI、厂商内部和厂商仿真脚本的混合器件/绝对路径不构成当前器件或实现证据。
- ci_7_result: 正向 `check_pds_tcl_entrypoints.ps1` 退出 0；删除任一清单项的负向测试退出 1。M2/M3 升格时必须同步清单角色与器件集合。
- h2_b0_scope: PCIe 当前 PG2L50H baseline 将五类问题归一化为 16 个唯一签名、42 次原始记录；baseline 比较完整多重集，新增、消失、改名、share-pin 位置或次数漂移均失败，活动 IDF family/device/package/speedgrade 漂移永久硬失败。
- h2_b0_result: canonical fixture 正向退出 0、strict 退出 1；缺失 UART、重复 UART、Timing 端口改名、share pin 改位和 IDF 改为 PG2L100H 五个变异均退出 1。本批无 RTL、活动 IDF、FDC、厂商 IP 或生成物修改。
- h2_b1_boundary: lane/refclk/PERST#/SCBV/UART/I/O timing 仍需板级资料与决策；H2-B0 不解除发布阻断。
- ci_8_status: PCIe 的 partial/stale evidence 风险已由 CI-8A manifest 关闭；CI-8B 等待 DDR3/OV7725 各自 PG2L50H canonical 升格后迁移，不使用时间戳容差或隐式假设。
- ci_8a_status: PCIe provenance pilot completed on 2026-08-31。
- ci_8a_inputs: `scripts/pds_sources.f` 是 37 个 HDL 的单一有序清单；与 `run.ps1`、`build.tcl`、`build_provenance.ps1`、活动 IDF/FDC 等合计形成 43 项 canonical 输入。
- ci_8a_manifest: 每次 build 以 32 位小写十六进制 `run_id` 原子替换固定 `build/provenance/pds-build.json`；状态为 `running/partial/failed/complete`，只有 `complete` 且 `valid=true` 可进入最终 gate。
- ci_8a_binding: 43 项输入与 full log、timing report、PNR 网表、slow SDF、`.sbit`、`.bin`、`bgr.db` 七项最终证据均绑定相对 POSIX path、length、SHA-256；日志中的唯一开始/完成标志必须与 manifest run_id 一致。
- ci_8a_result: partial compile、PDS executable 缺失、run-id 漂移、产物漂移和 FDC 输入漂移均 gate=1；最新完整 PG2L50H run `c24bc06b5d0643eeb6c9cb2878e7ace5` 为 `gen_bit_stream/complete/valid=true`，绑定 43 inputs/7 artifacts，full build=0、baseline=0、strict=1、slack=`0.100 ns`，H2-B0 16/42 多重集不变。baseline 可复现不解除发布阻断。
- ci_8b_boundary: DDR3 与 OV7725 仅在各自 PG2L50H canonical IP/约束和最终构建入口升格后迁移 provenance；先按项目真实源清单/产物布局独立实现，不抽公共模块。
- ci_9_status: 2026-09-01 implemented_and_verified_sensitive_diff_gate
- ci_9_entry: `scripts/check_sensitive_diff.ps1`；契约文档为 `docs/SENSITIVE_DIFF_GATE.md`，并由 `scripts/check_repo_consistency.ps1` 调用规则自检、`-FullTree` 当前树扫描和 PR merge-base 差异扫描。
- ci_9_scope: 全树模式检查当前 tracked/untracked 工作树，PR 模式检查 merge-base 之后的 changed paths 与 added lines；严格占位符白名单之外，拒绝许可证文件名、Windows/UNC/Unix 绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名及 host id。
- ci_9_self_test: 2 个允许新增行、5 个拒绝新增行、1 个允许文件名、1 个拒绝文件名均按预期判定。
- ci_9_result: 68 个 tracked 日志中的 143 处许可证绝对路径已替换为 `<license-path>`；当前树 `-FullTree` 扫描和 PR 差异扫描均通过。
- ci_9_boundary: 保护当前版本并阻止后续重新引入，不读取或输出实际许可证配置；本批不改写 Git 历史，历史清理和任何历史重写必须独立审核。
- hardware_target_decision: 用户于 2026-08-30 确认三个项目共用 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`；统一 PDS 目标为 `Logos2 / PG2L50H / FBG484 / -6`。
- legacy_100h_boundary: 全部 PG2L100H PDS/STA/网表/位流仅保留为历史证据，不得烧录或作为实板验收；三个项目必须分别建立 PG2L50H 新 baseline。
- ci_0_boundary: 仅为仓库结构与文档静态一致性门禁，不启动或替代 PDS 构建、STA、项目严格 gate 或四级仿真。
- simulation_readiness_status: Questa 2021.1 tools and Logos2 USIM/VSIM verified historically; PCIe S2-A historical controlled smoke PASS retained; current S2-A/S2-B static gates pass but dynamic revalidation exits 4 on external license checkout; DDR3 and OV5640 project suites remain pending
- simulation_asset_boundary: `ipcore/`、`ip_core/`、`ip_backup/` 内的 DDR3、PLL、FIFO 和 PCIe RC/EP testbench/filelist/DO 均为厂商示例，只能作为模型与接口参考；不得改名或直接计入 `ov7725_hdmi`、`ddr3_bringup_top` 或 `pcie_dma_test` 的集成覆盖。
- simulation_common_gap: PCIe S2-A 保留项目自有 TB、相对路径 filelist/DO 与历史唯一 `TEST PASS`；当前动态复验未产生新 PASS。DDR3/S1 与 OV5640/S3 仍缺项目级入口，PCIe S2-B 动态/S2-C 及三项目后级网表/SDF 仿真仍未完成。
- next_step: 恢复仓库外许可证后以新 run id 复验 S2-A，再进入 S2-B 动态和 S2-C；摄像头产品按 C0/C1/C2/C3/S3 推进 OV5640，不延续 OV7725 产品主线。
- s0_0_recheck: 2026-08-30 的未发现仿真器结论已被 2026-09-01 的实际 Questa 执行、USIM 编译与 PCIe S2-A 动态 PASS 取代。

## Verilog/SystemVerilog 注释规范

- implementation_status: documented
- code_path: null
- evidence_path: `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`
- evidence_gap: 现有厂商代码和历史 RTL 尚未进行全量合规检查。
- responsibility: 约束后续手写 RTL 的意图、接口、FSM、复位、CDC/RDC 和风险注释。

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
- responsibility: 将 4-byte staging beat 规范化为 vendor-independent PCIe Memory Write request descriptor，按 byte count 递增地址并转发 keep/last/frame_end。
- verification: TB 覆盖地址递增、`keep`、`last`、`frame_end` 与 4KB 边界标志；使用 `BASE_ADDR=0xffc` 验证跨界请求标记。
- boundary: 仅验证规范化描述符字段与 4KB 边界指示，不接厂商 PCIe IP，不定义 TLP 编码、最大 payload、DMA 完成、DDR3 地址或主机协议。

## main 独立 OV5640→PCIe normalized DDR3 write record

- implementation_status: behavior_verified_vendor_independent_ddr_record_only
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_ddr3_write_descriptor.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_ddr3_write_descriptor.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ddr3_write_descriptor.ps1`
- responsibility: 按帧接收 slot table 分配的 `slot/base/capacity`，生成单 beat 128-bit 数据、16-bit strobe 的 vendor-independent normalized DDR3 write record。
- allocation_contract: allocation 的 slot id、槽基 opaque token 与记录容量在握手时装载；slot table 是容量单一事实源，writer 只执行所分配容量的地址约束。
- integration_contract: writer 在背压期间保持记录稳定；新流水顶层在 writer 外执行“DDR write 接受后再向 frame commit 提交”的两阶段交付。
- address_contract: `write_addr` 从本帧 allocation base 起步，按 opaque `ADDR_STEP` 推进；该步长不解释为任何物理地址单位。
- regression_2026_09_03: Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 `TEST PASS`，仿真至 251 ns；覆盖 allocation 的 slot/base/capacity、背压字段保持、容量边界与恢复。
- boundary: 不假定地址单位、初始化行为或 AXI4 burst 语义；不接 vendor DDR3 IP。

## main 独立 OV5640→PCIe MWR bridge

- implementation_status: behavior_verified_audited_pin_bridge_provisional
- code_path: `main_ov5640_pcie/rtl/rgb565_axis4_pcie_mwr_bridge.sv`
- test_path: `main_ov5640_pcie/tb/tb_rgb565_axis4_pcie_mwr_bridge.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_pcie_mwr_bridge.ps1`
- responsibility: 将规范化请求映射到已审计的 `mwr32_req/ack`，统一锁存 `req_length/req_addr/req_data/req_keep/cross_4kb_boundary` 及 `last/frame_end/protocol_error`，并在 ack 前保持全部字段稳定。
- evidence: 2026-09-03 Questa Sim-64 2021.1 独立 TB 为 0 error/0 warning、唯一 TEST PASS、76 ns；输入事件字段在 busy 期间变化不会污染当前请求。
- boundary: `req_keep` 的 byte-enable 映射仍为临时合同；模块位于 vendor PCIe hierarchy 之外，不代表真实 PCIe TLP/DMA 通过。

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
- m3a_constraint_gap: 旧 `ddr3_ip.rcf` 层级与当前集成层级不一致，历史记录只处理 0 条 net；M3-B 必须证明 RCF 被加载且对象命中，并重新审核 FDC、wrapper、clock object 和全部板级 I/O。
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
- next_step: 保留 OV7725 legacy 证据不改名；只有在 OV5640 C0/C1 完成后，才能于 C2 逐项审核哪些 DDR3/HDMI、CDC/RDC 或复位结构可迁移，新产品 IP/约束必须在 C3 独立建立。

## OV5640 摄像头 HDMI 产品目标

- implementation_status: target_scoped_pending_reference_audit
- code_path: null
- evidence_path: `docs/OV5640_TARGET_SCOPE.md`
- product_boundary: 产品摄像头为 OV5640，目标板卡与器件为 `RK3568+PG2L50H100H` / `PG2L50H-6IFBG484`；现有 `41_ov7725_hdmi` 不属于产品实现。
- c0_boundary: 只读导入并审计参考工程的源、IP、约束、顶层、器件元数据和绝对路径，不覆盖 canonical。
- c1_boundary: 冻结单/双摄、模组料号、MCLK、RESET/PWDN、I/O 电压、管脚、DVP 位宽/极性、输出格式、分辨率、帧率与字节序。
- c2_boundary: 设计新的项目目录与顶层，形成 OV5640 SCCB/寄存器配置、读 ID 自检、采集、DDR3 帧缓存和 HDMI 输出迁移方案。
- c3_boundary: 所有 IP/约束按 `Logos2 / PG2L50H / FBG484 / -6` 重新审核或生成，完成七阶段 PDS 与严格 gate；旧 100H 产物不可继承。
- s3_boundary: 建立 OV5640 项目级自检 TB、相对路径 filelist/DO，并依次关闭行为级、综合后、PNR 功能和 PNR 时序仿真；公共 Questa/USIM/VSIM 证据不等于产品通过。
- next_step: 先完成 C0 参考工程可访问性与只读审计，再由 C1 冻结产品范围；C0/C1 未完成前不修改活动 RTL、IP 或约束。
- high_attention: `i2c_dri_clk` 逻辑生成时钟、`cam_pclk`/DDR `ui_clk`/`pixel_clk` 间业务 CDC、FIFO 分侧复位，以及 `ddr3_init_done` 参与的复位释放。

## DDR3 外层工程

- implementation_status: bringup_full_implementation_baseline
- code_path: `ddr3_test/ddr3_test/`
- project_path: `ddr3_test/ddr3_test/ddr3_test.pds`
- evidence_path: `ddr3_test/ddr3_test/scripts/regenerate_ip.ps1`, `ddr3_test/ddr3_test/doc/M2_IP_REGENERATION.md`, `ddr3_test/ddr3_test/doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`, `ddr3_test/ddr3_test/build/logs/pds-gen_bit_stream.log`, `ddr3_test/ddr3_test/build/pds/report_timing/test_ddr.rtr`, `ddr3_test/ddr3_test/scripts/check_build.ps1`
- evidence_gap: M2-B1 已纠正 PG2L50H staging 生成路径并完成参数/资产差异审计，但 canonical IP/FDC/RCF 仍是旧 PG2L100H 输入，旧全流程、STA、网表、SDF 和位流不可烧录实际板卡。板级 DDR3 参数、28 项 FDC pin 差异、canonical 升格、CI-6、50H 空目录七阶段、D3-0-R 与 D3-A/B/C 均未验收。
- responsibility: 当前以厂商 `test_ddr` 作为临时 DDR3 board bring-up 顶层；后续必须明确真正产品顶层和板级功能范围。
- hardware_target: `RK3568+PG2L50H100H` / `PG2L50H-6IFBG484` / `Logos2 / PG2L50H / FBG484 / -6`
- m2_active_input_audit: 活动 `ip_core/ddr3/ddr3.idf` 为 `PG2L100H`、生成器 `2022.2-SP6.4`；canonical FDC/RCF 为 `ip_core/ddr3/pnr/ddr_test.fdc` 与 `ip_core/ddr3/pnr/ddr3.rcf`；`ip_core/ddr_test.fdc` 是旧外层参考，不能直接升格。项目自有 `scripts/build.tcl` 与 `scripts/check_build.ps1` 也仍按 `PG2L100H`，待 50H 资产落地后再修正。
- m2_legacy_50h_audit: `ip_backup/20250108100125/ddr3/ddr3.idf` 为 `PG2L50H`，但生成器是 `2022.2-SP6.1`；仅可作为参数/硬宏差异 oracle，禁止直接恢复或复制到活动输入。
- m2_a_staging: `2026-08-30` 使用 `scripts/regenerate_ip.ps1` 在 `build/ipgen/pg2l50h` 调用 SP6.4 build 146967，目标 `Logos2/PG2L50H/FBG484/-6`，结果 `0 error(s), 0 warning(s)`；canonical IDF SHA-256 保持 `6CB70BF0954100B4797197A47F20496AD74945995E12B30FA040870EE3366C47`。
- m2_b1_derived_parameter: PDS SP6.4 `ui.tcl` 定义 `DEVICE_100H_EN` 为隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`；直接 `-device` 覆盖旧 100H IDF 会错误保留 `true` 并生成 PPLL `FALSE/CLKOUTF` 分支，已明确禁止。
- m2_b1_seed_regeneration: 活动 100H IDF 与 SP6.1 50H seed 的参数仅 `DEVICE_100H_EN` 不同；更新后的 `scripts/regenerate_ip.ps1` 先验证 seed 参数一致，再由 SP6.4 build 146967 重生成，结果 `DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，canonical 哈希保持不变。
- m2_b1_diff: 正确 PG2L50H staging 的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均不同；wrapper 端口 `21 → 26`，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`；FDC 有 28 项 pin 差异。
- m2_status: seed_parameter_validation_and_sp6_4_staging_verified_pending_board_evidence_and_canonical_promotion
- m2_gate: 取得原理图/BOM并锁定板级 DDR3 颗粒/组织/PCB 参数 → 审核 28 项 FDC pin 差异及 wrapper/PHY/filelist/IDF → 升格 canonical → 重跑 CI-6 → 清空 `build/` 完成七阶段与器件交叉检查 → 重审 D3-0-R，获审后才可进入 D3-A。M2-B1 未授权 canonical 替换、D3-A 或烧录。
- d3_0_read_only_review: `2026-08-30` 已确认活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`；公开端口包含 `ddr_init_done`、`core_clk` 和自定义 AXI-like AW/W/AR/R 接口。`test_ddr.v` 的物理 board wrapper 实例名 `I_ips_ddr_top` 必须保持不变。
- d3_0_status: legacy_contract_review_complete; PG2L50H IP/FDC/RCF regeneration and D3-A re-review required
- d3_0_handshake_contract: 写地址以 `axi_awvalid && axi_awready` 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读请求以 `axi_arvalid && axi_arready` 接受，核心用 `axi_rvalid`/`axi_rlast` 返回且没有 `axi_rready`。D3-A 按该非标准 AXI-like 契约实现；若 IP 重生成后语义、地址单位或层级变化则停止并重新审核。
- d3_0_boundary: 只更新文档和评审事实；D3-0 不修改 RTL、活动 IP、FDC/RCF 或构建脚本。
- d3_0_r_port_map: 提交 `2fd7c51` 新增 `D3A_PORT_MAP.md`，提交 `a5d1785` 的 CI-6 进一步静态交叉核对 core/wrapper/document；该契约属于旧 IP 事实，PG2L50H 重生成后必须重新运行门禁并审核，D3-A 之前不得修改厂商 IP 或物理端口。
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
- next_step: M2-B1 已确认隐藏派生参数语义并生成正确 50H staging；先依据原理图/BOM审核 28 项 FDC pin 差异和新增 wrapper 状态端口，再决定 canonical 升格。升格后重新核对握手、地址单位、端口和 `I_ips_ddr_top` 层级；重新审核 D3-A 后才可按 D3-A → D3-B → D3-C 实现项目自有 RTL

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
- evidence_gap: 活动 `pcie_test.idf`、build/PDS/gate 与产物已统一为 PG2L50H；S2-A 保留历史动态 PASS，当前 S2-A/S2-B 静态门禁通过。当前动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS；真实 RC/EP、DMA、板级证据和后级网表/SDF 仍缺失。
- responsibility: 集成 PCIe x2 IP、DMA、RAM/FIFO 与 UART2APB 管理路径。
- build_entry: `pcie_dma_test_100h/scripts/run.ps1`
- build_definition: `pcie_dma_test_100h/scripts/build.tcl`
- build_gate: `pcie_dma_test_100h/scripts/check_build.ps1`
- h2a_read_only_evidence: `2026-08-30`；顶层端口为 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；FDC 映射 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。
- h2a_status: completed_read_only_evidence_matrix; H2-B 仍待板级资料和审核
- h2a_constraint_gaps: FDC 未提供 lane 极性、板级拓扑、I/O delay 或 SCBV；`pcie_test.idf` metadata、build/PDS/gate 与新产物已与实物目标 `Logos2 / PG2L50H / FBG484 / -6` 一致，HSSTLP 资源为 PDS 模板指定的 `HSSTLP_292_612`。
- h2a_uart_gap: UART2APB 使用隐式 `rxd/txd` 网络，当前 `rxd` 被绑 0；该功能缺口不因 PDS/STA 成功而关闭。
- h2a_boundary: 器件型号已获用户审核；活动 PCIe IDF 不需仅因型号重生成。M1 已修改项目自有 build/gate，并依据 PDS 模板迁移 HSSTLP 资源后重建生成物；RTL/FDC 其余内容仍受 UART 与板级证据审核约束。
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
- contract: 串接 staging beat、`rgb565_axis4_mwr_descriptor` 与临时 `mwr32_req/ack` bridge；活动控制器事实为 `req_length` 按 DWORD，控制器边界将 `req_length=0` 判断为 `0x1000` 字节；当前组合路径每个 32-bit beat 仍发 `req_length=0`。
- evidence: 2026-09-03 专项 TB 使用 `BASE_ADDR=0x0ffc`，首请求等待 ack 时 descriptor 预取下一条带帧尾/错误记录，当前请求全部字段仍保持；ack 后地址为 `0x1000`。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 TEST PASS、115 ns。
- boundary: 不实例化厂商 PCIe IP；不证明真实 TLP、DMA、byte-enable、链路或主机输出。

## main OV5640→PCIe M3-B 行为级 DDR3/PCIe loopback

- implementation_status: behavior_verified_model_loopback_only
- test_path: `main_ov5640_pcie/tb/tb_ov5640_ddr3_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_pcie_loopback.ps1`
- behavior_path: OV5640 DVP→`ov5640_dvp_rgb565_cdc_staging_pipeline`→`rgb565_axis4_ddr3_write_descriptor`→TB 内 DDR3 数组模型→`rgb565_axis4_pcie_mwr_path`。
- scenario: 正常 3 像素帧形成 2 个 payload 记录和 1 个空载帧尾记录；复位后阻塞 DDR writer，64 像素压力帧形成 21 条记录，唯一 `keep=0/frame_end=1/protocol_error=1` abort 位于索引 20；随后 1 像素恢复帧形成 2 条正常记录。DDR3 模型保存并按序回读全部字段到 PCIe MWR。
- pcie_addresses: 正常帧地址仍为 `0x0ffc/0x1000/0x1002`；压力 epoch 中 abort 和恢复 payload 均从 `0x104c` 发起，证明空载控制记录不推进按有效字节计数的 PCIe 地址。
- evidence: 最新 Questa Sim-64 2021.1 编译为 0 error/0 warning，日志唯一 TEST PASS，仿真至 3900 ns；DDR3 模型在 posedge valid/ready 握手边沿采集写事务。
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
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 696 ns。
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
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 4264 ns。
- boundary: DDR3 仅为 TB 数组 token，PCIe 仅为规范化 MWR；不证明 vendor DDR3/PCIe IP、PCIe ACK 或主机接收、RK3568 DMA、链路、电气、时序或板级闭环。

## main OV5640→DDR3模型→已提交 PCIe 单一回归

- implementation_status: behavior_verified_committed_model_loopback_only
- test_path: `main_ov5640_pcie/tb/tb_ov5640_ddr3_committed_pcie_loopback.sv`
- script_path: `main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_committed_pcie_loopback.ps1`
- behavior_path: 通过 `ov5640_dvp_rgb565_ddr3_pcie_pipeline` 串接 OV5640 DVP、CDC staging、双槽分配/写入/提交、TB 数组模型、带槽单 outstanding 读调度与规范化 PCIe MWR。
- normal_scenario: slot0 写/读 token `0..2`，slot1 写/读 token `64..65`；两帧按提交顺序排队，slot0 完成后可复用。
- pressure_scenario: 错误帧占用 slot0 后只产生 1 次 drop、0 条 read command 和 0 条 MWR。
- recovery_scenario: slot1 在错误帧后恢复正常读出与 MWR。
- evidence: 2026-09-03 Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 TEST PASS、仿真至 4264 ns。
- boundary: TB 数组仅以 opaque token 建模双槽，PCIe 输出仅为规范化 MWR；不证明 vendor DDR3/PCIe IP、PCIe ACK/主机接收、RK3568 DMA、真实链路或板级时序。
