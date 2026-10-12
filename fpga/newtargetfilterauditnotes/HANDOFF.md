# targeted report 独立只读核实（交接主会话/负责代理）

本次没有启动 PDS/TA、没有 remote/program、没有修改代理或生产文件。所有工具串行；仅此目录新增审计脚本和结果。Hindsight 连接失败，结论来自现存文件。工作区 rg 不可用，使用 Python 字节搜索。

## 明确原因

exact09 的 targeted 筛选确实失效，原因不是推测的 PDS -file 丢参数：

- `physical_subagent_evidence_01/fixed_06/physical_exact_09/routed_mailbox/export.tcl:2` 有 from/to、nworst=2、max_path=10000、report_exception=TRUE；生成 `impl.tcl:3` 和实际 rtr 头部也有 from/to、nworst、max_path。
- `routed_mailbox/report_timing/run.log:16` 起 2640 条 Timing-4006，正好对应1320 launch+1320 capture 的综合祖先名称全部找不到。2656/2657 行明确：`STA-3016: The target option of report timing is ignored because -from/-to objects can not be found.`
- `routed_reset/report_timing/run.log:16` 起32条 Timing-4006，48行明确同样忽略 -to。
- 报告实际路径使用 `.../opit_0_*_perm/CLK`、`.../opit_0_*_perm/D` 等物理 child，查询却使用综合祖先 `/CLK`、`/D`。reset 综合 `/P` 与 routed `/RS` 还可能有端口语义转换；不能仅拼 child 或机械 P->RS，必须使用当前 DB 的经过证明的映射。
- 8份 target/shell/run/flow 日志已完整字节扫描，`unknown argument(s)/option(s)` 模式匹配均为0；不是错误日志全为0：Timing-4006 和 STA-3016 均非零。精确计数/行号见 log_counts.json。
- 这8份日志没有 `ta.exe` 进程调用行，Application name 是 pds_shell.exe。不能虚构 PDS 内部 ta.exe argv。能够实证的是 export TCL -> impl TCL -> report header -> 实际 timing graph 解析警告，足够证明 from/to 到达了报告器。原 STA A/B 独立 GUI 则有真实 ta.exe launch.json。

两份首记录相同的解释是：无效目标全部被忽略，输出变成全局报告（按其 report 配置挑选的全局路径，不能声称枚举设计全部可能路径）。首记录与 mailbox 无关不等于 mailbox 记录不存在。

## 实际记录统计与范围

`stream_results.json` 可复核，`stream_audit.py` 使用二进制逐行读取，仅保存当前记录字段和唯一对集合，不 readall 巨大报告。

|报告|本次范围|有 Slack 的完整 record|mailbox MaxDelay record|唯一目标覆盖|
|---|---|---:|---:|---|
|exact09 routed_mailbox 2,045,723,213 bytes|全扫到 EOF|258615，Slow129974/Fast128641|2640|Slow1320/1320，Fast1320/1320，unexpected0|
|exact09 routed_reset 10,759,580,391 bytes|只扫前128MiB，读到134217801 bytes，边界未完成记录不计|21621，均Slow|该前缀0|不能外推全文件|
|original STA A/B `ta_B_exact_grouped_01/bundle_max.snr` 5,951,739 bytes|全扫到 EOF|1280，均Slow|1280|对其原 manifest 应为1280/1280；本脚本共享exact09 manifest时交集1280/1320，不是原实验漏40对|
|original `reset.snr` 3,080,347 bytes|全扫到 EOF|32，均Slow|0|16 Recovery +16 Removal，覆盖16个 AXI reset_pipe P|

exact09 的覆盖使用去除 `/opit_*` 的审计 canonical 名称与该次 actual/analysis/manifest.json 的1320对比较；这种 canonical 统计不是可传给工具的查询名称，也不是完整物理一一映射证明。本次没有重新验证全部预算值、每条 slack 或整个签核，不把 coverage 当 timing PASS。

reset 额外只读抽样：偏移5,379,790,195处16MiB窗口匹配1391个 Recovery/Removal time 标记（可能包含边界片段，非完整record总数），可见 `Removal time`、`Path Type: min (slow corner)`、`Path Class: async timing path` 和物理 `/RS`；尾部16MiB该模式0。这个抽样不算全扫，不断言reset文件检查记录为0。

## 支持的筛选方式：已有帮助/实测证据

1. **PDS report_timing 字符串目标**：现存 `source_diagnostics_build_01/sta_ab_01/load_help/shell.log:43-83` 明确支持 input_db_file、delay_type、nworst、max_path、report_exception、from/to 字符串列表。因此优先修复传入的物理目标，不需要换一个没有证据的后端 API。
2. **已加载 TA 的真实 collection API**：`sta_ab_01/probe/shell.log:111-144` 帮助明确 get_pins/get_clocks 创建 collection，get_pins 支持 regexp/hierarchical；`ta_B_exact_grouped_01/shell.log:774` 真实执行以下查询，7436行 successfully；bundle_max.snr 全扫1280条与之吻合：

```tcl
report_timing -report_exception TRUE \
  -from [get_clocks {cmos1_pclk cmos2_pclk cmos3_pclk cmos4_pclk}] \
  -to [get_clocks {ddrphy_sysclk}] -max_path 2000 -nworst 2
```

该例是综合 Slow、时钟域定向，不能冒充 routed双角结果；物理精确对筛选应使用实际DB解析的get_pins目标。

3. **DB/约束加载有证据的方式**：安装 `C:/pango/PDS_2022.2-SP6.4/doc/Timing_Analyzer_User_Guide.pdf` PDF第14页（印刷13页）说明 Import DB and SDC，Design DB必选，支持PnR/PLC/Syn；第17页说明 From/Through/To；第24页说明无效位置会critical warning。原 A/B launch.json 有 `ta.exe -sdc combined.sdc -rtr <trial> synthesis.adf`，但原 RESULTS.md及实际ui_import.json明确只有GUI Import才被核实成功，不能依CLI推断已加载。
4. **不能凭空建议 loadDB/readConstraint/sizeof_collection**：本次未找到它们的已存help/成功调用；PDS `load_help/shell.log:109-110` 的 sizeof_collection/get_object_name exists为空，probe/shell.log:10 的 load_db exists为空。两种工具上下文不可混同；也不把另一上下文未注册推导为全工具永远不支持。collection应按已有get_pins/get_clocks帮助使用，集合大小/成员校验在已导出的graph及报告审计完成，不能对opaque collection假设llength有效。

`-max_path`/`-nworst` 也出现在impl与报告头。GUI手册PDF第15-16页说明语义，同时第16页明确 report_exception 是独立 exception 报告。总文件258615记录不能单凭大于10000就断言参数未解析（多角、多组、独立例外报告会影响总数）；本次没有实测其各表计数上限，不能确认全文件上限语义。

## reset parser 的独立错误

不是仅将 Path Type 换为 Path Class 就能修复：原真实reset.snr中：

```text
Path Type   : max (slow corner)
Path Class  : async timing path
Recovery time ...
```

Removal 是 `min (slow corner)`、同样 `async timing path`、`Removal time ...`。

`source_diagnostics_route_01/audit_targets.py:8` 仅存Path Type为kind；`audit_fixed.py:88-91` 用kind包含Recovery/Removal来筛选，必然空cover。`source_diagnostics_timing_build_01/routed_acceptance.py:92` 虽拼接path_class，真实两字段仍都无Recovery/Removal，因此对这类记录仍空cover。应新增 `check`，从当前record内行首 `Recovery time` / `Removal time` 推导；若其他报告格式明确有Recovery Path/Removal Path字段，再支持该明确字段，不能全block查Removal（`Clock Pessimism Removal`会把普通路径误判Removal）。原 `sta_ab_01/audit_control_report.py:10` 已使用Recovery time/Removal time作实测分类依据。

## 交给负责代理的具体改法（本次不改其文件、不启动队列）

- `audit_fixed.py:61,62,65,73-78`：用当前route哈希绑定的routed graph/coverageproof中的物理pairs、reset_bindings、sync_bindings生成字符串列表。exact11 finalize调用旧audit_fixed的路径还会再取actual综合manifest，必须在负责代理自己的入口参数化这三组，不能只完成physical proof却仍查询祖先名。timingbuild01现有routed_acceptance已适配physical pairs，保持其映射断言；对P->RS不能无证据强行修复。
- 每次report之后先检查 target shell日志及 `report_timing/run.log`：出现Timing-4006/STA-3016或unknown arguments/options立即判target失效，保存原因后退出；exit0与successfully都不足以放行。
- 先单对实际child `/CLK -> /D` 查询，nworst2/max_path8、report_exception TRUE；核实所有实际record起终点属目标，明确MaxDelay预算和corner，零STA-3016/4006。再分camera/小batch跑完整目标，按物理pair求集合覆盖；时钟定向可诊断但不能代替精确集合验收。
- 当前队列中的控制器在Python中已加载源码；仅改磁盘模块未必影响已加载函数。由主会话交给负责代理，在其受控后续审计入口改绑定与门禁，本次未干预进程。
- parser新增check并在reset门禁使用check，不使用kind/path_class拼接；corner只来自当前record的Path Type，避免原corner='Slow' if 'Slow' in block等将下个摘要混入最后一条record。
- 解析必须流式，record在Slack处完成后提交；下一Startpoint前的summary/exception table不要并入最后一条record；目标比较以物理名称为准，logical<->physical明确映射并检查非注入/遗漏。

建议负责代理落地的代码形态：

```python
# report完成之后；log_paths包括实际report_timing/run.log，不能只看returncode
for log_path in log_paths:
    with log_path.open('rb') as stream:
        for line in stream:
            if (b'Timing-4006' in line or b'STA-3016' in line or
                re.search(rb'unknown\s+(?:arguments?|options?)', line, re.I)):
                raise RuntimeError('Target collection failed: ' + line.decode('utf8','replace'))

# 在当前record范围内；支持空格和CRLF
recovery = re.search(r'^\s*Recovery\s+time\s', block, re.M | re.I)
removal = re.search(r'^\s*Removal\s+time\s', block, re.M | re.I)
row['check'] = 'Recovery' if recovery else 'Removal' if removal else None
selected = [x for x in subset if x.get('check') == kind]
```

PDS字符串筛选例（由代理填当前DB真实physical路径，不是祖先名）：

```tcl
report_timing -input_db_file {<current_route_pnr.adf>} -force_to_run \
  -delay_type min_max -report_exception TRUE -input_pins TRUE \
  -nworst 2 -max_path 8 \
  -from {{<actual_mailbox_child>/CLK}} -to {{<actual_host_bank_child>/D}}
```

这套改法直接利用已证明到达报告器的PDS参数接口。TA console替代仅在DB+约束已经按原实验方式明确加载之后，使用`-from [get_pins {<physical CLK>}] -to [get_pins {<physical D>}]`；本次没有验证一个新批处理loadDB/readConstraint命令，也不建议绕队列开启它。
