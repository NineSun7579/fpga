# 三项目整改 TODO

更新日期：2026-09-04（板卡与 OV5640 DVP 一手资料已登记，板级缺口部分收敛）

状态：当前产品主线为 OV5640 DVP 采集→DDR3 帧缓存→PCIe DMA Memory Write→RK3568 主机内存。唯一平台为 `RK3568_MES2L100H`（FPGA + ARM），FPGA 为 `PG2L100H-6IFBG484`，PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。此前写入的 50H 器件迁移结论全部作废；`PG2L50H` 只保留在历史错误假设、旧产物和待迁移文件名上下文。产品范围见 [`docs/OV5640_TARGET_SCOPE.md`](docs/OV5640_TARGET_SCOPE.md)。

## `main` 独立 OV5640→PCIe 工程（2026-09-02）

状态：工作分支为 `codex/main-ov5640-pcie`，已从远端最新 `origin/main` 重放建立。`parallel_driver` 只读参考，不能提供本工程的 RTL、IP、FDC/RCF、PDS 产物或验收证据。

首版数据流：

```text
单路 OV5640 DVP RGB565
  → FPGA 图像处理
  → DDR3 单帧缓存
  → 128-bit PCIe DMA Memory Write
  → 主机/RK3568 内存
```

当前完成：M1-A 已实现板级无关的 DVP 8-bit→RGB565 采集；M2-A 已实现 RGB565 灰度处理；后续 M3-A/M3-B 行为证据均建立在旧 50H 假设下。现有统一 TB 只能证明项目自有行为切片，不能视为 `PG2L100H` 适配，更不能视为真实 DDR3、PCIe Endpoint、链路或 RK3568 主机闭环。活动 PCIe IDF 仍为 50H metadata，必须先完成 100H IP/约束/顶层核验。

新增资料：已登记并核对 RK3568+PG2L50H/100H 硬件使用手册 v1.1 与 OV5640 DVP 模组指南 2.13；已确认 RK↔FPGA PCIe x2/FSPI/I2C0/GPIO、主要时钟、DDR3 颗粒/容量/物理映射，以及 OV5640 DVP 参考电气和上电时序。详细页码、SHA-256 和剩余缺口见 [`docs/MAIN_OV5640_PCIE_BOARD_EVIDENCE.md`](docs/MAIN_OV5640_PCIE_BOARD_EVIDENCE.md)。外部 PDF 不复制入仓，也不作为构建依赖。

下一批：以 `PG2L100H` 为目标重新核验/生成 DDR3、PCIe IP 和约束，建立 100H 产品顶层，再完成 PCIe IP/RX/config/reset/clock 接线，并与 RK3568 驱动做单帧 golden image。开始前仍必须取得完整原理图/BOM、匹配当前 IP 版本的 DDR3 用户手册与地址单位、PCIe byte-enable/主机协议、PERST#/链路时序、RK3568 DMA 缓冲协议，以及 OV5640 实际模组接线、FPGA Bank 电压/管脚和冻结 RGB565 模式资料。

M3-B 审计结论见 [`docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`](docs/MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md)：M3-A 的 16-bit `word_keep` 不得直连 PCIe 4-bit `tkeep`；逐记录 sideband 已编码到 DDR3 第 5 byte 并可读回；事务 CDC、项目侧请求仲裁以及到完整 PCIe TX top 的行为接线已关闭。partial keep 的发送能力仍不存在，但已冻结为无 ACK fail-stop 和 sticky policy fault；DDR3 地址单位、`RLAST` 正式语义及产品顶层/链路仍待一手资料确认。

停止条件：缺少模组、时钟、I/O 电压、管脚、DDR3 拓扑或主机协议资料时，不修改 canonical IP、PLL、FDC/RCF，不把历史 PG2L50H 行为切片、旧产物或 `parallel_driver` 产物解释为本工程通过。

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
- [x] 用户确认当前平台为 `RK3568_MES2L100H`（FPGA + ARM），目标器件为 `PG2L100H-6IFBG484`。
- [x] 完成平台纠偏审计：此前 50H 迁移结论作废；现有 50H 资产统一降级为历史/待迁移证据，当前工程回到 100H 目标。
- [x] 明确 VSCS 只强制覆盖后续修改的手写 RTL/TB，排除厂商生成 IP。
- [x] PCIe 建立相对路径 `build.tcl`、PowerShell 入口和严格产物检查器。
- [x] PCIe 历史上曾在 PDS `PG2L100H` 工程目标下完成全流程重建，慢角 setup WNS `0.584 ns`、TNS `0`；由于活动 IP metadata 与当前 100H 目标不一致，该数值不得作为当前验收结果。
- [x] PCIe 生成过非零 PNR 时序网表、SDF、`.sbit` 和 `.bin`；这些历史 100H 产物未满足当前 IP metadata、约束与板级复核要求，不可直接使用。
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
- [x] PCIe 完成 H2-A lane/refclk/PERST#/UART/SCBV/IP 目标证据矩阵；当前 100H 目标下，活动 `pcie_test.idf` 的 50H 元数据被识别为迁移阻断。
- [x] 修正 PCIe 静态 gate 为 `PG2L100H`，并在 100H IP 重新生成前保持严格失败。
- [ ] 重新生成或核验匹配 `PG2L100H` 的 PCIe IP，并从空 `build/` 建立新的 100H 产物基线。
- [x] PCIe 完成 H2-B0 精确 baseline 指纹：16 个对象签名、42 次记录；任何对象/数量/位置或 IP metadata 漂移均失败，严格 gate 仍保持发布阻断。
- [x] H0/H1/H3 资料准备：DDR3、PCIe 与 OV5640 分别维护板级证据清单；资料未提供前不修改硬件参数。
- [x] 2026-09-04 登记并核对 RK3568 板卡手册 v1.1 与 OV5640 DVP 指南 2.13，固化版本、页数、SHA-256、关键页码和“外部资料非仓库依赖”边界。
- [x] S0-0 完成公共仿真器可执行文件复核；2026-08-30 的历史复核未发现 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- [x] S0-0-Q（2026-09-01）：确认 Questa Sim-64 `2021.1` 的 `vsim.exe`、`vlog.exe`、`vlib.exe` 可执行；许可证由本机外部环境提供，仓库不得记录许可证路径、服务器、feature 或许可证文件。
- [x] S0-0-Q：最小 SystemVerilog 编译、elaboration 和运行成功，退出码为 0，日志包含唯一 `TEST PASS`。
- [x] S0-1-Q：PDS `2022.2-SP6.4` 已用 Questa `2021.1` 成功编译 Logos2 USIM，包括 Pango `modelsim10.2c` 保护模型、HSST 和 PCIe Gen2 库；日志无 `E:` 且库目录非空。
- [x] 完成 DDR3、PCIe 与 OV5640→DDR3→PCIe 的 S1/S2/S3 仿真就绪度盘点；矩阵见 [`docs/SIMULATION_READINESS_MATRIX.md`](docs/SIMULATION_READINESS_MATRIX.md)。主线已有行为级回归，真实 PG2L100H IP、后级网表和 SDF 验收仍待关闭。
- [x] 验证 QuestaSim 版本、三项可执行文件和最小 SystemVerilog smoke；许可证可用性仅由本机临时环境确认，不记录或提交任何许可证配置值。
- [x] 编译并验证 Logos2 VSIM；PNR 原语 `V_BUF` 已从共享库成功加载并完成最小动态 smoke。
- [ ] S0-2-Q（2026-09-01 当前复验）：Questa `2021.1` 环境检查、S2-A/S2-B 静态门禁通过，但 S2-A 动态启动因外部许可证 checkout 失败而以退出码 4 阻断；恢复仓库外许可证后必须生成新的 `SIM_RUN_ID` 和唯一 `TEST PASS`。
- [ ] 完成三项目分级自检仿真。

### 当前执行队列（2026-09-04）

按以下顺序推进；每项独立提交，未满足前置条件时保持阻塞，不以 baseline 放行代替验收：

1. **M0：统一平台事实**
   - 唯一目标为 `RK3568_MES2L100H / PG2L100H-6IFBG484`。
   - 所有构建、IDF、约束、STA、网表和位流必须与该目标一致。

2. **M1：PCIe PG2L100H IP 与构建基线**
   - 活动 `pcie_test.idf` 仍为 50H metadata，继续作为硬阻断。
   - 使用 SP6.4 重新生成或核验 100H IP 后，从空 `build/` 建立新的七阶段基线。

3. **M2：DDR3 PG2L100H IP 与约束核验**
   - 核验或重生成 controller/PHY、FDC/RCF 和仿真资产。
   - 关闭实际颗粒、地址单位、byte lane、复位、时钟和电压拓扑差异。

4. **C0/C1：OV5640 输入与产品范围冻结**
   - 审计参考工程，冻结单/双摄、模组、MCLK、RESET/PWDN、电压、DVP 格式、分辨率、帧率和字节序。
   - 未取得一手资料时，不修改 canonical 输入。

5. **C2/C3：OV5640→DDR3→PCIe 产品实现**
   - 以 `main_ov5640_pcie/` 为唯一产品实现，接入 PG2L100H DDR3 与 PCIe Endpoint。
   - 完成 SCCB/读 ID、产品顶层、FDC/RCF、CDC/RDC、STA、位流及 RK3568 单帧 golden image。

6. **S1/S2/S3：分级仿真**
   - 在现有行为回归基础上补齐综合后、PNR 后功能和 PNR 后时序验证。
   - 每级使用相对路径入口、watchdog、`$fatal`、唯一 `TEST PASS` 和可靠退出码。

7. **H0-H3：板级事实闭环**
   - 补齐原理图/BOM、bank 电压、DDR3 用户口、PCIe PERST#/链路时序、主机协议及实际模组接线。
   - 资料缺失时禁止猜测管脚、电气参数或时序例外。

### 近期执行顺序

1. **P0：保持平台与 IDF 阻断。** 所有项目统一到 `RK3568_MES2L100H / PG2L100H-6IFBG484`，活动 PCIe 50H IDF 在替换前持续硬失败。
2. **P0：PCIe 100H IP 先行。** 核验或重生成 IP，并从空 `build/` 建立新的七阶段基线。
3. **P1：DDR3 100H 核验。** 关闭颗粒、接口、地址单位、FDC/RCF 和板级拓扑。
4. **P1：冻结 OV5640 产品输入。** 审计参考工程与模组资料，随后进入产品顶层和真实 IP 集成。
5. **P2：完成四级仿真与实板闭环。** 依次关闭网表、SDF、PCIe 链路、RK3568 DMA 缓冲和 golden image。

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

依赖 D2 和 M2。D3-0 是基于当前 100H 活动 IP 的只读评审；D3-A 以后才修改项目自有 RTL 和 PDS 输入，始终不手改厂商 `ip_core/ddr3/**` 生成文件。任何非 PG2L100H 生成资产均不得进入当前工程。

- [x] D3-0：明确公开 core `ddr3` 与物理 board wrapper `test_ddr` 边界；统计状态只作为 core 公开接口，不新增 FPGA 物理 I/O。
- [x] D3-0：确认活动 DDR UI 是非标准 AXI-like 接口：写侧以 `axi_awvalid & axi_awready` 接收地址、以 `axi_wready` 计数据接受，IP 返回 `axi_wusero_id/axi_wusero_last`；读侧以 `axi_arvalid & axi_arready` 发起、仅以 `axi_rvalid/axi_rlast` 返回，没有 `axi_rready`。
- [x] D3-0：确认新物理顶层必须保持现有 DDR/时钟/复位/串口物理端口，并保留 FDC/RCF 依赖的 DDR IP 实例名 `I_ips_ddr_top`（见 `test_ddr.v`）。
- [x] D3-0：固定 D3-A 只允许新增项目自有 BIST/top、切换 PDS 顶层和输入清单并做 compile/elaboration；若重新生成 IP 后 AXI 语义、地址单位或 `I_ips_ddr_top` 层级发生变化，立即停止在评审并重新审核。
- [x] D3-0-R：只读核对活动 `ddr3` core 的完整用户/物理端口、参数宽度、`test_ddr` wrapper 复位链和 `I_ips_ddr_top` 实例映射，形成 [`D3A_PORT_MAP.md`](ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md)。
- [x] D3-0-R：明确 D3-A 不得套用完整 AXI4 假设：写地址按 `axi_awvalid && axi_awready`，写数据按活动 `axi_wready` 语义，读返回按 `axi_rvalid/axi_rlast`，且没有 `axi_rready`。
- [ ] D3-0-M：M2 在 PG2L100H 目标下核验或重生成 IP 后重跑 CI-6；确认端口、参数、`I_ips_ddr_top`、地址单位和 `axi_wready` 语义，再单独提请 D3-A 审核。
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
- [ ] CI-8B DDR3：在 PG2L100H canonical IP/FDC 核验并可执行最终构建后，按项目真实源清单和产物布局实现 provenance manifest。
- [ ] CI-8B 产品主线：在 PG2L100H DDR3/PCIe IP 与最终构建入口升格后，按真实源清单和产物布局实现 provenance manifest。
- [ ] 两个迁移完成并通过负向测试后，再评估是否抽公共模块；当前保持三个项目 gate 独立。

## 5. 外部阻断泳道

这些任务需要用户或实验环境提供事实，但不阻塞前述脚本、静态审计和内部实现基线。

### H0：三项目板级资料

- [x] 确认三个工程统一面向 `RK3568_MES2L100H`（FPGA + ARM），目标 FPGA 为 `PG2L100H-6IFBG484`。
- [x] 确认 PDS 目标统一为 `Logos2 / PG2L100H / FBG484 / -6`。
- [x] 登记板卡硬件使用手册 v1.1，确认 RK↔FPGA 使用 PCIe、FSPI、I2C0 和部分 GPIO，并记录主要 FPGA 管脚。
- [ ] 提供原理图版本、BOM 和可归档的 FPGA 丝印照片或等价一手记录。
- [ ] 提供配置 bank 电压、启动模式和 share pin 使用条件。

验收：原理图、BOM、芯片丝印或等价的一手资料已归档；每个器件/IP/管脚/电气参数能追溯到具体版本，相关约束或 waiver 已记录审核状态。

### H1：DDR3 板级参数

- [x] 板卡手册确认一片 `F60C1A0004-M79W`、x16、512 MByte、最大 1066 Mbps；完整管脚表位于手册 PDF 第 13 页。
- [ ] 提供颗粒正式数据手册，确认 rank/bank 组织、目标工作速率和控制器参数。
- [ ] 依据手册第 13 页和网表核对 A/BA/CK/DQ/DQS/DM byte-lane 映射及 bit/byte swap，并生成可审核 RCF/FDC。
- [ ] 确认 `free_clk` 频率、电气标准、精度和 `rst_board` 极性。
- [ ] 提供 VCCIO/VREF、ODT、终端、拓扑和 PCB 走线时延依据。
- [ ] 决定 UART/ADC 是否保留；若保留，提供管脚、电压和波特率。
- [ ] 建立经审核的板级参数清单；清单不存在或与 IDF/FDC 不一致时，严格发布 gate 必须失败。

### H2：PCIe 板级参数与严格 gate

- [x] H2-A：建立 lane/refclk/PERST#/share pin/UART/SCBV/IP 目标的板级证据矩阵和 SP6.4 IP 再生成契约；不修改 RTL/IDF/FDC，详见 `pcie_dma_test_100h/doc/PCIE_BOARD_EVIDENCE.md`。
- [x] H2-A：确认当前事实：目标器件为 PG2L100H，但活动 `pcie_test.idf` 仍为旧 PG2L50H，构成器件迁移阻断；FDC 固定 `F6/E6`、`M16`、`M15`、`M17/J16`，未提供 lane 极性、I/O delay 或 SCBV 板级证据；UART `rxd/txd` 为隐式网络且 `rxd` 被绑 0。
- [x] H2-B0：将 baseline gate 收紧为 16 个已知对象签名、42 次原始记录的精确多重集；任何新增、消失、重命名、位置或数量漂移默认失败，并继续输出不可发布标记。
- [x] H2-B0：活动 IDF 的 family/device/package/speedgrade 漂移改为无条件硬失败，不再由 baseline 参数放行。
- [x] 板卡手册确认实际 PCIe x2 连接、FPGA RX0/1=`D9/C9/B10/A10`、TX0/1=`D7/C7/B6/A6`，以及 100 MHz refclk=`F6/E6`。
- [ ] H2-B1：补齐板级资料并关闭 UART、SCBV、lane/refclk/PERST#、share pin 和 I/O timing 阻断，使严格 gate 返回 0。
- [ ] 复核 lane P/N 极性与 AC 耦合，确认 PERST#/CLKREQ#/WAKE#、M15/M16 share pin 和上电/释放时序；完成实际 Gen/link 训练记录。
- [ ] 决定 UART2APB 保留或删除；保留则提供 RX/TX 管脚、电气标准和波特率。
- [ ] 提供 SCBV 所需配置 bank 电压。
- [ ] 确认 LED 属于人眼状态灯且无外部同步时序要求，或提供正式时序要求。
- [x] PCIe 项目自有 build/gate、入口清单和器件交叉检查已统一为 `PG2L100H`，并会拒绝活动 50H IDF/产物被解释为当前平台通过。
- [ ] 使用 SP6.4 重新生成或核验匹配 `PG2L100H` 的 PCIe IP/IDF，并从空 `build/` 重建 100H 产物；旧 50H 产物不得复用。
- [ ] 按决策处理 UART，消除无驱动 `rxd` 和隐式网络。
- [ ] 为 HSST/refclk/lane/share pin 建立有官方模板和原理图依据的精确约束或 waiver。
- [x] 使用 baseline 放行完成全流程重建并保留产物、STA 和阻断证据。
- [ ] 关闭前述 H2 阻断后，完整重建并使 `check_build.ps1` 不带 baseline 放行参数返回 0。

### H3：OV5640/HDMI 板级参数

- [x] 登记 OV5640 DVP 指南 2.13，确认 8-bit 输出使用 `D[9:2]`、RESETB 低有效、PWDN 高有效、SCCB 上拉、供电范围和参考上电/复位时序。
- [ ] 确认实际 OV5640 模组完整料号、单摄或双摄、排线/连接器定义、XCLK、供电和 DOVDD。
- [ ] 冻结 OV5640 接入 FPGA 的连接器、Bank、具体管脚与 IO 电压；判断 DVP/RESETB 是否需要电平转换。当前位置由 owner 明确保持暂定。
- [ ] 确认 DVP 行场/像素时钟极性、PCLK 采样边沿、RGB565 字节序、分辨率和帧率。
- [ ] 提供并实测 SCCB 7-bit 地址、芯片 ID 期望值和 RGB565 初始化表；指南中的 `0x78` 8-bit 写地址及 VGA/YUV 示例不得直接冻结。
- [ ] 确认 HDMI 输出模式及外部时序要求。
- [ ] 根据板卡手册的一片 x16 DDR3 事实，清理产品主线中的 32-bit/800 MT/s 暂定假设；正式颗粒手册、IP 参数和 PCB 拓扑审核完成前不得固化。
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
- [ ] S0-2-Q：当前 S2-A 动态复验在 Questa 启动时因许可证 checkout 失败返回 4；恢复外部许可证后重跑，并以新 run marker、唯一 `TEST PASS`、`Errors: 0` 和 PowerShell 退出码 0 关闭。

### S1：DDR3 四级仿真

行为级依赖 D3、D4、S0；综合后和两个 PNR 后级别还依赖 D3-B 的新顶层网表/SDF 与严格构建证据。

- [ ] 行为级自检通过。
- [ ] 综合后自检通过。
- [ ] PNR 后功能自检通过。
- [ ] PNR 后时序自检通过且 SDF 层级正确。

共同验收：每级测试有超时 `$fatal`，失败退出非零，成功只输出一次 `TEST PASS`；时序仿真日志不存在 SDF annotation error、实例匹配错误或未批准 timing violation。

### S2：PCIe 集成仿真

行为级 smoke 依赖 S0、项目级 TB/filelist 和器件一致的 PCIe IP；不要求先关闭全部板级约束。综合后和 PNR 两级仿真还依赖 PCIe 严格构建闭环及对应网表/SDF。

- [x] S2-A：新建 `tb_pcie_dma_test.sv` 和受控 `pcie_test` 边界模型，覆盖项目顶层展开、真实 reset helper、复位释放/中断、LED 域、未知态和 3 ms watchdog；model-controlled link 不作为真实链路证据。
- [x] S2-A：新建相对路径 `sim/behav.f`、行为级 DO、`SIM_RUN_ID`/唯一 PASS 日志门禁和 `check_sim.ps1`；不修改厂商示例，契约见 [`S2A_BEHAVIOR_SMOKE.md`](pcie_dma_test_100h/doc/S2A_BEHAVIOR_SMOKE.md)。
- [x] S2-A 历史动态：仅在仿真专用 `sim/behav.f` 中补入 `ips2l_pcie_apb_cross_v1_0.v`，保持由 IDF 管理的 canonical PDS 源清单不变；Questa `2021.1` 下 RTL 编译为 0 errors/0 warnings，elaboration 成功并运行到 `1476105 ns`，同一 run marker、唯一 `TEST PASS` 和 PowerShell 退出码 0 均通过。
- [ ] S2-A 当前复验：静态 gate 通过；动态运行等待 S0-2-Q 恢复后生成新的 run id，旧 `fab4ccef3e2445abbd9d1cad1e66b2ab` 日志不得作为本次复验结果。
- [ ] S2-A RTL hygiene：显式处理 `u_ips2l_pcie_dma` 输出 `o_trgt1_radm_pkt_halt`，关闭现存 2 条未连接端口 warning；该项不改变 S2-A 受控 smoke 已通过的结论。
- [x] S2-B 静态：以厂商 `pango_pcie_top_sim` 为 RC、项目真实 `pcie_dma_test` 为 EP，建立双库、参数化模型、双向 x2 lane、两端 link/LTSSM L0、32 周期稳定、6 ms watchdog 和唯一 PASS 合同；见 [`S2B_REAL_LINK.md`](pcie_dma_test_100h/doc/S2B_REAL_LINK.md)。
- [ ] S2-B 动态：运行 `sim-link`，同一 `SIM_RUN_ID` 日志必须包含唯一 `INFO: S2B_REAL_LINK_UP` 和 `TEST PASS`；当前未生成真实 LTSSM/link-up 动态证据。
- [ ] S2-C：S2-B 通过后增加一次地址、长度和数据固定的基础 DMA 写读回。
- [ ] 再完成综合后、PNR 功能和 PNR 时序仿真。
- [ ] 每级成功只输出一个 `TEST PASS`，失败或超时返回非零。

### S3：OV5640 集成仿真

摄像头模型、行为级 TB 和纯 RTL 数据通路自检依赖 S0、C0/C1 与已确认的输入格式契约。PNR 后功能/时序仿真依赖 C3、H3 和器件一致的网表/SDF；现有行为回归必须在真实 IP 与产品顶层锁定后升级为四级验证。

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
- [ ] OV5640 产品主线增加多分辨率、帧中断和丢帧统计测试。
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
