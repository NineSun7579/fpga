# 三项目整改 TODO

更新日期：2026-08-30

状态：等待审核与外部环境输入。三项目 SP6.4 可重复构建基线均已建立；S0-0、DDR3 D3-0、PCIe H2-A、DDR3 D2、OV7725 O1-B 与 O2-A 已完成。O2-B 级联 serializer reset 方案已由真实 STA 否决并回退；O2-D1-G 已完成实现前契约收口，唯一待审核候选为“确定相位控制时钟 + 本地 reset 复制”。用户审核或外部资料到位前不启动新的功能 RTL/IP 修改。

## 1. 总体验收目标

三个工程最终都必须满足：

- 使用 PDS `2022.2-SP6.4` 从明确的源码、IP 和约束完成可重复构建。
- PDS 各阶段退出码为 0，且日志不存在 `^E:`；不能只信任进程退出码。
- 最终 STA 为 `All Constraints Met`、`WNS >= 0`、`TNS = 0`，setup、hold、recovery、removal 均通过。
- 行为级、综合后、PNR 后功能、PNR 后时序仿真均返回可靠退出码。
- 时序仿真成功标注 SDF，不存在实例层级匹配错误或未批准的 timing violation。
- 自检 testbench 失败使用 `$fatal`，成功只输出一次 `TEST PASS`。
- 项目使用的 PNR 网表、SDF 和位流文件存在且大小非零。
- 板级参数、管脚、电气标准、时序例外和批准的 warning 均有可追溯依据。

## 2. 执行原则

1. 每批只解决一个可独立验证的问题，并形成独立提交。
2. 不因缺少板卡资料或 QuestaSim 阻塞可重复构建、日志 gate、静态 CDC/RDC 审计等工作。
3. 不把厂商示例顶层、内部 STA 通过或非零位流描述为产品验收完成。
4. 修改手写 RTL/TB 时遵守 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`；厂商生成 IP 不批量改写。
5. 不直接修改厂商示例 TB 来伪装集成测试；新增项目级自检 TB。
6. 不用宽泛 `false_path`、虚假 I/O delay 或总开关掩盖真实 CDC、板级约束与工具告警。
7. 每批同步项目 README、`docs/IMPLEMENTATION_LOG.md` 和 `.nexus-map`，但不提交 `build/`。

## 3. 当前完成状态

- [x] 建立 Git 基线、根目录指南、`.gitignore` 和 repo-local `.nexus-map`。
- [x] 明确 VSCS 只强制覆盖后续修改的手写 RTL/TB，排除厂商生成 IP。
- [x] PCIe 建立相对路径 `build.tcl`、PowerShell 入口和严格产物检查器。
- [x] PCIe 在 SP6.4 下完成全流程重建，慢角 setup WNS `0.584 ns`、TNS `0`。
- [x] PCIe 生成非零 PNR 时序网表、SDF、`.sbit` 和 `.bin`。
- [x] PCIe 严格 gate 能拦截 6 类已知发布阻断；baseline 放行模式仅用于复现旧设计。
- [x] DDR3 明确暂用厂商 `test_ddr` 作为板级 bring-up 顶层，不声称为产品顶层。
- [x] DDR3 新脚本显式加载 18 个示例 RTL、`ddr3.idf`、PG2L100H FDC 和 RCF。
- [x] DDR3 compile-only 在 SP6.4 下成功，日志 `E:` 为 0。
- [x] DDR3 compile-only 基线完成文档同步、静态验证并提交（`848ca4c`）。
- [x] DDR3 从空 `build/` 完成到 `gen_bit_stream`，日志无 `E:`，内部 STA 为 `All Constraints Met`。
- [x] DDR3 生成非零综合网表、PNR 网表、SDF、`.sbit` 和 `.bin`。
- [x] DDR3 gate 已验证：严格模式因已知发布阻断返回非零，显式 baseline 放行模式返回 0 并标记不可发布。
- [x] DDR3 完成 D2 有限自检契约，确定项目自有 AXI 测试顶层、16 个有限写读比较 pair、稳定 done/error 和 TB 退出语义。
- [x] DDR3 完成 D3-0 core/wrapper、非标准 AXI-like 握手和 `I_ips_ddr_top` 层级只读评审；D3-A 仍待审核。
- [x] OV7725 完成 O0-A CDC/RDC 事实清单与整改契约。
- [x] OV7725 建立 O0-B SP6.4 可重复全流程构建基线和严格/baseline gate。
- [x] OV7725 完成 O1-B RTL 卫生修复：38 条确定性位宽告警消失，仅保留 `mem_a` 单项板级阻断。
- [x] OV7725 完成 O1-B 七阶段回归；严格 gate 返回非零，baseline 精确匹配 7 组失败指纹后返回 0 并标记不可发布。
- [x] OV7725 完成 O2-A serializer reset 联合释放契约，闭合快慢时钟检查、八个 OSERDES endpoint、O2-B 文件范围和回退条件。
- [x] OV7725 完成 O2-B 最小实现与七阶段实验；方案因 Slow/Fast Recovery 转移到 `pixel_clk_5x → pixel_clk` 且慢角同域仍为负而被否决，失败 RTL 已回退。
- [x] PCIe 完成 H2-A lane/refclk/PERST#/UART/SCBV/IP 目标证据矩阵；H2-B 仍待板级资料和 IP 重生成审核。
- [x] H2-B 静态准备：PCIe gate 直接解析 `pcie_test.idf` XML 元数据并强制校验 `Logos2/PG2L100H/FBG484/-6`；当前 `PG2L50H` 仍作为已知阻断，未放宽严格 gate。
- [x] H0/H1/H3 资料准备：新增 OV7725 HDMI 与 DDR3 板级证据清单，统一收集板卡、器件、时钟、电压、拓扑和 I/O 时序依据；资料未提供前不修改硬件参数。
- [x] S0-0 完成公共仿真器可执行文件复核；当前未发现 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- [x] S0-0 扩展复核 PATH、常见安装目录和 Windows 卸载注册表；仍未发现 ModelSim/QuestaSim 安装线索，保持外部阻断。
- [x] 完成三项目 S1/S2/S3 仿真就绪度只读盘点；矩阵见 [`docs/SIMULATION_READINESS_MATRIX.md`](docs/SIMULATION_READINESS_MATRIX.md)。三项目项目级 TB、`.f`、`.do` 均缺失，现有资产均为厂商 IP 示例，不能直接作为集成验收。
- [ ] 安装 QuestaSim/ModelSim 并记录版本和路径。
- [ ] 编译 Logos2 USIM/VSIM。
- [ ] 完成三项目分级自检仿真。

### 当前执行队列（2026-08-30）

按以下顺序推进；每项独立提交，未满足前置条件时保持阻塞，不以 baseline 放行代替验收：

1. **S0-1：恢复公共仿真环境（外部阻断）**
   - 前置：安装 ModelSim/QuestaSim，并提供许可证可用的 `vsim.exe`、`vlog.exe`、`vlib.exe` 路径与版本。
   - 交付：可覆盖路径参数、`build/simlib/usim` 与 `build/simlib/vsim`，以及编译日志。
   - 验收：USIM/VSIM 编译退出码为 0，库目录存在且非空；否则不进入动态仿真。

2. **H0/H1/H3：补齐板级事实（外部阻断）**
   - 前置：板卡型号、原理图/BOM、FPGA 丝印、bank 电压、DDR3 料号/拓扑、OV7725/HDMI 时序资料。
   - 交付：经审核的板级参数清单，明确 OV7725 `mem_a` 为 14/15 bit、DDR3 组织、时钟与 I/O delay。
   - 验收：清单与 IDF/FDC/RTL 一致；资料缺失时禁止猜测或收紧 gate。

3. **O2-D2：OV7725 serializer reset 单次实现（用户审核闸门）**
   - 前置：用户书面确认 O2-D1-G 契约；PLL/IP Compiler 可用；不要求先完成 QuestaSim。
   - 交付：一次性 PLL 重生成、项目自有控制器、`/5` generated-clock 和 pixel/read-FIFO 时钟原子迁移。
   - 验收：compile/elaboration 与七阶段 STA 均满足契约；八个 OSERDES endpoint 的 Slow/Fast Recovery/Removal 全部非负且覆盖完整。任一对象、warning、CDC、SDF 或 baseline 漂移触发整批回退。

4. **D3-A → D3-B → D3-C：DDR3 项目自有有限 BIST**
   - 前置：用户审核 D3-0 握手语义与顶层边界；保持 `I_ips_ddr_top` 和厂商 IP 原样。
   - 交付：BIST/top 骨架、16 个单 beat pair、watchdog/错误接口，再完成七阶段 PDS 回归。
   - 验收：先 compile/elaboration，再功能实现；不得新增物理端口、未批准告警或修改 `ip_core/ddr3/**`。

5. **H2-B：PCIe 器件与板级闭环**
   - 前置：H0/H2 板级资料、UART 保留/删除决策、PG2L100H IP 重生成审核。
   - 交付：PG2L100H 一致的 IDF、lane/refclk/PERST#/SCBV 约束和精确 gate 指纹。
   - 验收：严格 gate 无 baseline 参数返回 0；UART 隐式网络、器件元数据和板级约束阻断全部关闭。

6. **S1/S2/S3：三项目四级仿真**
   - 前置：S0-1 完成；对应项目 RTL/IP/网表/SDF 已锁定；先按 [`docs/SIMULATION_READINESS_MATRIX.md`](docs/SIMULATION_READINESS_MATRIX.md) 补齐项目级入口，禁止复用厂商示例顶层冒充集成验证。
   - 交付：相对路径 filelist/DO、自检 TB、行为/综合后/PNR 功能/PNR 时序日志；厂商示例仅保留为模型和接口参考。
   - 验收：每级只输出一次 `TEST PASS`；失败/超时 `$fatal`，退出码非零；SDF 无 annotation 或层级匹配错误。

7. **O1-C → O3-A → O2-C1 → O2-C2 → O3-B → O4：OV7725 最终闭环**
   - 前置：H3 与 O2-D2 结果；先完成 `mem_a`/IP/FDC 对齐，再处理 CDC、FIFO reset 和最窄时序例外。
   - 交付：逐域复位与事件 CDC、FIFO 复位语义、约束和最终 gate。
   - 验收：setup/hold/recovery/removal 全通过，SDF/位流/仿真齐全；不得用宽泛 `false_path`、multicycle 或 waiver 掩盖结构问题。

### 近期执行顺序

1. **P0：O2-D1-R 已完成。** 从空 `build/` 重建已回退 RTL，baseline gate 精确匹配 7 组失败；`ddrphy_sysclk → pixel_clk` 已恢复为 Slow/Fast `53/53`，O2-B 的 `54` 是实验布局产生的 video-driver endpoint 增量，不纳入 baseline。
2. **P0：O2-D1-G 架构契约收口已完成，提请用户审核。** 已固定 `+0.192 ns` 控制相位、本地 reset 复制、`/5` 奇数分频 waveform、pre/post-buffer 取点、业务复位与 serializer hard reset 分权、首个有效 TMDS symbol 条件和单次试验停止条件。
3. **P0：审核后执行一次 O2-D2。** 用 IP Compiler 重生成 PLL，原子迁移 DDR read FIFO `rd_clk` 与完整 HDMI pixel 域，完成一次 compile + 七阶段 STA。任何停止条件触发即完整回退，不扫描第二相位、不增加 waiver。
4. **P1：DDR3 D3-0 已完成。** 下一步仅在审核后进入 D3-A，新增项目自有 BIST/top 并先做 compile/elaboration。
5. **P2：PCIe H2-A 已完成。** 下一步仅在板级资料和审核后进入 H2-B，重生成 PG2L100H IP 并收紧精确 gate。
6. **O2-D2 成功后的主线：O3-A → O2-C1 → O2-C2 → O3-B → O4。** 先解除状态/复位耦合，再处理 FIFO reset、帧事件 CDC 和最终约束闭环。
7. **持续泳道：H0-H3、S0。** 板级资料或仿真器一旦到位，立即关闭对应阻断；H3 阻塞 O1-C 与最终 O4 发布闭环，S0 阻塞三项目动态仿真签核。

停止条件：缺少板级事实时不猜测管脚、电压、IP 参数或 I/O delay；任何 baseline 仅代表失败状态可重复，不得作为时序 waiver 或发布批准。

## 4. 主执行链

### D0：收口 DDR3 compile-only 基线（已完成）

范围只包含 DDR3 README、构建脚本和状态文档，不改 RTL、IP、FDC 或 RCF。

- [x] 新建 `ddr3_test/ddr3_test/scripts/build.tcl`。
- [x] 新建 `ddr3_test/ddr3_test/scripts/run.ps1`。
- [x] 新建 DDR3 README，说明 bring-up 边界和一键命令。
- [x] 验证 `-RunTo compile`：退出码 0、日志无 `^E:`、顶层为 `test_ddr`。
- [x] 验证 18 个示例 RTL、IDF、正确 FDC 和 RCF 均被加载。
- [x] 记录 compile 基线的 272 条 warning 分类：173 条无编号环路类、34 条 `Verilog-2023`、28 条 `Verilog-2006`、19 条 `Verilog-2019`、15 条 `Sdm-2000`、3 条 `Verilog-2039`。
- [x] 将 `test_ddr.v:855` 的两条 BIST 错误数据端口位宽告警列为后续明确处置项。
- [x] 同步 `docs/IMPLEMENTATION_LOG.md`、`.nexus-map` 和本 TODO。
- [x] 验证 PowerShell 语法、Markdown、JSON、`git diff --check` 和 `build/` 忽略状态。
- [x] 提交 `848ca4c build: 建立 DDR3 compile-only bring-up 基线`。

验收：从干净 `build/` 重跑 compile 得到相同输入集；严格区分“可编译基线”与“产品/板级验收”。

### D1：DDR3 完整实现与严格 gate（已完成）

依赖 D0；仍不宣称发布候选。

- [x] 为 DDR3 新增独立 `scripts/check_build.ps1`。
- [x] gate 检查 PDS `E:`、阶段完成标志、100H 器件、时序摘要和非零产物。
- [x] gate 将日志中出现的 UART、未约束关键 I/O、share pin、VCCIO/SCBV 和 BIST 位宽问题视为严格阻断。
- [x] 允许显式 baseline 模式验证历史设计可重复实现，但输出必须标记“不可发布”。
- [x] 从空 `build/` 执行 synthesize、dev_map、PNR、report_timing、gen_netlist 和 bitstream。
- [x] 记录新构建结果：慢角 setup WNS `0.678 ns`、TNS `0`，hold `0.137 ns`，recovery `4.578 ns`，removal `0.351 ns`。
- [x] 确认综合网表、PNR 网表、SDF、`.sbit`、`.bin` 均存在且非零。
- [x] 验证 baseline gate 返回 0、严格 gate 因 7 类已知阻断返回非零。
- [x] 将 `check_build.ps1` 的局部 `$Matches` 改为普通变量名，避免覆盖 PowerShell 自动变量，并重跑 AST 与 gate 双分支。
- [x] 同步 README、实现日志、`.nexus-map`，作为本批独立提交收口。

验收：完整 PDS 流程可重复执行，内部时序和产物检查有机器可判定结果；未获板级确认的问题仍被严格 gate 拦截。

### D2：定义 DDR3 有限自检契约（已完成）

该批只做设计评审，不修改 RTL/TB/IP/约束，也不要求 QuestaSim 已安装。完整契约见 `ddr3_test/ddr3_test/doc/FINITE_SELF_TEST_CONTRACT.md`。

- [x] 固定 16 个单 beat 写读比较 pair、地址 `0x0..0x78`、步长 8、确定数据函数和 131072 周期运行上限。
- [x] 选择新增项目自有 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`，不修改或复制厂商示例 BIST。
- [x] 明确初始化、写、读回、比较、完成、超时和失败的 FSM/接口契约。
- [x] 定义稳定 `test_done/test_failed/failure_code/error_count/completed_pairs` 和首错信息；禁止用 LED 作为签核接口。
- [x] 记录旧 TB 的五个失配端口、私有层级、FSDB/Verdi 和绝对路径问题，并移入 D4 处理。
- [x] 明确新 RTL/TB 的 VSCS 模块、接口、FSM、复位和机器验证要求。

验收：D3/D4 无需猜测事务、地址、数据、超时、`test_done/test_failed` 或 PASS/FAIL 语义；本批没有 RTL/TB/IP/约束修改。

### D3：实现 DDR3 项目自有限 BIST（先完成 D3-0 评审）

依赖 D2。D3-0 是只读评审，不修改 RTL/IP/约束；D3-A 以后才修改项目自有 RTL 和 PDS 输入，始终不修改厂商 `ip_core/ddr3/**` 生成文件。

- [x] D3-0：明确公开 core `ddr3` 与物理 board wrapper `test_ddr` 边界；统计状态只作为 core 公开接口，不新增 FPGA 物理 I/O。
- [x] D3-0：确认活动 DDR UI 是非标准 AXI-like 接口：写侧以 `axi_awvalid & axi_awready` 接收地址、以 `axi_wready` 计数据接受，IP 返回 `axi_wusero_id/axi_wusero_last`；读侧以 `axi_arvalid & axi_arready` 发起、仅以 `axi_rvalid/axi_rlast` 返回，没有 `axi_rready`。
- [x] D3-0：确认新物理顶层必须保持现有 DDR/时钟/复位/串口物理端口，并保留 FDC/RCF 依赖的 DDR IP 实例名 `I_ips_ddr_top`（见 `test_ddr.v`）。
- [x] D3-0：固定 D3-A 只允许新增项目自有 BIST/top、切换 PDS 顶层和输入清单并做 compile/elaboration；若重新生成 IP 后 AXI 语义、地址单位或 `I_ips_ddr_top` 层级发生变化，立即停止在评审并重新审核。
- [ ] D3-A：新增 `rtl/ddr3_bringup_top.sv` 与 `rtl/ddr3_finite_bist.sv` 接口/FSM 骨架，并按 VSCS 完成注释。
- [ ] D3-A：直接实例化活动 DDR3 IP，自动在初始化完成后启动一次有限测试。
- [ ] D3-A：原子更新 PDS 顶层、输入清单和 gate 中的产物基名，完成 compile/elaboration，禁止新增端口或位宽告警。
- [ ] D3-B：实现 16 个单 beat 写读比较 pair、watchdog、错误统计和首错信息。
- [ ] D3-C：从空 `build/` 完成七阶段回归，更新严格/baseline gate 和产物证据，不再修改功能 RTL。

验收：D3-0 后 D3-A 无需猜测 wrapper、握手或约束层级；D3-A/B/C 的公开接口满足 D2 契约，compile/PDS 无新增未分类问题，厂商示例和生成 IP 保持原样。

### D4：建立 DDR3 自检 testbench

依赖 D3；测试文件可先评审，实际运行依赖 S0。

- [ ] D4-A：新建 `tb_ddr3_finite_bist.sv`，用最小 AXI 响应模型覆盖正常、数据错误、写超时和读超时。
- [ ] D4-A：正向用例只输出一次 `TEST PASS`；数据、协议或超时失败必须 `$fatal`。
- [ ] D4-B：新建 `tb_ddr3_bringup.sv`，连接项目顶层与厂商 DDR3 memory model，不读取 DUT 私有层级。
- [ ] D4-B：新建相对路径 filelist/DO，去除强制 FSDB、Verdi PLI 和盘符绝对路径；训练或自检失败必须 `$fatal`。

验收：文件静态评审通过；QuestaSim 可用后，正向退出 0，全部负向用例按预期判定并返回可靠退出码。

### O0-A：OV7725 CDC/RDC 清单（已完成）

本批只建立事实与设计契约，不修改 RTL、IP 或 FDC。

- [x] 建立 CDC/RDC 表，覆盖 `sys_clk`、`i2c_dri_clk`、`cam_pclk`、`pixel_clk`、`pixel_clk_5x` 和 DDR `ui_clk`。
- [x] 每条跨域记录源域、目标域、信号类型、当前结构、风险、整改契约和验证方法。
- [x] 明确 `wr_load`、`rd_load`、`ddr3_init_done`、`capture_start` 和两个异步 FIFO 的跨域关系。
- [x] 将旧 STA 的 `-7.056 ns` setup、`-2.279 ns` FIFO 指针 setup 和 `-4.857 ns` recovery 路径映射到具体结构。
- [x] 明确逐域复位、单点事件同步、FIFO 分侧复位和最窄时序例外原则。
- [x] 同步项目状态、实现记录和 `.nexus-map` 后独立提交。

验收：跨域与复位决策先于 RTL/约束修改；不存在“先加宽泛 false path，后判断结构”的未决项。

### O0-B：OV7725 SP6.4 构建基线（已完成）

本批建立可重复构建入口，不修功能 RTL，也不移动厂商 IP。

- [x] 新建相对路径 `scripts/build.tcl`、PowerShell 入口和产物/日志检查器。
- [x] 显式固定 `Logos2 / PG2L100H / FBG484 / -6`、16 个手写 RTL（顶层 + 15 个子模块）、4 个 IP 和唯一 FDC。
- [x] 禁止依赖包含旧器件和失效绝对路径的 `prj/impl.tcl`，并排除 `ip_backup/**`、IP 内部 RTL/VP、模板和示例约束。
- [x] 在干净 `build/` 中完成 SP6.4 compile 基线：退出码 0、日志无 `E:`，共 1139 条 warning，其中 39 条为手写 RTL 端口位宽告警。
- [x] 在不修改 RTL/IP/FDC/RCF 的前提下完成 compile、synthesize、dev_map、PNR、report_timing、gen_netlist 和 bitstream。
- [x] 固化当前失败基线：慢角 setup WNS `-7.344 ns`、TNS `-132.832 ns`；read FIFO 指针路径 WNS `-2.275 ns`、TNS `-24.111 ns`；recovery WNS `-4.263 ns`、TNS `-202.445 ns`。
- [x] 确认综合网表、PNR 网表、SDF、`.sbit`、`.bin` 均存在且非零。
- [x] gate 硬检查器件、20 个设计输入、唯一 FDC、七阶段标志、日志 `^E:` 和产物；严格模式拦截 10 类发布阻断，baseline 模式仅放行已知六组时序失败端点并明确不可发布。

验收：所有工程输入可追溯，构建入口和失败基线可重复；严格 gate 返回非零，显式 baseline gate 返回 0 并输出 `not release-ready` 等价警告。

### O1-A：OV7725 RTL 卫生修复方案评审（已完成）

本批只读，不修改 RTL、IP 或约束。

- [x] 将 39 条手写 RTL 位宽告警逐条映射到文件、实例、端口和正确宽度来源。
- [x] 核对 `rst_n`、`sys_init_done` 等隐式 net 的驱动、扇出和预期类型。
- [x] 依据 DDR3 IDF/template 确认顶层地址、burst、`mem_a` 等接口宽度；不以告警消失代替接口正确性。
- [x] 确认 serializer 接收的是高有效 reset；四个 serializer 内共八个 OSERDES 应连接该复位。
- [x] 形成按文件拆分的最小修改清单、回归命令和回退边界，见 `41_ov7725_hdmi/doc/RTL_HYGIENE_AUDIT.md`。

验收：39 条已按 `1 + 4 + 26 + 6 + 2` 全部闭合；38 条具有确定修复，`mem_a` 单项保持板级阻断；本批没有修改 RTL、IP 或约束。

### O1-B：OV7725 RTL 卫生修复实现（已完成）

- [x] 显式声明 `rst_n`，删除无消费者的 `sys_init_done` 赋值。
- [x] 显式零扩展 I2C 地址、顶层地址和 burst，并将 25 个 DDR3 IP tie-off 改为 formal 对应的定宽常量。
- [x] 保留地址/长度左移 3 的 legacy 编码，显式使用地址低 24 bit 和长度低 8 bit，并由 gate 检查当前参数上界。
- [x] 将 serializer 端口改为高有效 `reset`，使四个 serializer 内的八个 OSERDES 都受控复位。
- [x] 更新 gate：只允许精确的 `ddr3_ip.mem_a` 单项 warning，其他手写 RTL 位宽告警全部失败。
- [x] 从空 `build/` 完成 compile 与七阶段回归：PDS 退出码 0、日志无 `E:`、五类产物非零。
- [x] 将新增 slow recovery `pixel_clk → pixel_clk_5x / 8/8` 与其余六组失败按 corner、check、clock pair 和 endpoint 数量精确固化；严格 gate 返回 1，baseline 返回 0 并明确不可发布。
- [x] 本批未修改 `mem_a`、DDR3 IP/FDC、FIFO、CDC/RDC 结构或时序例外。

验收：原 38 条确定性告警消失，只剩精确记录的 `mem_a` 1 条；完整日志无新增未分类 critical；新增 `8/8` recovery 已映射到八个 OSERDES，并明确转入 O2 修复而非时序 waiver。

### O1-C：OV7725 `mem_a`、IP 与板级约束对齐

依赖 H3，不与 O1-B 混合。

- [ ] 依据 DDR3 完整料号和原理图确认 row address 是 14 bit 还是 15 bit。
- [ ] 若为 14 bit：同时收窄两层手写 RTL，并删除 FDC 的 `mem_a[14] / V3` 约束。
- [ ] 若为 15 bit：用 SP6.4 IP Compiler 重生成 DDR3 IP，并复核控制器地址宽度、容量、FDC 和管脚映射。
- [ ] 完整重建并要求 `mem_a` warning 消失，IP、RTL 与 FDC 三方一致。

验收：不再存在悬空或固定为 0 的额外 DDR 地址脚；变更有板级一手资料和重新生成 IP 的可追溯证据。

### O2：OV7725 分时钟域复位

- [x] O2-A：建立 `doc/SERIALIZER_RESET_CONTRACT.md`，交叉核对 SP6.4 `GTP_OSERDES_E2` 仿真模型、`V_OSERDES_E2` timing model、PG2L100H 官方示例、当前 RTL 与最终 STA；本批不修改 RTL/FDC。
- [x] O2-A：确认 `RST` 高有效，且同一端口对 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 都存在 recovery/removal 要求；比较候选释放结构，禁止把“仅高速域同步”写成未经证明的结论。
- [x] O2-A：逐项映射 `serializer_b/g/r/clk × opit_2/opit_2_com` 八个 `OSR_IOLHR` endpoint，无遗漏或重复；记录 Slow Recovery `-0.643 ns / -4.191 ns / 8/8`、Slow Removal `+0.305 ns / 0/8`、Fast Recovery `+0.123 ns / 0/8`。
- [x] O2-A：固定 O2-B 的复位源、释放基准、同步级数、极性、扇出、文件范围、gate 修改、仿真补测和回退边界。
- [x] O2-B：曾仅修改 `dvi_transmitter_top.v`，保留 encoder 的 `pixel_clk` reset，并级联 `pixel_clk_5x` 两级释放生成 `serializer_reset`；compile 与七阶段 PDS 均退出 0，日志无 `E:`，五类产物非零。
- [x] O2-B：真实 STA 否决该结构。Slow Recovery 为 `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8`、`pixel_clk_5x → pixel_clk -2.173 ns / 8/8`；Fast Recovery 的反向组仍为 `-1.464 ns / 8/8`。
- [x] O2-B：八个反向 endpoint 正好是四个 serializer 的 master/slave OSERDES `OCLKDIV` 检查；失败 RTL 已回退，旧 `pixel_clk → pixel_clk_5x 8/8` baseline 保持不变，未增加 waiver、时序例外或新失败指纹。
- [x] O2-D1：依据 SP6.4 原语/timing model、官方 PG2L100H LVDS 示例、PLL 相位和 O2-B STA，拒绝普通双域同步器与单纯固定等待周期。
- [x] O2-D1：确认同源高速时钟经 `GTP_IOCLKDIV_E2 /5` 生成 pixel 时钟是当前领先拓扑；同时确认 `GTP_IOCLKBUF` 具备可选门控能力，但官方示例没有实际启用或连接该门控，不能据此宣称复位释放已闭环。
- [x] O2-D1：确认当前 `pixel_clk` 同时驱动 DDR read FIFO 读侧、video driver/display、encoder 与 serializer `OCLKDIV`；若采用 `/5` 时钟，必须原子迁移这些现有消费者，不能制造旧、新同频 pixel clock CDC。
- [x] O2-D1：否决动态 `GTP_IOCLKBUF` 门控路线。功能模型可无毛刺停启，但 SP6.4 Liberty 没有 `DI` clock-gating check，也不能证明“停钟、复位、释放、启钟”的顺序；仿真观察、endpoint 消失或 waiver 均不能替代八端点 STA。
- [x] O2-D1：唯一待验证候选为新增 `65.0026 MHz` 控制输出，目标参数 `STATIC_RATIO3=10`、`STATIC_CPHASE3=0`、`STATIC_PHASE3=1`，相位约 `+0.192 ns`；必须与每 serializer 一只本地 reset 寄存器复制原子实施，纯相位调整无效。
- [x] O2-D1：确认 generated-clock 审查是必选前置。`/5` 为奇数分频，不能默认 50% duty；必须唯一确认 IOCLKDIV 的输入取点、输出 waveform 和 PDS clock object，实际 FDC 是否增加精确声明由该审查决定。
- [x] O2-D1-R：从空 `build/` 完成七阶段重建；PDS 退出码 0、日志无 `^E:`、五类产物非零，baseline gate 精确匹配原 7 组失败并返回 0，严格 gate 按预期返回 1。
- [x] O2-D1-R：Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，Removal 均为 `0/53`。详细集合为 read FIFO 控制 26、RAM reset 8、video driver 17、video display 1、原 DVI `reset_syn` 1。
- [x] O2-D1-R：O2-B 的 `54` 由 video-driver endpoint 从 17 增为 18；新增 `serializer_reset_syn/reset_1` 属于独立的 `pixel_clk → pixel_clk_5x` clock pair。该漂移是实验结构/布局 delta，不修改旧 baseline。
- [x] O2-D1-G：冻结 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN` 唯一状态序列；固定 `QUALIFY=4`、`ENCODER_WARMUP=3`、`SERIALIZER_FILL=2`，统一采用 `counter == N-1` 的完整周期语义，并规定 counter 饱和不回卷。
- [x] O2-D1-G：冻结 `sys_rst_n/pll_lock` 异步 hard reset、pixel/business reset 与四路 serializer 本地 reset 的分权；`ddr3_init_done` 不得参与 hard-reset、资格确认、ARM、OSERDES reset 或状态转移；FIFO 本批只迁移 `rd_clk`，不改变 reset/flush 语义。
- [x] O2-D1-G：冻结 `/5` generated-clock 唯一对象：source=`u_pll_clk/clkout1`，target=唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`，pre-buffer 取点，waveform=`-edges {1 5 11} -edge_shift {0 0 0}`；对象重名、数量异常、waveform 不符或误接 post-buffer 均立即回退。
- [x] O2-D1-G：冻结 encoder warm-up 与首个有效 TMDS symbol 条件；ARM/SER_RELEASE 期间强制 `de=0,c0=0,c1=0,din=0`，serializer 释放后至少延后两个 control 周期再进入 RUN，避免未复位 encoder 流水造成不确定首符号。
- [x] O2-D1-G：冻结一次性 O2-D2 文件范围和预期 delta：PLL IDF/wrapper 由 IP Compiler 重生成；新增项目自有 TMDS clock/reset 控制器；修改顶层与 HDMI/DVI 接线、`build.tcl`，FDC/gate 仅在对象和 STA 证据满足后精确更新；完成后提请用户审核。
- [ ] O2-D2：只实现已审核候选。`ddr3_init_done` 不得进入 serializer hard-reset 控制器；旧 PLL `CLKOUT0` 对 pixel 域必须零消费者，派生 `/5` 时钟必须同时驱动 read FIFO `rd_clk` 和完整 HDMI pixel 域。
- [ ] O2-D2：从空 `build/` 先完成 compile/elaboration，确认 17 个手写源、1 个 IOCLKBUF、1 个 `/5` IOCLKDIV、4 个 serializer、8 个 OSERDES、唯一 pixel generated clock，且没有旧/新同频 pixel clock CDC。
- [ ] O2-D2：完成七阶段实现；八个 endpoint 的 Slow/Fast × Recovery/Removal × `OCLK` 双边沿/`OCLKDIV`/`SERCLK` 必须全部被覆盖且非负，只允许 O2-D1-G 预先列出的 clock 名、source count 和 reset endpoint delta。
- [ ] O2-D2：STA 成功后才更新 `check_build.ps1`，删除已关闭的 serializer 失败指纹并增加 generated clock、结构数量、八端点正向覆盖和旧 `CLKOUT0` 零消费者检查；失败则回退本批全部功能/IP/约束修改。
- [ ] O2-C1：在 O3-A 的同步状态可用后，为 sys、I2C、camera、pixel、DDR UI 等普通时钟域建立本地复位，解除 `ddr3_init_done` 对其他域异步复位释放的直接控制。
- [ ] O2-C2：单独核验两个厂商 FIFO 的 reset/flush 语义，再分别处理读写侧复位；不把 FIFO 复位与普通寄存器复位混为一个提交。

O2-D2 停止条件：控制相位或 `/5` generated clock 未被 PDS 唯一识别；本地 reset 复制后 Slow Recovery 仍为负；任一 Removal、八端点或双边沿覆盖不闭合；出现未预审 CDC/delta；需要 false path、multicycle、clock group、失败 baseline、未审核 LOC 或第二轮相位扫描。任一条件触发即回退，不继续试探。

验收：O2-D2 不使用时序 waiver 即关闭 serializer 的全部 recovery/removal；O2-C1/C2 完成后不存在跨域状态直接释放其他域复位，FIFO 两侧复位符合对应 IP 语义。

### O3：OV7725 业务 CDC 修复

- [ ] O3-A：将 `ddr3_init_done` 稳定电平分别同步到 camera 和 pixel 域，作为 capture/HDMI 的 enable/status；该批必须先于 O2-C1 删除旧复位耦合。
- [ ] O3-B：将 `video_vs/rd_load` 转为可靠的 `pixel_clk → ui_clk` 事件传输。
- [ ] O3-B：将 `cmos_frame_vsync/wr_load` 转为可靠的 `cam_pclk → ui_clk` 事件传输。
- [ ] O3-B：同一跨域事件只同步一次后在目标域扇出，避免多同步器重汇聚。
- [ ] O3-A/O3-B：覆盖复位期间不产生伪状态/伪事件，每个合法事件恰好生成一次目标域脉冲。

验收：O3-A 为 O2-C1 提供稳定替代 enable；O3-B 后旧 `pixel_clk → ui_clk` WNS `-7.056 ns` 的裸业务路径不再作为同步时序路径出现，CDC 检查只剩批准结构。

### O4：OV7725 FIFO、约束与时序闭环

- [ ] 依赖 O2-C2、O3-B；最终发布闭环还依赖 H3 的板级时钟与 I/O 事实。
- [ ] 核验 `wr_fifo`、`rd_fifo` 的时钟、指针同步和复位连接，不改厂商生成 RTL。
- [ ] 只对厂商认证的同步器/FIFO 内部路径添加最窄范围例外。
- [ ] 根据已落地结构声明异步时钟关系；禁止覆盖整个模块或时钟域的宽泛 false path。
- [ ] 确认所有约束对象匹配，无失效对象。
- [ ] 重跑 PNR，直到 setup、hold、recovery、removal 全部通过。
- [ ] 新增严格 gate，检查时序、未约束关键端口、SDF、位流和批准 waiver。

验收：最终 `All Constraints Met`、WNS 非负、TNS 为 0；旧 FIFO `ui_clk → pixel_clk` WNS `-2.279 ns` 不再被当作普通同步路径。

### CI-2：板级证据清单完整性门禁（已完成）

- [x] 三项目均存在板级证据清单，并统一包含当前工程事实、必须提供的资料和关闭条件章节。
- [x] 三项目 README 均链接对应证据清单；仓库级门禁检查项目关键词与入口可追溯性。
- [x] 门禁仅验证文档结构，不把待提供资料或模板字段判定为硬件事实。

## 5. 外部阻断泳道

这些任务需要用户或实验环境提供事实，但不阻塞前述脚本、静态审计和内部实现基线。

### H0：三项目板级资料

- [ ] 确认三个工程对应的板卡型号、原理图版本、BOM 和 FPGA 完整丝印。
- [ ] 确认是否统一为 `Logos2 / PG2L100H / FBG484 / -6`。
- [ ] 提供配置 bank 电压、启动模式和 share pin 使用条件。

验收：原理图、BOM、芯片丝印或等价的一手资料已归档；每个器件/IP/管脚/电气参数能追溯到具体版本，相关约束或 waiver 已记录审核状态。

### H1：DDR3 板级参数

- [ ] 提供 DDR3 完整料号、数量、容量、rank、x16/x32 组织和目标速率。
- [ ] 核对 A/BA/CK/DQ/DQS/DM byte-lane 映射及 bit/byte swap。
- [ ] 确认 `free_clk` 频率、电气标准、精度和 `rst_board` 极性。
- [ ] 提供 VCCIO/VREF、ODT、终端、拓扑和 PCB 走线时延依据。
- [ ] 决定 UART/ADC 是否保留；若保留，提供管脚、电压和波特率。
- [ ] 建立经审核的板级参数清单；清单不存在或与 IDF/FDC 不一致时，严格发布 gate 必须失败。

### H2：PCIe 板级参数与严格 gate

- [x] H2-A：建立 lane/refclk/PERST#/share pin/UART/SCBV/IP 目标的板级证据矩阵和 SP6.4 IP 再生成契约；不修改 RTL/IDF/FDC，详见 `pcie_dma_test_100h/doc/PCIE_BOARD_EVIDENCE.md`。
- [x] H2-A：确认当前事实：PDS 目标为 PG2L100H，但活动 `pcie_test.idf` 仍为 PG2L50H；FDC 固定 `F6/E6`、`M16`、`M15`、`M17/J16`，未提供 lane 极性、I/O delay 或 SCBV 板级证据；UART `rxd/txd` 为隐式网络且 `rxd` 被绑 0。
- [ ] H2-B：将 baseline gate 收紧为已知对象、类别和数量的精确指纹；任何新增、消失或漂移默认失败，并继续输出不可发布标记。
- [ ] 确认 PCIe x2 lane 映射/极性、100 MHz refclk、PERST# 和 M15/M16 share pin。
- [ ] 决定 UART2APB 保留或删除；保留则提供 RX/TX 管脚、电气标准和波特率。
- [ ] 提供 SCBV 所需配置 bank 电压。
- [ ] 确认 LED 属于人眼状态灯且无外部同步时序要求，或提供正式时序要求。
- [ ] 用 SP6.4 IP Compiler 为 PG2L100H 重生成 PCIe IP，消除 50H/100H IDF 不一致。
- [ ] 按决策处理 UART，消除无驱动 `rxd` 和隐式网络。
- [ ] 为 HSST/refclk/lane/share pin 建立有官方模板和原理图依据的精确约束或 waiver。
- [x] 使用 baseline 放行完成全流程重建并保留产物、STA 和阻断证据。
- [ ] 关闭前述 H2 阻断后，完整重建并使 `check_build.ps1` 不带 baseline 放行参数返回 0。

### H3：OV7725/HDMI 板级参数

- [ ] 确认 OV7725 输入格式、RGB565 字节序、分辨率、帧率和像素时钟范围。
- [ ] 确认 HDMI 输出模式及外部时序要求。
- [ ] 核对 DDR3 型号、32-bit 配置、800 MT/s 和 PCB 拓扑。
- [ ] 确认 DDR3 row address 位数及 `mem_a[14] / V3` 是否真实连接，关闭 O1-C 分支决策。
- [ ] 依据传感器和 PCB 数据补 `cam_pclk` input delay。
- [ ] 复核 `PAP_CLOCK_DEDICATED_ROUTE FALSE`、TMDS/DDR/share pin 和 I/O 电压。

## 6. 仿真器阻断泳道

### S0：公共仿真环境

- [x] S0-0（2026-08-30）：复核 PDS 与仿真器可执行文件；仅发现 `E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe`，PATH、`C:/questasim64/win64` 和常见 ModelSim/Questa 安装目录均未找到 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- [ ] 安装 ModelSim/QuestaSim，记录 `vsim.exe`、`vlog.exe` 的实际目录和版本。
- [ ] 编译 Logos2 USIM/VSIM 到仓库根 `build/simlib/`。
- [ ] 将仿真器安装路径作为可覆盖外部参数，不写入工程源清单。

### S1：DDR3 四级仿真

行为级依赖 D3、D4、S0；综合后和两个 PNR 后级别还依赖 D3-B 的新顶层网表/SDF 与严格构建证据。

- [ ] 行为级自检通过。
- [ ] 综合后自检通过。
- [ ] PNR 后功能自检通过。
- [ ] PNR 后时序自检通过且 SDF 层级正确。

共同验收：每级测试有超时 `$fatal`，失败退出非零，成功只输出一次 `TEST PASS`；时序仿真日志不存在 SDF annotation error、实例匹配错误或未批准 timing violation。

### S2：PCIe 集成仿真

行为级 smoke 依赖 S0、项目级 TB/filelist 和器件一致的 PCIe IP；不要求先关闭全部板级约束。综合后和 PNR 两级仿真还依赖 PCIe 严格构建闭环及对应网表/SDF。

- [ ] 新建 `tb_pcie_dma_test.sv`，先覆盖复位、链路建立和超时 smoke。
- [ ] 新建可移植 filelist 和行为级 DO，不改厂商示例 TB。
- [ ] 单独增加一次可预测的基础 DMA 写读回。
- [ ] 再完成综合后、PNR 功能和 PNR 时序仿真。
- [ ] 每级成功只输出一个 `TEST PASS`，失败或超时返回非零。

### S3：OV7725 集成仿真

摄像头模型、行为级 TB 和纯 RTL 数据通路自检依赖 S0 与已确认的输入格式契约，可先于全部板级约束开发。PNR 后功能/时序仿真依赖 O4、H3 和器件一致的网表/SDF。

- [ ] 建立可重复摄像头帧输入模型和 `tb_ov7725_hdmi.sv`。
- [ ] 覆盖 DDR 初始化延迟、帧写入/切换/读出、HDMI 有效区和 FIFO 边界。
- [ ] 覆盖复位中断、仿真超时和数据错误 `$fatal`。
- [ ] 完成行为级、综合后、PNR 功能和 PNR 时序仿真。

## 7. 公共 CI 与维护性

在三个项目各自 gate 稳定后再抽取共享逻辑，避免过早抽象。

- [x] 新增并运行仓库级静态一致性检查，确认三项目 README、PDS 入口、顶层声明、七阶段命令和 `build/` 忽略状态。
- [x] S0-1 准备参数化 `scripts/compile_simlib.tcl`/`scripts/compile_simlib.ps1`，支持外部覆盖仿真器路径并在调用 PDS 前检查三项可执行文件。
- [x] S0-1 收紧入口为强制仿真器预检，移除绕过检查的参数，避免产生误导性库编译结果。
- [x] CI-1 将仿真就绪度矩阵纳入仓库门禁，并检查根指南/TODO 对矩阵的引用；门禁仍只做静态检查，不替代 PDS/仿真器执行。
- [ ] 行为级仿真失败立即停止后续流程。
- [ ] 同时检查 PDS 退出码、日志 `^E:` 和阶段完成标志。
- [ ] 解析最终时序摘要，要求 `All Constraints Met`、`WNS >= 0`、`TNS = 0`。
- [ ] 未约束关键时钟/I/O 默认失败；批准项必须精确匹配并记录理由。
- [ ] SDF 日志不得包含 annotation error、实例匹配错误或未批准 timing violation。
- [ ] 检查唯一 `TEST PASS` 和非零网表/SDF/位流。
- [ ] 日志与报告作为 CI artifact 保存，不提交源码仓库。
- [ ] 每个项目 README 记录器件、临时/产品顶层、时钟、接口、命令、IP 版本和已知阻断。
- [ ] 每个时序例外记录对象、原因、IP/板级依据和审核状态。
- [ ] 仅在三个工程均验证后抽取公共 PowerShell/Tcl 小模块。

## 8. 可选增强

- [ ] DDR3 增加长时间随机地址/数据压力测试。
- [ ] PCIe DMA 增加不同长度、非对齐地址和错误恢复测试。
- [ ] OV7725 增加多分辨率、帧中断和丢帧统计测试。
- [ ] 冻结 SP6.4 作为当前可重复签核基线；另行侧装官方当前版本做兼容性实验，不得覆盖现有安装或混用生成物。
- [ ] 用相同输入、脚本和 gate 对比 SP6.4 与侧装版本的日志分类、STA、资源、网表/SDF 和位流；版本迁移必须作为独立评审批次。

## 9. 每个提交的完成定义

以下为每批提交必须重复检查的验收条款，不作为一次性待办：

- 修改范围单一，可独立说明和回退。
- 新增 RTL/TB、Tcl、DO 和 PowerShell 包含必要注释与阶段日志。
- 不新增工程内绝对路径、隐式 net 或仅打印但不失败的错误处理。
- 对应最低级别测试已通过；不能运行的测试明确记录阻断原因。
- README、实现日志、`.nexus-map` 和 TODO 状态同步。
- `git diff --check`、PowerShell 语法和 JSON 检查通过。
- 不提交 `build/`、transcript、临时库或其他工具生成物。
