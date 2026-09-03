> generated_by: Codex manual bootstrap
> verified_at: 2026-09-03
> provenance: existing PDS logs/reports, simulation runs, artifact gates, CI-9 self-tests and real-branch sensitive-diff scan

# Test Coverage

## 证据等级

- 已验证：当前文件或报告直接证明。
- 静态发现：源码、工程配置或日志可直接观察，但本轮没有重新运行工具。
- 未验证：缺少可执行资产、工具环境或运行记录。

## S0 环境与仿真库验证（截至 2026-09-01）

- 历史证据：2026-08-30 环境复核未发现仿真器；该结论已被后续实际执行证据取代。
- 已验证：S0-1 参数化入口 `scripts/compile_simlib.tcl` 与 `scripts/compile_simlib.ps1` 已提交；PowerShell AST 错误数为 0。入口支持 ModelSim/QuestaSim、USIM/VSIM/BOTH、family、语言、PDS/仿真器路径和输出目录覆盖，强制检查三项仿真器可执行文件，并检查 PDS 退出码、日志 `^E:` 与所选库目录。
- 已验证：Questa Sim-64 2021.1 最小 SystemVerilog 通过；PDS SP6.4 Logos2 USIM/VSIM 均编译成功。VSIM 编译入口退出 0、日志无 `^E:`、`vsim` 目录非空。
- 已验证：最小后级原语 smoke 从 VSIM 库加载 `V_BUF`，运行 `2 ns`，Errors 0/Warnings 0、唯一 `TEST PASS`。
- 当前复验：S2-A/S2-B 静态门禁通过；S2-A 动态启动因仓库外许可证 checkout 失败返回 4，未产生新的 run marker 或 `TEST PASS`。历史 S2-A PASS 继续保留，但不得冒充当前复验。
- 未验证：三个项目的综合后、PNR 功能、PNR 时序和 SDF 标注；公共 S0-1 完成不等于项目后级仿真通过。

## CI-0 仓库级静态一致性门禁（2026-08-30）

- 已验证：新增 `scripts/check_repo_consistency.ps1`，覆盖根指南/TODO/VSCS、三个项目 README、PDS 构建入口、顶层声明、七阶段命令、可配置工具路径、退出码、baseline 开关、产物/时序检查接口和 `build/` 忽略状态。
- 已验证：三个项目 README 的 PDS `2022.2-SP6.4`、顶层模块或仿真状态缺口已修正；门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 已验证：仓库内全部 7 个 PowerShell 脚本 AST 解析错误数为 0。
- 边界：CI-0 不启动 PDS 或 ModelSim/QuestaSim，不替代项目严格 gate、STA 或四级仿真。

## CI-2 板级证据清单完整性门禁（2026-08-30）

- 已验证：提交 `677808d` 将三项目板级证据清单路径和项目关键词加入 `scripts/check_repo_consistency.ps1`，并要求各项目 README 直接链接对应清单。
- 已验证：OV7725、DDR3、PCIe 清单均包含“当前工程事实”“必须提供的资料”“关闭条件”；PCIe 清单已统一章节名称和结构。
- 已验证：HEAD `677808d` 上仓库一致性门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 边界：CI-2 只证明清单结构、关键词和 README 链接完整，不证明清单中的板级资料已提交、审核或与实物一致。

## CI-3 项目 README 元数据完整性门禁（2026-08-30）

- 已验证：提交 `5bfaae9` 扩展 `scripts/check_repo_consistency.ps1`，对 OV7725、DDR3、PCIe 三个项目 README 统一检查器件目标、顶层、时钟、主要接口、构建入口、IP/IDF 来源和当前阻断七类元数据。
- 已验证：当前 HEAD `5bfaae9` 上仓库一致性门禁退出码为 0，并输出 `INFO: repository consistency gate passed`。
- 边界：CI-3 仅检查 README 中已有事实的可追溯表达和入口特征，不验证器件/板级参数是否真实或已审核，不替代 PDS、STA、SCBV、板级证据或四级仿真。

## CI-4 PDS 构建 gate 契约完整性门禁（2026-08-30）

- 已验证：提交 `66356aa` 扩展 `scripts/check_repo_consistency.ps1`，对三个项目 `run.ps1` 检查 PDS 进程退出码、`^E:` 错误记录和阶段完成处理。
- 已验证：同一门禁对三个项目 `check_build.ps1` 检查阶段或最终构建入口、时序摘要解析/结论、`throw` 失败路径、非零产物检查及 `AllowKnownBaselineIssues` 显式开关；当前 HEAD `66356aa`、44 个 Git 提交上门禁退出码为 0。
- 边界：CI-4 只验证 gate 代码路径存在和静态契约，不执行真实 PDS、STA、位流或仿真；baseline 放行仍明确不可发布。

## CI-5 PowerShell AST 语法门禁（2026-08-30）

- 已验证：提交 `5769d8f` 扩展 `scripts/check_repo_consistency.ps1`，自动递归解析全部非 `build/`、`.git/` 的 `.ps1` 文件，并报告具体语法错误文件、行号和消息。
- 已验证：当前 HEAD `5769d8f` 共扫描 8 个 PowerShell 脚本，AST 解析错误数为 0，仓库一致性门禁通过。
- 边界：CI-5 只证明 PowerShell 语法可解析，不执行或替代 PDS、STA、位流生成、ModelSim/QuestaSim 或项目动态仿真。

## CI-6 DDR3 D3-0-R 契约一致性门禁（2026-08-30）

- 已验证：提交 `a5d1785` 扩展 `scripts/check_repo_consistency.ps1`，交叉读取 `ddr3.v`、`test_ddr.v` 与 `D3A_PORT_MAP.md`。
- 已验证：门禁检查模块/参数声明、128-bit 数据和 28-bit 地址证据、`I_ips_ddr_top` 层级、AXI-like 握手字段，并在 core 出现 `axi_rready` 时失败；HEAD `a5d1785`、52 个 Git 提交上门禁和 8 个 PowerShell AST 均通过。
- 边界：CI-6 只保护旧活动 DDR3 IP 的静态契约；PG2L50H IP/FDC/RCF 重生成后必须重新核对并审核，不能替代 compile、STA 或动态仿真。

## CI-7 PDS Tcl 入口分类门禁（2026-08-30）

- 已验证：`docs/PDS_TCL_ENTRYPOINT_INVENTORY.json` 登记全部 13 个 tracked Tcl，并记录六类角色、`set_arch` 次数、器件集合、绝对路径和 `run_ps1_entry`。
- 已验证：只有三个项目 `scripts/build.tcl` 由 `run.ps1` 调用；PCIe 为 PG2L50H canonical，OV7725/DDR3 仍为 PG2L100H migration-blocked。
- 已验证：正向门禁退出码为 0；删除任一清单条目的负向测试退出码为 1。历史 GUI、厂商内部和厂商仿真 Tcl 不得用于器件身份、STA、网表、SDF、位流或集成仿真通过证明。
- 边界：CI-7 仅验证 tracked Tcl 分类和入口事实，不执行 PDS、IP Compiler、STA、位流或 ModelSim/QuestaSim。

## PCIe H2-B0 精确 baseline（2026-08-30）

- 已验证：五类已知问题归一化为 16 个唯一签名、42 次原始记录；baseline 按完整多重集比较，签名新增、消失、改名、share-pin 位置变化或次数漂移均失败。
- 已验证：活动 PCIe IDF 的 family/device/package/speedgrade metadata 漂移为永久硬失败，不受 baseline 放行参数影响；canonical fixture 正向退出 0、strict 退出 1，5 个变异 fixture 均退出 1。
- 外部阻断：H2-B1 仍需 lane/refclk/PERST#/SCBV/UART/I/O timing 的板级证据与决策。H2-B0 发现的 partial run 复用旧 full-build 日志/产物风险已由 CI-8A 的同次运行证明关闭。
- 边界：本批没有 RTL、活动 IDF、FDC、厂商 IP 或生成物修改；H2-B0 只保护失败基线不漂移，不代表 PCIe 可上板或可发布。

## PCIe CI-8A 构建证据绑定（2026-08-31）

- 已验证：37 个 HDL 由 `scripts/pds_sources.f` 单一有序清单驱动；43 项 canonical 输入和 7 项最终证据均以相对 POSIX path、length 和 SHA-256 写入固定 manifest。
- 已验证：每次 build 的 32 位 run_id 原子失效旧证据；`running`、`partial`、`failed` 均无效，只有完整 `gen_bit_stream` 的 `complete/valid` 可继续 gate。
- 负向覆盖：真实 partial compile、PDS executable 缺失、run-id 漂移、产物字节漂移与 FDC 输入漂移均返回 1，证明旧 full-build 证据不能复用。
- 正向覆盖：最终 PG2L50H full build 返回 0、baseline 返回 0、strict 返回 1、最差 slack `0.100 ns`；H2-B0 的 16 签名/42 次记录未漂移。
- 边界：本批未修改 RTL、活动 IDF、FDC 或厂商 IP；CI-8B 等待 DDR3/OV7725 各自 PG2L50H canonical 升格，并按项目独立实现，不抽公共模块。

## CI-9 许可证敏感差异门禁（2026-09-01）

- 已验证入口：`scripts/check_sensitive_diff.ps1 -FullTree` 扫描当前 tracked/untracked 工作树；PR 模式以指定基线和 `HEAD` 的 merge-base 为起点，扫描 changed paths 与 added lines。`docs/SENSITIVE_DIFF_GATE.md` 固化使用方法与边界。
- 已验证规则：严格占位符白名单之外，许可证文件名、Windows/UNC/Unix 绝对许可证路径、真实许可证环境赋值、裸端点、FlexNet 内容、签名与 host id 均返回非零。
- 自检覆盖：2 个允许新增行、5 个拒绝新增行、1 个允许文件名和 1 个拒绝文件名均按预期判定。
- 当前树覆盖：68 个 tracked 日志中的 143 处许可证绝对路径已替换为 `<license-path>`；`-FullTree` 扫描通过，PR 差异扫描也通过。
- 边界：全树门禁保证当前版本不再包含规则覆盖的敏感路径或内容，差异门禁阻止后续重新引入；两者均不读取或打印实际许可证配置，也不改写 Git 历史。

## S0-0-R 仿真器环境复核（2026-08-30）

- 已验证：提交 `ef5cc9a` 再次探测 PATH、常见安装目录和 `vsim.exe` 文件名，`vsim.exe`、`vlog.exe`、`vlib.exe` 均未发现。
- 边界：仅更新 S0-1 阻断证据，未执行 `compile_simlib`、PDS 或动态仿真。

## 项目状态

| 项目 | PDS 实现证据 | 时序证据 | 行为仿真 | 综合后仿真 | PNR 功能仿真 | PNR 时序仿真 |
|---|---|---|---|---|---|---|
| main OV5640→PCIe | M3-A/M3-B 仅有板级无关采集→灰度→128-bit 内部字→两槽 word 短缓冲→4-byte staging→双时钟 CDC→规范化 DDR3 写记录→TB DDR3 模型→PCIe MWR 联合 RTL/TB，无 PDS/IP/FDC/RCF/实现产物 | 固定 `cam_pclk` 源同步输入、一拍灰度处理、同域打包、短缓冲、ready/valid 行为合同与 TB 模型，无板级或 CDC STA | Questa 2021.1：既有 M3-A/M3-B 回归保持通过；新增行为级 loopback 为 0 error/0 warning、唯一 `TEST PASS`、442 ns，并检查 PCIe 地址 `0x0ffc`、`0x1000`、`0x1002` | 未生成 | 未生成 | 未生成/未标注 |
| OV5640 摄像头 HDMI | 产品目标已冻结为 OV5640；C0 参考审计和 C1 产品范围仍待完成 | C3 前无产品 STA；OV7725 旧时序只作 legacy 参考 | S3 项目级入口缺失 | 新产品网表尚未生成 | 新产品 PNR 网表尚未生成 | 新产品 SDF 尚未生成/标注 |
| DDR3 外层 | 旧 PG2L100H 七阶段与五类产物已完成，但不可用于实际 PG2L50H；需重生成 50H IP/FDC/RCF | 旧 100H `All Constraints Met` 只保留历史；50H STA 未执行 | D2/D3-0 旧契约已定，PG2L50H 重生成后须重审；S1 项目级入口缺失 | 旧网表不可签核 | 旧 PNR 网表不可签核 | VSIM/SDF 未验证，旧 100H 结果不可签核 |
| PCIe DMA | 活动 IDF、build/PDS/gate 与新产物均为 PG2L50H；已从空 `build/` 完成七阶段重建 | 50H STA 已生成，最差解析 slack `0.100 ns`；严格 gate 仍受板级/功能缺口阻断 | S2-A 受控 smoke 动态 PASS；不覆盖真实链路/DMA/板级 | 顶层未闭环 | 新 50H 网表待集成仿真 | 公共 VSIM 已验证，项目 SDF 待标注 |

## main OV5640→PCIe M1-A 行为覆盖

- 正向：默认 RGB565 高字节优先，两行各三像素；检查像素数据、零基坐标、首像素 `frame_start`、每行 `line_start/line_end` 和下一 VSYNC 的 `frame_end`。
- 负向：HREF 窗口内只有一个字节时丢弃半像素并产生一次 `protocol_error`；超时或检查失败使用 `$fatal`。
- 结果：主代理提供的 Questa Sim-64 2021.1 证据为编译 0 error/0 warning、运行成功、唯一 `TEST PASS`。
- 边界：未覆盖反字节序/反极性参数、坐标溢出、复位释放时序、SCCB、板级、CDC、DDR3、PCIe 和后级网表/SDF；该 PASS 只关闭板级无关采集切片行为。

## main OV5640→PCIe M2-A 行为覆盖

- 正向：M1-A 公开 DVP 输入经 `ov5640_dvp_rgb565_pipeline` 处理两行四像素黑、红、绿、蓝样本；检查 RGB565 灰度结果、零基坐标及帧/行事件保持。
- 算法/时序：R/G/B 先扩展为 8 bit，使用 `Y=(77*R+150*G+29*B)>>8`，输出灰度 RGB565；处理与所有事件固定延迟一拍 `cam_pclk`，无背压。
- 负向：HREF 窗口内单字节尾部丢弃半像素并保持一次 `protocol_error`；watchdog 或检查失败使用 `$fatal`，成功只输出一次 `TEST PASS`。
- 结果：`docs/IMPLEMENTATION_LOG.md` 记录 Questa Sim-64 2021.1 编译 4 个 RTL/TB 模块为 `0 error/0 warning`、行为仿真返回 0；`run_m2a.ps1` 另验证日志中 `TEST PASS` 恰好一次。
- 边界：未覆盖 SCCB、板级时钟/电气时序/管脚、CDC/FIFO、DDR3、PCIe/主机协议、PDS/STA、综合后/PNR/SDF；`parallel_driver` 仍仅只读参考。

## main OV5640→PCIe M3-A 行为覆盖

- 正向：`rgb565_word_packer` 单元 TB 检查 8 像素完整字的低位优先槽位、`word_keep=16'hffff` 和首帧/首行/行尾事件；3 像素部分行检查 `word_keep=16'h003f`、高位补零及行首/行尾。
- 集成：公开 OV5640 DVP 输入经 M1-A 采集、M2-A 灰度处理和 M3-A 打包形成一行 8 像素完整字与一行 3 像素部分字；另检查帧尾和奇字节协议错误各作为一次空载控制事件传播。
- 控制/退出：watchdog、数据、keep 或事件错误使用 `$fatal`；`run_m3a.ps1` 编译 5 个 RTL 与 1 个集成 TB，并要求日志中的 `TEST PASS` 恰好一次。
- 结果：`docs/IMPLEMENTATION_LOG.md` 记录 2026-09-03 使用 Questa Sim-64 2021.1 编译 6 个 RTL/TB 模块为 `0 error/0 warning`，集成行为仿真返回 0、唯一 `TEST PASS`。
- 边界：该证据只验证内部 `word_data[127:0]`/`word_keep[15:0]` 布局及控制事件；不覆盖 SCCB、板级、CDC/FIFO、DDR3 地址/事务、PCIe AXIS/TLP、主机协议、PDS/STA、综合后/PNR/SDF。
- 协议判定：两个 M3-A TB 现统一把 `word_valid && word_keep!=0` 视为 payload，把 `word_valid=1`、`word_keep=0` 视为纯控制事件，避免帧尾/协议错误被误判为无效输出。

## main OV5640→PCIe M3-B staging 覆盖

- 正向：完整 16-byte 字拆成四个 32-bit beat，低 lane 顺序保持，前三个及末 beat 的 4-bit keep/last 正确。
- 边界：2-byte 部分字只输出 `keep=4'h3`；空载帧尾输出 `keep=0`、`last=1`；首/尾事件位置和 downstream backpressure 均受检。
- 结果：`run_m3b.ps1` 使用 Questa Sim-64 2021.1 编译 2 个 RTL/TB 模块为 `0 error/0 warning`，行为返回 0、唯一 `TEST PASS`。
- 边界：该测试只证明 staging 行为，不证明厂商 PCIe `tkeep/tuser`、TLP、DDR3、CDC/FIFO、主机协议或 PDS/STA。

## main OV5640→PCIe M3-B 两槽 word skid 中止恢复覆盖

- code：`main_ov5640_pcie/rtl/rgb565_word_skid_buffer.sv`
- test：`main_ov5640_pcie/tb/tb_rgb565_word_skid_buffer.sv`
- script：`main_ov5640_pcie/scripts/run_m3b_word_skid_buffer.ps1`
- 正向：两槽 FIFO 按先入先出保留溢出前的两个 128-bit word；下游暂停时检查队首字段保持，第三个 word 在满队列且无同拍出队时触发 sticky `overflow`，不得覆盖前缀。
- 中止与恢复：原帧余量被丢弃，前缀后恰好输出一个 `keep=0/frame_end=1/protocol_error=1` 空载中止记录；中止记录尚未排队时到达的新帧整帧跳过。只有观察到原帧尾且中止记录已排队，后续 `frame_start` 才恢复，恢复帧不得带协议错误。
- 并发边界：覆盖满队列同拍 pop/push，确认出队前缀与新入队 word 的 FIFO 顺序和字段不被破坏；覆盖原 `frame_end` 到达与 synthetic abort 入队同拍，确认帧尾观察和中止排队两个条件不会丢失。
- 连续故障与复位：连续制造两个损坏帧，分别检查每帧恰好一个 abort 且两个 abort 与保留前缀的输出顺序正确；在 drop/abort 状态中施加异步复位，检查队列、sticky overflow 和恢复控制状态回到复位合同。
- 结果：Questa Sim-64 2021.1 编译 2 个 RTL/TB 为 0 error/0 warning，行为返回 0，日志唯一 `TEST PASS`，仿真至 526 ns。
- 边界：`in_ready` 仅作诊断，不能反向节流无背压 packer；已验证帧中止/恢复，但两槽缓存不保证持续满载无损，持续背压可跳过多个完整帧。未覆盖 DDR3 无效帧回收、真实帧缓存、PCIe、静态 CDC/RDC、复位释放或实现级时序。

## main OV5640→PCIe M3-B 联合 staging 覆盖

- 联合：`ov5640_dvp_rgb565_dma_staging_pipeline` 串接采集、灰度、128-bit 打包、4-byte staging 与帧统计描述符；3 像素输入输出 2 个 beat、6 个有效字节，描述符 `desc_protocol_error=0`。
- 握手：固定 `staging_ready=1`，描述符先背压后释放；数据通道由 staging ready 与 accounting ready 合取背压，`desc_ready` 不直接反向控制 adapter。
- 结果：`run_m3b_integration.ps1` 使用 Questa Sim-64 2021.1 编译 9 个 RTL/TB，0 error/0 warning，行为返回 0，日志唯一 `TEST PASS`。
- 边界：仅证明同一 `cam_pclk` 域的 staging 联合行为；`frame_end_pending` 是无输入背压条件下的临时对齐策略，不覆盖真实 FIFO/CDC、DDR3、PCIe AXIS/TLP、主机协议或后级 PDS/STA/SDF。

## main OV5640→PCIe M3-B 双时钟 CDC staging 覆盖

- 联合：`ov5640_dvp_rgb565_cdc_staging_pipeline` 串接采集、灰度、128-bit 打包、两槽 word 短突发缓冲、4-byte staging 与双时钟 CDC bridge；正常期 3 像素输入输出 2 个 payload beat 加 1 个 `keep=0` 空载帧尾事件，且 `source_overflow=0`。
- 压力：复位后保持 `out_ready=0`，输入 64 像素使两槽缓冲耗尽并置位 sticky `source_overflow`；恢复 ready 后输出 20 个 beat，其中前缀保持、当前帧余量丢弃，并且恰好 1 个 beat 为 `keep=0/frame_end=1/protocol_error=1` 中止记录。
- 恢复：只有原帧尾已观察且中止记录已排队，后续 `frame_start` 才解除丢帧状态；测试中的下一帧完整输出 2 个 beat。中止条件满足前到达的新帧不得泄漏到输出。
- 结果：`run_m3b_ov5640_cdc_staging.ps1` 使用独立 5 ns/7 ns 时钟编译 11 个 RTL/TB，Questa Sim-64 2021.1 为 0 error/0 warning，行为返回 0，日志唯一 `TEST PASS`，仿真至 2863 ns。
- 边界：仅证明该 staging/CDC 联合切片的中止记录和下一帧恢复；不覆盖中止记录经真实 DDR3/PCIe/主机协议保存或无效帧回收，也不覆盖静态 CDC/RDC、复位释放、RAM 推断、PDS/STA 或 SDF，不等同真实 DDR3/PCIe 闭环通过。

## main OV5640→PCIe normalized MWR descriptor 覆盖

- 正向：以 `BASE_ADDR=64'hffc` 输入两个 staging beat，检查第二请求地址按第一 beat 的有效字节数递增至 `0x1000`，`keep`、`last` 与 `frame_end` 原样保持。
- 边界：检查 4KB 跨界标志在首个请求置位、跨界后的请求清除；仅按 `keep` 有效字节计数，不引入厂商 TLP 编码。
- 结果：`tb_rgb565_axis4_mwr_descriptor.sv` 通过 watchdog、`$fatal` 和唯一 `TEST PASS` 判定上述字段。
- 边界：该 TB 只证明 vendor-independent normalized descriptor 的地址/字段行为，不证明厂商 PCIe IP、TLP/max-payload、DMA 完成、DDR3、CDC/FIFO 或后级 PDS/STA/SDF。

## main OV5640→PCIe MWR bridge 覆盖

- 正向：检查规范化请求映射到已审计 `mwr32_req` 接口，`req_length/addr/data/keep/cross_4kb_boundary` 字段正确。
- 握手：字段在 `mwr32_req_ack` 到达前保持稳定，ack 后释放 busy/request。
- 结果：`tb_rgb565_axis4_pcie_mwr_bridge.sv` 使用 watchdog、`$fatal` 和唯一 `TEST PASS` 验证上述行为。

## main OV5640→PCIe M3-B 规范化 MWR 组合路径覆盖

- 组合：`rgb565_axis4_pcie_mwr_path` 串接 staging、MWR descriptor 与临时 `mwr32_req/ack` bridge。
- 控制器事实：`req_length` 单位为 DWORD；在控制器边界 `req_length=0` 表示 `0x1000` 字节；当前每个 32-bit beat 仍发 `req_length=0`。
- 边界回归：`BASE_ADDR=0x0ffc` 的 4-byte 请求恰到 4KB 边界，不报 crossing；ack 后地址为 `0x1000`，并检查请求字段保持和事件传播。
- 结果：Questa Sim-64 2021.1，0 error/0 warning，唯一 `TEST PASS`，125 ns。
- 未覆盖：真实 TLP、DMA、byte-enable、PCIe 链路、主机输出及厂商 PCIe IP 集成。
- 边界：byte-enable 映射仍是临时合同；不证明真实 PCIe TLP、DMA、厂商 IP、DDR3、CDC/FIFO 或后级实现。

## main OV5640→PCIe normalized DDR3 write record 覆盖

- 正向：TB 使用 `BASE_ADDR=28'h12`、`ADDR_STEP=28'h4`，检查首个单 beat 128-bit `write_data`、16-bit `write_strobe`、`write_awlen=0`、opaque 28-bit `write_addr` 及 `write_last/frame_end/protocol_error` 字段；释放后验证地址为 `28'h16`。
- 结果：`run_m3b_ddr3_write_descriptor.ps1` 使用 Questa Sim-64 2021.1，编译 0 error/0 warning，行为日志唯一 `TEST PASS`。
- 回归增强（2026-09-03）：新增空 keep 控制记录（`write_valid=1`、`write_strobe=0`）；`write_ready=0` 背压期间保持地址、数据、strobe、last、frame_end 与 protocol_error 全部字段；连续记录检查 `ADDR_STEP` 地址推进；复位后检查 `BASE_ADDR` 覆盖恢复。Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`，仿真至 126 ns。
- 边界：地址推进仅由 `ADDR_STEP` 控制，仍是 opaque 28-bit token；不假定地址单位、初始化、AXI4 burst 或 vendor DDR3 IP；未覆盖 DDR3 控制器、CDC/FIFO、真实内存时序、PDS/STA/SDF。

## main OV5640→PCIe M3-B 行为级 DDR3/PCIe loopback 覆盖

- test：`main_ov5640_pcie/tb/tb_ov5640_ddr3_pcie_loopback.sv`
- script：`main_ov5640_pcie/scripts/run_m3b_ov5640_ddr3_pcie_loopback.ps1`
- 链路：OV5640 DVP 输入经过双时钟 CDC staging，转换为规范化 DDR3 单 beat 写记录；TB 内数组模型保存 3 条记录，再按帧序送入规范化 PCIe MWR 路径。
- 正向：3 个像素产生 2 条 payload 与 1 条空载帧尾记录；检查 DDR3 模型的 keep 分别为 `4'hf`、`4'h3`、`4'h0`，末记录携带 frame_end，回读请求的数据、keep、last、frame_end、protocol_error 与模型一致。
- 地址：PCIe MWR 地址依次为 `0x0ffc`、`0x1000`、`0x1002`，三次请求均不得误报跨 4 KB，ack 后 busy/request 必须释放。
- 结果：Questa Sim-64 2021.1 为 0 error/0 warning、日志唯一 `TEST PASS`，仿真至 442 ns。
- 边界：只证明正常帧 vendor-independent 行为记录的端到端保存与回送，尚未覆盖 overflow 中止记录；不证明真实 DDR3 地址/握手/初始化/读时序，不证明 PCIe TLP、byte-enable、链路、DMA/主机，也不证明板级时序或实现级 CDC/RDC。

## S1/S2/S3 仿真就绪度矩阵（2026-08-30）

- 已验证盘点：`docs/SIMULATION_READINESS_MATRIX.md` 已逐项目记录项目级 testbench、filelist、DO、厂商示例和四级仿真前置条件；PCIe S2-A 已实际执行 Questa 动态 smoke。
- DDR3 与 OV7725 的项目级资产仍为 `project_tb=0`、`project_f=0`、`project_do=0`。PCIe 已具备 1 个项目集成 TB、1 个受控边界模型、1 个行为 filelist 和 1 个 DO 入口，并已动态 PASS。
- OV5640/S3：先完成 C0 参考审计与 C1 产品范围冻结，再由 C2/C3 建立新项目顶层、PG2L50H IP/约束和实现 baseline；OV7725 厂商示例与 O2/O3 结果只作 legacy 参考。
- DDR3/S1：现有厂商 `test_ddr`/memory-model 资产端口失配且含绝对路径与 FSDB/Verdi 假设。进入 S1 前必须关闭 S0-1、重生成并复核 PG2L50H DDR3 IP/FDC/RCF、完成 D3-A/B/C 与 D4，并提供项目自有有限 BIST/top 与自检 TB。
- PCIe/S2：S2-A 已用项目级 `tb_pcie_dma_test` 实例化产品顶层，并以受控 `pcie_test` 边界动态验证顶层/复位/LED/未知态；现有 `pango_pcie_top` RC/EP testbench 仍不实例化产品顶层，只能在 S2-B 中作为真实 RC/编译顺序 oracle；S2-C 才验证 DMA。
- 验收边界：`ipcore/`、`ip_core/`、`ip_backup/` 中的厂商示例只能作为参考证据，不能计入产品集成覆盖，也不能通过改名冒充项目自有 testbench。
- 四级共同门槛：所有入口使用相对路径 filelist/DO 和项目自有集成 TB；必须具备超时、`$fatal`、唯一 `TEST PASS` 与可靠非零失败退出；PNR 时序仿真必须按实际 DUT 实例层级标注 SDF。
- 公共状态：Questa Sim-64 2021.1 工具、Logos2 USIM/VSIM 与历史 smoke 有通过证据；当前 S2-A/S2-B 静态门禁通过，动态复验受仓库外许可证 checkout 阻断。DDR3/S1、OV5640/S3、PCIe S2-B 动态/S2-C 与三个项目后级仿真仍未完成。

## PCIe S2-A 行为 smoke（2026-09-01，动态通过）

- 已验证源边界：`sim/behav.f` 嵌套复用 `scripts/pds_sources.f` 的 37 个 canonical HDL，并单独补入仿真所需 `ipcore/pcie_test/rtl/ips2l_pcie_apb_cross_v1_0.v`；`scripts/pds_sources.f` 不修改，因为该源在实现侧由 IDF 管理。
- 已验证编码与自检边界：受控模型恰好包含两个 `always_ff` 时序过程，静态 gate 禁止普通 `always @` 回退。TB 覆盖 `button_rst_n`、`perst_n`、同步复位、LED 计数门控和 TX/LED 未知态；3 ms watchdog 或检查失败调用 `$fatal`，正向源只包含一次 `$display("TEST PASS")`。
- 已验证 reset ownership：button reset 断言后，TB 先检查 ref counter 没有被 button reset 改写，再等待额外 8 个 refclk 周期并要求其在 model link 撤销期间严格保持；button reset 完整重新释放后，PERST# 再被单独断言、复位两组 LED 域并独立重新释放，不能由初次联合释放遮蔽 debounce 行为。
- 已验证复位与日志契约：TB 全局复位实例使用厂商要求的 `GRS_INST`；`run_behav.do` 通过 `echo` 将随机 32 位小写十六进制 `SIM_RUN_ID` 写入 transcript，PowerShell 只接受同 run-id marker 与 `TEST PASS` 各恰好一次。
- 动态结果：Questa Sim-64 2021.1 下 `vlog` 为 0 errors/0 warnings；`vsim` elaboration 成功并运行到 `1476105 ns`，Errors 0/Warnings 2、唯一 `TEST PASS`；PowerShell 同 run-id/唯一 PASS 门禁通过。
- 当前复验结果：S2-A 静态 gate 与 S2-B 静态契约 gate 通过；S2-A 动态启动因仓库外许可证 checkout 失败返回 4，未产生新的 `TEST PASS`。上一条仅为历史 PASS，不代表当前复验通过。
- 构建回归：当前 manifest run id `c24bc06b5d0643eeb6c9cb2878e7ace5` 为 `gen_bit_stream/complete/valid=true`，43 项输入和 7 项证据完整；baseline gate 再次返回 0，strict gate 仍因 UART RX tied low、未约束顶层 I/O、PCIe serial I/O、share pin 与 SCBV 返回 1。该结果只证明失败基线可复现。
- warning TODO：两条 warning 均为 `pcie_dma_test.v` 中 `u_ips2l_pcie_dma` 缺少输出 `o_trgt1_radm_pkt_halt` 连接；作为后续独立 RTL hygiene TODO，不影响本层受控 smoke PASS。
- 覆盖边界：受控模型的 `smlh_link_up/rdlh_link_up` 是激励，不验证真实 LTSSM、TLP、DMA、lane/P/N 极性、100 MHz refclk 电气、PERST# 板级时序或 RK3568 Root Complex。S2-B 必须使用真实厂商 RC/EP，S2-C 必须在其后验证 DMA。

## 已知功能与覆盖缺口

- OV7725：`41_ov7725_hdmi/doc/CDC_RDC_AUDIT.md` 已记录七类时钟域、`wr_load`/`rd_load` 多点采样、两个异步 FIFO 数据方向和分侧复位风险，以及三条旧 STA 失败路径。
- OV7725：O1-B 已完成 38 条确定性 RTL 卫生修复，手写 RTL 位宽告警只剩 `mem_a` 1 条；该单项因活动 IP 14 bit 与顶层/FDC 15 bit 冲突继续转 H3/O1-C，当前综合网表把 `mem_a[14]` 绑 0。
- OV7725：O2-B 详细 STA 将反向八个 endpoint 唯一映射到 `serializer_b/g/r/clk × opit_2/opit_2_com` 的 OSERDES `OCLKDIV` 检查；慢角高速同域 `OCLK` 也仍为负。该覆盖证明候选失败，不构成 serializer reset 通过证据。
- OV7725：O2-D1-R 已从空 `build/` 完成七阶段，baseline gate 精确匹配原七组 corner/check/clock pair/endpoints 并返回 0，严格 gate 返回 1；Slow/Fast `ddrphy_sysclk → pixel_clk` Recovery 均恢复为 `53/53`，endpoint 分类为 `26+8+17+1+1`，没有新增失败签名或 waiver。O2-D1-G 现已冻结：只允许一条 `pixel_clk` `/5` generated clock，源 `u_pll_clk/clkout1`、目标唯一 `GTP_IOCLKDIV_E2.CLKDIVOUT`、波形 `-edges {1 5 11} -edge_shift {0 0 0}`，并使用 `HARD_HOLD → QUALIFY → ARM → SER_RELEASE → RUN` 状态契约；审核前不实现 O2-D2，QuestaSim/S3 未完成。
- OV7725 M3-A：SP6.4 隔离探针已覆盖四个活动 IDF，确认不带安装定义时报 `IPCompiler 0037`，显式绑定当前定义时报版本不匹配 `IPCompiler 0057`，均退出 104。仓库门禁现检查迁移审计文档和四个 canonical IDF 的 SHA-256；该覆盖只证明旧 IDF 不可直接迁移及 canonical 未改，不证明 50H IP 已生成。
- OV7725 M3-B 待覆盖：SP6.4 GUI 新建四个 PG2L50H staging 实例后，必须验证 DDR3/PLL 派生参数、FIFO 85 DRM36K/170 DRM18K 上限、wrapper/FDC/RCF/仿真资产差异和 RCF 对象命中；板级资料未关闭时禁止升格、50H PDS 和 S3。
- DDR3：临时 `test_ddr` bring-up 已完成全流程与内部 STA/产物基线。严格 gate 因 7 类问题返回 1：BIST error-data 位宽不匹配、BIST dangling cleanup、`rst_board` 使用 share pin、BANKR4 VCCIO 3.3 不兼容、UART I/O 约束缺失、顶层输入 timing 缺失、顶层输出 timing 缺失。显式 baseline 放行返回 0，但明确标记不可发布。
- DDR3 M2 只读审计（2026-08-30）：活动 IDF 为 `ip_core/ddr3/ddr3.idf`，metadata `Logos2/PG2L100H/FBG484/-6`、生成器 `2022.2-SP6.4`；canonical FDC/RCF 为 `ip_core/ddr3/pnr/ddr_test.fdc` 与 `ip_core/ddr3/pnr/ddr3.rcf`。唯一 50H 备份来自 SP6.1，不能直接替换；外层 `ip_core/ddr_test.fdc` 仅供差异参考。
- DDR3 M2-B1 参数覆盖（2026-08-30）：PDS SP6.4 `ui.tcl` 静态证据确认 `DEVICE_100H_EN` 是隐藏派生参数，`PG2L100H/HX=true`、`PG2L50H=false`；已通过错误探针证明直接 `-device` 覆盖 100H IDF 会保留 `true` 并生成 PPLL `FALSE/CLKOUTF`，该路径已禁止。
- DDR3 M2-B1 重生成覆盖：脚本验证活动 100H IDF 与 SP6.1 50H seed 的所有参数仅上述 flag 不同，再由 SP6.4 build 146967 重生成；输出 `DEVICE_100H_EN=false`、PPLL `TRUE/CLKOUT4`、退出 0、`0 error(s), 0 warning(s)`，canonical 哈希不变。
- DDR3 M2-B1 差异覆盖：正确 staging 的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 均有差异；wrapper 端口数 `21 → 26`，新增 `ref_clk_p/n`、`pll_lock`、`ddrphy_cpd_lock`、`ddr_init_done`；FDC 有 28 项 pin 差异。该覆盖只证明生成输入与差异审计正确，不证明板级 pin 匹配。
- DDR3 M2 退出条件：取得原理图/BOM并审核板级参数、28 项 FDC pin 差异与新 wrapper/PHY/filelist/IDF 后才能升格 canonical；之后 CI-6 必须重新确认端口/128-bit 数据/28-bit 地址/握手/`I_ips_ddr_top`，并从空 `build/` 完成七阶段且产物器件交叉一致。M2-B1 未授权 D3-A/B/C 或项目自有 BIST RTL。
- DDR3：本次完整构建日志没有 SCBV 命中；这不替代板级批准参数清单。DDR3 颗粒/组织、VCCIO/VREF、ODT、拓扑、走线、UART/ADC 决策等仍缺少审核依据。
- DDR3：testbench 端口仍失配，BIST 无天然有限完成状态，缺少可靠 `$fatal`、超时、唯一 `TEST PASS` 和四级仿真证据；当前结果只验收可重复实现基线，不验收板级功能或产品状态。
- DDR3：D2 已以只读方式固定后续测试契约，厂商 `test_ddr`、持续运行 BIST 和旧 testbench 保持原样。计划新增 `ddr3_bringup_top.sv` 与 `ddr3_finite_bist.sv`，首版执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并设置 4096 周期 pair timeout 与 131072 周期 run timeout。
- DDR3：未来行为仿真必须通过公开且稳定的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息判定结果；D2 与 D3-0 仅完成只读决策，不构成实现或测试覆盖，D3-A/B/C 仍待用户审核。
- DDR3 D3-0（只读静态评审）：活动 IP 为 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的 `module ddr3`，公开端口包含 `ddr_init_done`、`core_clk` 与 AW/W/AR/R 自定义 AXI-like 接口；`test_ddr.v` 的物理 board wrapper 实例名为 `I_ips_ddr_top`，必须保留。
- DDR3 D3-0 已完成非标准 AXI-like 握手评审：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回依赖 `axi_rvalid`/`axi_rlast` 且无 `axi_rready`。D3-A 等待用户审核后按该契约实现，接口语义、地址单位或层级变化即停止并重新审核。
- DDR3 D3-0-R 端口映射见 `ddr3_test/ddr3_test/doc/D3A_PORT_MAP.md`：当前默认 `CTRL_ADDR_WIDTH=28`、`axi_wdata/axi_rdata=128` bit、`axi_wstrb=16` bit；文档明确 APB/debug tie-off 与物理端口不属于 D3-A BIST 接口。
- PCIe：S2-A 已动态通过覆盖 `pcie_dma_test` 集成顶层的受控行为 smoke；厂商 ModelSim 资产仍只覆盖 PCIe IP 示例，真实 RC/EP、LTSSM/TLP/DMA 与 UART2APB 无驱动输入仍未验证。
- PCIe H2-A（只读证据矩阵）：顶层使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 与 `ref_led/pclk_led`；FDC 固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。当前没有 lane 极性/板级拓扑、I/O delay 或 SCBV 证据。
- PCIe H2-A/M1 器件边界：活动 `pcie_test.idf`、build/PDS/gate、timing report 与 `bgr.db` 已统一匹配 `Logos2/PG2L50H/FBG484/-6`；UART2APB `rxd/txd`、SCBV、lane/refclk/PERST# 与 share pin 仍是独立功能/发布阻断。
- 三项目新流程均已生成顶层 PNR SDF，但尚未由 QuestaSim 验证实例层级。
- Questa Sim-64 2021.1、Logos2 USIM/VSIM、`V_BUF` 和 PCIe S2-A 保留历史通过证据；当前动态复验未通过许可证 checkout。不得将历史证据外推为当前运行、DDR3、OV5640、真实 PCIe 链路、DMA 或项目后级网表/SDF 通过。
- PDS 可能在日志含 `E:` 时仍返回退出码 0；新 PowerShell 入口必须同时检查退出码和错误日志。
- 2026-09-03 全回归曾出现 Questa `vopt signal 11`；根因是 D 盘仅余约 16 KB、数据库写满，非 HDL/库缺陷。清理忽略的 `build/` 运行态后，`run_m3b_accounting.ps1` 重新通过，恢复 `0 error/0 warning` 与唯一 `TEST PASS` 证据。

- main OV5640 M3-B 联合覆盖：3 像素 RGB565 输入经采集、灰度、128-bit 打包和 4-byte staging，输出 2 个 beat、6 个有效字节，并生成无协议错误帧描述符；固定 `staging_ready=1`、描述符先背压后释放。该证据不覆盖真实 DDR3/PCIe/CDC。
- PCIe 位流阶段报告 SCBV 未配置，这是当前发布阻断项。

## 统一验收门槛

1. 行为级 testbench 自检通过，失败使用 `$fatal`，成功只输出一个 `TEST PASS`。
2. PDS 各阶段退出码为 0，并对最终时序强制 `WNS >= 0`、`TNS = 0`。
3. 综合后、PNR 后功能和 PNR 后时序仿真均使用集成顶层，而非仅 IP 示例。
4. O2-D2 只允许一次已审核实验；八个 OSERDES endpoint 的 Slow/Fast × Recovery/Removal × `OCLK` 双边沿/`OCLKDIV`/`SERCLK` 全覆盖且非负，generated clock 唯一，旧 `CLKOUT0` 对 pixel 域为零消费者。generated-clock 对象/波形/取点、端点覆盖、PDS/gate/产物或新 baseline 失败任一异常即停止并完整回退，不得扫描第二相位或增加 waiver。
4. 时序仿真确认 SDF 实例层级匹配，日志无标注错误和未批准的 timing violation。
5. 最终位流文件存在且大小非零；关键未约束 I/O 必须修复或进入有依据的白名单。
6. DDR3 有限自检必须完成恰好 16 个 pair；任一 pair 超过 4096 周期或整次运行超过 131072 周期均失败，成功与失败只能由公开结果接口和退出码判定。
7. DDR3 D3-0 已冻结 AW/W/AR/R 握手语义与 `I_ips_ddr_top` 实例边界；D3-A/B/C 仍待用户审核和实现，且 D3-0 评审不构成 RTL/IP/约束变更或仿真通过证据。
8. 三项目最终产物必须证明目标为 `PG2L50H/FBG484/-6`；任何 PG2L100H report、SDF 或位流均拒绝烧录和签核。
9. PCIe H2-B 只有在 50H build/IDF/report/bitstream 一致、lane 极性/拓扑、I/O delay、SCBV 和 UART2APB 归属均有证据后才可发布。

## main OV5640→PCIe M3-B CDC bridge 覆盖

- 正向：`rgb565_axis4_cdc_bridge` 封装 `rgb565_axis4_async_fifo`，以独立 3 ns/5 ns 时钟传递 5 个 staging beat，验证顺序、首末事件、keep/last/user、ready/valid 与最终 drain。
- 结果：Questa Sim-64 2021.1，0 error/0 warning，唯一 TEST PASS，155 ns。
- 缺陷修正：FIFO entry 从错误的 41 bit 修正为实际 42 bit，避免 `user[4]` 截断。
- 边界：未覆盖静态 CDC/RDC、RAM 推断、复位释放、三时钟约束、真实 DDR3/PCIe IP 集成或实现级时序。

## main OV5640 M3-B 双时钟 CDC staging pipeline 覆盖

- 链路：`ov5640_dvp_rgb565_cdc_staging_pipeline` 串接 DVP、灰度、128-bit pack、两槽 word 短突发缓冲、4-byte adapter 与双时钟 CDC bridge。
- 正向：小帧双时钟 TB 验证 2 个 payload beat、1 个空载帧尾事件、`keep` 以及首/末事件跨域到达，且无 overflow；压力期验证 64 像素输入、下游暂停、sticky overflow、20 个输出 beat（含唯一中止记录）及下一帧 2 个 beat 恢复。
- 溢出语义：`source_overflow` 直接来自两槽 word skid；满队列溢出后保留前缀、丢弃当前帧余量，并注入唯一 `keep=0/frame_end=1/protocol_error=1` 中止记录。只有原帧尾已观察且中止记录已排队，后续 `frame_start` 才恢复；此前到达的新帧整帧跳过。
- 结果：Questa Sim-64 2021.1 编译 11 个 RTL/TB 为 0 error/0 warning，日志唯一 `TEST PASS`，仿真至 2863 ns。
- 边界：未覆盖中止记录经真实 DDR3/PCIe/主机协议保存或无效帧回收，也未覆盖静态 CDC/RDC、复位释放、RAM 推断、PDS/STA 或 SDF；两槽 skid 不等同帧缓存或真实 DDR3/PCIe 闭环。
