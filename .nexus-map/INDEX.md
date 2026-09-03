> generated_by: Codex manual bootstrap
> verified_at: 2026-09-03
> provenance: current worktree, PDS project files, implementation reports, root audit notes, and manual inspection; no HDL/raw-source AST extraction or Git-history statistics; PowerShell AST syntax gate is recorded as CI-5

# Embedded Completion Nexus Map

本仓库汇集三个 Pango FPGA 工程，并以根目录文档约束后续整改方式：

- `41_ov7725_hdmi/`：OV7725 采集、DDR3 帧缓存与 HDMI/TMDS 输出 legacy；已完成的 SP6.4 构建、STA、CDC/RDC 和 gate 结果只保留为历史证据，不得改名冒充 OV5640 产品实现。
- `ddr3_test/`：已用厂商 `test_ddr` 临时 bring-up 顶层完成 SP6.4 全流程实现、STA、网表/SDF、位流与构建 gate 验证；严格 gate 仍被板级和 RTL 已知问题阻断，它不是已验收的产品顶层。
- `pcie_dma_test_100h/`：PCIe x2 DMA 集成顶层；已按 PG2L50H 修正构建脚本/gate，并从空 `build/` 完成七阶段重建，HSSTLP 资源固定为 `HSSTLP_292_612`；S2-A 项目级受控行为 smoke 已由 Questa Sim-64 2021.1 动态验证，UART2APB 仍有隐式 `rxd/txd`、`rxd` 被绑 0 的功能缺口。

用户于 2026-08-30 确认三个产品方向最终共用 `RK3568+PG2L50H100H` 开发板，实际焊接器件为 `PG2L50H-6IFBG484`；PDS 统一目标因此修正为 `Logos2 / PG2L50H / FBG484 / -6`。摄像头 HDMI 产品目标于 2026-09-01 校正为 OV5640，范围见 [`OV5640_TARGET_SCOPE.md`](../docs/OV5640_TARGET_SCOPE.md)；现有 OV7725 工程只作 legacy。全部 PG2L100H 构建、STA 和位流只保留为历史证据，不得烧录或作为实板签核。

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
- DDR3 D3-0-R 端口映射已由提交 `2fd7c51` 固化到 [`D3A_PORT_MAP.md`](../ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md)：记录默认参数/宽度、128-bit 数据通路、28-bit 地址、AW/W/AR/R 握手、复位链和 `I_ips_ddr_top` 层级；地址单位与 `axi_wready` 完成语义仍待审核。
- PCIe H2-A 只读证据（2026-08-30，已完成）：`pcie_dma_test` 顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与两枚 LED；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。活动 `pcie_test.idf` 已正确标识 `Logos2/PG2L50H/FBG484/-6`，M1 已将 build/PDS/gate 与新产物统一到 50H，并按 PDS 模板将 HSSTLP 固定为 `HSSTLP_292_612`。lane 极性/板级拓扑、I/O delay、SCBV 和 UART2APB 归属仍未关闭。
- H0/H1/H3 板级资料清单已由提交 `12d7a21` 建立：[OV7725 HDMI 清单](../41_ov7725_hdmi/doc/BOARD_EVIDENCE.md) 与 [DDR3 Bring-up 清单](../ddr3_test/ddr3_test/doc/BOARD_EVIDENCE.md) 均由对应项目 README 直接链接。两份清单只定义待提供字段、证据来源和关闭条件；实际板级资料仍未提供，H0/H1/H3 保持外部阻断。
- 板级证据补充提交 `11dfcc2` 已确认两项具体歧义：OV7725 活动 DDR3 IDF 由 PDS `SP4.2` 生成，`MEM_ADDR_WIDTH`、`DDR3_MEM_ROW_WIDTH`、`MEM_ROW_WIDTH` 均为 14，而手写顶层/FDC 使用 15 bit；DDR3 活动 IDF 同时记录 `DESIRED_DDR3_RATE=1066.000` 与另一处 `1050.000` 速率值。前者保持 H3/O1-C 阻断，后者保持 H1 阻断，均不得在缺少料号、原理图和参数语义证据时猜测修正。
- PCIe H2-B 静态元数据 gate 已由提交 `03b694a` 落地；M1 已将期望值统一为 `Logos2/PG2L50H/FBG484/-6`，并增加 build log、timing report、`bgr.db` 的产物器件交叉校验，防止陈旧 PG2L100H 位流通过；UART、lane/refclk/PERST#/SCBV 阻断继续保留。
- PCIe H2-B0 精确 baseline（2026-08-30）已将五类问题归一化为 16 个唯一签名、42 次原始记录；baseline 使用精确多重集，签名新增/消失/改名、share-pin 位置或次数漂移均失败，活动 IDF metadata 漂移永久硬失败。canonical fixture 正向退出 0、strict 退出 1，5 个变异（缺失/重复 UART、Timing 端口改名、share pin 改位、IDF 改为 PG2L100H）均退出 1。
- H2-B1 仍等待 lane/refclk/PERST#/SCBV/UART/I/O timing 的板级资料和决策。H2-B0 发现的 partial run 复用旧 full-build 日志/产物风险已由 PCIe CI-8A 关闭；DDR3/OV7725 的 CI-8B 仍待各自 canonical 升格。
- PCIe CI-8A provenance pilot（2026-08-31）已完成：`scripts/pds_sources.f` 成为 37 个 HDL 的单一有序清单，`build_provenance.ps1` 为每次 build 生成 32 位 `run_id`，并原子发布固定的 `build/provenance/pds-build.json`。manifest 状态为 `running/partial/failed/complete`，只有 `complete + valid=true` 可进入 gate；43 项 canonical 输入和 7 项最终证据均以相对 POSIX 路径、长度和 SHA-256 绑定。partial compile、PDS executable 缺失、run-id、产物与 FDC 漂移均使 gate 返回 1。
- CI-8A 最新完整 PG2L50H 构建 run id 为 `c24bc06b5d0643eeb6c9cb2878e7ace5`，manifest 为 `run_to=gen_bit_stream / status=complete / valid=true`，绑定 43 项输入和 7 项最终证据。该次 baseline gate 返回 0、strict gate 返回 1，最差 slack `0.100 ns`，H2-B0 的 16/42 指纹保持不变；它证明当前输入的失败基线可复现，不表示可发布。CI-8B 仅在 DDR3/OV7725 各自 PG2L50H canonical 升格后迁移同一事实模型。
- PCIe S2-A 的历史动态受控 smoke 已由 Questa Sim-64 2021.1 通过：`sim/behav.f` 单独补入仿真所需 `ips2l_pcie_apb_cross_v1_0.v`，实现侧 `scripts/pds_sources.f` 保持不变；历史结果为唯一 `TEST PASS`。当前版本的 S2-A/S2-B 静态门禁仍通过，但动态复验在 Questa 启动时因仓库外许可证 checkout 失败返回 4，未产生新的 run marker 或 `TEST PASS`；旧日志不得冒充本次结果。
- OV7725 O0-A 已形成 [CDC/RDC 审计与整改契约](../41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md)，覆盖七类时钟域、帧事件多点采样、两个异步 FIFO 的数据方向/分侧复位风险及三条旧 STA 失败路径；本批只建立事实和契约，未修改 RTL、IP 或 FDC。
- OV7725 O1-B 已按 [RTL 卫生修复评审](../41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md) 完成：原 39 条手写 RTL 位宽告警中的 38 条确定性问题已消失，只保留活动 IP 14 bit 与顶层/FDC 15 bit 冲突的 `ddr3_ip.mem_a` 1 条；该项仍属于 H3/O1-C。
- O1-B 已从空 `build/` 完成 SP6.4 七阶段，进程退出 0、日志 `E: 0`，warning `4067`、critical `81`；非零产物为综合网表 `6,873,482`、PNR 网表 `11,604,756`、SDF `8,898,464`、`.sbit` `3,791,112` 和 `.bin` `3,789,476` 字节。
- O1-B 严格 gate 返回 `1`；baseline gate 只在 corner、check、clock pair 与 endpoint 数量精确匹配七组已知失败时返回 `0`，并明确标记不可发布。新 Slow Recovery `pixel_clk → pixel_clk_5x` 为 `-0.643 ns / -4.191 ns / 8/8`，端点正是四个 serializer 内的八个 OSERDES，转入 O2-A/O2-B；QuestaSim/S3 动态验证仍未完成。
- OV7725 O2-A 已形成 [Serializer Reset 联合释放契约](../41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md)：确认同一高有效 `RST` 同时受 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并固定 O2-B 首选为现有 `pixel_clk` 两级释放后再级联 `pixel_clk_5x` 两级释放，只驱动八个 OSERDES。本批未修改 RTL/FDC、未运行 PDS 或 QuestaSim。
- OV7725 O2-B 已按该契约完成 compile 和从空 `build/` 的七阶段实验，但最终 STA 报告 Slow Recovery `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8`、`pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。该方案已被否决，功能 RTL 已回退；旧七组 baseline 和 gate 均未放宽。
- OV7725 O2-D1 已否决动态 `GTP_IOCLKBUF` 门控路线：SP6.4 Liberty 无 `DI` clock-gating check，不能静态证明停钟、复位、释放和启钟顺序。O2-D1-G 已将唯一待验证候选收口为新增 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位控制输出，并为每个 serializer 本地复制 reset 寄存器；候选仍未实现或签核。
- O2-D1-R 已从空 `build/` 重建回退后的七组旧失败基线：baseline gate 精确匹配并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，O2-B 的 `54` 不修改旧 baseline。下一步由 O2-D1-G 收口 `/5` generated-clock、奇数分频 waveform、pre/post-buffer 取点、状态/复位分权和单次试验停止条件。
- O2-D1-G 契约已冻结：只允许一条 `pixel_clk` `/5` generated clock，源为 PLL wrapper `u_pll_clk/clkout1`、目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形 `-edges {1 5 11} -edge_shift {0 0 0}`；控制器状态为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`，并定义 hard/business reset 分权与首个有效 TMDS symbol。
- OV7725 M3-A 迁移前审计（2026-08-30）：四个活动 IP 均由 SP4.2 生成且与 SP6.4 安装版本断层（DDR3 `1.12→1.10`、PLL `1.3→1.5`、rd/wr FIFO `1.8→1.10`）；隔离探针分别以 `IPCompiler 0037`（未指定安装路径）和 `IPCompiler 0057`（版本不匹配）拒绝旧 IDF override。唯一允许路径是 SP6.4 IP Compiler GUI 在 `Logos2/PG2L50H/FBG484/-6` 下新建当前版本实例，并只输出 `41_ov7725_hdmi/build/ipgen/pg2l50h/**`；禁止手改版本/器件/隐藏参数或原地覆盖 canonical。DDR3 必须验证 `DEVICE_100H_EN=false`，PLL 必须验证 `DEVICE_PG2L50H=true`，FIFO 必须满足 PG2L50H 的 85 个 DRM36K/170 个 DRM18K 资源上限；旧 RCF 对象命中未证明，旧 100H baseline/STA/位流作废，板级资料和完整差异审核通过前不得 canonical 升格。
- S0-0/S0-0-R（2026-08-30）只保留为历史环境复核；其“未发现仿真器”的结论已被 2026-09-01 的 Questa Sim-64 2021.1 实际执行证据取代。
- S0-1 仿真库入口已完成实际验收：Questa Sim-64 2021.1 最小 SystemVerilog 通过，PDS SP6.4 Logos2 USIM/VSIM 均编译成功；VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 库目录非空。最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- CI-0 仓库级静态一致性门禁已完成并提交：`scripts/check_repo_consistency.ps1` 门禁退出码为 0，本批提交时全部 7 个 PowerShell 脚本 AST 解析错误数为 0；该门禁不启动或替代 PDS、STA、ModelSim/QuestaSim。
- 三项目 S1/S2/S3 仿真就绪度盘点见 [仿真就绪度矩阵](../docs/SIMULATION_READINESS_MATRIX.md)：DDR3 与 OV5640 仍无项目级 TB/`.f`/`.do`，OV7725 资产只作 legacy 参考；PCIe S2-A 保留历史动态 PASS，S2-A/S2-B 当前静态门禁通过，但当前动态复验受仓库外许可证 checkout 阻断。三个项目的综合后/PNR 功能/PNR 时序与 SDF 仿真仍未执行。
- CI-1 仿真矩阵引用门禁已扩展到当前产品范围：矩阵必须包含 DDR3、PCIe、OV5640/S3，并明确 OV7725 为 legacy；根 README 和 TODO 也必须链接该矩阵。该门禁只验证静态文档一致性，不替代动态仿真。
- CI-2 板级证据清单完整性门禁已由提交 `677808d` 落地：`scripts/check_repo_consistency.ps1` 为 OV7725、DDR3、PCIe 分别登记清单路径与关键词，要求各项目 README 直接链接清单，并强制三份清单包含“当前工程事实”“必须提供的资料”“关闭条件”结构；PCIe 清单已统一为同一章节规范。2026-08-30 复验退出码为 0。该门禁只验证结构与导航，不代表板级证据已经提供或关闭。
- CI-3 README 元数据完整性门禁已由提交 `5bfaae9` 落地：按项目特征检查三项目 README 是否记录器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断；2026-08-30 复验退出码为 0。该门禁只检查静态可追溯表达，不代表硬件参数已审核或功能阻断已关闭。
- CI-4 PDS 构建 gate 契约完整性门禁已由提交 `66356aa` 落地：三项目 `run.ps1` 均检查 PDS 退出码、`^E:` 错误记录和阶段完成标记；三项目 `check_build.ps1` 均检查阶段/最终构建入口、时序摘要、`throw` 失败路径、非零产物及显式 baseline 开关。2026-08-30 复验仓库门禁退出码为 0；该门禁只验证 gate 代码路径，不替代真实 PDS、STA 或位流执行。
- CI-5 PowerShell AST 语法门禁已由提交 `5769d8f` 落地：仓库门禁自动解析全部非 `build/`、`.git/` 的 `.ps1` 文件，报告具体文件、行号和错误消息；当前 8 个脚本解析通过。该门禁只验证 PowerShell 语法，不执行 PDS、仿真器或项目构建。
- CI-6 DDR3 D3-0-R 契约一致性门禁已由提交 `a5d1785` 落地：静态交叉核对活动 DDR3 core、`test_ddr` wrapper 与 `D3A_PORT_MAP.md` 的模块/参数、128-bit 数据、28-bit 地址、`I_ips_ddr_top`、AXI-like 握手及 core 不含 `axi_rready`；该门禁不替代 PG2L50H IP 重生成后的重新审核或动态验证。
- CI-7 PDS Tcl 入口分类门禁（2026-08-30）已稳定：机器清单覆盖全部 13 个 tracked Tcl，角色为 `canonical_project_build`、`migration_blocked_project_build`、`canonical_support_tool`、`historical_gui`、`vendor_generated_internal`、`vendor_sim_internal`；只有三个 `scripts/build.tcl` 是 `run.ps1` 入口。PCIe build 已为 PG2L50H canonical，OV7725/DDR3 build 仍为 PG2L100H migration-blocked；历史/厂商脚本中的混合器件或绝对路径不得作为器件、STA、网表、SDF 或位流证明。正向门禁退出 0，删除任一清单项的负向测试退出 1。
- main OV5640→PCIe M3-A（2026-09-03）在 M2-A 灰度流后新增 `rgb565_word_packer` 与 `ov5640_dvp_rgb565_word_pipeline`：8 个 RGB565 像素按接收顺序组成 128-bit 字，像素 0 位于低 16 bit；N 像素部分行尾字补零并使用 `word_keep` 低 `2N` 位。帧/行起止和协议错误可附着数据字或作为空载控制事件。Questa Sim-64 2021.1 编译 6 个 RTL/TB 模块为 `0 error/0 warning`，集成行为返回 0 且日志唯一 `TEST PASS`。该证据只关闭内部图像字布局，不证明 CDC/FIFO、DDR3、PCIe AXIS/TLP、主机协议或 PDS/STA。
- M3-A 协议与回归修正（2026-09-03）：两个 TB 现区分 payload（`word_valid && word_keep!=0`）与纯控制事件（`word_valid=1`、`word_keep=0`）。全回归中的 Questa `vopt signal 11` 根因确认为 D 盘仅余约 16 KB、数据库写满；清理忽略的 `build/` 运行态后 accounting 重新 PASS。
- main OV5640→PCIe M3-B 同域联合 staging（2026-09-03）保留 `ov5640_dvp_rgb565_dma_staging_pipeline` 证据：同域串接采集、灰度、128-bit 打包、4-byte staging 与帧统计描述符；3 像素输入得到 2 个 beat、6 个有效字节，描述符无协议错误。Questa Sim-64 2021.1 编译 9 个 RTL/TB 为 `0 error/0 warning`，行为返回 0 且日志唯一 `TEST PASS`。`staging_ready` 与 accounting ready 合取施加数据背压，`frame_end_pending` 仅为无输入背压同域验证策略；不证明真实 FIFO/CDC、DDR3、PCIe 或后级实现。
- main OV5640→PCIe M3-B 两槽 word skid（2026-09-03）由 `main_ov5640_pcie/rtl/rgb565_word_skid_buffer.sv`、`main_ov5640_pcie/tb/tb_rgb565_word_skid_buffer.sv` 与 `main_ov5640_pcie/scripts/run_m3b_word_skid_buffer.ps1` 定义：满队列溢出时保留已排队前缀、置位 sticky `overflow`、丢弃当前帧余量，并在前缀后恰好注入一个 `keep=0/frame_end=1/protocol_error=1` 中止记录。只有原帧尾已被观察且中止记录已排队，后续 `frame_start` 才恢复接收；在此之前到达的新帧整帧跳过。扩展专项 TB 还覆盖满队列同拍 pop/push、原 `frame_end` 与 abort 入队同拍、连续两个损坏帧各自产生唯一 abort 且顺序正确，以及 drop/abort 状态异步复位。Questa Sim-64 2021.1 编译 2 个 RTL/TB 为 `0 error/0 warning`，日志唯一 `TEST PASS`，仿真至 526 ns；不保证持续背压无丢帧，也不证明真实 DDR3/PCIe 闭环。
- main OV5640→PCIe M3-B 联合 CDC staging（2026-09-03）在 `ov5640_dvp_rgb565_cdc_staging_pipeline` 中串接 DVP→灰度→128-bit 打包→word skid→4-byte staging→双时钟 CDC。正常期 3 像素输出 2 个 payload beat 加 1 个 `keep=0` 空载帧尾事件且无 overflow；压力期 64 像素输入触发 sticky `source_overflow`，恢复 ready 后共输出 20 个 beat，其中恰好 1 个为空载错误中止记录，随后下一帧从 `frame_start` 完整恢复并输出 2 个 beat。Questa Sim-64 2021.1 编译 11 个 RTL/TB 为 `0 error/0 warning`，行为返回 0、日志唯一 `TEST PASS`，仿真至 2863 ns；不证明静态 CDC/RDC、复位、真实 DDR3/PCIe/主机协议或后级实现，也不等同真实 DDR3/PCIe 闭环通过。
- main OV5640→PCIe normalized MWR descriptor（2026-09-03）新增 `rgb565_axis4_mwr_descriptor` 及 TB：作为 vendor-independent PCIe Memory Write request descriptor，仅验证地址递增、`keep`、`last`、`frame_end` 与 4KB 边界标志；不接厂商 PCIe IP，也不证明 TLP、DMA、DDR3 或主机协议。
- main OV5640→PCIe MWR bridge（2026-09-03）由 `rgb565_axis4_pcie_mwr_bridge` 及 TB/脚本定义：把规范化请求映射到已审计 `mwr32_req/ack`，统一锁存 length/address/data/keep/4KB 状态及 last/frame_end/protocol_error，并在 ack 前保持全部字段稳定。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、76 ns；byte-enable 映射仍为临时合同，不代表真实 PCIe TLP/DMA 通过。
- main OV5640→PCIe M3-B（2026-09-03）由 `rgb565_axis4_pcie_mwr_path` 串接 staging beat、MWR descriptor 和请求 bridge。专项 TB 以 `BASE_ADDR=0x0ffc` 验证 4-byte 请求恰到 4KB 边界、首请求等待 ack 时预取下一条带帧尾/错误记录仍保持当前请求全部字段、ack 后地址为 `0x1000`；Questa Sim-64 2021.1 为 `0 error/0 warning`、唯一 `TEST PASS`、115 ns。该路径不实例化厂商 PCIe IP，不证明真实 TLP、DMA、byte-enable、链路或主机输出。
- main OV5640→PCIe normalized DDR3 write record（2026-09-03）新增 `ADDR_STEP` 参数并完成增强回归：TB 覆盖空 keep 控制记录、背压字段保持、连续 `ADDR_STEP` 地址推进及复位后 `BASE_ADDR` 覆盖；Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、126 ns。地址仍为 opaque 28-bit token，单 beat 128-bit/16-bit strobe，不假定地址单位、初始化或 AXI4 burst。
- main OV5640→PCIe M3-B 异步 FIFO/CDC bridge（2026-09-03）新增 `rgb565_axis4_cdc_bridge`：封装 `rgb565_axis4_async_fifo`，为 staging beat 提供上游/下游双时钟 ready/valid 边界，数据携带 `keep/last/user` 事件。Questa Sim-64 2021.1 独立 3 ns/5 ns 时钟下完成 5 beat 顺序、首末事件、keep/last、ready 与最终 drain 回归，0 error/0 warning、唯一 `TEST PASS`，155 ns。期间发现并修正 FIFO entry 41 bit/实际 42 bit 导致 `user[4]` 截断的缺陷。尚未完成静态 CDC/RDC、RAM 推断、复位释放、三时钟约束、真实 DDR3/PCIe IP 集成。
- main OV5640→PCIe M3-B 行为级 DDR3/PCIe loopback（2026-09-03）由 `tb_ov5640_ddr3_pcie_loopback.sv` 与对应脚本定义：正常 3 像素帧仍形成 3 条记录；DDR writer 阻塞下的 64 像素压力帧形成 21 条记录，唯一空载错误 abort 位于索引 20，随后 1 像素恢复帧形成 2 条正常记录。全部记录经 DDR3 模型回读到 PCIe MWR，abort 与恢复 payload 地址同为 `0x104c`，证明 `keep=0` 不推进图像字节地址。DDR3 模型在 `posedge` valid/ready 握手边沿采集写事务。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、3844 ns；不证明真实 DDR3 地址/握手、PCIe TLP/链路/DMA/主机或板级时序。
- main OV5640→PCIe M3-B frame commit（2026-09-03）由 `rgb565_axis4_frame_commit` 聚合每帧记录，除 bytes/records/error/committed 外保留首条记录的 opaque token 与 slot id；同一帧中 slot id 变化会并入协议错误并拒绝提交。TDD 在旧实现上于 47 ns 因槽号检查失败，最终 Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、240 ns。token 不是 DDR3 物理地址，slot id 也尚未形成完整双槽数据链。
- main OV5640→PCIe M3-B 双槽帧控制面（2026-09-03）新增 `rgb565_axis4_frame_slot_table.sv`、专项 TB 与 Questa 脚本：两个槽分别执行 `FREE→WRITING→QUEUED→READING→FREE`，错误帧从 `WRITING→FREE`；写分配是背压保持型 valid/ready，正常描述符进入深度 2 committed FIFO，内部 `reader_active` 保证任一时刻只有一个 READING。`read_done` 必须匹配 active slot，错槽或迟到完成只产生 fault、不释放槽；`SLOT_RECORD_CAPACITY` 超限帧 fault-drop。TDD 先出现目标 RTL 缺失红灯，再在连续 `read_desc_ready` 场景于 126 ns 暴露第二描述符错误开放；最终 Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、406 ns。槽表仍未实例化到 DDR writer、frame read scheduler 或 committed wrapper，因此当前不是完整双槽闭环。
- main OV5640→PCIe M3-B frame read scheduler（2026-09-03）统一命令、响应接收和帧完成语义：按首 opaque token 与记录数产生单 outstanding 顺序命令，支持命令与零延迟响应同拍；提前 `frame_end` 或最终响应缺失 `frame_end` 均归一化为帧尾并产生 protocol fault/完成，`committed && records=0` 直接 fault-complete。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、346 ns。token 仍只是数组索引，不是 DDR3 物理地址。
- main OV5640→PCIe M3-B frame readout gate（2026-09-03）由 scheduler 的响应接受资格配对读记录，并由统一 `frame_done_pulse` 关闭窗口；专项 Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、211 ns。
- main OV5640→PCIe M3-B committed PCIe MWR 路径（2026-09-03）已接入上述 scheduler，显式参数化 `TOKEN_ADDR_STEP`，并向集成层暴露 `frame_done_pulse/frame_fault_pulse`；错误帧仍为 1 drop、0 读命令、0 MWR。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、576 ns。当前 wrapper 仍向 frame commit 固定输入 slot 0，并丢弃输出 slot id，未实例化新槽表；该路径无物理双槽复用，不实例化真实 DDR3/PCIe IP，也不证明 PCIe TLP/DMA/链路或主机内存写入。
- main OV5640→DDR3模型→已提交 PCIe 单一回归（2026-09-03）由 `tb_ov5640_ddr3_committed_pcie_loopback.sv` 验证：正常 token `0..2` 依次形成 MWR `0x2000/0x2004/0x2006`；压力错误帧保存 21 条记录但只产生 1 次 drop、0 读命令和 0 MWR；恢复帧 token `21/22` 依次形成 MWR `0x2000/0x2004`。最新 Questa Sim-64 2021.1 仍为 0 error/0 warning、唯一 `TEST PASS`、3158 ns。DDR 模型仅以 opaque token 索引数组，不代表物理双槽、真实 DDR3 地址/IP 或真实 PCIe 链路。
- CI-9 许可证敏感门禁（2026-09-01）由 `scripts/check_sensitive_diff.ps1` 与 [`SENSITIVE_DIFF_GATE.md`](../docs/SENSITIVE_DIFF_GATE.md) 定义：`-FullTree` 全量扫描当前 tracked/untracked 工作树，PR 模式按 merge-base 扫描变更路径与新增行。当前版本已将 68 个 tracked 日志中的 143 处本机许可证引用替换为 `<license-path>`，全树与差异门禁均通过。门禁使用严格占位符白名单，并拒绝许可证文件名、机器本地许可证引用、真实许可证环境赋值、裸端点、FlexNet 内容、签名和 host id；它只保护当前树和后续新增差异，不改写或清理 Git 历史。
- CI-0、S0-1 入口与强制预检、仿真就绪度矩阵、README 导航、CI-1 至 CI-9、H2-B0、CI-8A、PCIe S2-A、S0-0-R、PCIe H2-B 静态元数据 gate、H0/H1/H3 证据清单、M0/M1、main OV5640 M2-A/M3-A、DDR3 M2-B1 与 OV7725 legacy M3-A 均按小批次记录；样本仍不足以计算可信的历史热点，CI-8B 等待 DDR3/OV7725 canonical 升格。
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

1. Questa Sim-64 2021.1 工具与 Logos2 USIM/VSIM 的历史验证保留；当前动态 checkout 返回 4，恢复仓库外许可证后必须以新 run id 重跑，不能复用旧 PASS。
2. H0/H1/H3 补齐板卡、原理图/BOM、器件丝印、bank 电压、DDR3 料号/拓扑及 OV5640/HDMI 时序资料；资料缺失时不得猜测参数、I/O delay 或收紧 gate。
3. OV5640 按 [`OV5640_TARGET_SCOPE.md`](../docs/OV5640_TARGET_SCOPE.md) 推进：C0 只读审计参考工程，C1 冻结单/双摄、模组与接口，C2 设计新项目/顶层和 SCCB/采集/DDR3/HDMI 边界，C3 在 PG2L50H 下完成实现；S3 建立四级自检仿真。OV7725 O0/O1/O2/M3-A 仅作 legacy 问题清单和可复用性参考。
4. DDR3 M2-B1 已纠正 staging 生成路径并完成参数/资产差异审计；下一步依据原理图/BOM 审核 28 项 FDC pin 差异及 DDR3 颗粒/拓扑，再决定是否升格 canonical。升格后必须重跑 CI-6、空目录七阶段与 D3-0-R，审核通过后才可进入 D3-A → D3-B → D3-C。
5. PCIe M1 已完成 build/PDS/gate 的 PG2L50H 迁移和空 `build/` 重建；活动 PCIe IP 无需因器件型号重生成。H2-B 仍等待 lane/refclk/PERST#/SCBV 与 UART 决策闭环。
6. PCIe S2-A 历史受控行为 smoke 保留为已通过证据；S2-A/S2-B 静态门禁当前通过，动态复验需先恢复仓库外许可证。随后 S2-B 使用真实厂商 RC/EP 验证链路，S2-C 才验证 DMA。
7. 摄像头产品最终闭环属于 OV5640 C0 → C1 → C2 → C3 → S3；OV7725 的 O1-C/O2/O3/O4 链不再自动授权产品实现，只能在 C2 审核后选择性迁移结构经验。

## 更新规则

当顶层、器件、IP 边界、时钟域、约束、测试结果或 Git 基线发生变化时，应同步更新本目录。人工推断必须继续标明证据缺口；未执行的工具流程不得记录为通过。
