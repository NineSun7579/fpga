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
- 未验证：动态仿真、USIM/VSIM 编译和 SDF 标注；安装 ModelSim/QuestaSim 并确认三个可执行文件后，才可解除该阻塞。

## CI-0 仓库级静态一致性门禁（2026-08-30）

- 已验证：新增 `scripts/check_repo_consistency.ps1`，覆盖根指南/TODO/VSCS、三个项目 README、PDS 构建入口、顶层声明、七阶段命令、可配置工具路径、退出码、baseline 开关、产物/时序检查接口和 `build/` 忽略状态。
- 已验证：三个项目 README 的 PDS `2022.2-SP6.4`、顶层模块或仿真状态缺口已修正；门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 已验证：仓库内全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- 边界：CI-0 不启动 PDS 或 ModelSim/QuestaSim，不替代项目严格 gate、STA 或四级仿真。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| OV7725 HDMI | O1-B 基线与 O2-B 实验均完成 SP6.4 compile/七阶段且日志无 `E:`；O2-B 失败 RTL 已回退，旧构建入口和 gate 未修改 | O2-B Slow Recovery：`pixel_clk_5x → pixel_clk_5x -0.349/8/8`、`pixel_clk → pixel_clk_5x +1.111/0/1`、`pixel_clk_5x → pixel_clk -2.173/8/8`；Fast 反向组 `-1.464/8/8`。方案被否决；严格 gate=1，旧七组 baseline gate=0 且不可发布 | 未就绪；Questa/S3 缺失 | O2-B 实验综合网表已生成，未仿真 | O2-B 实验 PNR 网表已生成，未仿真 | O2-B 实验 SDF 已生成，未标注验证 |
| DDR3 外层 | 从空 `build/` 完成 SP6.4 七阶段全流程，日志无 `E:`；综合网表 `5,914,586`、PNR 网表 `9,734,239`、SDF `9,130,393`、`.sbit` `3,791,112`、`.bin` `3,789,476` 字节 | `All Constraints Met`；慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`、recovery `4.578 ns`、removal `0.351 ns` | D2 有限自检契约已定，项目自有顶层尚未实现；Questa 缺失 | 综合网表已生成，有限自检顶层未实现、未运行 | PNR 网表已生成，有限自检顶层未实现、未运行 | SDF 已生成，未标注验证 |
| PCIe DMA | 新 SP6.4 全流程完成，日志无 `E:`；新网表、SDF、`.sbit/.bin` 非零 | 新最终报告通过：慢角 setup WNS `0.584 ns`、TNS `0`，hold WHS `0.138 ns` | 仅 IP 示例 | 顶层未闭环 | 生成网表但未运行 | SDF 已生成但未标注验证 |

## 已知功能与覆盖缺口

- OV7725：`41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md` 已记录七类时钟域、`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和分侧复位风险，以及三条旧 STA 失败路径。
- OV7725：O1-B 已完成 38 条确定性 RTL 卫生修复，手写 RTL 位宽告警只剩 `mem_a` 1 条；该单项因活动 IP 14 bit 与顶层/FDC 15 bit 冲突继续转 H3/O1-C，当前综合网表把 `mem_a[14]` 绑 0。
- OV7725：O2-B 详细 STA 将反向八个 endpoint 唯一映射到 `serializer_b/g/r/clk × opit_2/opit_2_com` 的 OSERDES `OCLKDIV` 检查；慢角高速同域 `OCLK` 也仍为负。该覆盖证明候选失败，不构成 serializer reset 通过证据。
- OV7725：O2-D1-R 已从空 `build/` 完成七阶段，baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，没有新增失败签名或 waiver。O2-D1-G 现已冻结：只允许一条 `pixel_clk` `/5` generated clock，源 `u_pll_clk/clkout1`、目标唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`、波形 `-edges {1 5 11} -edge_shift {0 0 0}`，并使用 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN` 状态契约；审核前不实现 O2-D2，QuestaSim/S3 未完成。
- DDR3：临时 `test_ddr` bring-up 已完成全流程与内部 STA/产物基线。严格 gate 因 7 类问题返回 1：BIST error-data 位宽不匹配、BIST dangling cleanup、`rst_board` 使用 share pin、BANKR4 VCCIO 3.3 不兼容、UART I/O 约束缺失、顶层输入 timing 缺失、顶层输出 timing 缺失。显式 baseline 放行返回 0，但明确标记不可发布。
- DDR3：本次完整构建日志没有 SCBV 命中；这不替代板级批准参数清单。DDR3 颗粒/组织、VCCIO/VREF、ODT、拓扑、走线、UART/ADC 决策等仍缺少审核依据。
- DDR3：testbench 端口仍失配，BIST 无天然有限完成状态，缺少可靠 `$fatal`、超时、唯一 `TEST PASS` 和四级仿真证据；当前结果只验收可重复实现基线，不验收板级功能或产品状态。
- DDR3：D2 已以只读方式固定后续测试契约，厂商 `test_ddr`、持续运行 BIST 和旧 testbench 保持原样。计划新增 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`，首版执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并设置 4096 周期 pair timeout 与 131072 周期 run timeout。
- DDR3：未来行为仿真必须通过公开且稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息判定结果；D2 与 D3-0 仅完成只读决策，不构成实现或测试覆盖，D3-A/B/C 仍待用户审核。
- DDR3 D3-0（只读静态评审）：活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`，公开端口包含 `ddr_init_done`、`core_clk` 与 AW/W/AR/R 自定义 AXI-like 接口；`test_ddr.v` 的物理 board wrapper 实例名为 `I_ips_ddr_top`，必须保留。
- DDR3 D3-0 已完成非标准 AXI-like 握手评审：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回依赖 `axi_rvalid`/`axi_rlast` 且无 `axi_rready`。D3-A 等待用户审核后按该契约实现，接口语义、地址单位或层级变化即停止并重新审核。
- PCIe：现有 ModelSim 资产只覆盖 PCIe IP 示例，不覆盖 `pcie_dma_test` 集成顶层；UART2APB 的无驱动输入属于已知功能缺陷。
- PCIe H2-A（只读证据矩阵）：顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与 `ref_led/pclk_led`；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。当前没有 lane 极性/板级拓扑、I/O delay 或 SCBV 证据。
- PCIe H2-A 器件边界：`ipcore/pcie_test/pcie_test.idf` metadata 为 `Logos2/PG2L50H/FBG484/-6`，PDS 工程目标为 `Logos2/PG2L100H/FBG484/-6`；在 IP 重生成前不得把实现结果当作目标器件签核。UART2APB `rxd/txd` 为隐式连接且 `rxd` 被绑 0，属于独立功能阻断。
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
8. PCIe H2-B 只有在 lane 极性/板级拓扑、I/O delay、SCBV、IDF/PDS 器件一致性和 UART2APB 端口归属均有证据后才可收紧 gate；任一缺口时保持 H2-A 只读状态。
