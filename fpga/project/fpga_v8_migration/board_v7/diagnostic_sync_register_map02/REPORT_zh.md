# diagnostic_sync_register_map02 真实 mapping 与独立审计

最终状态：FAIL。工具完成与物理结构通过分别核验。未执行 PNR、烧录或远程操作。

|阶段|独立存储单元 / 60|同步 / 28|复位 / 32|拓扑结果|
|---|---:|---:|---:|---|
|compile|60|28|32|PASS|
|synthesis|60|28|32|PASS|
|mapping|4|4|0|FAIL|

三个 devmap 整数选项的真实执行核验：True。
ADF、native DB 与导出 graph 的 hash 核验：{'compile': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True, 'dump_matches_export': True}, 'synthesis': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True, 'dump_matches_export': True}, 'mapping': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True, 'dump_matches_export': True}}。
逐端点连接/属性检查失败数：{'compile': 0, 'synthesis': 0, 'mapping': 60}。
受保护工程与旧 IP 文件：1022；活动输入 guard：741 个文件，差异 0。

gate 不可放行。实际 packing 失败绑定见 evidence/packing_failure.json。
本 map02 已实际对照 60 个 syn_noprune=1 原语实例。官方 ADS 第 90–91 页支持 instance 作用域，但只说明综合保留。UCE PDF 第 94 页明确 FF pack 无视 PAP_DONT_TOUCH。当前不能据此宣称存在有效物理防 packing 属性，详见 COMPARISON_zh.md。

详证：evidence/final_result.json、independent_audit_result.json、mapping_artifact.json、mapping_topology.json、mapping_endpoint_details.json；字节逆变换和属性对照见 attribute_byte_inverse.json、attribute_propagation.json。
