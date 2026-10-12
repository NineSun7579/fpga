# 最小接线与主机协议建议（尚未接入）

只支持当前冻结配置 DATA_WIDTH=16、DELAY=2、VSYNC_STABLE_CYCLES=0。
诊断模块没有 payload 端口，不驱动 capture、FIFO、RAW、DDR 或 NPU。

## 采样与 epoch

在 `ov5640_tc03_binding.v` 内，建议旁接如下信号。此文档不是生产补丁。

| 候选端口 | 建议信号/含义 |
|---|---|
| cam_clk | 与 cmos_capture 和源 CDC 相同的 cam_pclk |
| raw_href | **cmos_capture 实际输入** cam_href；不是旧 dbg_hr_ff 的同步输出 |
| raw_vsync | **cmos_capture 实际输入** capture_vsync；当前 bypass 配置等于 cam_vsync |
| raw_byte_accept | cam_href；当前 capture 无 ready，每个 HREF 高拍均采样字节，不能额外与 !VSYNC 相与 |
| capture_valid | 下降沿寄存后的 cmos_frame_valid_r，正是源 CDC 的 s_valid |
| capture_vsync | 下降沿寄存后的 cmos_frame_vsync_r，正是源 CDC 的 s_vsync |
| cam_reset | capture 复位及源统计会话复位的合并请求；例如 !ov_rst_n OR 源 CDC cam_rst |
| host_clk / host_reset | 新诊断寄存器适配器所在 AXI 时钟与复位 |

全部量以 cam_pclk **上升沿、NBA 更新前**观察。若原始第 n 拍完成一个双字节像素，
capture 的 valid 在第 n 拍 NBA 后产生，经现有下降沿寄存后，在第 n+1 拍被源 CDC 计数。
原始 VSYNC 第 n 拍被采样，DELAY=2 后在第 n+2 拍被源 CDC 看到。
因此候选内部把 raw VSYNC/HREF/accept 延迟两拍、把观测 capture_valid 再延迟一拍：

* 字节数、HREF 分段、奇数尾、尾空白、aligned_valid 均落在同一原始字节 epoch。
* native_valid 保持现有源 CDC 窗口规则：起始 marker 同拍 valid 属于新帧；结束 marker 同拍不属于旧帧。
* 窗口使用实际 capture_vsync 上升沿，区间 `[start, end)`。首个被 capture 放行的 marker 只建窗，不发布半帧。
* warmup 中原始字节不发布；当前 WAIT_FRAME=10，TB 实际经过 11 个原始 marker 后开窗。
* 若延迟的原始 VSYNC 与 capture_vsync 在已开窗区间不一致，mismatch 标记该帧，禁止盲目比较。

accepted bytes 指本采样点接纳的字节，不是 FIFO 接纳数。片段按 HREF 高电平连续区间计数，
奇数尾按片段内 accepted byte 奇偶计数。跨 VSYNC 的高片段在窗口处裁分，并置 clipped/bad。
单拍 HREF 低会在此数字接口结束片段；它的成因可能是上游 RTL/采样/配置等，**不能据此认定硬件故障**。

## 原子邮箱与复位

每个完整帧结束时一次性写入源域 mailbox，翻转 request；mailbox 在 ACK 返回前不再写。
主机域用三级 request 同步，随后一拍复制稳定 bundled data。主机必须显式 ACQUIRE，
才能把该快照租用到 host_bank；所有字段在 RELEASE 前保持不变，重复 ACQUIRE 也不覆盖。
只有 RELEASE 已租用 bank 才回传 ACK。新帧遇忙直接丢弃**快照**，不阻塞图像路径；
sticky overrun 可立即经两级同步读取，frame_seq 仍每帧递增。prev 字段仍保留紧邻的真实前帧，
即便那帧的快照被丢弃，故主机慢读不会破坏相邻窗口判断。

主机步骤：STATUS.available=1 → 写 ACQUIRE → 确认 STATUS.valid=1 → 读取全部 16 字 → 写 RELEASE。
同一主机/驱动独占该 lease。seq 仅作帧编号/跳帧判断，不承担防撕裂职责；无需前后 seq 检查。
STATUS 是独立实时控制状态，不属于冻结的 16 字帧内容。主机不释放将保持旧帧并报告 overrun。

任一域复位都异步撤销**整个诊断会话**，两个域分别两拍同步释放。没有跨 reset 的帧守恒承诺。
复位后的新数据必须重新 ACQUIRE；不会自动续上旧 lease。无有效 lease 读数据返回 read_error，
适配器必须把它映射到 AXI SLVERR，并在诊断会话复位时取消其待处理响应；主机丢弃该次读取。
即使相机复位发生在多字段读取中，也不会悄悄把新会话字段接到旧 lease 后面。
复位清空 overrun 与 seq。无需图像流停顿，亦不重置生产 RAW 路径。

接口是本地主机时钟的单拍 strobe，不是 AXI 实现。read_strobe 当拍采样 word index，
下一周期 read_valid/read_data/read_error 有效。AXI 包装器需自己保存 RDATA/RRESP 直到 RREADY；
不可直接把动态读 mux 接给 AXI。ACQUIRE/RELEASE 同拍发出不是支持的驱动协议。

CDC 物理集成还需标识同步器、异步时钟组及 bundled-data 约束：从 mailbox 源寄存器到
host_bank 数据端的最大延时建议限制为两个 host_clk 周期以内（req 三同步级后另拍复制），
保证该路径约束不会被全局 false-path 覆盖。ACK 两级同步。没有物理布局/亚稳态签核结论。

## 寄存器建议

建议预留**新**精确解码区间 `0x20001000..0x200013ff`，每相机 0x100 字节：
CAM1 0x20001000，CAM2 0x20001100，CAM3 0x20001200，CAM4 0x20001300。

现有 CAM 窗口在 `0x20000000..0x200007ff`（每相机 0x200），PREP 选页在
`0x20000100`，motion 精确页在 `0x20000800..0x200008ff`。
COOP endpoint 在 `0x40010000..0x40010fff`，其 router 将 offset>=0x100 路由到 CAPL，
因此不能只绕开当前已定义 CAPL 寄存器而占用该窗口中的其余 offset。

**现有 ovreg decoder 使用低位路由，会把新地址别名到旧从机；不能直接往现有 bus 写这些建议地址。**
集成时必须在该 decoder **之前**加入完整高地址精确拦截，新区间命中只送诊断适配器，
其余请求走原 decoder，且 AW/W/AR/响应必须保留各自事务归属。该路由与 AXI 适配器本次没有实现。
`address_audit.txt` 保留 GBK 字节级搜索的地址证据；文字常量无冲突不等于现有路由已支持。

| offset | 内容 |
|---:|---|
| 0x00 | frame_seq，32 位模计数，首个完整帧为 1 |
| 0x04 | accepted bytes，24 位 |
| 0x08 | HREF 高片段数，16 位 |
| 0x0c | 奇数 byte 尾片段数，16 位，包含恰在边界结束的片段 |
| 0x10 | aligned_valid，24 位，按末字节所属 epoch 对齐 |
| 0x14 | native_valid，24 位，复现源 CDC 窗口 |
| 0x18 | capture_valid && capture_vsync 总数，24 位 |
| 0x1c | [15:0] tail_gap；[16] 格式有效；[17] prev有效；[18] 本帧见过HREF；[19] gap到饱和值；[20] clipped；[21] mismatch；[22] 计数溢出；[23] bad（含边界奇数计数溢出） |
| 0x20 | previous accepted bytes |
| 0x24 | previous aligned_valid |
| 0x28 | previous native_valid |
| 0x2c | previous odd tails |
| 0x30 | [0] 起始 native valid；[1] 结束 native valid；[2] 起始 aligned valid；[3] 结束 aligned valid；[4] 结束原始 HREF；[5] 前帧起始 aligned valid；[6] 前帧结束 aligned valid；[7] 前帧 bad |
| 0x34 | previous HREF segments |
| 0x38 | accepted bytes && 原始 VSYNC 总数，24 位 |
| 0x3c | 格式常量 0x53464401 |
| 0x40 | STATUS：[0] lease valid；[1] sticky overrun；[2] snapshot available |
| 0x44 | 建议只写 COMMAND：[0] ACQUIRE 脉冲；[1] RELEASE 脉冲 |

数据字段都在同一冻结 bank 内。tail_gap 是最后一个原始 HREF 高拍与结束 VSYNC 之间，
严格夹在其中的 HREF 低拍数，最大 65535；两者相邻为 0，见过 HREF 标志为 0 时不可用。
24/16 位事件计数为模计数，溢出标记 bad；gap 单独饱和，饱和本身不使 valid/byte 计数失效。

## 主机判据

在 bad=0 且接纳策略与 capture 拼字策略一致时：`2*aligned_valid == bytes - odd_tails`。
分段增加且 odd_tails 增加可以解释在 byte 总量不变时的 valid 减少，但仍需实板测量确认。
若 bytes 减少而分段/奇偶正常，则是本采样点字节量减少；这里不判断它发生于引脚还是上游逻辑。

令 A=aligned_valid，N=native_valid，s/e 为 offset0x30 bit2/bit3：
`N - A = e - s`，主机用有符号宽整数计算。相邻帧的 e_prev 必须等于 s，
因此 `N_prev + N - A_prev - A = e - s_prev`。在外侧 endpoint 都为 0 时两帧总数相等。
prev_valid=0、任何相关计数溢出或延时契约不匹配时，不使用该式作根因判断。
clipped 时 native/aligned 时间窗恒等式仍可检查，但 bytes/odd 的独立拼字推断不成立。
