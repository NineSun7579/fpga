独立审查结果：FAIL。原 mapping60_01/final_result.json 保留 FAIL。

本地离线审查了原 mapped ADF 的既有官方 native export，未运行 PDS、PNR、bit、program 或远程操作。用原 parser 的逐字相同副本重新解析 native dump，graph SHA256 与原 graph 完全一致。

实际 60 个 retained cell / 60 个 PAP_LOC site / 60 个独立注册输出 net：28 gopQ、20 gopQ_Cell_1、12 gopLUT6Q_Cell_139。逐项数据在 rows60.json 与 rows60.csv，36 对相邻 Q-D 在 adjacent_Q_D.json。

精确 PCF+PAP_LOC 关联 60/60；clock identity 参数检查 60/60；原始参数匹配 60/60。PCF 是实际三参数 def_inst_site，没有 implementation 第四参数；mapped attributes 没有 PAP_NOPRUNE。两者如实记录，不凭空补入实现名或属性。

12 个 cr/hr/reset_pipe FF0 为一个 LUT6 加一个 FF 的结构。INIT 为 10 重复 32 次，完整 64 行 truth table 证明输出函数是 I0；I0 实际常量 0，另外 5 个 don't-care 输入穷举后全部 32 个可达组合输出均为 0。实际注册输出是 L6Q，CLK/RS 独立，后级 D 接它。通过此项的 FF0：12/12。未以 reset 根来源相同替代 LUT 函数证明。

严格 FAIL 缺口：安装的官方 gopQ/gopLUT6Q 等 .eval 文件是 PANG 二进制。已保存其 before/after hashes、官方 gopL6Q packing rule 和既有参数解码依据，但没有可读行为模型或既有解码器可证明完整 QMUX/clock/reset/CE/GRS/async 行为。官方 packing rule 仅证明 gopQ+gopLUT6 合并成 oneFF 的端口与参数映射；不能替代完整行为模型证明。60 行 official_gop_behavior_decoded 均未通过，因此不产生独立 PASS。

reset cone 的完整 16 行 truth table 比较也仅在精确 retained 原 source-register 输出边界上成立；边界上实际存在 L5Q/L6Q 和反相寄存器实现，未接受这些源寄存器变换的完整语义。具体 mapped driver records 与全部 LUT 参数/真值表已逐行留证。

非模型缺口：[]。

保护核验：3430 文件 before/after SHA256 全部相同：True。原 build04（含原 map/FAIL）、build03、map01、map02、保护源及计划均未修改。artifact_provenance.json 记录实际 ADF/dmr/PCF/native dump/graph/parser 和工具、parser 日志 hashes；protection_comparison.json、before_hashes.json、after_hashes.json 提供完整核验。

consumer 必要兼容改动（仅审查副本实现）：

- 从丢失的逻辑 alias 转为 fresh60 exact GTP retained ff path + planned site + actual PCF/PAP_LOC 的交叉绑定。
- host clock 使用原 u_sysclk_bufg 的精确 retained CLKOUT；ACK 输入源识别实际 L5Q。
- oneFF integrated LUT 使用实际 L6Q 作为注册输出、完整 LUT 函数作为内部 D；普通 FF 使用实际 D/Q/CLK/RS，禁止猜造 D 端口。
- 仅接受已证明的精确类型与参数；SRL、QQ、多级 pack 或未知类型必须 FAIL。取得官方 gop 行为解码依据后才可进一步作完整功能判定。

attempt_01 与 attempt_02 保留离线 consumer 修正前发现；没有重复执行 mapping/export，也没有改原结果。
