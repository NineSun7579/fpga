# 已复制工程上下文与约束反标

第一/二轮启动架构后的命令发现未加载设计；第三轮实际帮助确认open_project project_file_path语法和export_fdc对工程上下文的要求。本轮在map08退出后，绑定并复制attempt03的project、compile/synth/map/PnR ADF/DB/PCF与约束到copied目录，只打开副本、枚举接口、导出约束。不运行compile/synth/map/PNR/bit，不访问板设备。

copy_bindings.json绑定原件和副本hash，context_receipt.json检查操作后原件hash未漂移。原PnR IO报告仍失败；导出约束本身没有证明内部BANK状态的效力，也不能替代完整112行IO验收。打开project的标记不能无条件证明routed design对象已被加载，需依据实际命令/输出继续核查。

本轮仍为诊断，未声称实际IO PASS、时序签核或交付成功。任何失败和部分产物保持原位。
