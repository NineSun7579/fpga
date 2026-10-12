# 四路 recovery 集成审查：只允许全域冷启动恢复

## 判定

**现有冻结 top/parent 不能直接替换为 recovery 候选并放行。** 已用实际启动逻辑和四个候选 CDC 复现正常启动永久 fault；目前也没有四路冷启动授权、camera fault 会话锁存与上层会话禁止的完整连接。

**本次没有发现 TC04 的 `abort_req` 路径撤销 AWVALID、丢弃已接受 AW 的剩余 W、或提前用 abort 确认释放共享 owner 的反例。** 真实 writer/stream_pipe、真实 recovery wrapper/controller、真实七路仲裁器与 TC03 DDR adapter 的定向测试通过。可以以此继续设计“关闭新采集/发布，保留已承担的 AXI 义务，故障只由平台全域冷启动清除”的集成；不需要为了这种模式先声称实现了全系统 drain。

但这不等于现有系统已集成，也不等于任何故障都能有限时间退出：AWREADY/WREADY/vendor completion 永不返回时，必须保持义务，不能靠 watchdog 丢账。**本次不宣称全系统 drain、局部自动恢复、DDR 内容原子回滚或四路物理 CDC/PNR 合格。** 没有修改 abort RTL 来隐藏问题。

仅本地隔离目录新增 TB、启动摘录、脚本、日志和本报告；未改既有候选/冻结/生产/IP，未执行 remote、program 或 PDS。Hindsight 服务连接失败，全部结论来自本地代码与实际仿真。最后的 `protected_result.json` 记录 1015 个受监视文件 SHA256 不变，包括候选/冻结 RTL、生产 source/IP 及工程文件；它是文件级保护记录，不是整个工作区每个文件的快照。

## 实际使用的冻结层级

冻结根：`../../whole_candidate_v7_route_01`，以下行号均对应当前受保护源文件。

- `project.pds` 实际注册顶层 **`rtl/fpga_v8_cooperative_top_v2_rfg01.v`**，不是只读取 `inputs/source/top.v` 就下结论。
- 四个 `ov5640_top` 的定义来自 `rtl/parent_tc04_c40cee500c37.v`；其 capture/I²C/CDC 绑定来自 `rtl/ov5640_tc03_binding.v`。
- 四路写 DMA 是 `rtl/axi_dma_write_tc04.v`，实际 `BURST_LEN=16`、128-bit、`WAIT_FOR_DATA=1`，使用原 `inputs/source/axi_dma/stream_pipe.v`。
- 相机 AXI 写接 `fpga_v8_cooperative_core_rfg01.write_arbiter` 中的 **`fpga_v8_ddr_write_arbiter`**，MASTER_COUNT=7。老 `ddr_w_arb.v` 虽仍注册，不是这次顶层实际相机共享写路径。
- 仲裁器输出接 `fpga_v8_ddr_adapter_tc03`，再接 vendor DDR 用户端口。adapter 先缓存完整突发，vendor `wusero_last` 才生成上游 B。

| 相机 | 实际 top 实例 | writer 实例 | AWID | 七路 arb slot | abort 请求/确认 |
| --- | --- | --- | --- | --- | --- |
| 1 | `ov5640_top` (1043) | `ov5640_axi_dma_write` (1830) | 1 | 0 | `cam_dma_abort_req` / `cam_dma_abort` |
| 2 | `cam2_ov5640_top` (1255) | `cam2_axi_dma_write` (1876) | 4 | 1 | `cam2_dma_abort_req` / `cam2_dma_abort` |
| 3 | `cam3_ov5640_top` (1327) | `cam3_axi_dma_write` (1922) | 2 | 2 | `cam3_dma_abort_req` / `cam3_dma_abort` |
| 4 | `cam4_ov5640_top` (1428) | `cam4_axi_dma_write` (1968) | 8 | 3 | `cam4_dma_abort_req` / `cam4_dma_abort` |

top 3248 附近按 `{cam6,cam5,cam4,cam3,cam2,cam1}` 打包；core 224–250 再把 cooperative bridge 加到 slot 6。slot 4/5/6 在本次共享测试中保持空闲。

## startup/reset/fault 到实际信号的映射

| 信号/域 | 冻结连接与含义 | recovery 集成要求 |
| --- | --- | --- |
| `camera_ctrl_rst_n` / clk_50m | top 1025–1034：初始化为 0，16-bit startup counter 到全 1 后置 1；无运行期复位分支；四路 parent 共用 | 不是全域冷 reset 的替代。普通 button/DDR reset 不会重启该计数器 |
| parent `clk_50m_rst_n` | parent 296 接 binding `rst_n` | 仅相机控制域授权，不表示 DDR ledger 或 host ownership 已清空 |
| `i2c_start_en[i]` | binding 96–115：`rst_n` 释放后计满 `CLK_FREQ/1000*7` 再置 1；默认 50 MHz 实际为约 7 ms | 正常启动时长时间保持低，应在首次冷启动授权内等待，不能当运行期 fault |
| `cam_rst_n[i]` / cmos reset pin | binding 115：等于 `i2c_start_en`；binding 372：CDC `cam_rst=!cam_rst_n` | 原连接中的 cam request 就是此信号；不能擅自等同于 I²C 配置完成 |
| `cam_init_done[i]`、`ov_rst_n[i]` | binding 119：`ov_rst_n=rst_n & cam_init_done`；I²C cfg 的 reset 是 `rst_n & i2c_start_en` (166)；capture reset 是 `ov_rst_n` (322) | 源 capture 的初始化/复位域和 CDC cam reset 不相同。需要暴露源 ready/源复位原因，或监督 `ov_rst_n` 在运行期下降。仅监督 `!cam_rst_n` 不能覆盖这条路径 |
| `axi_rst` / video/AXI | top 358：`axi_rst=~ddr_init_done`；四路 parent video reset、writer reset、arb/adapter reset 均由此派生 | 普通运行期 AXI reset 会清 writer ledger；不能当仅关闭采集的安全 fault 操作 |
| DDR reset | top 251：vendor DDR `resetn=button_rst_n` | button 复位 DDR 不等于重新配置全部相机/会话状态；不证明所有域的旧响应/ownership 已清空 |
| `boundary_fault[i]` | recovery 的 reset sticky、transport sticky 加 raw local reset request | 新端口须经 binding、parent 暴露；接 FIR 的故障清除、wrapper transport_abort 和会话 fault。不能接 writer/stream_pipe/arb/adapter 的局部 reset |
| `cam_dma_abort_req[i]` | parent 516 原样输出；recovery wrapper 71 为 `capture_bad | transport_abort`；top 接 writer `abort_req` | sticky transport fault 时持续保持。writer 可继续补完剩余零 strobe W、接收真实 B |
| `cam_dma_abort[i]` / `cam_dma_done[i]` | writer `data_in_abort` / `data_in_last` 回 parent/wrapper/controller | 是本命令失败/成功完成脉冲，不是全局 drain ack；空闲时 fault 不保证产生 abort 脉冲 |

这里的 `cam_init` 对应实际 binding 内部 `cam_init_done`，不是一个现成的顶层四位 ready 总线。父层虽接有 `ov_rst_n`，当前没有 recovery supervisor 的四路 ready/fault 接口。

### 已执行的启动反例

`run.py` 从实际 top 原样按字节摘取 startup counter，从实际 binding 原样摘取 power_on counter，生成 `startup_extract.v`；未缩短计数参数。四个 CDC 实例用略有差异的 cam 时钟、约 131 MHz video 时钟；FIFO 是原 vendor 模型。

1. `system_reset=axi_rst`，令 DDR 初始化在 1 us 时完成，而 camera 正常延迟启动尚未结束。
2. `request_reset=cam_rst | video_rst` 在 system_reset 释放后仍为 1。
3. recovery.vh 5–7 的 `always @(posedge video_clk or posedge request_reset or posedge system_reset)` 在 video 上升沿执行 `else if(request_reset) reset_fault<=1`。**不需要 request 再上升，保持高本身就会锁存。**
4. 实际 camera reset 于约 8.311 ms 释放后，四路 fault 仍是 `1111`。
5. 对照仅在首次冷启动授权持续到局部 request 全低后释放：fault 为 `0000`。另测冷授权先释放、video reset 仍高的相反顺序，也得到永久 `1111`。

```text
REVIEW_STARTUP actual_50MHz_time_ns=8311027.320 naive_fault=1111 ordered_fault=0000 errors=0
REVIEW_STARTUP_VIDEO_LATE fault=1111 errors=0
```

8.311 ms 是本 TB 观测点，不是实际板上 DDR 初始化时间的测量；反例证明当前接法对一种允许的正常释放顺序不安全。没有完整仿真 SCCB 初始化或 sensor PCLK 起振，不能把此对照当成全部启动时序验收。

**不得用永久 `system_reset = cam_rst | video_rst` 修补反例。** 运行期局部 reset 会因此清 sticky fault 并重新授权旧会话。正确方向是独立、只在平台冷启动中有效的 startup authorization；其首次释放条件等待实际局部 reset/源初始化以及域 ready，运行期异常只能进入 sticky fault。

## 当前 abort 到 AXI ledger 的实际行为

TC04 源码对应：

- 183–196：AWVALID 只由全域 `rst` 或 AW handshake 清除。`abort_req`/`abort_r` 阻止新增 AW，**不撤销已展示 AW**；199–204 在 AWVALID 高时固定 addr/len。
- 263–274：命令活动时采样 abort；297–303：abort 后停止取上游数据，用 `WSTRB=0` 的补充 beat 完成尚未送入 stream_pipe 的 burst 长度。
- stream_pipe 已接收/对外展示的 beat 保持原 payload；不能把其 reset 拉高来“清相机”。已承诺的非零 strobe 写仍可能完成，fault 不是撤销 DDR 写。
- 306–322：只有外部 WLAST handshake 后才开启 BREADY。
- 280–281：abort_done 只能发生在真实 B handshake，或根本没有广告 AW/活动 burst 时本地退休。324–332 的成功/失败互斥。watchdog 不构造 B。
- recovery controller 回 IDLE/清 cmd_valid 只是撤销内部 command remainder。数据账本由 writer 继续持有，wrapper FIFO flush 不得清 writer/stream_pipe；本次真实绑定正是这样接线。
- arb 108–123、184–197：owner 保留到 B handshake；adapter 131–145：缓存满 burst 才展示 vendor AW，最后 vendor 消费事件才生成 B。缺 W 会堵住 adapter/共享 owner，故验证不能只看 controller 已 IDLE。

**现有 abort 安全性结论仅针对保持 AXI 时钟与 ledger、不复位写路径的 fault。** 若将 boundary_fault OR 到 writer rst，writer 185、214、264 和 stream_pipe 45–47 会清 AW/剩余 W/队列，已接受 AW 的义务可能被丢弃。此处是禁止的集成接法，不是声称当前 `abort_req` 实现有该缺陷。运行期 `axi_rst` 本身牵涉共同 DDR reset，必须走平台全域重置契约，不能用本文 abort 仿真给它背书。

## 可执行 TB 与实际证据

仓库根执行：

```powershell
python project/fpga_v8_migration/board_v7/four_camera_recovery_review/run.py
# 定向重跑，例如：
python project/fpga_v8_migration/board_v7/four_camera_recovery_review/run.py startup binding
```

ModelSim SE-64 10.6e，支持 MODELSIM_BIN。脚本只在本目录建 work/log；直接编译既有 recovery 源、冻结 DMA/pipe/arb/adapter/packer 和 vendor FIFO/primitive。没有 force 控制器状态、伪 FIFO、修改 DUT、直接向 DUT 内部写计数器或伪造 DMA done。外部 DDR 用户端口由 TB 驱动合法消费事件，不实例化 DDR3 物理控制器/DRAM。

| 文件 / 日志 | 覆盖 | 实际结果 |
| --- | --- | --- |
| `tb_startup.sv` / `startup/simulation.log` | 原 50 MHz 计数逻辑 + 四 CDC；相机晚释放、video 晚释放及正确首次授权对照 | 两个正常启动误锁反例 `1111`，对照 `0000`，errors=0 |
| `tb_ledger.sv` / `ledger/simulation.log` | 四个真实 writer，ID 1/4/2/8，每路 8 cutpoints，16-beat burst；AW/W stall payload 不变、WLAST/credit、真实 B 后结果 | 32 个 cases，errors=0；每个有 AW 的 case 完成 `1 AW / 16 W / 1 B`，只一次 abort、无 success |
| `tb_binding.sv` / `binding/simulation.log` | 候选 CDC 真实局部 reset 触发 sticky fault → 真 recovery wrapper/controller/packer → 真 DMA；自然送 256 像素，2×16 数据 beat + 1 tag beat | 11 cases，errors=0；9 个活动命令故障、冷 reset 后正常发布对照、真实 tag dma_done 同拍 fault |
| `tb_shared.sv` / `shared/simulation.log` | 四 writer 竞争真实 7-slot arb + TC03 adapter + 原 DDR FIFO；slot4–6 空闲；vendor AW backpressure、断续消费和延迟最后 beat | 单路/四路 simultaneous fault 各 `4 AW / 64 W / 64 vendorW / 4 B`，最终 busy=0，arb/adapter errors=0 |

ledger cutpoint 0=命令已接受但 source 无数据/无 AW；1=AWVALID 背压；2=AW 刚接受；3=WVALID 持续背压；4=部分 W 已接受；5=外部 WLAST 背压；6=完成 W 等待 B；7=abort 与 B 同拍。每个有 AW 的 case 延迟 B 1100 cycles，超过该 TB 的 WD_LIMIT=1000；没有任何提前成功/失败确认。

binding cutpoint 0=自然 frame command handshake 后未出 AW；1=数据 AW 背压；2=AW 已接受；3=W 背压；4=部分 W；5=数据 burst 等 B；6=自然 tag AW 背压；7=自然 tag WLAST 背压；8=tag B 与 fault 同拍；9=冷 reset 后完整正常帧；10=tag B 已完成、writer 的真正 dma_done 高时 fault。

```text
REVIEW_BINDING cut=6 AW=3 W=33 B=3 abort=1 data_success=1 publish=0 errors=0
REVIEW_BINDING cut=7 AW=3 W=33 B=3 abort=1 data_success=1 publish=0 errors=0
REVIEW_BINDING cut=8 AW=3 W=33 B=3 abort=1 data_success=1 publish=0 errors=0
REVIEW_BINDING cut=9 AW=3 W=33 B=3 abort=0 data_success=2 publish=1 errors=0
REVIEW_BINDING cut=10 AW=3 W=33 B=3 abort=0 data_success=2 publish=0 errors=0
REVIEW_SHARED case=0 AW=4 W=64 vendorW=64 B=4 zero_strobe=12 busy=0 errors=0
REVIEW_SHARED case=1 AW=4 W=64 vendorW=64 B=4 zero_strobe=60 busy=0 errors=0
```

cut10 说明重要的接口限制：fault 到来时 DMA 已真正退休，因而无 `cam_dma_abort` 脉冲，controller 仍正确禁止发布。不能设计“等四个 abort ack 都出现才能保持/清故障”的 supervisor。

shared 每次延迟最后 vendor beat 150 cycles，超过该 TB 的 WD_LIMIT=100；延迟期间确认 B 不提前发生、共享 owner 不释放、其他相机不能越过该事务。之后合法返回最后 beat，adapter 生成 B，四路继续完成。case0 其他三路各正常完成一次；case1 四路各失败一次。**这是在下游最终继续响应的条件下没有新增协议死锁的证据，不是永久故障下的有限退休保证。**

所有四套编译日志 0 errors/0 warnings；仿真日志中存在未连接诊断输出等未使用端口 warning，不据此宣称零仿真 warning。本次 binding 输入从 DDR wrapper 像素口进入，不重新覆盖 sensor→capture→CDC→FIR 的逐像素正确性；那部分保留先前候选报告的覆盖边界。共享测试也不覆盖 PCIe/其他三个 master/主机 lease 生命周期。

## 四路集成的最小接口与硬阻挡

以下是设计要求，**本目录没有实现或接入生产四路 supervisor**。

| 最小接口/行为 | 必须解决的问题 |
| --- | --- |
| 独立 `cold_session_reset`/首次启动授权，贯穿四路 CDC/binding/parent | 启动期间保持候选 system_reset；等待四路实际 local reset 释放，源初始化/域 ready 条件成立后再撤销。运行期不得由 local reset OR 重新生成此权限。现有 top 无此接口 |
| 每路 `source_ready`/`source_reset_seen`，来自实际 `cam_init_done`/`ov_rst_n` 与 `i2c_start_en`；必要的同步和停钟处理 | 把“正常初始化尚未完成”和“运行期源 reset”分开；避免只看 sensor reset pin 漏掉 capture epoch 变化。候选内部跨域 ready 仍需保留 |
| 每路 `boundary_fault[3:0]` 输出与 raw fault 原因；parent FIR fault clear、`ddr_recovery.transport_abort` 输入 | 冻结 binding/parent 没有这些贯穿端口。不能仅替换 CDC 名字就认为已接入；不触碰 DMA/pipe/arb/adapter reset |
| 会话级 sticky `camera_session_fault`，纳入 `boundary_fault`、capture_bad/abort_req 原因、writer `cam_dma_abort` 等所选致命错误 | 原 capture_bad 在 flush 中清除，原 watchdog/B-error 只报命令失败，现有逻辑仍可能接下一帧。如果目标是所有 camera fault 只冷恢复，必须将这些错误也锁存。使用寄存 fault，避免从 transport_abort→abort_req→transport_abort 形成组合反馈 |
| 合并系统 admission/fault，但保留 response 路径 | guard_02 没有 camera fault 输入，且只监督 DDR/PCIe/时钟健康。需要新合并会话 fault，关闭新采集、frame/tag 发布与新 lease/host 消费授权；可选广播 transport_abort 到四路，使所有相机命令停止扩展。**不得关掉已展示的 AW/WVALID、BREADY，或给仲裁器/adapter 单独复位** |
| 保留每路已有 `available/abort_req/abort/done/cmd/data` 接口 | 此接口足够请求当前 writer 安全失败；abort 是命令结果，不是全部域 ready 或 drain。无需为冷恢复模式冒造 drain_ack。若增加 busy/ledger 观察，仅作诊断，不授予热重启权限 |
| 平台级冷复位/重新配置及 ownership 重建契约 | 覆盖四路 capture/CDC/FIR/packer/controller/DMA/pipe、全部共享 master/arb/adapter/vendor DDR 事务、PCIe/lease/bank/generation。旧发布不能由新 fault 撤回；未发布脏 bank 不得重新作为好帧使用。现有 `camera_ctrl_rst_n` 和 guard_02 的持久状态都不是普通 button reset 清除的全域状态 |

因此阻挡分为：**已实证的 startup 接法错误**；**尚未实现的四路 supervisor/故障贯穿与 host ownership 策略**；**运行期 AXI/DDR reset 的平台共同清除契约**；以及候选报告已有的物理 CDC、异步 fault 路径/复位映射、source 少像素问题。不能把“缺全局 drain 接口”重新包装成本次没有验证 writer：writer/shared 层面的账本已做实测；同样不能用这些局部结果宣布系统全域安全恢复完成。

下一步如果继续实施，应先在另一个授权的隔离集成中实现上述首次启动/会话故障接口，再运行完整四路 top 级故障传播和平台冷启动验收。本次审查的交付是明确反例、可重跑的真实握手证据及接口阻挡，不是可部署替换件。
