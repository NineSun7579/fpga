# DDR3 有限自检契约

状态：D2 设计决策；待 PG2L100H IP 版本核验、契约复核和 D3 实现审核
适用日期：2026-08-30
目标器件：`Logos2 / PG2L100H / FBG484 / -6`
适用 DDR3 配置：计划保持 x16、128-bit 用户数据通路；必须由当前 PG2L100H `ddr3.idf` 重新确认

## 1. 目标与边界

本契约定义一个有限、确定、可由 CI 判定的 DDR3 bring-up 自检。它只回答以下问题：

1. DDR Controller/PHY 是否完成初始化；
2. 一组确定地址能否完成写入、读回和逐位比较；
3. 数据错误、协议停滞和超时是否能形成稳定的失败状态；
4. 行为级及门级 testbench 是否能只通过公开接口判定 PASS/FAIL。

本契约不替代：

- DDR3 板级颗粒、byte lane、VREF、ODT、终端和 PCB 时延核对；
- 长时间随机压力测试；
- PDS STA、CDC/RDC、I/O timing 或板级测试；
- 厂商 DDR Controller/PHY 的内部训练签核。

## 2. 现有厂商示例不能直接作为有限自检

当前 `test_ddr` 和 `axi_bist_top_v1_0` 保留为厂商 bring-up 证据，不作为后续项目自有测试接口。

已确认的问题：

- `test_main_ctrl_v1_0` 的 `E_END` 会继续选择写或读状态，BIST 没有自然终点；见 `example_design/rtl/test_main_ctrl_v1_0.v:181`。
- `bist_stop` 只撤销读写使能，不产生完成状态；见同文件 `:155` 和 `:168`。
- `bist_run_led` 是完成脉冲计数后的翻转指示；见同文件 `:195`。
- `test_ddr` 将 `err_flag` 与 `bist_run_led` 相或，LED 不能区分错误和运行状态；见 `example_design/rtl/test_ddr.v:84`。
- 旧 TB 仍连接五个当前顶层不存在的端口，并在初始化完成后固定延时 `$finish`；见 `example_design/bench/ddr3_tb/ddr3_test_top_tb.v:64` 和 `:198`。
- 旧 TB 无条件调用 FSDB system task，并依赖 DDR PHY 私有层级；见同文件 `:214` 和 `:251`。

因此：

- 不修改或批量格式化 `ip_core/ddr3/**` 下的厂商生成 IP、示例 RTL 和示例 TB；
- 不用 LED、固定等待时间、层级 `force` 或内部状态名作为签核接口；
- 后续新增项目自有顶层和测试引擎，直接实例化活动 DDR3 IP。

## 3. 推荐结构

后续 D3/D4 使用以下项目自有文件：

```text
ddr3_test/ddr3_test/
├─ rtl/
│  ├─ ddr3_bringup_top.sv
│  └─ ddr3_finite_bist.sv
├─ tb/
│  ├─ tb_ddr3_finite_bist.sv
│  └─ tb_ddr3_bringup.sv
└─ sim/
   ├─ rtl.f
   └─ tb.f
```

职责边界：

- `ddr3_bringup_top.sv`：实例化活动 `ddr3.idf` 所生成的 IP，处理复位、初始化完成和自动启动；不实现数据比较算法。
- `ddr3_finite_bist.sv`：产生有限 AXI 写读事务、比较数据、统计完成数和错误，并输出稳定状态；不包含 DDR PHY、UART 或 LED 签核逻辑。
- `tb_ddr3_finite_bist.sv`：使用最小 AXI 响应模型验证正常、数据错误和协议超时分支。
- `tb_ddr3_bringup.sv`：连接厂商 DDR3 memory model，验证项目顶层集成和初始化后的完整有限自检。

## 4. 规范性接口

### 4.1 测试引擎接口

`ddr3_finite_bist` 必须提供：

```systemverilog
input  logic         core_clk;
input  logic         core_rst_n;
input  logic         ddr_init_done;
input  logic         test_start;

output logic         test_busy;
output logic         test_done;
output logic         test_failed;
output logic [3:0]   failure_code;
output logic [31:0]  error_count;
output logic [31:0]  completed_pairs;
output logic [27:0]  first_error_addr;
output logic [127:0] first_expected_data;
output logic [127:0] first_actual_data;
```

上述片段是 D3 的规范性接口草案，必须由实际 elaboration 验证，不能仅凭本文声称正确。

### 4.2 启动与保持语义

- `test_start` 只在 `test_busy == 0` 且 DDR 初始化已完成时接受。
- 项目顶层在 `ddr_init_done` 首次有效后自动产生一个 `core_clk` 周期的 `test_start`。
- 接受启动后的下一个周期，`test_busy` 必须为 1；运行期间忽略新的启动请求。
- `test_done`、`test_failed`、`failure_code`、`error_count` 和首错信息在下一次合法启动或复位前保持稳定。
- `test_done` 是稳定电平，不是单周期脉冲。
- `test_pass` 不必保存为独立状态；顶层可定义为：

```systemverilog
assign test_pass = test_done && !test_failed && (error_count == 32'd0);
```

- LED 只能映射公开状态，例如 `busy/done/pass/failed`，不得作为原始签核接口。

## 5. 有限事务定义

### 5.1 固定参数

首版 smoke test 固定为：

| 参数 | 值 | 约束 |
|---|---:|---|
| `TEST_PAIR_COUNT` | 16 | 合法范围 `1..256` |
| `TEST_ADDR_BASE` | `28'h0000000` | 当前 DDR 用户地址空间起点 |
| `TEST_ADDR_STRIDE` | 8 | DDR 控制器地址单位，不宣称为字节 |
| `TEST_ADDR_LAST` | `28'h0000078` | `BASE + (PAIR_COUNT-1)*STRIDE` |
| `AXI_LEN` | 0 | 每次写/读均为单 beat |
| `AXI_ID` | 0 | 首版不测试乱序或多 ID |
| `AXI_AP` | 0 | 使用普通访问属性 |
| `PAIR_TIMEOUT_CYCLES` | 4096 | 每个写读比较对的最大周期数 |
| `RUN_TIMEOUT_CYCLES` | 131072 | 接受启动到终态的全局最大周期数 |

`TEST_ADDR_STRIDE=8` 与当前厂商示例一致：16-beat 初始化事务后地址增加 128，读数据每 beat 的期望地址增加 8；证据见 `test_wr_ctrl_v1_0.v:136` 和 `test_rd_ctrl_v1_0.v:247`。如果重新生成 IP 后接口地址单位变化，D3 必须停止并重新审核本契约。

关键参数必须在 elaboration 或 assertion 中检查：

- `TEST_PAIR_COUNT > 0`；
- `TEST_PAIR_COUNT <= 256`；
- `TEST_ADDR_STRIDE > 0`；
- 最后一个地址不越过当前 `CTRL_ADDR_WIDTH`；
- 用户数据宽度必须为当前契约的 128 bit。

### 5.2 一项事务的完成定义

一项 pair 是同一地址上的完整写入、完整读取和数据比较：

1. 写地址握手；
2. 单 beat 写数据被控制器接受；
3. 所有写 outstanding 清零；
4. 同一地址的读地址握手；
5. 单 beat 读数据有效；
6. 完成逐位比较并更新错误状态。

只发生 AW/AR 握手、只接收数据，或者只增加请求计数，都不能算作完成一项 pair。

`completed_pairs` 只在第 6 步完成后的下一个 `core_clk` 周期增加一次。最终 pair 完成比较且 outstanding 为 0 后，下一个周期置位 `test_done`。

## 6. 数据模式

第 `pair_index` 项使用确定的 32-bit `seed`：

```text
seed       = 32'h1F12_3BB5 XOR zero_extend(pair_index)
seed_swap  = {seed[15:0], seed[31:16]}
write_data = {seed, NOT seed, seed_swap, NOT seed_swap}
```

要求：

- 读比较必须重新计算期望值，不能从写数据缓存直接回放；
- 全部 16 个 byte strobe 有效；
- 比较范围为完整 128 bit，不屏蔽错误位；
- 首版不加入随机种子、可变 burst、多 ID、乱序或 error injection 逻辑。

该模式用于确定性 smoke test，不声称覆盖全部 DDR 故障模型。长时间随机压力测试保留为后续可选增强。

## 7. FSM 与终态

推荐 FSM：

```text
IDLE
  → WRITE_ADDR
  → WRITE_DATA
  → WAIT_WRITE_IDLE
  → READ_ADDR
  → READ_DATA
  → CHECK
  → NEXT_PAIR ──┐
  ├─────────────┘
  ├→ PASS
  └→ FAIL
```

FSM 契约：

- 类型：Moore 为主；握手有效信号可以是由当前状态和 ready 组合形成的协议输出。
- 编码：`auto`，接口不依赖固定编码。
- 复位状态：`IDLE`。
- 非法状态：RTL 回到 `FAIL` 并置 `failure_code = INTERNAL_STATE`；不得只凭 `default` 注释宣称安全恢复已验证。
- `test_done`、`test_failed` 是寄存输出，在进入 `PASS/FAIL` 后可见。
- 数据不匹配不提前停止；继续完成剩余 pair，以得到有限错误计数。
- 协议停滞、pair timeout 或 run timeout 立即进入 `FAIL`。

## 8. 错误统计与失败码

`error_count` 的单位为“存在任意未屏蔽位差的读 beat 数”，不是错误 bit 数，也不是失败事务数。

- 每个单 beat pair 最多增加 1；
- 32-bit 饱和，达到 `32'hFFFF_FFFF` 后不回卷；
- 首次不匹配时锁存地址、期望值和实际值，后续错误不得覆盖首错信息；
- 数据不匹配置 `test_failed`，但继续执行；
- 协议/超时失败不伪增 `error_count`，通过 `failure_code` 区分。

失败码固定为：

| 值 | 名称 | 语义 |
|---:|---|---|
| `0` | `NONE` | 尚无失败 |
| `1` | `DATA_MISMATCH` | 至少一个读 beat 数据不匹配 |
| `2` | `WRITE_TIMEOUT` | 写地址或写数据阶段超时 |
| `3` | `READ_TIMEOUT` | 读地址或读数据阶段超时 |
| `4` | `RUN_TIMEOUT` | 全局运行周期上限到达 |
| `5` | `PROTOCOL_ERROR` | outstanding、响应次序或计数不变量被破坏 |
| `6` | `INTERNAL_STATE` | FSM 进入未定义状态 |

若先发生数据不匹配，随后发生更高优先级的协议/超时错误，`failure_code` 必须更新为后者；首错数据仍保持第一次数据不匹配信息。

## 9. Testbench 契约

### 9.1 集成正向测试

`tb_ddr3_bringup.sv` 必须：

1. 只连接项目顶层公开端口和厂商 memory model，不读取 DUT 私有训练层级；
2. 等待公开 `ddr_init_done`，训练等待上限为 `20 ms`；
3. 等待 `test_done`，自检运行上限为 `5 ms`；
4. 检查 `completed_pairs == 16`、`error_count == 0`、`test_failed == 0`；
5. 成功时只输出一次 `TEST PASS` 后 `$finish`；
6. 训练超时、自检超时或状态不符时调用 `$fatal`。

### 9.2 引擎负向测试

`tb_ddr3_finite_bist.sv` 使用项目自有最小 AXI 响应模型，不修改生产 RTL：

- 正常响应：必须完成 16 个 pair 并通过；
- 单个读 beat 数据翻转：必须 `test_failed=1`、`failure_code=DATA_MISMATCH`、`error_count=1`，且首错信息正确；
- 阻断写响应：必须以 `WRITE_TIMEOUT` 结束；
- 阻断读响应：必须以 `READ_TIMEOUT` 结束；
- 每个失败场景必须 `$fatal` 或返回非零；测试期望某种失败状态时，只有状态与期望一致才算该负向用例通过。

### 9.3 可移植性

- 新 filelist、DO 和 Tcl 使用相对路径或由 PowerShell 注入的外部路径；不得写盘符绝对路径。
- 默认使用 Questa/ModelSim WLF；FSDB/Verdi 只能通过显式宏和已配置 PLI 作为可选功能。
- 仿真脚本必须有 `onerror {quit -code 1 -force}`，成功使用 `quit -code 0 -force`。
- 厂商 memory model 内部的 `$finish` 不能替代项目 testbench 的 `$fatal` 和结果检查。

## 10. VSCS 注释与验证要求

新增项目自有 RTL/TB 必须遵守根目录 `VERILOG_SYSTEMVERILOG_COMMENTING_STANDARD.md`：

- 文件和模块说明职责、边界及外部依赖，不维护作者、日期或 Revision History；对应 `VSCS-FILE-001/002`、`VSCS-MOD-001`。
- 参数说明单位、合法范围和非法值行为，并以 elaboration/assertion 执行；对应 `VSCS-MOD-002/003`。
- `test_start/done/failed`、超时、错误计数和首错信息的采样周期、保持规则及错误语义必须写入接口契约；对应 `VSCS-MOD-004`。
- FSM 注释说明类型、编码、复位态、非法状态策略和输出可见周期；对应 `VSCS-FSM-001/007`。
- `.sv` 使用 `always_ff/always_comb`，时序过程使用非阻塞赋值；对应 `VSCS-PROC-001/002`。
- 注释不得替代端口 elaboration、位宽检查、assertion、仿真或 PDS 报告；对应 `VSCS-VER-001/003`。

D3 至少加入以下机器检查：

- 参数合法性；
- `completed_pairs <= TEST_PAIR_COUNT`；
- `test_done` 时 outstanding 为 0；
- `test_done` 后状态和统计保持；
- 同一周期不能同时接受两个新的地址事务；
- 运行 watchdog 不得回卷。

## 11. 后续批次

### D3-A：项目顶层与接口骨架

- 新增 `ddr3_bringup_top.sv` 和 `ddr3_finite_bist.sv` 的接口/FSM 骨架；
- 直接实例化活动 DDR3 IP；
- 更新 PDS 输入清单和顶层；
- 只验证 compile/elaboration，不加入随机、UART 或板级 LED 决策。

### D3-B：有限事务与 PDS 回归

- 实现 16 个单 beat 写读比较 pair；
- 实现 timeout、错误统计和首错信息；
- 从空 `build/` 完成 PDS 全流程并更新严格 gate；
- 新实现不得引入端口、位宽、latch、多驱动或未分类 critical warning。

### D4：自检 testbench

- 新建引擎单元 TB 和 DDR3 集成 TB；
- 新建可移植 filelist/DO；
- 执行正向、数据错误、写超时和读超时用例；
- QuestaSim 不可用时可以完成文件评审，但不得声称仿真通过。

## 12. D2 完成定义

D2 只在以下事实成立时完成：

- 本契约经审核，后续实现无需猜测事务数、地址、数据、超时、done 或 error 语义；
- 厂商示例 RTL/TB 保持不变；
- TODO、README、实施记录和知识图同步；
- D2 提交中没有 RTL、TB、IDF、FDC、RCF 或 `build/` 生成物。

## 13. D3-0 core/wrapper 评审结论

2026-08-30 依据活动 IP、实例模板和示例 wrapper 完成只读复核。D3-A 的接口事实固定如下：

- `ip_core/ddr3/ddr3.v` 的 `ddr3` 是公开 core；`core_clk`、`ddr_init_done`、PLL/PHY 状态和 128-bit 用户数据通路属于可用接口。`ip_core/ddr3/example_design/rtl/test_ddr.v` 是物理 board wrapper，保留 DDR3、时钟、复位和 UART 物理端口。
- wrapper 中的 core 实例名固定为 `I_ips_ddr_top`。后续 FDC/RCF、网表层级和 gate 检查均以此名称为边界；不得为改名或简化层级而修改该实例名。
- 用户接口为 Pango 定制 AXI-like 端口，不是完整 AXI4：写地址握手为 `axi_awvalid & axi_awready`，写数据接受由 core 输出 `axi_wready` 表示，并返回 `axi_wusero_id/axi_wusero_last`；读地址握手为 `axi_arvalid & axi_arready`，读数据仅返回 `axi_rvalid/axi_rlast`，没有 `axi_rready`。
- 当前示例用 `axi_wready` 与 `axi_rvalid` 分别累计写/读完成数；这只是活动 IP 的已观察语义，D3-A 必须在项目自有 BIST 中显式建模并加入 timeout/assertion，不得套用标准 AXI4 的 B/R 通道假设。

D3-A 允许新增项目自有 top/BIST 并切换 PDS 顶层和输入清单，首轮仅做 compile/elaboration。若 IP 重生成后端口、地址单位、握手语义或 `I_ips_ddr_top` 层级发生变化，立即停止并重新审核；厂商 `ip_core/ddr3/**`、FDC、RCF、物理端口和生成 Verilog 继续禁止修改。
