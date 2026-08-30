> generated_by: Codex manual bootstrap
> verified_at: 2026-08-30
> provenance: root guide, TODO, source tree, PDS reports, and manual inspection

# Domains

## Pango PDS 实现流程

HDL 经 compile、synthesize、dev_map、PNR、timing report、netlist 和 bitstream 阶段形成实现产物。阶段命令成功不等于时序或板级接口已经满足约束。

## 外部四级仿真

ModelSim/QuestaSim 分别承担行为级、综合后、PNR 后功能和 PNR 后时序仿真。USIM 用于 PNR 前原语，VSIM 用于 PNR 后原语；时序仿真还依赖正确层级的 SDF 标注。

## 产品顶层与 IP 示例边界

厂商 IP 自带 `example_design`、testbench 或 PNR 工程只能证明示例自身状态。只有产品顶层显式包含所需 RTL、IP、板级约束和集成测试后，结果才能归属于产品工程。

DDR3 D2 已进一步固定该边界：厂商 `test_ddr`、持续运行 BIST 与旧 testbench 保持原样；后续有限自检由项目自有 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 承担。首版仅执行 16 个单 beat 写读比较 pair，地址 `0x0..0x78`、步长 8，并通过稳定公开的 `test_done`、`test_failed`、`failure_code`、`error_count`、`completed_pairs` 和首错信息完成签核。

## CDC 与异步 FIFO

单比特电平、脉冲、多比特数据和 FIFO 指针需要不同跨时钟域策略。同步器降低亚稳态传播概率但不消除亚稳态；时序例外只能施加在结构已验证的 CDC 上。

OV7725 的帧同步当前是长电平而非单周期脉冲，且 `wr_load`/`rd_load` 分别被多个逻辑独立采样。整改契约要求源域用 toggle 或握手表达事件，目标 `ui_clk` 域只同步一次、生成单周期事件后统一扇出，避免多同步器重汇聚。

厂商异步 FIFO 可以承担多比特数据跨域，但 reset/flush 仍属于 RDC。write FIFO 的 camera/UI 两侧和 read FIFO 的 UI/pixel 两侧必须分别在本地时钟域释放复位；只有确认 SP6.4 对厂商指针同步结构的识别后，才允许添加最窄范围例外。

## 复位域交叉

各时钟域应明确复位来源和释放方式。外部异步条件或其他时钟域状态直接释放复位会形成 recovery/removal 风险，应采用异步置位、同步释放或等效的经验证结构。

OV7725 已确定 sys、I2C、camera、pixel 和 DDR UI 域需要各自的本地复位。O3-A 必须先将 `ddr3_init_done` 同步为 camera/pixel 域的状态与使能，O2-C1 才能解除它对其他域异步复位释放的直接控制并建立普通时钟域本地复位。

O1-B 将高有效 reset 接入四个 serializer 内的八个 OSERDES 后，PDS 新报告 Slow Recovery `pixel_clk → pixel_clk_5x` `-0.643 ns / TNS -4.191 ns / 8/8`。O2-A 已确认 SP6.4 对同一 `RST` 同时建立 `OCLK/SERCLK=pixel_clk_5x` 与 `OCLKDIV=pixel_clk` 的 recovery/removal 检查，并将八个唯一 `opit_2/opit_2_com/OSR_IOLHR` endpoint 固定为验收集合。

O2-B 已实现上述级联结构并完成 compile/七阶段实验，但 Slow Recovery 同时出现 `pixel_clk_5x → pixel_clk_5x -0.349 ns / 8/8` 和 `pixel_clk_5x → pixel_clk -2.173 ns / 8/8`，Fast Recovery 反向组仍为 `-1.464 ns / 8/8`。八个反向 endpoint 均为 OSERDES `OCLKDIV` 检查；方案已否决、RTL 已回退，baseline/gate 未放宽。

O2-D1 已否决动态 `GTP_IOCLKBUF` 门控：功能模型虽能无毛刺停启，但 PG2L100H SP6.4 Liberty 没有 `DI` clock-gating check，STA 不能证明停钟、复位、释放、启钟的运行时顺序。唯一待验证候选为新增 `CLKOUT3=65.0026 MHz`、约 `+0.192 ns` 相位控制输出，并为四个 serializer 各自复制本地 reset 寄存器；纯相位调整不足以通过。

进入实现前先完成 O2-D1-R 回退基线重建，再由 O2-D1-G 固定 `/5` 奇数分频 waveform、IOCLKBUF 前后取点、控制器状态/计数、serializer hard reset 与业务 reset 分权、首个有效 TMDS symbol 和停止条件。审核后只允许一次 O2-D2，禁止第二相位扫描、false path、multicycle、clock-group waiver 或失败 baseline 放行。

两个厂商异步 FIFO 的 reset/flush 属于独立的 O2-C2，不与 O2-C1 的普通寄存器复位混批；帧事件 CDC 归 O3-B。O4 只有在 O2-C2 与 O3-B 都完成后才可进入约束和最终时序闭环。

## 时序闭环

`All Constraints Met` 只覆盖已建模路径。验收还需检查未约束时钟、未约束关键 I/O、CDC 报告、setup/hold/recovery/removal、SDF 标注与板级接口假设。

## PDS 生成物与可重复构建

GUI 原生工程目录中的日志、数据库和绝对路径脚本是历史证据，不是可移植构建入口。目标结构应以相对路径脚本和统一 `build/` 目录隔离生成物。

OV7725 O1-B 已按该边界固定 16 个手写 RTL、4 个活动 IDF 和唯一顶层 FDC，在 SP6.4 下完成七阶段实现：进程退出 0、日志 `E: 0`、warning `4067`、critical `81`，五类产物均非零。严格 gate 返回 1；baseline 只有在七组 corner/check/clock pair/endpoints 精确匹配时返回 0，并继续标记不可发布。

## RTL 卫生与板级接口边界

OV7725 O1-A 以 `RTL_HYGIENE_AUDIT.md` 固定手写 RTL 卫生契约，O1-B 已完成其中 38 条确定性修复：显式零扩展、定宽 tie-off、地址/长度编码、`rst_n` 声明、删除 `sys_init_done` 死网及 serializer reset 连接均已落地。

serializer 接收高有效 reset；O1-B 已让该信号驱动四个 serializer 内共八个 OSERDES 的高有效 `RST`。O2-B 级联释放实验已由 STA 否决并回退，当前仍是旧七组失败基线；O2-D1-R/O2-D1-G 完成并经用户审核前不得启动新的 serializer RTL。

`mem_a` 是板级接口冲突而非机械消警：活动 IP 为 14 bit，顶层/FDC 为 15 bit，当前综合网表将第 15 bit 绑 0。它必须等待 H3 板级 DDR3 事实并在 O1-C 独立处理；O1-B 不修改 `mem_a`、IP、FDC、CDC/RDC 或时序例外。

## VSCS 注释治理

后续手写 Verilog/SystemVerilog 应记录设计意图、接口契约、FSM、复位、CDC/RDC 和风险，不重复可以从代码、Git 或工具报告自动推导的事实。
