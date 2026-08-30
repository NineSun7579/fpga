> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: existing PDS logs/reports, new DDR3 and OV7725 full-build logs, timing reports, artifact gate runs, and static audit; no simulator execution in this repository session

# Test Coverage

## 证据等级

- 已验证：当前文件或报告直接证明。
- 静态发现：源码、工程配置或日志可直接观察，但本轮没有重新运行工具。
- 未验证：缺少可执行资产、工具环境或运行记录。

## S0 环境复核（2026-08-30）

- 静态发现：`E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe` 存在，可作为当前唯一已发现工具。
- 静态发现：PATH、`C:/questasim64/win64`、`C:/ModelSim/win64`、`C:/Program Files/ModelSim/win64`、`C:/Program Files/QuestaSim/win64`、`C:/Program Files/Siemens/QuestaSim/win64` 及常见 Intel ModelSim 目录均未找到 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- 已验证：S0-1 参数化入口 `scripts/compile_simlib.tcl` 与 `scripts/compile_simlib.ps1` 已提交；PowerShell AST 错误数为 0。入口支持 ModelSim/QuestaSim、USIM/VSIM/BOTH、family、语言、PDS/仿真器路径和输出目录覆盖，强制检查三项仿真器可执行文件，并检查 PDS 退出码、日志 `^E:` 与所选库目录。
- 已验证阻断：默认运行在调用 PDS 前因 `C:/questasim64/win64/vsim.exe` 缺失返回 1，`vlog.exe`、`vlib.exe` 同样不存在。
- 未验证：实际 USIM/VSIM 编译、库目录内容、动态仿真和 SDF 标注；安装有许可证的 ModelSim/QuestaSim 并成功运行入口后，才可解除该阻断。

## CI-0 仓库级静态一致性门禁（2026-08-30）

- 已验证：新增 `scripts/check_repo_consistency.ps1`，覆盖根指南/TODO/VSCS、三个项目 README、PDS 构建入口、顶层声明、七阶段命令、可配置工具路径、退出码、baseline 开关、产物/时序检查接口和 `build/` 忽略状态。
- 已验证：三个项目 README 的 PDS `2022.2-SP6.4`、顶层模块或仿真状态缺口已修正；门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 已验证：仓库内全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- 边界：CI-0 不启动 PDS 或 ModelSim/QuestaSim，不替代项目严格 gate、STA 或四级仿真。

## CI-2 板级证据清单完整性门禁（2026-08-30）

- 已验证：提交 `677808d` 将三项目板级证据清单路径和项目关键词加入 `scripts/check_repo_consistency.ps1`，并要求各项目 README 直接链接对应清单。
- 已验证：OV7725、DDR3、PCIe 清单均包含“当前工程事实”“必须提供的资料”“关闭条件”；PCIe 清单已统一章节名称和结构。
- 已验证：HEAD `677808d` 上仓库一致性门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 边界：CI-2 只证明清单结构、关键词和 README 链接完整，不证明清单中的板级资料已提交、审核或与实物一致。

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

## CI-6 DDR3 D3-0-R 契约一致性门禁（2026-08-30）

- 已验证：提交 `a5d1785` 扩展 `scripts/check_repo_consistency.ps1`，交叉读取 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md`。
- 已验证：门禁检查模块/参数声明、128-bit 数据和 28-bit 地址证据、`I_ips_ddr_top` 层级、AXI-like 握手字段，并在 core 出现 `axi_rready` 时失败；HEAD `a5d1785`、52 个 Git 提交上门禁和 8 个 PowerShell AST 均通过。
- 边界：CI-6 只保护旧活动 DDR3 IP 的静态契约；PG2L50H IP/FDC/RCF 重生成后必须重新核对并审核，不能替代 compile、STA 或动态仿真。

## S0-0-R 仿真器环境复核（2026-08-30）

- 已验证：提交 `ef5cc9a` 再次探测 PATH、常见安装目录和 `vsim.exe` 文件名，`vsim.exe`、`vlog.exe`、`vlib.exe` 均未发现。
- 边界：仅更新 S0-1 阻断证据，未执行 `compile_simlib`、PDS 或动态仿真。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| OV7725 HDMI | 旧 PG2L100H O1-B/O2-B/O2-D1-R 流程完成，但与实际 PG2L50H 不匹配；四个 IP 需重生成并建立 50H baseline | 旧 100H Recovery 失败只作为候选分析证据；50H STA 尚未执行，O2-D2 必须在新 baseline 后重审 | 未就绪；Questa/S3 缺失 | 旧 100H 网表不可签核 | 旧 100H PNR 网表不可签核 | 旧 100H SDF 未标注且不可签核 |
| DDR3 外层 | 旧 PG2L100H 七阶段与五类产物已完成，但不可用于实际 PG2L50H；需重生成 50H IP/FDC/RCF | 旧 100H `All Constraints Met` 只保留历史；50H STA 未执行 | D2/D3-0 旧契约已定，PG2L50H 重生成后须重审；Questa 缺失 | 旧网表不可签核 | 旧 PNR 网表不可签核 | 旧 SDF 未标注且不可签核 |
| PCIe DMA | 活动 IDF、build/PDS/gate 与新产物均为 PG2L50H；已从空 `build/` 完成七阶段重建 | 50H STA 已生成，最差解析 slack `0.100 ns`；严格 gate 仍受板级/功能缺口阻断 | 仅 IP 示例 | 顶层未闭环 | 新 50H 网表待集成仿真 | 新 50H SDF 待标注仿真 |

## S1/S2/S3 仿真就绪度矩阵（2026-08-30）

- 已验证静态盘点：`docs/SIMULATION_READINESS_MATRIX.md` 已逐项目记录项目级 testbench、filelist、DO、厂商示例和四级仿真前置条件；本轮没有执行 ModelSim/QuestaSim。
- 三项目的项目级资产计数一致为 `project_tb=0`、`project_f=0`、`project_do=0`，因此当前没有任何项目具备可直接运行的集成仿真入口。
- OV7725/S3：现有厂商示例只覆盖单个 IP。进入 S3 前必须关闭 S0-1、重生成四个 PG2L50H IP并建立新 baseline、重新审核 O2-D2、固定摄像头输入格式契约并锁定 O2-D2/O3 RTL。
- DDR3/S1：现有厂商 `test_ddr`/memory-model 资产端口失配且含绝对路径与 FSDB/Verdi 假设。进入 S1 前必须关闭 S0-1、重生成并复核 PG2L50H DDR3 IP/FDC/RCF、完成 D3-A/B/C 与 D4，并提供项目自有有限 BIST/top 与自检 TB。
- PCIe/S2：现有 `pango_pcie_top` RC/EP testbench 不实例化产品顶层。进入 S2 前必须关闭 S0-1、完成 PG2L50H build/gate/产物一致性与 H2-B，并新增项目级 smoke/DMA TB。
- 验收边界：`ipcore/`、`ip_core/`、`ip_backup/` 中的厂商示例只能作为参考证据，不能计入产品集成覆盖，也不能通过改名冒充项目自有 testbench。
- 四级共同门槛：所有入口使用相对路径 filelist/DO 和项目自有集成 TB；必须具备超时、`$fatal`、唯一 `TEST PASS` 与可靠非零失败退出；PNR 时序仿真必须按实际 DUT 实例层级标注 SDF。
- 公共阻断：S0-1 仍因本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断；矩阵完成只读静态盘点，不构成动态仿真通过证据。

## 已知功能与覆盖缺口

- OV7725：`41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md` 已记录七类时钟域、`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和分侧复位风险，以及三条旧 STA 失败路径。
- OV7725：O1-B 已完成 38 条确定性 RTL 卫生修复，手写 RTL 位宽告警只剩 `mem_a` 1 条；该单项因活动 IP 14 bit 与顶层/FDC 15 bit 冲突继续转 H3/O1-C，当前综合网表把 `mem_a[14]` 绑 0。
- OV7725：O2-B 详细 STA 将反向八个 endpoint 唯一映射到 `serializer_b/g/r/clk × opit_2/opit_2_com` 的 OSERDES `OCLKDIV` 检查；慢角高速同域 `OCLK` 也仍为负。该覆盖证明候选失败，不构成 serializer reset 通过证据。
- OV7725：O2-D1-R 已从空 `build/` 完成七阶段，baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，没有新增失败签名或 waiver。O2-D1-G 现已冻结：只允许一条 `pixel_clk` `/5` generated clock，源 `u_pll_clk/clkout1`、目标唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`、波形 `-edges {1 5 11} -edge_shift {0 0 0}`，并使用 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN` 状态契约；审核前不实现 O2-D2，QuestaSim/S3 未完成。
- OV7725 M3-A：SP6.4 隔离探针已覆盖四个活动 IDF，确认不带安装定义时报 `IPCompiler 0037`，显式绑定当前定义时报版本不匹配 `IPCompiler 0057`，均退出 104。仓库门禁现检查迁移审计文档和四个 canonical IDF 的 SHA-256；该覆盖只证明旧 IDF 不可直接迁移及 canonical 未改，不证明 50H IP 已生成。
- OV7725 M3-B 待覆盖：SP6.4 GUI 新建四个 PG2L50H staging 实例后，必须验证 DDR3/PLL 派生参数、FIFO 85 DRM36K/170 DRM18K 上限、wrapper/FDC/RCF/仿真资产差异和 RCF 对象命中；板级资料未关闭时禁止升格、50H PDS 和 S3。
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
- PCIe：现有 ModelSim 资产只覆盖 PCIe IP 示例，不覆盖 `pcie_dma_test` 集成顶层；UART2APB 的无驱动输入属于已知功能缺陷。
- PCIe H2-A（只读证据矩阵）：顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与 `ref_led/pclk_led`；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。当前没有 lane 极性/板级拓扑、I/O delay 或 SCBV 证据。
- PCIe H2-A/M1 器件边界：活动 `pcie_test.idf`、build/PDS/gate、timing report 与 `bgr.db` 已统一匹配 `Logos2/PG2L50H/FBG484/-6`；UART2APB `rxd/txd`、SCBV、lane/refclk/PERST# 与 share pin 仍是独立功能/发布阻断。
- 三项目新流程均已生成顶层 PNR SDF，但尚未由 QuestaSim 验证实例层级。
- 本机 S0 复核未找到 ModelSim/QuestaSim，因此本轮未运行任何仿真；安装并验证 `vsim.exe`、`vlog.exe`、`vlib.exe` 前不得声称动态仿真通过。
- PDS 可能在日志含 `E:` 时仍返回退出码 0；新 PowerShell 入口必须同时检查退出码和错误日志。
- PCIe 位流阶段报告 SCBV 未配置，这是当前发布阻断项。

## 统一验收门槛

1. 行为级 testbench 自检通过，失败使用 `$fatal`，成功只输出一个 `TEST PASS`。
2. PDS 各阶段退出码为 0，并对最终时序强制 `WNS >= 0`、`TNS = 0`。
3. 综合后、PNR 后功能和 PNR 后时序仿真均使用集成顶层，而非仅 IP 示例。
4. O2-D2 只允许一次已审核实验；八个 OSERDES endpoint 的 Slow/Fast × Recovery/Removal × `OCLK` 双边沿/`OCLKDIV`/`SERCLK` 全覆盖且非负，generated clock 唯一，旧 `CLKOUT0` 对 pixel 域为零消费者。generated-clock 对象/波形/取点、端点覆盖、PDS/gate/产物或新 baseline 失败任一异常即停止并完整回退，不得扫描第二相位或增加 waiver。
4. 时序仿真确认 SDF 实例层级匹配，日志无标注错误和未批准的 timing violation。
5. 最终位流文件存在且大小非零；关键未约束 I/O 必须修复或进入有依据的白名单。
6. DDR3 有限自检必须完成恰好 16 个 pair；任一 pair 超过 4096 周期或整次运行超过 131072 周期均失败，成功与失败只能由公开结果接口和退出码判定。
7. DDR3 D3-0 已冻结 AW/W/AR/R 握手语义与 `I_ips_ddr_top` 实例边界；D3-A/B/C 仍待用户审核和实现，且 D3-0 评审不构成 RTL/IP/约束变更或仿真通过证据。
8. 三项目最终产物必须证明目标为 `PG2L50H/FBG484/-6`；任何 PG2L100H report、SDF 或位流均拒绝烧录和签核。
9. PCIe H2-B 只有在 50H build/IDF/report/bitstream 一致、lane 极性/拓扑、I/O delay、SCBV 和 UART2APB 归属均有证据后才可发布。
