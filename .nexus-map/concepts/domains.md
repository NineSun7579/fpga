> generated_by: Codex manual bootstrap
> verified_at: 2026-09-04
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## 当前平台基线

当前唯一目标为 `RK3568_MES2L100H`（FPGA + ARM）、`PG2L100H-6IFBG484`、
`Logos2 / PG2L100H / FBG484 / -6`。旧 50H 节点只作历史审计或待迁移文件名说明；活动 PCIe IDF 仍为 50H metadata，因此当前入口必须保持 migration-blocked。

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

2026-08-30 S0 环境复核的“未发现仿真器”结论已被后续实际执行证据取代。截至 2026-09-01，Questa Sim-64 2021.1 最小 SystemVerilog 已通过，参数化 `scripts/compile_simlib.tcl`/`.ps1` 已成功生成 Logos2 USIM/VSIM；VSIM 编译退出 0、日志无 `^E:` 且库目录非空。

CI-7 入口分类要求全部 tracked Tcl 完整登记。只有项目自有 `scripts/build.tcl` 可通过 `run.ps1` 进入 `pds_shell`；活动入口以 PG2L100H 为唯一目标，PCIe 因活动 IDF 仍带旧 PG2L50H metadata 而 migration-blocked。`impl.tcl`、parse-design screen、厂商 IP PNR 和单 IP 仿真脚本中的旧器件、混合目标或绝对路径只保留为历史/内部证据，不能用于当前器件、STA、网表、SDF、位流或集成仿真签核。

2026-09-01 CI-9 同时覆盖当前树和 PR 差异：`-FullTree` 扫描 tracked/untracked 工作树，PR 模式依据 Git merge-base 扫描 changed paths 与 added lines。当前版本已将 68 个 tracked 日志中的 143 处许可证绝对路径替换为 `<license-path>`；全树和差异门禁均通过。门禁不读取实际配置，也不改写 Git 历史。

DDR3、PCIe 和摄像头产品共用 `RK3568_MES2L100H`（FPGA + ARM）平台，FPGA 为 `PG2L100H-6IFBG484`，统一 PDS 目标为 `Logos2/PG2L100H/FBG484/-6`。摄像头产品目标为 OV5640，按 C0 参考审计、C1 范围冻结、C2 项目边界、C3 PG2L100H 实现和 S3 四级仿真推进。

## 板级一手资料与产品冻结边界

2026-09-04 登记的 RK3568 板卡手册 v1.1 已把 RK↔FPGA PCIe x2、FSPI、I2C0、GPIO、25 MHz 系统
时钟、100 MHz PCIe refclk、DDR 参考时钟和 x16 512 MByte DDR3 物理映射从“推断”提升为手册事实。
这些事实不定义 PG2L100H DDR3 控制器用户口、PCIe DMA/TX 软件语义或 RK3568 缓存一致性；旧 PG2L50H 用户口记录只作迁移比对。

同日登记的 OV5640 DVP 指南 2.13 定义 8-bit `D[9:2]` 参考接口、RESETB/PWDN 极性、供电范围、
电平转换风险、SCCB 上拉和参考启动/复位时序。它不是实际模组原理图，也不冻结 FPGA Bank、管脚、
SCCB 7-bit 地址、RGB565 寄存器表、PCLK 采样边沿、字节序、宽高或帧率。用户已明确接入位置暂定，
因此产品顶层和 FDC/RCF 必须继续等待实际接线决策。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

Questa Sim-64 2021.1、Logos2 USIM/VSIM、`V_BUF` 和 PCIe S2-A 受控 smoke 均保留历史通过证据。当前版本 S2-A/S2-B 静态门禁通过，但 S2-A 动态复验因仓库外许可证 checkout 失败返回 4，未产生新 PASS。DDR3 与 OV5640 仍缺项目级入口，三个产品方向的真实网表/SDF 仿真仍待完成。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D3-0（2026-08-30）已完成只读边界评审：活动 IP 是 `ddr3_test/ddr3_test/ip_core/ddr3/ddr3.v` 的公开 `module ddr3`，其端口包含 `core_clk`、`ddr_init_done` 以及自定义 AXI-like AW/W/AR/R 接口；`test_ddr.v` 的物理 board wrapper 实例名必须保留为 `I_ips_ddr_top`。

D3-0 已确认旧 IP 接口不能按标准 AXI ready/valid 擅自解释：AW/AR 分别以 valid/ready 接受，写数据接受由 `axi_wready` 指示，核心返回 `axi_wusero_id`/`axi_wusero_last`；读返回使用 `axi_rvalid`/`axi_rlast` 且没有 `axi_rready`。CI-6 已保护该静态事实，但 M2 必须核验或重生成 PG2L100H IP/FDC/RCF并重跑门禁；只有端口、地址单位与 `I_ips_ddr_top` 层级重新确认并审核后才可进入 D3-A。

DDR3 M2-B1 历史差异审计通过 PDS SP6.4 `ui.tcl` 确认 `DEVICE_100H_EN` 是隐藏派生参数：`PG2L100H/HX=true`，`PG2L50H=false`。旧流程直接用 `-device PG2L50H` 覆盖 100H IDF 会保留错误值并选择不一致分支，因此 50H override、staging 和生成路径均已禁止，旧 `scripts/regenerate_ip.ps1` 也已硬阻断。历史 50H seed/staging 与当前 100H 资产的 DDR PHY slice、wrapper、FDC、仿真 filelist 与 IDF 差异只用于迁移审计；当前只允许按 PG2L100H 核验或重生成，并在原理图/BOM审核后才可升格 canonical，D3-A 仍未授权。

PCIe H2-A（2026-08-30）固定产品顶层的板级边界：`pcie_dma_test` 使用 x2 `rxn/rxp/txn/txp`、差分 `ref_clk_p/n`、`perst_n`、`button_rst_n` 和两枚 LED；当前 FDC 仅固定 refclk `F6/E6`、PERST# `M16`、button reset `M15`、LED `M17/J16`。lane 极性、板级拓扑、I/O delay 和 SCBV 均没有证据，不能由实现成功推断。

PCIe H2-B0（2026-08-30）在历史 50H baseline 中将五类问题归一化为 16 个唯一签名、42 次原始记录，并以完整多重集保护失败状态。旧 fixture 及其“100H IDF 变异失败”只说明该门禁绑定错误平台，不能沿用为当前批准规则。当前 PG2L100H gate 必须拒绝活动 IDF 的 50H metadata；H2-B1 仍受 lane/refclk/PERST#/SCBV/UART/I/O timing 外部资料阻断，partial run 复用旧 full-build 证据的风险已由 PCIe CI-8A 关闭。

PCIe CI-8A（2026-08-31）把构建证据定义为一次运行的不可拆分集合：37 个 HDL 单一清单、43 项输入和 7 项最终证据由同一 32 位 run_id 与 SHA-256 manifest 绑定。每次 build 开始即原子失效旧 complete 证据；`running/partial/failed` 均不可验收，只有 `complete/valid` 可继续 gate。历史 PG2L50H full build/baseline/strict 为 `0/0/1`，slack `0.100 ns`，只作旧产物审计；CI-8B 等待 DDR3 与 OV5640 建立 PG2L100H canonical 输入后逐项目迁移。

PCIe S2-A 的历史 PASS 只验证产品壳层受控行为 smoke；当前复验因仓库外许可证 checkout 失败而未运行。受控 link 不证明真实 LTSSM、TLP、DMA 或板级链路；S2-B 静态契约已通过，仍必须在许可证恢复后产生新的真实 RC/EP 动态证据，S2-C 才执行基础 DMA 回读。

当前审核确认活动 `pcie_test.idf` 的 `Logos2/PG2L50H/FBG484/-6` metadata 是错误平台记录，也是 PG2L100H 迁移阻断；禁止手改厂商 IDF，必须由 SP6.4 重新生成或取得可审计的 PG2L100H PCIe IP。项目自有 build/gate 已按 PG2L100H 管理，旧 50H baseline/STA/位流只作历史证据，同时继续阻断 UART2APB、lane/refclk/PERST# 与 SCBV 缺口。

DDR3 D2 已进一步固定该边界：厂商 `test_ddr`、持续运行 BIST 与旧 testbench 保持原样；后续有限自检由项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 承担。首版仅执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并通过稳定公开的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息完成签核。

## CDC 与异步 FIFO

单比特电平、脉冲、多比特数据和 FIFO 指针需要不同跨时钟域策略。同步器降低亚稳态传播概率但不消除亚稳态；时序例外只能施加在结构已验证的 CDC 上。

main 线的 DDR `core_clk`→PCIe `pclk_div2` MWR32 边界使用“同步控制 token + bundled-data MCP”，而不是逐位同步 payload。源 payload 从 request token 发出保持到 ACK 返回；online/fault 保持两级同步，request/ACK token 使用三级同步，确保 peer-offline 先于事务 token 到达事务逻辑；目标检测 token 后额外等待一拍再采样。placed-design 必须为 holding registers→capture registers 签核 max-delay/bus-skew，禁止把整条 payload 总线简单 false-path。RTL 行为通过不等价于 CDC/RDC/STA 签核。

## main OV5640 M2-A 图像处理

M2-A 将 `cam_pclk` 域的 M1-A RGB565 采集流连接到 `rgb565_grayscale`。模块先按 R[15:11]、G[10:5]、B[4:0] 扩展 8 bit，再使用 `Y=(77*R+150*G+29*B)>>8`，把 Y 复制到 RGB565 三个分量；像素、坐标、帧/行事件和协议错误统一延迟一拍。项目自有 TB 覆盖黑/红/绿/蓝四像素、两行坐标、事件保持和奇数字节错误，并以 Questa 编译 0 error/0 warning、行为返回 0、唯一 `TEST PASS` 作为当前证据。该切片不覆盖 SCCB、板级、CDC/FIFO、DDR3、PCIe 或后级实现；`parallel_driver` 仅只读参考。

## main OV5640 M3-A 128-bit 图像字

M3-A 在同一 `cam_pclk` 域承接 M2-A 灰度 RGB565 流。`rgb565_word_packer` 将像素 0..7 按接收顺序放入 `word_data` 从低到高的八个 16-bit 槽位；完整字含 8 像素且 `word_keep=16'hffff`，N 像素部分行尾字补零并只置 keep 低 `2N` 位。两个 M3-A TB 按新协议区分 payload（`word_valid && word_keep!=0`）与纯控制事件（`word_valid=1`、`word_keep=0`）。Questa Sim-64 2021.1 的 6 模块集成行为仿真为 0 error/0 warning、返回 0、唯一 `TEST PASS`。该内部布局不定义 DDR3 地址、PCIe AXIS `tkeep`、TLP payload 或主机内存字节序。

## main OV5640 M3-B 溢出帧中止与恢复

M3-B 的两槽 word skid 位于无背压 packer 与 4-byte adapter 之间。满队列且无同拍出队时，溢出前已经排队的 word 构成可保留前缀；触发 word 和当前帧余量被丢弃，前缀后恰好注入一个 `keep=0/frame_end=1/protocol_error=1` 空载中止记录，使下游可以识别并作废不完整帧。`source_overflow` 是复位周期内 sticky 的输入损失事实，不等同于无损或自动回收。

恢复需要两个先决条件同时成立：已经观察到被丢弃原帧的帧尾，且唯一中止记录已经排队。随后只接受带 `frame_start` 的新输入；在条件成立前到达的新帧整帧跳过，避免帧中段或过早新帧泄漏。Questa 2021.1 专项回归扩展为 526 ns，新增覆盖满队列同拍 pop/push、原 `frame_end` 与 abort 入队同拍、连续两个损坏帧各自产生唯一 abort 且顺序正确，以及 drop/abort 状态异步复位；联合 DVP→CDC 回归保持 2863 ns。两项均为 0 error/0 warning、日志唯一 `TEST PASS`，联合压力仍为 20 个 beat（含 1 个中止）并验证下一帧恢复 2 个 beat。该证据仍不覆盖中止记录经真实 DDR3/PCIe/主机协议保存、DDR3 无效帧回收、静态 CDC/RDC、复位释放或板级时序。

## main OV5640 M3-B canonical MWR32 TX 单 DWORD 边界

normalized MWR length 字段已从 DWORD-1 改为实际 DWORD 数，payload request 固定为 `1`。`keep=0` 控制记录在 descriptor 本地接受，不产生 MWR，不推进 PCIe 字节地址；partial keep 仍未有可验证的 canonical byte-enable 映射。

旧 50H 文件名行为切片 `tb_rgb565_pg2l50h_mwr32_tx_integration` 直接把项目 bridge 连到未修改 `ips2l_pcie_dma_mwr_tx_ctrl`。Questa Sim-64 2021.1 仿真至 136 ns，0 error/0 warning、日志唯一 `TEST PASS`；动态检查覆盖 req 保持至 ACK、header length=`1`、DWBE=`0x0f`、地址 `0x1000`、数据低 DWORD=`0x44332211` 和 busy 释放。该旧证据仅限单 DWORD、`keep=4'hf`、4 字节对齐的 vendor TX 隔离仿真，不批准 50H，仍待 PG2L100H IP 复核。

## main OV5640 M3-B 旧 50H 文件名行为切片：PCIe TX 请求仲裁边界

旧 50H 文件名行为切片 `rgb565_pg2l50h_pcie_tx_request_arbiter` 在 PCIe TX 时钟域内仲裁完整 native `MWR32/MWR64/MRD32/MRD64` bundle 与 camera MWR32。native 的 request type、MWR user-defined 模式、length/address/data 原子选择；owner 与字段保持到匹配 ACK，ACK 只返回当前 owner。空闲同拍竞争按上次完成 owner 轮转，复位后 native 先行。MWR 模式在 MWR ACK 时锁存，native MRD 不改变该模式，并保持到下一次 MWR。匹配 ACK 后进入 `WAIT_ACK_LOW`，vendor ACK 拉低前不得换 owner或发布下一事务；正式集成只面向 PG2L100H。

增强专项 TB 为 265 ns；native RAM-data 与 camera user-defined 通过未修改 vendor MWR TX 的集成 TB 为 205 ns。两者均为 0 error/0 warning、日志唯一 `TEST PASS`。这关闭的是 PCIe 域项目仲裁合同，不是完整 PCIe 顶层；异步 camera 请求由下述 mailbox/wrapper 接入，`ips2l_pcie_dma_tx_top`/产品顶层实例化、partial keep/byte enable、PCIe 链路和 RK3568 仍未关闭。

## main OV5640 M3-B DDR→PCIe MWR32 异步事务边界

旧 50H 文件名行为切片 `rgb565_pg2l50h_pcie_mwr32_async_mailbox` 以单 outstanding toggle handshake 把 length/address/data 从 DDR `core_clk` 传到 PCIe `pclk_div2`。源端只在目标真实 ACK 后回应上游，目标端寄存并保持请求字段；源 request 撤销前保持源 ACK，目标 ACK 撤销前停留 `WAIT_ACK_LOW`。在线 reset handshake 在双方 channel-ready 前阻止新请求；idle 单域复位可重对齐，在途任一域复位则产生 fault、事务结果不确定且不 replay，要求上层作废当前 frame/slot 并协调 flush。该行为不批准 50H，placed-design 只按 PG2L100H 签核。

旧 50H 文件名行为切片 `rgb565_pg2l50h_pcie_tx_cdc_arbiter` 将该 mailbox 与现有 native/camera 仲裁器组合。2026-09-04 Questa Sim-64 2021.1 的 mailbox 双速率/复位专项为 2296 ns，CDC arbiter→未修改 MWR TX 集成为 385 ns，均 0 error/0 warning、唯一 `TEST PASS`。因此行为级 DDR→PCIe CDC 已实现；PG2L100H placed-design payload max-delay/bus-skew、CDC/RDC/STA 仍须签核。

## main OV5640 M3-B 完整 PCIe TX top 行为边界

旧 50H 文件名行为切片 `rgb565_pg2l50h_pcie_tx_top_adapter` 在项目自有边界内把上述 CDC/仲裁请求 bundle 接到未修改的完整 `ips2l_pcie_dma_tx_top`，并透传三路 AXIS TX、BAR0/BAR2 读口和 CPLD 输入。非谐波双时钟专项依次发送 native user-defined MWR 与 camera MWR，检查完整 TX top 输出四个正确的 header/data AXIS beat；2026-09-04 Questa Sim-64 2021.1 仿真至 385 ns，0 error/0 warning、日志唯一 `TEST PASS`。该证据不批准 50H，必须在 PG2L100H Endpoint/IP 下复核。

该证据只关闭“camera/native CDC/仲裁请求到完整 TX top AXIS 输出”的行为集成缺口。AXIS 输出不是链路完成或主机内存可见的证明；LTSSM、PCIe 串行链路、真实 DDR3 IP、RK3568 主机内存、产品顶层与板级闭环仍未关闭。

## main OV5640 M3-B canonical DDR→完整 TX top 统一策略边界

旧 50H 文件名行为切片 `ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline` 将 `cam_pclk/cam_rst_n`、`io_clk/io_rst_n`、`pcie_clk/pcie_rst_n` 固定为三个独立域；待 PG2L100H 复核的 DDR 行为接口、逐记录策略和 mailbox 源端位于 IO 域，完整 TX top 位于 PCIe 域。它只放行 `req_keep=4'hf`、`req_length=1`、无 `req_protocol_error`、不跨 4 KiB 的请求，形成明确的 `FULL_DWORD_ONLY` 边界。

任何 policy-invalid 有效请求都不会进入 TX adapter，也不会获得 ACK。上游保持请求并 fail-stop，IO 域首次阻断产生一个 `tx_policy_fault_pulse`，sticky 保持到复位；恢复需要 camera/IO/PCIe 协调复位，不能伪造 ACK 或自动重放。`frame_done_pulse` 仍是 DDR 读出/请求路径接受事件，不是完整 TX top、TLP、PCIe 链路或 RK3568 主机完成。

2026-09-04 的统一 TB 在同一仿真中跨过 DVP、canonical DDR 行为存储、异步 mailbox 和完整 TX top，Questa Sim-64 2021.1 至 1996 ns，0 error/0 warning、日志唯一 `TEST PASS`。它验证 3 条 full-DWORD MWR32、Requester ID、地址/数据/TLAST、AXIS0/1 静默、partial-DWORD 无 ACK fail-stop 及 policy pulse/sticky；真实 DDR3 core、placed-design CDC/RDC/STA、PCIe PHY/LTSSM/链路和 RK3568 软件仍是外部证据缺口。

## main OV5640 M3-B canonical DDR3 用户口

`rgb565_axis4_ddr3_write_descriptor` 把 32-bit payload 放在记录低 4 byte，第 5 byte 的 bit `[3:0]/[4]/[5]/[6]` 保存 `keep/last/frame_end/protocol_error`，并固定 `write_strb[4]=1`。因此即使 `keep=0`，控制记录仍会写入元数据 byte，而不是在 DDR 写路径被本地消费。

旧 50H 文件名行为切片 `rgb565_pg2l50h_ddr3_write_adapter` 将记录映射到非标准 AW/W 口；同类切片 `rgb565_pg2l50h_ddr3_read_adapter` 将 scheduler 命令映射到 AR/R 口。专项 write/write path/read 为 221/196/191 ns，均 0 error/0 warning、唯一 `TEST PASS`。这些结果只证明公开端口行为，不批准 50H；正式集成前必须用 PG2L100H DDR3 IP 重新核对 `ddr_init_done`、AW/W/AR/R 握手、地址单位和无 `axi_rready` 假设。

旧 50H 文件名行为切片 `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline` 串接双槽主链和待 PG2L100H 复核的 AW/W→AR/R adapters；端到端 TB 在其 MWR32 输出后接入异步 mailbox、native/camera 仲裁与未修改 vendor MWR TX。2026-09-04 的更新回归为 1086 ns，验证第 5 byte 元数据跨 DDR 存储边界恢复、`core_clk`→`pclk_div2` 和两组 TLP header/data。该证据不批准 50H；这里的 DDR 是公开端口模型，不是加密 core，正式地址单位/槽范围、PG2L100H placed-design max-delay/bus-skew、CDC/RDC/STA、产品顶层、partial keep、链路、RK3568 软件及板级资料仍未关闭。

## main OV5640 M3-B 帧提交、作废与已提交帧回送

`rgb565_axis4_frame_commit` 把帧级协议结果收敛为 committed 或不可提交描述符，并保留首条记录的 opaque token、首 slot id、记录数、有效字节数与错误状态；同帧 slot id 改变会并入协议错误。该扩展先在旧 RTL 上于 47 ns 红灯，最终专项 Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、240 ns。`rgb565_axis4_frame_read_scheduler` 从首 token 起按记录数生成单 outstanding 顺序命令，并统一响应接收与完成语义：命令和零延迟响应可同拍；提前帧尾或最终响应缺失帧尾均归一化为帧尾并 fault-complete；committed 零记录也直接 fault-complete。scheduler 专项为 346 ns，readout gate 以 `read_accept_enable` 配对响应并以 `frame_done_pulse` 关闭窗口，专项为 211 ns，均 0 error/0 warning、唯一 `TEST PASS`。opaque token 只是数组索引，不是 DDR3 物理地址。

`rgb565_axis4_frame_slot_table` 管理双槽生命周期。正常槽状态只沿 `FREE→WRITING→QUEUED→READING→FREE` 前进，错误帧沿 `WRITING→FREE` 回收；写分配采用保持型 valid/ready 并携带 slot id、槽基 opaque token 与 record capacity，正常描述符进入深度 2 committed FIFO。内部 `reader_active` 限制任一时刻仅一个槽处于活动读取，`read_done` 必须匹配 active slot；错槽、重复或迟到完成只报告 fault，不释放任何槽。专项 TDD 经历目标 RTL 缺失和连续 ready 场景 126 ns 两次红灯，最终为 0 error/0 warning、唯一 `TEST PASS`、436 ns。

`rgb565_axis4_committed_pcie_mwr_path` 已实例化槽表并把带槽 committed 描述符交给 scheduler/readout gate；scheduler 完成时携 slot id 回收匹配 READING 槽。专项结果为 0 error/0 warning、唯一 `TEST PASS`、656 ns，并验证空控制响应零 MWR但正常回收槽。旧顶层 `ov5640_dvp_rgb565_ddr3_pcie_pipeline` 保留 4194 ns 双槽控制面证据；旧 50H 文件名行为切片 `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline` 加入待 PG2L100H 复核的 DDR 用户口适配并形成 806 ns 行为证据。两者均不批准 50H，也不证明加密 DDR core、正式地址单位/槽范围、完整 PCIe DMA/链路、RK3568 主机接收或板级时序。

厂商异步 FIFO 可以承担多比特数据跨域，但 reset/flush 仍属于 RDC。write FIFO 的 camera/UI 两侧和 read FIFO 的 UI/pixel 两侧必须分别在本地时钟域释放复位；只有确认 SP6.4 对厂商指针同步结构的识别后，才允许添加最窄范围例外。

## 复位域交叉

各时钟域应明确复位来源和释放方式。外部异步条件或其他时钟域状态直接释放复位会形成 recovery/removal 风险，应采用异步置位、同步释放或等效的经验证结构。

## 时序闭环

`All Constraints Met` 只覆盖已建模路径。验收还需检查未约束时钟、未约束关键 I/O、CDC 报告、setup/hold/recovery/removal、SDF 标注与板级接口假设。

## PDS 生成物与可重复构建

GUI 原生工程目录中的日志、数据库和绝对路径脚本是历史证据，不是可移植构建入口。目标结构应以相对路径脚本和统一 `build/` 目录隔离生成物。

## RTL 卫生与板级接口边界

## VSCS 注释治理

后续手写 Verilog/SystemVerilog 应记录设计意图、接口契约、FSM、复位、CDC/RDC 和风险，不重复可以从代码、Git 或工具报告自动推导的事实。
## Endpoint AXIS 域

Endpoint AXIS boundary 位于完整 TX top adapter 与产品 `pcie_test` 之间，接入合同见 `docs/MAIN_OV5640_PCIE_ENDPOINT_INTEGRATION_CONTRACT.md`。Endpoint 拥有用户时钟/复位和 ready，项目拥有 valid/data/last/user；AXIS2 承载 camera MWR。当前只完成等端口模型行为验证，AXIS 接线不等于 PCIe 链路或主机内存完成。
