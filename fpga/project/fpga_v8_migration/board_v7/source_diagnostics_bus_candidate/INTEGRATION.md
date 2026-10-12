# 总线隔离候选的接线和驱动合同

本目录实现可评审 RTL；**未接入生产或冻结顶层，未运行 PDS，未上板**。
原 source_frame_diagnostics_candidate 文件保持原样；run.py 对依赖的六个文件固定 SHA256，
变化即停止测试，不会自动接受新的依赖。v7_sdb 内直接实例化四份原 v7_sfd_candidate。

## 实际地址证据和本次修订

冻结 `whole_candidate_v7_route_01/inputs/source/ov5640/axi_to_axi_lite.v`：
第92/123行原样传 AWADDR/ARADDR；第98–99行仅取 WDATA 低32位和 WSTRB低4位；
第130行把 RDATA 低32位补零为128位。它**没有**地址右移，也不把一个128-bit beat拆成四次读。
别名实际发生在更上游：冻结 `pcie_dma/pcie_fifo.v` 第7行AXI_DATA_SIZE=$clog2(128/8)=4；
第358/668行把起始地址写成 `{(fpga_ddr3_addr >> AXI_DATA_SIZE), {AXI_DATA_SIZE{1'b0}}}`，
丢掉低4位；第363/671行按 `(LEN+1)<<4` 步进。故主机的+4/+8/+c会成为相同AXI地址。
适配器无法检测已丢失的地址低位；必须在主机API拒绝不对齐地址，禁止使用原紧密4-byte表。
address_evidence.txt保留字节级提取的源码行和位置。
原 ov5640_reg 的 DBG 寄存器使用 +0x10、+0x20、+0x30 等，保留同样间隔。

新区间严格匹配 `address[31:10] == 22'h080004`，即 `0x20001000..0x200013ff`。
4相机基址依次 0x20001000/1100/1200/1300。每相机0x100只有16个16-byte槽，
原16字段再加控制装不下，因此修订为间接 INDEX/DATA，而不是扩窗或借用旧页。

| 相机内偏移 | 访问 | 含义 |
|---|---|---|
| 0x00 | R | STATUS：bit0 lease有效且会话可用；bit1 overrun；bit2 available；bit3 session invalid/恢复中/epoch耗尽 |
| 0x10 | W | COMMAND：整字1=ACQUIRE，整字2=RELEASE；其他值SLVERR |
| 0x20 | RW | INDEX：0..15，采样于DATA的AR握手；复位初值0 |
| 0x30 | R | DATA：原候选对应word的冻结bank字段；无lease返回SLVERR |
| 0x40 | R | EPOCH：32-bit会话代数；camera reset不能清零，只由整个AXI接口reset清零 |
| 其余全部实际AXI地址 | — | SLVERR，包括+4/+8/+c、未对齐和未定义槽，适配器内绝不别名 |

所有写要求低4位WSTRB=0xf；非法寄存器、超界INDEX、非法COMMAND、恢复中写均SLVERR。
ACQUIRE无available/lease时SLVERR；重复ACQUIRE保留旧lease；无lease RELEASE允许幂等成功。
COMMAND的OKAY表示命令已被接受；camera reset可能紧接着撤销lease，因此必须读STATUS确认。
INDEX不随camera reset清除，DATA始终检查lease和epoch，不会因此读取有效的新会话。
DATA word0..15严格沿用原候选表（旧文档offset/4），包括word15格式常量0x53464401。

## 顶层拟接线

现有 bridge 的全部 `m_axil_*` → 新 `v7_sdb.s_*`；
新 `v7_sdb.m_*` → 原 `ovreg_axil_decode_tc01.s_*`；原decoder的五路输出连接不变。
clk为该AXI接口时钟；rst必须与上游bridge和下游decoder的**整个接口复位**同域同合同。
不能把任意camera reset接到rst。

每相机采样点以冻结 `ov5640_tc03_binding.v` 为依据：

| v7_sdb向量相应bit | 拟连接 |
|---|---|
| cam_clk | cam_pclk |
| raw_vsync | capture实际输入capture_vsync（当前VSYNC_STABLE_CYCLES=0等于cam_vsync） |
| raw_href / raw_byte_accept | cam_href，不额外与!VSYNC相与 |
| capture_vsync | 第358行下降沿寄存后的cmos_frame_vsync_r |
| capture_valid | 第356行下降沿寄存后的cmos_frame_valid_r |
| cam_reset | `!ov_rst_n OR !cam_rst_n`：capture复位加第372行源CDC cam_rst请求 |

这些内部信号尚未从binding导出；未来顶层集成需明确增加诊断旁接端口，不接payload、不回压图像。
fixture.vh提供实际bridge→新RTL→冻结decoder的可编译接线示例；其余slave为行为测试从机。
TB编译实际冻结capture，复现binding不带复位的negedge寄存器，未编译整个binding和整板top。

区间外请求原地址、数据、WSTRB原样送旧decoder，保留CAM/PREP/motion及CDC特殊读路由，
也保留旧decoder在其他高地址上的历史别名。新区间内未知地址全报错；
不能把“新区间未知地址不别名”扩大表述为全地址空间已消除历史别名。
新层增加排队延迟：AW和W独立接收各一项，收齐后先转发AW，握手后才转发W；
此顺序保证冻结decoder的aw_saved归属，不改变旧窗口的功能路由语义。

## AXI事务与camera reset：替代原INTEGRATION第51行

**禁止取消已接受AR或撤销stalled RVALID。** 新合同如下：

1. AXI寄存状态只有rst分支清除。每方向最多一个outstanding，读写可独立并行。
2. AR时捕获完整地址、相机、INDEX和epoch。诊断DATA用固定两拍管线取本地注册结果。
   在响应承诺前，若源read_valid被camera reset清除、read_error、恢复中或epoch变化，
   始终产生一次SLVERR；不会等一个已被复位抹掉的valid而挂死。
3. 一旦s_rvalid=1，RDATA/RRESP保持到RREADY握手。camera reset可以使该旧响应过时，
   **不能**改其数据、改成SLVERR或撤回RVALID。BVALID同理。
4. 每相机reset_pipe异步置位、四拍同步释放，捕捉短于host周期的reset请求，
   也覆盖原候选两拍host复位恢复。每次invalid低→高时epoch加1。
   恢复期内多次reset属于同一不可用会话，不允许ACQUIRE，故不需要逐脉冲计数。
5. epoch到0xffffffff永久fail-closed，STATUS.invalid=1，禁止ACQUIRE/DATA，
   避免回绕ABA；只有整个接口reset可恢复，驱动同时丢弃所有旧事务上下文。

这是RTL状态保持的结构论证加仿真断言，**不是形式验证/物理CDC证明**。
原候选第51行“取消待处理响应”及第46行“无需前后检查”不适用于本总线适配器。

## 主机读取算法（独占每个相机lease，串行完成每次MMIO）

1. 等STATUS.bit3=0且bit2=1，读EPOCH为E0；写COMMAND=1并等B。
2. 读STATUS，要求bit0=1且bit3=0。
3. 对INDEX=0..15分别写INDEX、等B、读DATA、等R；全部响应必须OKAY。
4. 再读STATUS确认lease仍有效且bit3=0，最后读EPOCH为E1。
5. 仅E0==E1且上述条件全部满足才接受整包；否则丢弃整包重试。
6. 写RELEASE。驱动不得让同相机INDEX/COMMAND和DATA并发；其他相机可轮询。

这样即使某字段是reset前已承诺的旧OKAY响应，而恢复后显式重新ACQUIRE读到了新数据，
前后epoch也会不同。最后epoch响应之后发生reset不追溯破坏已完成的旧快照读取。
整个AXI接口reset允许epoch归零，驱动必须将其视作设备重新初始化，禁止跨接口reset拼包。

使用单拍128-bit DMA访问，每个寄存器地址16-byte对齐，有效数据位于低32位，
驱动提交DMA之前必须验证 `(address & 15)==0`；硬件不能替驱动检测上游已对齐的原始错误地址。
写低4个byte strobe须全置位；读只取低32位。冻结bridge忽略LEN/SIZE/BURST且固定RLAST=1，
因此**不支持把16字段读打成AXI burst**，本候选也不修复冻结bridge的多拍协议缺陷。

## 物理集成门槛

必须签核cam/host异步时钟组、reset异步断言/同步释放、request/ACK同步链、
reset_pipe的ASYNC_REG识别，以及mailbox→host_bank的bundled-data稳定窗。
沿用原候选建议：数据路径最大延时限制在两个host周期以内，不能被全局false-path吞掉；
request三级同步后另拍复制，ACK两级。reset短脉冲仍须满足器件异步置位最小脉宽。
epoch加法在host域是普通32-bit加法，未作时序优化/签核。
没有资源、Fmax、布局布线、亚稳态或实板结论；不得把本次数字仿真当作CDC物理签核。
