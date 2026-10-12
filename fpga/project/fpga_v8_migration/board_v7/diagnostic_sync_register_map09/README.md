# 原生 PCF 与实际映射图的位置约束验证

此前实际CLI实验无法完成export_fdc工程上下文：open_project在脚本预解析报错，project_file_path虽出现在帮助中但被参数解析器拒绝，-project和-file不可同时指定。失败日志hash绑定于constraint_consumer_change.json，原尝试不修改或视为PASS。

本次两个实验臂准备工程/RTL/时钟/位置约束与map07一致，保留全部独立存储单元及D/Q/CLK/reset/INIT/GRS/CE和链连接检查。映射脚本仅执行set_arch/add_constraint/dev_map，拒绝任何未知/忽略选项与错误。

位置约束证据改为两项都必须存在：原生PCF中实际映射单元名、site与impl的精确绑定；实际映射图中同一单元PAP_LOC属性或CDB条目包含该site/impl。不以输入约束存在代替已消费，不宣称完成FDC反标。如工具未保留实际图位置属性，本方法也不能PASS。

即使PASS_METHOD_ONLY仍只证明twoFF方法，生产60级/时序/IO/新bit/烧录及截图仍需独立实证。
