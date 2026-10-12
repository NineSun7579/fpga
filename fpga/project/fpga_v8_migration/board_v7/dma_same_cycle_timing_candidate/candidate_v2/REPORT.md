# DMA len 主锥候选 v2

本目录独立于上版，v1 原档及其日志不写入。目标是直接缩小 `len → burst_len → page boundary → max_burst_len → source_burst_ready → waiting_source → wd_clear → wd_cnt` 中的 page boundary 算术。继承 v1 的两处已验证布尔改写，新增改动没有寄存器、时钟或 latency。没有运行 PDS、远程操作或设备编程；候选 slack 尚未测量，不代表 WNS 通过。

## 输入和分支边界

Golden 是实际 exact09 `axi_dma_write_tc04.v`，SHA256 `cfcac8a1987e0b443d5521b27ac508ba82cc4e9cec5ea269c8cf3f3af956a6e8`。v1 输入为 `../rtl/axi_dma_write_dma_sc_candidate.v`，SHA256 `82459c1c26166ade9b5b6732615141100100ce2387ea9fcc68844bc7dbe35ef2`。两者均实际复制并冻结；reference 仅改独立模块名，不生成行为镜像。v2 候选模块名为 `axi_dma_write_dma_sc_v2`。

实际 v2 候选 SHA256：`400e565fd8df20bc070abb323b44cdebf3999bd627050e3c2991ddfc15fa90c8`。

静态 specialization 必须同时满足 DATA_WIDTH=128、KEEP_WIDTH=16、AXI_BURST_SIZE=4、`$bits(BURST_LEN)=32`，并且 BURST_LEN 是有符号的 0..255。对这个已限制的值域，`!(BURST_LEN < -1)` 排除无符号参数：有符号非负值与 -1 比较为 false，无符号值与转换后的 32'hffffffff 比较为 true。没有在 BURST_LEN 本身强制 signed cast。其他宽度、负值、256 或更大值、无符号/窄/宽参数全部回退；generate 条件未知也按原 Verilog generate-if 语义走 else。

Generic 分支逐字保留原 `assign max_burst_len` 行。v2 用字节替换生成，逆向替换新增 generate 区及模块名必须逐字节还原 v1。GBK 注释与未编辑字节保持不变。两份 diff 分别为 `evidence/from_exact09.patch` 与 `evidence/from_v1.patch`。没有修改 PDS 登记或 queued build02 的源码/脚本。

## 宽度、符号和四态证明

原表达式 `(addr & 12'hfff)` 为 32-bit unsigned：addr 是 32-bit unsigned reg，位运算把 12-bit 常量零扩展。原跨界加法的 32-bit 上下文同样传播到 `burst_len << AXI_BURST_SIZE`；右移及与 unsized zero 的比较仍在 32-bit unsigned 值域。原真分支中 `13'h1000` 由于 32-bit addr 操作数而零扩展，减法与右移为 32-bit unsigned；conditional 两分支在较宽上下文合并，最后赋值到 8-bit max_burst_len。最终只保留减法结果的 bits[11:4]。

在法定分支中：页偏移 p=addr[11:0]，0≤p≤4095；独立 burst_len b 为 8-bit unsigned，0≤b≤255。`p + 16*b` 最大 4095+4080=8175，13-bit 无溢出。定义明确的 13-bit unsigned wire：page_offset=`{1'b0,addr[11:0]}`、burst_bytes=`{1'b0,burst_len,4'b0000}`、page_sum=二者相加、page_remaining=`13'h1000-page_offset`。remaining 范围为 1..4096，13-bit 无下溢或溢出。

跨界测试保持 `((page_sum >> 12) != 13'd0)`，没有改为 min 或采用不同严格性的不等号。已知输入时它与原式都判断 `p+16*b >=4096`，包括刚好结束在页边界。真分支取 page_remaining[11:4]，恰为原 32-bit 差值右移后赋到 8-bit 的低 8 位；假分支仍是 burst_len。offset=0 时 remaining=4096，低 8 位确实是 0，但 b≤255 导致 sum≤4080，原式与新式均不选真分支；这不是独立的无保护 min 函数。非对齐 offset 1..4095 全部纳入证明，未增加 16-byte alignment 假设。

四态方面：原 mask 对 addr[31:12] 的 X/Z 总是得到 0；新式只取低 12 位，结果相同。如果低页偏移或 burst_len 有 X/Z，Verilog + 对应宽度的整个结果为 X；原 32-bit 和新 13-bit 结果右移后与 0 比较都为 X。剩余减法若页偏移含未知，两者保留的 8 位均为 X；如果页偏移已知，则低 8 位逐位相同。仍使用 continuous assign 的 `?:`，未知条件逐位合并真/假结果，不使用 procedural if、casez/casex 或二态转换。特别是已知 offset、部分未知 burst 时，known matching bits 会保留，不能简单把未知结果替换为全 X。

此数学论证加上 ModelSim 实际 RTL 验证构成所述分支的证明；不声称任意完整模块状态或所有四态组合经过形式等价工具。

## 实际 RTL 验证

`python run.py` 调用本机 ModelSim SE-64 10.6e，编译 exact09 actual reference、v2 actual candidate 及实际 stream_pipe。页边界测试在两个真实 DMA 实例上保持时钟停止，成对驱动 addr，并 force 实际 burst_len wire 为独立 8-bit 变量；直接比较实际 max_burst_len/source_burst_ready/waiting_source/wd_clear/wd_step。没有重写边界函数作为 golden。

每个向量另外断言 actual addr 与 burst_len 确实跟随输入 force/deposit，防止刺激未生效导致空比较；已知默认宽度输入还用独立整数范围公式检查结果，作为实际 RTL golden 之外的辅助 oracle。含 mask 高位 X/Z 而低页偏移已知的输入也执行此辅助检查。

默认分支穷举全部 4096 个 offset × 256 个 burst_len =1,048,576 组合。每个 offset（包括不对齐值）都检查。12 组参数实例还验证 specialized/fallback elaboration：有符号 8/0/1/255；-1、256、32'd8、8'd8、64'd8；DATA_WIDTH64/256；128-bit 数据与 KEEP_WIDTH8 的混合参数。

Credit 比较仍保留原 16-bit `data_in_available >= max_burst_len`，绝不截断 credit。已知阈值 0..255 时，把 credit[15:8] 分为 0 与非零两类：高位为 0 时逐个检查全部 low byte；高位非零时 credit≥256，比较对全部 8-bit 阈值都为 true。实际 RTL 为每个阈值检查 high=0/1/255 与全部 low=0..255，即 196,608 组合；这按数学等价类覆盖全部 credit 0..65535，不宣称逐个运行全部 16,777,216 credit/threshold 对。阈值、credit 或 valid 为 X/Z 的关系运算与 ready/clear 下游也定向及随机检查。

每组参数有逐位 addr（含被 mask 的高位）X/Z、逐位 burst X/Z、credit X/Z、valid 0/1/X/Z，及 4,096 个确定种子的四态随机向量。首个反例会打印 COUNTEREXAMPLE，写入 vendor 日志并立即终止，不通过后续接受步骤。

完整 cycle miter 复用 v1 已运行的实际 TB 字节，仅改实例模块名，在独立 sim/work 编译：800 个命令用例、WAIT0/1、64/128/256-bit 数据和选定 burst 参数；timeout=0/1/7/0xffffff 的 162,253-cycle 边界回归；67,116 个成对状态向量；15 个自然 abort/timeout 退休场景；3,072 个长度 update 优先级向量。所有公开输出（含 invalid payload）以及 wd_cnt/len/addr/trans/abort/available/实际突发/内部 W/clear/progress 等关键状态逐周期比较。AW 不可取消、最终外部 W 后真实 B 退休、zero-byte、B error、abort/reset/backpressure 的原规则均保留。

高 timeout 的 carry/saturation 边界使用成对内部 deposit，不是自然驻留 2^24 周期；大命令的原 400-cycle 用例是有限窗口。四态函数验证在冻结时钟条件下完成；完整周期随机协议回归为原二态刺激，不称为全模块四态穷举。

## 实际计数与交付

以 `evidence/results.json` 的实际 PASS 和计数为准。每次运行 vendor 日志在 `sim/*.log`，BUS_COUNTS 保留 AW/W/最后 W/B/Berror/abort/reset/backpressure 实际观测计数。`evidence/protected_sha256.json` 保护整个 v1 原档以及 build01/build02/map01 源码脚本；`evidence/artifact_sha256.json` 记录 v2 RTL、miter、证明文件、日志、报告和脚本哈希。执行 `python finalize.py` 完成交付审计。

本次实际 ModelSim 全部 PASS：默认域 1,048,576 个穷举边界向量；其他 11 组参数各 2,048 个已知随机向量；12 组各 4,452 个 X/Z 定向及随机向量（共 53,424）；196,608 个 credit 类向量。完整 DMA 800-case / 162,253-cycle / 67,116-vector / 15-natural-scenario / 3,072-priority-vector 回归和 v1 的 81,920 局部四态组合再次全部 PASS。1,191 个受保护文件哈希一致，包含整个 v1 原档及活动 build 的源码脚本。Vendor 日志无 Error/Fatal；vsim 报现有 -novopt 性能提示，不影响比较结果。

物理可评估变化是把原主锥中的 32-bit 页加法/减法和跨界判定限定为显式 13-bit wire、1-bit 越界判定及 8-bit slice；len 限幅、16-bit credit compare、waiting_source/clear 的当拍依赖仍存在。综合器可能已做部分宽度裁剪，实际映射、路由与 slack 必须未来独立测量。本目录不将 RTL PASS 推断为 PNR PASS。
