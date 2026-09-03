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
- 该层不实例化 DDR3 IP；实际用户口接入必须等待 PG2L50H IP 重生成及 D3-0-M 复核。

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

## 2026-09-03：main PG2L50H canonical MWR32 TX 语义修复

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
