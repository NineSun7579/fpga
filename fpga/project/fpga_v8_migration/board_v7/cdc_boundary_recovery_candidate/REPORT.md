# CDC boundary recovery 隔离候选

结论：已实现并实际仿真 **fail-closed 修正**。任一独立 reset 不再造成无 fault 重放；故障通过新增接口接入真实 FIR、DDR wrapper/controller 的隔离派生链路，禁止后续帧发布。**不是可直接替换上板版本，不支持局部自动恢复，不宣称 DMA/DDR 已安全退休。** 只有显式全域 `system_reset` 才允许重新开始，且必须等待两个域 ready 和新完整帧边界。

全部新增文件位于本目录；未改旧候选、冻结 RTL、生产工程或 IP。未执行 remote/program/PDS。`protected_hashes.txt` 验证旧候选/冻结输入/原集成 harness 中 605 个被监视文件运行前后 SHA256 不变。Hindsight 服务连接失败，本报告依据本地代码与日志。

## 先读的实际证据

`../cdc_boundary_candidate/review_independent/REVIEW.md`、`simulation.log` 记录：源 64 像素已排空，仅 video reset 后累计输出 128，fault=0；marker 在 pixel FIFO=1024、meta 未满时触发故障。实际 cam/video reset 分离，不符合旧候选联合 reset 前提。

冻结 parent 的 `cam_dma_abort`、`cam_dma_abort_req`、`cam_dma_done` 是现有接口；没有本候选可以使用的全系统 DMA drain/epoch-clear 完成确认。真实 controller 原 `publish = dma_done && WAIT_TAG_DONE` 没有排除同拍 abort。因此不能把 OR 两个 reset 或 controller 进入 IDLE 当作 AXI AW/W/B 已经退休。

## 实现与新集成接口

- `generate.py` 按字节从旧候选及冻结 wrapper/controller 生成 `cdc_recovery.v`、`ddr_recovery.v`、`ddr_ctrl_recovery.v`，各自附 `.diff`。没有修改原文件。metadata FIFO 逻辑保持原有排序。
- 新输入 `system_reset` 是**系统全域 reset 契约**，不是 `cam_rst | video_rst` 的别名。局部 cam/video request 异步锁存 `reset_fault`；溢出/非法 overlap 锁存 `transport_fault`。任一触发立即隔离两侧 FIFO 和输出。两个 sticky 状态只能由 system_reset 清除；甚至同时拉高两个局部 reset 也不能清故障。
- 两域分别三级释放、两级交叉 ready 同步。某域停钟时它不能宣告 ready，对端也不能入队/消费；局部请求短于任一时钟周期仍在数字仿真中捕获。释放后先见 VSYNC 低，再见新的上升 marker 才 rearm，不能把复位时已经为高的 VSYNC 当新帧。复位/等待期间的新像素明确丢弃，不计作可恢复旧帧，不补像素。
- pixel full 仅在 `s_valid` 时拒收。marker-only 在 metadata 未满时可继续排队；下降沿带 valid 仍使用原有 marker-first 排序与 guard。
- `boundary_fault` 接 FIR reset，并接 `ddr_recovery.transport_abort`。wrapper 将其加入 capture_stop、engine_busy、frame_good 否定、capture flush、dma_abort_req 以及实际 controller 的 dma_abort 输入。
- controller 派生版使 abort 在所有状态优先，清 pending SOF/命令寄存器，`frame_done` 与 `publish` 都排除 abort。因此 fault 与 tag `dma_done` 同拍时不能增加帧成功计数或发布 bank。
- `binding_recovery/chain.v` 保留真实 capture 和负沿寄存级，新增独立 system_reset、boundary_fault；cam/video request 分开驱动。`binding_recovery/tb.sv` 可审查到 FIR、wrapper/controller 的全部实际连接。这是新增集成接口的真实模块仿真，**不是已改造整个四路 parent/top**。

## 运行与结果

命令（仓库根目录，ModelSim 10.6e / 真实 vendor FIFO 和 primitive，无 FIFO stub）：

```text
python project/fpga_v8_migration/board_v7/cdc_boundary_recovery_candidate/run.py
python project/fpga_v8_migration/board_v7/cdc_boundary_recovery_candidate/run.py --extended
python project/fpga_v8_migration/board_v7/cdc_boundary_recovery_candidate/run.py --review
```

| 日志目录 | 本次实际结果 |
| --- | --- |
| baseline | 29 cases，errors=0；保留 307199/307070 admission 失败复现 |
| candidate | 29 cases，errors=0；短尾全尺寸 source/output/admitted=307200，publish=1 |
| candidate | 连续三帧 source/output/admitted=921600，published=3 |
| extra | 2 cases，errors=0；原忙时丢整帧契约未改变 |
| long_baseline / long_candidate | 各 3 cases，errors=0；candidate 长高电平保留，末高宽 5925/5924/5796 video cycles |
| review / review_board | 两组 12/16ns、11.905/7.619ns；所有定向断言 errors=0 |
| contract | 原有 800 像素/101 marker 顺序、下降沿首像素、三种 fault、积压 reset 回归，errors=0 |
| binding_recovery | 4 个真实 capture 场景，BINDING_DONE errors=0 |

关键实际输出：

```text
RECOVERY near_full accepted=11000 output=11000 fault=0
RECOVERY unilateral case=0 before=64 after=64 fault=1
... case=1..7 同样 before=64 after=64 fault=1
RECOVERY marker_full accepted=1024 output=1024 fault=0
RECOVERY metadata_full fault=1 abort=1
RECOVERY overlap fault=1 abort=1
RECOVERY stopped_release new_frame_output=64 fault=0
RECOVERY controller_abort cutpoints=5 no_dma_retirement_claim=1
RECOVERY_BINDING video_reset before=128 after=128 fault=1
RECOVERY_BINDING source_reset output=307200 publish=1 fault=1
RECOVERY_BINDING full_global_reset source=307200 output=307200 admitted=307200 published=1
```

unilateral 0/1：排空后 video/source 短脉冲；2/3：128 像素积压、video 停钟时短脉冲；4：两钟停住时 video request，随后恢复；5：积压 source request；6/7：积压下 video/source 100ns request。短脉冲=0.2ns 只是数字模型测试，不是器件最小脉宽验收。复位后输入新像素仍锁死。overflow 后同时局部 reset 不清 sticky；显式 system reset 才恢复。

启动测试覆盖 video 停钟、cam request 先释放、复位期间持续 valid、重新开钟时 VSYNC 已高、低后新上升沿才恢复。原 contract 为匹配新契约增加 reset 后 ready 等待，以及 pixel-overflow 前的初始帧 marker；原断言计数未放宽。首次适配脚本因空格匹配未插入 marker，导致该项未进入 armed 状态，原始失败保留于 `contract/initial_unadapted_failure.log`；修正变换并加匹配断言后重跑通过。

controller 的 5 个 cutpoint 是 ADDR/DATA/ADDR_TAG/DATA_TAG/WAIT_TAG_DONE：通过显式 force 状态测试真实派生 controller 的 abort/done 竞争。不是用 force 生成 DMA retirement；正常帧沿用原 endpoint 命令/beat 完成模型。binding full 注入显式 force pixel_full，局部 overflow 自然填满的另有 review 测试。故障后完整 307200 帧通过发生在全域 reset 之后。

编译日志 0 errors/0 warnings；仿真包含继承环境 novopt，以及 TB 未连接非检查端口的工具 warning（以各 simulation.log 为准），无最终 FAIL。

## 剩余阻挡与禁止扩大结论

1. **系统 DMA drain/reset 是硬阻挡。** 当前没有已连接的 drain 完成确认。fault 发生时已经交给 DMA 的命令、数据或 tag 可能仍在途；候选禁止新的帧发布，但不撤回已完成发布，不证明 DDR 中没有旧写入，不保证任意 AXI 通道有限时间退休。状态机回 IDLE、capture_flush=4 都不等于 retirement。必须停用受影响会话并对 DMA、DDR 写路径、FIR、CDC、buffer ownership 一起执行系统 reset；全域 reset 解除前由系统保证旧事务不会回流。不能把普通 video_rst 接到 system_reset 自动重试。
2. **物理 CDC 未验收。** Gray 指针双方向 skew/max-delay、异步分组例外优先级、同步级保护、metadata 2048×3 存储映射/组合读时序、reset recovery/removal、短脉冲 async 捕获、sticky fault 到 video 控制的异步禁止路径均需实际工具验收。当前 raw fault 直接用于故障优先禁止路径；数字同拍测试不证明模拟亚稳态或任意相位硬件竞争安全。未跑 PDS，不能宣称多异步控制寄存器映射/四路 PNR 已过。
3. **覆盖边界明确。** 没有完整四路 top、真实 DMA AXI ledger/B-response 故障矩阵；没有两个释放先后与所有停钟/任意相位的穷举或形式证明。已测停读钟释放与停写钟后请求，但不能写成全部启动组合已验收。需要后续系统集成证明才能放行。
4. **源数据不足仍独立阻挡。** 不解释 board 上 source=307199/307198/307193，不补像素、不放宽 307200；仍需实际 capture/HREF/VSYNC overlap 和吞吐/尾 blank 的板级证据。hsync 与统计快照的原有限制保留。

可交付的是独立可审查 RTL、差异、可重跑真实模块仿真和上述剩余阻挡；不是生产替换、自动恢复功能或 DDR 安全认证。
