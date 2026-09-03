> generated_by: Codex manual bootstrap
> verified_at: 2026-09-03
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

2026-08-30 S0 环境复核的“未发现仿真器”结论已被后续实际执行证据取代。截至 2026-09-01，Questa Sim-64 2021.1 最小 SystemVerilog 已通过，参数化 `scripts/compile_simlib.tcl`/`.ps1` 已成功生成 Logos2 USIM/VSIM；VSIM 编译退出 0、日志无 `^E:` 且库目录非空。

2026-08-30 CI-7 入口分类确认全部 13 个 tracked Tcl 已登记。只有三个项目 `scripts/build.tcl` 通过 `run.ps1` 进入 `pds_shell`；PCIe 为 PG2L50H canonical，OV7725/DDR3 仍为 PG2L100H migration-blocked。`impl.tcl`、parse-design screen、厂商 IP PNR 和单 IP 仿真脚本中的旧器件、混合目标或绝对路径只保留为历史/内部证据，不能用于当前器件、STA、网表、SDF、位流或集成仿真签核。

2026-09-01 CI-9 同时覆盖当前树和 PR 差异：`-FullTree` 扫描 tracked/untracked 工作树，PR 模式依据 Git merge-base 扫描 changed paths 与 added lines。当前版本已将 68 个 tracked 日志中的 143 处许可证绝对路径替换为 `<license-path>`；全树和差异门禁均通过。门禁不读取实际配置，也不改写 Git 历史。

DDR3、PCIe 和摄像头 HDMI 共用 `RK3568+PG2L50H100H` 开发板与 `PG2L50H-6IFBG484`，统一 PDS 目标为 `Logos2/PG2L50H/FBG484/-6`。摄像头产品目标于 2026-09-01 校正为 OV5640；`41_ov7725_hdmi` 及其 O0/O1/O2/M3-A 只作 legacy。OV5640 按 C0 参考审计、C1 范围冻结、C2 项目边界、C3 PG2L50H 实现和 S3 四级仿真推进。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

Questa Sim-64 2021.1、Logos2 USIM/VSIM、`V_BUF` 和 PCIe S2-A 受控 smoke 均保留历史通过证据。当前版本 S2-A/S2-B 静态门禁通过，但 S2-A 动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS。DDR3 与 OV5640 仍缺项目级入口，OV7725 资产只作 legacy 参考；三个产品方向的真实网表/SDF 仿真仍待完成。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D3-0（2026-08-30）已完成只读边界评审：活动 IP 是 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`，其端口包含 `core_clk`、`ddr_init_done` 以及自定义 AXI-like AW/W/AR/R 接口；`test_ddr.v` 的物理 board wrapper 实例名必须保留为 `I_ips_ddr_top`。

D3-0 已确认旧 IP 接口不能按标准 AXI ready/valid 擅自解释：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回使用 `axi_rvalid`/`axi_rlast` 且没有 `axi_rready`。CI-6 已保护该静态事实，但 M2 必须重生成 PG2L50H IP/FDC/RCF并重跑门禁；只有端口、地址单位与 `I_ips_ddr_top` 层级重新确认并审核后才可进入 D3-A。

DDR3 M2-B1 通过 PDS SP6.4 `ui.tcl` 确认 `DEVICE_100H_EN` 是隐藏派生参数：`PG2L100H/HX=true`，`PG2L50H=false`。因此禁止直接用 `-device PG2L50H` 覆盖 100H IDF；该路径会保留错误的 `true` 并选择 PPLL `FALSE/CLKOUTF` 分支。活动 100H IDF 与 SP6.1 50H seed 的全部参数只有此 flag 不同，更新后的 `scripts/regenerate_ip.ps1` 会先验证参数一致，再由 SP6.4 build 146967 生成正确 50H staging：`DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、`0 error(s), 0 warning(s)`，canonical 哈希不变。正确差异覆盖 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF；wrapper 由 21 增至 26 个端口并新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`，FDC 有 28 项 pin 差异。审计证据为 `doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md`；原理图/BOM 缺失时不得升格 canonical，D3-A 仍未授权。

PCIe H2-A（2026-08-30）固定产品顶层的板级边界：`pcie_dma_test` 使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；当前 FDC 仅固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。lane 极性、板级拓扑、I/O delay 和 SCBV 均没有证据，不能由实现成功推断。

PCIe H2-B0（2026-08-30）将五类 baseline 问题归一化为 16 个唯一签名、42 次原始记录，并以完整多重集保护失败状态；任何签名新增、消失、改名、share-pin 位置或次数漂移均失败，IDF metadata 漂移永久硬失败。canonical fixture 正向为 0、strict 为 1，缺失/重复 UART、Timing 端口改名、share pin 改位和 100H IDF 五个变异均为 1。H2-B1 仍受 lane/refclk/PERST#/SCBV/UART/I/O timing 外部资料阻断；partial run 复用旧 full-build 证据的风险已由 PCIe CI-8A 关闭。

PCIe CI-8A（2026-08-31）把构建证据定义为一次运行的不可拆分集合：37 个 HDL 单一清单、43 项 canonical 输入和 7 项最终证据由同一 32 位 run_id 与 SHA-256 manifest 绑定。每次 build 开始即原子失效旧 complete 证据；`running/partial/failed` 均不可验收，只有 `complete/valid` 可继续 H2-B0/strict gate。partial、工具缺失、run-id、产物或 FDC 漂移均失败；最终 PG2L50H full build/baseline/strict 为 `0/0/1`，slack `0.100 ns`。CI-8B 等待 DDR3/OV7725 canonical 升格后逐项目迁移，不预先共享实现。

PCIe S2-A 的历史 PASS 只验证产品壳层受控行为 smoke；当前复验因仓库外许可证 checkout 失败而未运行。受控 link 不证明真实 LTSSM、TLP、DMA 或板级链路；S2-B 静态契约已通过，仍必须在许可证恢复后产生新的真实 RC/EP 动态证据，S2-C 才执行基础 DMA 回读。

实物确认后，活动 `pcie_test.idf` 的 `Logos2/PG2L50H/FBG484/-6` metadata 被证明正确；错误项是顶层 build/PDS/gate 和现有主产物仍为 PG2L100H。M1 不为型号重复生成 PCIe IP，而是修正项目自有 build/gate、清空旧 build并建立 50H baseline，同时继续阻断 UART2APB、lane/refclk/PERST# 与 SCBV 缺口。

DDR3 D2 已进一步固定该边界：厂商 `test_ddr`、持续运行 BIST 与旧 testbench 保持原样；后续有限自检由项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 承担。首版仅执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并通过稳定公开的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息完成签核。

## CDC 与异步 FIFO

单比特电平、脉冲、多比特数据和 FIFO 指针需要不同跨时钟域策略。同步器降低亚稳态传播概率但不消除亚稳态；时序例外只能施加在结构已验证的 CDC 上。

OV7725 的帧同步当前是长电平而非单周期脉冲，且 `wr_load`/`rd_load` 分别被多个逻辑独立采样。整改契约要求源域用 toggle 或握手表达事件，目标 `ui_clk` 域只同步一次、生成单周期事件后统一扇出，避免多同步器重汇聚。

## main OV5640 M2-A 图像处理

M2-A 将 `cam_pclk` 域的 M1-A RGB565 采集流连接到 `rgb565_grayscale`。模块先按 R[15:11]、G[10:5]、B[4:0] 扩展 8 bit，再使用 `Y=(77*R+150*G+29*B)>>8`，把 Y 复制到 RGB565 三个分量；像素、坐标、帧/行事件和协议错误统一延迟一拍。项目自有 TB 覆盖黑/红/绿/蓝四像素、两行坐标、事件保持和奇数字节错误，并以 Questa 编译 0 error/0 warning、行为返回 0、唯一 `TEST PASS` 作为当前证据。该切片不覆盖 SCCB、板级、CDC/FIFO、DDR3、PCIe 或后级实现；`parallel_driver` 仅只读参考。

## main OV5640 M3-A 128-bit 图像字

M3-A 在同一 `cam_pclk` 域承接 M2-A 灰度 RGB565 流。`rgb565_word_packer` 将像素 0..7 按接收顺序放入 `word_data` 从低到高的八个 16-bit 槽位；完整字含 8 像素且 `word_keep=16'hffff`，N 像素部分行尾字补零并只置 keep 低 `2N` 位。两个 M3-A TB 按新协议区分 payload（`word_valid && word_keep!=0`）与纯控制事件（`word_valid=1`、`word_keep=0`）。Questa Sim-64 2021.1 的 6 模块集成行为仿真为 0 error/0 warning、返回 0、唯一 `TEST PASS`。该内部布局不定义 DDR3 地址、PCIe AXIS `tkeep`、TLP payload 或主机内存字节序。

## main OV5640 M3-B 溢出帧中止与恢复

M3-B 的两槽 word skid 位于无背压 packer 与 4-byte adapter 之间。满队列且无同拍出队时，溢出前已经排队的 word 构成可保留前缀；触发 word 和当前帧余量被丢弃，前缀后恰好注入一个 `keep=0/frame_end=1/protocol_error=1` 空载中止记录，使下游可以识别并作废不完整帧。`source_overflow` 是复位周期内 sticky 的输入损失事实，不等同于无损或自动回收。

恢复需要两个先决条件同时成立：已经观察到被丢弃原帧的帧尾，且唯一中止记录已经排队。随后只接受带 `frame_start` 的新输入；在条件成立前到达的新帧整帧跳过，避免帧中段或过早新帧泄漏。Questa 2021.1 专项回归扩展为 526 ns，新增覆盖满队列同拍 pop/push、原 `frame_end` 与 abort 入队同拍、连续两个损坏帧各自产生唯一 abort 且顺序正确，以及 drop/abort 状态异步复位；联合 DVP→CDC 回归保持 2863 ns。两项均为 0 error/0 warning、日志唯一 `TEST PASS`，联合压力仍为 20 个 beat（含 1 个中止）并验证下一帧恢复 2 个 beat。该证据仍不覆盖中止记录经真实 DDR3/PCIe/主机协议保存、DDR3 无效帧回收、静态 CDC/RDC、复位释放或板级时序。

## main OV5640 M3-B 帧提交、作废与已提交帧回送

`rgb565_axis4_frame_commit` 把帧级协议结果收敛为 committed 或不可提交描述符，并保留首条记录的 opaque token、首 slot id、记录数、有效字节数与错误状态；同帧 slot id 改变会并入协议错误。该扩展先在旧 RTL 上于 47 ns 红灯，最终专项 Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、240 ns。`rgb565_axis4_frame_read_scheduler` 从首 token 起按记录数生成单 outstanding 顺序命令，并统一响应接收与完成语义：命令和零延迟响应可同拍；提前帧尾或最终响应缺失帧尾均归一化为帧尾并 fault-complete；committed 零记录也直接 fault-complete。scheduler 专项为 346 ns，readout gate 以 `read_accept_enable` 配对响应并以 `frame_done_pulse` 关闭窗口，专项为 211 ns，均 0 error/0 warning、唯一 `TEST PASS`。opaque token 只是数组索引，不是 DDR3 物理地址。

`rgb565_axis4_frame_slot_table` 管理双槽生命周期。正常槽状态只沿 `FREE→WRITING→QUEUED→READING→FREE` 前进，错误帧沿 `WRITING→FREE` 回收；写分配采用保持型 valid/ready 并携带 slot id、槽基 opaque token 与 record capacity，正常描述符进入深度 2 committed FIFO。内部 `reader_active` 限制任一时刻仅一个槽处于活动读取，`read_done` 必须匹配 active slot；错槽、重复或迟到完成只报告 fault，不释放任何槽。专项 TDD 经历目标 RTL 缺失和连续 ready 场景 126 ns 两次红灯，最终为 0 error/0 warning、唯一 `TEST PASS`、436 ns。

`rgb565_axis4_committed_pcie_mwr_path` 已实例化槽表并把带槽 committed 描述符交给 scheduler/readout gate；scheduler 完成时携 slot id 回收匹配 READING 槽。专项结果为 0 error/0 warning、唯一 `TEST PASS`、696 ns。新顶层 `ov5640_dvp_rgb565_ddr3_pcie_pipeline` 在 writer 外保证 DDR write 接受先于 frame commit；完整 `tb_ov5640_ddr3_committed_pcie_loopback` 为 4264 ns，覆盖 slot0 token `0..2`、slot1 token `64..65` 的两帧排队、slot0 复用、错误帧 1 drop/0 read/0 MWR 和 slot1 恢复。该证据仍只使用 TB 数组 token 与规范化 PCIe MWR，不生成真实 DDR3 地址，不实例化 vendor IP，也不证明 DDR3 持久化、PCIe ACK/TLP/DMA/链路、RK3568 主机接收或板级时序。

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
