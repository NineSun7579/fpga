# 实施记录

## 2026-08-29：建立基线

- 创建根提交 `1a2d493`，保存三个原始 PDS 工程、现有报告、指南和整改 TODO。
- 本机 PDS：`2022.2-SP6.4 build 146967`。
- 默认位置未找到 ModelSim/QuestaSim，外部仿真暂不可执行。
- 明确以 PCIe 工程作为公共流水线基准，因为其现有内部时序已通过。
- 明确 PCIe 的 `impl.tcl` 是 GUI 操作历史，不作为重建入口。
- 明确 PCIe 有效输入为 37 个用户 RTL、`pcie_test.idf` 和 `pcie_dma_test.fdc`。
- PCIe IP 的 IDF 仍记录旧器件 PG2L50H，而顶层工程为 PG2L100H；后续需重新生成或形成有证据的偏离记录。
- PCIe UART2APB 使用未声明顶层端口的隐式 `rxd/txd`；在硬件接口决策前不猜测管脚，也不修改功能 RTL。

## 当时下一步

1. 建立 PCIe 相对路径 `build.tcl` 和 PowerShell 入口。
2. 先执行 compile-only 重建，验证输入清单与脚本语法。
3. 再执行完整 PDS 流程并从新 `build/` 目录读取时序、网表和位流证据。
4. QuestaSim 可用后再实现并放行四级集成仿真。

## 2026-08-29：PCIe 首次 compile-only 探测

- 新相对路径脚本成功加载 37 个用户 RTL、PCIe IDF 和 FDC，并完成 compile。
- 新日志再次确认两个已知阻断项：PCIe IDF 的器件仍为 PG2L50H；UART `rxd` 无驱动并被绑为 0。
- PDS 在读取 Tcl 时会预解析未执行的后续命令。本次发现 `max_parallel_jobs`、synthesis/dev_map 的 `top_module`、`verilog_2001` 和 `number_of_router_thread` 对当前器件不受支持。
- 更重要的是，上述预解析错误出现时，`pds_shell.exe` 最终仍返回 0。PowerShell 入口因此增加日志 `E:` 扫描，不能只信任进程退出码。
- 删除不支持选项并增加 `E:` 门禁后，已清理 `build/` 并重新执行 compile-only；新日志没有 `E:`，compile 在约 12 秒内完成。
- 当前仍保留并明确暴露 PG2L50H IDF 与无驱动 UART `rxd` 两项 warning。compile-only 通过不构成完整构建或功能验收。

## 2026-08-29：PCIe 完整重建

- 使用新相对路径脚本完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，总耗时约 3 分 30 秒，日志无 `E:`。
- 新最终时序报告为 `All Constraints Met`；慢角 setup 最差 WNS `0.584 ns`、TNS `0`，慢角 hold 最差 WHS `0.138 ns`。
- 新生成 `pcie_dma_test_sim.v`（约 10.6 MiB）和 `pcie_dma_test_sta.sdf`（约 8.2 MiB），关闭了“没有 PNR 网表/SDF”的构建资产缺口；尚未用 QuestaSim 验证 SDF 层级。
- 新生成 `pcie_dma_test.sbit` 和 `pcie_dma_test.bin`，均非零。
- 新发现位流关键配置缺口：PDS 报告 SCBV 未设置。必须依据 PCB 配置 bank 电压后才能把位流视为发布候选。
- 新增严格 `check_build.ps1`：检查日志 `E:`、时序、SDF/网表/位流，并把 PG2L50H IDF、UART死通道、未约束 I/O、share pin 和 SCBV 列为发布阻断项。
- 提供 `-AllowKnownBaselineIssues` 仅用于确认旧设计可重复构建；该模式不得作为发布 gate。
- 已验证 gate 的两个分支：严格模式因 6 类已知阻断项返回非零；显式允许历史问题时，时序与四类非零产物检查通过并返回 0。
- gate 首次执行暴露 PowerShell 续行符误用；修正后重新验证两个分支，未保留未经测试的实现。

## 2026-08-29：DDR3 重建边界

- 确认外层 `ddr3_test.pds` 只是 IP 壳；下一基线明确使用当前 IP 自带的 `test_ddr` 作为板级 bring-up 顶层，而非声称为产品工程。
- 干净工程输入为 18 个示例 RTL、`ddr3.idf`、PG2L100H 的 `pnr/ddr_test.fdc` 和 `pnr/ddr3.rcf`。
- 厂商 DDR Controller/PHY 源只通过 IDF 展开，禁止再递归加入 `.vp` 和生成 RTL。
- 外层旧 `ip_core/ddr_test.fdc` 保留 PG2L50H 硬宏位置，不可作为重建约束。
- 当前 TB 连接 5 个已删除端口，且 BIST 没有天然有限完成状态；本批只建立可重复实现入口，不伪造 `TEST PASS`。

## 2026-08-29：DDR3 compile-only 重建

- 新相对路径脚本成功加载 18 个示例 RTL、`ddr3.idf`、PG2L100H 的 FDC 和 RCF，并以 `test_ddr` 为顶层完成 compile。
- 为保持 D0 粒度，PowerShell 和 Tcl 的默认终点均为 `compile`；完整实现必须显式指定 `-RunTo gen_bit_stream`，尚未实现的仿真动作暂不暴露。
- PDS 退出码为 0，日志没有 `E:`；`run.ps1` PowerShell 语法检查通过。
- compile 日志共有 272 条 warning：173 条无编号环路类、34 条 `Verilog-2023`、28 条 `Verilog-2006`、19 条 `Verilog-2019`、15 条 `Sdm-2000`、3 条 `Verilog-2039`。
- 手写示例顶层的明确问题为 `test_ddr.v:855` 两条 BIST 错误数据端口位宽不匹配；其他大量告警来自厂商 IP，后续按分类建立基线和严格 gate，不直接批量修改生成源码。
- 当前结论仅为“compile-only bring-up 基线可重复”；synthesis、PNR、时序、产物 gate、板级约束和四级仿真仍未验收。

## 2026-08-29：DDR3 完整重建与严格 gate

- 从空 `build/` 执行 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，总耗时约 3 分 16 秒；PDS 退出码为 0，完整日志没有 `E:`。
- 最终时序报告为 `All Constraints Met`：慢角 setup WNS `0.678 ns`、TNS `0`，慢角 hold `0.137 ns`，recovery `4.578 ns`，removal `0.351 ns`。
- gate 对全部已解析时序摘要行得到的最差 slack 为 `0.101 ns`；该值是跨角落/检查类型的机器门禁最小值，不替代前述慢角 setup 指标。
- 实现资源约为 4820 个 LUT、5327 个 FF 和 55 个 I/O。
- 新生成 `test_ddr_syn.vm`（5,914,586 字节）、`test_ddr_sim.v`（9,734,239 字节）、`test_ddr_sta.sdf`（9,130,393 字节）、`test_ddr.sbit`（3,791,112 字节）和 `test_ddr.bin`（3,789,476 字节）。
- 完整日志包含 0 个 error、3 个 critical warning 和 2911 条 warning。严格 gate 捕获 7 类发布阻断：BIST 位宽、BIST dangling cleanup、`rst_board` share pin、BANKR4 VCCIO 不兼容、UART I/O 缺失、输入 timing 缺失和输出 timing 缺失。
- 严格 gate 实测退出码为 1；显式 `-AllowKnownBaselineIssues` 模式实测退出码为 0，并输出“不可发布”警告。两种模式都要求阶段标志、器件、STA 和五类非零产物有效。
- 本次日志没有出现 SCBV 告警，但这不能替代板级配置 bank 电压确认；经审核的板级参数清单仍是发布前置条件。
- `check_build.ps1` 的 PowerShell AST 检查为 0 个错误；局部正则结果变量不再覆盖自动变量 `$Matches`。


## 2026-08-29：DDR3 D2 有限自检契约

- 只读复核确认现有厂商 `test_main_ctrl_v1_0` 在 `E_END` 后继续随机进入写或读状态，不存在自然 `done`；`bist_stop` 也不会生成完成状态。
- `bist_run_led` 只是完成脉冲计数后的翻转灯，顶层又执行 `err_flag_led = err_flag | bist_run_led`，因此两个 LED 都不能作为 CI 或板级 PASS/FAIL 接口。
- 旧 `ddr3_test_top_tb.v` 仍连接五个已删除端口，依赖 DDR PHY 私有层级和 FSDB system task，并在初始化后固定延时 `$finish`；ModelSim 脚本/filelist 还包含 `D:/pango` 绝对路径。
- D2 决定保留 `ip_core/ddr3/**` 厂商文件不动，后续新增项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv`，直接实例化活动 DDR3 IP。
- 首版契约固定为 16 个单 beat 写读比较 pair、控制器地址 `0x0..0x78`、步长 8、确定数据函数、4096 周期 pair timeout 和 131072 周期 run timeout。
- 完成接口固定为稳定 `test_done/test_failed/error_count/completed_pairs`、失败码和首错地址/期望值/实际值；最终比较及 outstanding 清零后的下一周期才允许置位 `test_done`。
- 新 RTL/TB 必须遵守 VSCS 的模块边界、接口、FSM、复位和验证证据条款；文件不得维护作者/日期历史，注释不得替代 elaboration、assertion、仿真或 PDS 报告。


## 2026-08-30：S0 公共仿真环境复核

- 复核 PDS 与外部仿真器可执行文件：`E:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe` 存在；PATH、`C:/questasim64/win64` 及常见 ModelSim/Questa 安装目录均未找到 `vsim.exe`、`vlog.exe` 或 `vlib.exe`。
- 结论：S0 仍为外部环境阻断。未运行 `compile_simlib`、行为级仿真或门级 SDF 仿真；不得把 PDS 生成网表/SDF 误记为仿真通过。安装并记录实际版本/路径后，再编译 Logos2 USIM/VSIM。

## 2026-08-30：DDR3 D3-0 core/wrapper 只读评审

- 本批只读检查活动 `ip_core/ddr3/ddr3.v`、`ddr3_tmpl.v`、`example_design/rtl/test_ddr.v`、`axi_bist_top_v1_0.v`、`test_wr_ctrl_v1_0.v` 和 `test_rd_ctrl_v1_0.v`，未修改 RTL、IP、FDC、RCF、TB 或构建脚本。
- `ddr3` core 的公开接口包含 `core_clk`、`ddr_init_done`、128-bit AXI-like 数据通路和 Pango 扩展状态；`test_ddr` 保留物理板级端口，并以 `I_ips_ddr_top` 实例化该 core。
- 该用户接口不是完整 AXI4：写地址以 `axi_awvalid & axi_awready` 握手，写数据由 core 的 `axi_wready` 表示接受并返回 `axi_wusero_id/axi_wusero_last`；读地址以 `axi_arvalid & axi_arready` 握手，读数据仅用 `axi_rvalid/axi_rlast` 返回，接口没有 `axi_rready`。示例控制器分别以 `axi_wready` 与 `axi_rvalid` 计数完成。
- D3-A 因此只能在审核后新增项目自有 top/BIST、切换 PDS 顶层和输入清单并完成 compile/elaboration；不得修改厂商 `ip_core/ddr3/**`、物理端口、FDC/RCF 或 `I_ips_ddr_top` 名称。地址单位或握手语义若在 IP 重生成后变化，必须停止并重新审核。

## 2026-08-30：PCIe H2-A 板级证据只读评审

- 本批只读检查 `hdl/pcie_dma_test.v`、`ipcore/pcie_test/pcie_test.idf`、`fdc/pcie_dma_test.fdc`、`scripts/build.tcl` 与 `scripts/check_build.ps1`，未修改 RTL、IDF、FDC、RCF、gate 或生成物。
- 当前 PDS 目标为 `Logos2/PG2L100H/FBG484/-6`，活动 PCIe IDF metadata 仍为 `PG2L50H/FBG484/-6`；该器件不一致必须通过 SP6.4 IP Compiler 重生成或经审核的偏离记录解决。
- 顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n` 和两枚 LED。FDC 固定 `ref_clk_p/n=F6/E6`、`perst_n=M16`、`button_rst_n=M15`、LED=`M17/J16`，但未提供 lane 极性/PCB 拓扑、I/O delay 或 SCBV 板级证据。
- UART2APB 仍连接隐式 `rxd/txd`，顶层没有端口且 `rxd` 被工具绑为 0；必须先决定保留/删除并补齐板级参数，不能用内部 STA 通过替代硬件接口签核。
- H2-A 已冻结为只读证据矩阵和 IP 再生成契约；H2-B 依赖板级资料闭合后再收紧精确 baseline，任一 lane/refclk/PERST#/UART/SCBV/IP 目标不确定即停止。

## 2026-08-30：三项目 TODO 状态索引校正

- 本次只修正状态索引，没有改变任何实现结论、gate 规则或功能文件边界。

## 2026-08-30：仓库级静态一致性门禁

- 新增 `scripts/check_repo_consistency.ps1`，只检查仓库结构与文档一致性，不启动 PDS 或 ModelSim/QuestaSim。
- 门禁覆盖根指南/TODO/VSCS、三个项目的 README、`build.tcl`、`run.ps1`、`check_build.ps1`、顶层模块、七阶段入口、显式 baseline 开关和非空产物检查接口。
- 门禁确认 `.gitignore` 会忽略各层 `build/`，且当前没有被 Git 跟踪的生成目录；同时拒绝活动 Tcl 中的 `simulate` 命令和反斜杠绝对路径。
- 首次运行发现并修正 README 的事实缺口：统一记录 PDS `2022.2-SP6.4`、顶层模块和 DDR3 仿真阻断状态。
- 静态门禁最终输出 `INFO: repository consistency gate passed`；七个 PowerShell 脚本 AST 解析错误数为 0。
- 本批未运行 PDS/QuestaSim，未修改 RTL、IP、PLL、FDC、RCF 或 `build/`。

## 2026-08-30：S0-1 仿真库入口准备

- 新增参数化 `scripts/compile_simlib.tcl` 和 `scripts/compile_simlib.ps1`；仿真器路径、库类型、器件系列和语言均可通过 PowerShell 参数覆盖，不写入工程源清单。
- PowerShell 入口先检查 PDS shell 以及 `vsim.exe`、`vlog.exe`、`vlib.exe`，再调用 PDS `compile_simlib`；任一可执行文件缺失即返回非零并停止。
- Tcl 入口通过环境变量传递参数，输出目录固定默认为 `build/simlib`，工作目录和日志分别位于 `build/pds-simlib` 与 `build/logs/compile-simlib.log`。
- 仓库级静态一致性门禁已纳入两个入口及关键参数检查，防止仿真库脚本脱离 CI 覆盖。
- 本机默认预检实测返回 1，具体阻断为 `C:\questasim64\win64\vsim.exe` 不存在；未调用 PDS，也未声称 USIM/VSIM 编译成功。
- 普通 `tclsh` 执行该脚本会因缺少 PDS 专有 `compile_simlib` 命令返回 `invalid command name`，该命令只能由 `pds_shell.exe` 执行。
- 为保持门禁语义一致，移除了 `SkipSimulatorValidation` 绕过参数；现在每次调用都必须先验证 `vsim.exe`、`vlog.exe` 和 `vlib.exe`。
- 两个新增 PowerShell 脚本与现有五个项目脚本 AST 解析错误均为 0；本批未修改 RTL、IP、PLL、FDC、RCF 或生成物。

## 2026-08-30：三项目 S1/S2/S3 仿真就绪度盘点

- 新增 `docs/SIMULATION_READINESS_MATRIX.md`，记录 DDR3、PCIe DMA 与 OV5640→DDR3→PCIe 产品主线的项目级 TB、filelist、DO、路径可移植性和四级仿真缺口。
- 厂商示例顶层不能作为项目验收；后续统一新增项目自有相对路径入口。
- 本批只做静态盘点和 TODO 排序，未运行 PDS、ModelSim/QuestaSim 或 SDF 仿真。

## 2026-08-30：CI-1 仿真矩阵引用门禁

- 门禁同时验证根 `README.md` 与 `TODO.md` 均链接 `docs/SIMULATION_READINESS_MATRIX.md`，防止规划文档脱离入口指南。
- PowerShell AST、仓库一致性门禁和 `git diff --check` 均通过；本批未运行 PDS、ModelSim/QuestaSim 或 SDF，也未修改 RTL/IP/约束/生成物。

## 2026-08-30：PCIe H2-B 静态元数据 gate

- `pcie_dma_test_100h/scripts/check_build.ps1` 现在直接解析活动 `ipcore/pcie_test/pcie_test.idf`，校验 family、device、package 和 speedgrade 是否为 `Logos2/PG2L100H/FBG484/-6`。
- 元数据不一致会进入已知问题集合：显式 `-AllowKnownBaselineIssues` 可复现当前基线，严格模式必定失败；旧的日志重复匹配已移除。
- 本批仅修改 gate、TODO 和实现记录；未修改 PCIe RTL、IDF、FDC、厂商 IP 或生成物。

## 2026-08-30：H0/H1/H3 板级证据清单准备

- DDR3、PCIe 与 OV5640 产品主线分别维护板级事实、资料来源和关闭条件。
- 清单覆盖 FPGA/板卡身份、DDR3 颗粒与拓扑、时钟/复位、bank 电压、share pin、摄像头输入格式和产品接口。
- 资料缺失时不修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物。

## 2026-08-30：CI-2 板级证据清单完整性门禁

- 仓库级一致性脚本检查板级证据清单的“当前工程事实”“必须提供的资料”“关闭条件”章节。
- 门禁只验证结构和入口，不把模板或待提供字段当作已确认硬件事实。
- 本批未修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物；资料阻断保持不变。

## 2026-08-30：CI-3 项目 README 元数据完整性门禁

- 仓库级一致性脚本现按项目检查 README 是否明确记录器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断。
- 检查使用项目特征匹配，兼容现有三份 README 的表达差异；不把静态文档门禁当作板级、PDS 或仿真验收。
- 本批仍未修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物；S0/H0/H1/H2/H3 及 O2-D2/D3-A 审核闸门保持原状。

## 2026-08-30：CI-4 PDS 构建 gate 契约完整性门禁

- 仓库级一致性脚本现检查三个项目的 `run.ps1` 是否处理 PDS 退出码、`^E:` 日志和阶段入口，并检查 `check_build.ps1` 是否覆盖阶段标志、时序摘要、失败抛错与非零产物。
- 三项目仍保留显式 baseline 放行开关；静态门禁不会把 baseline 结果视为发布通过，也不替代真实 PDS/STA/位流执行。
- 本批未修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物。

## 2026-08-30：CI-5 PowerShell AST 语法门禁

- `scripts/check_repo_consistency.ps1` 现自动扫描仓库内全部非 `build/` `.ps1` 文件，并使用 PowerShell Parser 报告语法错误文件、行号和消息。
- 当前扫描 8 个脚本全部解析通过；该门禁不执行 PDS、ModelSim/QuestaSim 或项目构建。

## 2026-08-30：S0-0-R 仿真器环境复核

- 重新检查 PATH、`C:/questasim64/win64`、常见 ModelSim/QuestaSim 安装目录及 `vsim.exe` 文件名，仍未发现 `vsim.exe`、`vlog.exe`、`vlib.exe`。
- S0-1 继续等待用户安装并提供有许可证的仿真器；本次只更新阻断证据，没有运行 `compile_simlib` 或动态仿真。

## 2026-08-30：DDR3 D3-0-R 端口与层级核对

- 只读核对活动 `ip_core/ddr3/ddr3.v`、`example_design/rtl/test_ddr.v` 与 D2 契约，确认参数默认值、128-bit 用户数据、28-bit 控制器地址、DDR 物理端口和 `I_ips_ddr_top` 实例边界。
- 明确活动接口不是完整 AXI4：写地址使用 `axi_awvalid && axi_awready`，写数据接受依赖 core 输出 `axi_wready`，读返回使用 `axi_rvalid/axi_rlast`，没有 `axi_rready`。
- 形成 [`D3A_PORT_MAP.md`](../ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md)。本批只新增只读文档与 TODO 状态，不修改厂商 IP、RTL、FDC、RCF 或物理端口；D3-A 仍等待审核。

## 2026-08-30：CI-6 DDR3 D3-0-R 契约一致性门禁

- 仓库一致性脚本现静态核对活动 `ddr3.v`、`test_ddr.v` 和 `D3A_PORT_MAP.md` 的模块、参数、端口、实例层级事实，并拒绝 `ddr3.v` 出现 `axi_rready`。
- 当前门禁通过；该检查只防止 D3-0-R 文档与源码漂移，不执行 D3-A RTL、PDS 或仿真。
- DDR3 只读复核发现活动 IDF 同时记录 `DESIRED_DDR3_RATE=1066.000` 与另一处 1050 速率参数；wrapper 默认 `MEM_ROW_WIDTH=15`、`COLUMN=10`、`BANK=3`、`DQ=16`、`DQS=2`。在确认参数语义、颗粒料号和 PCB 拓扑前，H1 继续阻断。

## 2026-08-30：S0-0 仿真器路径扩展复核

- 复核 PATH、`C:\questasim64\win64`、常见 ModelSim/QuestaSim 安装目录及 Windows 卸载注册表，均未发现 `vsim.exe`、`vlog.exe` 或 `vlib.exe`。
- 本批没有下载或安装商业仿真器，也未调用 PDS `compile_simlib`；S0-1 仍等待用户提供合法安装路径、版本和许可证环境。

## 2026-08-30：历史错误假设——三项目 PG2L50H 目标审核与迁移规划

> 2026-09-04 纠偏：本节记录已作废的 50H 平台假设，只用于解释旧提交和旧产物来源；当前唯一平台为 `RK3568_MES2L100H / PG2L100H-6IFBG484`，不得执行本节迁移指令。

- 当时误把系列手册文件名解释成实物选型，进而把三个项目写成 `PG2L50H-6IFBG484` 并规划 50H 迁移；该结论已于 2026-09-04 作废。
- 当时曾因错误的 50H 选型判断而降级既有 PG2L100H 产物；当前这些产物仍需重新核验，但原因是 IP metadata、版本、约束和板级证据未闭合，而不是平台应改为 50H。
- 当时错误地把 PCIe 50H IDF 视为正确输入并计划把 build/gate 降到 50H；当前做法相反：build/gate 保持 100H，并硬拒绝该 IDF。
- 当时规划用 SP6.4 重生成 50H DDR3 controller/PHY、FDC/RCF 和仿真资产；该执行路径已作废，当前只能核验或重生成 PG2L100H 资产。
- O2-D1-G 的状态机、复位分权、唯一 `/5` clock 和端点覆盖方法仍可复用，但任何旧器件 STA/指纹都不能作为当前 PG2L100H 验收证据。
- 本批只更新规划、README、板级证据和契约状态；未修改 RTL、厂商 IP、IDF、FDC、RCF、构建脚本或生成物。

## 2026-08-30：历史错误假设——PCIe M1 PG2L50H 首批迁移

- 将 `pcie_dma_test_100h/scripts/build.tcl` 的 PDS 目标改为 `Logos2 / PG2L50H / FBG484 / -6`，并把 `check_build.ps1` 的器件期望改为 PG2L50H。
- 门禁新增三方器件交叉校验：PDS 构建日志的 `set_arch`、最终 timing report 的 `Device` 字段、`generate_bitstream/bgr.db` 的 `PG2L50H-6FBG484`；发现陈旧 PG2L100H 即失败。
- 首次 50H 完整构建暴露旧 FDC 的 `HSSTLP_364_918` 资源名无效；依据 PDS 2022.2-SP6.4 官方 HSSTLP PG2L50H 模板，将 x2 lane/PLL0 迁移到 `HSSTLP_292_612`。未修改 lane 逻辑、管脚或电气属性。
- 从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，PDS 退出码为 0，日志无 `E:`，生成非零网表、慢角 SDF、`.sbit` 和 `.bin`。
- 新 50H timing report 为 `All Constraints Met`，门禁解析的最差 slack 为 `0.100 ns`；资源约为 3779 LUT、4279 FF、40.5 DRM、6 个顶层 I/O。
- 严格 `check_build.ps1` 返回非零并精确报告 UART RX 死通道、未约束顶层 I/O、PCIe 串行 I/O 约束缺口、M15/M16 share pin 和 SCBV 未配置。显式 baseline 放行返回 0，但明确标记不可发布。
- 本批未运行 ModelSim/QuestaSim；S0-1 仍因本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断。

## 2026-08-30：PCIe H2-B0 精确 baseline 指纹门禁

- 复验当时的 PG2L50H 历史构建：baseline gate 返回 0 并明确不可发布，strict gate 返回 1；该结果只用于解释旧指纹。
- 旧 gate 只按五个宽泛正则判断是否命中，不比较对象或数量；同类别新增、消失、改名、share-pin 位置漂移可被误放行，IP metadata mismatch 也被错误并入 baseline 集合。
- 新增 `doc/H2B_BASELINE_FINGERPRINT.json` 与审核文档，将五类阻断归一化为 16 个签名、42 次记录。baseline 模式逐项比较完整多重集；metadata 漂移改为无条件硬失败。
- 日志变异测试覆盖缺失 UART、重复 UART、Timing 端口改名、share-pin `M15 -> N15` 和 IDF `PG2L50H -> PG2L100H`，五项即使显式 baseline 均返回 1。
- 本批未修改 RTL、活动 IDF、FDC、厂商 IP 或生成物；lane/refclk/PERST#/SCBV/UART/I/O timing 仍属于 H2-B1 外部阻断，strict gate 继续失败。
- 审计另发现 partial PDS run 可能遗留旧 full-build 日志与产物；该问题进入 CI-8 provenance/freshness，不在本批用时间戳容差或隐式假设处理。

## 2026-08-31：CI-8A PCIe 单次构建证据绑定

- 新增 `scripts/pds_sources.f`，让 PDS Tcl 与 PowerShell provenance 共用 37 个 HDL 的唯一有序清单；活动 IDF/FDC 和构建入口合计形成 43 项 canonical 输入。
- 新增 `scripts/build_provenance.ps1`；`run.ps1` 每次 build 开始即以唯一 `run_id` 原子替换旧 manifest，状态为 `running/partial/failed/complete`，只有完整 `gen_bit_stream` 可设置 `valid=true`。
- `build.tcl` 强制校验并回显 32 位小写十六进制 `PDS_RUN_ID`，完整结束时输出同 id 的 `PDS_RUN_COMPLETE`；gate 要求两个标志各出现一次。
- complete manifest 固定记录 full log、timing report、post-PNR 网表、slow SDF、`.sbit`、`.bin` 和 `bgr.db` 七项证据的工程相对路径、长度和 SHA-256。
- 动态负测证明：真实 partial compile、PDS executable 缺失、run-id 漂移、`bgr.db` 字节漂移和 FDC 输入漂移均返回 1，旧 full-build 证据不可复用。
- 该历史 PG2L50H 七阶段构建曾返回 0，manifest 为 complete/valid、43 输入/7 证据；现已降级为旧产物来源记录，不得用于当前 100H 验收。

## 2026-08-31：PCIe S2-A 项目级行为 smoke 入口

- 新增项目自有 `tb_pcie_dma_test.sv`，实例化真实 `pcie_dma_test` 顶层；按 VSCS 记录职责、时钟/复位假设、验证边界和失败语义。
- 新增受控 `pcie_test` 边界模型，只提供确定性的 refclk/pclk、core reset、idle 接口和延迟 link 激励；明确不验证 LTSSM、TLP、DMA、lane/refclk 电气或板级时序。
- 新增 `sim/behav.f`，嵌套复用 37 个 HDL 的 canonical `scripts/pds_sources.f`，仅追加两个真实 reset helper、受控模型和项目 TB；不维护第二份 RTL 清单。
- 新增 `scripts/run_behav.do` 与 `scripts/check_sim.ps1`。DO 使用相对路径、独立 work、USIM 和 transcript；静态门禁检查 filelist 顺序、路径、模型端口、DUT/TB/DO 契约。
- `run.ps1 -Action sim-behav` 现在生成唯一 `SIM_RUN_ID`，动态成功必须在同一日志中包含匹配 run marker 和唯一 `TEST PASS`。
- S2 后续拆为 S2-B 真实厂商 RC/EP LTSSM/link-up 和 S2-C 基础 DMA 回读；S2-A model-controlled link 不得冒充两者。
- `run.ps1` 属于 CI-8A canonical 输入，因此 S2-A 入口变更后旧 manifest 被正确拒绝；当时按错误 50H 目标重新执行的七阶段构建只保留为 provenance 机制历史证据，不是当前器件证据。
- 本机仍未发现 QuestaSim/ModelSim，故本批只完成静态门禁，未执行动态仿真、未生成 `TEST PASS`；活动 IDF、FDC、项目 RTL 和厂商示例未修改，忽略的 PDS 证据仅由上述同一次 canonical 构建自动刷新。

## 2026-08-31：PCIe S2-B 真实 RC/EP 静态入口

- 新增 `tb_pcie_dma_link.sv`，以厂商 `pango_pcie_top_sim` 为 Root Complex、项目真实 `pcie_dma_test` 为 Endpoint，共用 100 MHz 差分 refclk 并双向直连 x2 lane。
- PASS 合同要求 RC/EP 两端 `smlh_link_up`、`rdlh_link_up` 为 1，LTSSM 为 L0 并稳定 32 个 refclk 周期；6 ms watchdog、未知态或掉链均 `$fatal`。
- 新增 50 项 `sim/link_vendor_local.f`。它保持厂商 filelist 顺序，只保留 PCIe 底层、真实 EP wrapper、仿真 RC wrapper 和三个 RC-only cfg 模块，排除厂商 TB、厂商 EP top 及重复 UART/DMA example RTL。
- `pcie_vendor` 独立编译 10 个加密 DWC 头和厂商 DO 的 DWC/HSST/GTP block；216 条旧安装前缀由 `PANGO_PDS_ROOT` 替换，项目/RC/TB 则编译到每个 `SIM_RUN_ID` 的独立 `work`。
- 新增 `check_link_sim.ps1`，静态检查源清单、双库、路径、拓扑、私有层级、LTSSM、watchdog、marker 和唯一 PASS。`tclsh` mock probe 验证 11 次预期 `vlog` 调用的 Tcl 语义，但不等同于模型编译或仿真。
- 当前机器仍缺少 ModelSim/QuestaSim，因此 S2-B 仅标记静态入口完成，未声明动态链路、RK3568 实板、协商宽度/速率或 DMA 通过。

## 2026-09-01：PCIe S2-A Questa 动态闭环

- 使用 Questa Sim-64 `2021.1` 和已编译的 Logos2 USIM 执行项目级 S2-A；工具安装与许可证配置均由仓库外参数提供，仓库不记录许可证路径、服务器、feature、内容或许可证文件。
- 首次动态运行证明 `sim/behav.f` 缺少 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`。该文件已由 PCIe IDF 管理实现侧资产，因此只加入仿真 filelist，不修改 37 项 canonical PDS 源清单。
- Pango RAM 模型固定引用顶层 `GRS_INST.GRSNET`，TB 的 `GTP_GRS` 实例名按厂商模型契约改为 `GRS_INST`；厂商生成文件保持只读。
- Questa 2021.1 的 transcript 不记录 Tcl `puts` 输出，`run_behav.do` 改用 `echo` 写入随机 `SIM_RUN_ID`；PowerShell 仍要求同一日志中匹配 run marker 和唯一 `TEST PASS`。
- 最终 run id `fab4ccef3e2445abbd9d1cad1e66b2ab`：RTL 编译 `0 errors/0 warnings`，elaboration 成功，运行至 `1476105 ns`，`Errors: 0, Warnings: 2`，唯一 `TEST PASS`，PowerShell 动态入口返回 0。
- 两条 warning 精确指向 `u_ips2l_pcie_dma` 未连接输出 `o_trgt1_radm_pkt_halt`，作为后续独立 RTL hygiene TODO；S2-A 通过仍只证明受控边界、复位链和 LED 域，不证明真实 LTSSM、TLP、DMA、RK3568 链路或可发布位流。

## 2026-09-01：CI-9 许可证敏感差异门禁

- 新增 `scripts/check_sensitive_diff.ps1`，只检查相对 Git 基线的新增文件名和新增行，不读取或回显本机许可证环境变量实际值。
- 门禁拒绝许可证文件、包含许可证信息的 Windows 绝对路径、许可证环境变量实际赋值、真实服务器端点、FlexNet 内容、签名和 host id；`<license-source>` 等明确占位符允许用于文档。
- 新增 [`SENSITIVE_DIFF_GATE.md`](SENSITIVE_DIFF_GATE.md)，记录 `BaseRef`、堆叠 PR 用法、允许占位符和历史边界。
- `scripts/check_repo_consistency.ps1` 现自动运行 CI-9 规则自检和真实 Git 差异检查；规则自检覆盖 2 个允许的新增行场景、5 个拒绝的新增行场景、1 个允许文件名和 1 个拒绝文件名，当前分支相对 `origin/main` 的扫描退出码为 0。
- CI-9 只阻止新增泄露，不清理已跟踪历史日志或 Git 历史；历史重写和强推仍属于单独人工审核批次。
## 2026-09-01：OV5640 范围校正、Questa 复验与许可证日志脱敏

- 从远端快进到 PR #5 合并后的最新 `origin/main`，后续工作基于该主线。
- 产品主线明确为 OV5640→DDR3→PCIe，并由 `main_ov5640_pcie/` 承载独立实现与验证证据。
- 新增 `docs/OV5640_TARGET_SCOPE.md`，将参考工程只读导入、单/双摄与模组接口冻结、项目边界、PG2L50H 迁移和四级 Questa 验证拆为 C0/C1/C2/C3/S3。
- 本机复核确认 Questa Sim-64 `2021.1` 的 `vsim`、`vlog` 和 `vlib` 可执行文件位于安装根的 `win64` 子目录；tracked 文档不记录本机安装或许可证实际路径。
- PCIe S2-A/S2-B 静态门禁和环境检查通过；当前 S2-A 动态启动因外部许可证 checkout 失败返回 4，没有生成新的 `TEST PASS`。历史 run id 的通过证据继续保留，但不作为本次复验结果。
- 发现历史 PDS 日志中存在许可证绝对路径；当前版本统一替换为 `<license-path>`，并将 CI-9 扩展为当前树全量扫描和 PR 新增差异扫描。历史 `.log` 标记为 `-diff`，避免 PR 页面展开旧路径；该修复不改写 Git 历史。

## 2026-09-02：main OV5640 M1-A DVP RGB565 采集

- 新增独立 `main_ov5640_pcie/` 目录；本批只实现板级无关的 `cam_pclk` 域 DVP 8-bit
  字节拼接、RGB565 像素坐标和帧/行边界事件，不导入 `parallel_driver` 的 RTL、IP、FDC、
  PDS 或运行态。
- `ov5640_dvp_rgb565_capture` 默认按首字节高位优先拼接 RGB565，并将 VSYNC 有效沿作为
  帧边界、HREF 作为行窗口；HREF 关闭时的未配对字节和 16-bit 坐标溢出报告
  `protocol_error`。
- 自检 TB 覆盖两行三像素、像素顺序、零基坐标、首帧/行首、行尾、下一帧帧尾以及奇数字节
  负向场景；失败使用 `$fatal`，成功只输出一次 `TEST PASS`。
- 项目脚本 `main_ov5640_pcie/scripts/run_m1a.ps1` 将 Questa 编译库、日志和 transcript
  全部写入 `main_ov5640_pcie/build/`，模拟器目录通过参数传入，不写入仓库。
- Questa Sim-64 2021.1 项目脚本实测编译 `0 error/0 warning`，行为仿真返回 0，日志唯一
  `TEST PASS`；该证据不覆盖 SCCB、板级电气时序、CDC/FIFO、DDR3、图像处理或 PCIe 集成。

## 2026-09-02：main OV5640 M2-A RGB565 图像处理

- 新增 `rgb565_grayscale` 和 `ov5640_dvp_rgb565_pipeline`，将 M1-A 采集输出接入固定一拍
  延迟的 RGB565 灰度处理；算法为 `Y=(77R+150G+29B)>>8`，输出保持 RGB565。
- 新增管线自检 TB，覆盖黑/红/绿/蓝四个像素、两行坐标、帧/行事件保持、奇数字节协议错误
  和唯一 `TEST PASS`。
- 新增 `run_m2a.ps1`，运行态只写入 `main_ov5640_pcie/build/`；模拟器目录由参数提供，
  不写入仓库。
- Questa Sim-64 2021.1 实测 4 个 RTL/TB 模块编译 `0 error/0 warning`，管线行为仿真返回 0；
  当前证据仍不覆盖 SCCB、板级时钟/电气时序、CDC/FIFO、DDR3、PCIe 或 PDS 实现。

## 2026-09-03：main OV5640 M3-A 128-bit 图像字打包

- 新增 `rgb565_word_packer`，按接收顺序将 8 个 RGB565 像素组织为 128-bit 字：
  像素 0 位于低 16 bit，`word_keep` 低 2N 位表示 N 个有效像素的 byte lane。
- 部分行尾字补零并保留 `line_end`；无数据的帧尾和协议错误以控制事件输出，避免
  帧边界或错误被静默吞掉。
- 新增 `ov5640_dvp_rgb565_word_pipeline` 连接层、单元 TB、DVP 集成 TB 和
  `run_m3a.ps1`。集成测试覆盖 8 像素完整字、3 像素行尾字、帧尾事件和奇字节
  协议错误传播。
- Questa Sim-64 2021.1 实测 6 个 RTL/TB 模块编译 `0 error/0 warning`，集成行为
  仿真唯一输出 `TEST PASS`，返回码为 0。
- 本批只定义内部 128-bit 数据布局，不证明 DDR3 用户接口地址单位、CDC/FIFO、
  PCIe AXIS `tkeep` 转换、PCIe TLP、主机地址或板级 OV5640 配置。

## 2026-09-03：main OV5640 M3-B DDR3/PCIe 适配层接口审计

- 只读核对 M3-A、活动 PCIe DMA 和 DDR3 用户接口，确认 M3-A 的 16-bit `word_keep`
  与 PCIe 的 4-bit `tkeep` 不是同一语义，禁止直接连线。
- 确认 PCIe Memory Write 还依赖独立的 10-bit 请求长度、64-bit 目标地址、32-bit
  请求数据和 4 KB 边界状态；数据流、请求描述、TLP 分段必须由适配层分别管理。
- 确认 DDR3 用户口为 128-bit 数据/16-bit 写掩码的非标准 AXI-like 接口；地址单位、
  burst 长度和 `axi_wready` 完成语义尚未获得足够一手依据，暂不实现帧缓存地址发生器。
- 新增 [`MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md`](MAIN_OV5640_PCIE_M3B_ADAPTER_CONTRACT.md)，
  固化转换职责、禁止事项和 M3-B 关闭条件。本批未修改 RTL、TB、厂商 IP、FDC/RCF 或生成物。

## 2026-09-03：main OV5640 M3-B staging adapter

- 新增 `rgb565_word_to_axis4_adapter`，将 M3-A 的 128-bit/16-byte 内部字按低 lane
  顺序拆为最多四个 32-bit staging beat；每个 beat 独立产生 4-bit `out_keep`。
- 输入字在 downstream backpressure 期间保持；首帧/首行事件附着首 beat，行尾/帧尾/
  协议错误附着末 beat；无 payload 控制事件使用 `out_keep=0` 和 `out_last=1`。
- 新增 `tb_rgb565_word_to_axis4_adapter.sv` 与 `run_m3b.ps1`，覆盖完整字、部分字、
  空载控制事件及背压。该 staging `out_user` 仍不是厂商 PCIe `tuser` 合同。
- Questa Sim-64 2021.1 实测编译 2 个 RTL/TB 模块为 `0 error/0 warning`，行为仿真
  返回 0，日志唯一 `TEST PASS`；中途修复 beat 最后索引 2-bit 回绕和 TB 部分字激励/调度问题。
- 复核发现多 beat 字的末事件曾在中间 beat 保持；现改为首事件仅出现在首 beat、
  行尾/帧尾/协议错误仅出现在末 beat，并由 TB 显式检查中间 beat 的 `out_user=0`。
  修正后再次得到 `0 error/0 warning` 和唯一 `TEST PASS`。

## 2026-09-03：main OV5640 M3-B 帧统计描述符

- 新增 `rgb565_axis4_frame_accounting`，从 staging beat 的 4-bit keep 和事件位统计
  有效字节、有效 beat 与协议错误，在帧尾生成固定描述符；不承载 DDR3 地址或 PCIe TLP 语义。
- 新增独立 Questa 入口 `run_m3b_accounting.ps1` 和 TB，覆盖 5-byte/2-beat 累计、
  空载帧尾、错误传播和描述符背压；编译 `0 error/0 warning`，行为返回 0，唯一 `TEST PASS`。

## 2026-09-03：PCIe Memory Write 请求边界审计

- 只读核对活动 PCIe DMA 控制器，确认 `req_addr` 为高低地址拼接，`req_length` 在
  控制器内按 DWORD 计数并参与字节长度/4 KB 边界计算，`req_data` 为 32-bit。
- 确认 `i_mwr32_req`/`i_mwr64_req` 与 ack 驱动内部状态机；这些端口不是可直接连接
  staging stream 的标准 `valid/ready` 协议。
- 决策：下一批先实现并验证板级无关的规范化 Memory Write 请求描述符，再实现独立
  厂商桥接层；本批不修改 PCIe IP，不声称 DMA 或主机输出已通过。

## 2026-09-03：main OV5640 M3-B 联合 staging wrapper

- 新增 `ov5640_dvp_rgb565_dma_staging_pipeline`，连接 OV5640 DVP 采集、灰度处理、
  128-bit word packer、4-byte staging adapter 和帧统计描述符；本批不接 DDR3、PCIe、
  CDC 或板级配置。
- 修正 wrapper 握手：staging 输出由外部 `staging_ready` 与 accounting `in_ready`
  合取施加背压，`desc_ready` 不再直接反向控制数据通道。
- 修正 word packer 的纯控制事件分支，确保无 payload 的帧尾/协议错误事件也拉高
  `word_valid`；否则帧尾会在 M3-A 与 M3-B 之间静默丢失。
- 联合 TB 覆盖 3 像素、2 个 staging beat、6 个有效字节、帧尾描述符和错误为 0；
  Questa Sim-64 2021.1 编译 `0 error/0 warning`，行为仿真返回 0，唯一 `TEST PASS`。
- 由于 M3-A 当前无输入背压，wrapper 暂以一位 `frame_end_pending` 将提前到达的帧尾
  对齐到最后一个 staging payload beat；该策略仅限同域 staging 验证，后续真实 FIFO/CDC
  设计必须重新冻结事件承载和吞吐合同。

## 2026-09-03：main OV5640 M3-B 临时 PCIe Memory Write bridge

- 新增 `rgb565_axis4_pcie_mwr_bridge`，将规范化请求描述符映射到已审计的
  `mwr32_req/ack`、`req_length/req_addr/req_data` 和 4 KB 状态请求边界。
- bridge 在 ack 前锁存并保持请求字段；`req_keep` 作为旁路信息保留，因为活动控制器
  的请求端口没有独立 byte-enable 输入。
- 新增独立 Questa TB 和脚本；编译 `0 error/0 warning`，请求字段稳定性和 ack 释放验证
  通过，日志唯一 `TEST PASS`。
- 该 bridge 不实例化厂商 PCIe IP，尚不证明真实 TLP、DMA、byte-enable、主机地址或
  PCIe 链路行为；下一步需用真实控制器/链路模型重新审核启动、ack、busy 和分段语义。

## 2026-09-03：main OV5640 M3-B 临时 DDR3 写记录层

- 新增 `rgb565_axis4_ddr3_write_descriptor`，将单个 32-bit staging beat 放入
  128-bit 写数据低位，并将 4-bit keep 映射到 16-bit 写掩码低位。
- 输出固定单 beat 记录（`write_awlen=0`）；28-bit 地址保持为 opaque token，不解释
  活动 DDR3 IP 的地址单位、初始化时序或 AXI4 burst 语义。
- 地址推进改为显式 `ADDR_STEP` 参数；TB 使用 `BASE_ADDR=0x12`、`ADDR_STEP=0x4`
  验证释放后地址为 `0x16`，不再把 token 步长硬编码为某种地址单位。
- 新增独立 Questa TB 和脚本；编译 `0 error/0 warning`，记录保持/释放、数据和掩码
  映射通过，日志唯一 `TEST PASS`。
- 该层不实例化 DDR3 IP；实际用户口接入必须等待 PG2L100H IP 核验或重生成及 D3-0-M 复核。

## 2026-09-03：main OV5640 M3-B DDR3 写记录边界回归增强

- 扩展 `tb_rgb565_axis4_ddr3_write_descriptor`，覆盖空 `keep` 控制记录、下游背压期间
  数据/地址/标志稳定、第二条记录按 `ADDR_STEP` 推进，以及异步复位后回到 `BASE_ADDR`。
- 使用 Questa Sim-64 `2021.1` 重新编译并运行；编译 `0 error/0 warning`，仿真在 `126 ns`
  完成，日志包含唯一 `TEST PASS`。
- 本批仍只证明规范化单 beat 记录层的握手合同；不改变“28-bit 地址为 opaque token”的
  结论，也不解除真实 DDR3 用户口、地址单位、burst、初始化和 CDC 阻断。

## 2026-09-03：main OV5640 M3-B staging 异步 FIFO

- 新增 `rgb565_axis4_async_fifo`，在独立写入/读出时钟域之间传输 32-bit staging beat，
  携带 4-bit `keep`、`last` 和 5-bit 事件标志；Gray 指针用于跨域传递读写进度。
- 新增独立双时钟 Questa TB，覆盖满/空握手、下游节奏变化、6 个 beat 的顺序和最终 empty。
- Questa Sim-64 `2021.1` 编译 `0 error/0 warning`，仿真至 `287 ns`，日志唯一 `TEST PASS`。
- 该切片仅是板级无关 CDC/FIFO 行为合同；尚未完成静态 CDC/RDC 分类、RAM 推断审计、
  三时钟域复位合同、DDR3/PCIe 用户时钟约束或真实 IP 接入。

## 2026-09-03：main OV5640 M3-B staging CDC bridge

- 新增 `rgb565_axis4_cdc_bridge`，将异步 FIFO 封装为明确的上游/下游 staging 接口，
  事件标志与数据保持同一 FIFO entry，供后续连接采集、DDR3 或 PCIe 用户时钟域。
- 联合 TB 使用独立 `3 ns` 与 `5 ns` 时钟，验证 5 个 beat 的顺序、首/末事件、keep、
  last、下游 ready 和最终 drain；Questa `0 error/0 warning`，唯一 `TEST PASS`，`155 ns`。
- 调试期间发现 FIFO entry 原先按 41 bit 声明，但字段实际为 `5+1+4+32=42 bit`，
  会截断 `user[4]`；已修正为 42 bit，并由末 beat 事件断言复验。
- 本批仍不声称 OV5640 源端具备背压、完成静态 CDC/RDC、RAM 推断、复位释放和真实
  DDR3/PCIe 集成；这些边界继续等待最终帧缓存与板级时钟合同。

## 2026-09-03：main OV5640 M3-B 规范化 PCIe MWR 组合路径

- 新增 `rgb565_axis4_pcie_mwr_path`，串接 staging beat、规范化 MWR descriptor
  和 `mwr32_req/ack` 临时桥，保留请求地址、长度、keep、last、帧尾及协议错误字段。
- 专项 TB 使用 `BASE_ADDR=0x0ffc` 验证 4-byte 请求恰好到达 4 KB 边界时不误报 crossing；
  ack 后下一请求地址为 `0x1000`，并验证请求字段在等待期间保持。
- Questa Sim-64 `2021.1` 编译 `0 error/0 warning`，仿真至 `125 ns`，日志唯一 `TEST PASS`。
- 该路径仍是 vendor-independent 合同，不实例化 PCIe IP；不证明 TLP、DMA、byte-enable、
  链路、主机地址或真实控制器启动/忙状态已经闭合。

## 2026-09-03：main OV5640 M3-B DVP 到 CDC staging 联合切片

- 新增 `ov5640_dvp_rgb565_cdc_staging_pipeline`，串接 DVP 采集、灰度处理、128-bit
  打包、4-byte staging adapter 和双时钟 CDC bridge；输出域接收数据与事件标志。
- 新增 `source_overflow` 粘滞状态，显式报告 camera-side packer 无输入背压时 adapter/FIFO
  无法接收的情况；它不声称自动恢复或无损。
- 小帧双时钟 TB 验证 2 个 staging beat、有效 keep、首/末事件跨域到达；Questa `0 error/0 warning`，
  唯一 `TEST PASS`，仿真至 `413 ns`，并确认压力场景置位 `source_overflow`。
- 本批仍未接入真实 DDR3/PCIe IP，未完成三时钟复位、静态 CDC/RDC、RAM 推断和帧缓存
  丢帧/恢复策略；`source_overflow` 是当前进入帧缓存前的明确阻断信号。

## 2026-09-03：main OV5640 M1-M3B 回归与工具环境诊断

- 全回归首先发现 M3-A 旧 TB 将 `word_valid` 等同于 payload；随着纯控制事件修正为
  `word_valid=1、word_keep=0`，两个 TB 已改为按 keep 区分 payload 与控制事件，M3-A
  和联合 M3-B 随后重新通过。
- accounting 回归曾在 `vopt` 阶段报告 `Unexpected signal: 11`。最小化诊断确认
  Questa 实际报错为 `database or disk is full`，当时 D 盘仅剩 16 KB；清理忽略的
  `main_ov5640_pcie/build/` 运行态后，accounting 重新得到 `0 error/0 warning` 和
  唯一 `TEST PASS`。该故障不归因于 RTL。

## 2026-09-03：main OV5640 M3-B 源端短突发缓冲

- 新增 `rgb565_word_skid_buffer`，位于无背压 `rgb565_word_packer` 与 4-byte staging
  adapter 之间，使用两个槽位保存 128-bit word、16-bit keep 和五项帧/行事件。
- 缓冲输入沿用 packer 的无背压 `word_valid` 脉冲；输出使用标准 `valid/ready`。下游
  暂停时保持队首字段，满队列同拍出队/入队允许替换尾槽；无可用槽位时丢弃新 word，
  `overflow` 异步清零、事件发生后粘滞保持。
- 新增 `tb_rgb565_word_skid_buffer.sv` 与 `run_m3b_word_skid_buffer.ps1`。Questa
  Sim-64 2021.1 编译 `0 error/0 warning`，仿真至 `85 ns`，日志唯一 `TEST PASS`。
- `ov5640_dvp_rgb565_cdc_staging_pipeline` 已接入该缓冲，联合 TB 的正常期验证 2 个
  payload beat 加 1 个空载帧尾事件且无 overflow；64 像素、下游暂停压力期置位
  overflow，恢复 ready 后排出 19 个保留 beat。联合 Questa 编译 `0 error/0 warning`，
  唯一 `TEST PASS`，仿真至 `2527 ns`。
- 测试诊断修正了一个过时假设：无 payload 帧尾是合法输出事件，不能从 staging beat
  统计中删除。该缓冲只吸收短突发，未定义 overflow 后的帧丢弃/恢复，也不解除静态
  CDC/RDC、三时钟复位、RAM 推断、真实 DDR3/PCIe IP 和板级协议阻断。
- 以上为提交 `16ce24e` 的初版短缓冲证据；其中 `85 ns`、`2527 ns`、19 个保留 beat
  和“恢复未定义”由本日志后续的 overflow 整帧中止与恢复批次取代。

## 2026-09-03：main OV5640 行为级 DDR3→PCIe 往返切片

- 新增 `tb_ov5640_ddr3_pcie_loopback.sv`，通过公开接口串接 OV5640 DVP 采集、灰度/128-bit
  打包、双时钟 staging、规范化 DDR3 单 beat 写记录、受控 DDR3 存储模型和 PCIe MWR 请求路径。
- DDR3 模型按规范化记录槽位保存 `data/keep/last/frame_end/protocol_error`，再逐条读回；
  不把 28-bit DDR3 地址 token 解释为真实控制器地址单位。
- 3 像素帧产生 3 条记录：`keep=0xf`、`keep=0x3` 和空载帧尾 `keep=0x0`；PCIe MWR
  请求以 `0x0ffc` 起始，按有效字节推进到 `0x1000`、`0x1002`，并验证请求字段在 ack
  前保持、4 KB 边界不误报。
- 使用 Questa Sim-64 `2021.1` 运行 `run_m3b_ov5640_ddr3_pcie_loopback.ps1`；编译和仿真均为
  `0 error/0 warning`，日志唯一 `TEST PASS`，仿真至 `442 ns`。
- 该证据只证明行为级接口字段和控制事件贯通；尚未证明厂商 DDR3 初始化/读写时序、真实
  PCIe TLP/DMA/byte-enable、链路训练、主机目标地址或板级 OV5640 电气时序。

## 2026-09-03：main OV5640 overflow 整帧中止与恢复

- 扩展 `rgb565_word_skid_buffer`：满队列且无同拍出队时，首个无法保存的 word 置位
  sticky `overflow` 并进入丢帧状态；已排队前缀保持 FIFO 顺序，当前帧余下输入被丢弃。
- 缓冲在有空间时注入唯一的 `keep=0/frame_end=1/protocol_error=1` 中止记录。只有已观察到
  原帧尾、中止记录已经排队且后续输入带 `frame_start` 时，才恢复保存新帧；中止记录
  排队前提前到达的新帧会被整帧跳过，避免从帧中段恢复。
- `tb_rgb565_word_skid_buffer.sv` 覆盖已保存前缀、中间 word 丢失、原帧尾、提前新帧跳过、
  唯一中止记录、后续帧恢复和 sticky overflow。后续又补入满队列同拍出入队、
  丢弃侧帧尾与 abort 入队同拍、连续两个损坏帧及 drop 状态异步复位；Questa Sim-64
  2021.1 为 `0 error/0 warning`、唯一 `TEST PASS`、`526 ns`。
- DVP→CDC 联合 TB 的压力帧排出 20 个 beat，其中恰好一个位于末尾的空载错误帧尾；随后 1 像素新帧
  以 2 个正常 beat 恢复且无协议错误。Questa 为 `0 error/0 warning`、唯一 `TEST PASS`、
  `2863 ns`。M3-A 正常路径和 OV5640→DDR3 模型→PCIe MWR 往返仍分别通过。
- 该策略只保证损坏帧可识别并从后续帧首重同步，不保证持续背压无丢帧；DDR3 侧仍需
  作废带协议错误的帧，FIFO 深度、三时钟复位和真实控制器接入仍未闭合。

## 2026-09-03：main OV5640 PCIe 元数据保持与中止记录往返

- PCIe path 新增预取竞态回归：首请求等待 ack 时，descriptor 接收下一条带
  `last/frame_end/protocol_error` 的记录。旧实现的事件元数据直接旁路 descriptor，导致
  当前请求地址/数据/keep 与下一记录事件错配；红灯于 `56 ns` 稳定复现。
- `rgb565_axis4_pcie_mwr_bridge` 现将三个事件位与地址、长度、数据、keep 和 4 KB 状态
  一并锁存。bridge 独立回归为 `76 ns`，组合 path 回归为 `115 ns`，均为 Questa
  `0 error/0 warning`、唯一 `TEST PASS`。
- 扩展行为级 DDR3→PCIe loopback：DDR writer 阻塞时输入 64 像素，压力帧形成 21 条
  DDR 模型记录，唯一空载错误中止位于索引 20；下一帧恢复后，全部记录逐条回送 PCIe。
- 中止记录和恢复 payload 均从 PCIe 地址 `0x104c` 发起，证明 `keep=0` 控制记录不会
  消耗图像地址空间。Questa 为 `0 error/0 warning`、唯一 `TEST PASS`、`3844 ns`。
- 该证据关闭的是 vendor-independent 行为模型中的中止记录保存和回送，不实例化真实
  DDR3/PCIe IP，也不证明 TLP byte-enable、链路、DMA、主机内存或板级时序。

## 最终回归：loopback 模型采样修正

- 最终重跑 word skid、DVP→CDC staging、PCIe MWR bridge、PCIe MWR path、OV5640→DDR3 模型→PCIe
  loopback 和 M3-A；每项均为 Questa Sim-64 2021.1 编译/仿真 `0 error/0 warning`、唯一 `TEST PASS`。
- loopback 仿真至 `3844 ns`：正常帧 3 条记录；64 像素压力帧 21 条记录，唯一 abort 位于索引
  20；1 像素恢复帧 2 条记录；abort 与恢复 payload 的 PCIe 地址均为 `0x104c`。
- 复测发现测试模型若在 `negedge ddr_clk` 延迟采集，会在 descriptor 于 `posedge` 完成最后一次
  握手后提前统计，漏掉最后一条 abort。现改为在 `posedge` 的 `write_valid && write_ready` 握手边沿
  采集，记录语义与接口合同一致。

## main OV5640 帧提交/作废与 PCIe 读出门控

- 审计确认既有路径只有 DDR3 记录写入和逐条 MWR 请求，没有独立的帧完成提交、错误帧作废
  和“只发送已提交帧”边界。
- 新增 `rgb565_axis4_frame_commit`：在规范化记录帧尾锁存有效字节、记录数和累计错误；正常帧
  标记 committed，overflow abort 或中途协议错误帧标记为不可提交；运行中复位清除半帧统计
  和待消费描述符。专项回归 `210 ns`。
- 新增 `rgb565_axis4_frame_readout_gate`：已提交帧按 ready/valid 透传 DDR3 读回记录，帧尾握手后
  关闭窗口；作废帧只产生单周期 drop 提示。增强回归在 `read_valid=1` 时证明作废帧不泄漏，
  并验证运行中复位关闭读窗口。专项回归 `171 ns`。
- 新增 `rgb565_axis4_committed_pcie_mwr_path`，串接提交、读出门控和现有 MWR path。联合回归先
  作废错误帧，再恢复正常帧；仅正常帧产生 `0x2000/0x2004` 请求。等待 ACK 时复位会清除旧请求、
  关闭读窗口，复位后地址重新从 `0x2000` 起始。专项回归 `366 ns`。
- 三项均为 Questa Sim-64 2021.1 `0 error/0 warning`、唯一 `TEST PASS`。当前仍没有帧表、DDR3
  读地址、槽位回收或真实 DDR3/PCIe IP，因此不能解释为板级闭环。

## 2026-09-03：main OV5640 已提交帧读命令与完整行为闭环

- `rgb565_axis4_frame_commit` 描述符增加帧首 opaque DDR token；首记录地址与 records/bytes/error
  一起保持，专项回归仍为 `210 ns`。
- 新增 `rgb565_axis4_frame_read_scheduler`：不可提交描述符不产生命令；已提交帧从首 token 起
  产生单 outstanding 连续读命令，每条命令等待对应响应被后级接受后再推进。专项回归覆盖命令
  背压、三记录顺序、最终完成脉冲和运行中复位，`226 ns`。
- `rgb565_axis4_committed_pcie_mwr_path` 原子分发同一提交描述符给调度器和读出门控，并把读记录
  握手作为调度响应完成事件。错误帧零命令/零 MWR、正常帧地址和等待 ACK 复位回归为 `416 ns`。
- 新增 `tb_ov5640_ddr3_committed_pcie_loopback.sv`：DDR 模型写入与 commit 在同一边沿接受，模型只
  响应调度器命令。正常帧 token `0..2` 到达 `0x2000/0x2004/0x2006`；压力错误帧 21 条记录后
  一次 drop、零读命令、零 MWR；恢复帧 token `21/22` 从 `0x2000/0x2004` 发送。Questa Sim-64
  2021.1 为 `0 error/0 warning`、唯一 `TEST PASS`、`3158 ns`。
- 该证据仍没有带槽号双槽帧表、物理槽复用、真实 DDR3 地址/控制器、PCIe TLP/DMA/链路、
  主机内存或板级时序，不能作为真实硬件闭环结论。

## 2026-09-03：main 读响应完成语义与零延迟配对修复

- 只读评审确认首 token 和描述符原子分发正确，同时发现 gate 按原始 `frame_end`、scheduler
  按记录数分别结束时会在提前或缺失帧尾场景永久分裂；命令与零延迟响应同拍时，旧 scheduler
  还可能漏记已经被下游消费的响应。
- scheduler 现在统一输出响应接收资格，支持命令/响应同拍，并以“原始帧尾或最后计数响应”
  结束当前帧；两者不一致时强制归一化帧尾并置协议 fault。committed 零记录描述符直接输出
  完成/fault，不进入挂死状态。扩展 TB 在旧 RTL 上于 `91 ns` 得到预期红灯，修复后 `346 ns`。
- readout gate 只透传 scheduler 可配对的响应，并由统一完成脉冲关闭；专项回归 `211 ns`。
- committed wrapper 暴露 `frame_done_pulse/frame_fault_pulse`，显式绑定 `TOKEN_ADDR_STEP`，联合
  回归覆盖提前帧尾、缺失最终帧尾、零延迟响应、错误标记和下一帧恢复，`576 ns`。
- 完整 OV5640→DDR3 记录模型→已提交帧读调度→PCIe MWR 行为回归保持 `3158 ns`：正常 token
  `0..2`、压力错误帧 21 条记录且零读/零 MWR、恢复 token `21/22`；全部回归均为 Questa
  Sim-64 2021.1 `0 error/0 warning`、唯一 `TEST PASS`。
- 这些修复关闭的是行为协议死锁，不增加物理双槽、DDR3 控制器、PCIe DMA/TLP 或主机驱动证据。

## 2026-09-03：main 双槽帧表控制面

- 新增 `rgb565_axis4_frame_slot_table`、专项 TB 和 Questa 脚本。槽表提供两个保持型写槽分配，
  管理 `FREE/WRITING/QUEUED/READING` 生命周期，并以深度 2 FIFO 保存 committed 描述符顺序。
- 错误帧不进入读队列，立即释放原槽并输出带槽号 drop；正常读完成必须匹配 active reader
  slot ID，错误、重复或迟到事件只输出 fault，不改变槽状态。
- 初版在 `read_desc_ready` 持续为高时会连续弹出两个描述符，使两个槽同时 READING。专项 TB
  在 `126 ns` 得到预期红灯；加入内部 `reader_active/reader_slot_id` 后关闭该 P1。
- 增加 `SLOT_RECORD_CAPACITY`，零记录、超容量和 committed/error 决策矛盾均 fault-drop；两个
  槽基 token 相同或容量为零由初始化参数检查拒绝。
- 最终槽表专项覆盖两槽同时写、两个 committed 排队、背压保持、单 reader、错槽完成、错误帧
  回收、超容量、合法第二槽 commit 与第一槽 read-done 同拍，以及运行中复位；Questa Sim-64
  2021.1 为 `0 error/0 warning`、唯一 `TEST PASS`、`406 ns`。
- `frame_commit` 同步增加首 slot ID 保存和同帧槽号一致性检查，专项更新为 `240 ns`；既有
  committed path `576 ns` 和完整行为 loopback `3158 ns` 保持通过。
- 该批结束时槽表尚未接入 DDR writer、read scheduler 和 committed wrapper；后续接入结果见
  下一节。该独立控制面证据本身不能解释为真实 DDR3 控制器或 PCIe 主机闭环。

## 2026-09-03：main 双槽行为主链接入

- `rgb565_axis4_ddr3_write_descriptor` 改为每帧先接受 slot ID、槽基 token 和容量分配；无槽时
  背压 staging。容量内按 `ADDR_STEP` 推进，越界后停在本槽末 token 并强制错误直到帧尾，
  避免污染另一槽。专项 TDD 先因参数缺失红灯，最终 `251 ns`。
- `rgb565_axis4_frame_slot_table` 将容量随 allocation 输出，成为 writer/槽表单一事实源；正确
  WRITING 槽若提交错误首 token，现会 fault-drop 并释放，避免槽泄漏。专项更新为 `436 ns`。
- `rgb565_axis4_frame_read_scheduler` 锁存描述符 slot ID，正常、零记录和帧尾不一致完成均携带
  `frame_done_slot_id`；专项保持 `346 ns`。
- `rgb565_axis4_committed_pcie_mwr_path` 已实例化槽表，frame commit 描述符先排队，队首再原子
  分发给 scheduler/gate；drop 只由槽表产生，scheduler done 带槽回收。专项为 `696 ns`。
- 新增 `ov5640_dvp_rgb565_ddr3_pcie_pipeline`。每条 writer 记录先完成外部 DDR 写握手，下一阶段
  才进入 frame commit，避免已提交帧读到尚未写入的数据；等待 commit 时不会重复 DDR 写事务。
- 完整 OV5640 行为 loopback 覆盖 slot0/slot1 两帧排队、顺序读回、slot0 第三帧复用、21 记录
  错误帧带槽 drop 和 slot1 恢复。Questa Sim-64 2021.1 为 0 error/0 warning、唯一
  `TEST PASS`、`4264 ns`；旧逐条 loopback 更新 writer allocation 后为 `3900 ns`。
- 当前 done 只表示 DDR 响应已离开槽并被本地 PCIe 请求寄存器接受，不表示 PCIe ACK、TLP
  完成或 RK3568 主机已接收。真实板级闭环仍等待原理图、OV5640 初始化、DDR3/PCIe IP 用户口
  和 RK3568 驱动/缓存/帧协议资料。

## 2026-09-03：main 旧 PG2L50H 文件名行为切片——canonical MWR32 TX 语义修复

- canonical 源码审计确认 `i_req_length` 是实际 DWORD 数；旧 normalized path 的单 DWORD值 0
  会被解释为错误长度。descriptor/bridge/path 已统一改为 `length_dw=1`。
- `keep=0` 是项目内部无 payload 帧控制记录，现由 descriptor 本地接受，不产生 vendor MWR，
  也不推进 PCIe 字节地址。vendor 固定 full-DWORD byte enable，partial keep 继续保持未关闭边界。
- 新增 bridge→未修改 `ips2l_pcie_dma_mwr_tx_ctrl` 动态集成 TB。Questa Sim-64 2021.1 于
  `136 ns` 唯一 `TEST PASS`，编译/仿真 0 error/0 warning；验证保持型 ACK、header length=1、
  DWBE=`8'h0f`、地址 `0x1000`、数据低 DWORD=`0x44332211` 和 busy 释放。
- descriptor、bridge、normalized path 同步复跑为 `95/76/125 ns`；committed path、旧 loopback、
  双槽 committed loopback 适配后为 `656/3858/4194 ns`，并验证空控制响应零 MWR、地址不推进和
  scheduler/槽释放。该证据不证明完整 DMA 顶层
  请求仲裁、PCIe 链路训练、RK3568 缓冲映射、主机内存写入或真实 DDR3 接入。

## 2026-09-03：main 旧 PG2L50H 文件名行为切片——canonical DDR3 读写应用边界

- 新增单 outstanding canonical DDR3 写适配器：两拍同步 `ddr_init_done`，AW 保持到握手，数据保持
  到 `axi_wready`，完成型 ready 保证 frame commit 不早于用户口消费。专项 221 ns、联合写路径
  196 ns，均 0 error/0 warning、唯一 `TEST PASS`。
- 审计确认读口没有 RREADY。新增四状态 AR/R 适配器，以本地寄存器吸收不可反压的返回拍；覆盖
  AR 背压、同拍 AR/R、下游背压、RID/RLAST 错误、无命令响应和复位，专项 191 ns 通过。
- 为避免 `bytes/records` 无法唯一重建任意 keep/last，将逐记录 keep、last、frame_end、error 编码
  到 DDR3 第 5 byte，`WSTRB[4]` 恒为 1；零 payload 控制记录因此也有可读回的物理元数据。
- 新增 `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline`，串接 OV5640 双槽主链、canonical DDR3 读写口和
  MWR32 request/ack；端到端 TB 再实例化未修改 vendor MWR TX。4 像素自检完成 3 条 DDR 记录、
  2 条 MWR 及两组 TLP header/data，806 ns 通过。
- 受影响回归：写描述符 251 ns、canonical 写路径 196 ns、双槽 committed loopback 4194 ns、
  canonical MWR TX 136 ns，均 0 error/0 warning、唯一 `TEST PASS`。
- 应用边界尚未实例化加密 DDR3 core 或完整 PCIe DMA 顶层；地址单位、板级槽范围、partial DWORD、
  RK3568 DMA 缓冲/缓存一致性、OV5640 SCCB/管脚和 golden frame 仍是外部关闭条件。

## 2026-09-03：main 旧 PG2L50H 文件名行为切片——PCIe TX 双请求源仲裁

- 审计确认 canonical DMA controller 的 MWR32/MWR64/MRD32/MRD64 共用同一组 length/address/data，
  因此只 mux MWR32 会在其他 native 请求活动时破坏 bundle 原子性。
- 新增项目自有 `rgb565_pg2l50h_pcie_tx_request_arbiter`，不修改 vendor RTL。native 完整 bundle 与
  camera full-DWORD MWR32 使用轮转仲裁，owner 保持到 ACK，ACK 只返回当前源，并保留请求清除空拍。
- 首版专项 145 ns 通过，但 vendor 集成超时，暴露 `i_user_define_data_flag` 在 ACK 后仍被 MWR FSM
  实时读取。仲裁器改为 MWR ACK 时锁存模式并保持到下一 MWR；MRD 不改变模式。
- 最终专项覆盖四类 native 请求、camera 请求、字段稳定、ACK 隔离、轮转、模式保持和复位，
  `245 ns` 通过。动态集成让 native RAM-data 与 camera user-defined 请求共享未修改 vendor MWR TX，
  输出地址 `0x1000/0x2000` 的两组 TLP header/data，`205 ns` 通过。两项均 0 error/0 warning、
  唯一 `TEST PASS`。
- 当前切片只关闭同一 PCIe 时钟域的请求 bundle 仲裁。DDR `core_clk`→PCIe `pclk_div2` 异步 mailbox、
  完整 TX top 接线、partial keep、链路和 RK3568 主机完成仍未关闭。

## 2026-09-03：main DDR→PCIe 异步 MWR32 mailbox

- 新增 `rgb565_pg2l50h_pcie_mwr32_async_mailbox`。单 outstanding 请求使用 toggle 往返，payload 采用
  源寄存保持、目标额外等待一拍捕获的 bundled-data MCP；目标请求保持到真实 ACK，源 ACK 保持到
  原请求撤销。目标 ACK 保持高期间，源端不重新开放 channel ready。
- 独立审查指出 online/token 同级独立同步可能在硅上错拍；实现改为 online 两级、request/ACK token
  三级同步，使 peer-offline 先进入事务决策。该结构仍需 placed-design CDC/RDC 报告确认。
- reset/online 双向握手保证 idle 单域复位必须先被 peer 观察再重入。事务在途任一域复位由保留侧
  产生单周期 fault 并锁存 sticky，禁止静默成功或自动重放；恢复需要协调双域复位。
- mailbox 首轮在 220 ns 因 TB 监视器早于 DUT NBA 更新计数而红灯，修正监视器采样相位后继续；
  第二轮在 332 ns 暴露源端会在目标 ACK 仍高时过早 ready，增加目标 release-ready 返回同步后关闭。
- 最终 mailbox 专项同时运行源快/目标慢和源慢/目标快两实例，覆盖每组至少三笔 token 往返、字段
  稳定、ACK 延迟/延长、请求保持防重复、idle 单域复位、在途双向复位 fault 与协调恢复；
  Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、`2296 ns`。
- 仲裁器完成态改为等待下游 ACK 与已完成源请求都拉低，再接受下一 owner；增强专项 `265 ns`。
- 新增 `rgb565_pg2l50h_pcie_tx_cdc_arbiter`，将 mailbox 输出接到完整 native/camera 请求仲裁。
  native RAM-data 与异步 camera user-defined 请求经未修改 MWR TX 输出两组 TLP，`385 ns` 通过。
- canonical OV5640→DDR3 TB 已拆分 `core_clk` 和 `pclk_div2`：4 像素帧完成 AW/W→AR/R、异步
  mailbox、仲裁和未修改 MWR TX 两组 header/data，`1086 ns` 通过。三项均 0 error/0 warning、
  唯一 `TEST PASS`。
- 当前仍是公开用户口/行为模型证据。完整 `ips2l_pcie_dma_tx_top`、加密 DDR3 core、PDS CDC/RDC/STA、
  partial DWORD、PCIe link、RK3568 缓冲/缓存/驱动与 OV5640 SCCB/模式仍是板级闭环条件。

## 2026-09-04：DDR→PCIe CDC 发布复验

- 在未修改 RTL 的前提下重跑六项关键 Questa Sim-64 2021.1 回归：mailbox 2296 ns、CDC 仲裁到
  MWR TX 385 ns、canonical OV5640→DDR3→异步 PCIe TX 1086 ns、请求仲裁器 265 ns、既有同域
  仲裁集成 205 ns、canonical MWR32 TX 136 ns。
- 六项均为 0 error/0 warning、日志唯一 `TEST PASS`。该证据确认行为级请求和数据字段贯通，
  不替代加密 DDR3 core、完整 PCIe DMA/TX 顶层、placed-design CDC/RDC/STA、链路和主机验证。

## 2026-09-04：RK3568 板卡与 OV5640 DVP 一手资料登记

- 登记本机外部资料 `RK3568_MES2L50H_100H_硬件使用手册_v1.1.pdf`：34 页、
  SHA-256 `FE7017CC64FDAD56ECE2BED92391A9071B2D0B8FB92BDC195BAEA0D987B395F5`。
- 板卡手册确认 RK↔FPGA 使用 PCIe、FSPI、I2C0 和部分 GPIO；PCIe 实际为 x2，FPGA RX0/1
  P/N=`D9/C9/B10/A10`，TX0/1 P/N=`D7/C7/B6/A6`；100 MHz HSST refclk 为 `F6/E6`。
- 手册还确认 `MAIN_CLK_25M=V4`、DDR 参考时钟 `R4/T4`，以及一片
  `F60C1A0004-M79W` x16 512 MByte DDR3；有效地址为 `ddr3_addr[14:0]`，完整物理映射见 PDF 第 13 页。
- 登记本机外部资料 `OV5640_自动对焦照相模组应用指南(DVP_接口)__R2.13C.pdf`：版本 2.13、
  63 页、修改日期 2011-11-04、SHA-256
  `D709BDF8DC26AD2608759B4DFB4BC083DA409F7D3DC7074C47C6B6BFA9D81AD8`。
- 指南确认 8-bit DVP 使用传感器 `D[9:2]`，RESETB 低有效、PWDN 高有效，SCCB 需外部上拉；
  供电/电平差异可能要求 DVP 与 RESETB 电平转换。参考启动下限为 AVDD 稳定 5 ms、PWDN 拉低
  1 ms、RESETB 拉高后 20 ms 再初始化；硬件复位低脉冲至少 1 ms。
- 两份 PDF 只登记位置、版本、hash 和关键页码，不复制入仓、不进入构建依赖。OV5640 实际模组
  排线、FPGA 连接器/Bank/管脚仍保持暂定；指南中的 SCCB `0x78` 写地址和 VGA/YUV 示例不能
  直接冻结为产品 RGB565 配置。
- 当前剩余主阻断为完整原理图/BOM、PCIe PERST#/链路时序、DDR3 IP 正式用户口、产品顶层
  PCIe IP/RX/config/reset/clock 接线、RK3568 驱动/缓存协议，以及 OV5640 实际电平/接线和冻结 RGB565 模式。

## 2026-09-04：main 完整 PCIe TX top adapter

- 新增项目自有 `rgb565_pg2l50h_pcie_tx_top_adapter`，串接 camera MWR32 异步 mailbox、完整 native
  request bundle 仲裁与未修改的 `ips2l_pcie_dma_tx_top`；厂商生成 RTL 未改动。
- 新增非谐波 camera/PCIe 双时钟专项。首轮编译因三个 FIFO filelist 漏写 `fifo/` 子目录失败；
  修正脚本后全量编译通过。第二轮运行超时由 VCD 定位为 TB 在 ACK 后负沿过早撤 request，违反
  下游 MWR 控制器下一正沿采样 `request && ack` 的保持合同；改为本域正沿撤请求后通过，功能 RTL 未改。
- 最终专项验证 native/camera 两笔 MWR32 的 AXIS2 header/data、地址 `0x1000/0x2000`、Requester ID
  `16'h2a18`、DWORD length、byte enable、数据字节序和 TLAST，并断言 AXIS0/1 无意外流量；
  Questa Sim-64 2021.1 为 `385 ns`、编译/仿真均 0 error/0 warning、唯一 `TEST PASS`。
- 受影响回归保持通过：同域 TX 仲裁集成 `205 ns`、CDC 仲裁集成 `385 ns`、canonical
  OV5640→DDR3→PCIe 行为闭环 `1086 ns`，均 0 error/0 warning、唯一 `TEST PASS`。
- 本批只关闭项目请求边界到完整 PCIe TX top AXIS 输出的行为集成缺口；真实 DDR3 core、产品顶层、
  PCIe LTSSM/串行链路、PDS CDC/RDC/STA 和 RK3568 主机内存仍未闭合。

## 2026-09-04：main OV5640→DDR3→完整 PCIe TX top 统一行为集成

- 新增 `ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline`，在同一 camera-only wrapper 中连接
  OV5640/canonical DDR3 主链、异步 request mailbox 和未修改的完整 `ips2l_pcie_dma_tx_top`。
  native DMA、MRD、CPLD、BAR read data 与 TX restart 在该边界内关断，三路 AXIS 保持可见。
- wrapper 只准入 full-DWORD、length 1、无逐记录协议错误且不跨 4 KiB 的请求。partial keep 或
  其他非法请求不进入 mailbox、不获得伪 ACK，产生一次 IO 域 policy fault 并保持 fail-stop；
  sticky 状态只由协调 camera/io/PCIe 复位清除，禁止自动重放。
- 首轮专项按 TDD 在目标 wrapper 不存在时得到 Questa `1 error/0 warning`。实现后首次动态失败由
  TB 把 `frame_done` 误当 TX 完成导致；状态值证明 request 已 fail-stop，按既有“请求路径接受”
  语义修正断言，功能 RTL 不因该测试假设修改。
- 最终统一 TB 在一个实例中覆盖 DVP、canonical AW/W 与 AR/R、非谐波 IO/PCIe 时钟、完整 TX top、
  AXIS0/1 空闲、三笔合法 AXIS2 TLP、partial policy fault 和协调复位恢复。Questa Sim-64 2021.1
  于 `1996 ns` 返回唯一 `TEST PASS`，编译/仿真均 0 error/0 warning。
- 受影响回归保持通过：canonical OV5640→DDR3→异步 MWR TX `1086 ns`、CDC 仲裁集成 `385 ns`、
  完整 TX top adapter `385 ns`，均 0 error/0 warning、唯一 `TEST PASS`。
- 该证据仍不包含加密 DDR3 core、实际产品顶层、PCIe LTSSM/串行链路、RK3568 驱动与缓存协议、
  PDS CDC/RDC/STA、位流或 golden image，不能表述为板级闭环。

## 2026-09-04：PCIe Endpoint AXIS boundary wrapper

- 审计 `pcie_test.v` 和 `pango_pcie_top.v` 后冻结项目边界：Endpoint 产生 `pclk_div2/core_rst_n`，
  三路 AXIS slave 的 ready 由 Endpoint 产生，项目送入 valid/data/last/user；AXIS0/1/2 分别保留
  CPLD/MRD/MWR 通道，camera 图像使用 AXIS2。
- 新增 `main_ov5640_pcie/rtl/rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv`，复用现有完整
  TX-top adapter，明确关闭 native、MRD、CPLD、BAR-read 和 restart 输入；`smlh_link_up` 与
  `rdlh_link_up` 只透传为遥测，不参与 ACK、丢弃或重放策略。
- 新增 `main_ov5640_pcie/tb/tb_rgb565_pg2l50h_pcie_endpoint_axis_boundary.sv` 和
  `main_ov5640_pcie/scripts/run_m3b_pg2l50h_pcie_endpoint_axis_boundary.ps1`。Questa Sim-64 2021.1
  最终编译/仿真均 `0 error/0 warning`、唯一 `TEST PASS`；覆盖 Endpoint reset ownership、
  AXIS0/1 静默、AXIS2 header 后 payload 背压保持、链路遥测和 camera MWR32 header/data/TLAST。
- 调试记录：第一次超时来自 TB 从 IDLE 拉低 ready，第二次来自 ACK 被误当作 AXIS 完成；两次均由
  源码/追踪确认后修正测试合同。另发现仲裁器必须在 camera owner 选中时提前呈现 user-defined
  mode，已修复 `rgb565_pg2l50h_pcie_tx_request_arbiter.sv`，既有回归需重跑。
- 本批只证明项目 TX path 到 Endpoint AXIS 子集的行为接线；不证明真实 `pcie_test` 编译、PHY、
  LTSSM、串行链路、RC、DDR3 持久化、RK3568 主机内存、PDS CDC/RDC/STA 或板级闭环。

## 2026-09-04：PCIe Endpoint 产品接入合同

- 新增 `docs/MAIN_OV5640_PCIE_ENDPOINT_INTEGRATION_CONTRACT.md`，依据仓库内真实
  `pcie_test.v` 与 `pango_pcie_top.v` 冻结 Endpoint 用户时钟/复位所有权、AXIS0/1/2 方向、
  配置字段来源、camera-only 关断清单、ACK 与 AXIS 握手的区别以及链路遥测边界。
- 合同明确产品顶层只允许一套完整 PCIe TX 生成路径；当前项目 wrapper 不实例化真实 Endpoint，
  不复制其复位同步器，也不把 `link_up` 组合门控到 ACK、丢弃或重放。
- 合同将现有专项证据标为等端口 stub 行为验证，保留真实 `pcie_test`/PHY/LTSSM/RX/DBI/APB、
  DDR3 core、RK3568 主机协议和板级 PDS/STA 作为未关闭边界。

## 2026-09-04：当前平台纠偏为 RK3568_MES2L100H

- owner 最新确认当前平台为 `RK3568_MES2L100H`（FPGA + ARM），目标 FPGA 为 `PG2L100H-6IFBG484`，PDS 目标为 `Logos2 / PG2L100H / FBG484 / -6`。
- 活动 PCIe `pcie_test.idf` 仍为 `PG2L50H/FBG484/-6`。本轮只修正项目自有文档、build/gate/入口清单，不修改厂商 IDF；根一致性门禁因此保持对活动 IDF 的硬失败。
- `parallel_driver` 继续独立隔离，只读参考，不进入 `main` 的 RTL、IP、约束、构建产物或验收证据。
- 已进一步修正 TODO、DDR3 README、Endpoint 合同和历史实施记录：PCIe build/gate 的 100H 改造标记为已完成，100H PCIe IP/产物重建保持未完成；旧 DDR3 50H 自动探针继续硬阻断。
- 当前不能宣称 OV5640→DDR3→PCIe 实板闭环；活动 PCIe IDF 仍是唯一已定位的器件级硬阻断，其他板级资料与真实 DDR3/主机协议缺口继续保留。
- 根一致性门禁已同步为 PG2L100H 合同，不再强制旧 50H staging/派生参数；最终运行精确只报告活动 PCIe IDF 的一项器件不一致。
- PDS Tcl 13 项分类、敏感信息 self/full/origin-main、全部 JSON、全部非 build PowerShell AST、Nexus 39 节点/84 边结构和 `git diff --check` 均通过；本批没有 RTL 修改。
