# twoFF 探针顶层解析修正

map05实际完成编译和综合，但导出图解析器仍绑定v7_sdt_top而不是探针map03_twoff_probe，导致topviews=[]。原始编译/综合/导出及解析失败完整保留在map05。

本次两个臂的准备输入与map05逐字节相同；仅控制器在创建隔离parser副本时，精确替换两处顶层字符串。原生产parser、图构造算法和所有RTL/时钟/位置约束不变。parser_top_binding.json绑定原始parser和探针parser hash及替换范围；后续实际export receipt仍绑定实际parser hash。

PASS_METHOD_ONLY仍仅为两个寄存器方法探针，不替代生产60级或最终bit/板级验收。
