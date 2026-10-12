# physical FDC match09 子代理

query_epoch08/result.json 已核对：SIZE3/4 是 get_pins 符号表达式长度，acceptance=false；不作为匹配证据。

官方 User Constraint Editor 文档 PDF 第69页（印刷68页）规定集成版 instance 层次为点，pin 分隔可点或斜杠；后端 SDC 层次斜杠、pin 冒号。PDS 文档 PDF172页说明 RTL 网表约束由软件传递到后续网表。native_probe_07 的 compile graph 是向量 mailbox/host_bank；synthesis graph 是 GTP_DFF_CE 标量。单纯拼接两个阶段名称和 Tcl llength 不能证明 UCE 接受或传递。

2026-10-06 子代理启动 tiny_match09.py 被单实例断言挡住，未启动任何 PDS。进程快照确认父会话 Python37960/run_native_fixed08.py -> PDS53016/76680 正在 compile，Python77844/finish_native08.py 等待它。未修改正在运行的工程/约束/RTL/DB，未终止任何进程。

已启动后台 shell sh_111799595001mWQwuSKxG8Qg8a：Wait-Process 37960,77844 自然退出，然后串行执行 tiny_match09.py。其五种 dot/slash/escaped/wild/regexp 方案在 fixed_06/tiny_match09/ 独立目录，真实 compile/synthesize/dev_map/report_timing；验收要求没有 E:/Timing-4003，且实际 rtr 有 Startpoint 和 MaxDelay Path。没有 intentionalstop，也没有 sizeof/llength 检测。各方案失败独立保留，不改生产/旧V7/IP，不生成bit，不remote/program。

完整四路 native08 流程由父会话正在运行，子代理等待其结束后才能继续工具实测。此记录不是实现成功收据；tiny 尚未运行完成、map/pnr 和约束覆盖尚未验收。

后续实际结果：native08/dev_map_result.json 确认 compile、synthesize、Device Map 都 started/done，exit0 errors=[]，且设计 successfully mapped。finish_failure.txt 停在 new_derive_exact_complement exit1，PNR尚未验收。tiny_match09 五个案例都失败在报告输入DB不存在：run.log只有 Executing compile/synthesize/dev_map successfully，无任何 Process started；原因是 Tcl 未指定 force_to_run，仅登记流程。已将 tiny_match09.py 修正为每阶段 force_to_run，输出改独立 tiny_match10，旧失败保留。启动修正版再被单实例保护阻止；此时父会话 PDS84476/81056 正在 fixed_06/match_epoch09 运行 synthesize，父控制器62444。避免与父会话竞争工具，子代理不再排队自动启动；脚本待父会话串行调度。尚无 tiny 实际匹配验收，不能将五个案例失败解释成 UCE 不支持名字。
