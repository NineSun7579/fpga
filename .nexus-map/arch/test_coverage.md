> generated_by: Codex manual bootstrap
> verified_at: 2026-09-02
> provenance: existing PDS logs/reports, simulation runs, artifact gates, CI-9 self-tests and real-branch sensitive-diff scan

# Test Coverage

## 证据等级

- 已验证：当前文件或报告直接证明。
- 静态发现：源码、工程配置或日志可直接观察，但本轮没有重新运行工具。
- 未验证：缺少可执行资产、工具环境或运行记录。

## S0 环境与仿真库验证（截至 2026-09-01）

- 历史证据：2026-08-30 环境复核未发现仿真器；该结论已被后续实际执行证据取代。
- 已验证：S0-1 参数化入口 `scripts/compile_simlib.tcl` 与 `scripts/compile_simlib.ps1` 已提交；PowerShell AST 错误数为 0。入口支持 ModelSim/QuestaSim、USIM/VSIM/BOTH、family、语言、PDS/仿真器路径和输出目录覆盖，强制检查三项仿真器可执行文件，并检查 PDS 退出码、日志 `^E:` 与所选库目录。
- 已验证：Questa Sim-64 2021.1 最小 SystemVerilog 通过；PDS SP6.4 Logos2 USIM/VSIM 均编译成功。VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 目录非空。
- 已验证：最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- 当前复验：S2-A/S2-B 静态门禁通过；S2-A 当前 Questa run `add7efa39f644384af9929e8a9366739` 运行至 `1476105 ns`，Errors 0、Warnings 0、唯一 `TEST PASS`、退出 0。S2-B run `30bad6e164be4a4b8284a00f1e96bd87` 编译/elaboration 成功，输出唯一 link-up marker 与唯一 `TEST PASS`，Errors 0、Warnings 26、PowerShell 退出 0。
- 未验证：PCIe PNR 时序/SDF，以及 DDR3/OV5640 项目后级仿真；S2-E PNR 功能通过不等于这些层级通过。

## CI-0 仓库级静态一致性门禁（2026-08-30）

- 已验证：新增 `scripts/check_repo_consistency.ps1`，覆盖根指南/TODO/VSCS、三个项目 README、PDS 构建入口、顶层声明、七阶段命令、可配置工具路径、退出码、baseline 开关、产物/时序检查接口和 `build/` 忽略状态。
- 已验证：三个项目 README 的 PDS `2022.2-SP6.4`、顶层模块或仿真状态缺口已修正；门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 已验证：仓库内全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- 边界：CI-0 不启动 PDS 或 ModelSim/QuestaSim，不替代项目严格 gate、STA 或四级仿真。

## CI-2 板级证据清单完整性门禁（2026-08-30，2026-09-02 扩展）

- 已验证：提交 `677808d` 最初将 OV7725 legacy、DDR3、PCIe 三个存量目录纳入门禁；2026-09-02 的扩展又将双 OV5640 文档型项目骨架纳入 `scripts/check_repo_consistency.ps1`，四个目录均要求对应 README 直接链接板级证据清单。
- 已验证：OV7725、DDR3、PCIe、双 OV5640 清单均包含“当前工程事实”“必须提供的资料”“关闭条件”；OV7725 继续明确为 legacy。
- 已验证：原始 HEAD `677808d` 与 2026-09-02 当前扩展工作树的仓库一致性门禁均退出 0；当前运行明确输出 `INFO: dual OV5640 C1-A product boundary checked` 和 `INFO: repository consistency gate passed`。
- 边界：CI-2 当前只证明四份清单的结构、关键词和 README 链接完整；双 OV5640 项目尚无 RTL/IP/FDC/TB，C1/H3 仍阻断，也不证明任何清单中的板级资料已提交、审核或与实物一致。

## CI-3 项目 README 元数据完整性门禁（2026-08-30）

- 已验证：提交 `5bfaae9` 扩展 `scripts/check_repo_consistency.ps1`，对 OV7725、DDR3、PCIe 三个项目 README 统一检查器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断七类元数据。
- 已验证：当前 HEAD `5bfaae9` 上仓库一致性门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 边界：CI-3 仅检查 README 中已有事实的可追溯表达和入口特征，不验证器件/板级参数是否真实或已审核，不替代 PDS、STA、SCBV、板级证据或四级仿真。

## CI-4 PDS 构建 gate 契约完整性门禁（2026-08-30）

- 已验证：提交 `66356aa` 扩展 `scripts/check_repo_consistency.ps1`，对三个项目 `run.ps1` 检查 PDS 进程退出码、`^E:` 错误记录和阶段完成处理。
- 已验证：同一门禁对三个项目 `check_build.ps1` 检查阶段或最终构建入口、时序摘要解析/结论、`throw` 失败路径、非零产物检查及 `AllowKnownBaselineIssues` 显式开关；当前 HEAD `66356aa`、44 个 Git 提交上门禁退出码为 0。
- 边界：CI-4 只验证 gate 代码路径存在和静态契约，不执行真实 PDS、STA、位流或仿真；baseline 放行仍明确不可发布。

## CI-5 PowerShell AST 语法门禁（2026-08-30）

- 已验证：提交 `5769d8f` 扩展 `scripts/check_repo_consistency.ps1`，自动递归解析全部非 `build/`、`.git/` 的 `.ps1` 文件，并报告具体语法错误文件、行号和消息。
- 已验证：当前 HEAD `5769d8f` 共扫描 8 个 PowerShell 脚本，AST 解析错误数为 0，仓库一致性门禁通过。
- 边界：CI-5 只证明 PowerShell 语法可解析，不执行或替代 PDS、STA、位流生成、ModelSim/QuestaSim 或项目动态仿真。

## CI-6 DDR3 D3-0-R/M 契约一致性门禁（2026-09-02）

- 已验证：提交 `a5d1785` 扩展 `scripts/check_repo_consistency.ps1`，交叉读取 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md`。
- 已验证：门禁检查模块/参数声明、128-bit 数据和 28-bit 地址证据、`I_ips_ddr_top` 层级、AXI-like 握手字段，并在 core 出现 `axi_rready` 时失败；HEAD `a5d1785`、52 个 Git 提交上门禁和 8 个 PowerShell AST 均通过。
- 边界：CI-6 只保护旧活动 DDR3 IP 的静态契约；PG2L50H IP/FDC/RCF 重生成后必须重新核对并审核，不能替代 compile、STA 或动态仿真。

## CI-7 PDS Tcl 入口分类门禁（2026-08-30）

- 已验证：`docs/PDS_TCL_ENTRYPOINT_INVENTORY.json` 登记全部 14 个 tracked Tcl；新增 DDR3 `scripts/build_staging_compile.tcl` 为非发布 `canonical_support_tool`，清单继续记录六类角色、`set_arch` 次数、器件集合、绝对路径和 `run_ps1_entry`。
- 已验证：只有三个项目 `scripts/build.tcl` 由 `run.ps1` 调用；PCIe 为 PG2L50H canonical，OV7725/DDR3 仍为 PG2L100H migration-blocked。
- 已验证：正向门禁退出码为 0；删除任一清单条目的负向测试退出码为 1。历史 GUI、厂商内部和厂商仿真 Tcl 不得用于器件身份、STA、网表、SDF、位流或集成仿真通过证明。
- 边界：CI-7 仅验证 tracked Tcl 分类和入口事实，不执行 PDS、IP Compiler、STA、位流或 ModelSim/QuestaSim。

## PCIe H2-B0 精确 baseline（2026-08-30）

- 已验证：五类已知问题归一化为 16 个唯一签名、42 次原始记录；baseline 按完整多重集比较，签名新增、消失、改名、share-pin 位置变化或次数漂移均失败。
- 已验证：活动 PCIe IDF 的 family/device/package/speedgrade metadata 漂移为永久硬失败，不受 baseline 放行参数影响；canonical fixture 正向退出 0、strict 退出 1，5 个变异 fixture 均退出 1。
- 外部阻断：H2-B1 仍需 lane/refclk/PERST#/SCBV/UART/I/O timing 的板级证据与决策。H2-B0 发现的 partial run 复用旧 full-build 日志/产物风险已由 CI-8A 的同次运行证明关闭。
- 边界：本批没有 RTL、活动 IDF、FDC、厂商 IP 或生成物修改；H2-B0 只保护失败基线不漂移，不代表 PCIe 可上板或可发布。

## PCIe CI-8A 构建证据绑定（2026-08-31）

- 已验证：37 个 HDL 由 `scripts/pds_sources.f` 单一有序清单驱动；`run.ps1` 中 build-scoped Questa launcher 属于 canonical 输入，合计 43 项 canonical 输入和 7 项最终证据均以相对 POSIX path、length 和 SHA-256 写入固定 manifest。launcher 变更必须触发完整构建证据重绑定。
- 已验证：每次 build 的 32 位 run_id 原子失效旧证据；`running`、`partial`、`failed` 均无效，只有完整 `gen_bit_stream` 的 `complete/valid` 可继续 gate。
- 负向覆盖：真实 partial compile、PDS executable 缺失、run-id 漂移、产物字节漂移与 FDC 输入漂移均返回 1，证明旧 full-build 证据不能复用。
- 正向覆盖：最新完整 PG2L50H run `9952da4164f040d5924a558baa5cd8ca` 的 manifest 为 `complete/valid=true`，绑定 43 inputs/9 artifacts；baseline 返回 0、strict 返回 1，不表示 release-ready。
- 边界：本批未修改 RTL、活动 IDF、FDC 或厂商 IP；CI-8B 等待 DDR3/双 OV5640 各自 PG2L50H canonical 升格，并按产品项目独立实现，不抽公共模块。OV7725 不再升格。

## CI-9 许可证敏感差异门禁（2026-09-01）

- 已验证入口：`scripts/check_sensitive_diff.ps1 -FullTree` 扫描当前 tracked/untracked 工作树；PR 模式以指定基线和 `HEAD` 的 merge-base 为起点，扫描 changed paths 与 added lines。`docs/SENSITIVE_DIFF_GATE.md` 固化使用方法与边界。
- 已验证规则：严格占位符白名单之外，许可证文件名、Windows/UNC/Unix 绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名与 host id 均返回非零。
- 自检覆盖：2 个允许新增行、5 个拒绝新增行、1 个允许文件名和 1 个拒绝文件名均按预期判定。
- 当前树覆盖：68 个 tracked 日志中的 143 处许可证绝对路径已替换为 `<license-path>`；`-FullTree` 扫描通过，PR 差异扫描也通过。
- 边界：全树门禁保证当前版本不再包含规则覆盖的敏感路径或内容，差异门禁阻止后续重新引入；两者均不读取或打印实际许可证配置，也不改写 Git 历史。

## S0-0-R 仿真器环境复核（2026-08-30）

- 已验证：提交 `ef5cc9a` 再次探测 PATH、常见安装目录和 `vsim.exe` 文件名，`vsim.exe`、`vlog.exe`、`vlib.exe` 均未发现。
- 边界：仅更新 S0-1 阻断证据，未执行 `compile_simlib`、PDS 或动态仿真。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| 双 OV5640 摄像头 HDMI | C0 已完成只读审计且 Import=none；已建立 README/BOARD_EVIDENCE 文档骨架，C1/H3 仍 blocked，尚无 RTL/IP/FDC/PDS/TB | 参考根 PDS 与 4 个必要 IP 为 PG2L100H；FDC 缺 I/O delay，PG2L50H 产品 STA 未建立 | C0 已审计 4 个参考 TB，但未导入；其中一项 force init 且无 canonical PASS | 新产品网表尚未生成 | 新产品 PNR 网表尚未生成 | 新产品 SDF 尚未生成/标注 |
| DDR3 外层 | 旧 PG2L100H 七阶段与五类产物已完成，但不可用于实际 PG2L50H；需重生成 50H IP/FDC/RCF | 旧 100H `All Constraints Met` 只保留历史；50H STA 未执行 | D2/D3-0 旧契约已定，PG2L50H 重生成后须重审；S1 项目级入口缺失 | 旧网表不可签核 | 旧 PNR 网表不可签核 | VSIM/SDF 未验证，旧 100H 结果不可签核 |
| PCIe DMA | PDS run `9952da4164f040d5924a558baa5cd8ca` complete/valid，43 inputs/9 artifacts | timing/SDF 已生成；strict gate 仍失败 | S2-A/S2-B 动态 PASS | S2-D 受限 smoke PASS | S2-E run `927abae8ed7d40aeb5d6f706b3723e0a` 动态 PASS | S2-F 已执行；SDF 标注成功，但 2 errors、退出 1，GLS/STA 冲突且负时序模型语义不完整，blocked |

## S1/S2/S3 仿真就绪度矩阵（2026-08-30）

- 已验证盘点：`docs/SIMULATION_READINESS_MATRIX.md` 已逐项目记录项目级 testbench、filelist、DO、厂商示例和四级仿真前置条件；PCIe S2-A 已实际执行 Questa 动态 smoke。
- DDR3 与 OV7725 的项目级资产仍为 `project_tb=0`、`project_f=0`、`project_do=0`。PCIe 已具备 S2-A/S2-B 两套项目 filelist/DO 定义、项目集成 TB、受控边界模型和真实 RC/EP TB；S2-A 与 S2-B 均已动态 PASS。
- 双 OV5640/S3：C0 已在 `docs/OV5640_C0_REFERENCE_AUDIT.md` 完成逐文件审计；`59_top_dual_ov5640_hdmi/` 当前只有 README/BOARD_EVIDENCE 文档骨架，17 个明文 RTL、4 个 TB、4 个 PCIe video 参考文件和 4 个 PG2L100H 生成 IP 均未导入。C1/H3 输入冻结后才允许选择性导入实现资产；4 个参考 TB 当前均不计覆盖，`tb_dual_ov5640_dri.v` 的 force 初始化与非 canonical 成功字符串必须整改。
- 仿真归档边界：新项目 `.f/.do/TB` 只进入 `59_top_dual_ov5640_hdmi/sim/questa/`，运行态只进入其 `build/`；`41_ov7725_hdmi/sim/questa/` 仅 legacy。`sim_*`、work、mpf、ini、日志、波形、绝对路径生成物和许可证配置均不得导入。
- DDR3/S1：现有厂商 `test_ddr`/memory-model 资产端口失配且含绝对路径与 FSDB/Verdi 假设。进入 S1 前必须关闭 S0-1、重生成并复核 PG2L50H DDR3 IP/FDC/RCF、完成 D3-A/B/C 与 D4，并提供项目自有有限 BIST/top 与自检 TB。
- PCIe/S2：S2-A 已用项目级 `tb_pcie_dma_test` 实例化产品顶层，并以受控 `pcie_test` 边界动态验证顶层/复位/LED/未知态；现有 `pango_pcie_top` RC/EP testbench 仍不实例化产品顶层，只能在 S2-B 中作为真实 RC/编译顺序 oracle；S2-C 才验证 DMA。
- 验收边界：`ipcore/`、`ip_core/`、`ip_backup/` 中的厂商示例只能作为参考证据，不能计入产品集成覆盖，也不能通过改名冒充项目自有 testbench。
- 四级共同门槛：所有入口使用相对路径 filelist/DO 和项目自有集成 TB；必须具备超时、`$fatal`、唯一 `TEST PASS` 与可靠非零失败退出；PNR 时序仿真必须按实际 DUT 实例层级标注 SDF。
- PCIe/S2-C BAR1：`check_s2c_bar1` 已覆盖动态 XML 生成/解析、唯一允许差异（Enable false→true、Size 256→512 Bytes）、`MASK_EN=false`/`MASK=31'h0` 保持，以及 canonical IDF/wrapper SHA 不变。损坏 mask 与缺 `index.xml` 的负向测试均按预期失败；旧 dry-run 的非法 `BAR1_MASK=31'h0(` 不再允许。
- 输入证据缺口：17 个实时 origin 分支、完整历史/reflog、工作区和 SP6.4 安装均无匹配 PCIe 1.2c `index.xml`；完整实例还必须匹配 IP ID `042004`、build `146967`、`PG2L50H/FBG484/-6`。因此 canonical BAR1 仍关闭，S2-C 未通过。
- PCIe/S2-C 归档诊断：run `d1d25d3f23384590918f26abbfd2e839` 已动态覆盖 RC 主动 EP BAR0 写入/读回，运行至 `710535 ns`，0 errors、26 vendor warnings、唯一成功 marker 与唯一 `TEST PASS`、退出 0。覆盖边界不包含 Endpoint 主动 MRd/CplD/MWr DMA 闭环，不能关闭 BAR1/`index.xml` 阻断或升格 S2-C。
- 公共状态：三个项目的可复现工程源均留在各自 `sim/questa/`，运行态只进入各工程 `build/`。PCIe S2-E PNR 后功能已动态通过；S2-F 工程已归档并执行，但保持 blocked。DDR3/S1、OV5640/S3 与 S2-C 仍未完成。

## PCIe S2-D 综合后受限 smoke（2026-09-01，动态通过）

- 工程归档：`sim/questa/post_syn.f`、`run_post_syn.do` 与 `tb/tb_pcie_dma_post_syn.sv` 保存在 PCIe 项目内；work/vendor library、launcher ini、日志、transcript 和波形只进入 `build/`。
- 构建前提：后续 PDS run 已更新，S2-D 通过事实仍只限其当时绑定的 canonical 综合网表与受限覆盖。
- 动态结果：Questa 2021.1 run `41135fd3fadd4c51a70508a6fa5af3e3` 运行至 `491965 ns`，Errors 0、Warnings 1，唯一 `INFO: POST_SYN_RESET_PATH_OK` 与唯一 `TEST PASS`，退出 0。
- 覆盖边界：只验证综合网表展开、项目 reset debounce/sync 和 reference-clock LED counter 路径；不验证 PCIe 链路、DMA、PNR、SDF、时序、H2-B1 或发布。

## PCIe S2-E PNR 后功能 smoke（动态通过）

- 工程归档：三个项目的可复现仿真工程分别保留在各自工程内独立 `sim/questa/`；运行库、launcher ini、日志、transcript 与波形只进入对应 `build/`。
- PDS 证据：run `9952da4164f040d5924a558baa5cd8ca` 为 `complete/valid=true`，绑定 43 inputs/9 artifacts。
- 动态结果：Questa run `927abae8ed7d40aeb5d6f706b3723e0a` 运行至 `491965 ns`，唯一 `INFO: POST_PNR_FUNC_RESET_PATH_OK`、唯一 `TEST PASS`、Errors 0、Warnings 1、Suppressed Warnings 80、PowerShell 退出 0。
- 覆盖边界：只验证无 SDF PNR 功能网表展开、reset debounce/sync 与 reference-clock LED counter；不证明 PCIe link、DMA、SDF timing、H2-B1、实板或 release。

## PCIe S2-F PNR 后时序 smoke（动态阻断）

- 工程归档：`sim/questa/post_pnr_timing.f`、`run_post_pnr_timing.do` 与 `tb/tb_pcie_dma_post_pnr_timing.sv` 保存在 PCIe 项目内；独立启动器为 `scripts/run_post_pnr_timing_sim.ps1`，检查入口为 `scripts/check_post_pnr_timing_sim.ps1`，运行态只进入 `build/`。
- PDS 证据：S2-F 未修改 canonical PDS `scripts/run.ps1`，其原始字节/SHA 已恢复；仿真入口变更不属于 PDS 实现输入漂移。baseline provenance gate 返回 0，因此无需重跑 PDS，继续沿用 run `9952da4164f040d5924a558baa5cd8ca` 的 `complete/valid=true`、43 inputs/9 artifacts。
- 动态结果：独立启动器当前 run `7fc77a7ec8db479db7332e8037426d6c` 成功标注 SDF 且 DUT 层级匹配，未对设计信号使用 force/release；HSST `ext_rstn_debounce` 自然产生与先前 run `d64e2f32ac7f4e2e93fa961b3695abc0` 相同的 setup `cnt_rst[5]` 与 hold `rstn_sync` 两个正 timing error。Questa Errors 2，脚本汇总 5 类失败并退出 1。
- 模型边界：`vsim-3004` 来自 `V_DRM18K_E1`，`vsim-8756` 来自 `V_FFASYN`；slow-corner STA setup/hold 均为正。当前只能判定 GLS 与 STA 冲突，不能宣称仿真通过，也不能据此断言硅上时序失败。
- 求解器诊断：Questa 2021.1 run `f79dc238c12949b7b67db2ef0d0ddd0b` 的 level1/2/3 三个独立进程均退出 0，SDF/功能/`TEST PASS` marker 各恰好一次，3316/3616 均为 0；3004 为 `3624/1590/1590`，8756 为 `1/1/1`，三档均为相同 setup=1、hold=1、Errors=2。level3 仅非 canonical 诊断，canonical level2 验收未修改，S2-F 继续 blocked。
- 归档边界：timing netlist、slow SDF、TB、`V_FFASYN`、`V_DRM18K_E1` 的 SHA-256 已写入诊断证据；每档结束后清理该 run 的 work/launcher，日志与汇总 JSON 只位于项目 `build/`。
- 判定规则：TB 即使输出 `TEST PASS`，也不能覆盖仿真器 error summary 和非零退出码；S2-F 保持 blocked，不关闭 PCIe link、DMA、H2-B1、实板或发布。

## PCIe S2-A 行为 smoke（2026-09-01，动态通过）

- 已验证源边界：`sim/questa/behav.f` 嵌套复用 `scripts/pds_sources.f` 的 37 个 canonical HDL，并单独补入仿真所需 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`；`scripts/pds_sources.f` 不修改，因为该源在实现侧由 IDF 管理。
- 已验证编码与自检边界：受控模型恰好包含两个 `always_ff` 时序过程，静态 gate 禁止普通 `always @` 回退。TB 覆盖 `button_rst_n`、`perst_n`、同步复位、LED 计数门控和 TX/LED 未知态；3 ms watchdog 或检查失败调用 `$fatal`，正向源只包含一次 `$display("TEST PASS")`。
- 已验证 reset ownership：button reset 断言后，TB 先检查 ref counter 没有被 button reset 改写，再等待额外 8 个 refclk 周期并要求其在 model link 撤销期间严格保持；button reset 完整重新释放后，PERST# 再被单独断言、复位两组 LED 域并独立重新释放，不能由初次联合释放遮蔽 debounce 行为。
- 已验证复位与日志契约：TB 全局复位实例使用厂商要求的 `GRS_INST`；`run_behav.do` 通过 `echo` 将随机 32 位小写十六进制 `SIM_RUN_ID` 写入 transcript，PowerShell 只接受同 run-id marker 与 `TEST PASS` 各恰好一次。
- 动态结果：Questa Sim-64 2021.1 当前 run id `add7efa39f644384af9929e8a9366739`，运行至 `1476105 ns`，0 errors/0 warnings、唯一 `TEST PASS`、退出码 0；PowerShell 同 run-id/唯一 PASS 门禁通过。
- 工程归档回归：PCIe `.f/.do` 迁入 `sim/questa/` 后，run id `26db7d3206c542218634caff2c6e71ea` 再次运行至 `1476105 ns`，0 errors/0 warnings、唯一 `TEST PASS`、退出码 0；DDR3 与摄像头的项目级动态入口仍待实现。
- 当前复验结果：S2-A 静态 gate 与 S2-B 静态契约 gate 通过，S2-A 动态复验通过；S2-B 真实 RC/EP 动态链路也已通过。S2-A 受控模型仍不覆盖真实 RC/EP、LTSSM/TLP 或 DMA，S2-B 也不覆盖 DMA、实板、电气或后级网表。
- 构建回归：build-scoped Questa launcher 纳入 canonical 输入后，当前 PDS run id `dde6ee70b2c84d2da4ee2256d8a5c127` 为 `gen_bit_stream/complete/valid=true`，43 项输入和 7 项证据完整；baseline gate 返回 0，strict gate 仍因 UART RX tied low、未约束顶层 I/O、PCIe serial I/O、share pin 与 SCBV 返回 1，最差 slack `0.1 ns`。baseline=0 只复现获准失败基线，不表示 release-ready。
- RX halt hygiene：`o_trgt1_radm_pkt_halt[2:0]` 接口分别对应 posted、non-posted 与 completion/CPLD halt；当前 bit0/bit1 有效、bit2 源端恒为 0，三位接口路径已由项目顶层贯通活动 `pcie_test` wrapper 至 hard-IP。wrapper 原 3'b0 tie-off 已删除；生成资产重生成会覆盖该修正，静态 gate 检测该已知接口漂移并要求重新审核。
- 覆盖边界：受控模型的 `smlh_link_up/rdlh_link_up` 是激励，不验证真实 LTSSM、TLP、DMA、lane/P/N 极性、100 MHz refclk 电气、PERST# 板级时序或 RK3568 Root Complex。S2-B 必须使用真实厂商 RC/EP，S2-C 必须在其后验证 DMA。

## PCIe S2-B 真实链路（2026-09-01，动态通过）

- 工程与生成物边界：三个项目的 Questa 工程定义分别保留在各自 `sim/questa/`；启动器在 `build/sim/launcher/<run-id>/` 创建并显式绑定 run-scoped `modelsim.ini`，PowerShell 通过进程内 `SIM_PROJECT_ROOT` 让 DO 切回项目根。work/vendor library、日志、transcript、波形与 ini 全部只写入 `build/`，不将本机安装或许可证信息纳入仓库证据。
- 运行隔离：S2-B 的 `work` 与物理 vendor library 均按 `SIM_RUN_ID` 隔离；厂商模型直接编译到本次运行的物理库目录，避免逻辑库映射或旧运行产物被误用。
- 厂商兼容契约：TB 固定唯一 `GTP_GRS GRS_INST`，满足 RAM 模型对 `GRS_INST.GRSNET` 的层级解析；项目源统一以 `1ns/10ps` 编译；DO 使用 `echo` 将 run marker 写入 transcript。
- 稳定窗口契约：首次进入 L0 后，RC 可合法进入 `0x0d` Recovery/速率重训练；TB 在 6 ms 总窗口内寻找连续 32 周期双端 link-up/L0，任一中断只将连续计数归零，不立即误判失败。
- 动态结果：Questa Sim-64 2021.1 run `30bad6e164be4a4b8284a00f1e96bd87` 的厂商模型与项目 RTL 编译成功，elaboration 成功；输出唯一 `INFO: S2B_REAL_LINK_UP` 与唯一 `TEST PASS`，Errors 0、Warnings 26、PowerShell 退出 0。
- 根目录洁净性：最新 S2-A/S2-B 运行后，项目根 `modelsim.ini`、transcript、`vsim.wlf` 计数均为 0，验证所有运行生成物均留在 `build/`。
- 覆盖边界：该结果只证明仿真模型中的真实 RC/项目 EP 能取得连续 32 周期双端 link-up/L0；不证明 DMA、RK3568 实板、协商 x2/5.0 GT/s、PCB/时钟/PERST# 电气或后级网表。

## 已知功能与覆盖缺口

- OV7725：`41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md` 已记录七类时钟域、`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和分侧复位风险，以及三条旧 STA 失败路径。
- OV7725：O1-B 已完成 38 条确定性 RTL 卫生修复，手写 RTL 位宽告警只剩 `mem_a` 1 条；该单项因活动 IP 14 bit 与顶层/FDC 15 bit 冲突冻结为 legacy 风险，当前综合网表把 `mem_a[14]` 绑 0。
- OV7725：O2-B 详细 STA 将反向八个 endpoint 唯一映射到 `serializer_b/g/r/clk × opit_2/opit_2_com` 的 OSERDES `OCLKDIV` 检查；慢角高速同域 `OCLK` 也仍为负。该覆盖证明候选失败，不构成 serializer reset 通过证据。
- OV7725：O2-D1-R 已从空 `build/` 完成七阶段，baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 并返回 0，严格 gate 返回 1；O2-D1-G 的 generated-clock 和状态契约保留为历史设计证据。owner 已取消 O2-D2 与旧工程 Questa/S3，不再继续实现。
- OV7725 M3-A：SP6.4 隔离探针已覆盖四个活动 IDF，确认不带安装定义时报 `IPCompiler 0037`，显式绑定当前定义时报版本不匹配 `IPCompiler 0057`，均退出 104。仓库门禁现检查迁移审计文档和四个 canonical IDF 的 SHA-256；该覆盖只证明旧 IDF 不可直接迁移及 canonical 未改，不证明 50H IP 已生成。
- OV7725 M3-B 已取消：不再新建四个 PG2L50H staging 实例、升格 canonical、执行 50H PDS 或旧工程 S3；M3-A 只防止旧 IP 被双 OV5640 误用。
- DDR3：临时 `test_ddr` bring-up 已完成全流程与内部 STA/产物基线。严格 gate 因 7 类问题返回 1：BIST error-data 位宽不匹配、BIST dangling cleanup、`rst_board` 使用 share pin、BANKR4 VCCIO 3.3 不兼容、UART I/O 约束缺失、顶层输入 timing 缺失、顶层输出 timing 缺失。显式 baseline 放行返回 0，但明确标记不可发布。
- DDR3 M2 只读审计（2026-08-30）：活动 IDF 为 `ip_core/ddr3/ddr3.idf`，metadata `Logos2/PG2L100H/FBG484/-6`、生成器 `2022.2-SP6.4`；canonical FDC/RCF 为 `ip_core/ddr3/pnr/ddr_test.fdc` 与 `ip_core/ddr3/pnr/ddr3.rcf`。唯一 50H 备份来自 SP6.1，不能直接替换；外层 `ip_core/ddr_test.fdc` 仅供差异参考。
- DDR3 M2-B1 参数覆盖（2026-08-30）：PDS SP6.4 `ui.tcl` 静态证据确认 `DEVICE_100H_EN` 是隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`；已通过错误探针证明直接 `-device` 覆盖 100H IDF 会保留 `true` 并生成 PPLL `FALSE/CLKOUTF`，该路径已禁止。
- DDR3 M2-B1 重生成覆盖：脚本验证活动 100H IDF 与 SP6.1 50H seed 的所有参数仅上述 flag 不同，再由 SP6.4 build 146967 重生成；输出 `DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、退出 0、`0 error(s), 0 warning(s)`，canonical 哈希不变。
- DDR3 M2-B1 差异覆盖：正确 staging 的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均有差异；wrapper 端口数 `21 → 26`，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`；FDC 有 28 项 pin 差异。该覆盖只证明生成输入与差异审计正确，不证明板级 pin 匹配。
- DDR3 M2 退出条件：取得原理图/BOM并审核板级参数、28 项 FDC pin 差异与新 wrapper/PHY/filelist/IDF 后才能升格 canonical；之后 CI-6 必须重新确认端口/128-bit 数据/28-bit 地址/握手/`I_ips_ddr_top`，并从空 `build/` 完成七阶段且产物器件交叉一致。M2-B1 未授权 D3-A/B/C 或项目自有 BIST RTL。
- DDR3：本次完整构建日志没有 SCBV 命中；这不替代板级批准参数清单。DDR3 颗粒/组织、VCCIO/VREF、ODT、拓扑、走线、UART/ADC 决策等仍缺少审核依据。
- DDR3：testbench 端口仍失配，BIST 无天然有限完成状态，缺少可靠 `$fatal`、超时、唯一 `TEST PASS` 和四级仿真证据；当前结果只验收可重复实现基线，不验收板级功能或产品状态。
- DDR3：D2 已以只读方式固定后续测试契约，厂商 `test_ddr`、持续运行 BIST 和旧 testbench 保持原样。计划新增 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`，首版执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并设置 4096 周期 pair timeout 与 131072 周期 run timeout。
- DDR3：未来行为仿真必须通过公开且稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息判定结果；D2 与 D3-0 仅完成只读决策，不构成实现或测试覆盖，D3-A/B/C 仍待用户审核。
- DDR3 D3-0（只读静态评审）：活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`，公开端口包含 `ddr_init_done`、`core_clk` 与 AW/W/AR/R 自定义 AXI-like 接口；`test_ddr.v` 的物理 board wrapper 实例名为 `I_ips_ddr_top`，必须保留。
- DDR3 D3-0 已完成非标准 AXI-like 握手评审：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回依赖 `axi_rvalid`/`axi_rlast` 且无 `axi_rready`。D3-A 等待用户审核后按该契约实现，接口语义、地址单位或层级变化即停止并重新审核。
- DDR3 D3-0-R 端口映射见 `ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md`：当前默认 `CTRL_ADDR_WIDTH=28`、`axi_wdata/axi_rdata=128` bit、`axi_wstrb=16` bit；文档明确 APB/debug tie-off 与物理端口不属于 D3-A BIST 接口。
- DDR3 D3-0-M：`check_d3a_staging_contract.ps1` 动态确认 canonical/staging core whole-file 相同，wrapper 只新增五个登记端口与 `GTP_INBUFDS`，唯一连接变化为 `.ref_clk(free_clk)`→`.ref_clk(ref_clk)`；错误 refclk、删除 `ref_clk_n`、新增 `axi_rready` 的负向探针均失败。该 gate 不加载 FDC/RCF、不执行 Questa/PDS 后级，也不关闭 H1 或 D3-A。
- PCIe：S2-A 已动态通过覆盖 `pcie_dma_test` 集成顶层的受控行为 smoke；厂商 ModelSim 资产仍只覆盖 PCIe IP 示例，真实 RC/EP、LTSSM/TLP/DMA 与 UART2APB 无驱动输入仍未验证。
- PCIe H2-A（只读证据矩阵）：顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与 `ref_led/pclk_led`；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。当前没有 lane 极性/板级拓扑、I/O delay 或 SCBV 证据。
- PCIe H2-A/M1 器件边界：活动 `pcie_test.idf`、build/PDS/gate、timing report 与 `bgr.db` 已统一匹配 `Logos2/PG2L50H/FBG484/-6`；UART2APB `rxd/txd`、SCBV、lane/refclk/PERST# 与 share pin 仍是独立功能/发布阻断。
- 三项目新流程均已生成顶层 PNR SDF，但尚未由 QuestaSim 验证实例层级。
- Questa Sim-64 2021.1、Logos2 USIM/VSIM、`V_BUF` 和 PCIe S2-A 当前动态复验已通过。不得将该证据外推为 DDR3、OV5640、真实 PCIe 链路、DMA 或项目后级网表/SDF 通过。
- PDS 可能在日志含 `E:` 时仍返回退出码 0；新 PowerShell 入口必须同时检查退出码和错误日志。
- PCIe 位流阶段报告 SCBV 未配置，这是当前发布阻断项。

## 约束例外清单与漂移门禁

- 已验证：`docs/CONSTRAINT_EXCEPTION_INVENTORY.json` 精确登记 4 个 artifact、15 条 timing exception 与 1 条 dedicated-route override。DDR3 为 6 条 vendor-generated/unreviewed 且仍有旧 PG2L100H target mismatch；PCIe 为 3 条 vendor-derived/unreviewed；OV7725 legacy 为冻结且非批准的 6 条 timing exception 与 1 条 `PAP_CLOCK_DEDICATED_ROUTE FALSE`；双 OV5640 为 0 条且 canonical FDC not-created/H3-blocked。
- 已验证：`scripts/check_constraint_exceptions.ps1` 正向检查和 CRLF-only checkout 可移植性 fixture 退出 0；增加未登记 exception、改写已登记 exception、在双 OV5640 目录过早创建 FDC，以及包含 `source`、Tcl 续行或分号多命令的输入均被负向 fixture 拒绝。根一致性门禁调用该自测。
- 边界：清单成员资格只证明文本可追溯和漂移受控，不构成 waiver 或技术批准；静态 gate 不执行 Tcl，不证明 `get_clocks`/`get_pins` 对象能唯一解析，不证明 CDC、STA、实现、位流、发布或实板通过。

## 统一验收门槛

1. 行为级 testbench 自检通过，失败使用 `$fatal`，成功只输出一个 `TEST PASS`。
2. PDS 各阶段退出码为 0，并对最终时序强制 `WNS >= 0`、`TNS = 0`。
3. 综合后、PNR 后功能和 PNR 后时序仿真均使用集成顶层，而非仅 IP 示例。
4. 双 OV5640 新项目必须重新证明 serializer recovery/removal、generated clock 唯一性、端点覆盖、逐域复位和 FIFO 分侧复位；不得把 OV7725 O2-D2 契约直接计为覆盖。
5. 时序仿真确认 SDF 实例层级匹配，日志无标注错误和未批准的 timing violation。
6. 最终位流文件存在且大小非零；关键未约束 I/O 必须修复或进入有依据的白名单。
7. DDR3 有限自检必须完成恰好 16 个 pair；任一 pair 超过 4096 周期或整次运行超过 131072 周期均失败，成功与失败只能由公开结果接口和退出码判定。
7. DDR3 D3-0-R/M 已冻结 AW/W/AR/R、无 `axi_rready`、`I_ips_ddr_top` 及 staging wrapper/refclk 差异；D3-A/B/C 仍受 H1 阻断，且该评审不构成 RTL/IP/约束变更或仿真通过证据。
8. 三项目最终产物必须证明目标为 `PG2L50H/FBG484/-6`；任何 PG2L100H report、SDF 或位流均拒绝烧录和签核。
9. PCIe H2-B 只有在 50H build/IDF/report/bitstream 一致、lane 极性/拓扑、I/O delay、SCBV 和 UART2APB 归属均有证据后才可发布。
