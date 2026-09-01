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

## 2026-08-29：OV7725 CDC/RDC 审计基线

- 本批只新增项目状态与 CDC/RDC 契约文档，不修改 RTL、厂商 IP 或 FDC。
- 明确 `sys_clk`、`i2c_dri_clk`、`cam_pclk`、`pixel_clk`、`pixel_clk_5x`、`clk_50m/ref_clk` 和 `ui_clk` 的来源与用途。
- 明确两个厂商 FIFO 的数据方向：write FIFO 为 `cam_pclk → ui_clk`，read FIFO 为 `ui_clk → pixel_clk`；FIFO 类型正确，但帧复位脉冲跨两侧直接分发，释放未逐域同步。
- 明确 `cmos_frame_vsync/wr_load` 与 `video_vs/rd_load` 缺少单点事件同步契约，并被多个目标逻辑分别采样。
- 明确 `ddr3_init_done` 从 `ui_clk` 域直接参与 camera、pixel 和 AXI 逻辑的异步复位组合；顶层 `rst_n = sys_rst_n & clk_locked` 也未逐域同步释放。
- 旧 STA 直接印证风险：`video_vs → rd_load` setup WNS `-7.056 ns`，read FIFO 指针路径 WNS `-2.279 ns`，`ddr3_init_done → pixel reset` recovery WNS `-4.857 ns`。
- 后续方向固定为逐域复位、状态同步、单点事件同步、FIFO 分侧复位以及结构整改后的最窄时序例外；禁止先用宽泛 `false_path` 消除报告。
- `cam_pclk` input delay、专用时钟路由豁免、DDR/HDMI 板级参数仍需原理图、传感器和 PCB 资料，当前不猜测。

## 2026-08-29：OV7725 SP6.4 完整重建与 gate

- 新构建入口显式固定 `Logos2 / PG2L100H / FBG484 / -6`、16 个手写 Verilog、4 个活动 IDF 和唯一 FDC；不再依赖 `prj/impl.tcl`、`ip_backup/**`、IP 内部 RTL/VP 或示例约束。
- compile-only 从空 `build/` 完成，PDS 退出码为 0、日志无 `E:`，共 1139 条 warning；严格 compile gate 精确命中 39 条项目手写 RTL 端口位宽告警。
- 随后从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，总耗时约 3 分 33 秒，PDS 退出码为 0，日志仍无 `E:`。
- 最终 STA 为 `Some Constraints Violated`。慢角 setup 中 `video_vs/rd_load` 跨域相关路径 WNS `-7.344 ns`、TNS `-132.832 ns`、20/20 端点失败；read FIFO 指针相关路径 WNS `-2.275 ns`、TNS `-24.111 ns`、11/11 端点失败；慢角 recovery WNS `-4.263 ns`、TNS `-202.445 ns`、53/53 端点失败。快角存在相同三组失败端点。
- 完整日志包含 81 条 critical 和 4105 条 warning。critical 分类为 72 条 `ConstraintEditor-2002`、4 条 `SDC-2025`、3 条 `Route-2036`、1 条 `DeviceMap-2011` 和 1 条 `Place-2028`；另有 88 条 `STA-3011`、129 条 `Timing-4086` 和 249 条 `Timing-4087`。
- 新生成 `ov7725_hdmi_syn.vm`（6,873,287 字节）、`ov7725_hdmi_sim.v`（11,600,361 字节）、`ov7725_hdmi_sta.sdf`（8,894,116 字节）、`ov7725_hdmi.sbit`（3,791,112 字节）和 `ov7725_hdmi.bin`（3,789,476 字节）。
- 严格 gate 实测返回 1，覆盖负时序、39 条手写 RTL 位宽、未约束时钟、次优时钟路由/拓扑/放置、share pin 和未约束顶层 I/O；显式 baseline 模式返回 0，只允许当前快慢角六组已知失败端点，并输出不可发布警告。
- 本批未修改 RTL、厂商 IP、FDC 或 RCF，也未运行四级仿真。下一步先做 DDR3 D2 有限自检契约评审，再对 OV7725 O1-A 最小 RTL 卫生修复方案提请审核。

## 2026-08-29：DDR3 D2 有限自检契约

- 只读复核确认现有厂商 `test_main_ctrl_v1_0` 在 `E_END` 后继续随机进入写或读状态，不存在自然 `done`；`bist_stop` 也不会生成完成状态。
- `bist_run_led` 只是完成脉冲计数后的翻转灯，顶层又执行 `err_flag_led = err_flag | bist_run_led`，因此两个 LED 都不能作为 CI 或板级 PASS/FAIL 接口。
- 旧 `ddr3_test_top_tb.v` 仍连接五个已删除端口，依赖 DDR PHY 私有层级和 FSDB system task，并在初始化后固定延时 `$finish`；ModelSim 脚本/filelist 还包含 `D:/pango` 绝对路径。
- D2 决定保留 `ip_core/ddr3/**` 厂商文件不动，后续新增项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv`，直接实例化活动 DDR3 IP。
- 首版契约固定为 16 个单 beat 写读比较 pair、控制器地址 `0x0..0x78`、步长 8、确定数据函数、4096 周期 pair timeout 和 131072 周期 run timeout。
- 完成接口固定为稳定 `test_done/test_failed/error_count/completed_pairs`、失败码和首错地址/期望值/实际值；最终比较及 outstanding 清零后的下一周期才允许置位 `test_done`。
- 新 RTL/TB 必须遵守 VSCS 的模块边界、接口、FSM、复位和验证证据条款；文件不得维护作者/日期历史，注释不得替代 elaboration、assertion、仿真或 PDS 报告。
- 本批只新增契约并同步状态，没有修改 RTL、TB、IDF、FDC 或 RCF。D3 实现待审核；下一批转入 OV7725 O1-A 只读评审。

## 2026-08-29：OV7725 O1-A RTL 卫生修复评审

- 从 SP6.4 完整日志精确复现 39 条项目根 `rtl/` 的 `Verilog-2019`：I2C 1 条、AXI 适配 4 条、DDR3 IP 实例 26 条、顶层参数 6 条、OSERDES 2 条。
- 38 条已有确定修复：I2C 零扩展、地址/长度编码的显式低位选择、25 个 DDR3 IP 定宽 tie-off、顶层参数零扩展及高有效 OSERDES reset。
- 地址和长度左移 3 是现有协议的一部分；当前地址高 3 位固定为 0，burst 为 160。后续必须显式固化低 24/8 bit 及上界，不能直接删除拼接。
- `rst_n` 是有实际扇出的隐式 wire，应显式声明；`sys_init_done` 只有赋值没有读取者，应删除死网。复位跨域结构仍留在 O2，不在 O1-B 顺带重构。
- PDS SP6.4 原语模型和官方 PG2L100H 示例确认 `GTP_OSERDES_E2.RST` 高有效；当前四个 serializer 共八个 OSERDES 的本地复位均被绑 0，后续应连接现有高有效 reset。
- `mem_a` 存在真实冲突：活动 IDF/module/template 为 14 bit，手写顶层和 FDC 为 15 bit，综合网表把 `mem_a[14]` 固定为 0。该项必须等待 DDR3 料号和原理图，转入 H3/O1-C。
- 本批新增 `RTL_HYGIENE_AUDIT.md` 并同步状态，没有修改 RTL、厂商 IP、FDC 或 RCF，也没有运行 PDS 或四级仿真。

## 2026-08-29：OV7725 O1-B RTL 卫生修复

- 将 5 个目标历史 RTL 无损转换为无 BOM UTF-8，并以独立提交 `963a2e5` 固化编码准备；逻辑修改随后单独实施。
- I2C 地址显式 8→16 bit 零扩展；DDR 地址/长度保留 legacy 左移 3 编码，并显式限制为地址低 24 bit、长度低 8 bit；25 个 DDR3 IP tie-off 改为 formal 对应的定宽常量。
- 顶层显式声明 `rst_n`、删除无消费者 `sys_init_done`，并把六个地址/长度连接改为显式定宽。
- serializer 端口统一为高有效 `reset`；四个 serializer 的 master/slave 共八个 `GTP_OSERDES_E2.RST` 均获得受控复位。新增注释按 VSCS 记录极性、原语 `ASYNC_RESET` 行为和 O2/RDC 剩余责任。
- `check_build.ps1` 新增参数上界检查，并把手写 RTL 位宽白名单收紧为唯一 `ddr3_ip.mem_a`；即使 baseline 模式也拒绝其他位宽告警。
- 从空 `build/` 完成 compile：PDS 退出码 0、日志无 `E:`，compile warning 从 1139 降为 1101，38 条确定性手写 RTL 位宽告警全部消失。
- 随后完成七阶段实现：完整日志无 `E:`，warning 从 4105 降为 4067，critical 保持 81；综合网表 6,873,482 字节、PNR 网表 11,604,756 字节、SDF 8,898,464 字节、`.sbit` 3,791,112 字节、`.bin` 3,789,476 字节。
- 接入 OSERDES reset 后新增 Slow/Recovery `pixel_clk → pixel_clk_5x`，WNS `-0.643 ns`、TNS `-4.191 ns`、8/8 endpoint；详细报告确认对应八个 OSERDES。baseline gate 改为精确匹配 `corner/check/clock pair/endpoints` 的 7 组失败指纹，不把该路径视为 waiver。
- PowerShell AST 为 0 个错误；严格 gate 返回 1，baseline gate 返回 0 并明确不可发布。`mem_a`、厂商 IP、FDC、RCF、FIFO、CDC/RDC 结构和时序例外均未修改。
- 下一步依次拆为 O2-A 只读联合释放契约、O2-B serializer 局部实现、O3-A 同步初始化状态、O2-C1 普通时钟域复位、O2-C2 FIFO reset/flush、O3-B 帧事件 CDC 与 O4 时序闭环。SP6.4 timing model 对同一 `RST` 同时建立 `OCLK`、`OCLKDIV`、`SERCLK` 的 recovery/removal 检查，因此 O2-A 必须先证明方案，不能预设“只同步到高速域”必然闭环；QuestaSim 未安装，不能声明 HDMI 动态复位或四级仿真通过。

## 2026-08-29：OV7725 O2-A Serializer Reset 联合释放契约

- 本批只新增契约和同步状态，不修改 RTL、厂商 IP、FDC、RCF 或 gate，也未运行新的 PDS/QuestaSim 流程。
- SP6.4 功能/timing model、PG2L100H 示例和当前 RTL 共同确认：OSERDES `RST` 高有效；同一端口相对 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 均有 recovery/removal 要求。
- 最终 STA 的 serializer 组为 Slow Recovery `-0.643 ns / -4.191 ns / 8/8`、Slow Removal `+0.305 ns / 0/8`、Fast Recovery `+0.123 ns / 0/8`、Fast Removal `+0.114 ns / 0/8`。
- Device-map 与 STA 已将 `serializer_b/g/r/clk` 各自 master=`opit_2`、slave=`opit_2_com` 的八个 `OSR_IOLHR` endpoint 唯一闭合。
- O2-A 当时把 O2-B 首选最小结构固定为：保留现有 `pixel_clk` 两级 reset 驱动 encoder，再级联现有两级同步器到 `pixel_clk_5x`，生成只驱动八个 OSERDES 的高有效 `serializer_reset`；该结构后来已由 O2-B 真实 STA 否决并回退。
- O2-B 必须由完整 PDS 同时证明八端点相对 `OCLK`、`SERCLK`、`OCLKDIV` 的 Slow/Fast Recovery 与 Removal 全部非负；若违例转移、需要 false path/waiver 或扩大到 PLL/IP/FDC/FIFO/业务 CDC，则回退并重新评审。
- 当前只能声明 O2-A 设计契约完成，不能声明 serializer reset、HDMI 动态复位或四级仿真已经通过。

## 2026-08-29：OV7725 O2-B 级联复位实验否决与回退

- O2-B 曾仅修改 `rtl/hdmi_top/dvi_transmitter_top.v`：保留 encoder 的 `pixel_clk` reset，再级联现有两级同步器到 `pixel_clk_5x`，生成只驱动四个 serializer、八个 OSERDES 的高有效 `serializer_reset`。
- 从空 `build/` 完成 compile 和七阶段流程，PDS 退出码均为 0，日志无 `E:`；compile warning 为 1101，与 O1-B 基线一致。完整实现 warning 4067、critical 81，五类关键产物均非零。
- 产物大小为：`ov7725_hdmi_syn.vm` 6,895,395 字节、`ov7725_hdmi_sim.v` 11,594,515 字节、`ov7725_hdmi_sta.sdf` 8,897,235 字节、`ov7725_hdmi.sbit` 3,791,112 字节、`ov7725_hdmi.bin` 3,789,476 字节。
- Slow Recovery 为 `pixel_clk_5x → pixel_clk_5x -0.349 ns / -1.599 ns / 8/8`、`pixel_clk → pixel_clk_5x +1.111 ns / 0/1`、`pixel_clk_5x → pixel_clk -2.173 ns / -16.191 ns / 8/8`。
- Fast Recovery 的同域组为 `+0.310 ns / 0/8`，单同步器组为 `+1.830 ns / 0/1`，但反向 `pixel_clk_5x → pixel_clk` 仍为 `-1.464 ns / -10.863 ns / 8/8`。Slow/Fast Removal 均为正，不能抵消 Recovery 失败。
- 八个反向 endpoint 正好是 `serializer_b/g/r/clk × opit_2/opit_2_com` 的 OSERDES `OCLKDIV` 检查；原 `pixel_clk → pixel_clk_5x` 失败没有被结构性关闭，而是转移并在慢角增加同域失败。
- O2-B 已按契约停止条件完整回退；未修改 `check_build.ps1`、baseline、FDC、RCF、PLL/IP，也未加入任何时序例外或 waiver。
- 下一批为 O2-D1 只读架构评审，比较显式释放相位 sequencer、统一复位控制器和厂商推荐结构；审核前不启动新的 serializer RTL。

## 2026-08-30：OV7725 O2-D1 统一拓扑中间评审

- 本批只读复核 SP6.4 `GTP_OSERDES_E2`、`V_OSERDES_E2`、`GTP_IOCLKDIV_E2`、`GTP_IOCLKBUF`、PG2L100H LVDS 示例、当前 PLL/RTL 和 O2-B STA；未修改 RTL、IP、PLL、FDC、RCF 或 gate，未运行 PDS/QuestaSim。
- timing model 对同一 `RST` 相对 `OCLK` 正负边沿、`OCLKDIV` 正边沿和 `SERCLK` 正边沿均建立 Recovery/Removal；O2-B 已证明普通级联同步器会把失败转移到 `pixel_clk_5x → pixel_clk`，固定等待周期不能改变固有相位预算。
- 同源高速时钟经 `GTP_IOCLKDIV_E2 /5` 生成整个 pixel 域是当前领先拓扑；当前 `pixel_clk` 同时驱动 DDR read FIFO 读侧、video driver/display、encoder 与 serializer，最终若采用该拓扑必须原子迁移。
- 进一步核对发现官方示例的 `tx_gate_en` 没有消费者，`GTP_IOCLKBUF` 使用默认 `GATE_EN="FALSE"`，且 400 MHz/50 MHz PLL 输出请求相位均为 0；示例没有证明停钟释放，也没有最终 STA 报告。
- 动态门控路线已否决：功能模型虽可无毛刺停启，但 SP6.4 Liberty 没有 `DI` clock-gating check，也不能证明停钟、复位、释放、启钟的顺序；仿真、endpoint 消失或 waiver 都不能替代八端点 STA。
- 唯一待验证候选为新增 `65.0026 MHz`、约 `+0.192 ns` 的 PLL 控制输出，并为每个 serializer 本地复制 reset 寄存器。按 O2-B 路径预算，reset 总数据延迟需压到约 `0.939 ns` 以下；纯相位调整不能通过。
- `/5` generated-clock、奇数分频 waveform、IOCLKBUF 前后取点、serializer hard reset 与业务 reset 分权均为 O2-D2 前置契约；FIFO 只迁移 `rd_clk`，reset/flush 仍留给 O2-C2。
- 当前 `build/` 已清空，下一步先重建已回退 RTL 的等价基线并判断 53/54 endpoint 漂移，再收口 O2-D1-G 并提请审核；当前仍不允许编码 O2-D2，工程继续不可发布。

## 2026-08-30：OV7725 O2-D1-R 回退基线重建

- 从空 `41_ov7725_hdmi/build/` 使用 PDS 2022.2-SP6.4 完成七阶段实现，进程退出 0、日志无 `^E:`，总耗时约 3 分 4 秒；本批未修改 RTL、IP、PLL、FDC、RCF、构建脚本或 gate。
- baseline gate 精确匹配原 7 组 `corner/check/clock pair/endpoints` 失败签名并返回 0；严格 gate 按预期返回 1，工程继续不可发布。
- 新最终报告中 Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均为 `53/53`，Removal 均为 `0/53`；Slow serializer Recovery 恢复为旧基线 `pixel_clk → pixel_clk_5x -0.643 ns / 8/8`。
- 完整详细路径的 53 个唯一 endpoint 分类为 read FIFO 控制 26、read FIFO RAM reset 8、video driver 17、video display 1、原 DVI reset 同步器 1。
- O2-B 的 `54` 来自 video-driver 物理 endpoint 增为 18；新增 `serializer_reset_syn/reset_1` 属于另一 clock pair。该漂移未在回退后保留，因此不修改旧 baseline，也不归为已修复问题。
- 五类产物大小与既有基线一致：综合网表 6,873,482、PNR 网表 11,604,756、SDF 8,898,464、`.sbit` 3,791,112、`.bin` 3,789,476 字节。
- O2-D1-R 完成；下一批只收口 O2-D1-G generated-clock、状态/计数、复位分权、warm-up 和一次性停止条件，审核前不修改功能设计。

## 2026-08-30：OV7725 O2-D1-G 实现前契约收口

- 本批仅更新 `SERIALIZER_RESET_CONTRACT.md`、根 `TODO.md`、OV7725 README 和知识图，不修改 RTL、PLL/IP、FDC、RCF、构建脚本、gate 或 `build/`，也未声明 QuestaSim 可用。
- 唯一 pixel 时钟拓扑冻结为：PLL `u_pll_clk/clkout1` 同时进入唯一 `GTP_IOCLKBUF` 和唯一 `GTP_IOCLKDIV_E2(DIV_FACTOR="5")`；divider 取 pre-buffer 点，`pixel_clk` generated-clock 仅允许一条显式对象，waveform 固定 `-edges {1 5 11} -edge_shift {0 0 0}`。`-divide_by 5`、post-buffer 取点和自动/显式重名均触发回退。
- 控制状态冻结为 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN`；`QUALIFY=4`、`ENCODER_WARMUP=3`、`SERIALIZER_FILL=2`，counter 表示已完成完整周期且饱和不回卷。`sys_rst_n/pll_lock` 负责异步 hard reset，video/business reset 与四路本地 serializer reset 分权；`ddr3_init_done` 不进入控制器状态或 OSERDES reset。
- ARM/SER_RELEASE 期间 encoder 输入强制 `de=0,c0=0,c1=0,din=0`；首个有效 TMDS symbol 定义为四 lane 同时确定的完整并行字，RUN 至少延后两个 control 周期以覆盖未复位 encoder 流水。
- O2-D2 只允许一次实现试验：IP Compiler 重生成 PLL，新增项目自有控制器并原子迁移 read FIFO `rd_clk` 与完整 pixel 域。任何 generated-clock/endpoint/Recovery/Removal/覆盖、warning、baseline、CDC 或 SDF 停止条件触发即完整回退，不扫描第二相位、不增加 waiver。
- O2-D1-G 文档收口完成，等待用户审核；审核前不得进入 O2-D2 编码。

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

- 总 TODO 已同步标记 S0-0、DDR3 D3-0 和 PCIe H2-A 为已完成的只读/环境复核；对应的安装、D3-A、H2-B 和 OV7725 O2-D2 仍保持未完成并受外部资料或用户审核约束。
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

- 新增 `docs/SIMULATION_READINESS_MATRIX.md`，记录 OV7725 HDMI、DDR3 和 PCIe DMA 三个项目的项目级 TB、filelist、DO、厂商示例资产、路径可移植性和四级仿真缺口。
- 盘点结论：三个项目均没有项目级集成 testbench 或四级仿真入口；现有 `tb`、`.f`、`.do` 面向 Pango 厂商 IP 示例，不能作为项目验收。
- OV7725 现有 DDR3/PLL/FIFO 示例不覆盖 `ov7725_hdmi`；DDR3 现有 `test_ddr` 示例 TB 与计划项目 BIST/top 不同且端口已失配；PCIe 现有 `pango_pcie_top_tb` 不实例化 `pcie_dma_test`。
- 三项目厂商仿真脚本或 filelist 含历史绝对路径/工作目录假设；本批不修改厂商生成文件，后续新增项目级相对路径入口。
- S0-1 仍因本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断；本批只做静态盘点和 TODO 排序，未运行 ModelSim/QuestaSim、PDS 或 SDF 仿真。

## 2026-08-30：CI-1 仿真矩阵引用门禁

- 扩展 `scripts/check_repo_consistency.ps1`，要求仿真就绪度矩阵存在，并包含 OV7725、DDR3、PCIe 和 S1/S2/S3 执行队列。
- 门禁同时验证根 `README.md` 与 `TODO.md` 均链接 `docs/SIMULATION_READINESS_MATRIX.md`，防止规划文档脱离入口指南。
- PowerShell AST、仓库一致性门禁和 `git diff --check` 均通过；本批未运行 PDS、ModelSim/QuestaSim 或 SDF，也未修改 RTL/IP/约束/生成物。

## 2026-08-30：PCIe H2-B 静态元数据 gate

- `pcie_dma_test_100h/scripts/check_build.ps1` 现在直接解析活动 `ipcore/pcie_test/pcie_test.idf`，校验 family、device、package 和 speedgrade 是否为 `Logos2/PG2L100H/FBG484/-6`。
- 元数据不一致会进入已知问题集合：显式 `-AllowKnownBaselineIssues` 可复现当前基线，严格模式必定失败；旧的日志重复匹配已移除。
- 本批仅修改 gate、TODO 和实现记录；未修改 PCIe RTL、IDF、FDC、厂商 IP 或生成物。

## 2026-08-30：H0/H1/H3 板级证据清单准备

- 新增 `41_ov7725_hdmi/doc/BOARD_EVIDENCE.md` 与 `ddr3_test/ddr3_test/doc/BOARD_EVIDENCE.md`，分别记录当前工程事实、证据来源、用户需提供的板级字段和关闭条件。
- 清单覆盖 FPGA/板卡身份、DDR3 颗粒与拓扑、`mem_a[14]` 分支、时钟/复位、bank 电压、share pin、OV7725 输入格式和 HDMI 模式。
- 本批只新增文档并更新 TODO；未修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物。资料缺失仍保持 H0/H1/H3 阻断。
- 只读复核进一步确认 OV7725 活动 `ddr3_ip.idf` 的 `MEM_ADDR_WIDTH`、`DDR3_MEM_ROW_WIDTH`、`MEM_ROW_WIDTH` 均为 14，手写顶层/FDC 仍为 15 位，并发现该 IDF 生成器版本为 SP4.2；该冲突和版本差异已写入证据清单，不能依据 FDC 单独收窄。

## 2026-08-30：CI-2 板级证据清单完整性门禁

- 仓库级一致性脚本现检查 OV7725、DDR3、PCIe 三份板级证据清单是否存在，并要求统一的“当前工程事实”“必须提供的资料”“关闭条件”章节。
- 同时检查每个项目 README 是否链接对应清单，以及清单是否包含项目关键词；门禁只验证结构和入口，不把模板或待提供字段当作已确认硬件事实。
- 本批未修改 RTL、厂商 IP、IDF、FDC、RCF 或生成物；H0/H1/H2/H3 的资料阻断保持不变。

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

## 2026-08-30：三项目实际 PG2L50H 目标审核与迁移规划

- 用户确认 DDR3、PCIe、OV7725 HDMI 三个项目最终运行在同一块 `RK3568+PG2L50H100H` 开发板，实际焊接 FPGA 为 `PG2L50H-6IFBG484`；PDS 目标统一为 `Logos2/PG2L50H/FBG484/-6`，并批准按 PCIe → DDR3 → OV7725 分批迁移。
- 既有 PG2L100H compile/PNR/STA、网表、SDF、`.sbit` 和 `.bin` 全部降级为历史证据，不得用于实际板卡验收或烧录。
- PCIe 活动 `pcie_test.idf` 已由 SP6.4 生成为 PG2L50H，配置方向正确；原 build/gate 强制 PG2L100H 才是错误项。下一批只修正工程目标和器件交叉 gate，再从空 `build/` 重建，不为型号重复生成 PCIe IP。
- DDR3 活动 IDF/FDC 为 PG2L100H；SP6.1 的 PG2L50H backup 与活动配置参数高度一致，但 PHY slice 和硬宏位置存在器件差异，只能作参数/差异依据。必须用本机 SP6.4 重生成 50H controller/PHY、FDC/RCF 和仿真资产，再重跑 CI-6；器件迁移批准不等同于 D3-A 编码授权。
- OV7725 的 DDR3、PLL、读 FIFO、写 FIFO 四个活动 IDF 均为 SP4.2 PG2L100H 生成物，旧 backup 是 PGL25G 而非 50H。实际 DDR3 组织和管脚闭合后，四个 IP 都必须在 SP6.4/PG2L50H 下重生成。
- O2-D1-G 的状态机、hard/business reset 分权、唯一 `/5` clock、八端点覆盖和禁止 waiver/第二相位等纪律继续有效；100H 的 `+0.192 ns` 裕量、七组时序指纹和 endpoint 数不再是 50H 验收证据，O2-D2 暂停到新基线后重新审核。
- 本批只更新规划、README、板级证据和契约状态；未修改 RTL、厂商 IP、IDF、FDC、RCF、构建脚本或生成物。

## 2026-08-30：PCIe M1 PG2L50H 首批迁移

- 将 `pcie_dma_test_100h/scripts/build.tcl` 的 PDS 目标改为 `Logos2 / PG2L50H / FBG484 / -6`，并把 `check_build.ps1` 的器件期望改为 PG2L50H。
- 门禁新增三方器件交叉校验：PDS 构建日志的 `set_arch`、最终 timing report 的 `Device` 字段、`generate_bitstream/bgr.db` 的 `PG2L50H-6FBG484`；发现陈旧 PG2L100H 即失败。
- 首次 50H 完整构建暴露旧 FDC 的 `HSSTLP_364_918` 资源名无效；依据 PDS 2022.2-SP6.4 官方 HSSTLP PG2L50H 模板，将 x2 lane/PLL0 迁移到 `HSSTLP_292_612`。未修改 lane 逻辑、管脚或电气属性。
- 从空 `build/` 完成 `compile → synthesize → dev_map → pnr → report_timing → gen_netlist → gen_bit_stream`，PDS 退出码为 0，日志无 `E:`，生成非零网表、慢角 SDF、`.sbit` 和 `.bin`。
- 新 50H timing report 为 `All Constraints Met`，门禁解析的最差 slack 为 `0.100 ns`；资源约为 3779 LUT、4279 FF、40.5 DRM、6 个顶层 I/O。
- 严格 `check_build.ps1` 返回非零并精确报告 UART RX 死通道、未约束顶层 I/O、PCIe 串行 I/O 约束缺口、M15/M16 share pin 和 SCBV 未配置。显式 baseline 放行返回 0，但明确标记不可发布。
- 本批未运行 ModelSim/QuestaSim；S0-1 仍因本机缺少 `vsim.exe`、`vlog.exe`、`vlib.exe` 阻断。

## 2026-08-30：PCIe H2-B0 精确 baseline 指纹门禁

- 复验当前 PG2L50H 构建：baseline gate 返回 0 并明确不可发布，strict gate 返回 1；IDF、build log、timing report 与 `bgr.db` 均匹配 `Logos2/PG2L50H/FBG484/-6`。
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
- 最终 PG2L50H 七阶段构建返回 0，manifest 为 complete/valid、43 输入/7 证据；baseline=0、strict=1、最差解析 slack `0.100 ns`，16/42 H2-B0 指纹和 H2-B1 五类阻断保持不变。
- 本批未修改 RTL、活动 IDF、FDC 或厂商 IP；DDR3/OV7725 的 CI-8B 迁移继续等待各自 PG2L50H canonical 输入和最终构建入口闭合。

## 2026-08-31：PCIe S2-A 项目级行为 smoke 入口

- 新增项目自有 `tb_pcie_dma_test.sv`，实例化真实 `pcie_dma_test` 顶层；按 VSCS 记录职责、时钟/复位假设、验证边界和失败语义。
- 新增受控 `pcie_test` 边界模型，只提供确定性的 refclk/pclk、core reset、idle 接口和延迟 link 激励；明确不验证 LTSSM、TLP、DMA、lane/refclk 电气或板级时序。
- 新增 `sim/behav.f`，嵌套复用 37 个 HDL 的 canonical `scripts/pds_sources.f`，仅追加两个真实 reset helper、受控模型和项目 TB；不维护第二份 RTL 清单。
- 新增 `scripts/run_behav.do` 与 `scripts/check_sim.ps1`。DO 使用相对路径、独立 work、USIM 和 transcript；静态门禁检查 filelist 顺序、路径、模型端口、DUT/TB/DO 契约。
- `run.ps1 -Action sim-behav` 现在生成唯一 `SIM_RUN_ID`，动态成功必须在同一日志中包含匹配 run marker 和唯一 `TEST PASS`。
- S2 后续拆为 S2-B 真实厂商 RC/EP LTSSM/link-up 和 S2-C 基础 DMA 回读；S2-A model-controlled link 不得冒充两者。
- `run.ps1` 属于 CI-8A canonical 输入，因此 S2-A 入口变更后旧 manifest 被正确拒绝；重新执行七阶段 PG2L50H 构建，run id `c24bc06b5d0643eeb6c9cb2878e7ace5` 返回 0，manifest 为 complete/valid、43 输入/7 证据，baseline=0、strict=1、最差解析 slack `0.100 ns`。
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
- owner 将摄像头产品目标校正为 OV5640；现有 `41_ov7725_hdmi`、O0/O1/O2/M3-A 和对应 STA/CDC/RDC 证据保留为 OV7725 legacy，不改名冒充新项目。
- 新增 `docs/OV5640_TARGET_SCOPE.md`，将参考工程只读导入、单/双摄与模组接口冻结、项目边界、PG2L50H 迁移和四级 Questa 验证拆为 C0/C1/C2/C3/S3。
- 本机复核确认 Questa Sim-64 `2021.1` 的 `vsim`、`vlog` 和 `vlib` 可执行文件位于安装根的 `win64` 子目录；tracked 文档不记录本机安装或许可证实际路径。
- PCIe S2-A/S2-B 静态门禁和环境检查通过；当前 S2-A 动态启动因外部许可证 checkout 失败返回 4，没有生成新的 `TEST PASS`。历史 run id 的通过证据继续保留，但不作为本次复验结果。
- 发现历史 PDS 日志中存在许可证绝对路径；当前版本统一替换为 `<license-path>`，并将 CI-9 扩展为当前树全量扫描和 PR 新增差异扫描。历史 `.log` 标记为 `-diff`，避免 PR 页面展开旧路径；该修复不改写 Git 历史。

## 2026-09-01：PCIe S2-A RX halt 端口 hygiene

- 发现 `u_ips2l_pcie_dma.o_trgt1_radm_pkt_halt` 是 DMA RX 队列的 3-bit halt 请求：bit0 由 tag full 驱动，bit1 由 completion transmit ready 反相驱动，bit2 当前为 0。原顶层未连接，且生成 wrapper 将 hard-IP 输入固定为 `3'b0`。
- 独立审计确认 AXI ready 不是该 RX 资源流控的替代路径；把输出标成 unused 只会隐藏高流量下的 tag/完成队列风险。
- 本批在项目顶层贯通 DMA 输出，为活动 `pcie_test` wrapper 增加输入并删除内部 tie-off，保留已有 hard-IP `i_trgt1_radm_pkt_halt` 连接。不修改 DMA 内部、example design、IDF 或 PDS 源清单。
- S2-A 静态门禁现检查唯一 producer/consumer、wrapper 输入、hard-IP 连接、tie-off 消失、仿真替身端口和重生成风险注释。真实高流量下的流控闭环仍由 S2-B/S2-C 验证。
- Questa Sim-64 `2021.1` 当前复验 run id `966942334060436dba8444ae9155557c` 编译 `0 errors/0 warnings`，elaboration 成功，运行到 `1476105 ns`，唯一 `TEST PASS`，PowerShell 退出 0。
- PDS run id `50b37eb3628e419592cecac02ff932bf` 完成 PG2L50H 七阶段，provenance=`complete/valid`，baseline/strict gate=`0/1`，最差 slack `0.100 ns`，网表/SDF/位流均为非零。原两条未连接端口 warning 消失；bit2 恒 0 的 2 条优化/清理 warning 保留。

## 2026-09-01：三项目 Questa 工程归档

- 三个项目均建立项目内 `sim/questa/` 目录，归档项目自有的 Questa 工程定义；不提交仿真器二进制 `work` 库、transcript、日志、波形、安装位置或许可证配置。
- PCIe 的 S2-A/S2-B `.f/.do` 从分散的 `sim/` 与 `scripts/` 迁入 `pcie_dma_test_100h/sim/questa/`，`scripts/run.ps1` 和两项静态 gate 改为只认新位置，避免双份 filelist 漂移。
- DDR3 与摄像头目录目前只记录厂商 IP 示例边界和项目级入口缺口：厂商 `sim/modelsim` 资产不计作项目集成仿真；DDR3 等待 D3 canonical 闭环，摄像头等待 OV5640 C0/C1/C2/C3 后再补四级入口。
- 迁移后使用 Questa Sim-64 `2021.1` 从新入口复验 S2-A；run `26db7d3206c542218634caff2c6e71ea` 编译 0 errors/0 warnings，运行至 `1476105 ns`，唯一 `TEST PASS`，PowerShell 退出 0。
- 后续审核明确要求仿真工程完整留在各自项目内：新增 `scripts/check_sim_archives.ps1`，将 PCIe 的三个既有项目自有 SV 仿真源收拢到 `sim/questa/tb/`，并把该检查纳入根仓库门禁。
- 结构门禁拒绝归档目录中的 `.mpf`、`work`、`modelsim.ini`、transcript、日志和波形；`.gitignore` 同步覆盖常见 Questa 工程运行态扩展名。
- 收拢后复验 S2-A run `517c1897a6dd433bb3c5cfc84acd0ba9`：编译 `0 errors/0 warnings`、运行至 `1476105 ns`、唯一 PASS、退出 0；S2-B run `6a7817195de44fc6b1ab55a16f073e31`：运行至 `702175 ns`、唯一 link marker/PASS、`Errors: 0, Warnings: 26`、退出 0。
- S2-C 下一小批冻结 `S2C_BAR1_REGENERATION.md` 和 `check_s2c_bar1.ps1`：活动 BAR1 仍为禁用事实，只有 PDS IP Compiler staging、完整参数/资产差异审核和原子升格后才允许进入 Endpoint 主动 DMA 动态闭环。
- 已确认 SP6.4 `ip_generate.exe` 的现有实例 CLI；新增 `regenerate_bar1_staging.ps1`，只把 BAR1 启用/512 Bytes 改动写入 `build/ipgen/pcie_bar1/`，默认不执行生成，避免覆盖 canonical IP。

## 2026-09-01：PCIe S2-B 动态入口推进

- 修正厂商模型在切换工作目录后仍使用逻辑库名的问题，所有加密 DWC/HSST/GTP 模型改写入每个 run 独立的物理 `pcie_vendor` 库；原 55 个未定义 Pango 原语错误消失。
- 项目 TB 按厂商 RAM 模型契约使用唯一顶层 `GRS_INST.GRSNET`，并沿用厂商 PCIe DO 的 `1ns/10ps` 编译时间尺度；原 48 个 GRS 层级错误和两个 `vsim-3009` 时间尺度错误消失。
- 中间 run `9e0fae4e1d6d4ef7959cd98308b1e0f0` 记录首次 L0 后第 10 个周期 RC 进入 `0x0d`、EP 保持 `0x11`；厂商示例同样在首次 link-up 后等待速率切换再检查 L0，证明旧 TB 错把合法重训练当成永久掉链。
- 按 TDD 增加“连续稳定周期累计、重训练时计数清零”静态契约，再将 TB 改为在 6 ms 总窗口内寻找连续 32 周期双端 link-up/L0；没有缩短窗口、抑制错误或放宽 PASS 条件。
- 最终 Questa Sim-64 `2021.1` run `dc461d6d3970409185f8f1fb3dd417d6` 在 `702175 ns` 输出唯一 `INFO: S2B_REAL_LINK_UP` 和唯一 `TEST PASS`，`Errors: 0, Warnings: 26`，PowerShell 退出 0。warning 来自厂商/生成模型端口与受保护模型，不改写为零 warning。
- `run_link.do` 的 run marker 使用可进入 transcript 的 `echo`。运行生成的库、日志和 transcript 仍只位于 `build/`，不进入 Git；S2-B 通过不扩张为 DMA、RK3568 实板、协商宽度/速率或板级电气通过。
- 归档边界复验发现 Questa 会在启动目录创建 transcript，且 `vmap` 会在当前目录复制 `modelsim.ini`。`run.ps1` 现为每个 run 在 `build/sim/launcher/<run-id>/` 创建并显式绑定 ini，通过进程内 `SIM_PROJECT_ROOT` 执行项目 DO；静态合同锁定该边界。
- 最新 S2-A run `add7efa39f644384af9929e8a9366739` 为 0 errors/0 warnings、`1476105 ns`、唯一 PASS、退出 0；最新 S2-B run `30bad6e164be4a4b8284a00f1e96bd87` 为 0 errors/26 warnings、`702175 ns`、唯一 link marker/PASS、退出 0。两次运行后工程根 ini/transcript/波形计数为 0。
- `run.ps1` 属于 CI-8A canonical 输入，因此归档边界修正后重新执行完整 PG2L50H 七阶段。PDS run `dde6ee70b2c84d2da4ee2256d8a5c127` 退出 0，manifest=`complete/valid`、43 输入/7 证据，baseline/strict gate=`0/1`、最差 slack `0.100 ns`；五类 strict 发布阻断保持不变。
