> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: current worktree, PDS project files, implementation reports, root audit notes, and manual inspection; no AST extraction or Git-history statistics

# Embedded Completion Nexus Map

本仓库汇集三个 Pango FPGA 工程，并以根目录文档约束后续整改方式：

- `41_ov7725_hdmi/`：OV7725 采集、DDR3 帧缓存与 HDMI/TMDS 输出；已完成 SP6.4 七阶段可重复实现和产物/gate 基线，但最终时序失败。
- `ddr3_test/`：已用厂商 `test_ddr` 临时 bring-up 顶层完成 SP6.4 全流程实现、STA、网表/SDF、位流与构建 gate 验证；严格 gate 仍被板级和 RTL 已知问题阻断，它不是已验收的产品顶层。
- `pcie_dma_test_100h/`：PCIe x2 DMA 集成顶层；实现和时序通过，但 H2-A 发现板级收发器资料与 IP 器件元数据缺口，且 UART2APB 通道存在隐式 `rxd/txd` 连接、`rxd` 被绑 0 的功能缺口。

三个工程当前有效器件目标均按 `Logos2 / PG2L100H / FBG484 / -6` 审计。2026-08-30 S0 环境复核确认唯一已发现工具为 `E:\pango\PDS_2022.2-SP6.4\bin\pds_shell.exe`；PATH、`C:\questasim64\win64` 及常见 ModelSim/QuestaSim 目录均未找到 `vsim.exe`、`vlog.exe`、`vlib.exe`。PDS 负责实现，外部 ModelSim/QuestaSim 负责仿真；动态仿真仍阻塞，安装仿真器后才可编译 USIM/VSIM。

## 当前基线

- Git 分支：`main`。
- Git 基线提交：`1a2d493`（三个原始工程、已有报告和整改文档）。
- 原始 PDS 生成物仍位于各 GUI 工程目录中；新增流程统一输出到被忽略的 `build/`。
- PCIe 已完成新 `build/` 全流程、STA、网表/SDF/位流和严格 gate 验证。
- DDR3 已从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，日志无 `E:`；最终报告为 `All Constraints Met`，慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`、recovery `4.578 ns`、removal `0.351 ns`。
- DDR3 已生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`；严格 gate 因 7 类已知阻断返回 1，显式 baseline 放行返回 0 但明确不可发布。日志没有 SCBV 命中，板级批准参数清单仍缺失，功能与四级仿真仍未验收。
- DDR3 D2 只读决策已完成：厂商 `test_ddr`、持续运行 BIST 和失配 testbench 保持原样；后续项目自有顶层固定为 `rtl/ddr3_bringup_top.sv` 与 `rtl/ddr3_finite_bist.sv`。首版契约执行 16 个单 beat 写读比较 pair，控制器地址为 `0x0..0x78`、步长 8，单 pair timeout 为 4096 周期、整次 run timeout 为 131072 周期，并公开稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息。该设计尚未实现或仿真，D3 待审核。
- DDR3 D3-0 只读评审（2026-08-30，已完成）：已固定活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`、非标准 AXI-like AW/W/AR/R 握手和 `I_ips_ddr_top` board wrapper 边界。D3-A 等待用户审核后按该契约实现；接口语义、地址单位或层级变化即停止并重新审核。本批只记文档，不改 RTL、IP 或约束。
- PCIe H2-A 只读证据（2026-08-30，已完成）：`pcie_dma_test` 顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与两枚 LED；当前 FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。FDC 未提供 lane 极性/板级拓扑、I/O delay 或 SCBV；活动 `pcie_test.idf` metadata 仍为 `Logos2/PG2L50H/FBG484/-6`，而 PDS 目标为 `Logos2/PG2L100H/FBG484/-6`。UART2APB 的 `rxd/txd` 为隐式连接，`rxd` 被绑 0。
- OV7725 O0-A 已形成 [CDC/RDC 审计与整改契约](../41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md)，覆盖七类时钟域、帧事件多点采样、两个异步 FIFO 的数据方向/分侧复位风险及三条旧 STA 失败路径；本批只建立事实和契约，未修改 RTL、IP 或 FDC。
- OV7725 O1-B 已按 [RTL 卫生修复评审](../41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md) 完成：原 39 条手写 RTL 位宽告警中的 38 条确定性问题已消失，只保留活动 IP 14 bit 与顶层/FDC 15 bit 冲突的 `ddr3_ip.mem_a` 1 条；该项仍属于 H3/O1-C。
- O1-B 已从空 `build/` 完成 SP6.4 七阶段，进程退出 0、日志 `E: 0`，warning `4067`、critical `81`；非零产物为综合网表 `6,873,482`、PNR 网表 `11,604,756`、SDF `8,898,464`、`.sbit` `3,791,112` 和 `.bin` `3,789,476` 字节。
- O1-B 严格 gate 返回 `1`；baseline gate 只在 corner、check、clock pair 与 endpoint 数量精确匹配七组已知失败时返回 `0`，并明确标记不可发布。新 Slow Recovery `pixel_clk → pixel_clk_5x` 为 `-0.643 ns / -4.191 ns / 8/8`，端点正是四个 serializer 内的八个 OSERDES，转入 O2-A/O2-B；QuestaSim/S3 动态验证仍未完成。
- OV7725 O2-A 已形成 [Serializer Reset 联合释放契约](../41_ov7725_hdmi/doc/SERIALIZER_RESET_CONTRACT.md)：确认同一高有效 `RST` 同时受 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并固定 O2-B 首选为现有 `pixel_clk` 两级释放后再级联 `pixel_clk_5x` 两级释放，只驱动八个 OSERDES。本批未修改 RTL/FDC、未运行 PDS 或 QuestaSim。
- OV7725 O2-B 已按该契约完成 compile 和从空 `build/` 的七阶段实验，但最终 STA 报告 Slow Recovery `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8`、`pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。该方案已被否决，功能 RTL 已回退；旧七组 baseline 和 gate 均未放宽。
- OV7725 O2-D1 已否决动态 `GTP_IOCLKBUF` 门控路线：SP6.4 Liberty 无 `DI` clock-gating check，不能静态证明停钟、复位、释放和启钟顺序。O2-D1-G 已将唯一待验证候选收口为新增 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位控制输出，并为每个 serializer 本地复制 reset 寄存器；候选仍未实现或签核。
- O2-D1-R 已从空 `build/` 重建回退后的七组旧失败基线：baseline gate 精确匹配并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，O2-B 的 `54` 不修改旧 baseline。下一步由 O2-D1-G 收口 `/5` generated-clock、奇数分频 waveform、pre/post-buffer 取点、状态/复位分权和单次试验停止条件。
- O2-D1-G 契约已冻结：只允许一条 `pixel_clk` `/5` generated clock，源为 PLL wrapper `u_pll_clk/clkout1`、目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形 `-edges {1 5 11} -edge_shift {0 0 0}`；控制器状态为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`，并定义 hard/business reset 分权与首个有效 TMDS symbol。
- S0-0 环境复核（2026-08-30，已完成）：PDS shell 路径存在且可作为唯一已发现工具；未发现 `vsim.exe`/`vlog.exe`/`vlib.exe`，动态仿真与 USIM/VSIM 编译保持阻塞。
- S0-1 仿真库入口已作为独立批次提交：参数化 `scripts/compile_simlib.tcl` 与 `scripts/compile_simlib.ps1` 支持 ModelSim/QuestaSim、USIM/VSIM/BOTH、Logos2 family、语言、PDS/仿真器路径和输出目录覆盖。预检绕过开关已从工作区移除，入口始终检查 `vsim.exe`、`vlog.exe`、`vlib.exe`；两个相关 PowerShell 脚本 AST 错误数为 0，CI-0 门禁通过，默认运行仍因缺少 `vsim.exe` 在 PDS 前返回 1，因此实际库编译保持阻塞。
- CI-0 仓库级静态一致性门禁已完成并提交：`scripts/check_repo_consistency.ps1` 门禁退出码为 0，本批提交时全部 7 个 PowerShell 脚本 AST 解析错误数为 0；该门禁不启动或替代 PDS、STA、ModelSim/QuestaSim。
- 三项目 S1/S2/S3 仿真就绪度只读盘点已形成 [仿真就绪度矩阵](../docs/SIMULATION_READINESS_MATRIX.md)：三个项目均无项目级 TB、`.f` 或 `.do`；现有资产全部属于厂商 DDR3/PLL/FIFO/PCIe IP 示例，只能作为模型与接口参考，不能作为产品集成顶层验收。本批矩阵尚未提交，S0-1 仍阻断全部动态仿真。
- CI-0 仓库级静态一致性门禁已作为独立批次提交；随后 S0-1 入口与强制预检也已独立提交，仓库累计 27 个 Git 提交，样本仍不足以计算可信的历史热点。
- 根目录 [README](../README.md) 是 PDS 外部实现与仿真指南。
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

1. S0-1 的参数化 `compile_simlib` Tcl/PowerShell 入口已准备并强制预检三项仿真器可执行文件，不提供绕过开关；当前仍受 ModelSim/QuestaSim 安装、许可证及工具路径阻断，只有实际 Logos2 USIM/VSIM 编译退出 0、日志无 `E:` 且库目录非空后才解除动态仿真阻断。
2. H0/H1/H3 补齐板卡、原理图/BOM、器件丝印、bank 电压、DDR3 料号/拓扑及 OV7725/HDMI 时序资料；资料缺失时不得猜测参数、I/O delay 或收紧 gate。
3. O2-D2 等待用户书面审核 O2-D1-G 契约；通过后只执行一次 PLL 重生成、控制器与 `/5` generated-clock 实现，任一对象、warning、CDC、SDF、时序或 baseline 漂移异常即完整回退。
4. DDR3 D3-0 握手语义与 `I_ips_ddr_top` 边界评审已完成；D3-A → D3-B → D3-C 等待用户审核后依次实现骨架、16 个有限 pair 与七阶段回归，厂商 `ip_core/ddr3/**` 保持原样。
5. PCIe H2-B 等待 H0/H2 板级资料、UART 保留/删除决策及 PG2L100H IP 重生成审核；完成器件、lane/refclk/PERST#/SCBV 与精确 gate 闭环前保持阻断。
6. S1/S2/S3 等待 S0-1 完成且对应 RTL/IP/网表/SDF 锁定；三项目还必须分别新增项目自有集成 TB、相对路径 `.f`/`.do` 和四级入口，禁止以厂商 `test_ddr`、DDR3/PLL/FIFO 示例或 `pango_pcie_top` RC/EP 示例冒充产品验证。
7. OV7725 最终链为 O1-C → O3-A → O2-C1 → O2-C2 → O3-B → O4，前置为 H3 板级事实与 O2-D2 结果；最终必须完成非负 setup/hold/recovery/removal、SDF、位流和仿真闭环。

## 更新规则

当顶层、器件、IP 边界、时钟域、约束、测试结果或 Git 基线发生变化时，应同步更新本目录。人工推断必须继续标明证据缺口；未执行的工具流程不得记录为通过。
