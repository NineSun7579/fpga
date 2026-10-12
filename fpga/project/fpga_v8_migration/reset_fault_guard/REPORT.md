# reset_fault_guard：窄范围 runtime fail-stop 候选

已实现逻辑和实际 v2 绑定候选；**不是 uniform-reset recovery provider，上板准入仍未认证**。依据 `whole_reset_contract_01/REPORT.md` 和其 `source_manifest.json` 的准确源字节；生成器先校验审计 SHA256，不从另一份同名模块推导行为。仅本目录有新增/写入，没有 PDS、SSH、板访问、复位、journal provisioning，也没有修改 v2/currentrunningPnR/production/IP 或既有 host helpers。

## 交付物

- `fpga_v8_reset_fault_guard.v`：25 MHz free_clk supervisor，sticky fault、local ready sample ACK、分频 heartbeat CDC、启动连续资格和两个域的准入信号。没有 AXI/reset/drain 输出。
- `build_binding.py`：字节级变换；保留未变更行的原始 mixed CRLF/LF。所有模块使用新名 `_rfg01`。`artifacts/binding.diff` 是便于评审的 ASCII 转义视图；非 ASCII 注释不能用此文本 diff 覆盖原文件。`build()` 返回实际候选字节，可在未来独立分支登记；当前没有创建另一份 whole/PnR 工程。
- `artifacts/fpga_v8_cooperative_top_v2.diff`：124 行左右的 top 差异，连接真实 PCIe `smlh_link_up/rdlh_link_up`、真实 `pcie_rst=~core_rst_n` 输出、`perst_n`、`axi_rst`、`ddr_init_done`、物理 button 和 free_clk。没有臆造 resetIPO/PLL/reset-monitor 来源。
- 真实 FIFO/controller 新名候选及仅作 ModelSim 声明前移的 compatibility 版本。wrapper/core/control 分别有小 diff；只有测试需要的 cooperative control 副本保留。未复制完整 top。
- `session_fault_transport.hpp`：可供原 RAW 和 cooperative helpers 共用的本地 Transport 装饰器，既有 owner/transport mutex 内使用；每次底层读、CLAIM/ACK write、COPY 前先 ordered-read RAW STATUS bit2。读取不确定/故障或操作不确定后本对象锁停。没有修改 completed helpers，没有新 driver 或板后端。

## 状态和准入

配置初始 Inactive，两个域必须实际获得时钟并采样 reset 释放/ready；free_clk 同步 ACK 和 heartbeat，连续资格成立才进入 runtime_active。默认 heartbeat 超时 256 个 free_clk 周期，即约 10.24 us；资格为 32 周期，即约 1.28 us，另加 CDC/heartbeat 延迟。分频 heartbeat 可能在某些频率关系下混叠；该情况会保守拒绝/故障，不是时钟质量认证。

启动 ACK 还采样**真实可见 idle**：FIFO writer IDLE、无 read_pending/queue，F2H read FSM IDLE、未 read_started；PCIe pack/copy 和 mrd/mwr busy；top capture engine idle、未 armed、RAW/cooperative banks FREE、cooperative/bridge/arbiter busy 为零。这些条件不是 hard-IP tags、posted writes 或整个 DDR/fabric 的退休证明。READY 不直接 ARM；原 manager 仍 disarmed，host 必须按现有 helper 完成显式新 generation 配置。

runtime_active 后独立 PERST、PCIe local reset、link loss、AXI reset、DDR-init loss、任一域 heartbeat 超时均使 authority 永久失效。短于 free_clk 周期的实际 reset/loss 脉冲通过异步 assertion 锁存；本实现仍需 PDS reset/CDC/timing signoff。local reset 不清 supervisor，也不清用于读回的跨域故障同步器。

新的 H2F COMMAND（真实 controller command bit24=0）、尚未发出的 MRD request、FIFO writer 从 IDLE 启动新事务、ARM、capture SOF、新的 cooperative lease input 被锁闭。既有 AW/W/B、AR/R 状态机不 OR 入 fault/PERST reset；已接受事务仍按原 W/R/B 协议推进。不会把 guard permit 当成 drain receipt。

**F2H 读保持开放**，以便实际端点/时钟幸存时读取 RAW STATUS。把所有 controller register write/F2H 都关掉会使 STATUS 自己不可达，因此这个候选只封 authority-changing H2F COMMAND。metadata staging 可继续，但不能启动 H2F；不可信/绕过装饰器的调用者仍可请求只读 COPY。它不是新的 driver admission 或主机 DMA memory quarantine 实现。

RAW control 的既有 `protocol_fault` 输入 OR 入 `fault_axi`，保持原 STATUS bit2。不能 OR 到 manager 的输出驱动。cooperative control 增加只读 `session_fault`：STATUS error bit6 和 LAST_ERROR 固定 `0x52534647`，不 OR 入 `bridge_error`，不修改 busy、在途结果或 source-release 状态机。

物理 button 可清 supervisor 的原因 fault，但若曾 runtime_active/fault，则同时锁存 `reconfiguration_required`；有效故障读回和准入继续封闭。local/soft/link reset 无清除路径。只有新的 FPGA 配置可重新开始启动资格；**重新配置仍不是旧 host DMA/IRQ/posted writes 已消失的证明**。未认证的按钮按压、任意 pulse 宽度都不能获得“host safe”收据。

## 仿真观察与边界

运行 `python fpga_v8_migration/reset_fault_guard/run_tests.py`。ModelSim 10.6e 编译真实 v2 FIFO/controller、审计登记的 RX/TX Pango FIFO/DRM、真实 ARM endpoint/lease，PCIe shell 仅建模公开 reset/clock/busy/BAR 接口。没有层次 force 内部状态。shell BAR tasks 只驱动真实 controller 的 BAR 输入；真实 W/R/B 在 DUT 公口记录/检查。原 legacy forward declarations 仅在仿真 compatibility 文件前移，两个既有隐式 wire 显式声明。MSVC C++17 编译并运行 Transport 公共接口测试。

`artifacts/results.json`、`tb_*.log`、`host_test.log` 记录最终结果：

- startup 停 PCIe clock、startup 可见 busy 均不开放；两个 domain reset/loss 的短 pulse、两类 link-up loss、两种 clock stop 均 sticky，恢复时钟/局部 reset 不重开。
- runtime button 清原因 fault 后仍不重开；正常 runtime busy 与真实正常 ARM/epoch_start 不报故障。
- PERST/link loss 注入真实 writer 的 pending B：旧 B 能被消费，之后新 H2F COMMAND 不产生新 AW/W。DDR loss 确实销毁 writer 状态，候选保持 fault，不伪造 B-drain 或自动重启。
- DDR loss 位于 staged generation 与 ARM 之间：新 ARM 拒绝；RAW STATUS bit2 可见 sticky fault。已接受 ARM 的控制 B 被 hold 时发生 link loss，原 B 保持；HELD 帧 link loss 后不重新 ARM。
- cooperative 正在 busy 时 fault 只改变 STATUS/error hint；原 active operation 正常完成至 READY/source-release pending。
- 在途 R 在 link loss 后继续消费；故障后 F2H STATUS read request/AR/R 可见路径仍可发起。该 shell 不证明 F2H posted write 对 CPU 可见。
- C++ 装饰器每次 CLAIM/COPY/ACK 前先读取硬件故障位，故障后没有新的 write/COPY，硬件位后来清零也不自动重开本对象。

**明确的不支持观察**：`tb_capture_fault MODE=3` 人为仅 reset control endpoint（测试 fixture 的局部输入，未加入产品 guard），manager 的 HELD 仍在、endpoint bound claim 已丢失，supervisor 无从检测。准确 v2 的 control/manager 都只有 axi_rst，capture datapath reset 为 `axi_rst | epoch_start`；正常 epoch_start 不可误报。若未来加入独立 capture/control reset，必须把那条真实 reset 源接到 supervisor fault 事件，或明确禁止其存在；不能凭空增加一个未绑定监控端口后声称覆盖。此用例是暴露缺口，不是 isolation PASS。

19 个执行场景及 1 个上述缺口观察符合预期。组件编译包括 PCIe wrapper/DMA/core/control 的新接口；**没有完整 top/hard-IP elaboration、PDS synthesis/PnR、板级统一复位认证或物理 FIFO 两端 reset 认证**。camera1–4/SFP ingress 的审计 top 字节范围、F2H AXI read 后缀及 writer reset/W/B equations 有静态保留断言。所有读取的 v2 RTL、测试用 IP、project.pds 和既有 helper 审计 hash 前后检查不变。

仍需父会话评审/后续验证：异步 fault-set 到目标域准入的物理时序及 CDC；top 真实工程登记/完整 elaboration；PCIe 硬 IP transaction cancellation、resetIPO 与 posted visibility；DDR/fabric 全部 outstanding；物理 uniform-reset provider；实际 driver owner、IRQ drain 和 DMA mapping quarantine。CPU/process 重启没有 fabric 输入，此 RTL 不能检测它。默认 startup visible-idle 也不证明 hard-IP 从配置前的主机事务中退休。保持 board recovery certification=false。
