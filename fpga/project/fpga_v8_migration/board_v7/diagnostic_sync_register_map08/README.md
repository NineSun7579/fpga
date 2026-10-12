# 实际工程上下文的映射与约束反标探针

map07完成基线Device Map，但export_fdc要求打开工程上下文，随后失败。原映射数据库和失败不改写。本次仅在实际mapping脚本的set_arch后插入open_project，路径指向隔离执行工程。语法来自已实际运行的PDS帮助，context_interface_basis.json绑定帮助和前次失败hash。

两个实验臂的工程/RTL/clock/site准备输入与map07一致；生产文件和所有原尝试不变。继续保留twoFF图、复位/CE语义、独立单元、Q-to-D以及PCF/FDC位置传递实证门禁。尚无方法PASS，更无生产60级和bit/板级PASS。
