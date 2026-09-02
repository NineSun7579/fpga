> generated_by: Codex manual bootstrap
> verified_at: 2026-09-02
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

2026-08-30 S0 环境复核的“未发现仿真器”结论已被后续实际执行证据取代。截至 2026-09-01，Questa Sim-64 2021.1 最小 SystemVerilog 已通过，参数化 `scripts/compile_simlib.tcl`/`.ps1` 已成功生成 Logos2 USIM/VSIM；VSIM 编译退出 0、日志无 `^E:` 且库目录非空。

CI-7 入口分类现确认全部 14 个 tracked Tcl 已登记；新增 DDR3 `scripts/build_staging_compile.tcl` 为非发布 `canonical_support_tool`。只有三个项目 `scripts/build.tcl` 通过 `run.ps1` 进入 canonical 项目构建链；PCIe 为 PG2L50H canonical，OV7725/DDR3 正式 build 仍为 PG2L100H migration-blocked。`impl.tcl`、parse-design screen、厂商 IP PNR、单 IP 仿真和 compile-only 支持脚本中的旧器件、混合目标或绝对路径只保留为历史、内部或受限验证证据，不能用于当前 STA、网表、SDF、位流或集成仿真签核。

2026-09-01 CI-9 同时覆盖当前树和 PR 差异：`-FullTree` 扫描 tracked/untracked 工作树，PR 模式依据 Git merge-base 扫描 changed paths 与 added lines。当前版本已将 68 个 tracked 日志中的 143 处许可证绝对路径替换为 `<license-path>`；全树和差异门禁均通过。门禁不读取实际配置，也不改写 Git 历史。

摄像头产品固定双 OV5640。C0 已对 `origin/parallel_driver@485f3bba71e4b57fb8bb49cec30e9d331b952be3` 完成只读审计，登记 17 个 HDMI 明文 RTL、83 个生成/受保护依赖、4 个 TB、4 个 PCIe video 参考文件、4 个 PG2L100H 生成 IP 及 FDC/PDS 风险；本批没有导入实现文件。参考 `top_dual_ov5640_hdmi` 使用两路独立 SCCB/RESET/PWDN/DVP，每路采集 960x1080 半幅，通过双写 DDR3 组成 1920x1080。2026-09-02 已建立 `59_top_dual_ov5640_hdmi/README.md` 与项目级 `BOARD_EVIDENCE.md`，并将其纳入板级证据门禁；该目录仍无 RTL/IP/FDC/TB，C1/H3 保持阻断。输入冻结后才允许选择性导入并独立建立 PG2L50H 证据；`41_ov7725_hdmi` 仅 legacy。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

双 OV5640 C0 已审计 4 个参考 TB，但尚未选择性导入；`tb_dual_ov5640_dri.v` force `cam_init_done`，成功字符串也不是 canonical `TEST PASS`，且没有覆盖双摄→DDR3→HDMI 集成链，不能计入产品覆盖。未来可复现仿真源只进入 `59_top_dual_ov5640_hdmi/sim/questa/`，运行态只进入其 `build/`；禁止导入 `sim_*`、`work`、`.mpf`、`modelsim.ini`、日志、波形、绝对路径生成物或许可证配置。`41_ov7725_hdmi/sim/questa/` 仅 legacy。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D3-0（2026-08-30）已完成只读边界评审：活动 IP 是 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`，其端口包含 `core_clk`、`ddr_init_done` 以及自定义 AXI-like AW/W/AR/R 接口；`test_ddr.v` 的物理 board wrapper 实例名必须保留为 `I_ips_ddr_top`。

D3-0 已确认旧 IP 接口不能按标准 AXI ready/valid 擅自解释：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回使用 `axi_rvalid`/`axi_rlast` 且没有 `axi_rready`。CI-6 已保护该静态事实，但 M2 必须重生成 PG2L50H IP/FDC/RCF并重跑门禁；只有端口、地址单位与 `I_ips_ddr_top` 层级重新确认并审核后才可进入 D3-A。

DDR3 M2-B1 通过 PDS SP6.4 `ui.tcl` 确认 `DEVICE_100H_EN` 是隐藏派生参数：`PG2L100H/HX=true`，`PG2L50H=false`。因此禁止直接用 `-device PG2L50H` 覆盖 100H IDF；该路径会保留错误的 `true` 并选择 PPLL `FALSE/CLKOUTF` 分支。活动 100H IDF 与 SP6.1 50H seed 的全部参数只有此 flag 不同，更新后的 `scripts/regenerate_ip.ps1` 会先验证参数一致，再由 SP6.4 build 146967 生成正确 50H staging：`DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，canonical 哈希不变。正确差异覆盖 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF；wrapper 由 21 增至 26 个端口并新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，FDC 有 28 项 pin 差异。审计证据为 `doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`；原理图/BOM 缺失时不得升格 canonical，D3-A 仍未授权。

PCIe H2-A（2026-08-30）固定产品顶层的板级边界：`pcie_dma_test` 使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；当前 FDC 仅固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。lane 极性、板级拓扑、I/O delay 和 SCBV 均没有证据，不能由实现成功推断。

PCIe H2-B0（2026-08-30）将五类 baseline 问题归一化为 16 个唯一签名、42 次原始记录，并以完整多重集保护失败状态；任何签名新增、消失、改名、share-pin 位置或次数漂移均失败，IDF metadata 漂移永久硬失败。canonical fixture 正向为 0、strict 为 1，缺失/重复 UART、Timing 端口改名、share pin 改位和 100H IDF 五个变异均为 1。H2-B1 仍受 lane/refclk/PERST#/SCBV/UART/I/O timing 外部资料阻断；partial run 复用旧 full-build 证据的风险已由 PCIe CI-8A 关闭。

PCIe CI-8A 把构建证据定义为一次运行的不可拆分集合。最新 PDS run `9952da4164f040d5924a558baa5cd8ca` 为 `complete/valid=true`，绑定 43 项输入与 9 项产物。baseline/strict=`0/1`，不表示发布通过。

PCIe S2-A 当前 PASS 只验证产品壳层受控行为 smoke；run `add7efa39f644384af9929e8a9366739` 运行至 `1476105 ns`，0 errors/0 warnings、唯一 `TEST PASS`、退出 0。受控 link 不证明真实 LTSSM、TLP、DMA 或板级链路。S2-B 使用 run-scoped 物理 vendor library、固定 `GTP_GRS GRS_INST` 以满足 `GRS_INST.GRSNET`、厂商兼容 `1ns/10ps` 和 transcript `echo`；首次 L0 后允许 RC 合法进入 `0x0d` Recovery/速率重训练，TB 在 6 ms 总窗口内寻找连续 32 周期双端 link-up/L0，任何中断将计数归零。run `30bad6e164be4a4b8284a00f1e96bd87` 编译/elaboration 成功，输出唯一 link-up marker 与唯一 `TEST PASS`，Errors 0、Warnings 26、PowerShell 退出 0。两个 run 后项目根 `modelsim.ini`、transcript、`vsim.wlf` 计数均为 0。该结果不证明 DMA、RK3568 实板、协商 x2/5.0 GT/s、电气或后级网表；S2-C 下一步执行基础 DMA 回读。`o_trgt1_radm_pkt_halt[2:0]` 已贯通项目顶层、活动 `pcie_test` wrapper 和 hard-IP，原 3'b0 tie-off 已删除并由静态 gate 锁定。

三个项目的可复现仿真工程分别保留在各自工程内独立 `sim/questa/`，运行态只进入对应 `build/`。PCIe S2-E run `927abae8ed7d40aeb5d6f706b3723e0a` 已在 `491965 ns` 以唯一 marker/PASS、Errors 0、Warnings 1、Suppressed Warnings 80、PowerShell 退出 0 通过。覆盖只限无 SDF PNR 功能网表展开、reset debounce/sync 与 reference-clock LED counter，不关闭 link、DMA、SDF timing、H2-B1、实板或 release。

PCIe S2-F 的 `.f/.do/TB` 与检查入口也已归档到项目内部。Questa 当前 run `7fc77a7ec8db479db7332e8037426d6c` 成功将 slow-corner SDF 标注到真实 DUT 层级，且没有 force/release 设计信号；HSST `ext_rstn_debounce` 自然产生 setup/hold 各 1 个 timing error，Errors 2，独立脚本汇总 5 类失败并退出 1。与此同时，Pango `V_DRM18K_E1` 产生 1590 个 `vsim-3004` 负限制求解退化，`V_FFASYN` 产生 1 个 `vsim-8756` delayed-copy 缺口，而同一 provenance 的 slow-corner STA setup/hold 均为正。因此状态是“GLS 与 STA 冲突且模型语义不完整”，既不是仿真通过，也不是已证明硅上失败。

负时序求解器诊断 run `f79dc238c12949b7b67db2ef0d0ddd0b` 在 Questa 2021.1 下比较 level1/2/3。三档均退出 0且唯一输出 SDF、功能、PASS marker，但均保留同一 setup/hold error 和 `Errors=2`；`vsim-3004=3624/1590/1590` 来自 `V_DRM18K_E1`，`vsim-8756=1/1/1` 来自 `V_FFASYN`，3316/3616 均为 0。level3 只允许作为非 canonical 诊断，不能替代 level2 验收；固定输入和模型 SHA-256 已归档，逐档运行态清理后仅日志/JSON 保留在 `build/`，S2-F 状态不变。

实物确认后，活动 `pcie_test.idf` 的 `Logos2/PG2L50H/FBG484/-6` metadata 被证明正确；错误项是顶层 build/PDS/gate 和现有主产物仍为 PG2L100H。M1 不为型号重复生成 PCIe IP，而是修正项目自有 build/gate、清空旧 build并建立 50H baseline，同时继续阻断 UART2APB、lane/refclk/PERST# 与 SCBV 缺口。

DDR3 D2 已进一步固定该边界：厂商 `test_ddr`、持续运行 BIST 与旧 testbench 保持原样；后续有限自检由项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 承担。首版仅执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并通过稳定公开的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息完成签核。

## CDC 与异步 FIFO

单比特电平、脉冲、多比特数据和 FIFO 指针需要不同跨时钟域策略。同步器降低亚稳态传播概率但不消除亚稳态；时序例外只能施加在结构已验证的 CDC 上。

OV7725 的帧同步当前是长电平而非单周期脉冲，且 `wr_load`/`rd_load` 分别被多个逻辑独立采样。整改契约要求源域用 toggle 或握手表达事件，目标 `ui_clk` 域只同步一次、生成单周期事件后统一扇出，避免多同步器重汇聚。

厂商异步 FIFO 可以承担多比特数据跨域，但 reset/flush 仍属于 RDC。write FIFO 的 camera/UI 两侧和 read FIFO 的 UI/pixel 两侧必须分别在本地时钟域释放复位；只有确认 SP6.4 对厂商指针同步结构的识别后，才允许添加最窄范围例外。

## 复位域交叉

各时钟域应明确复位来源和释放方式。外部异步条件或其他时钟域状态直接释放复位会形成 recovery/removal 风险，应采用异步置位、同步释放或等效的经验证结构。

OV7725 审计已确认 sys、I2C、camera、pixel 和 DDR UI 域的复位与 `ddr3_init_done` 存在风险；旧 O3-A/O2-C1 已取消，只作为双 OV5640 C2/C3 逐域复位设计的输入。

O1-B 将高有效 reset 接入四个 serializer 内的八个 OSERDES 后，PDS 新报告 Slow Recovery `pixel_clk → pixel_clk_5x` `-0.643 ns / TNS -4.191 ns / 8/8`。O2-A 已确认 SP6.4 对同一 `RST` 同时建立 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并将八个唯一 `opit_2/opit_2_com/OSR_IOLHR` endpoint 固定为验收集合。

O2-B 已实现上述级联结构并完成 compile/七阶段实验，但 Slow Recovery 同时出现 `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8` 和 `pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。八个反向 endpoint 均为 OSERDES `OCLKDIV` 检查；方案已否决、RTL 已回退，baseline/gate 未放宽。

旧 PG2L100H O2-D1 已否决动态 `GTP_IOCLKBUF` 门控，其 Liberty 没有 `DI` clock-gating check；O2-D1-G 曾收口出 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 与本地 reset 复制候选。owner 已取消 OV7725 M3/O2-D2，该结论只能作为双 OV5640 新项目的风险提示，不能机械继承。

M3-A 进一步确认旧 IDF 不能迁移：DDR3、PLL、FIFO 的活动版本与 SP6.4 安装版本全部断层，`IPCompiler 0037/0057` 已否决 CLI override。OV7725 canonical 现已冻结，不再新建 50H 实例；双 OV5640 需要的 DDR3/PLL/FIFO 必须在新项目独立生成并证明派生参数、资源与 RCF/FDC 对象。

O2-D1-R 已完成回退基线重建：七组失败精确复现，Slow/Fast `ddrphy_sysclk → pixel_clk` 均为 `53/53`，endpoint 分类为 read FIFO 控制 26、RAM reset 8、video driver 17、video display 1、原 DVI reset 同步器 1。O2-D1-G 已冻结 `/5` 奇数分频 waveform 和取点：必须显式且仅创建一个 `pixel_clk` generated clock，源为 PLL wrapper `u_pll_clk/clkout1`，目标为唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，波形为 `-edges {1 5 11} -edge_shift {0 0 0}`，master 为唯一 `CLKOUT1_Inferred`，旧 `CLKOUT0_Inferred` 对 pixel 域零消费者，divider 不得接 post-buffer。

O2-D1-G 的唯一控制器状态序列为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`：`HARD_HOLD` 对 `!sys_rst_n || !pll_lock` 异步保持并清 divider、pixel/business、四路本地 serializer reset 和计数；`QUALIFY` 要求 4 个 control_clk 周期；`ARM` 释放 `/5`、同步释放 pixel reset、强制 encoder `CTRLTOKEN0` 条件并等待 3 个 pixel 周期；`SER_RELEASE` 在同步 `arm_req` 后下一个 control 周期清除四个本地 reset，驻留 2 个完整 control 周期；`RUN` 才撤销 encoder 强制。计数表示已完成周期且饱和，阈值统一用 `N-1`。

旧复位契约曾固定 sys/pll hard reset、business reset、OSERDES 本地 reset、`ddr3_init_done` 与 FIFO reset/flush 的分权，并定义首个有效 TMDS symbol 与 warm-up 条件。相关实现任务已取消；这些规则只能作为双 OV5640 C2/C3 的候选审核输入。

O2-D2 已取消。其 generated-clock 唯一性、waveform/取点、OSERDES recovery/removal 覆盖和禁止 waiver 的原则转为双 OV5640 C2/C3 的审核清单；具体对象与端点必须在新项目重新定义。

旧 O2-C1/C2、O3-B、O4 已取消。普通寄存器复位、FIFO reset/flush、双路帧事件 CDC 和最终约束闭环必须由双 OV5640 C2/C3/S3 在新项目重新拆批验证。

## 时序闭环

约束例外采用“精确登记而非默认批准”模型：主 JSON 清单记录 canonical、legacy 与 not-created 三种角色，PowerShell gate 对敏感命令和双 OV5640 FDC 缺席合同做漂移检查。DDR3 6 条例外仍属于旧 PG2L100H 厂商生成输入且未经审核；PCIe 3 条为 vendor-derived/unreviewed；OV7725 的 6 条 timing exception 与 dedicated-route override 只作为冻结 legacy 证据；双 OV5640 在 H3 关闭前保持 0 条和 canonical FDC not-created。清单通过不能替代对象解析、约束理由审核、STA 或发布签核。

`All Constraints Met` 只覆盖已建模路径。验收还需检查未约束时钟、未约束关键 I/O、CDC 报告、setup/hold/recovery/removal、SDF 标注与板级接口假设。

## PDS 生成物与可重复构建

GUI 原生工程目录中的日志、数据库和绝对路径脚本是历史证据，不是可移植构建入口。目标结构应以相对路径脚本和统一 `build/` 目录隔离生成物。

OV7725 O1-B 已按该边界固定 16 个手写 RTL、4 个活动 IDF 和唯一顶层 FDC，在 SP6.4 下完成七阶段实现：进程退出 0、日志 `E: 0`、warning `4067`、critical `81`，五类产物均非零。严格 gate 返回 1；baseline 只有在七组 corner/check/clock pair/endpoints 精确匹配时返回 0，并继续标记不可发布。

## RTL 卫生与板级接口边界

OV7725 O1-A 以 `RTL_HYGIENE_AUDIT.md` 固定手写 RTL 卫生契约，O1-B 已完成其中 38 条确定性修复：显式零扩展、定宽 tie-off、地址/长度编码、`rst_n` 声明、删除 `sys_init_done` 死网及 serializer reset 连接均已落地。

serializer 接收高有效 reset；O1-B 已让该信号驱动四个 serializer 内共八个 OSERDES 的高有效 `RST`。O2-B 级联释放实验已由 STA 否决并回退，O2-D1-R 已证明当前仍精确复现旧七组失败基线；O2-D1-G 完成并经用户审核前不得启动新的 serializer RTL。

`mem_a` 是板级接口冲突而非机械消警：活动 IP 为 14 bit，顶层/FDC 为 15 bit，当前综合网表将第 15 bit 绑 0。O1-C 已随 OV7725 产品主线取消；该事实只作双 OV5640 DDR3 参数审核的反例，旧工程不再修改。

## VSCS 注释治理

后续手写 Verilog/SystemVerilog 应记录设计意图、接口契约、FSM、复位、CDC/RDC 和风险，不重复可以从代码、Git 或工具报告自动推导的事实。
