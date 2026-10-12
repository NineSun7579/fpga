独立外部 review03 交付

请独立 reviewer 在自己的新 review03 目录只读核验本目录；不得覆盖 build04_mapped_endpoint_review02 或原 mapping FAIL。这里没有代替外部审计生成 PASS。

审计输入：review03_bundle_hashes.json 覆盖本目录封存文件；copy_adf_binding.json 将官方输出关联原 mapped ADF；native02_launch.json、native02_process.json、native02_receipt.json 和 native02/shell.log 提供真实导出命令/工具 hash/退出结果/全部产物 hash。functional01 对 MAP phase 拒绝的完整日志也在包中，必须保留该反证。

必要复查：

1. 原与 copy ADF 同为 3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419；原 build04/03/02 完整树和 review02 原保护清单未漂移。
2. native02 官方 .v 确实只有 OPER 黑盒而无 V_* 行为；不要将可读库模型的存在当成 mapped 绑定。
3. fresh_native_graph_binding 的原 parser hash、fresh dump hash、fresh graph 与原 graph 的比较及 60 行实际记录；统计独立注册输出仍需参照 review02 rows60/36 对 Q-D 和实际 graph，不能从空模块数推断。
4. gen_netlist 要求 PNR phase 是实际错误，不允许通过改 phase 或新 PNR 抹去；native01 超时及 help01 unsupported 的退出状态如实记录。
5. OFFICIAL_MODEL_BOUNDARY_ZH 的精确行为分析仅限安装 primitive 本身，60 FF 与源 resetcone 仍未绑定。

预期审计结果：可独立判定导出 receipt/原件保护通过，但 mapped 行为完整性仍 FAIL/BLOCKED，bit/board 不放行。最小支持接口详见 RESULT_ZH.md。
