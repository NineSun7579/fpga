# main OV5640 M3-B DDR3/PCIe 适配层合同

更新日期：2026-09-04

## 范围

本合同只冻结 M3-A 内部 128-bit 图像字到后续 DDR3 帧缓存、PCIe DMA 输入之间的职责边界和待决接口字段。它不修改厂商 IP、PCIe/DDR3 RTL、FDC/RCF 或物理管脚，也不把 `parallel_driver` 作为实现来源。

## 已核对的接口事实

- M3-A 输出的 `word_data` 为 128 bit，内部 `word_keep` 为 16 bit；每个 RGB565 像素占两个连续 byte lane，部分字只使低 `2N` 个 lane 有效。
- 活动 PCIe DMA 接口的数据宽度为 128 bit，但其 `tkeep` 只有 4 bit；同时存在 `tvalid/tready/tlast/tuser`，不能把 M3-A 的 16-bit `word_keep` 直接连接到 PCIe。
- PCIe DMA 发起路径另行使用 10-bit `req_length`、64-bit `req_addr`、32-bit `req_data` 和 `cross_4kb_boundary`；请求描述与数据流不是同一个接口。
- PCIe Memory Write 控制器按配置的最大 payload 分段，分段地址递增按 4-byte 单位计算；最大 payload 编码与实际字节数的映射必须由 PCIe IP/协议资料和 TB 冻结，不能由 M3-A 推断。
- 活动 DDR3 用户接口为 128-bit `axi_wdata/axi_rdata`、16-bit `axi_wstrb`、28-bit地址字段和 4-bit `axi_awlen/axi_arlen`；当前源码显示它不是完整 AXI4，写数据接受依赖 `axi_wready`，读侧没有 `axi_rready`。

## 适配层职责

适配层必须独立承担以下工作：

1. 将 M3-A 的 16-byte 内部字拆分为 PCIe 可接受的 4-byte lane 有效信息，或在确认 PCIe 语义后选择明确的聚合/缓存方式；不得截断 `word_keep`。
2. 将部分行尾字的有效字节数、帧/行边界和协议错误转换为 DDR3 写掩码、帧描述信息或显式错误状态；控制事件不得因无 payload 而静默丢失。
3. 为 DDR3 写入和 PCIe Memory Write 分别提供地址、长度、边界拆分和完成/错误状态；不能把 DDR3 地址直接解释为主机物理地址。
4. 在 `cam_pclk`、DDR3 `core_clk` 和 PCIe 用户时钟之间使用经审核的 FIFO/握手 CDC；M3-A 当前同域行为证据不能替代 CDC 证明。

## 当前禁止事项

- 禁止将 `word_keep[15:0]` 直接接到 PCIe `tkeep[3:0]`。
- 禁止把 `word_data` 的 bit/byte 槽位直接宣称为 PCIe TLP payload 或主机内存字节序。
- 禁止在未确认 DDR3 地址单位、burst 语义、容量和 `axi_wready` 完成语义前编写帧缓存地址发生器。
- 禁止在未取得主机协议资料前确定 BAR/寄存器编码、目标地址来源、帧头格式、最大 TLP payload 或 4 KB 拆分策略。
- 禁止修改 `ip_core/**`、canonical PCIe/DDR3 IP、FDC/RCF 和历史 `parallel_driver` 资产来绕过上述缺口。

## M3-B 关闭条件

以下资料齐备并通过一次独立审核后，才允许进入适配层 RTL/TB：

- PCIe AXIS `tkeep` 的 byte lane 语义、`tuser` 编码、最大 payload、4 KB 边界和 Memory Write 请求寄存器协议；
- DDR3 控制器地址单位、burst/`axi_awlen` 语义、初始化完成时序、写掩码和读返回边界；
- 图像帧尺寸、有效字节数、帧描述符、主机目标地址分配和丢帧/超时/错误恢复策略；
- 三个时钟域的频率、复位释放和 FIFO 深度/吞吐预算。

## 当前结论

当前已完成板级无关 staging、canonical DDR3 用户口适配、双槽行为帧缓存、跨域请求仲裁以及完整 PCIe TX top 的行为接线和自检，但不能声称已经具备“OV5640 输入、DDR3 缓存、PCIe 处理后图像输出”的可上板闭环。剩余缺口集中在真实 DDR3 core、产品顶层、物理链路、RK3568 主机协议与板级约束。

## Staging adapter 方案

`rgb565_word_to_axis4_adapter` 作为本合同的板级无关行为实现：每个 128-bit
输入字最多拆成四个 32-bit beat，按低 byte lane 到高 byte lane 输出；最后一个
beat 的 `out_keep` 表示该片段的有效 byte 数。`out_user[0:4]` 分别承载首帧、首行、
行尾、帧尾和协议错误事件，空载控制事件使用 `out_keep=0`。该 `out_user` 只是
项目 staging 编码，不等同于厂商 PCIe `tuser` 编码。

`rgb565_axis4_frame_accounting` 在 staging beat 流上累计有效字节、有效 beat
和协议错误，并在 `in_user[3]` 帧尾被接受后产生固定描述符。该描述符只提供后续
DDR3/PCIe 请求层所需的帧统计输入，不包含地址分配、TLP 长度或 DDR3 burst 语义。

当前已新增同域联合 wrapper `ov5640_dvp_rgb565_dma_staging_pipeline` 并完成 3 像素
行为自检。wrapper 显式连接 accounting `in_ready`，不把 `desc_ready` 直接当作数据
通道 ready；同时用一位 `frame_end_pending` 将 M3-A 无 payload 帧尾对齐到最后一个
staging payload beat。该挂起策略只用于当前无背压的同域 staging 验证，不能替代后续
真实 FIFO/CDC 的事件排队设计。

## 临时 DDR3 写记录层

`rgb565_axis4_ddr3_write_descriptor` 将一个 staging beat 转换为单 beat、128-bit
数据和 16-bit 写掩码记录，并在下游 ready 前保持字段稳定。其 28-bit 地址只是
opaque token，推进量由 `ADDR_STEP` 参数显式提供；`write_awlen=0` 只表示本模块
输出一个记录，不代表活动 DDR3 IP 的
地址单位、burst 长度或初始化完成语义。该层不实例化 DDR3 IP，必须在 50H IP 重生成
并完成 D3-0-M 复核后，才能进行实际用户口映射。

## PCIe 请求描述边界补充

对活动 PCIe DMA 控制器的手写 RTL 只读核对得到以下事实：`req_addr` 由高、低地址
寄存器拼接；`req_length` 是实际 DWORD 数，在控制器内部转换为字节长度参与
4 KB 边界判断；`req_data` 是 32-bit 请求数据。当前控制器以独立的 `i_mwr32_req` /
`i_mwr64_req` 及对应 ack 驱动内部状态机，不能把这组端口直接宣称为标准
`valid/ready` 请求接口。

因此后续应先新增板级无关的“规范化 PCIe Memory Write 请求描述符”接口，至少包含
目标地址、有效字节数、32-bit 数据、帧尾和错误状态，再由专用 vendor bridge 映射
到 `req_length/req_addr/req_data/i_mwr*_req`。在该 bridge 的启动、ack、busy 和
4 KB 分段语义获得 TB 证据前，不修改活动 PCIe IP 或把 staging stream 直接接入。

## 临时请求桥接层

`rgb565_axis4_pcie_mwr_bridge` 已作为独立手写 RTL 实现初步桥接：它锁存规范化请求，
将请求保持到 `mwr32_req_ack`，并保持 `req_length/req_addr/req_data/req_keep`、
4 KB 状态及 `last/frame_end/protocol_error` 稳定。事件元数据必须与地址和数据一起在
bridge 内锁存；否则 descriptor 在 bridge 忙时预取下一记录会使当前请求与下一记录事件
错配。该模块不实例化厂商 PCIe IP；`req_keep` 仅作为旁路信息保留，因为
活动控制器的请求端口没有独立 byte-enable 输入。该 byte-enable 映射、请求启动和
ack 关系已由直接实例化 canonical MWR TX controller 的 TB 审核。该 TX 控制器固定 full-DWORD
byte enable，因此当前只有 `req_keep=4'hf` 可无损映射；`req_keep=0` 由 descriptor 本地完成，
其余 partial keep 仍不得直接进入该 vendor TX 路径。

## 规范化 MWR 组合路径

`rgb565_axis4_pcie_mwr_path` 已将 staging beat、规范化 MWR descriptor 和临时请求桥
串接。2026-09-03 的专项 TB 使用 `BASE_ADDR=0x0ffc`：4-byte 请求恰好到达 4 KB
边界时不标记 crossing；首请求等待 ack 时 descriptor 预取下一条带帧尾/错误的记录，
首请求的地址、数据、keep、last、帧尾和协议错误仍保持不变，ack 后下一请求地址为
`0x1000`。Questa Sim-64 2021.1 编译 `0 error/0 warning`、唯一 `TEST PASS`，仿真至
`125 ns`；bridge 独立字段保持回归为 `76 ns`。

## PG2L50H canonical MWR32 TX 动态证据

`tb_rgb565_pg2l50h_mwr32_tx_integration` 将项目自有 bridge 直接连接到未修改的
`ips2l_pcie_dma_mwr_tx_ctrl`，并固定 `i_user_define_data_flag=1`。2026-09-03 的 Questa
回归在 `136 ns` 唯一 `TEST PASS`，编译和仿真均为 `0 error/0 warning`。测试证明请求字段保持到
PG2L50H TX 的保持型 ACK、单 DWORD header length 为 1、First/Last DWBE 为 `8'h0f`、32-bit 地址字段为
对齐后的 `0x1000`，输入 `0x11223344` 的数据 beat 低 DWORD 为 `0x44332211`，且 bridge/vendor busy
最终释放。

该证据只适用于单 DWORD、`keep=4'hf`、4 字节对齐请求。ACK 只表示 TX 控制器接受请求；它不证明
TLP 已离开 FPGA。完整 `ips2l_pcie_dma` 内部仍有原命令控制器，项目请求源的仲裁/替换入口尚未实现，
也未证明 PCIe 链路训练、RK3568 DMA 缓冲或主机内存写入。

该组合路径仍不实例化厂商 PCIe IP，不证明真实 TLP、DMA、byte-enable、链路、主机
地址或 PCIe 控制器启动/忙状态；真实接入必须继续使用活动控制器的链路模型和实现级证据。

## OV5640 到 CDC staging 联合切片

`ov5640_dvp_rgb565_cdc_staging_pipeline` 已串接 OV5640 DVP 采集、图像处理、128-bit
打包、4-byte adapter 和双时钟 CDC bridge。2026-09-03 的小帧 TB 使用 `cam_pclk`
与独立输出时钟，验证 2 个 staging beat 的有效字节、帧/行事件和跨域到达；Questa
Sim-64 2021.1 编译 `0 error/0 warning`，唯一 `TEST PASS`，仿真至 `413 ns`。

该测试同时观察到 camera-side packer 无输入背压：在 adapter/FIFO 接收能力不足时，
`source_overflow` 被置位。当前实现会保留已排队前缀、注入空载错误帧尾并丢弃余帧，
随后只从后续 `frame_start` 恢复。该策略保证损坏帧可识别，不是无损保证；真实帧缓存
仍需按吞吐预算确定 FIFO 深度，并在 DDR3 侧回收带协议错误的帧。

## 源端短突发缓冲

`rgb565_word_skid_buffer` 位于无背压的 `rgb565_word_packer` 和
`rgb565_word_to_axis4_adapter` 之间，保存两个 128-bit word 及完整事件字段。其输入
沿用 packer 的 `word_valid` 脉冲，`in_ready` 只用于判断当前是否还有槽位；不能把该
信号反向连接成 packer 的输入背压。输出仍是标准 `valid/ready`，下游暂停时已保存
word 的所有字段保持，满队列同拍出队/入队时允许直接替换尾槽。

当 `in_valid` 到达且两个槽位都不能接收时，模块丢弃该新 word 并将 `overflow` 粘滞
置 1。已排队前缀继续按 FIFO 顺序输出，随后插入唯一的
`keep=0/frame_end=1/protocol_error=1` 中止记录；当前帧剩余 word 全部丢弃。只有已看到
原帧尾、中止记录已经排队且后续输入带 `frame_start` 时才恢复接收。若持续背压使紧邻
的新帧首无法保存，则继续丢弃该整帧，避免从帧中段恢复。恢复依赖 packer 最终产生
`frame_end`；若源端边界永久缺失，只能通过复位退出丢帧状态，不使用超时猜测边界。

专项 TB 覆盖两个 word 在下游暂停期间按顺序排出、第三个 word 触发 overflow、余帧
丢弃、中止记录排队前提前到达的新帧整帧跳过、唯一中止记录、后续帧恢复、满队列
同拍出入队、丢弃侧帧尾与 abort 同拍、连续损坏帧及 drop 状态复位；
Questa Sim-64 2021.1 编译 `0 error/0 warning`、唯一 `TEST PASS`、仿真至 `526 ns`。联合 TB 覆盖 3 个正常 staging beat、64 像素
下游暂停压力帧的 20 个输出（含末尾唯一中止记录），以及下一帧 2 个正常恢复 beat；
Questa 编译 `0 error/0 warning`、唯一 `TEST PASS`，仿真至 `2863 ns`。

## 行为级 DDR3 到 PCIe 往返证据

`tb_ov5640_ddr3_pcie_loopback` 通过现有公开接口串接 DVP 采集、灰度/打包、双时钟
staging、规范化 DDR3 写记录、受控存储模型和 PCIe MWR 请求路径。3 像素帧生成两个
payload 记录和一个空载帧尾记录，读回后 PCIe 地址按有效字节从 `0x0ffc` 推进到
`0x1000`、`0x1002`。扩展场景阻塞 DDR 写端并输入 64 像素，camera-side overflow 后
DDR 模型动态保存 21 条压力记录，唯一 `keep=0/frame_end=1/protocol_error=1` 中止记录
位于索引 20；随后 1 像素恢复帧写入两个正常记录。全部记录回读到 PCIe MWR 后，中止
记录和恢复 payload 的请求地址均为 `0x104c`，验证空载中止不会推进图像字节地址。
最终 Questa Sim-64 2021.1 回归为 `0 error/0 warning`、唯一 `TEST PASS`，
仿真至 `3844 ns`。DDR3 记录模型在 `posedge` 的 `valid && ready` 握手边沿采集写事务，
避免在握手完成后延迟到 `negedge` 采集而漏记最后一条控制记录。

DDR3 模型中的 28-bit 地址只作为记录槽位，未映射到活动控制器的真实地址单位；模型
读回也不代表活动 DDR3 IP 的 `axi_arvalid/axi_rvalid/axi_rlast` 时序。PCIe 请求仍由
临时 `mwr32_req/ack` bridge 接收，不证明 TLP byte enable、DMA、链路训练或主机内存
写入。该测试是后续真实控制器连接的回归合同，不能作为板级闭环验收证据。

## 帧提交、作废与 PCIe 读出门控

`rgb565_axis4_frame_commit` 在规范化 DDR3 记录帧尾生成保持型描述符，保存该帧首个 opaque
DDR token 和 slot ID，并统计有效字节、记录数和累计协议错误。同帧记录切换 slot ID 会被
聚合为协议错误。无错误帧输出 `committed=1`；包含
overflow abort 或其他协议错误的帧输出 `committed=0`。空载帧尾仍计入记录数，但不增加
有效字节。首 token 只是上游已经使用的记录标识，不是物理 DDR3 地址。

## 双槽帧表控制面

`rgb565_axis4_frame_slot_table` 管理两个固定槽基 token，槽生命周期只允许
`FREE→WRITING→QUEUED→READING→FREE`；错误帧走 `WRITING→FREE`。写分配使用寄存保持的
valid/ready 描述符，避免背压期间 free 槽变化导致 slot ID 漂移。可提交帧按完成顺序进入深度 2
FIFO，reader active 时第二个 committed 帧仍可排队，但不会暴露第二个读描述符。

分配描述符同时携带 slot ID、槽基 token 和 `SLOT_RECORD_CAPACITY`，writer 在帧开始前原子锁存，
使槽表成为容量单一事实源。writer 的容量内记录按 `ADDR_STEP` 推进；越界后地址停在本槽最后
一个 token，并从首条越界记录起强制 protocol error，继续接受到帧尾后 fault-drop，不跨入另一槽。

读完成必须携带当前 active reader 的 slot ID；错误、重复或迟到完成只产生 fault，不释放任何槽。
零记录、超过 `SLOT_RECORD_CAPACITY`、错误首 token 或 committed/error 决策矛盾的描述符均
fault-drop。正确 WRITING 槽若提交错误首 token，会释放该槽，避免永久泄漏。
专项 TB 覆盖两个槽同时 WRITING、两个 committed 排队、描述符背压、持续 ready 下单 reader、
错误完成、错误帧回收、超容量帧、合法 `commit+read_done` 同拍和运行中复位。连续-ready 测试在
旧实现于 `126 ns` 红灯；修复后 Questa Sim-64 2021.1 为 `0 error/0 warning`、唯一
`TEST PASS`；增加容量随分配输出和错误首 token 回收后，最新专项为 `436 ns`。

`rgb565_axis4_frame_read_scheduler` 只为 committed 描述符产生读命令，从首 token 起按
`ADDR_STEP` 推进；每次只允许一个响应 outstanding，命令在背压时保持，收到对应记录被后级
接受的事件后才推进下一 token。命令和零延迟响应允许同拍；提前帧尾或最后计数响应缺少帧尾
都会结束当前帧、归一化输出帧尾并报告 fault；committed 零记录描述符直接 fault 完成，不进入
无命令 active 状态。专项回归以非默认 `ADDR_STEP=4` 覆盖上述边界、背压、响应配对和运行中复位，Questa Sim-64
2021.1 为 `0 error/0 warning`、唯一 `TEST PASS`、`346 ns`。

`rgb565_axis4_frame_readout_gate` 只为 `committed=1` 的帧打开 DDR3 记录读出窗口；作废帧
不拉高读侧 ready，并产生一个单周期 `drop_frame_pulse`，供后续帧表回收对应槽位。已提交
帧的读回记录只有在 scheduler 声明可与当前命令配对时才按 ready/valid 透传；窗口由 scheduler
统一产生的 `frame_done_pulse` 关闭，不再独立依赖原始 `read_frame_end`。读出源可以独立拉高
valid，但必须在握手前保持全部字段；外部调度器不得为作废帧安排读记录。

`rgb565_axis4_committed_pcie_mwr_path` 已将 frame commit、双槽表、读命令调度器、读出门控与
规范化 PCIe MWR path 串接。frame commit 描述符完整进入槽表；槽表队首只在 scheduler 和 gate
均 ready 时原子出队。scheduler 描述符锁存 slot ID，正常或读协议 fault 完成都用
`frame_done_pulse/frame_done_slot_id` 回收匹配 READING 槽；错误帧的
`drop_frame_pulse/drop_slot_id` 只由槽表产生。组合 path 最新专项为 `696 ns`。

`ov5640_dvp_rgb565_ddr3_pcie_pipeline` 是当前 vendor-independent 可综合顶层。writer 记录先通过
外部 `ddr_write_valid && ddr_write_ready`，下一阶段才送 frame commit；等待 commit 时禁止重复
DDR 写 valid，并保持记录字段，因此提交不会早于模型持久化边界。scheduler 的 done 表示最后一条
DDR 读响应已被本地 PCIe 请求路径锁存，允许复用 DDR 槽；它不表示 PCIe ACK 或主机已经收到帧。

`tb_ov5640_ddr3_committed_pcie_loopback` 直接实例化该顶层：读侧阻塞时，两个正常帧分别写入
slot0 token `0..2` 和 slot1 token `64..65`，随后按提交顺序回送 PCIe；slot0 完成后由第三帧
重新写入 token `0..1`。64 像素压力错误帧形成 21 条记录，只产生一次 slot0 drop、零读命令和
零 MWR；恢复帧使用 slot1 token `64/65`。Questa Sim-64 2021.1 为 `0 error/0 warning`、唯一
`TEST PASS`、`4194 ns`。其中 payload 请求使用实际 DWORD 长度 1，空控制响应不生成 MWR，
但仍完成 scheduler 计数和带槽回收。

该闭环仍以数组索引解释 DDR token，以规范化 `mwr32_req/ack` 表示 PCIe 请求。它不实例化
PG2L50H DDR3/PCIe IP，不证明真实地址单位、初始化/校准、读口时序、TLP、DMA、链路训练、
RK3568 主机内存写入或板级时序。

## PG2L50H canonical DDR3 读写应用边界

`rgb565_pg2l50h_ddr3_write_adapter` 已按生成 example 的非标准写协议实现单 outstanding：init 同步
完成后预锁存一条记录，保持 AW 到 `axi_awready`，再保持 data/strobe 到 `axi_wready`；上游只在
数据拍被用户口消费时完成。单拍固定 `AWLEN=0`，无 B channel，因此完成不表示物理 DRAM 持久化。

`rgb565_pg2l50h_ddr3_read_adapter` 已按 canonical AR/R 端口实现四状态单 outstanding。读口不存在
RREADY，因此返回拍必须无条件进入本地寄存器，再以 ready/valid 送给帧读出链。单拍固定
`ARLEN=0`；RID 不匹配、RLAST 缺失随记录标记错误，无 outstanding 或输出占用时的额外 RVALID
产生独立 port fault。AR 与 R 同拍返回也已覆盖。

仅凭 committed descriptor 的 `bytes/records` 不能唯一恢复任意逐记录 keep，也不能恢复 staging
`last`。当前格式因此把 payload 保存在 `WDATA[31:0]`，把 keep、last、frame_end、protocol_error
依次保存在 `WDATA[35:32]`、`[36]`、`[37]`、`[38]`；`WSTRB[4]` 始终为 1，低四位仍对应 payload。
这样零 payload 帧尾记录也会真实写入元数据，不依赖分辨率、行宽或总字节数推断。

新增 `ov5640_dvp_rgb565_pg2l50h_pcie_pipeline` 串接现有双槽主链、canonical DDR3 写/读适配器和
MWR32 request/ack 边界。端到端 TB 再实例化未修改的 PG2L50H MWR TX controller。4 像素回归
形成两条 full-DWORD payload 和一条零 payload 帧尾记录，通过地址 `0/8/16` 的 canonical 端口
模型写入/读回，再输出地址 `0x4000/0x4004` 的两组 TLP header/data；Questa Sim-64 2021.1 于
`806 ns` 为 0 error/0 warning、唯一 `TEST PASS`。

`DDR_ADDR_STEP` 在该应用层默认 0 并由 elaboration 拒绝，防止把 example 中每 beat 加 8 的观察值
静默冒充官方地址单位。真实集成仍需匹配当前 IP 版本的用户手册、加密 core 动态验证和板级地址
范围；PCIe 侧仍需完整 DMA 顶层请求仲裁、partial keep 策略、链路和 RK3568 主机证据。

## PG2L50H PCIe TX 双请求源仲裁边界

canonical DMA controller 以同一组 `req_length/req_addr/req_data` 配合 MWR32、MWR64、MRD32、
MRD64 四类请求驱动 TX top，因此 camera MWR32 不能只与 native MWR32 做组合 OR 或单信号 mux。
`rgb565_pg2l50h_pcie_tx_request_arbiter` 将完整 native request bundle 作为一个原子源，并把 camera
full-DWORD MWR32 作为第二源；vendor 生成 RTL 保持未修改。

owner 从空闲仲裁后保持到对应 TX ACK，未选源不会收到 ACK。完成后进入显式 ACK-low 释放状态；
只有下游 ACK 和已完成源请求均拉低才返回 `OWNER_IDLE`，保持型 ACK 不会泄漏到下一源。两源同拍到达使用基于上一完成 owner 的轮转，
复位后的首次竞争优先 native；该策略避免持续同拍竞争时固定饿死 camera，但不声明 PCIe 链路级公平性。

该 MWR TX 不只在 ACK 边沿读取 `i_user_define_data_flag`，其启动、RAM 读使能和 DATA_TX 结束条件
也读取实时电平。因此仲裁器在 MWR ACK 时锁存选中源的数据模式，并持续输出到下一条 MWR ACK 替换；
MRD ACK 不改变该模式。专项覆盖四类 native 请求、camera 请求、字段保持、ACK 隔离、连续竞争、
运行中复位和模式保持，Questa Sim-64 2021.1 为 0 error/0 warning、唯一 `TEST PASS`、`245 ns`。

动态集成 TB 让 native 先以 RAM-data 模式发送一条 MWR32，同时保持 camera user-defined MWR32 等待。
前一事务完成前 camera 不改变实时数据模式；随后 camera 获得 ACK。未修改的
`ips2l_pcie_dma_mwr_tx_ctrl` 最终输出两组独立 header/data，地址为 `0x1000/0x2000`，仿真
`205 ns`，0 error/0 warning、唯一 `TEST PASS`。

增强专项加入保持型 ACK 在请求撤销后继续拉高的场景，最终 `265 ns` 通过。

## DDR core_clk 到 PCIe pclk_div2 事务 mailbox

`rgb565_pg2l50h_pcie_mwr32_async_mailbox` 使用单 outstanding toggle handshake。源域同拍锁存
length/address/data 并翻转请求 token；token 三级同步到 PCIe 域后，目标额外等待一个目标周期再采样
稳定 payload。目标只使用本地捕获寄存器，并保持 MWR32 请求直到真实 ACK；ACK token 返回源域后，
源 ACK 保持到原请求撤销。目标与源端都等待保持型 ACK 的释放状态，不允许同一高电平完成下一笔。

reset/online 使用双向可见握手：本地域复位后 online 保持低，直到 peer 明确观察到该低电平才重新加入。
online 用两级同步而 request/ACK token 用三级同步，使 peer-offline 先于复位导致的 token 改变进入事务逻辑。
idle 单域复位因此可重新对齐 token 且不产生幽灵请求。事务在途时任一域复位会使保留侧置位 fault，
禁止自动重放；恢复要求双方协调复位。该协议不承诺 PCIe exactly-once，在 ACK 或复位边界发生时，
上层必须作废当前 frame/slot 并执行系统级 flush。

payload 是 bundled-data MCP，不是逐位同步。源 holding register 到目标 capture register 必须施加经 PDS
验证的 max-delay/bus-skew 约束；toggle/online/fault 同步器需要 CDC 报告确认。不得用异步 clock-group
或总线 false-path 把 payload 一并隐藏。RTL 仿真只证明协议状态和数据稳定，不能证明亚稳态或位间 skew。

mailbox 专项以两组非谐波时钟覆盖源快/目标慢、目标快/源慢、三笔 token 往返、payload 捕获后上游改值、
ACK 延迟/延长、保持请求防重复、idle 单域复位、在途双向复位 fault 与协调恢复；Questa Sim-64 2021.1
为 0 error/0 warning、唯一 `TEST PASS`、`2296 ns`。`rgb565_pg2l50h_pcie_tx_cdc_arbiter` 再把 mailbox
输出接入完整 native/camera 仲裁器；未修改 MWR TX 的双源动态回归为 `385 ns`。

`tb_ov5640_pg2l50h_ddr3_pcie_loopback` 已将 canonical DDR 行为模型和 PCIe TX 时钟拆分。4 像素帧经
AW/W→AR/R、`core_clk`→`pclk_div2` mailbox、仲裁器和未修改 MWR TX 输出两组 TLP header/data，
`1086 ns`、0 error/0 warning、唯一 `TEST PASS`。

## 完整 PCIe TX top 行为接线

`rgb565_pg2l50h_pcie_tx_top_adapter` 将 `rgb565_pg2l50h_pcie_tx_cdc_arbiter` 的完整请求 bundle
接入未修改的 `ips2l_pcie_dma_tx_top`，并向产品集成层暴露 CPLD、MRD、MWR 三路 AXIS TX、
BAR0/BAR2 读口以及 RX completion 相关输入。adapter 不修改厂商生成 RTL，也不解释 BAR 存储、
RX completion、链路状态或主机 DMA 缓冲所有权。

非谐波双时钟专项先发 native user-defined MWR32，再发送 camera MWR32，验证 AXIS2 上两组
header/data、地址 `0x1000/0x2000`、DWORD length 1、full-DWORD byte enable、Requester ID
`16'h2a18`、数据字节序和 TLAST。AXIS0/1 在无 CPLD/MRD 输入时必须保持无有效流量。Questa
Sim-64 2021.1 于 `385 ns` 返回唯一 `TEST PASS`，编译和仿真摘要均为 0 error/0 warning。

本节关闭的是“项目 CDC/仲裁请求到完整 TX top AXIS 输出”的行为集成缺口，仍不证明产品顶层、
PCIe IP/RX/config/reset/clock 接线、LTSSM、串行链路、RK3568 内存写入、中断完成或 placed-design
CDC/RDC/STA。真正的 exactly-once 还需要事务序号和接收端去重协议。

## 单一 OV5640 到完整 TX top 行为路径

`ov5640_dvp_rgb565_pg2l50h_pcie_tx_top_pipeline` 在一个 camera-only 可综合 wrapper 中连接
`ov5640_dvp_rgb565_pg2l50h_pcie_pipeline` 与 `rgb565_pg2l50h_pcie_tx_top_adapter`。adapter 的
camera 域绑定 DDR 应用 `io_clk`，PCIe TX top 保持独立 `pcie_clk`；native DMA、MRD、CPLD、
BAR read data 和 TX restart 在该边界内明确关断，三路 AXIS 仍对外可见。

完整 TX top 没有逐请求 byte-enable 输入，因此准入条件固定为：`req_keep=4'hf`、
`req_length=1`、`req_protocol_error=0` 且 `cross_4kb_boundary=0`。任一条件不满足时，请求不会
进入 mailbox，也不会收到伪造 ACK；wrapper 在 `io_clk` 产生一次 `tx_policy_fault_pulse` 并保持
`tx_policy_fault_sticky`，原请求维持 fail-stop。恢复必须协调复位 camera、IO 和 PCIe 域，禁止
自动重放。该策略关闭的是错误数据外发风险，不代表 partial-DWORD TLP 发送能力已经实现。

`frame_fault_pulse` 在 IO 域汇总原流水线 fault、camera 侧 CDC fault 和 policy fault；PCIe 侧
CDC fault 仍独立留在 `pcie_clk` 域。`frame_done_pulse` 只表示 DDR 记录被本地请求路径接收，
即使后续 policy fail-stop 也可能已产生，不能解释为 TX ACK、TLP 发出或 RK3568 内存完成。

统一 TB 在非谐波 `io_clk/pcie_clk` 下输入 4 像素和 3 像素两帧。第一帧产生两笔合法
full-DWORD MWR32；第二帧先产生一笔合法 MWR32，再在 partial 记录上 fail-stop。三笔 AXIS2
header/data 的地址为 `0x4000/0x4004/0x4008`，Requester ID 为 `16'h2a18`，TLAST 和数据字节序
正确，AXIS0/1 全程无有效流量。协调复位后 policy sticky 和 camera request busy 清零。
Questa Sim-64 2021.1 于 `1996 ns` 返回唯一 `TEST PASS`，编译和仿真摘要均为 0 error/0 warning。

该统一证据仍使用 canonical DDR3 行为模型，并只覆盖完整 TX top 的 AXIS 输出。加密 DDR3 core、
PCIe IP/RX/config/reset/clock、LTSSM、串行链路、RK3568 DMA/IOMMU/cache、主机帧描述符、中断和
golden image 均未进入本测试，不能据此宣称板级闭环。
