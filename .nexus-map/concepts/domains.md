> generated_by: Codex manual bootstrap
> verified_at: 2026-09-01
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

2026-08-30 S0 环境复核的“未发现仿真器”结论已被后续实际执行证据取代。截至 2026-09-01，Questa Sim-64 2021.1 最小 SystemVerilog 已通过，参数化 `scripts/compile_simlib.tcl`/`.ps1` 已成功生成 Logos2 USIM/VSIM；VSIM 编译退出 0、日志无 `^E:` 且库目录非空。

2026-08-30 CI-7 入口分类确认全部 13 个 tracked Tcl 已登记。只有三个项目 `scripts/build.tcl` 通过 `run.ps1` 进入 `pds_shell`；PCIe 为 PG2L50H canonical，OV7725/DDR3 仍为 PG2L100H migration-blocked。`impl.tcl`、parse-design screen、厂商 IP PNR 和单 IP 仿真脚本中的旧器件、混合目标或绝对路径只保留为历史/内部证据，不能用于当前器件、STA、网表、SDF、位流或集成仿真签核。

2026-09-01 CI-9 将许可证保密边界落实为新增差异门禁：`scripts/check_sensitive_diff.ps1` 依据 Git merge-base 扫描 tracked 新增路径、diff 新增行和未跟踪文本，仅接受严格白名单占位表达，并拒绝新增许可证文件、绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名及 host id。门禁自检与真实分支扫描均通过；它只防止新的泄露进入提交，不读取实际配置，也不清理历史。

2026-08-30 用户确认 DDR3、PCIe、OV7725 HDMI 共用 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`，统一 PDS 目标为 `Logos2/PG2L50H/FBG484/-6`。M0 已完成器件事实审核；M1 先迁移 PCIe build/gate，M2 重生成 DDR3 50H IP/FDC/RCF，M3 重生成 OV7725 四个 50H IP并建立新 baseline。所有 PG2L100H 产物不得烧录。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

2026-08-30 仿真就绪度盘点时三个项目均无项目级 TB、`.f` 或 `.do`。截至 2026-09-01，PCIe S2-A 已完成项目级受控行为 smoke 动态验证：`sim/behav.f` 单独补入仿真所需 `ips2l_pcie_apb_cross_v1_0.v`，不修改由 IDF 管理实现侧源的 `scripts/pds_sources.f`；TB 使用厂商要求的 `GRS_INST`，DO 通过 `echo` 将随机 `SIM_RUN_ID` 写入 transcript。最终 `vlog` 为 0 errors/0 warnings，`vsim` elaboration 成功并运行到 `1476105 ns`，Errors 0/Warnings 2、唯一 `TEST PASS`，PowerShell 同 run-id/唯一 PASS 门禁通过。另有最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。OV7725 与 DDR3 仍缺项目级入口，三个项目真实网表/SDF 仿真仍待完成。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D3-0（2026-08-30）已完成只读边界评审：活动 IP 是 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`，其端口包含 `core_clk`、`ddr_init_done` 以及自定义 AXI-like AW/W/AR/R 接口；`test_ddr.v` 的物理 board wrapper 实例名必须保留为 `I_ips_ddr_top`。

D3-0 已确认旧 IP 接口不能按标准 AXI ready/valid 擅自解释：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回使用 `axi_rvalid`/`axi_rlast` 且没有 `axi_rready`。CI-6 已保护该静态事实，但 M2 必须重生成 PG2L50H IP/FDC/RCF并重跑门禁；只有端口、地址单位与 `I_ips_ddr_top` 层级重新确认并审核后才可进入 D3-A。

DDR3 M2-B1 通过 PDS SP6.4 `ui.tcl` 确认 `DEVICE_100H_EN` 是隐藏派生参数：`PG2L100H/HX=true`，`PG2L50H=false`。因此禁止直接用 `-device PG2L50H` 覆盖 100H IDF；该路径会保留错误的 `true` 并选择 PPLL `FALSE/CLKOUTF` 分支。活动 100H IDF 与 SP6.1 50H seed 的全部参数只有此 flag 不同，更新后的 `scripts/regenerate_ip.ps1` 会先验证参数一致，再由 SP6.4 build 146967 生成正确 50H staging：`DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，canonical 哈希不变。正确差异覆盖 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF；wrapper 由 21 增至 26 个端口并新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，FDC 有 28 项 pin 差异。审计证据为 `doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`；原理图/BOM 缺失时不得升格 canonical，D3-A 仍未授权。

PCIe H2-A（2026-08-30）固定产品顶层的板级边界：`pcie_dma_test` 使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；当前 FDC 仅固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。lane 极性、板级拓扑、I/O delay 和 SCBV 均没有证据，不能由实现成功推断。

PCIe H2-B0（2026-08-30）将五类 baseline 问题归一化为 16 个唯一签名、42 次原始记录，并以完整多重集保护失败状态；任何签名新增、消失、改名、share-pin 位置或次数漂移均失败，IDF metadata 漂移永久硬失败。canonical fixture 正向为 0、strict 为 1，缺失/重复 UART、Timing 端口改名、share pin 改位和 100H IDF 五个变异均为 1。H2-B1 仍受 lane/refclk/PERST#/SCBV/UART/I/O timing 外部资料阻断；partial run 复用旧 full-build 证据的风险已由 PCIe CI-8A 关闭。

PCIe CI-8A（2026-08-31）把构建证据定义为一次运行的不可拆分集合：37 个 HDL 单一清单、43 项 canonical 输入和 7 项最终证据由同一 32 位 run_id 与 SHA-256 manifest 绑定。每次 build 开始即原子失效旧 complete 证据；`running/partial/failed` 均不可验收，只有 `complete/valid` 可继续 H2-B0/strict gate。partial、工具缺失、run-id、产物或 FDC 漂移均失败；最终 PG2L50H full build/baseline/strict 为 `0/0/1`，slack `0.100 ns`。CI-8B 等待 DDR3/OV7725 canonical 升格后逐项目迁移，不预先共享实现。

PCIe S2-A（2026-09-01）只验证产品壳层受控行为 smoke。受控模型替代生成的 `pcie_test`，提供确定性时钟、复位、idle 接口和延迟 link 激励；TB 验证顶层展开、两路外部/同步复位、两组 LED 计数门控及可观察输出未知态。两条 `vsim` warning 均来自 `pcie_dma_test.v` 中 `u_ips2l_pcie_dma` 未连接输出 `o_trgt1_radm_pkt_halt`，作为独立 RTL hygiene TODO，不影响本层受控 smoke PASS。模型产生的 link indication 不证明真实 LTSSM、TLP、DMA 或板级链路；S2-B 必须改用厂商 RC/EP 验证真实链路，S2-C 才执行基础 DMA 回读。

实物确认后，活动 `pcie_test.idf` 的 `Logos2/PG2L50H/FBG484/-6` metadata 被证明正确；错误项是顶层 build/PDS/gate 和现有主产物仍为 PG2L100H。M1 不为型号重复生成 PCIe IP，而是修正项目自有 build/gate、清空旧 build并建立 50H baseline，同时继续阻断 UART2APB、lane/refclk/PERST# 与 SCBV 缺口。

DDR3 D2 已进一步固定该边界：厂商 `test_ddr`、持续运行 BIST 与旧 testbench 保持原样；后续有限自检由项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 承担。首版仅执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并通过稳定公开的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息完成签核。

## CDC 与异步 FIFO

单比特电平、脉冲、多比特数据和 FIFO 指针需要不同跨时钟域策略。同步器降低亚稳态传播概率但不消除亚稳态；时序例外只能施加在结构已验证的 CDC 上。

OV7725 的帧同步当前是长电平而非单周期脉冲，且 `wr_load`/`rd_load` 分别被多个逻辑独立采样。整改契约要求源域用 toggle 或握手表达事件，目标 `ui_clk` 域只同步一次、生成单周期事件后统一扇出，避免多同步器重汇聚。

厂商异步 FIFO 可以承担多比特数据跨域，但 reset/flush 仍属于 RDC。write FIFO 的 camera/UI 两侧和 read FIFO 的 UI/pixel 两侧必须分别在本地时钟域释放复位；只有确认 SP6.4 对厂商指针同步结构的识别后，才允许添加最窄范围例外。

## 复位域交叉

各时钟域应明确复位来源和释放方式。外部异步条件或其他时钟域状态直接释放复位会形成 recovery/removal 风险，应采用异步置位、同步释放或等效的经验证结构。

OV7725 已确定 sys、I2C、camera、pixel 和 DDR UI 域需要各自的本地复位。O3-A 必须先将 `ddr3_init_done` 同步为 camera/pixel 域的状态与使能，O2-C1 才能解除它对其他域异步复位释放的直接控制并建立普通时钟域本地复位。

O1-B 将高有效 reset 接入四个 serializer 内的八个 OSERDES 后，PDS 新报告 Slow Recovery `pixel_clk → pixel_clk_5x` `-0.643 ns / TNS -4.191 ns / 8/8`。O2-A 已确认 SP6.4 对同一 `RST` 同时建立 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并将八个唯一 `opit_2/opit_2_com/OSR_IOLHR` endpoint 固定为验收集合。

O2-B 已实现上述级联结构并完成 compile/七阶段实验，但 Slow Recovery 同时出现 `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8` 和 `pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。八个反向 endpoint 均为 OSERDES `OCLKDIV` 检查；方案已否决、RTL 已回退，baseline/gate 未放宽。

旧 PG2L100H O2-D1 已否决动态 `GTP_IOCLKBUF` 门控，其 Liberty 没有 `DI` clock-gating check；O2-D1-G 曾收口出 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 与本地 reset 复制候选。该结论不能机械继承到 PG2L50H；M3 必须重生成四个活动 IP、重建 50H baseline并重新计算相位/端点后，再提请 O2-D2 审核。

M3-A 进一步确认迁移不能从旧 IDF 开始：DDR3、PLL、FIFO 的活动版本与 SP6.4 安装版本全部断层，`IPCompiler 0037/0057` 已否决 CLI override。唯一允许路径是 SP6.4 GUI 在 PG2L50H 目标下新建当前版本实例并只写 staging；DDR3 `DEVICE_100H_EN=false`、PLL `DEVICE_PG2L50H=true` 和 FIFO 85 DRM36K/170 DRM18K 上限必须由新实例证明。RCF 对象命中、DDR3 组织和板级电气未关闭前，不得升格 canonical。

O2-D1-R 已完成回退基线重建：七组失败精确复现，Slow/Fast `ddrphy_sysclk → pixel_clk` 均为 `53/53`，endpoint 分类为 read FIFO 控制 26、RAM reset 8、video driver 17、video display 1、原 DVI reset 同步器 1。O2-D1-G 已冻结 `/5` 奇数分频 waveform 和取点：必须显式且仅创建一个 `pixel_clk` generated clock，源为 PLL wrapper `u_pll_clk/clkout1`，目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形为 `-edges {1 5 11} -edge_shift {0 0 0}`，master 为唯一 `CLKOUT1_Inferred`，旧 `CLKOUT0_Inferred` 对 pixel 域零消费者，divider 不得接 post-buffer。

O2-D1-G 的唯一控制器状态序列为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`：`HARD_HOLD` 对 `!sys_rst_n || !pll_lock` 异步保持并清 divider、pixel/business、四路本地 serializer reset 和计数；`QUALIFY` 要求 4 个 control_clk 周期；`ARM` 释放 `/5`、同步释放 pixel reset、强制 encoder `CTRLTOKEN0` 条件并等待 3 个 pixel 周期；`SER_RELEASE` 在同步 `arm_req` 后下一个 control 周期清除四个本地 reset，驻留 2 个完整 control 周期；`RUN` 才撤销 encoder 强制。计数表示已完成周期且饱和，阈值统一用 `N-1`。

复位分权固定为：sys_rst_n 下降或 pll_lock 丢失可异步回 HARD_HOLD；普通 video/business reset 只能撤销 RUN 并重新 warm-up，不得组合异步驱动 OSERDES 本地 reset；`ddr3_init_done` 不参与 hard reset、QUALIFY、ARM、OSERDES reset 或状态转移，后续仅作为同步业务 enable/status；FIFO reset/flush 独立归 O2-C2。首个有效 TMDS symbol 是 serializer reset 下降后首个 `OCLKDIV` 上升沿采入的四路同时确定完整 TMDS 并行字，不等同于首个活动像素；RUN 至少延后两个 control 周期确保其完整发送。

审核后只允许一次 O2-D2；generated-clock 对象为 0/多对象、源计数非 1、自动/显式重名、waveform 不符、divider 接 post-buffer、八个 OSERDES endpoint 的 Slow/Fast Recovery/Removal 未全覆盖或为负、PDS/gate/产物失败、或出现新 baseline 失败签名，均立即停止并完整回退。禁止第二相位扫描、false path、multicycle、clock-group waiver 或放宽 baseline。

两个厂商异步 FIFO 的 reset/flush 属于独立的 O2-C2，不与 O2-C1 的普通寄存器复位混批；帧事件 CDC 归 O3-B。O4 只有在 O2-C2 与 O3-B 都完成后才可进入约束和最终时序闭环。

## 时序闭环

`All Constraints Met` 只覆盖已建模路径。验收还需检查未约束时钟、未约束关键 I/O、CDC 报告、setup/hold/recovery/removal、SDF 标注与板级接口假设。

## PDS 生成物与可重复构建

GUI 原生工程目录中的日志、数据库和绝对路径脚本是历史证据，不是可移植构建入口。目标结构应以相对路径脚本和统一 `build/` 目录隔离生成物。

OV7725 O1-B 已按该边界固定 16 个手写 RTL、4 个活动 IDF 和唯一顶层 FDC，在 SP6.4 下完成七阶段实现：进程退出 0、日志 `E: 0`、warning `4067`、critical `81`，五类产物均非零。严格 gate 返回 1；baseline 只有在七组 corner/check/clock pair/endpoints 精确匹配时返回 0，并继续标记不可发布。

## RTL 卫生与板级接口边界

OV7725 O1-A 以 `RTL_HYGIENE_AUDIT.md` 固定手写 RTL 卫生契约，O1-B 已完成其中 38 条确定性修复：显式零扩展、定宽 tie-off、地址/长度编码、`rst_n` 声明、删除 `sys_init_done` 死网及 serializer reset 连接均已落地。

serializer 接收高有效 reset；O1-B 已让该信号驱动四个 serializer 内共八个 OSERDES 的高有效 `RST`。O2-B 级联释放实验已由 STA 否决并回退，O2-D1-R 已证明当前仍精确复现旧七组失败基线；O2-D1-G 完成并经用户审核前不得启动新的 serializer RTL。

`mem_a` 是板级接口冲突而非机械消警：活动 IP 为 14 bit，顶层/FDC 为 15 bit，当前综合网表将第 15 bit 绑 0。它必须等待 H3 板级 DDR3 事实并在 O1-C 独立处理；O1-B 不修改 `mem_a`、IP、FDC、CDC/RDC 或时序例外。

## VSCS 注释治理

后续手写 Verilog/SystemVerilog 应记录设计意图、接口契约、FSM、复位、CDC/RDC 和风险，不重复可以从代码、Git 或工具报告自动推导的事实。
