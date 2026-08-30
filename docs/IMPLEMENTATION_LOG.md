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
