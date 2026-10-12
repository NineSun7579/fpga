# 四路冷启动授权与会话故障监督隔离候选

已实现 `four_camera_reset_supervisor.v` 和可编译的四路最小连接 `four_camera_supervised_boundary.v`，实际 ModelSim RTL 回归通过。正常 `i2c_start_en/cam_init_done` 等待不再产生运行 fault；任一已启动源复位、CDC overflow、运行 video reset、停钟超时、重复授权或指定命令错误锁住整个 camera session。故障广播四路 transport_abort，不重新生成 cold reset，不输出 drain_ack。

**这是隔离候选，不是冻结 top 的直接替换件，也不支持 warm reset 恢复。** 真实 top 尚没有可信的配置 epoch 接口；本候选明确要求由配置上电 epoch 提供，未把 DDR init、button、camera startup counter 或 AXI reset 假接成冷授权。冷授权不代表 DMA drain 或旧 host ownership 已清除。

## 输入依据与隔离范围

先读了 `../four_camera_recovery_review/REPORT.md`、`tb_startup.sv` 的真实启动 1111/首次有序授权 0000 对照，以及 `../cdc_boundary_recovery_candidate/REPORT.md` 和 CDC 实现。重新核对冻结 `fpga_v8_cooperative_top_v2_rfg01.v:358` 的 `axi_rst=~ddr_init_done`，1025 起配置初始化的 startup counter，以及 binding 115/119 的 `cam_rst_n=i2c_start_en`、`ov_rst_n=rst_n & cam_init_done`。

新增 RTL 只有上述两个模块。旧 CDC/wrapper/controller、TC04 writer/stream_pipe、七路 arb、TC03 adapter、vendor FIFO/primitive 均直接引用，未复制修改。仅从审查目录派生必要 TB，并记录 `.sv.diff`；`run.py` 对启动摘录与冻结原始计数片段做字节一致性检查，不缩短真实 startup counter。新模块名做了字节级重名扫描。

`protected_result.json`：1033 个被监视源码/工程/约束/脚本/文档 SHA256 不变，涵盖既有候选、审查、冻结、生产 source/IP 和工程文件；不是整个工作区所有文件的快照。未执行 remote、PDS、program。Hindsight 不可连接，本报告依据本地 RTL 和日志。

## 授权及监督合同

| 接口/状态 | 实际行为与限制 |
| --- | --- |
| `config_epoch_reset` / `epoch_reset` | 仅由配置上电 epoch 提供的可信初始化输入，覆盖 supervisor 的全部 sticky 状态与 source heartbeat divider。必须保证真实初始化被执行。不能由本模块自行验证“这真是一次配置”；平台若把普通 warm reset 接进来就违反合同。 |
| `config_cold_request` / `cold_request` | epoch reset 期间保持低，释放后一次上升并保持到 `authorization_used`。两级同步后连续 `QUALIFY_CYCLES` 个采样才消费；默认 4。未消费的短请求也 fail-closed，不静默重试。初次请求后再次上升，即使第一次尚未合格，也异步锁 fault。跨 epoch 一直为高不能授权。 |
| `authorization_used` | 每 epoch 最多置位一次。request 后续正常下降不清授权；保持高不算重复上升。外部不能把重复 request 当新的配置 epoch。 |
| 三路真实源条件 | 每相机 `raw_ready=i2c_start_en & cam_init_done & ov_rst_n`，两级同步，并同时检查原始条件。不能只观察 sensor reset pin。等待初始化不算 fault；超过 STARTUP_LIMIT 则会话永久失败。 |
| `source_started[i]` | 授权合格、真实源条件成立且看见近期该 source clock heartbeat 后永久置位。四路独立：其余相机尚未 ready 时，此相机之后的任一源条件下降也锁住会话。不是等待全四路 ready 才开始监督。 |
| source clock | 每路 source clock 的四位分频计数 bit3 经两级同步。未起振时不产生 started；已启动后没有 heartbeat 达 CLOCK_LIMIT 则故障。时钟恢复不能解锁。停钟检测有界但不瞬时，也不等于帧活性检查。 |
| video reset | 初始保持高可正常等待；曾经采到低后任何重新拉高都是不支持的 warm reset，异步 fault。它从不清 supervisor。 |
| `cold_system_reset` | epoch 内初始保持高，只有一次资格消费、四路 started、当前三路源条件全成立、video reset 低且无会话错误时才下降。下降后永不因本地 reset/fault/request 再上升。启动失败时保持高，同时 sticky 会话故障关闭所有 admission。 |
| `boundary_fault[3:0]` | cold release 后纳入异步会话锁存。启动期间 CDC 输出中的 raw local reset 属正常等待，不直接误报；源启动之后的真实局部 reset 由独立 raw_ready/video 监督补足。 |
| `capture_abort_req/writer_abort` | 对已经 started 的源同步采样，锁会话故障；真实 binding TB 已连接 wrapper dma_abort_req 和 writer data_in_abort。该返回环路经过寄存器，不形成 transport_abort→abort_req 的组合环。 |
| `transport_abort[3:0]` | 会话故障广播全四路。故障寄存器加原始紧急 reset/boundary 原因立即封锁，不依赖四个 writer 都产生 abort ack；空闲 writer 可以没有 ack。 |
| `admission_enable` | 初次 release 且无会话错误。它仅是新采集/新授权的外层许可，**不表示 CDC 内部 ready、DMA 空闲或 drain**。旧 CDC 仍自行等待两域 release/交叉 ready 和 VSYNC 先低后新上升，像素不会越过其原有约束。 |

默认 STARTUP_LIMIT=134217728 个 video 周期（131 MHz 约 1.02 s），CLOCK_LIMIT=4096（约 31.3 us）；部署前必须结合 SCCB 最坏初始化时间、实际 source/video 频率与抖动配置。参数须为正、在有符号 32 位计数范围内。heartbeat 高/低脉宽必须足够被 video 域采到，不支持任意未知频率比的无条件 clock monitor 保证。

## 可 review 的最小顶层连接

`four_camera_supervised_boundary.v` 已实际例化四个原 `cdc_recovery` 和 supervisor，在 `tb_supervisor` 中运行。它接受真实 capture 输出，导出四路 video 数据、FIR clear、transport_abort、会话 fault 和 admission；没有 writer/arb/adapter reset 输出。

| 实际层级所需贯穿端口 | 应接位置 |
| --- | --- |
| 配置 epoch 的两个可信输入 | 本候选 `config_epoch_reset/config_cold_request`。**冻结 top 无可直接声明可靠的现成来源，须新增平台契约与接入。** `camera_ctrl_rst_n` 只提供相机控制上电时序，不是此来源。 |
| 每个 binding 的 i2c_start_en、cam_init_done、ov_rst_n | 通过 parent 暴露，接三组四位状态；不能拿 cam_rst_n 代替全部三项。 |
| source 数据与 cam clock | 保持原 capture 和负沿寄存级后接本候选四路输入；CDC cam_rst 仍接 `!i2c_start_en`，system_reset 独立接 cold_system_reset。 |
| `fir_clear[i]` | 与该路 FIR 的原初始化 reset 合并；供数据前处理隔离。不可扩展到 writer/pipe/arb/adapter reset。 |
| `transport_abort[i]` | 接该路原 recovery wrapper 的 transport_abort；它已接 capture_stop/flush、禁止 frame_good/publish 和 controller abort。 |
| wrapper `dma_abort_req[i]` | 原样接该路 TC04 writer.abort_req，同时回接 supervisor.capture_abort_req[i]。不要额外组合 gating 已展示的 AW/W/command。 |
| writer `data_in_abort[i]` | 原样回 wrapper.dma_abort，同时回 supervisor.writer_abort[i]。data_in_last/done 原样保持；二者均不是 drain。 |
| `camera_session_fault` / `admission_enable` | 上层需要与既有 guard 的会话 fault/新请求许可合并，禁止新 camera capture、frame/lease/host 消费授权。AXI 已承诺的请求和响应路径继续工作；不能组合关闭 AWVALID/WVALID/BREADY。 |

这里没有复制整个 parent/top，也没有宣称现有生产 guard/lease 已接入。数据路径需继续保留 parent 原 FIR/packer/wrapper、地址/bank 选择和所有 AXI 接口。最小模块的 FIR/DDR 接线意图有端口和注释，真实 wrapper 的故障/发布路径由 `tb_binding.sv` 单独实测；四 writer 共享路径由 `tb_shared.sv` 实测。三者是分层实证，不是一次完整四 sensor→capture→FIR→DDR→host 的端到端验收。

## 实际 RTL 测试与结果

仓库根运行：

```powershell
python project/fpga_v8_migration/board_v7/four_camera_reset_supervisor_candidate/run.py
# 可单独指定 supervisor startup ledger binding shared
```

ModelSim SE-64 10.6e，MODELSIM_BIN 可覆盖；所有 work/log 在新目录。没有 force DUT 内部状态/FIFO full、没有改真实 DUT、没有伪造 DMA done/B。DDR 侧 TB 在 vendor 用户接口驱动合法消费事件，不包含 DDR3 物理控制器/DRAM 模型。测试内每个全新 case 将测试 reset 同时视为新配置 epoch，仅用于清洁环境重建，**不构成生产 axi_rst→epoch_reset 接线建议**。

| 日志 | 覆盖及实际结果 |
| --- | --- |
| `supervisor/simulation.log` | 19 cases，errors=0。真实四 CDC；正常分步初始化、单路 clock 从 epoch 就停住后迟到、永久不起振、init 不完成、其余源尚未 ready 时已启动源短 reset、ov_rst_n/i2c/cam_init 单侧短 reset、video warm reset、运行 source 停钟、四 CDC 同时 fault、capture/writer 错误返回、自然 FIFO overrun；短授权、重复授权（含首次资格未完成）、跨 epoch 持高非法请求；video 最后释放的正常启动。 |
| `startup/simulation.log` | 原 50 MHz startup/power_on 计数逻辑、四个真实 CDC；naive_fault=1111，监督器 ordered_fault=0000，errors=0。之后 video/AXI warm reset：warm_fault=1、cold=0，无法重授权。 |
| `ledger/simulation.log` | 真 TC04 writer/pipe，ID 1/4/2/8 各 8 cutpoints，共32 cases，errors=0；故障经本 supervisor 广播。AW stall、AW 已接收、W stall、部分 W、WLAST stall、等 B、B 同拍故障以及无 AW。每个有 AW 的 case 保留 1AW/16W/1B；B 延迟1100 cycles > WD_LIMIT=1000，无提前 completion。 |
| `binding/simulation.log` | 真 CDC→supervisor→真 recovery wrapper/controller/packer→writer，11 cases，errors=0。自然256像素生成数据/tag命令，命令/数据/tag切点与真实 dma_done 同拍故障；9=冷 epoch 后正常发布1次，10=tag DMA已退休时故障，无 abort ack 但 publish=0。实际 wrapper abort_req/writer abort 回接 supervisor。 |
| `shared/simulation.log` | 四真 writer 竞争真7-slot arb+TC03 adapter+vendor FIFO，slot4–6空闲。单路 fault 和四路并发 fault 都由 supervisor 广播；两次均4AW/64W/64vendorW/4B、zero_strobe=60、busy=0、errors=0。延迟 vendor 最后一拍150 cycles > WD_LIMIT=100，**逐拍检查 owner 值和 busy 保持**，无 B/命令完成提前出现。 |

启动日志观测时间 `8311636.920 ns`（约8.312 ms）来自保留原始计数逻辑后等待监督器释放的 TB 观测点，不是板上 SCCB/PCLK 起振测量。该套 startup 为 cam_init/ov_ready 使用 cam_rst_n 测试替身；独立 `supervisor` 套件才分别操纵三组源条件和迟到时钟，未假称完整仿真 I²C 配置。

自然 overflow 用更快的 source 连续合法像素填满真实 CDC（case13 boundary=0001），无 force；四路 reset 同时注入 case10 得到 boundary=1111。0.2 ns 请求只证明数字事件捕获，不是器件最小脉宽合格。五套编译日志均0 errors/0 warnings；仿真存在未用诊断端口等继承 warning，不宣称零仿真 warning。

## 仍需系统条件与禁止扩大结论

1. **配置 epoch 的可信来源与全系统 ownership 重建尚未实现。** 每次新 epoch 前，平台必须确保相机/capture/CDC/FIR/packer/controller/DMA/pipe、全部共享 master/arb/adapter/vendor DDR 和 PCIe/lease/bank/generation 不再接受旧响应或复用旧发布。epoch/cold_authorization 是平台前提，不是本模块通过计时或四个 abort 自动推导出的 drain。旧已发布帧不能被新 fault 撤销，脏 bank 不能作为好帧重新发放。
2. **运行 axi_rst/button DDR reset 仍不支持。** supervisor 会 fail-closed，但冻结 top 的 axi_rst 仍会清 writer/arb/adapter账本；本候选不使这种物理 reset 自动安全。系统必须将其视为会话终止/重新配置流程，不能依赖本地 retry；若要保留义务，AXI 时钟和 ledger 必须保持运转。
3. **下游无限不响应时没有有限时间退休保证。** watchdog、初始化超时、停钟超时均不能生成 B、取消已广告 AW、丢剩余 W或释放共享 owner。本次证明的完成以 vendor 后续真实响应为条件。
4. **物理实现未验收。** 新 async fault/request event 寄存器、多异步控制映射、reset recovery/removal、短脉宽、同步器保护、raw_ready 组合故障路径及候选原 metadata/Gray CDC 都需要设备约束与实际工具检查。没有 PDS/synthesis/PNR 签核。`clk` 使用 video 时钟，若该监督时钟自己停止，clock timeout 无法计数；需已有独立 always-on 系统健康监控撤销新授权。本模块只在 video 时钟工作前提下监督 source clocks。
5. **完整四路生产 parent/top、guard/host admission 尚待接入和验收。** 最小连接模块/分层 TB 不能替代四路 FIR/capture/实际 I²C、其他三 master、host lease 生命周期与真实 DDR 控制器端到端测试。board source 少像素、物理 sensor 时序和先前 recovery 报告的其他阻挡仍保留。

交付范围是可 review 的独立监督 RTL、最小四 CDC 连接、真实写路径回归与明确的平台接口条件；没有声称可部署、热恢复、全系统 drain 或 DDR 内容回滚。
