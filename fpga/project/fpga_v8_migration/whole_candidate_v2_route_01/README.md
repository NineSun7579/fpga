# v2 独立 PnR 01

状态：单次 fresh Compile / Synthesize / Device Map / Place & Route 全部完成，PDS exit 0，无 E:；约 17 分 45 秒。最终 routed DB 独立慢/快角 STA 完成。**时序未闭合，不可作为 bitgen 发布或上板验收依据。** 没有重新运行 PnR，也没有生成 bitstream。

本工程根目录就是 `-work_dir`，project.pds 启动前逐字节复制自冻结 whole_candidate_v2。694 个 inputs 与 18 个 rtl 文件（17 个组件和 1 个顶层）全部为本工程自己的本地副本；每条登记路径解析后均在此目录，哈希与冻结源相同。采用 fresh flow，不复用已有综合数据库；顶层 `fpga_v8_cooperative_top_v2`，器件 `PG2L100H-6FBG484`，131.25 MHz 与六个源 FDC 保持原字节。

`preparation.json`、`registered_sources_before.json` 和 `inputs_before.json` 保存输入证据。`protected_before.json` 保护 4175 个文件，包括既有 v2 完整树和 completed compile_01；外部保护继承上一轮显式路径清单，不包含父会话可变根 README 或 viewer 的并行工作。运行器在 PDS 退出后自动比对保护及本地输入，保留 project.pds 自动格式化前后副本，并重新核验源绑定。

全局 tasklist 在准备和启动前均检查 pds.exe / pds_shell.exe；出现阻塞会直接报告，绝不 kill。没有 SSH、上板、IP 生成或 bitstream 生成授权。

最终 core 时序（ns；不是布线器 after-hold-fix 中间摘要）：

| 检查 | 慢角 WNS | 快角 WNS | 慢/快失败 endpoints |
| --- | ---: | ---: | ---: |
| Setup | -0.429 | +2.608 | 39 / 0 |
| Hold | -0.028 | -0.015 | 1 / 1 |
| Recovery | +1.395 | +3.594 | 0 / 0 |
| Removal | +0.352 | +0.248 | 0 / 0 |
| Min pulse | +2.464 | +3.011 | 0 / 0 |

core 慢角 setup TNS −8.067 ns。所有域合计：慢角 setup 39、hold 336、removal 11；快角 hold 225，其他类型无失败。全部 611 条负 slack 路径与汇总失败数一致，完整起终点和路径细节在 `evidence/all_reported_failing_paths.json`。另保存 470 条无评分 IO 路径；CHECK 为 no_clock=0、loops=0、latch_loops=0、latchs=0；no_input_delay=62、no_output_delay=71。clk_150m 是 1 个无 loads 的虚拟时钟，工具保留相应警告。min-pulse 最小域余量是两个 phy_dq_clk 的 +0.011 ns；全时钟慢/快角表和 clock interaction 在 `evidence/final_sta_summary.json` / `final_sta_tables.json`。

实际 PRR 资源：LUT 29856、FF 30779、DRM 71.5、APM 0、GPIO/DDR IO 112。综合资源 LUT 31251、FF 31535、DRM 72.5、Tool I/O 114 是另一阶段口径，不把 114 当成 114 个 GPIO pad。112 个 PRR pads 的全部电气字段与冻结基线相同；285 行 generic IO pinout 的 package pin、IO site、bank、功能、设计端口全部相同。14 个独立 HSST 位的顶层连接及 PCIe/SFP 五个 hard-site 全部相同。free_clk 保留 V4/LVCMOS15/UNUSED 属性，STA 确认为 25 MHz 根时钟，171 clock loads。没有新增黑盒警告。

四套 motion histories 各 19200×8=153600 bits，总计 614400 bits；实际保留 32 个 DRM36K 实例，全部逐个确认 READ_BEFORE_WRITE、1-bit slice、15-bit 地址、写数据/history_q 和物理 PLACE 记录。32 个 cell 原始 Verilog、2444 个 RAM/寄存器连接块、693 个 motion register bank 实例与消费者证据保存在 `evidence/`。这些是资源和连接证据，不是 whole functional equivalence。

原综合 core hold −0.004 ns / TNS −0.040 ns / 10 failing endpoints 的普通报告只列出 3 个详细路径。定向 routed STA 使用 exact CONNECT 绑定的 o_rid[0:3]/o_rlast 五个 packed-memory 数据引脚，慢/快角共 10 条路径全部为正，最小 +0.827/+0.508 ns；**这 10 条 routed 路径不是原综合 10 个 endpoint 的已证双射**。当前 core hold 失败路径是 `ov5640_top/u_cam_fir3/out_pixel[15] → ov5640_top/u_motion_tap/events_7/ram32x2d/DIH`，与原 DDR prefetch FIFO 代表路径不同。额外原综合定向报告被 PDS 以 Flow-0013 拒绝（report_timing 要求 PNR phase）；失败日志、脚本、结果全部保留，没有猜测参数重试。

PDS 自动格式化新增了本地输出 `_file` 登记，最初外层源绑定 guard 将其误当冻结源，故外层 exit 1。原始 `pnr_result.json` 如实保留该结果；修正后的补充审查 `source_binding_postformat_review.json` 证实 402 条冻结登记路径全部保留、字节一致，新增路径仅为本目录生成产物。所有最终源和保护 guard 均通过：712 个本地输入及 4175 个既有文件不变，包括 v2 完整树与 completed compile_01。4175 是实际保护 union 数量，不冒充历史 3344。

源 top SHA256：`a857aecf13e57edb41225e230399273a7a3bebf7e243914e749cb62e15ce1ae1`；最终 route DB SHA256：`8a7f29428b50e511f8cb41771faaf399dffc8feaa5160d3e9d9adde775246797`。六个源 FDC 哈希见 `parent_handoff.json`；RTL/约束没有修改、没有新增 false path 或放宽时钟。

完整交接：`parent_handoff.json`。既有组件 mapped endpoint 654 operations / 0 oracle differences 只证明该组件测试范围，不能证明 whole-map 等价。独立 reset epoch、physical input identity、RX/output 动态分配、F2H posted-write retirement 和 host ordering 等既有 blocker 仍在；没有 SSH、IP 生成、bitgen/load、硬件 paired 比较或 FPGA FPS 验收。

`baseline_reference.json` 为只读提取的冻结基线证据。独立导出在新 `final_export`、`focused_route_hold`、`focused_synthesis_hold` 子工程，运行前逐次全局 tasklist 检查；没有 kill GUI。使用本机 PDS 文档和 `timing_help.log` 确认的参数。最终 routed DB 和综合 DB 的导出前后哈希不变，所有日志保留。
