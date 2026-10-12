# 诊断 bundled-data CDC 约束独立评审

## 结论与边界

**现有 FDC 原样保留并只追加 `set_max_delay`：无法据此签核。** 四个 PCLK 的单组 asynchronous 声明和 ddrphy_sysclk 的单组声明都覆盖 mailbox→host_bank。调整加载顺序、再声明一个包含这两个时钟的组、添加路径报告分组，都没有本地手册支持的“撤销已有异步关系”语义。`set_max_skew` 可以穿透该豁免，但只限制数据位之间的延迟差；所有位一起延迟 30 ns 而 skew 为 0，仍违反 15.238 ns 的绝对界限。

**从已公开命令语义看，可以解决，不是已经证明的工具硬阻挡：** 在后续独立约束候选中替换受影响的五条单组声明，保留其他时钟关系，把四个 PCLK→AXI 方向的旧 CDC 豁免精确迁移到 mailbox 数据路径以外，再对真实 mailbox→host_bank 路径施加 `set_max_delay -datapath_only 15.238`。这要求真实综合对象、完整路径集合及 STA A/B 证据；当前均未解析、未执行、未签核。

另发现本机二进制中的 **`set_clock_groups -allow_paths` 线索**，帮助文字为 `Enable the timing analysis between specified asynchronous clock groups`。PDF 未记录此选项，不能凭字符串称为已验证支持；后续可探测，它可能保留异步标识同时开放分析，但仍需精确旧路径例外，不能直接对整个钟域开放分析后宣称等价。

本次只读 STATUS、PHYSICAL_REVIEW、六个 FDC、本地 PDF/文本及工具可执行文件的 bytes。没有启动任何 PDS/TA、没有编译/综合/PNR/remote，没有修改工程、源、约束或运行日志。唯一写入为本文件。真实综合 cells/pins 必须等主会话通知后才解析。本文件的 Tcl 是后续验证方案，未运行。

“不放宽旧约束”按旧路径实际生效语义保持解释：旧同步路径的时钟、IO 合同、setup/hold/recovery/removal/min-pulse-width 不削弱；旧 CDC 被豁免的路径仍按原语义豁免；新数据路径增加绝对上界。若要求原六份 FDC 连生效的五条全局 async 语句都不能替换，则公开命令路线受阻，只有经实测确认的例外选项才可能解锁，当前不能继续物理签核。

## 本地依据

输入位置均相对于 `project/fpga_v8_migration/board_v7/`：

- `source_diagnostics_build_01/STATUS.md:18–20`：AXI 为 131.25 MHz，要求 ≤15.238 ns；综合导出在成功且 PDS 单实例空闲后执行；未关门槛不进入 PNR。
- `source_diagnostics_top_candidate/PHYSICAL_REVIEW.md:13–29`：mailbox/host_bank 每路 512 位；request 三级同步后另拍复制；request/ack/overrun 首级、reset 链、negedge 半周期、AXI 普通状态逻辑分别审查。
- `source_diagnostics_build_01/inputs/source/constraints/clock.fdc:62–65,77`：四个 PCLK 和 ddrphy_sysclk 各有一个只含自身的异步组。:28 的 40 ns ×16/84 = 7.619047619 ns；两个 AXI 周期为 15.238095238 ns，因此 15.238 ns 是向下取整的更严格上界。
- 其余五份 FDC 以 bytes 搜索例外命令；`cdc.fdc` 中出现的 false_path/max_delay 都是注释。没有把注释算作生效约束。

本地官方文档根目录：`C:/pango/PDS_2022.2-SP6.4/doc/`。文本副本在 build_01 下是 UTF-8（实际 bytes 前缀确认），不能强行按 GBK 解码；PDF 提取后以 `.encode('gbk', errors='replace')` bytes 搜索 ASCII 命令和 GBK 中文关键字，核对完整页内容，未写额外提取文件。

| 文档与印刷页（PDF页=印刷页+1） | 已确认规则 |
| --- | --- |
| Pango Design Suite User Guide §6.2.5，182–186 | 多个 `-group` 只豁免不同组之间；单个 `-group` 豁免该组和其余所有时钟，包括相关派生时钟关系；同组可分析不表示能取消其他命令的豁免。Example 2 明确两组声明“且只表示”指定两钟异步。 |
| 同手册 §6.4.1，198 | 明确 `set_max_skew` 优先于 `set_false_path`、`set_clock_groups`，且与 max/min delay、multicycle 不冲突。 |
| 同手册 §6.5.1，200–202；UCE Guide §2.2.4.1，83 | `set_max_delay` 支持 `-datapath_only`；UCE 明确包含 launch CLK→Q、组合延迟、capture setup，不计 clock skew/jitter。 |
| 同手册 §6.5.4，207–209 | `set_false_path` 支持 `-setup`/`-hold`、from/to/through；不能把整条新数据路径同时 setup/hold false-path。 |
| 同手册 §6.7.1，210–211 | `report_timing -from/-to/-through -delay_type min|max|min_max -nworst -max_path`。注意是 `-max_path`，不是其他厂商常见拼法。 |
| Timing Analyzer Guide v1.4，15 | `Report Exception` 展示 max/min delay、multicycle、false_path 独立报告；`Limit Paths by Clock Group` 是报告筛选。非标准 endpoint 的 min/max delay path 可用 `**default**` 筛选。 |

优先级证据的限度：手册明确写出 skew 对 async/false_path 的优先级，没有完整 max_delay 与 async/false_path 的优先级表。全局 async 的“不会分析”语义意味着不能依靠追加 max_delay 证明恢复分析；“追加一定能覆盖”没有文档依据。是否静默忽略、以哪种分类报告，需后续真实 DB A/B 核实。**不将缺少完整优先级表伪装成实测结果。**

手册未找到 `path_group`、`group_path`、`reset_path`、`remove_clock_groups` 或组内按 path 排除选项。三个常用分析二进制中同样未找到这些命令字符串；这不是数学意义上的不存在证明，但不足以提供可用命令。`[-disable]` 文档含义是“使本条约束不生效”，不能推断追加同名带 `-disable` 会撤销旧语句。不得使用臆造的 `reset_path`/`remove_clock_groups`。

可复查指纹：

```text
clock.fdc SHA256 81b2ecb012968cfd2bae4b32dc7393b83081372e8be7f6fe9872f97eb1a0ddbb
Pango_Design_Suite_User_Guide.pdf SHA256 e2ac3f2ac7bb539cc51fe85cc239ea2249f4ee6790912b67c86cae23a3898ba2
Timing_Analyzer_User_Guide.pdf SHA256 0714bec1196c68b6cc49771c1415bfc1d36062349b8ae52fa5e1d6767c03c53a
pds_shell.exe SHA256 631ffd8f14d6246872873c72025cbc2734c9f8c388075b7afb0b042f3a684e6f
ta.exe SHA256 da319b57aac193a2e0b39f64beec2ddc6ea85d6fd1f3157882524c994ff08f42
```

## 路线 A：公开语法重建精确关系（推荐基线）

后续在独立 candidate 的加载约束中真正去掉/禁用原四个 PCLK 与 ddrphy_sysclk 的五条声明，不能先加载原声明再仅追加下面命令。保持所有 create_clock/create_generated_clock、uncertainty、IO 和其他约束值不变。其他单组 async 不动。由原关系矩阵验证下面两个 group 不会切断任何新增的旧同步关系。

已声明的时钟名字来自 clock.fdc，以下没有猜 cell/pin：

```tcl
# 替换五条原单组声明之后加载；必须在全部时钟创建完成之后。
set cam_clock_names {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk}
set other_clock_names {
    free_clk cam1_sccb cam2_sccb cam3_sccb cam4_sccb clk_150m
    rst_clk phy_dq_clk_0 phy_dq_sysclk_0 phy_dq_clk_1 phy_dq_sysclk_1
    sfp_fabric pclk pclk_div2 ref_clk
}
# Camera 与“其他”保持异步；AXI 与“其他”保持异步。
# 两个 -group，避免单个 -group 再覆盖 Camera/AXI。
set_clock_groups -name review_cam_other -asynchronous \
    -group [get_clocks $cam_clock_names] -group [get_clocks $other_clock_names]
set_clock_groups -name review_axi_other -asynchronous \
    -group [get_clocks {ddrphy_sysclk}] -group [get_clocks $other_clock_names]
# 四个独立 PCLK 之间的原豁免必须保留。
for {set i 0} {$i < 4} {incr i} {
    for {set j [expr {$i+1}]} {$j < 4} {incr j} {
        set_clock_groups -name review_cam_${i}_${j} -asynchronous \
            -group [get_clocks [lindex $cam_clock_names $i]] \
            -group [get_clocks [lindex $cam_clock_names $j]]
    }
}
# 所有 AXI -> Camera 反向路径继续保持原跨域豁免。
foreach cname $cam_clock_names {
    set_false_path -from [get_clocks {ddrphy_sysclk}] -to [get_clocks $cname]
}
```

这个名字列表只是当前 FDC 的已声明钟集，不能代替后续 `all_clocks`/真实时钟传播导出。若 DB 中出现额外生成时钟、多时钟寄存器或工具对 generated clocks 的隐式扩展，先算完整原关系矩阵再补充明确组列表。要求仅 Camera→AXI 四个有向关系从全局豁免迁移到路径级；不能把所有相机、AXI 简单归为一个“同步组”并漏掉 Camera↔Camera 和其他时钟关系。

### 路径集合与精确补集

对每个 Camera→AXI 有向钟对，令 `U_i` 为原单组语句实际覆盖的完整时序路径集合（含相关输入起点、数据/CE/reset 终点、双沿、多时钟传播情况）；`B_i` 为实际 mailbox→host_bank bundled-data 路径集合。后续新 setup false-path 集合必须是 `U_i \ B_i`，新绝对 delay 集合必须完整覆盖 `B_i`。每条旧更严格的例外仍需保留并做交集审查，不能因新 max_delay 值较大而覆盖一个旧更小的 delay。

不要用“host_bank 之外所有终点”单独作为补集：可能存在非 mailbox 起点也到达 host_bank。若正常数据路径是起点集合 `S`×终点集合`T`，mailbox 起点`M`、host_bank 终点`H`，可以用两个矩形 `(S\M)×T` 与 `M×(T\H)` 表达补集，前提是确认 `B = U∩(M×H)`，并单独处理 control/reset arcs。若不满足这个条件，枚举精确起终点/through 路径类别，不能按名称猜补集。

为了避免 collection API 和名字匹配方括号的厂商差异，建议由真实 DB 生成逐条对象的 Tcl；以下变量必须由后续 manifest 赋值。启动点优先实际顺序 cell 的 clock pin（或确认支持的顺序 cell），终点用实际 D pin，确保 max_delay 包含 CLK→Q 和 setup。Q→D 示例在手册存在，但只测 Q→D 不能自行声称已经包含 launch CLK→Q。manifest 必须导出每位映射、寄存器 type、clock provenance、D/Q/CLK pin、是否被优化/复制/合并，不硬编码 pin 字母。

```tcl
# old_exempt_pairs: 真实 U_i\B_i 路径类别；每项为 {start_clock_pin end_pin}。
# bundled_pairs: 真实 B_i；每项为 {launch_clock_pin capture_data_pin}。
# 这两个变量未经真实 DB 构造不得执行，以下不给臆造名字。
if {![info exists old_exempt_pairs] || ![info exists bundled_pairs]} {
    error "Missing reviewed actual synthesis path manifest"
}
foreach pair $old_exempt_pairs {
    lassign $pair start_pin end_pin
    set_false_path -from [get_pins $start_pin] -to [get_pins $end_pin]
}
foreach pair $bundled_pairs {
    lassign $pair launch_pin capture_pin
    set_max_delay -datapath_only 15.238 \
        -from [get_pins $launch_pin] -to [get_pins $capture_pin]
    # 异步邮箱没有相位相关的同步 hold 合同：保留原 hold 豁免，
    # setup/绝对 delay 必须可见。需实测 -hold 不会连 max_delay 一起屏蔽。
    set_false_path -hold -from [get_pins $launch_pin] -to [get_pins $capture_pin]
}
```

逐对 from/to 覆盖同一对端点之间的所有路径，不能表达只豁免其中一个分支。若一个端点对里包含不同 CDC 语义，需要官方支持的 `-through [get_pins/get_nets ...]` 再精确区分，并验证没有 overlap；无法区分则该分区方案失败。集合必须来自连接图/全部 arc，不可由受当前 false_path 过滤的“无时序路径”报告推导。实际出现空集合、多匹配、bit 丢失、未知扇出，一律停止。

`set_false_path -hold` 与 max_delay 并存是可验证候选，不是假定 PDS 全版本有效：本地语法支持按 hold 豁免，但未执行优先级试验。若它连 setup max_delay 一并屏蔽，路线 A 在保留旧 hold 豁免条件下还需要有效的 hold-only 替代；没有验证替代之前不能签核。不要用一个负数 `set_min_delay` 随意放宽来隐藏这个问题。

请求/确认/overrun 仅跨域进入首级的异步路径属于精确 CDC 豁免；首级→第二/第三同步级是目标时钟域正常路径，不能被旧补集或新增 false_path 误选。原负沿到正沿半周期路径和 AXI epoch/index/response 普通逻辑不属于这些补集。reset 相关恢复/移除与脉宽按独立清单审查，不能为了让邮箱报告好看而 false-path 全部 reset 树。

## 路线 B：本机 `-allow_paths` 线索（须先查帮助和实测）

只读 bytes 检查发现 `allow_paths`：pds_shell.exe 文件偏移 34930680；ta.exe 偏移 41163784。其紧邻字符串包括 `Specifies that the clock groups are asynchronous to each other.`、上述 `Enable the timing analysis...`、`Specifies a list of clocks.`。de.exe、pds.exe 也包含线索。仅此不能证明该参数的解析类型、组合限制、是 no-op 还是有效。

后续主会话允许且全局 PDS 空闲时，在独立工具探测目录先执行以下 Tcl（本次未执行）：

```tcl
foreach cmd {set_clock_groups set_max_delay set_false_path report_timing} {
    puts "=== HELP $cmd ==="
    set rc [catch [list $cmd -help] result]
    puts "rc=$rc result=$result"
}
foreach cmd {path_group group_path reset_path remove_clock_groups} {
    puts "$cmd exists=[expr {[llength [info commands $cmd]] > 0}]"
}
```

如果 runtime help 证实 `-allow_paths` 为 flag，可在替换后的独立候选中尝试：

```tcl
# 只作为实测候选；不是已核准 FDC。
foreach cname {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk} {
    set_clock_groups -name review_allow_$cname -asynchronous -allow_paths \
        -group [get_clocks $cname] -group [get_clocks {ddrphy_sysclk}]
}
```

要么先移除重建所有覆盖这些钟对的旧 global async，随后应用 allow 组与上述精确补集；要么 A/B 实验证明该选项能优先于仍生效的每一条旧全局声明。**不能只追加 allow 组就推断覆盖五条旧声明。** allow 组没有路径选择参数线索，因此仍须为旧跨域控制/数据保留精确例外。用它标记 asynchronous 不会自动证明邮箱采样安全，也不能替代数据稳定协议证明。

## 后续导出与 STA 验证步骤

1. 先收到主会话真实综合完成通知，确认成功阶段结果、全部 PDS/GUI 空闲。仅由负责构建的主会话运行既有 `export_synthesis.py`，核对 `.adf` 导出前后 SHA256 相同。该脚本只有 `.switch_db` 导出与 `report_timing -help`，不会自动给出全部命令支持、clock propagation 或 STA 生效证明。本次不运行、不改该脚本。
2. 将实际综合 dump 的寄存器/pin/net 连接与诊断 manifest 交叉核对。为四路每路 512 位建立逻辑位→实际 launch/capture mapping；允许优化后的合并/复制，但每个逻辑位必须有可解释覆盖，不能简单拿报告条数等于 2048 作为证明。检查 mailbox 所有真实 fanout、capture 所有 fanin，AXI clock 真正来自 ddrphy_sysclk，request/ack/overrun 首级及同步级、cr/hr/reset_pipe 和负沿路径分类完整。任何实际对象未确定，门槛保持 OPEN。
3. 独立 DB/constraints 副本上分别加载：A 原 FDC + 新 maxdelay；B 路线 A 重建 + 精确例外 + maxdelay；C 同 B 且仅去掉新 hold-only false_path；D 若 help 支持则单独检验 allow_paths。每个变体用全新会话/DB 副本，不靠未证实的删除或同名覆盖命令。保留六份原 FDC hash、候选约束差异、实际展开对象、命令返回/error/warning、clock 关系矩阵。
4. 对每个实际 bundled 端点对执行官方公开的查询语法，报告上限不会用来替代逐位覆盖：

```tcl
foreach pair $bundled_pairs {
    lassign $pair launch_pin capture_pin
    puts "BUNDLE $launch_pin -> $capture_pin"
    report_timing -from [get_pins $launch_pin] -to [get_pins $capture_pin] \
        -delay_type max -nworst 10 -max_path 100
}
# 另逐条查询真实首级→后级、负沿→正沿、AXI 普通寄存器路径，
# 使用从 DB 生成的 ordinary_pairs，而不是 RTL 名称通配符。
foreach pair $ordinary_pairs {
    lassign $pair start_pin end_pin
    report_timing -from [get_pins $start_pin] -to [get_pins $end_pin] \
        -delay_type min_max -nworst 10 -max_path 100
}
```

5. 用实际 `report_timing -help` 确认 corner、输出文件、Report Exception/Max Skew 的 CLI 参数后再填入。只读 bytes 虽有 `report_exception`、`report_max_skew` 字符串，不等于已确认 bool 参数写法。本手册公开的基础 report_timing 语法不足以臆造 `-corner`、`-file` 或 `report_exceptions` 命令。GUI/TA 可复核时选择 Slow 和 Fast 各自报告，开启 **Report Exception**，全钟组、不限定 slack/logic-level，保存 Set_Max_Delay Setup 详细报告；若路径未落普通钟组，增加 `**default**` 报告筛选。报告文件和 shell transcript 必须由后续验证会话保存到独立目录。
6. 生效判据必须同时满足：所有 B 位/分支都有非空最大延迟分析；requirement 为 ≤15.238 ns，报告明确对应新 maxdelay/datapath_only；有 launch CLK→Q、组合/net 与 capture setup 或明确等价分项；不以两异步时钟默认相位关系作为 requirement；B 不在 setup false_path/async ignored 中；hold-only 不屏蔽最大延迟；原 CDC 补集仍豁免且与 B setup 交集为空；所有旧同步关系和更严格例外不削弱。保存每条 B 的 delay、slack、corner、覆盖来源，不只保存“0 failing paths”摘要。
7. 做敏感性试验：独立新会话候选把某一真实 B 路径 maxdelay 下调到其已报告 datapath delay 以下的非负值，必须产生该路径负 slack；恢复 15.238 后 required/slack 相应变化。若小值仍“0 failures”且路径缺失或数字不变，这是被忽略的证据，不能签核。比较 B/C 可证明 hold-only 是否影响 setup；比较原 global async 与拆分版本可确认实际屏蔽机制。
8. 合成 DB 验证的是命令和路径覆盖，不能证明布线后绝对延迟。只有约束门槛关闭后才由主会话决定后续 PNR；最终 routed DB 重解析优化/复制后的对象，重新做全部 B 逐位覆盖与 Slow/Fast maxdelay，并复用 V7 十组 setup/hold/recovery/removal/min-pulse-width 全零失败和 pin/HSST/motion 资源比对。旧十组全零不能替代 mailbox 专项验证。

## 失败判据与最终判断

- 追加 maxdelay 仍被原 async 忽略，且不允许替换生效的五条全局声明，又没有实测有效的 allow/exception：**在该不可修改边界下硬阻挡，禁止 PNR/签核。**
- 拆分后 maxdelay 不能对有效顺序 cell/pin产生绝对 requirement，或 hold-only 连带屏蔽、无法精确保留旧 CDC 补集：**当前版本/对象方案阻挡，需要官方确认或另一个经实测的支持机制，禁止假签核。**
- 真实数据路径超过 15.238：是实现时序失败，不能通过放宽上界、skew-only、乱加 false_path 或多周期宣称解决。
- 有效 delay 全覆盖且补集、普通路径等价审查通过：仅关闭约束表达/优先级门槛；完成 routed/corners/reset 等证据后才可能物理签核。

当前确定结果：公开命令提供可验证的精确例外重构路线，本机还存在 allow_paths 候选线索；没有足够证据宣称 PDS 无法表达此约束，也没有足够证据宣称新邮箱已满足绝对 delay。**可解的约束方案已给出，实际工具和综合对象验证待通知；物理门槛未关闭。**
