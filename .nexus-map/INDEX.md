> generated_by: Codex manual bootstrap
> verified_at: 2026-09-01
> provenance: current worktree, PDS project files, implementation reports, root audit notes, and manual inspection; no HDL/raw-source AST extraction or Git-history statistics; PowerShell AST syntax gate is recorded as CI-5

# Embedded Completion Nexus Map

本仓库的三个活动产品项目是 DDR3、PCIe 和双 OV5640，并以根目录文档约束后续整改方式。`41_ov7725_hdmi/` 仅为 legacy 证据工程，不是活动 TODO 项目：

- `41_ov7725_hdmi/`：OV7725 采集、DDR3 帧缓存与 HDMI/TMDS 输出 legacy；已完成的 SP6.4 构建、STA、CDC/RDC 和 gate 结果只保留为历史证据，不得改名冒充 OV5640 产品实现。
- `ddr3_test/`：已用厂商 `test_ddr` 临时 bring-up 顶层完成 SP6.4 全流程实现、STA、网表/SDF、位流与构建 gate 验证；严格 gate 仍被板级和 RTL 已知问题阻断，它不是已验收的产品顶层。
- `pcie_dma_test_100h/`：PCIe x2 DMA 集成顶层；已按 PG2L50H 修正构建脚本/gate，并从空 `build/` 完成七阶段重建，HSSTLP 资源固定为 `HSSTLP_292_612`；S2-A 项目级受控行为 smoke、S2-B 真实 RC/EP 链路、S2-D 综合后受限 smoke 与 S2-E PNR 后功能 smoke 均已由 Questa Sim-64 2021.1 当前复验通过。S2-F PNR 后时序工程也已归档到项目内 `sim/questa/`，但当前 run `7fc77a7ec8db479db7332e8037426d6c` 虽成功标注 SDF，仍自然产生 2 个 HSST reset timing error，且 `V_FFASYN` 负时序模型语义不完整，故保持 blocked。`o_trgt1_radm_pkt_halt[2:0]` 已从项目顶层贯通活动 `pcie_test` wrapper 至 hard-IP，UART2APB 仍有隐式 `rxd/txd`、`rxd` 被绑 0 的功能缺口。

用户已将摄像头 HDMI 产品固定为双 OV5640。C0 已对 `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3` 完成只读审计，逐文件结论见 [`OV5640_C0_REFERENCE_AUDIT.md`](../docs/OV5640_C0_REFERENCE_AUDIT.md)；本批未导入 RTL/IP/FDC/PDS/TB。参考 HDMI 顶层为 `top_dual_ov5640_hdmi`：两路独立 SCCB/RESET/PWDN/DVP，每路采集 960x1080 半幅，双写 DDR3 后组成 1920x1080 输出。参考根 PDS 与 DDR3/PLL/FIFO 为 PG2L100H，PCIe IP 虽为 PG2L50H，但 BAR1/BAR2 均禁用；这些资产不能作为实际 `PG2L50H-6IFBG484` 产品实现证据。C1 仍受 H3 板级资料阻断，后续只选择性导入到 `59_top_dual_ov5640_hdmi/`；现有 `41_ov7725_hdmi/` 及其 `sim/questa/` 均只作 legacy。

参考仓库发现 4 个 TB，但尚未选择性导入；`tb_dual_ov5640_dri.v` 会 force `cam_init_done`，且成功字符串不是 canonical `TEST PASS`，不能计为产品自检通过。未来可复现仿真源只进入 `59_top_dual_ov5640_hdmi/sim/questa/`，运行态只进入该工程 `build/`；禁止导入 `sim_*`、`work`、`.mpf`、`modelsim.ini`、日志、波形、绝对路径生成物或许可证配置。

## 当前基线

- Git 分支：`main`。
- Git 基线提交：`1a2d493`（三个原始工程、已有报告和整改文档）。
- 原始 PDS 生成物仍位于各 GUI 工程目录中；新增流程统一输出到被忽略的 `build/`。
- PCIe 已完成新 `build/` 全流程、STA、网表/SDF/位流和严格 gate 验证。
- DDR3 已从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，日志无 `E:`；最终报告为 `All Constraints Met`，慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`、recovery `4.578 ns`、removal `0.351 ns`。
- DDR3 已生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`；严格 gate 因 7 类已知阻断返回 1，显式 baseline 放行返回 0 但明确不可发布。日志没有 SCBV 命中，板级批准参数清单仍缺失，功能与四级仿真仍未验收。
- DDR3 D2 只读决策已完成：厂商 `test_ddr`、持续运行 BIST 和失配 testbench 保持原样；后续项目自有顶层固定为 `rtl/ddr3_bringup_top.sv` 与 `rtl/ddr3_finite_bist.sv`。首版契约执行 16 个单 beat 写读比较 pair，控制器地址为 `0x0..0x78`、步长 8，单 pair timeout 为 4096 周期、整次 run timeout 为 131072 周期，并公开稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息。该设计尚未实现或仿真，D3 待审核。
- DDR3 D3-0 只读评审（2026-08-30，已完成）：已固定旧活动 IP 的公开 `module ddr3`、非标准 AXI-like AW/W/AR/R 握手和 `I_ips_ddr_top` board wrapper 边界。由于该 IP/FDC/RCF 属于旧 PG2L100H 目标，必须先用 SP6.4 为 PG2L50H 重生成并重新核对端口、地址单位和层级，之后重新审核 D3-A；本批不改 RTL、IP 或约束。
- DDR3 M2-B1 参数与差异审计（2026-08-30）：PDS SP6.4 `ui.tcl` 证明 `DEVICE_100H_EN` 是隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`。直接以 `-device PG2L50H` 覆盖 100H IDF 会错误保留 `true`，生成 PPLL `FALSE/CLKOUTF` 分支，现已禁止。活动 100H IDF 与 SP6.1 50H seed 的全部参数仅此 flag 不同；更新后的 `scripts/regenerate_ip.ps1` 先验证 seed 参数一致，再以 SP6.4 build 146967 重生成，得到 `DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，且 canonical 哈希保持不变。正确 staging 的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均有差异；wrapper 端口由 21 增至 26，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，FDC 有 28 项 pin 差异。证据见 [`M2B1_PARAMETER_AND_DIFF_AUDIT.md`](../ddr3_test/ddr3_test/doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md)；未取得原理图/BOM 前不得升格 canonical，也未授权 D3-A。
- DDR3 M2-B2 staging compile-only（2026-09-01）已完成：项目内 [`build_staging_compile.tcl`](../ddr3_test/ddr3_test/scripts/build_staging_compile.tcl)、`run_staging_compile.ps1` 与 `check_staging_compile.ps1` 固定验证 `Logos2/PG2L50H/FBG484/-6`、18 个 staging RTL、一个 IDF 和 26 端口 `test_ddr`。最终 run `1d4b8c264ba940f0bb0e2517b8c36c07` 的 PDS 退出 0、`E:` 为 0、warning 为 272，三个 compile 产物非零，四个 canonical 哈希不变；错误目标、零长度产物和错误记录三项动态负向测试均退出 1。完整合同见 [`M2B2_STAGING_COMPILE.md`](../ddr3_test/ddr3_test/doc/M2B2_STAGING_COMPILE.md)。该 Tcl 是 `canonical_support_tool` 而非 canonical project build；它不加载 FDC/RCF，不做 synthesize/dev_map/PNR/STA/netlist/SDF/bitstream，也不授权 canonical 升格、仿真、实板或烧录，M2 仍受 H1 板级资料阻断。
- DDR3 D3-0-R 端口映射已由提交 `2fd7c51` 固化到 [`D3A_PORT_MAP.md`](../ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md)：记录默认参数/宽度、128-bit 数据通路、28-bit 地址、AW/W/AR/R 握手、复位链和 `I_ips_ddr_top` 层级；地址单位与 `axi_wready` 完成语义仍待审核。
- PCIe H2-A 只读证据（2026-08-30，已完成）：`pcie_dma_test` 顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与两枚 LED；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。活动 `pcie_test.idf` 已正确标识 `Logos2/PG2L50H/FBG484/-6`，M1 已将 build/PDS/gate 与新产物统一到 50H，并按 PDS 模板将 HSSTLP 固定为 `HSSTLP_292_612`。lane 极性/板级拓扑、I/O delay、SCBV 和 UART2APB 归属仍未关闭。
- H0/H1/H3 板级资料清单已由提交 `12d7a21` 建立：[OV7725 HDMI 清单](../41_ov7725_hdmi/doc/BOARD_EVIDENCE.md) 与 [DDR3 Bring-up 清单](../ddr3_test/ddr3_test/doc/BOARD_EVIDENCE.md) 均由对应项目 README 直接链接。两份清单只定义待提供字段、证据来源和关闭条件；实际板级资料仍未提供，H0/H1/H3 保持外部阻断。
- 板级证据补充提交 `11dfcc2` 已确认两项具体歧义：OV7725 活动 DDR3 IDF 由 PDS `SP4.2` 生成，`MEM_ADDR_WIDTH`、`DDR3_MEM_ROW_WIDTH`、`MEM_ROW_WIDTH` 均为 14，而手写顶层/FDC 使用 15 bit；DDR3 活动 IDF 同时记录 `DESIRED_DDR3_RATE=1066.000` 与另一处 `1050.000` 速率值。前者冻结为 OV7725 legacy 风险，不再进入产品整改；后者保持 H1 阻断。双 OV5640 与 DDR3 产品参数均不得在缺少料号、原理图和参数语义证据时猜测修正。
- PCIe H2-B 静态元数据 gate 已由提交 `03b694a` 落地；M1 已将期望值统一为 `Logos2/PG2L50H/FBG484/-6`，并增加 build log、timing report、`bgr.db` 的产物器件交叉校验，防止陈旧 PG2L100H 位流通过；UART、lane/refclk/PERST#/SCBV 阻断继续保留。
- PCIe H2-B0 精确 baseline（2026-08-30）已将五类问题归一化为 16 个唯一签名、42 次原始记录；baseline 使用精确多重集，签名新增/消失/改名、share-pin 位置或次数漂移均失败，活动 IDF metadata 漂移永久硬失败。canonical fixture 正向退出 0、strict 退出 1，5 个变异（缺失/重复 UART、Timing 端口改名、share pin 改位、IDF 改为 PG2L100H）均退出 1。
- H2-B1 仍等待 lane/refclk/PERST#/SCBV/UART/I/O timing 的板级资料和决策。H2-B0 发现的 partial run 复用旧 full-build 日志/产物风险已由 PCIe CI-8A 关闭；DDR3/双 OV5640 的 CI-8B 仍待各自 canonical 升格。
- PCIe CI-8A provenance pilot（2026-08-31）已完成：`scripts/pds_sources.f` 成为 37 个 HDL 的单一有序清单，`build_provenance.ps1` 为每次 build 生成 32 位 `run_id`，并原子发布固定的 `build/provenance/pds-build.json`。manifest 状态为 `running/partial/failed/complete`，只有 `complete + valid=true` 可进入 gate；43 项 canonical 输入和 7 项最终证据均以相对 POSIX 路径、长度和 SHA-256 绑定。partial compile、PDS executable 缺失、run-id、产物与 FDC 漂移均使 gate 返回 1。
- CI-8A 最新完整 PG2L50H 构建 run id 为 `9952da4164f040d5924a558baa5cd8ca`；manifest 为 `run_to=gen_bit_stream / status=complete / valid=true`，绑定 43 项输入和 9 项产物。baseline gate 返回 0、strict gate 返回 1；该结果不表示可发布。
- 三个项目的可复现仿真工程分别保留在各自工程内独立的 `sim/questa/`，运行态只进入对应 `build/`。PCIe S2-E run `927abae8ed7d40aeb5d6f706b3723e0a` 已通过；S2-F 的 `.f/.do/TB` 与检查入口也已在 PCIe 工程内留档。S2-F 当前 run `7fc77a7ec8db479db7332e8037426d6c` 成功标注 SDF、未 force/release 设计信号，但产生 setup/hold 各 1 个 error，Questa 汇总 Errors 2、独立脚本汇总 5 类失败并退出 1；`V_DRM18K_E1` 产生 `vsim-3004=1590`，`V_FFASYN` 产生 `vsim-8756=1`，负 timing check 语义不完整。slow-corner STA setup/hold 均为正，当前结论是 GLS 与 STA 冲突，不能宣称仿真通过，也不能据此断言硅上时序失败。
- S2-F 负时序求解器诊断最终 run `f79dc238c12949b7b67db2ef0d0ddd0b` 使用 Questa 2021.1 比较 level1/2/3：三档进程均为 0，SDF、功能和 `TEST PASS` marker 均唯一，`vsim-3004=3624/1590/1590`、`vsim-8756=1/1/1`、`vsim-3316/3616=0`，且三档均复现同一 setup/hold error、`Errors=2`。3004 归属 `V_DRM18K_E1`，8756 归属 `V_FFASYN`；level3 仅为非 canonical 诊断，canonical level2 验收未改，S2-F 仍 blocked。输入/模型 SHA-256 已归档，逐档 work/launcher 会清理，日志与汇总 JSON 只进入 `build/`。
- OV7725 O0-A 已形成 [CDC/RDC 审计与整改契约](../41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md)，覆盖七类时钟域、帧事件多点采样、两个异步 FIFO 的数据方向/分侧复位风险及三条旧 STA 失败路径；本批只建立事实和契约，未修改 RTL、IP 或 FDC。
- OV7725 O1-B 已按 [RTL 卫生修复评审](../41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md) 完成：原 39 条手写 RTL 位宽告警中的 38 条确定性问题已消失，只保留活动 IP 14 bit 与顶层/FDC 15 bit 冲突的 `ddr3_ip.mem_a` 1 条；O1-C 已取消，该项冻结为 legacy 风险。
- O1-B 已从空 `build/` 完成 SP6.4 七阶段，进程退出 0、日志 `E: 0`，warning `4067`、critical `81`；非零产物为综合网表 `6,873,482`、PNR 网表 `11,604,756`、SDF `8,898,464`、`.sbit` `3,791,112` 和 `.bin` `3,789,476` 字节。
- O1-B 严格 gate 返回 `1`；baseline gate 只在 corner、check、clock pair 与 endpoint 数量精确匹配七组已知失败时返回 `0`，并明确标记不可发布。新 Slow Recovery `pixel_clk → pixel_clk_5x` 为 `-0.643 ns / -4.191 ns / 8/8`，端点正是四个 serializer 内的八个 OSERDES，转入 O2-A/O2-B；QuestaSim/S3 动态验证仍未完成。
- OV7725 O2-A 已形成 [Serializer Reset 联合释放契约](../41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md)：确认同一高有效 `RST` 同时受 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并固定 O2-B 首选为现有 `pixel_clk` 两级释放后再级联 `pixel_clk_5x` 两级释放，只驱动八个 OSERDES。本批未修改 RTL/FDC、未运行 PDS 或 QuestaSim。
- OV7725 O2-B 已按该契约完成 compile 和从空 `build/` 的七阶段实验，但最终 STA 报告 Slow Recovery `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8`、`pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。该方案已被否决，功能 RTL 已回退；旧七组 baseline 和 gate 均未放宽。
- OV7725 O2-D1 已否决动态 `GTP_IOCLKBUF` 门控路线：SP6.4 Liberty 无 `DI` clock-gating check，不能静态证明停钟、复位、释放和启钟顺序。O2-D1-G 曾收口 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位与本地 reset 复制候选；O2-D2 已取消，该候选仅作历史风险证据。
- O2-D1-R 已从空 `build/` 重建回退后的七组旧失败基线：baseline gate 精确匹配并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，O2-B 的 `54` 不修改旧 baseline。O2-D1-G 已收口 `/5` generated-clock、奇数分频 waveform、pre/post-buffer 取点、状态/复位分权和停止条件；后续实现已取消。
- O2-D1-G 契约已冻结：只允许一条 `pixel_clk` `/5` generated clock，源为 PLL wrapper `u_pll_clk/clkout1`、目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形 `-edges {1 5 11} -edge_shift {0 0 0}`；控制器状态为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`，并定义 hard/business reset 分权与首个有效 TMDS symbol。
- OV7725 M3-A 迁移前审计（2026-08-30）：四个活动 IP 均由 SP4.2 生成且与 SP6.4 安装版本断层（DDR3 `1.12→1.10`、PLL `1.3→1.5`、rd/wr FIFO `1.8→1.10`）；隔离探针分别以 `IPCompiler 0037` 和 `IPCompiler 0057` 拒绝旧 IDF override。owner 已冻结 OV7725 产品主线，M3-B 和 canonical 升格取消；上述参数、资源、RCF 和旧 100H baseline 只作为防误用证据，双 OV5640 必须在新项目独立建立 IP/FDC/STA。
- S0-0/S0-0-R（2026-08-30）只保留为历史环境复核；其“未发现仿真器”的结论已被 2026-09-01 的 Questa Sim-64 2021.1 实际执行证据取代。
- S0-1 仿真库入口已完成实际验收：Questa Sim-64 2021.1 最小 SystemVerilog 通过，PDS SP6.4 Logos2 USIM/VSIM 均编译成功；VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 库目录非空。最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- CI-0 仓库级静态一致性门禁已完成并提交：`scripts/check_repo_consistency.ps1` 门禁退出码为 0，本批提交时全部 7 个 PowerShell 脚本 AST 解析错误数为 0；该门禁不启动或替代 PDS、STA、ModelSim/QuestaSim。
- PCIe S2-C BAR1 staging 合同（2026-09-01）已禁止旧 dry-run 产生的非法 `BAR1_MASK=31'h0(`。允许差异仅为 `BAR1_Enable: false→true` 与 `BAR1_Size: 256→512 Bytes`，并必须保持 `BAR1_MASK_EN=false`、`BAR1_MASK=31'h0`。`check_s2c_bar1` 动态生成并解析 XML，验证唯一差异及 canonical IDF/wrapper SHA 不变；损坏 mask 与缺 `index.xml` 的负向测试均失败。17 个实时 origin 分支、完整历史/reflog、工作区和 SP6.4 安装中均未找到匹配 PCIe 1.2c 的 `index.xml`；原始完整实例必须匹配 IP ID `042004`、build `146967`、`PG2L50H/FBG484/-6`，新版本迁移须另立批次。canonical BAR1 仍关闭，S2-C 未通过。
- PCIe S2-C 归档诊断 run `d1d25d3f23384590918f26abbfd2e839` 由 RC 主动完成 EP BAR0 写入/读回，在 `710535 ns` 输出唯一 `INFO: S2C_DMA_WRITE_READBACK_OK` 与唯一 `TEST PASS`，Errors 0、厂商 Warnings 26、PowerShell 退出 0。该结果只证明诊断路径可运行，不是 Endpoint 主动 MRd/CplD/MWr DMA 闭环；BAR1 仍禁用，`index.xml` 输入阻断不变，S2-C 不得标记为通过。
- 三项目 S1/S2/S3 仿真就绪度盘点见 [仿真就绪度矩阵](../docs/SIMULATION_READINESS_MATRIX.md)：PCIe S2-E PNR 后功能已动态通过；S2-F 已执行但因 GLS/STA 冲突和负时序模型语义不完整而 blocked。S2-C、DDR3/OV5640 四级仿真仍未完成。
- CI-1 仿真矩阵引用门禁已扩展到当前产品范围：矩阵必须包含 DDR3、PCIe、OV5640/S3，并明确 OV7725 为 legacy；根 README 和 TODO 也必须链接该矩阵。该门禁只验证静态文档一致性，不替代动态仿真。
- CI-2 板级证据清单完整性门禁已由提交 `677808d` 落地：`scripts/check_repo_consistency.ps1` 为 OV7725 legacy、DDR3、PCIe 三个存量目录分别登记清单路径与关键词，要求对应 README 直接链接清单，并强制三份清单包含“当前工程事实”“必须提供的资料”“关闭条件”结构；PCIe 清单已统一为同一章节规范。2026-08-30 复验退出码为 0。双 OV5640 的 `59_top_dual_ov5640_hdmi/doc/BOARD_EVIDENCE.md` 仍是 C1 待办；现有门禁通过不代表该产品清单存在，也不代表板级证据已经提供或关闭。
- CI-3 README 元数据完整性门禁已由提交 `5bfaae9` 落地：按项目特征检查三项目 README 是否记录器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断；2026-08-30 复验退出码为 0。该门禁只检查静态可追溯表达，不代表硬件参数已审核或功能阻断已关闭。
- CI-4 PDS 构建 gate 契约完整性门禁已由提交 `66356aa` 落地：三项目 `run.ps1` 均检查 PDS 退出码、`^E:` 错误记录和阶段完成标记；三项目 `check_build.ps1` 均检查阶段/最终构建入口、时序摘要、`throw` 失败路径、非零产物及显式 baseline 开关。2026-08-30 复验仓库门禁退出码为 0；该门禁只验证 gate 代码路径，不替代真实 PDS、STA 或位流执行。
- CI-5 PowerShell AST 语法门禁已由提交 `5769d8f` 落地：仓库门禁自动解析全部非 `build/`、`.git/` 的 `.ps1` 文件，报告具体文件、行号和错误消息；当前 8 个脚本解析通过。该门禁只验证 PowerShell 语法，不执行 PDS、仿真器或项目构建。
- CI-6 DDR3 D3-0-R 契约一致性门禁已由提交 `a5d1785` 落地：静态交叉核对活动 DDR3 core、`test_ddr` wrapper 与 `D3A_PORT_MAP.md` 的模块/参数、128-bit 数据、28-bit 地址、`I_ips_ddr_top`、AXI-like 握手及 core 不含 `axi_rready`；该门禁不替代 PG2L50H IP 重生成后的重新审核或动态验证。
- CI-7 PDS Tcl 入口分类门禁现覆盖全部 14 个 tracked Tcl；新增 DDR3 `scripts/build_staging_compile.tcl` 归为非发布 `canonical_support_tool`，只有三个项目 `scripts/build.tcl` 是 `run.ps1` 入口。PCIe build 已为 PG2L50H canonical，OV7725/DDR3 build 仍为 PG2L100H migration-blocked；历史、厂商和 compile-only 支持脚本不得作为 STA、网表、SDF 或位流发布证明。正向门禁退出 0，删除任一清单项的负向测试退出 1。
- CI-9 许可证敏感门禁（2026-09-01）由 `scripts/check_sensitive_diff.ps1` 与 [`SENSITIVE_DIFF_GATE.md`](../docs/SENSITIVE_DIFF_GATE.md) 定义：`-FullTree` 全量扫描当前 tracked/untracked 工作树，PR 模式按 merge-base 扫描变更路径与新增行。当前版本已将 68 个 tracked 日志中的 143 处本机许可证引用替换为 `<license-path>`，全树与差异门禁均通过。门禁使用严格占位符白名单，并拒绝许可证文件名、机器本地许可证引用、真实许可证环境赋值、裸端点、FlexNet 内容、签名和 host id；它只保护当前树和后续新增差异，不改写或清理 Git 历史。
- CI-0、S0-1 入口与强制预检、仿真就绪度矩阵、README 导航、CI-1 至 CI-9、H2-B0、CI-8A、PCIe S2-A、S0-0-R、PCIe H2-B 静态元数据 gate、H0/H1/H3 证据清单、M0/M1、M2-A、M2-B1、M2-B2 与 M3-A 均按小批次记录；样本仍不足以计算可信的历史热点，CI-8B 等待 DDR3 与双 OV5640 canonical 升格。
- 根目录 [README](../README.md) 是 PDS 外部实现与仿真指南，现已直接链接仿真就绪度矩阵。
- 根目录 [TODO](../TODO.md) 是当前整改顺序和验收门槛。
- 新增或修改 Verilog/SystemVerilog 时必须遵循 [VSCS](../VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md)。

## 先读路由

进行工程修改前，按任务读取：

- [系统边界](arch/systems.md)
- [依赖关系](arch/dependencies.md)
- [测试与时序证据](arch/test_coverage.md)
- [领域概念](concepts/domains.md)
- [Git 基线与高关注区](hotspots/git_forensics.md)
- [机器可读概念模型](concepts/concept_model.json)

## 当前优先级

1. PCIe S2-E PNR 后功能已通过；下一步继续 S2-C DMA 与 SDF 时序仿真，不把该无 SDF smoke 外推为链路、DMA、时序、实板或发布证据。
2. H0/H1/H3 补齐板卡、原理图/BOM、器件丝印、bank 电压、DDR3 料号/拓扑及 OV5640/HDMI 时序资料；资料缺失时不得猜测参数、I/O delay 或收紧 gate。
3. 双 OV5640 C0 已完成：17 个 HDMI 明文 RTL、4 个 TB、4 个 PCIe video 参考文件、4 个 PG2L100H 生成 IP，以及 PDS/FDC/BAR、VSCS/CDC/RDC 风险已登记。C1 继续等待两路模组、MCLK、电压、DVP、DDR3、HDMI 和管脚事实；冻结后才允许选择性导入 `59_top_dual_ov5640_hdmi/`，4 个参考 TB 不能原样计入 S3。
4. DDR3 M2-B2 已用 PG2L50H staging 完成独立 compile-only 闭包，但没有加载 FDC/RCF 或执行实现后级。下一步仍须依据原理图/BOM 审核 28 项 FDC pin 差异及 DDR3 颗粒/拓扑，再决定是否升格 canonical；升格后必须重跑 CI-6、空目录七阶段与 D3-0-R，审核通过后才可进入 D3-A → D3-B → D3-C。
5. PCIe M1 已完成 build/PDS/gate 的 PG2L50H 迁移和空 `build/` 重建；活动 PCIe IP 无需因器件型号重生成。H2-B 仍等待 lane/refclk/PERST#/SCBV 与 UART 决策闭环。
6. PCIe S2-A 受控行为 smoke、S2-B 真实厂商 RC/EP 链路和 S2-D 综合后受限 smoke 均已通过。S2-D 只关闭综合网表展开、reset debounce/sync 与 reference-clock LED counter 路径；S2-C Endpoint 主动 DMA、PNR、SDF、时序、H2-B1 和发布 gate 保持未完成。
7. 摄像头产品最终闭环属于双 OV5640 C2 → C3 → S3；`41_ov7725_hdmi/sim/questa/` 仅 legacy，新的可复现仿真源必须归档到 `59_top_dual_ov5640_hdmi/sim/questa/`，运行态只进其 `build/`。

## 更新规则

当顶层、器件、IP 边界、时钟域、约束、测试结果或 Git 基线发生变化时，应同步更新本目录。人工推断必须继续标明证据缺口；未执行的工具流程不得记录为通过。
