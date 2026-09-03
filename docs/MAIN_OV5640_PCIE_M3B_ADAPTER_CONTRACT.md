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

当前描述符模块与 staging adapter 仍是独立的同域组件；后续 wrapper 需要显式连接
两者，并在进入 `cam_pclk` 到 DDR3/PCIe 用户时钟的 CDC 之前完成联合行为验证。
