# DMA 同周期独立候选

仅本地真实 RTL 差分仿真。候选没有进行 PDS 综合、布局布线、远程操作或设备编程，不能报告候选 WNS 或时序通过。build01、build02 和 map01 的源文件及脚本不在本任务写入范围。

## 冻结与可逆性

实际输入是 `../source_diagnostics_route_02/rtl/axi_dma_write_tc04.v`，SHA256 为 `cfcac8a1987e0b443d5521b27ac508ba82cc4e9cec5ea269c8cf3f3af956a6e8`，与 exact09 的 `input_hashes.json` 中 `rtl\\axi_dma_write_tc04.v` 一致。exact09 的 `standard_flow_exact09.pds` 实际登记该文件。

`original/axi_dma_write_tc04.v` 是逐字节原件；`original/axi_dma_write_dma_sc_reference.v` 仅改模块名，作为实际 RTL golden。候选为 `rtl/axi_dma_write_dma_sc_candidate.v`，模块名独立，SHA256 为 `82459c1c26166ade9b5b6732615141100100ce2387ea9fcc68844bc7dbe35ef2`。共享 stream_pipe 也按 exact09 哈希冻结。没有修改任何 PDS 绑定。撤销候选只需不采用此独立目录；不需要还原活动工程。

生成器对原件执行 ASCII 字节段替换，保持其余 GBK 字节及换行。逆向替换两处表达式及模块名后，必须逐字节等于原件。差异见 `evidence/candidate.patch`。

## 两处有限改写

1. watchdog clear 非 waiting 分支删除 `w_progress`：`!burst_trans || data_in_valid || !t_m_axi_wready`。外层 `abort_r` 已清除计数；当 abort_r 为 0，w_progress 成立必有 data_in_valid 成立；abort_r 为 1 时外层已经清除。未知值行为由四态穷举验证。w_progress 信号本身和 timeout 判定仍保留，没有新增寄存器，没有延后任何 clear/progress/timeout 边沿，24-bit 饱和计数逐位 D 路径不改。
2. `abort_done` 从 `trans && (abort_r || abort_req || (b_fire && bresp[1])) && (b_fire || (abort_r && !burst_trans && !awvalid))` 改为 `trans && ((b_fire && (abort_r || abort_req || bresp[1])) || (abort_r && !burst_trans && !awvalid))`。只用逻辑运算的分配律和吸收律。没有 casez、casex、二态强制转换或新增状态。failed 仍保持原式供 success pulse 使用。

四态测试分别穷举 7 个独立标量的 16,384 个组合、8 个独立标量的 65,536 个组合，值域包含 0、1、X、Z，并用 `!==` 比较。watchdog 的 act_burst_len > 0 结果用独立标量抽象，甚至包含实际关系运算不会产生的 Z；这是更强的局部表达式覆盖。局部穷举不是完整模块形式证明。

长度、BURST_LEN 比较、4KB 边界算术及 data_in_available 比较完全保留。没有将 16-byte 对齐假设硬编码到通用 DATA_WIDTH/KEEP_WIDTH 参数。没有取消已广告的 AW；abort dummy W、外部最后 W、真实 B 和退休规则保持原状。

## 实际时序锥

从已存在的 exact09 `final_export/report_timing/v7_sdt_top.rtr` 只读提取，报告 SHA256 为 `44d73013de8830af6635763716cdc594c9b0cf16c9ee5909bab12837a8dccb34`。其中 DMA 同时钟 setup 路径 199 条，均负 slack，WNS -1.790 ns；194 条是 len 到 wd_cnt。清单为 `evidence/exact09_timing_cones.json`，最差五条完整路径为 `evidence/exact09_len_wdcnt_*.txt`。

最差路径：`cam6_axi_dma_write/len[22]` → `N78_mux28_20` → `N81[2]` / burst_len[2] → `N108_1` 4KB 加法 → `N519_1.fsub` / max_burst_len[7] → `N84.lt` / source_burst_ready → `N99_3` / waiting_source → `N188.eq_5` / wd_clear → `N200` / wd_step → wd_cnt[5] D 路径。11 个逻辑级，logic 1.986 ns、route 6.900 ns。burst_len[2]、max_burst_len[7]、wd_clear 的单段 route 分别为 1.128、1.309、1.221 ns；wd_clear 在这条报告路径 fanout 为 18。

RTL 主锥为：`len > BURST_LEN` 限幅与宽 mux → `((addr & 12'hfff) + (burst_len << AXI_BURST_SIZE)) >> 12` 跨界判定 → 边界剩余长度或 burst_len mux → `data_in_available >= max_burst_len` → source_burst_ready → waiting_source → credit-change 与非 waiting clear 的 mux → wd_step / 每位 clear。另有 len 非零检测直接进入 waiting_source 和 AWvalid 条件。

默认 DATA_WIDTH=128 时，len 为 29 位，burst_len/max_burst_len 为 8 位、credit 为 16 位。原边界加法因 32-bit addr 操作数及表达式上下文传播形成较宽算术；直接换成 12/13 位比较、或先将 credit 截成 8 位，需要另外证明进位、截断、参数值及 X 条件合并语义。尤其 BURST_LEN 是无类型参数，burst_len 最终 8-bit 截断及不同 AXI_BURST_SIZE 的移位均是原语义的一部分。因此本交付没有把这些尚未验证的算术平衡写入候选。

此次吸收删除了 clear 中 w_progress 经 t_m_axi_wvalid/act_burst_len 的冗余输入；abort 因式分解缩短表达式层级。这两处均没有切断上述 len 主锥，综合器也可能已经吸收它们，因此不承诺实际资源或 slack 改善。没有在未建立全部宽度、参数、四态语义证明前改写边界加减法。DFI 到同步 RS clear 路径不在本候选修改范围，也没有创建 false path。

## 真实 RTL miter 与验证入口

运行 `python run.py`，ModelSim SE-64 10.6e 的 vlib/vlog/vsim 实际编译两份真实 RTL，共用相同输入。独立 `sim/work` 不影响其他回归库。

复用 timing_correction_02 的端口解析与 80-case 命令刺激，以及 timing_correction_04/tests/dma_edges_body.sv 的真实握手和边界刺激，只改本目录的生成结果，不执行原 runner 的 main。每周期比较全部公开输出（包括 invalid 周期 payload）及 len、addr、trans、burst_trans、act_burst_len、wd_cnt、abort_r、available_q、w_done、burst_len、max_burst_len、source_burst_ready、waiting_source、wd_clear、wd_step、w_progress、failed、abort_done、全部 t_m_axi_w*。

命令刺激涵盖 zero、1/15/16/17、31/32/33、255/256/257、4080/4081/4092/4095/4096/4097、最大长度和随机长度；地址包含页首、页中、距页尾 256/16 bytes、下一页等。WAIT_FOR_DATA=0/1，DATA_WIDTH=64/128/256，BURST_LEN=1/8/16/32/255 的选定组合。随机 AW/W backpressure、B response/error、abort、reset、多周期演进与真实最终 W/B 退休均复用。

边界回归覆盖 WD_LIMIT=0/1/7/0xffffff、24 位 carry 与饱和、credit 增减/flush、timeout 当拍及同时 reset/abort/progress、AW/B 优先级。高位边界通过成对内部状态 deposit 到达，未自然驻留 2^24 周期。额外 priority miter 对 16 个长度 × 64 组 reset/command/AW/abort 同拍组合 × 3 个 DATA_WIDTH，独立检查 len 的 reset > cmd handshake > AW handshake > abort_done 优先级。大长度命令的 400-cycle 原回归为有限窗口，不声称全部长度完整传输结束。

实际计数及各运行记录以 `evidence/results.json` 为准，vendor 日志在 `sim/*.log`。输入保护哈希为 `evidence/protected_sha256.json`，交付件及日志 SHA256 为 `evidence/artifact_sha256.json`。报告、脚本及额外时序提取件的最终哈希由 `finalize.py` 补齐。所有 PASS 指 RTL 差分及指定局部验证，不指 PNR。

验证结果：800 个有限窗口命令用例，162,253 个边界回归周期，67,116 个成对状态向量，15 个自然 timeout/abort 退休场景，3,072 个优先级向量，81,920 个局部四态表达式组合。每次仿真的 AW/W/最后 W/B/Berror/abort/reset/backpressure 实际观测计数分别记录在 vendor 日志的 BUS_COUNTS 和 results.json 的 bus_counts 中；边界仿真计数包含 deposit 后的观察，不将其全部计为自然协议事务。
