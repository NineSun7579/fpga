# 三项目整改 TODO

更新日期：2026-09-01

状态：三项目器件迁移已获审核。DDR3、PCIe 和摄像头 HDMI 最终均运行在同一块 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`，PDS 目标统一为 `Logos2 / PG2L50H / FBG484 / -6`。摄像头产品目标已由 owner 校正为 OV5640；现有 `41_ov7725_hdmi` 仅保留为 OV7725 legacy 历史基线与可复用基础设施来源。既有 PG2L100H 构建、STA、网表、SDF 和位流不得用于实际板卡验收或烧录。OV5640 范围见 [`docs/OV5640_TARGET_SCOPE.md`](docs/OV5640_TARGET_SCOPE.md)。

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
2. 不因缺少板卡资料或某一项目尚未完成动态仿真而阻塞可重复构建、日志 gate、静态 CDC/RDC 审计等工作。
3. 不把厂商示例顶层、内部 STA 通过或非零位流描述为产品验收完成。
4. 修改手写 RTL/TB 时遵守 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`；厂商生成 IP 不批量改写。
5. 不直接修改厂商示例 TB 来伪装集成测试；新增项目级自检 TB。
6. 不用宽泛 `false_path`、虚假 I/O delay 或总开关掩盖真实 CDC、板级约束与工具告警。
7. 每批同步项目 README、`docs/IMPLEMENTATION_LOG.md` 和 `.nexus-map`，但不提交 `build/`。

## 3. 当前完成状态

- [x] 建立 Git 基线、根目录指南、`.gitignore` 和 repo-local `.nexus-map`。
- [x] 用户确认三项目共用实际焊接 `PG2L50H-6IFBG484` 的 `RK3568+PG2L50H100H` 开发板，并批准统一迁移方案。
- [x] owner 将摄像头产品目标校正为 OV5640；现有 OV7725 工程和完成证据保留为 legacy，不机械改名或继承为 OV5640 验收。
- [x] 完成三项目 50H 只读审计：PCIe 活动 IP 已匹配 50H；DDR3 活动 IP 和 OV7725 legacy 的四个活动 IP 仍为 100H，必须分项目处理。
- [x] 明确 VSCS 只强制覆盖后续修改的手写 RTL/TB，排除厂商生成 IP。
- [x] PCIe 建立相对路径 `build.tcl`、PowerShell 入口和严格产物检查器。
- [x] PCIe 在错误的 PG2L100H 工程目标下完成历史全流程重建，慢角 setup WNS `0.584 ns`、TNS `0`；该数值不得继承为 50H 验收结果。
- [x] PCIe 生成过非零 PNR 时序网表、SDF、`.sbit` 和 `.bin`；当前 100H 产物与实物不符，不可使用。
- [x] PCIe 严格 gate 能拦截 6 类已知发布阻断；baseline 放行模式仅用于复现旧设计。
- [x] DDR3 明确暂用厂商 `test_ddr` 作为板级 bring-up 顶层，不声称为产品顶层。
- [x] DDR3 新脚本显式加载 18 个示例 RTL、`ddr3.idf`、PG2L100H FDC 和 RCF；该输入集现仅作为历史 100H 基线。
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
- [x] OV7725 完成 M3-A 四 IP 迁移前审计：活动/安装版本断层使 CLI override 被 `IPCompiler 0037/0057` 否决，唯一后续路径为 SP6.4 GUI 在 50H 目标下新建实例并只写入 staging。
- [x] PCIe 完成 H2-A lane/refclk/PERST#/UART/SCBV/IP 目标证据矩阵；新器件事实证明活动 `pcie_test.idf` 的 PG2L50H 元数据正确，原“重生为 100H”结论作废。
- [x] 识别 PCIe 静态 gate 的错误目标：已改为 PG2L50H，并增加日志、STA、bitstream 器件交叉检查。
- [x] PCIe 完成 H2-B0 精确 baseline 指纹：16 个对象签名、42 次记录；任何对象/数量/位置或 IP metadata 漂移均失败，严格 gate 仍保持发布阻断。
- [x] H0/H1/H3 资料准备：现有 OV7725 HDMI 与 DDR3 板级证据清单保留历史事实；OV5640 另行收集模组、接口、时钟、电压、拓扑和 I/O 时序依据，资料未提供前不修改硬件参数。
- [x] S0-0 完成公共仿真器可执行文件复核；2026-08-30 的历史复核未发现 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- [x] S0-0-Q（2026-09-01）：确认 Questa Sim-64 `2021.1` 的 `vsim.exe`、`vlog.exe`、`vlib.exe` 可执行；许可证由本机外部环境提供，仓库不得记录许可证路径、服务器、feature 或许可证文件。
- [x] S0-0-Q：最小 SystemVerilog 编译、elaboration 和运行成功，退出码为 0，日志包含唯一 `TEST PASS`。
- [x] S0-1-Q：PDS `2022.2-SP6.4` 已用 Questa `2021.1` 成功编译 Logos2 USIM，包括 Pango `modelsim10.2c` 保护模型、HSST 和 PCIe Gen2 库；日志无 `E:` 且库目录非空。
- [x] 完成三项目 S1/S2/S3 仿真就绪度盘点；矩阵见 [`docs/SIMULATION_READINESS_MATRIX.md`](docs/SIMULATION_READINESS_MATRIX.md)。DDR3 与摄像头 HDMI 仍缺项目级 TB、`.f`、`.do`；PCIe 已具备 S2-A/S2-B 项目入口，厂商示例仍不能直接作为集成验收。
- [x] 验证 QuestaSim 版本、三项可执行文件和最小 SystemVerilog smoke；许可证可用性仅由本机临时环境确认，不记录或提交任何许可证配置值。
- [x] 编译并验证 Logos2 VSIM；PNR 原语 `V_BUF` 已从共享库成功加载并完成最小动态 smoke。
- [x] S0-2-Q（2026-09-01 当前复验）：仓库外许可证恢复后，Questa `2021.1` 以新 run id `966942334060436dba8444ae9155557c` 完成 S2-A；编译/elaboration/运行均成功，`Errors: 0, Warnings: 0`、唯一 `TEST PASS`、PowerShell 退出 0。仓库仍不记录许可证配置。
- [ ] 完成三项目分级自检仿真。

### 当前执行队列（2026-09-01）

按以下顺序推进；每项独立提交，未满足前置条件时保持阻塞，不以 baseline 放行代替验收：

1. **M0：统一 PG2L50H 板级事实与防错门禁**
   - 前置：用户已确认并批准实际器件与三项目共板边界。
   - 交付：TODO、README、板级证据、实施记录和 `.nexus-map` 统一记录 50H；旧 100H 产物明确标记不可烧录。
   - 验收：静态门禁禁止把 build、IDF、README、STA 或位流中的 100H/50H 混用解释为通过。

2. **M1：PCIe PG2L50H 首批迁移（构建部分完成）**
   - 前置：活动 PCIe IDF 已由 SP6.4 生成为 `PG2L50H/FBG484/-6`；不需要仅为型号重新生成 IP。
   - 交付：build/gate 改为 50H，从空 `build/` 完成 compile 和七阶段重建，重新采集 STA、网表、SDF 和位流；HSSTLP 资源迁移到 PDS SP6.4 模板指定的 `HSSTLP_292_612`。
   - 验收：日志、IDF、时序报告和 bitstream 数据库全部为 PG2L50H；strict gate 已验证仍因 UART、SCBV、lane/refclk/PERST# 板级缺口返回非零。

3. **M2：DDR3 PG2L50H IP 与约束重生成**
   - 前置：使用本机 SP6.4 IP Compiler；SP6.1 的 50H backup 只作参数和差异证据。
   - 交付：按现有 row15/col10/bank3/DQ16/DQS2 参数重生成 50H controller/PHY、示例、FDC/RCF 和 sim 资产，再完成 compile/dev_map 与七阶段重建。
   - M2-A 已建立 `scripts/regenerate_ip.ps1` staging 入口和 [`M2_IP_REGENERATION.md`](ddr3_test/ddr3_test/doc/M2_IP_REGENERATION.md)。M2-B1 已从 SP6.4 `ui.tcl` 关闭 `DEVICE_100H_EN` 语义，并形成 [`参数与差异审计`](ddr3_test/ddr3_test/doc/M2B1_PARAMETER_AND_DIFF_AUDIT.md)。
   - 当前正确 staging 为 PG2L50H、SP6.4、`DEVICE_100H_EN=false`，DDR PHY 使用 `TRUE/CLKOUT4` 分支，canonical 哈希不变；顶层新增 5 个端口，FDC 有 28 项管脚差异，尚未升格。
   - 验收：先用原理图/BOM 关闭新增 refclk、DDR byte lane、复位/UART/LED/状态输出和电压拓扑，再原子升格并重跑 CI-6、七阶段和 D3-0-R。D3-A 仍需另行审核。

4. **C0/C1：OV5640 参考工程审计与产品范围冻结**
   - 前置：将 owner 指定的 `59_top_dual_ov5640_hdmi` 参考工程只读导入 staging；当前路径尚不可访问，不能声称已审核源码。
   - 交付：源/IP/FDC/顶层/器件清单；单摄或双摄决策；模组、MCLK、RESET/PWDN、电压、DVP、格式、分辨率、帧率和字节序契约。
   - 验收：明确新的 OV5640 项目目录与顶层；旧 OV7725 的 SCCB 地址、8 位寄存器表、640x480 RGB565 和板级假设均不得默认继承。

5. **M3：OV7725 legacy 基础设施的 PG2L50H 可复用性审计**
   - 前置：先获得实际 DDR3 料号、x16/x32 组织、row 位数和管脚拓扑；当前 100H DDR 配置与仓库历史 50H DDR 工程不可互换。
   - M3-A 已完成 [`四 IP 迁移前审计`](41_ov7725_hdmi/doc/M3A_IP_MIGRATION_AUDIT.md)：活动版本为 DDR3 `1.12`、PLL `1.3`、FIFO `1.8`，SP6.4 安装版本为 `1.10/1.5/1.10`；旧 IDF override 和手改版本字段均禁止。
   - 下一批 M3-B 只允许用 SP6.4 IP Compiler GUI 在 `Logos2 / PG2L50H / FBG484 / -6` 下新建四个实例，输出到 `build/ipgen/pg2l50h/**`，先完成参数和完整资产差异审计，不原地覆盖 canonical。
   - 交付：板级参数审核后原子升格四个 IP，重建 FDC/RCF、clock object 和全流程 baseline；DDR3 `DEVICE_100H_EN=false`、PLL `DEVICE_PG2L50H=true`，FIFO 必须满足 85 个 DRM36K/170 个 DRM18K 资源上限。
   - 验收：旧 100H 七组时序指纹、endpoint 数和 `+0.192 ns` 裕量全部作废；基于新 50H STA 重新审核 O2-D2。

6. **S0-1：关闭公共 Questa 仿真环境门禁（已完成）**
   - 已完成：Questa Sim-64 `2021.1` 三项可执行文件、外部许可证 checkout、最小 SystemVerilog smoke，以及 Logos2 USIM/VSIM 编译验证。
   - 保密边界：工具安装位置和许可证配置只通过运行参数或本机环境提供；许可证路径、服务器、feature、许可证内容和许可证文件均不得提交。
   - 验证证据：USIM/VSIM 各自编译退出码为 0、日志无 `^E:`、两个库目录均存在且非空；最小 SV smoke 与从 VSIM 加载 `V_BUF` 的原语 smoke 均为唯一 `TEST PASS`。
   - 当前复验：Questa 新 run id `966942334060436dba8444ae9155557c` 已完成 S2-A，编译与运行均为 0 errors/0 warnings、唯一 `TEST PASS`、退出码 0；安装和许可证配置继续作为仓库外输入，不复用旧日志冒充新结果。
   - 剩余边界：公共环境门禁完成不等于三个项目的后级网表、SDF 标注或板级功能通过；这些仍由 S1/S2/S3 分项目关闭。

7. **H0/H1/H3：补齐其余板级事实（外部阻断）**
   - 前置：板卡型号与 FPGA 型号已确认；仍需原理图/BOM、bank 电压、DDR3 料号/拓扑、OV5640/HDMI 时序资料。
   - 交付：经审核的板级参数清单，明确 OV7725 `mem_a` 为 14/15 bit、DDR3 组织、时钟与 I/O delay。
   - 验收：清单与 IDF/FDC/RTL 一致；资料缺失时禁止猜测或收紧 gate。

8. **O2-D2：OV7725 legacy serializer reset 研究（不得直接延续到 OV5640）**
   - 前置：M3 的 50H baseline 完成，并基于 50H PLL/STA 重新确认 O2-D1-G 契约；原 100H 审核不能直接作为编码授权。
   - 交付：一次性 PLL 重生成、项目自有控制器、`/5` generated-clock 和 pixel/read-FIFO 时钟原子迁移。
   - 验收：compile/elaboration 与七阶段 STA 均满足契约；八个 OSERDES endpoint 的 Slow/Fast Recovery/Removal 全部非负且覆盖完整。任一对象、warning、CDC、SDF 或 baseline 漂移触发整批回退。

9. **D3-A → D3-B → D3-C：DDR3 项目自有有限 BIST**
   - 前置：M2 后重跑 CI-6，并重新审核 D3-0 握手语义与顶层边界；保持新生成的 `I_ips_ddr_top` 和厂商 IP 原样。
   - 交付：BIST/top 骨架、16 个单 beat pair、watchdog/错误接口，再完成七阶段 PDS 回归。
   - 验收：先 compile/elaboration，再功能实现；不得新增物理端口、未批准告警或修改 `ip_core/ddr3/**`。

10. **H2-B1：PCIe 板级闭环**
   - 前置：M1 完成，补齐 H2 板级资料和 UART 保留/删除决策。
   - H2-B0 已完成精确 baseline 指纹；它只保护失败状态不漂移，不解除任何板级阻断。
   - 交付：PG2L50H 一致的工程/IDF/产物、lane/refclk/PERST#/SCBV 约束和精确 gate 指纹。
   - 验收：严格 gate 无 baseline 参数返回 0；UART 隐式网络、器件元数据和板级约束阻断全部关闭。

11. **S1/S2/S3：三项目四级 Questa 仿真**
   - 前置：S0-1 完成；对应项目 RTL/IP/网表/SDF 已锁定；先按 [`docs/SIMULATION_READINESS_MATRIX.md`](docs/SIMULATION_READINESS_MATRIX.md) 补齐项目级入口，禁止复用厂商示例顶层冒充集成验证。
   - 交付：相对路径 filelist/DO、自检 TB、行为/综合后/PNR 功能/PNR 时序日志；厂商示例仅保留为模型和接口参考。
   - 验收：每级只输出一次 `TEST PASS`；失败/超时 `$fatal`，退出码非零；SDF 无 annotation 或层级匹配错误。

12. **C2/C3：OV5640 项目实现与最终闭环**
   - 前置：C0/C1、H3 与 PG2L50H IP/FDC 决策完成；OV7725 O1/O2/O3/O4 只作问题清单和可复用性参考。
   - 交付：新的 OV5640 SCCB/读 ID/采集路径、逐域复位与事件 CDC、FIFO reset、DDR3/HDMI 约束和最终 gate。
   - 验收：setup/hold/recovery/removal 全通过，SDF/位流/仿真齐全；不得用宽泛 `false_path`、multicycle 或 waiver 掩盖结构问题。

### 近期执行顺序

1. **P0：M0 器件事实落盘。** 统一三项目实际目标为 PG2L50H，并禁止误用所有 100H 产物。
2. **P0：M1 PCIe 先行。** 活动 PCIe IP 已是 SP6.4 50H，先修 build/gate，再从空 `build/` 建立新的 50H 七阶段基线。
3. **P1：M2 DDR3 迁移。** 以 SP6.1 50H backup 为参数/差异 oracle，用 SP6.4 正式重生成；当前 100H FDC 不得复用。
4. **P1：C0/C1 OV5640 范围。** 先导入并只读审计参考工程，再冻结单/双摄、模组接口和输出格式；不得先改名或移植 RTL。
5. **P1：M3 基础设施迁移。** 只审核 OV7725 legacy 中 DDR3/PLL/FIFO/HDMI 基础设施的可复用性；不能继承旧 `+0.192 ns` 或七组时序指纹。
6. **P2：恢复功能主线。** M2 后重审 D3-A；OV5640 仅在 C0/C1 审核完成后进入 C2/C3，不由旧 O2-D2 批准自动解锁。
7. **持续泳道：H0-H3、S0-S3。** 原理图/BOM/DDR3/PCIe/OV5640 证据或项目级 Questa 入口一旦到位，立即关闭对应阻断。

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

依赖 D2 和 M2。D3-0 是基于旧 100H 活动 IP 的只读评审；PG2L50H IP 重生成后必须先重跑 CI-6 和契约审核，D3-A 以后才修改项目自有 RTL 和 PDS 输入，始终不手改厂商 `ip_core/ddr3/**` 生成文件。

- [x] D3-0：明确公开 core `ddr3` 与物理 board wrapper `test_ddr` 边界；统计状态只作为 core 公开接口，不新增 FPGA 物理 I/O。
- [x] D3-0：确认活动 DDR UI 是非标准 AXI-like 接口：写侧以 `axi_awvalid & axi_awready` 接收地址、以 `axi_wready` 计数据接受，IP 返回 `axi_wusero_id/axi_wusero_last`；读侧以 `axi_arvalid & axi_arready` 发起、仅以 `axi_rvalid/axi_rlast` 返回，没有 `axi_rready`。
- [x] D3-0：确认新物理顶层必须保持现有 DDR/时钟/复位/串口物理端口，并保留 FDC/RCF 依赖的 DDR IP 实例名 `I_ips_ddr_top`（见 `test_ddr.v`）。
- [x] D3-0：固定 D3-A 只允许新增项目自有 BIST/top、切换 PDS 顶层和输入清单并做 compile/elaboration；若重新生成 IP 后 AXI 语义、地址单位或 `I_ips_ddr_top` 层级发生变化，立即停止在评审并重新审核。
- [x] D3-0-R：只读核对活动 `ddr3` core 的完整用户/物理端口、参数宽度、`test_ddr` wrapper 复位链和 `I_ips_ddr_top` 实例映射，形成 [`D3A_PORT_MAP.md`](ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md)。
- [x] D3-0-R：明确 D3-A 不得套用完整 AXI4 假设：写地址按 `axi_awvalid && axi_awready`，写数据按活动 `axi_wready` 语义，读返回按 `axi_rvalid/axi_rlast`，且没有 `axi_rready`。
- [ ] D3-0-M：M2 重生成 50H IP 后重跑 CI-6；确认端口、参数、`I_ips_ddr_top`、地址单位和 `axi_wready` 语义，再单独提请 D3-A 审核。
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
- [ ] O2-D1-M：完成 M3 的 PG2L50H 四 IP 重生成和新七阶段 baseline；重新计算相位裕量、七组失败指纹和 endpoint 集合，并再次提请 O2-D2 审核。
- [ ] O2-D2：只实现经 50H baseline 重新审核的候选。`ddr3_init_done` 不得进入 serializer hard-reset 控制器；旧 PLL `CLKOUT0` 对 pixel 域必须零消费者，派生 `/5` 时钟必须同时驱动 read FIFO `rd_clk` 和完整 HDMI pixel 域。
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

### CI-3：项目 README 元数据完整性门禁（已完成）

- [x] 三项目 README 均记录 PDS/器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断。
- [x] 仓库级门禁按项目特征检查上述字段，避免 README 与构建脚本、证据清单和当前状态脱节。
- [x] 门禁只检查已有事实的可追溯表达，不要求补写未经板级资料确认的参数。

### CI-4：PDS 构建 gate 契约完整性门禁（已完成）

- [x] 三项目 `run.ps1` 均显式检查 PDS 退出码、`^E:` 日志和阶段处理。
- [x] 三项目 `check_build.ps1` 均包含阶段/最终构建入口、时序摘要、失败抛错和非零产物检查，并保留显式 baseline 开关。
- [x] 门禁只验证 gate 代码路径存在，不替代真实 PDS、STA 或位流执行。

### CI-5：PowerShell AST 语法门禁（已完成）

- [x] 仓库门禁自动解析所有非 `build/` `.ps1` 文件并报告具体语法错误位置。
- [x] 当前 8 个 PowerShell 脚本 AST 解析通过。
- [x] 语法门禁只验证脚本可解析，不代表 PDS、仿真器或外部许可证可用。

### CI-6：DDR3 D3-0-R 契约一致性门禁（已完成）

- [x] 静态核对活动 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md` 的模块、参数、数据宽度、公开状态、`I_ips_ddr_top` 层级和握手字段。
- [x] 显式拒绝 core 出现 `axi_rready`，防止误套用完整 AXI4 语义。
- [x] 门禁只验证 D3-0-R 文档与源码事实一致，不代表 D3-A BIST 已实现或通过 elaboration。

### CI-7：PDS Tcl 入口分类门禁（已完成）

- [x] 枚举并分类全部 13 个 tracked Tcl；确认只有三个项目 `scripts/build.tcl` 可由 `run.ps1` 调用。
- [x] 机器清单记录角色、`set_arch` 次数、器件集合、绝对路径事实和 `run.ps1` 入口身份。
- [x] 仓库门禁通过正向检查和缺失清单项负向测试；文档、Nexus 与验证证据已同步，纳入独立 CI-7 提交。

### CI-8：PDS 构建证据新鲜度（实施中，PCIe 试点已完成）

- [x] CI-8A PCIe：每次 build 以唯一 `run_id` 原子发布 `running/partial/failed/complete` manifest，partial 或失败运行立即使旧 complete 证据失效。
- [x] CI-8A PCIe：固定 43 项 canonical 输入和 7 项最终证据的相对路径、长度与 SHA-256；日志必须含唯一且匹配的开始/完成标志，不使用时间窗口猜测。
- [x] CI-8A PCIe：真实 full build、partial、PDS 启动失败、run-id/输入/产物漂移和 baseline/strict gate 已验证，详见 `pcie_dma_test_100h/doc/CI8A_BUILD_PROVENANCE.md`。
- [ ] CI-8B DDR3：在 PG2L50H canonical IP/FDC 升格并可执行最终构建后，按项目真实源清单和产物布局实现 provenance manifest。
- [ ] CI-8B OV7725：在四个 PG2L50H IP 升格并可执行最终构建后，按项目真实源清单和产物布局实现 provenance manifest。
- [ ] 两个迁移完成并通过负向测试后，再评估是否抽公共模块；当前保持三个项目 gate 独立。

## 5. 外部阻断泳道

这些任务需要用户或实验环境提供事实，但不阻塞前述脚本、静态审计和内部实现基线。

### H0：三项目板级资料

- [x] 确认三个工程统一面向 `RK3568+PG2L50H100H` 开发板，实际 FPGA 为 `PG2L50H-6IFBG484`。
- [x] 确认 PDS 目标统一为 `Logos2 / PG2L50H / FBG484 / -6`。
- [ ] 提供原理图版本、BOM 和可归档的 FPGA 丝印照片或等价一手记录。
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
- [x] H2-A：确认新事实：实际器件和活动 `pcie_test.idf` 均为 PG2L50H，原 PDS 目标 PG2L100H 才是不一致项；FDC 固定 `F6/E6`、`M16`、`M15`、`M17/J16`，未提供 lane 极性、I/O delay 或 SCBV 板级证据；UART `rxd/txd` 为隐式网络且 `rxd` 被绑 0。
- [x] H2-B0：将 baseline gate 收紧为 16 个已知对象签名、42 次原始记录的精确多重集；任何新增、消失、重命名、位置或数量漂移默认失败，并继续输出不可发布标记。
- [x] H2-B0：活动 IDF 的 family/device/package/speedgrade 漂移改为无条件硬失败，不再由 baseline 参数放行。
- [ ] H2-B1：补齐板级资料并关闭 UART、SCBV、lane/refclk/PERST#、share pin 和 I/O timing 阻断，使严格 gate 返回 0。
- [ ] 确认 PCIe x2 lane 映射/极性、100 MHz refclk、PERST# 和 M15/M16 share pin。
- [ ] 决定 UART2APB 保留或删除；保留则提供 RX/TX 管脚、电气标准和波特率。
- [ ] 提供 SCBV 所需配置 bank 电压。
- [ ] 确认 LED 属于人眼状态灯且无外部同步时序要求，或提供正式时序要求。
- [x] 将 PCIe build/gate 恢复为 PG2L50H，保留已匹配实物的 SP6.4 PCIe IDF，并从空 `build/` 重新生成全部 50H 产物；严格 gate 仍保留发布阻断。
- [ ] 按决策处理 UART，消除无驱动 `rxd` 和隐式网络。
- [ ] 为 HSST/refclk/lane/share pin 建立有官方模板和原理图依据的精确约束或 waiver。
- [x] 使用 baseline 放行完成全流程重建并保留产物、STA 和阻断证据。
- [ ] 关闭前述 H2 阻断后，完整重建并使 `check_build.ps1` 不带 baseline 放行参数返回 0。

### H3：OV5640/HDMI 板级参数

- [ ] 确认 OV5640 模组完整料号、单摄或双摄、MCLK、RESET/PWDN、供电和 I/O 电压。
- [ ] 确认 DVP 位宽、行场/像素时钟极性、输出格式、字节序、分辨率和帧率。
- [ ] 确认 HDMI 输出模式及外部时序要求。
- [ ] 核对 DDR3 型号、32-bit 配置、800 MT/s 和 PCB 拓扑。
- [ ] 确认 DDR3 row address 位数及 `mem_a[14] / V3` 是否真实连接，关闭 O1-C 分支决策。
- [ ] 依据 OV5640 模组和 PCB 数据补摄像头时钟及 input delay。
- [ ] 复核 `PAP_CLOCK_DEDICATED_ROUTE FALSE`、TMDS/DDR/share pin 和 I/O 电压。

## 6. 仿真验证泳道

### S0：公共仿真环境

- [x] S0-0（2026-08-30）：历史环境复核未发现 ModelSim/QuestaSim 三项可执行文件；该结论已由 2026-09-01 的新环境证据取代。
- [x] S0-0-Q（2026-09-01）：确认 Questa Sim-64 `2021.1` 的 `vsim.exe`、`vlog.exe`、`vlib.exe` 可执行，最小 SystemVerilog smoke 编译、elaboration、运行和退出码均通过。
- [x] S0-1-Q：编译 Logos2 USIM 到 `build/simlib/`，Pango 保护模型、HSST 和 PCIe Gen2 库编译成功，日志无 `^E:`。
- [x] 编译 Logos2 VSIM 到 `build/simlib/`；编译日志无 `^E:`，库目录非空，`V_BUF` 原语可被 Questa 加载并完成最小 smoke。
- [x] 将仿真器安装路径作为可覆盖外部参数，不写入工程源清单。
- [x] 将许可证配置保持在仓库外部；禁止提交许可证绝对路径、服务器、feature、内容或许可证文件。
- [x] S0-2-Q：已以新 run marker `966942334060436dba8444ae9155557c` 重跑 S2-A，唯一 `TEST PASS`、`Errors: 0, Warnings: 0` 和 PowerShell 退出码 0 均满足。
- [x] S0-3-Q：三个项目均建立项目内 `sim/questa/` 归档目录。PCIe 的 S2-A/S2-B/S2-C `.f/.do/TB` 已收拢并作为唯一脚本来源；`scripts/check_sim_archives.ps1` 禁止项目自有 TB 再散落到工程外层，也禁止归档 `.mpf`、`work`、`modelsim.ini`、日志、transcript 和波形。DDR3 与摄像头目录记录厂商示例边界和待建项目级入口；许可证配置不进入 Git。
- [x] S0-4-Q：PCIe 启动器为每个 run 在 `build/sim/launcher/` 创建并显式绑定 `modelsim.ini`，通过运行时 `SIM_PROJECT_ROOT` 返回工程根执行归档 DO。S2-A run `add7efa39f644384af9929e8a9366739` 与 S2-B run `30bad6e164be4a4b8284a00f1e96bd87` 均动态通过；两次运行后工程根 `modelsim.ini`、transcript、波形计数为 0。因 `run.ps1` 是 canonical 输入，PG2L50H PDS run `dde6ee70b2c84d2da4ee2256d8a5c127` 已重建为 complete/valid、43 输入/7 证据，baseline/strict gate=`0/1`、最差 slack `0.100 ns`。

### S1：DDR3 四级仿真

行为级依赖 D3、D4、S0；综合后和两个 PNR 后级别还依赖 D3-B 的新顶层网表/SDF 与严格构建证据。

- [ ] 行为级自检通过。
- [ ] 综合后自检通过。
- [ ] PNR 后功能自检通过。
- [ ] PNR 后时序自检通过且 SDF 层级正确。

共同验收：每级测试有超时 `$fatal`，失败退出非零，成功只输出一次 `TEST PASS`；时序仿真日志不存在 SDF annotation error、实例匹配错误或未批准 timing violation。

### S2：PCIe 集成仿真

行为级 smoke 依赖 S0、项目级 TB/filelist 和器件一致的 PCIe IP；不要求先关闭全部板级约束。综合后和 PNR 两级仿真还依赖 PCIe 严格构建闭环及对应网表/SDF。

- [x] S2-A：在 `sim/questa/tb/` 归档 `tb_pcie_dma_test.sv` 和受控 `pcie_test` 边界模型，覆盖项目顶层展开、真实 reset helper、复位释放/中断、LED 域、未知态和 3 ms watchdog；model-controlled link 不作为真实链路证据。
- [x] S2-A：新建相对路径 `sim/questa/behav.f`、行为级 DO、`SIM_RUN_ID`/唯一 PASS 日志门禁和 `check_sim.ps1`；不修改厂商示例，契约见 [`S2A_BEHAVIOR_SMOKE.md`](pcie_dma_test_100h/doc/S2A_BEHAVIOR_SMOKE.md)。
- [x] S2-A 历史动态：仅在仿真专用 `sim/questa/behav.f` 中补入 `ips2l_pcie_apb_cross_v1_0.v`，保持由 IDF 管理的 canonical PDS 源清单不变；Questa `2021.1` 下 RTL 编译为 0 errors/0 warnings，elaboration 成功并运行到 `1476105 ns`，同一 run marker、唯一 `TEST PASS` 和 PowerShell 退出码 0 均通过。
- [x] S2-A 当前复验：静态 gate 通过；Questa 新 run id `966942334060436dba8444ae9155557c` 编译 `0 errors/0 warnings`，运行到 `1476105 ns`，唯一 `TEST PASS`，PowerShell 退出 0。
- [x] S2-A RTL hygiene：将 `u_ips2l_pcie_dma.o_trgt1_radm_pkt_halt` 贯通到活动 `pcie_test` wrapper 的 hard-IP RX halt 输入，关闭悬空端口和原 `3'b0` tie-off；静态 gate 锁定生成 wrapper 重生成覆盖风险。S2-A 只验证布线/壳层，真实高流量 backpressure 正确性仍依赖 S2-B/S2-C。
- [x] S2-A RTL hygiene 实现回归：PDS run id `50b37eb3628e419592cecac02ff932bf` 完成 PG2L50H 七阶段，provenance=`complete/valid`，baseline/strict gate=`0/1`，最差 slack `0.100 ns`。原两条未连接端口 warning 消失；bit2 恒 0 仍产生 2 条寄存器优化/清理 warning，不得误写为端口悬空。
- [x] S2-B 静态：以厂商 `pango_pcie_top_sim` 为 RC、项目真实 `pcie_dma_test` 为 EP，建立双库、参数化模型、双向 x2 lane、两端 link/LTSSM L0、32 周期稳定、6 ms watchdog 和唯一 PASS 合同；见 [`S2B_REAL_LINK.md`](pcie_dma_test_100h/doc/S2B_REAL_LINK.md)。
- [x] S2-B 动态：Questa `2021.1` 最新 run `30bad6e164be4a4b8284a00f1e96bd87` 完成厂商模型与项目 RTL 编译/elaboration，并在首次速率重训练后取得连续 32 周期双端 link-up/L0；`702175 ns` 输出唯一 `INFO: S2B_REAL_LINK_UP`、唯一 `TEST PASS`，`Errors: 0, Warnings: 26`，PowerShell 退出 0。该结果不证明 DMA、RK3568 实板链路、协商宽度/速率或板级电气。
- [ ] S2-C：归档入口和静态合同已建立，但当前诊断 TB 只是 RC 主动访问 EP BAR0；活动 EP 的 BAR1 被禁用，尚不能完成厂商 canonical Endpoint 主动 DMA 闭环。先审核并通过 PDS IP Compiler 原子重生成 BAR1 配置，再验证 EP MRd RC BAR0 → CplD 落 EP BAR2 → EP MWr 写回 RC BAR0 的固定 1 DW 全 32-bit 数据合同。
- [x] S2-C-BAR1：冻结 BAR1 重生成和原子升格边界，见 [`S2C_BAR1_REGENERATION.md`](pcie_dma_test_100h/doc/S2C_BAR1_REGENERATION.md)；当前仅通过阻断门禁，未修改生成 IP。
- [ ] 再完成综合后、PNR 功能和 PNR 时序仿真。
- [ ] 每级成功只输出一个 `TEST PASS`，失败或超时返回非零。

### S3：OV5640 集成仿真

摄像头模型、行为级 TB 和纯 RTL 数据通路自检依赖 S0、C0/C1 与已确认的输入格式契约。PNR 后功能/时序仿真依赖 C3、H3 和器件一致的网表/SDF；现有 OV7725 TB 计划不得直接改名复用。

- [ ] 建立可重复 OV5640 帧输入模型、读 ID/配置检查和 `tb_ov5640_hdmi.sv`。
- [ ] 覆盖 DDR 初始化延迟、帧写入/切换/读出、HDMI 有效区和 FIFO 边界。
- [ ] 覆盖复位中断、仿真超时和数据错误 `$fatal`。
- [ ] 完成行为级、综合后、PNR 功能和 PNR 时序仿真。

## 7. 公共 CI 与维护性

在三个项目各自 gate 稳定后再抽取共享逻辑，避免过早抽象。

- [x] 新增并运行仓库级静态一致性检查，确认三项目 README、PDS 入口、顶层声明、七阶段命令和 `build/` 忽略状态。
- [x] S0-1 准备参数化 `scripts/compile_simlib.tcl`/`scripts/compile_simlib.ps1`，支持外部覆盖仿真器路径并在调用 PDS 前检查三项可执行文件。
- [x] S0-1 收紧入口为强制仿真器预检，移除绕过检查的参数，避免产生误导性库编译结果。
- [x] CI-1 将仿真就绪度矩阵纳入仓库门禁，并检查根指南/TODO 对矩阵的引用；门禁仍只做静态检查，不替代 PDS/仿真器执行。
- [x] CI-9 增加[许可证敏感差异门禁](docs/SENSITIVE_DIFF_GATE.md)：拒绝新增许可证绝对路径、服务器、feature、环境变量实际值、许可证内容或许可证文件；仿真日志仅作为仓库外 CI artifact。
- [ ] 单独审计并清理已跟踪的历史工具日志中的旧许可证路径。普通删除不能清除 Git 历史；若需历史重写和强推，必须单独提案、人工审核并协调所有克隆。
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
- 不新增许可证路径、服务器、feature、环境变量实际值、许可证内容或许可证文件。
- 对应最低级别测试已通过；不能运行的测试明确记录阻断原因。
- README、实现日志、`.nexus-map` 和 TODO 状态同步。
- `git diff --check`、PowerShell 语法和 JSON 检查通过。
- 不提交 `build/`、transcript、临时库或其他工具生成物。
