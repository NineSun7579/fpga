# twoFF 综合 CE 化简等价审计

map06实际编译/综合/导出已成功；综合将CE=1的GTP_DFF_CE化简为GTP_DFF_C，两个独立寄存器的D/Q/CLK/C/INIT/GRS均通过，失败仅为原审计仍要求CE引脚。官方GTP_DFF_C模型无CE端口，在异步clear/GRS未激活时每个正时钟沿采样D；其文件路径和hash绑定于CE_normalization_basis.json。

本次准备工程、RTL和约束与map06完全一致。审计保留所有独立端点、时钟/复位源和初始化检查；有CE的单元仍须CE=1；无CE仅接受类型严格等于GTP_DFF_C且端口集合严格等于Q/D/CLK/C。不能将任意无CE单元当成等价。

本次仍需实际baseline/site映射图和位置传递证据，尚无方法PASS；即使PASS也不替代生产60级及bit/板级验收。map06失败和全部原始工件不修改。
