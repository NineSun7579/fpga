# attempt03 原生 IO bank 差异

前序 route_attempt_03 已完成1320对 mailbox 双角查询，但全局审计在 physical_subagent_evidence_01/audit_fixed.py:56 的112行完整IO比较处失败。official_attempt03_failure.txt 与 remaining_physical_failure.txt 保留；该候选没有完整签核，也没有 bit 放行。

只读源码及原生工件调查排除 summarize_route.py 的 bank 推算错误：该解析器直接保留 XML data 文本。attempt03 的 place_route/prr.db、v7_sdt_top.prr、v7_sdt_top_prr.prt 均记录差异，不是只在 JSON 中出现。

原生例子：M15/button_rst_n 从基线 BANKL4 变为 BANKL6；Y18/cmos1_data[0] 从 BANKL5 变为 BANKL6。attempt03 文本 IO 报告的112行全部为 BANKL6，包括 DDR、free_clk 和相机IO。pinout 中 M15 的 IOBD_0_624/DIFFIO_L4_G3_23P_VS1、Y18 的 IOBD_0_450/DIFFIO_L5_G2_12P_GMCLK、V4 的 IOBD_372_468/DIFFIO_R5_G1_11P_GMCLK 与基线相同，但 bank 全显示L6；未占用引脚仍显示其他 bank。至少 button 的 routed ADF PAP_IO_LOC、IBUF/IOL SITEREF 也未改变。

工程和 impl.tcl 均声明 Logos2/PG2L100H/-6/FBG484。上述矛盾提示已占用 IO 的 bank 元数据或报告生成异常，但不足以判定真实 bank 配置正确，也未确定异常首次出现阶段。不得忽略 BANK 列、依据基线改写原生报告或按 DIFFIO 名称覆盖 bank 后放行。

第三版 runtime 的提取算法无相应解析错误，global_audit.py 仍执行完整112行比较；当前没有第三版完成的 PnR 实证。后续先定位已有 compile/synth/map/routed 工件中的首次差异，再在工具空闲时用隔离、只读的官方报告重生成实验验证原因。原始失败不替换，冻结候选输入不修改。

进一步只读阶段调查：异常首次可观察于 PnR 原生输出。attempt03 device_map/dmr.db 的封装表（约671/1022/2228行）及当前/bak pinout 仍记录 M15=L4、Y18=L5、V4=R5；但其 PORT/DIRECTION 为空，这仅证明封装映射，不能证明已分配 primitive 的内部 bank 状态。compile/synth 原生表没有可用 BANK 字段，导出属性也没有显式 bank。PnR prr.db 的 IO 表和 pinout 才将已用IO全记为L6。登记的FDC/Tcl/PDS未发现显式全局 bank 赋值。安装 BSDL PG2L100H_FBG484.bsm 的499/527/660行分别记录 L4_PAD47:M15、L5_PAD25:Y18、R5_PAD23:V4，但该文件 preliminary 标记保留，不能代替配置验收。

没有找到可引用的已知官方 BANK 报告 bug 说明。已准备 diagnostic_io_bank_report01/discover_interfaces.tcl，仅用于工具空闲后的实际命令/帮助发现；尚未执行。后续诊断需分别读取 map/routed 副本的封装关系及已用 primitive bank，以区分报告异常、进程状态和实际内部配置变化，不必预先重跑完整流程。

另一个独立门禁：map02 final_result.json 已实测 FAIL。compile/synthesis 各60独立寄存器，但mapping仅4独立sync、0独立reset；primitive syn_noprune 不能阻止当前打包。现有 map03 条件队列仍用于位置约束方法实测，twoFF通过也不能代替生产60级验收。
