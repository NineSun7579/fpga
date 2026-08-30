> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

2026-08-30 S0 环境复核确认 `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe` 存在，是当前唯一已发现工具；PATH、`C:/questasim64/win64` 与常见 ModelSim/QuestaSim 目录均没有 `vsim.exe`、`vlog.exe`、`vlib.exe`。S0-1 已准备参数化 `scripts/compile_simlib.tcl`/`.ps1` 入口，但默认运行在 PDS 前即因缺少 `vsim.exe` 返回 1；安装有许可证的仿真器并实际生成非空 USIM/VSIM 库前，动态仿真仍阻塞。

2026-08-30 用户确认 DDR3、PCIe、OV7725 HDMI 共用 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`，统一 PDS 目标为 `Logos2/PG2L50H/FBG484/-6`。M0 已完成器件事实审核；M1 先迁移 PCIe build/gate，M2 重生成 DDR3 50H IP/FDC/RCF，M3 重生成 OV7725 四个 50H IP并建立新 baseline。所有 PG2L100H 产物不得烧录。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

2026-08-30 仿真就绪度盘点确认三个项目均无项目级 TB、`.f` 或 `.do`。OV7725 现有 DDR3/PLL/FIFO TB、DDR3 工程的 `test_ddr`/memory-model TB、PCIe 的 `pango_pcie_top` RC/EP TB 都属于厂商 IP 示例，不覆盖产品集成顶层。项目验收必须新增相对路径 filelist/DO、自检 TB、唯一 `TEST PASS`、超时与 `$fatal`，并以实际 DUT 实例层级标注 SDF。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D3-0（2026-08-30）已完成只读边界评审：活动 IP 是 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`，其端口包含 `core_clk`、`ddr_init_done` 以及自定义 AXI-like AW/W/AR/R 接口；`test_ddr.v` 的物理 board wrapper 实例名必须保留为 `I_ips_ddr_top`。

D3-0 已确认旧 IP 接口不能按标准 AXI ready/valid 擅自解释：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回使用 `axi_rvalid`/`axi_rlast` 且没有 `axi_rready`。CI-6 已保护该静态事实，但 M2 必须重生成 PG2L50H IP/FDC/RCF并重跑门禁；只有端口、地址单位与 `I_ips_ddr_top` 层级重新确认并审核后才可进入 D3-A。

DDR3 M2-A 已建立 `scripts/regenerate_ip.ps1` 与 `doc/M2_IP_REGENERATION.md`：SP6.4 build 146967 在 `build/ipgen/pg2l50h` 为 `PG2L50H-6IFBG484` staging 生成成功，日志 `0 error(s), 0 warning(s)`，canonical IDF 哈希未变。比较结果显示 `ddr3.v`、`ddr3_ddrphy_top.v`、`ddr3.rcf` 不变，`test_ddr.v`、FDC、IDF 漂移；新 wrapper 保留 `free_clk` 并新增差分 `ref_clk_p/n`，FDC 使用 `DDRPHY_CPD_297_4`。`DEVICE_100H_EN=true` 是待确认的生成参数，不能据此推断目标错误，也不得手改。staging 尚未升格 canonical，D3-A 仍未授权。

PCIe H2-A（2026-08-30）固定产品顶层的板级边界：`pcie_dma_test` 使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；当前 FDC 仅固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。lane 极性、板级拓扑、I/O delay 和 SCBV 均没有证据，不能由实现成功推断。

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
