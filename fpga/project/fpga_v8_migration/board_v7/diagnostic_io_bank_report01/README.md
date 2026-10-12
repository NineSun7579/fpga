# 原生 IO bank 报告诊断

目的：区分 attempt03 routed ADF 内部 bank 状态和原生报告生成异常。原始112行 IO gate 保持失败；不改写 bank、不修改冻结候选、不重新运行综合/映射/PNR、不生成 bit。

当前已知边界：attempt03 的 map 原生封装表 M15=L4、Y18=L5、V4=R5；map 表的 PORT/DIRECTION 尚为空，不能据此证明已用 primitive 状态。PnR 原生 IO 表将112个已用 IO 全标 L6，pinout 的 site/功能名仍与原封装一致。详见 goal_board_validation_01/ATTEMPT03_IO_NATIVE_FAILURE_REVIEW01_ZH.md。

discover_interfaces.tcl 仅初始化正确架构、枚举实际命令，并对存在的查询/报告命令请求帮助。不加载数据库、不执行报告生成、不猜测 bank 属性值。现已实际执行，discovery_receipt.json绑定脚本和完整日志hash：退出0、完成标记存在。该发现阶段不是IO验收。

实际发现：没有bank/pinout命令；get_pins/get_cells/get_ports帮助可用；get_attribute、get_property、read_db、read_adf、report_io、report_pinout、report_package不存在。可用数据库命令列表只有.switch_db。不能据此宣称内部bank正确，也不能将猜测的API用于验收；需要继续找受支持的数据库检查/报告生成途径。

执行时必须确认现有 PDS/TA/GUI 单实例队列已空闲，并使用此隔离目录作为 work_dir；不能插入正在运行的 clock_epoch、map02 follow-up 或 map03 控制器之间造成竞争。

接口确认后的下一阶段须复制 map 与 routed ADF 到独立目录，绑定原件/副本哈希；只加载副本，分别比较封装 pin/site/bank 和已用 IO primitive 的 bank 信息。原始报告、失败和数据库不替换。结果必须包含全112行及电气属性，不以三个示例代替最终验收。
