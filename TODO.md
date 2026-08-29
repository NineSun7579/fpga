# 三项目整改 TODO

更新日期：2026-08-29

状态：实施中。PCIe 可重复构建基线已完成；DDR3 compile-only 基线已提交；当前进入 DDR3 完整实现与严格 gate；OV7725 尚未开始整改。

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
- [ ] OV7725 建立 SP6.4 可重复构建基线并开始 CDC/RDC 整改。
- [ ] 安装 QuestaSim/ModelSim，编译 Logos2 USIM/VSIM 并完成三项目四级仿真。

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

### D1：DDR3 完整实现与严格 gate（当前批次）

依赖 D0；仍不宣称发布候选。

- [ ] 为 DDR3 新增独立 `scripts/check_build.ps1`。
- [ ] gate 检查 PDS `E:`、阶段完成标志、100H 器件、时序摘要和非零产物。
- [ ] gate 将 UART、未约束关键 I/O、share pin、SCBV/板级参数和 BIST 位宽问题视为严格阻断。
- [ ] 允许显式 baseline 模式验证历史设计可重复实现，但输出必须标记“不可发布”。
- [ ] 分阶段执行 synthesize、dev_map、PNR、report_timing、gen_netlist 和 bitstream。
- [ ] 记录新构建的 WNS、TNS、hold/recovery/removal、资源和 constraint warning。
- [ ] 确认综合网表、PNR 网表、SDF、`.sbit`、`.bin` 均存在且非零。
- [ ] 验证 baseline gate 通过、严格 gate 对未关闭项返回非零。
- [ ] 同步 README、实现日志、`.nexus-map` 后独立提交。

验收：完整 PDS 流程可重复执行，内部时序和产物检查有机器可判定结果；未获板级确认的问题仍被严格 gate 拦截。

### D2：定义 DDR3 有限自检契约

该批先做设计评审，不要求 QuestaSim 已安装。

- [ ] 确定有限事务数、地址范围、数据模式、最大完成时间和错误统计语义。
- [ ] 决定采用“修改 bring-up BIST 暴露 done/error”还是“建立更小的专用 AXI 测试顶层”。
- [ ] 明确初始化、写、读回、比较、完成和失败的状态机契约。
- [ ] 禁止把 `bist_run_led` 或 `err_flag_led` 直接解释为测试完成。
- [ ] 修正现有 TB 与当前 `test_ddr` 的五个端口失配。
- [ ] 移除 FSDB/Verdi PLI 和 `D:/pango` 等机器路径依赖。
- [ ] 新 TB 必须有超时、training/BIST error 的 `$fatal` 和唯一 `TEST PASS`。

验收：TB 设计无需猜测即可实现，done/error 有稳定、可观察、可自动判定的协议。

### O0：OV7725 CDC/RDC 清单与 SP6.4 构建基线

依赖 D1 完成后开始；本批不修改功能 RTL。

- [ ] 建立 CDC/RDC 表，覆盖 `sys_clk`、`cam_pclk`、`pixel_clk`、`pixel_clk_5x` 和 DDR `ui_clk`。
- [ ] 每条跨域记录源域、目标域、信号类型、协议、事件频率、复位行为和验证方法。
- [ ] 明确 `wr_load`、`rd_load`、`ddr3_init_done`、`capture_start` 和两个异步 FIFO 的跨域关系。
- [ ] 新建相对路径 `scripts/build.tcl`、PowerShell 入口和产物/日志检查器。
- [ ] 显式固定 `Logos2 / PG2L100H / FBG484 / -6`、15 个业务 RTL、4 个 IP 和唯一 FDC。
- [ ] 禁止依赖包含旧器件和失效绝对路径的 `prj/impl.tcl`。
- [ ] 在干净 `build/` 中完成 SP6.4 compile 基线，并记录全部 warning。
- [ ] 不修改 RTL 的前提下尝试完整实现，固化旧 WNS/TNS/recovery 基线和非零产物状态。

验收：所有工程输入可追溯，构建入口可重复；CDC/RDC 决策先于时序例外。

### O1：OV7725 RTL 卫生修复

- [ ] 显式声明 `rst_n`、`sys_init_done` 等隐式 net。
- [ ] 按端口宽度书写所有常量，消除顶层地址、burst 和 serializer RST 位宽警告。
- [ ] 核对顶层 `mem_a` 宽度与 DDR IP 配置。
- [ ] 使 `serializer_10_to_1.reset_n` 真正控制 OSERDES，或经设计评审删除无效输入。
- [ ] 不在本批修改 CDC 结构或时序约束。

验收：compile 不再报告上述手写 RTL 的隐式网络和端口位宽问题；接口宽度与 IDF/template 一致。

### O2：OV7725 分时钟域复位

- [ ] 为 sys、camera、pixel、DDR UI 时钟域分别建立异步置位、同步释放复位。
- [ ] `ddr3_init_done` 只作为同步后的状态/使能，不再直接参与其他域异步复位释放。
- [ ] FIFO 两侧复位分别在各自读写时钟域释放。
- [ ] 消除复位重汇聚和组合异步释放。
- [ ] 新增或修改的手写 RTL 按 VSCS 记录 RDC 契约和验证证据。

验收：RTL 中不存在跨域状态直接接异步复位脚；后续 STA recovery/removal 全部非负。

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

### H1：DDR3 板级参数

- [ ] 提供 DDR3 完整料号、数量、容量、rank、x16/x32 组织和目标速率。
- [ ] 核对 A/BA/CK/DQ/DQS/DM byte-lane 映射及 bit/byte swap。
- [ ] 确认 `free_clk` 频率、电气标准、精度和 `rst_board` 极性。
- [ ] 提供 VCCIO/VREF、ODT、终端、拓扑和 PCB 走线时延依据。
- [ ] 决定 UART/ADC 是否保留；若保留，提供管脚、电压和波特率。

### H2：PCIe 板级参数与严格 gate

- [ ] 确认 PCIe x2 lane 映射/极性、100 MHz refclk、PERST# 和 M15/M16 share pin。
- [ ] 决定 UART2APB 保留或删除；保留则提供 RX/TX 管脚、电气标准和波特率。
- [ ] 提供 SCBV 所需配置 bank 电压。
- [ ] 确认 LED 属于人眼状态灯且无外部同步时序要求，或提供正式时序要求。
- [ ] 用 SP6.4 IP Compiler 为 PG2L100H 重生成 PCIe IP，消除 50H/100H IDF 不一致。
- [ ] 按决策处理 UART，消除无驱动 `rxd` 和隐式网络。
- [ ] 为 HSST/refclk/lane/share pin 建立有官方模板和原理图依据的精确约束或 waiver。
- [ ] 完整重建并使 `check_build.ps1` 不带 baseline 放行参数返回 0。

### H3：OV7725/HDMI 板级参数

- [ ] 确认 OV7725 输入格式、RGB565 字节序、分辨率、帧率和像素时钟范围。
- [ ] 确认 HDMI 输出模式及外部时序要求。
- [ ] 核对 DDR3 型号、32-bit 配置、800 MT/s 和 PCB 拓扑。
- [ ] 依据传感器和 PCB 数据补 `cam_pclk` input delay。
- [ ] 复核 `PAP_CLOCK_DEDICATED_ROUTE FALSE`、TMDS/DDR/share pin 和 I/O 电压。

## 6. 仿真器阻断泳道

### S0：公共仿真环境

- [ ] 安装 ModelSim/QuestaSim，记录 `vsim.exe`、`vlog.exe` 的实际目录和版本。
- [ ] 编译 Logos2 USIM/VSIM 到仓库根 `build/simlib/`。
- [ ] 将仿真器安装路径作为可覆盖外部参数，不写入工程源清单。

### S1：DDR3 四级仿真

依赖 D1、D2、S0。

- [ ] 行为级自检通过。
- [ ] 综合后自检通过。
- [ ] PNR 后功能自检通过。
- [ ] PNR 后时序自检通过且 SDF 层级正确。

### S2：PCIe 集成仿真

依赖 H2、S0。

- [ ] 新建 `tb_pcie_dma_test.sv`，先覆盖复位、链路建立和超时 smoke。
- [ ] 新建可移植 filelist 和行为级 DO，不改厂商示例 TB。
- [ ] 单独增加一次可预测的基础 DMA 写读回。
- [ ] 再完成综合后、PNR 功能和 PNR 时序仿真。
- [ ] 每级成功只输出一个 `TEST PASS`，失败或超时返回非零。

### S3：OV7725 集成仿真

依赖 O4、H3、S0。

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

- [ ] 修改范围单一，可独立说明和回退。
- [ ] 新增 RTL/TB、Tcl、DO 和 PowerShell 包含必要注释与阶段日志。
- [ ] 不新增工程内绝对路径、隐式 net 或仅打印但不失败的错误处理。
- [ ] 对应最低级别测试已通过；不能运行的测试明确记录阻断原因。
- [ ] README、实现日志、`.nexus-map` 和 TODO 状态同步。
- [ ] `git diff --check`、PowerShell 语法和 JSON 检查通过。
- [ ] 不提交 `build/`、transcript、临时库或其他工具生成物。
