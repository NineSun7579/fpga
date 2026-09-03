# main OV5640 M3-B DDR3/PCIe 适配层合同

更新日期：2026-09-03

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

当前 staging adapter 已完成板级无关的行为实现和自检，但不能声称已经具备“OV5640 输入、DDR3 缓存、PCIe 处理后图像输出”的可综合或可上板闭环。M3-A 只证明内部图像字布局；M3-B 的厂商接口接入仍需资料驱动的转换合同。

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
寄存器拼接；`req_length` 在控制器内部按 DWORD 计数编码，并转换为字节长度参与
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
ack 关系仍是临时合同，必须在真实 PCIe TLP/DMA TB 中重新审核后才能用于产品路径。

## 规范化 MWR 组合路径

`rgb565_axis4_pcie_mwr_path` 已将 staging beat、规范化 MWR descriptor 和临时请求桥
串接。2026-09-03 的专项 TB 使用 `BASE_ADDR=0x0ffc`：4-byte 请求恰好到达 4 KB
边界时不标记 crossing；首请求等待 ack 时 descriptor 预取下一条带帧尾/错误的记录，
首请求的地址、数据、keep、last、帧尾和协议错误仍保持不变，ack 后下一请求地址为
`0x1000`。Questa Sim-64 2021.1 编译 `0 error/0 warning`、唯一 `TEST PASS`，仿真至
`115 ns`；bridge 独立字段保持回归为 `76 ns`。

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
DDR token，并统计有效字节、记录数和累计协议错误。无错误帧输出 `committed=1`；包含
overflow abort 或其他协议错误的帧输出 `committed=0`。空载帧尾仍计入记录数，但不增加
有效字节。首 token 只是上游已经使用的记录标识，不是物理 DDR3 地址。

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

`rgb565_axis4_committed_pcie_mwr_path` 将提交器、读命令调度器、读出门控与现有规范化 PCIe
MWR path 串接。提交描述符只在调度器和门控都 ready 时原子分发，避免两侧帧序失配。
顶层显式以 `TOKEN_ADDR_STEP` 绑定读 token 步长，并向帧管理器输出 `frame_done_pulse` 与
`frame_fault_pulse`，为后续带槽号回收提供事件基础；当前事件尚未携带槽号。
专项回归在读侧存在待发送记录时提交错误帧，确认读窗口保持关闭且没有 MWR 请求；随后
提交正常帧，payload 与空载帧尾分别从 `0x2000`、`0x2004` 发起请求。增强测试还覆盖帧统计、
已打开读窗口和等待 ACK 请求的运行中复位，复位后请求地址重新从 `0x2000` 开始。frame
commit、readout gate 和组合 path 的 Questa Sim-64 2021.1 回归分别为 `210 ns`、`211 ns`、
`576 ns`，均为 `0 error/0 warning`、唯一 `TEST PASS`。

`tb_ov5640_ddr3_committed_pcie_loopback` 把写模型和 commit 接受绑定到同一握手边沿，DDR 模型
只为已接受的调度命令返回记录。正常 3 像素帧由 token `0..2` 产生 `0x2000/0x2004/0x2006`
请求；64 像素压力错误帧形成 21 条记录、一次 drop、零读命令和零 MWR；随后 2 像素恢复帧
只读取 token `21/22` 并从 `0x2000/0x2004` 发送。该回归为 `0 error/0 warning`、唯一
`TEST PASS`、`3158 ns`。

该切片没有带槽号的帧表、槽位分配、槽基 token 重装或真实存储回收逻辑。连续 token 调度
只覆盖当前行为模型，`drop_frame_pulse` 也不等同于实际 DDR3 空间已经回收。
它不实例化厂商 DDR3/PCIe IP，不证明 DDR3 写入持久化、读口时序、TLP、DMA、链路训练、
主机内存写入或板级时序。
