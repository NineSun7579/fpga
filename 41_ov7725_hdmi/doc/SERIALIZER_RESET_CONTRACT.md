# Serializer Reset 联合释放契约

## 1. 目的与边界

本文定义 OV7725 HDMI 工程中四个 TMDS serializer、八个 `GTP_OSERDES_E2` 的复位契约，记录 O2-B 最小方案的实现、真实 STA 否决与回退，并为后续 O2-D1 备选架构评审提供事实基线。

O2-A 仅完成证据核验和设计决策，不修改 RTL、厂商 IP、FDC、RCF、gate 或生成物，也不声明动态仿真通过。

本文只处理 serializer 局部复位。以下问题仍属于后续批次：

- `ddr3_init_done` 跨域同步与顶层复位耦合：O3-A、O2-C1；
- 两个异步 FIFO 的 reset/flush：O2-C2；
- 帧事件 CDC：O3-B；
- 最终约束与全设计时序闭环：O4；
- `mem_a` 板级冲突：H3、O1-C。

## 2. 一手证据

| 证据 | 位置 | 已确认事实 |
|---|---|---|
| 当前复位同步器 | `rtl/hdmi_top/asyn_rst_syn.v:23-49` | 低有效异步输入；两级寄存器异步置 1、随目标时钟同步清 0；输出为高有效 reset |
| DVI 顶层 | `rtl/hdmi_top/dvi_transmitter_top.v:40-132` | 唯一 `reset` 在 `pclk` 域释放；同时驱动三个 encoder 和四个 serializer |
| Serializer | `rtl/hdmi_top/serializer_10_to_1.v:25-125` | 每个实例含 master/slave 两个 OSERDES；`RST` 高有效；`OCLKDIV=serial_clk`，`OCLK=SERCLK=serial_clk_5x` |
| Device map | `build/pds/device_map/run.log:206-209,292-295` | `opit_2` 对应 `GTP_OSERDES_E2_data_master`，`opit_2_com` 对应 `GTP_OSERDES_E2_data_slave` |
| SP6.4 功能模型 | `E:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation/GTP_OSERDES_E2.v:37-45,70-78,221-232` | `LRS_TYPE_DQ*` 支持 `ASYNC_RESET`；`RST` 直接进入本地 reset 路径 |
| SP6.4 timing model | `E:/pango/PDS_2022.2-SP6.4/arch/vendor/pango/verilog/bsim/V_OSERDES_E2.v:921-928` | 同一 `RST` 分别对 `OCLK` 双边沿、`OCLKDIV` 上升沿和 `SERCLK` 上升沿建立 `$recrem` |
| PG2L100H 官方示例 | `E:/pango/PDS_2022.2-SP6.4/example/PG2L100H_lvds4to1/rtl/pgd_ddr_lvds4to1_tx_top.v:59-65,114-120` | `.RST(~tx_gtp_rstn)` 证明 OSERDES `RST` 高有效；示例时钟/复位生成方式不作为本工程直接模板 |
| 活动 PLL | `prj/ipcore/pll_clk/pll_clk.v:79-115` | `CLKOUT0/1` 的静态 phase/cphase 参数均为 0 |
| 最终 STA | `build/pds/report_timing/ov7725_hdmi.rtr:17-24,116-153,227-264` | `pixel_clk` 与 `pixel_clk_5x` 是同一 GPLL 的 1:5 相关时钟；serializer recovery/removal 结果可独立追踪 |

证据优先级为：当前 SP6.4 原语模型与最终 STA、当前项目 RTL、同器件官方示例。示例只用于确认原语接口和极性，不能覆盖本工程的实际时钟关系与 STA。

## 3. 当前结构

```text
reset_n
  │ 低有效异步条件
  ▼
asyn_rst_syn @ pixel_clk
  │ 高有效 reset
  ├─ 三个 TMDS encoder @ pixel_clk
  └─ 四个 serializer
       └─ 八个 OSERDES
            OCLKDIV = pixel_clk
            OCLK    = pixel_clk_5x
            SERCLK  = pixel_clk_5x
```

当前结构相对 `pixel_clk` 同步释放，但同一 reset 直接进入 `pixel_clk_5x` 捕获的 OSERDES 本地异步复位端点，因此不能视为高速域已经闭环。

## 4. 时钟与 STA 基线

最终报告中的相关时钟为：

| 逻辑时钟 | PDS generated clock | 频率 | 周期 |
|---|---|---:|---:|
| `pixel_clk` | `sys_clk|u_pll_clk/u_gpll/CLKOUT0_Inferred` | 65.0026 MHz | 15.384 ns |
| `pixel_clk_5x` | `sys_clk|u_pll_clk/u_gpll/CLKOUT1_Inferred` | 325.0975 MHz | 3.076 ns |

Serializer reset 当前时序结果：

| Corner | Check | Launch → Capture | WNS/WHS | TNS/THS | Failing/Total |
|---|---|---|---:|---:|---:|
| Slow | Recovery | `pixel_clk → pixel_clk_5x` | -0.643 ns | -4.191 ns | 8/8 |
| Slow | Removal | `pixel_clk → pixel_clk_5x` | +0.305 ns | 0 | 0/8 |
| Fast | Recovery | `pixel_clk → pixel_clk_5x` | +0.123 ns | 0 | 0/8 |
| Fast | Removal | `pixel_clk → pixel_clk_5x` | +0.114 ns | 0 | 0/8 |

Slow Recovery 的 startpoint 均为：

```text
u_hdmi_top/u_rgb2dvi_0/reset_syn/reset_1/opit_0_srl/CLK
```

## 5. 八个唯一 endpoint

PDS 对不同边沿组合会报告同一物理 endpoint 的多条 path。验收按以下八个唯一 `OSR_IOLHR` 计数，不按 path 行数计数。

| Serializer | 逻辑原语数 | Master endpoint（`opit_2`） | Slave endpoint（`opit_2_com`） |
|---|---:|---|---|
| `serializer_b` | 2 | `.../serializer_b/GTP_OUTBUFDS_data_lane/opit_2/OSR_IOLHR` | `.../serializer_b/GTP_OUTBUFDS_data_lane/opit_2_com/OSR_IOLHR` |
| `serializer_g` | 2 | `.../serializer_g/GTP_OUTBUFDS_data_lane/opit_2/OSR_IOLHR` | `.../serializer_g/GTP_OUTBUFDS_data_lane/opit_2_com/OSR_IOLHR` |
| `serializer_r` | 2 | `.../serializer_r/GTP_OUTBUFDS_data_lane/opit_2/OSR_IOLHR` | `.../serializer_r/GTP_OUTBUFDS_data_lane/opit_2_com/OSR_IOLHR` |
| `serializer_clk` | 2 | `.../serializer_clk/GTP_OUTBUFDS_data_lane/opit_2/OSR_IOLHR` | `.../serializer_clk/GTP_OUTBUFDS_data_lane/opit_2_com/OSR_IOLHR` |

Device-map 日志把四个 `GTP_OSERDES_E2_data_master` 打包到 `opit_2`，把四个 `GTP_OSERDES_E2_data_slave` 打包到 `opit_2_com`；因此八个 STA endpoint 的逻辑角色和物理端点可唯一对应。

## 6. 候选结构比较

| 方案 | 结论 | 原因 |
|---|---|---|
| 保持当前 `pixel_clk` reset 直接驱动 OSERDES | 拒绝 | 已有 Slow Recovery 8/8 失败 |
| 从顶层 `reset_n` 独立生成 `pixel_clk_5x` reset | 拒绝作为首选 | 可能使 OSERDES 早于 encoder 退出复位，破坏现有先后关系；仍需单独证明 `OCLKDIV` 检查 |
| 将两个独立同步 reset 组合后驱动 OSERDES | 拒绝 | 形成复位重汇聚；最终释放由最后变化分支决定，增加 RDC 分析复杂度 |
| 现有 `pixel_clk` reset 后级联 `pixel_clk_5x` 两级释放同步器 | O2-B 已否决 | 实现范围最小，但真实 STA 把八个 OSERDES 的失败转移到 `pixel_clk_5x → pixel_clk`，慢角同域检查也仍为负 |
| 显式相位计数、统一复位控制器或厂商推荐结构 | 进入 O2-D1 评审 | 只读比较释放边沿、状态顺序、原语检查和实现边界；评审前不预设状态机结构 |

首选方案利用两个 PLL 输出固定的 1:5 相关关系，但不把相位关系写成安全保证。只有实现后的 PDS recovery/removal 结果可以接受或否决该方案。

## 7. O2-B 历史实现契约（已否决）

本节保留 O2-B 实施时的输入、输出、文件和验收边界，作为失败实验的可追溯记录。对应 RTL 已回退，不代表当前设计仍包含 `serializer_reset`。

### 7.1 复位语义

- 输入来源：现有 `pclk` 域高有效 `reset`。
- Encoder reset：继续使用现有 `reset`，不改变三个 encoder 的行为。
- Serializer reset：新增高有效 `serializer_reset`。
- 异步断言：`reset` 变高时，`serializer_reset` 必须异步变高。
- 同步释放：`serializer_reset` 必须只在 `pclk_x5` 上升沿序列中变低。
- 同步级数：复用现有 `asyn_rst_syn` 的两级实现；该选择只适用于本批最小复用，不是全项目固定规则。
- 顺序：Serializer 不得早于 encoder reset 释放。
- 时钟假设：`pclk` 和 `pclk_x5` 在外层 `reset_n` 允许释放前必须已经运行；上游 `ddr3_init_done` 复位耦合仍由 O3-A/O2-C1 处理。

### 7.2 资料性连接草图

下列片段描述 O2-B 曾实现并完成 compile/STA 的连接；该实现已由真实 STA 否决并回退，不能作为后续候选模板直接复用：

```verilog
wire serializer_reset;

asyn_rst_syn serializer_reset_syn (
    .clk       (pclk_x5),
    .reset_n   (~reset),
    .syn_reset (serializer_reset)
);
```

四个 serializer 的 `.reset(...)` 均改接 `serializer_reset`。`serializer_10_to_1.v` 内八个 OSERDES 的 `RST` 连接保持不变。

### 7.3 文件边界

O2-B 功能 RTL 只允许修改：

- `rtl/hdmi_top/dvi_transmitter_top.v`。

O2-B 验证与状态文件可修改：

- `scripts/check_build.ps1`；
- `README.md`、`doc/SERIALIZER_RESET_CONTRACT.md`、根 `TODO.md`、`docs/IMPLEMENTATION_LOG.md`；
- `.nexus-map/**`。

O2-B 不修改：

- `rtl/hdmi_top/asyn_rst_syn.v`；
- `rtl/hdmi_top/serializer_10_to_1.v`；
- 顶层、camera、DDR、FIFO 或其他业务 RTL；
- PLL、DDR3、FIFO 等厂商 IP；
- FDC、RCF 或任何时序例外；
- `mem_a`。

### 7.4 VSCS 注释要求

O2-B 实施时的 RTL 注释必须说明：

- `serializer_reset` 是高有效、异步断言、相对 `pclk_x5` 同步释放；
- 它级联在 encoder 的 `pclk` reset 之后，用于保持释放顺序；
- 同一 OSERDES 仍同时受 `OCLK/OCLKDIV/SERCLK` 检查，安全性由 STA 判定。

注释不得声称“两级同步消除亚稳态”“保证无毛刺”或“保证时序通过”。极性、实例数量和连接关系由 RTL/elaboration 作为事实源，不在注释中重复维护长清单。

## 8. O2-B 验收

### 8.1 静态与 compile

1. PowerShell gate AST 无错误。
2. PDS compile 退出码为 0，日志无 `E:`。
3. 不新增手写 RTL 端口、位宽、隐式 net 或多驱动问题。
4. Elaborated design 仍恰有四个 serializer、八个 OSERDES，且八个 `RST` 全部由同一 `serializer_reset` 驱动。

### 8.2 七阶段实现

1. 从空 `build/` 完成 compile、synthesize、dev_map、pnr、report_timing、gen_netlist、gen_bit_stream。
2. PDS 退出码为 0，日志无 `E:`，五类关键产物存在且非零。
3. Slow/Fast Recovery 与 Removal 对八个 serializer endpoint 全部非负。
4. 不得出现新的 `pixel_clk_5x → pixel_clk` 或其他 serializer reset 失败 clock pair。
5. 必须确认八个 endpoint 仍被 recovery/removal 分析覆盖；“失败行消失”不能替代覆盖证明。
6. 其他既有 setup、DDR/FIFO recovery、板级 critical 仍由严格 gate 阻断，不在 O2-B 顺带处理。

### 8.3 Gate 更新

只有真实报告满足 8.2 后，才允许从 baseline 精确集合中删除：

```text
Slow|Recovery|pixel_clk|pixel_clk_5x|8/8
```

Gate 必须增加 serializer reset 的正向覆盖检查，验证八个 endpoint 的 Recovery/Removal 被分析且裕量非负。禁止加入 false path、multicycle、clock-group waiver 或新的 baseline 失败签名来让 O2-B 通过。

### 8.4 动态验证边界

当前没有可用的 ModelSim/QuestaSim，因此 O2-B 即使通过 PDS，也只能声明静态复位时序闭环，不能声明：

- HDMI/TMDS 动态复位通过；
- Serializer 在任意相位复位下均无 `X` 或无瞬态；
- 行为级、综合后、PNR 功能或 PNR 时序仿真通过。

S0/S3 就绪后必须补测异步断言、释放顺序、输出恢复、超时和带 SDF 的 timing violation。

## 9. 停止与回退条件

O2-B 出现以下任一情况必须停止并回退功能 RTL，不得扩大本批范围：

- 八个 endpoint 不能唯一映射或不再被 STA 覆盖；
- Slow/Fast Recovery 或 Removal 任一为负；
- 失败转移为 `pixel_clk_5x → pixel_clk` 或其他新 clock pair；
- 必须修改 PLL/IP/FDC/RCF 才能使首选方案通过；
- 必须同时修改顶层、camera、DDR、FIFO 或业务 CDC；
- 需要 false path、waiver 或新增 baseline 失败；
- 新增未分类 warning/critical 或关键产物异常。

回退后重新进入契约评审，评估显式相位 sequencer 或厂商推荐结构；不得在同一提交中试探多种方案。

## 10. O2-B 实施结果与否决

O2-B 仅修改 `dvi_transmitter_top.v`，新增级联的 `serializer_reset_syn` 并把四个 serializer 改接其输出。Compile 与从空 `build/` 的七阶段流程均退出 0，日志无 `E:`，五类关键产物存在且非零；这些结果只证明实现流程完成，不证明复位时序安全。

最终 Recovery 摘要如下：

| Corner | Launch → Capture | WNS | TNS | Failing/Total | 归属 |
|---|---|---:|---:|---:|---|
| Slow | `pixel_clk_5x → pixel_clk_5x` | `-0.349 ns` | `-1.599 ns` | `8/8` | 八个 OSERDES 的高速时钟检查 |
| Slow | `pixel_clk → pixel_clk_5x` | `+1.111 ns` | `0` | `0/1` | `serializer_reset_syn/reset_1` |
| Slow | `pixel_clk_5x → pixel_clk` | `-2.173 ns` | `-16.191 ns` | `8/8` | 八个 OSERDES 的 `OCLKDIV` 检查 |
| Fast | `pixel_clk_5x → pixel_clk_5x` | `+0.310 ns` | `0` | `0/8` | 八个 OSERDES 的高速时钟检查 |
| Fast | `pixel_clk → pixel_clk_5x` | `+1.830 ns` | `0` | `0/1` | `serializer_reset_syn/reset_1` |
| Fast | `pixel_clk_5x → pixel_clk` | `-1.464 ns` | `-10.863 ns` | `8/8` | 八个 OSERDES 的 `OCLKDIV` 检查 |

Slow/Fast Removal 对上述三组均为正，但不能抵消 Recovery 失败。详细报告将反向八个 endpoint 唯一映射到 `serializer_b/g/r/clk × opit_2/opit_2_com`；因此 O2-B 明确触发第 9 节“失败转移或任一裕量为负”的停止条件。

处理结论：

- 已回退全部 O2-B 功能 RTL，不提交失败结构；
- 不删除旧 `pixel_clk → pixel_clk_5x 8/8` baseline，不新增失败签名、false path、multicycle 或 clock-group waiver；
- `ddrphy_sysclk → pixel_clk` Recovery 总 endpoint 在本次实现中由 53 变为 54，当前报告可分为 read FIFO 34、原 `reset_syn` 1、video display 1、video driver 18；历史详细报告不足以做集合差分，留待回退后的等价基线重建确认；
- 下一批 O2-D1 只读比较显式释放相位 sequencer、统一复位控制器与厂商推荐结构，不在同一批实现试探方案。

## 11. O2-A 完成定义

O2-A 完成仅表示：

- `RST` 极性、快慢时钟检查和八个 endpoint 已由一手证据闭合；
- O2-B 当时的首选结构、文件范围、注释责任、验收与回退条件已经固定；该结构后来已由第 10 节真实 STA 否决；
- 没有修改功能 RTL、IP、约束或 gate，也没有运行新的实现/仿真。

O2-A 不表示 serializer reset 已修复，也不改变当前设计不可发布的结论。

## 12. O2-D1 评审结论与后续 gate

O2-D1 为架构评审，不修改 RTL、IP、PLL、FDC、RCF 或 gate。当前已确认：在两个 GPLL 输出分别驱动 `pixel_clk` 与 `pixel_clk_5x` 的拓扑上，局部增加同步级或等待周期不能结构性消除同一 `RST` 对 `OCLK`、`OCLKDIV` 与 `SERCLK` 的联合检查。O2-B 的真实 Slow/Fast Recovery 已证明，失败会在快慢检查之间转移。

### 12.1 已否决路线

动态 `GTP_IOCLKBUF` 门控不进入 O2-D2：

- 功能模型可以在低电平窗口无毛刺停启时钟，但这只是仿真行为。
- SP6.4 Liberty 没有 `DI` 相对 `CLKIN` 的 clock-gating check，也不能证明“停钟、断言 reset、释放 reset、重新启钟”的运行时顺序。
- divider `RST_N` 同样没有足以证明该顺序的 Recovery/Removal 模型。
- endpoint 在某个静态模式消失、功能仿真无报错或增加 waiver，均不能替代八个 OSERDES endpoint 的静态覆盖。

PG2L100H LVDS 示例只能支持统一硬块拓扑方向：它没有启用动态门控，也没有最终 STA 报告，不能作为门控释放已通过的证据。

### 12.2 唯一待验证候选

O2-D2 只允许执行一次以下不可拆候选：

1. 用 SP6.4 IP Compiler 重生成 PLL，新增 `65.0026 MHz` 控制输出；目标参数为 `STATIC_RATIO3=10`、`STATIC_CPHASE3=0`、`STATIC_PHASE3=1`，相对当前同相输出约延后 `0.192 ns`。
2. 每个 serializer 使用一只本地 reset 寄存器，直接驱动其两只 OSERDES；异步置位，且只允许在控制时钟上升沿同步清零。禁止在本地寄存器之后组合重汇聚。
3. O2-B 慢角高速路径总延迟为约 `1.480 ns`；新控制边沿到下一 OCLK 下降沿的名义窗口约 `1.346 ns`。要达到零 slack，本地 reset 总数据延迟需压到约 `0.939 ns` 以下，并应额外保留裕量。纯 PLL 相位调整不能闭合。
4. 首轮只测试该一个相位，不扫描其他相位。`phase=0` 不能依赖 STA 自动跳过同刻捕获边沿，更大的正相位只会继续缩短高速窗口。

O2-D1-G 仍需把异步断言条件、资格确认、ARM、OSERDES 释放、pixel 域 warm-up 和 RUN 的状态/计数语义写成无歧义契约。`dvi_encoder.v` 的多级中间流水寄存器不复位，因此“serializer 已释放”不等于“首个 TMDS symbol 已确定”；必须单独固定 encoder 填充和首个有效 symbol 条件。

### 12.3 同源 `/5` 拓扑与原子迁移

当前 `pixel_clk` 同时驱动 DDR read FIFO 读侧、`video_driver`、`video_display`、三个 encoder 和八个 OSERDES 的 `OCLKDIV`。候选拓扑必须：

1. 保留 `pixel_clk_5x` 为唯一高速源，经唯一 `GTP_IOCLKBUF` 驱动八个 OSERDES 的 `OCLK/SERCLK`。
2. 从同一高速源经唯一 `GTP_IOCLKDIV_E2(DIV_FACTOR="5")` 生成整个 pixel 域时钟。
3. 原子迁移 DDR read FIFO 的 `rd_clk` 和完整 HDMI pixel 域；旧 PLL `CLKOUT0` 不得继续驱动任何 pixel 消费者。
4. 只迁移 FIFO 时钟，不改变现有 FIFO reset/flush 语义；该职责继续留给 O2-C2。
5. 将 serializer hard reset 与 video/encoder business reset 分权；`ddr3_init_done` 不得进入 serializer hard-reset 控制器。

`/5` 是奇数分频，不能默认 50% duty。O2-D1-G 必须唯一固定 IOCLKDIV 的 pre/post-buffer 输入取点、PDS clock object 和 waveform。本机 PG2L100H 官方示例对 IOCLKDIV 输出显式使用 `create_generated_clock`；本工程应先检查 PDS 是否唯一推断，只有需要时才增加一个精确声明，禁止重复或宽泛 clock object。

最小审核边界包括：

- 由 IP Compiler 重生成的 `pll_clk.idf` 和 wrapper；禁止手改生成 Verilog。
- 新增项目自有 `rtl/hdmi_top/tmds_clock_reset_ctrl.v`。
- 修改 `rtl/ov7725_hdmi.v`、`rtl/hdmi_top/hdmi_top.v`、`rtl/hdmi_top/dvi_transmitter_top.v` 与 `scripts/build.tcl`。
- 将 `prj/source/ov7725_hdmi.fdc` 纳入 generated-clock 审查；STA 成功后再修改 `scripts/check_build.ps1`。
- `serializer_10_to_1.v`、video、encoder、FIFO 和 DDR wrapper 原则上不为改网名而修改，由网表/gate 证明迁移完成。

### 12.4 编码前任务

1. **O2-D1-R：** 从空 `build/` 重建已回退 RTL，确认原 7 组失败指纹，并判断 `ddrphy_sysclk → pixel_clk` 为 53 还是 54 个 endpoint。该漂移不能在没有等价基线时归因于 serializer reset。
2. **O2-D1-G：** 固定控制器状态、计数、reset 断言/释放边沿、generated-clock waveform、业务 reset 顺序、encoder warm-up、预期网表/STA delta 和完整回退条件。
3. 完成文档与用户审核后才允许进入 O2-D2；本节不是编码授权。

### 12.5 O2-D2 硬验收与停止条件

1. Compile/elaboration 后必须有 17 个手写源、1 个 IOCLKBUF、1 个 `/5` IOCLKDIV、4 个 serializer、8 个 OSERDES 和唯一 pixel generated clock。
2. 旧 `CLKOUT0` 对 pixel 域零消费者，不存在旧、新同频 pixel clock CDC。
3. 八个 endpoint 的 Slow/Fast × Recovery/Removal × `OCLK` 正负边沿/`OCLKDIV`/`SERCLK` 均保留分析覆盖且 slack 非负。
4. 只允许 O2-D1-G 预先列出的 clock 名、source count 和 reset endpoint delta；其余 warning、critical、CDC 或 baseline 漂移为零。
5. QuestaSim 可用后补测异步断言、业务 reset 顺序、encoder warm-up、唯一首个有效 TMDS symbol、超时和 SDF 标注。

以下任一项出现即完整回退，不进行第二相位尝试：控制相位或 generated clock 未被唯一识别；本地复制后 Slow Recovery 仍为负；任一 Removal/八端点/双边沿覆盖不完整；需要 false path、multicycle、clock group、失败 baseline、未审核 LOC 或其他 waiver。当前设计继续保持不可发布状态。
