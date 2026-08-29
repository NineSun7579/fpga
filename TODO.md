# 三项目整改 TODO

更新日期：2026-08-29

状态：实施中。三项目 SP6.4 可重复构建基线均已建立；DDR3 D2 和 OV7725 O1-A 设计评审已完成。下一实现批次在 OV7725 O1-B 与 DDR3 D3 之间只选择一条，经审核后执行。

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
- [x] OV7725 完成 O0-A CDC/RDC 事实清单与整改契约。
- [x] OV7725 建立 O0-B SP6.4 可重复全流程构建基线和严格/baseline gate。
- [x] OV7725 完成 O1-B RTL 卫生修复：38 条确定性位宽告警消失，仅保留 `mem_a` 单项板级阻断。
- [x] OV7725 完成 O1-B 七阶段回归；严格 gate 返回非零，baseline 精确匹配 7 组失败指纹后返回 0 并标记不可发布。
- [ ] 安装 QuestaSim/ModelSim 并记录版本和路径。
- [ ] 编译 Logos2 USIM/VSIM。
- [ ] 完成三项目分级自检仿真。

### 近期执行顺序

1. **P0：O1-B 已完成。** 功能 RTL、完整构建、双模式 gate、状态文档和 `.nexus-map` 已作为独立批次收口。
2. **P0：执行 O2-A。** 只读确认 OSERDES 的 `pixel_clk_5x` 复位释放契约，不修改 RTL 或时序例外。
3. **P1：执行 O2-B。** 只修改 serializer 的高速时钟域复位，关闭新增 recovery `8/8`，不混入 camera/UI/FIFO 复位。
4. **P1：准备 DDR3 D3-0。** 明确公开 core/物理 board wrapper 边界和 Pango DDR 用户接口握手；任一时刻只开启一条功能 RTL 泳道。
5. **P2：PCIe H2-A/H2-B。** 在板级资料缺失时只做证据矩阵、IP 再生成契约和 baseline gate 精确化，不修改 IP/RTL/FDC。
6. **持续泳道：H0-H3、S0。** 板级资料或仿真器一旦到位，立即关闭对应阻断；H3 阻塞 O1-C/O4，S0 阻塞三项目动态仿真签核。

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

### D3：实现 DDR3 项目自有限 BIST（待审核）

依赖 D2；本批修改项目自有 RTL 和 PDS 输入，不修改厂商 `ip_core/ddr3/**` 生成文件。

- [ ] D3-0：明确公开 core 与物理 board wrapper 边界；统计状态只作为 core 公开接口，不新增 FPGA 物理 I/O。
- [ ] D3-0：确认活动 DDR UI 的 `axi_wready`、`axi_wusero_id/last` 等非标准 AXI 握手和完成语义。
- [ ] D3-0：新物理顶层保持现有物理端口，并保留 FDC/RCF 依赖的 DDR IP 实例名 `I_ips_ddr_top`。
- [ ] D3-A：新增 `rtl/ddr3_bringup_top.sv` 与 `rtl/ddr3_finite_bist.sv` 接口/FSM 骨架，并按 VSCS 完成注释。
- [ ] D3-A：直接实例化活动 DDR3 IP，自动在初始化完成后启动一次有限测试。
- [ ] D3-A：原子更新 PDS 顶层、输入清单和 gate 中的产物基名，完成 compile/elaboration，禁止新增端口或位宽告警。
- [ ] D3-B：实现 16 个单 beat 写读比较 pair、watchdog、错误统计和首错信息。
- [ ] D3-C：从空 `build/` 完成七阶段回归，更新严格/baseline gate 和产物证据，不再修改功能 RTL。

验收：公开接口满足 D2 契约；compile/PDS 无新增未分类问题；厂商示例和生成 IP 保持原样。

### D4：建立 DDR3 自检 testbench

依赖 D3；测试文件可先评审，实际运行依赖 S0。

- [ ] 新建 `tb_ddr3_finite_bist.sv`，用最小 AXI 响应模型覆盖正常、数据错误、写超时和读超时。
- [ ] 新建 `tb_ddr3_bringup.sv`，连接项目顶层与厂商 DDR3 memory model，不读取 DUT 私有层级。
- [ ] 新建相对路径 filelist/DO，去除强制 FSDB、Verdi PLI 和盘符绝对路径。
- [ ] 正向用例只输出一次 `TEST PASS`；训练、自检、数据或协议失败必须 `$fatal`。

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

- [ ] O2-A：只读确认 `GTP_OSERDES_E2.RST` 对 `OCLK=pixel_clk_5x`、`OCLKDIV=pixel_clk` 的释放契约，逐项映射八个 recovery endpoint。
- [ ] O2-A：固定 serializer 双域复位的文件范围、极性、实例数量、STA 和仿真验收，不修改 RTL/FDC。
- [ ] O2-B：保留 encoder 的 `pixel_clk` 域复位，新增 `pixel_clk_5x` 域异步置位、同步释放复位，只驱动八个 OSERDES。
- [ ] O2-B：重跑七阶段，要求新增 slow recovery `8/8` 消失或 WNS/TNS 非负，且 removal 不新增失败。
- [ ] O2-C：再为 sys、camera、pixel、DDR UI 和 FIFO 两侧建立各自异步置位、同步释放复位。
- [ ] O2-C：`ddr3_init_done` 只作为同步后的状态/使能，不再直接参与其他域异步复位释放。
- [ ] O2-C：消除复位重汇聚和组合异步释放；新增或修改的手写 RTL 按 VSCS 记录 RDC 契约和验证证据。

验收：O2-B 不使用 false path 即关闭八个 OSERDES recovery；O2-C 完成后 RTL 中不存在跨域状态直接接异步复位脚，STA recovery/removal 全部非负。

### O3：OV7725 业务 CDC 修复

- [ ] 将 `video_vs/rd_load` 转为可靠的 `pixel_clk → ui_clk` 事件传输。
- [ ] 将 `cmos_frame_vsync/wr_load` 转为可靠的 `cam_pclk → ui_clk` 事件传输。
- [ ] 将 `ddr3_init_done` 稳定电平分别同步到 camera 和 pixel 域。
- [ ] 同一跨域事件只同步一次后在目标域扇出，避免多同步器重汇聚。
- [ ] 覆盖复位期间不产生伪事件、每个合法事件恰好生成一次目标域脉冲。

验收：旧 `pixel_clk → ui_clk` WNS `-7.056 ns` 的裸业务路径不再作为同步时序路径出现；CDC 检查只剩批准结构。

### O4：OV7725 FIFO、约束与时序闭环

- [ ] 核验 `wr_fifo`、`rd_fifo` 的时钟、指针同步和复位连接，不改厂商生成 RTL。
- [ ] 只对厂商认证的同步器/FIFO 内部路径添加最窄范围例外。
- [ ] 根据已落地结构声明异步时钟关系；禁止覆盖整个模块或时钟域的宽泛 false path。
- [ ] 确认所有约束对象匹配，无失效对象。
- [ ] 重跑 PNR，直到 setup、hold、recovery、removal 全部通过。
- [ ] 新增严格 gate，检查时序、未约束关键端口、SDF、位流和批准 waiver。

验收：最终 `All Constraints Met`、WNS 非负、TNS 为 0；旧 FIFO `ui_clk → pixel_clk` WNS `-2.279 ns` 不再被当作普通同步路径。

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
- [ ] 在 SP6.4 与侧装 SP6.4-Patch2 中比较 QoR 和工具缺陷；不得覆盖现有安装。

## 9. 每个提交的完成定义

以下为每批提交必须重复检查的验收条款，不作为一次性待办：

- 修改范围单一，可独立说明和回退。
- 新增 RTL/TB、Tcl、DO 和 PowerShell 包含必要注释与阶段日志。
- 不新增工程内绝对路径、隐式 net 或仅打印但不失败的错误处理。
- 对应最低级别测试已通过；不能运行的测试明确记录阻断原因。
- README、实现日志、`.nexus-map` 和 TODO 状态同步。
- `git diff --check`、PowerShell 语法和 JSON 检查通过。
- 不提交 `build/`、transcript、临时库或其他工具生成物。
