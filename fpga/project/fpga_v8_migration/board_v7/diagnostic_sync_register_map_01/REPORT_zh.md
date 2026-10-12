# map01 真实 mapping 与独立审计

最终状态：FAIL。工具完成与物理结构通过分别核验。未执行 PNR、烧录或远程操作。

|阶段|独立存储单元 / 60|同步 / 28|复位 / 32|拓扑结果|
|---|---:|---:|---:|---|
|compile|60|28|32|PASS|
|synthesis|60|28|32|PASS|
|mapping|4|4|0|FAIL|

三个 devmap 整数选项的真实执行核验：True。
ADF、native DB 与导出 graph 的 hash 核验：{'compile': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True}, 'synthesis': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True}, 'mapping': {'adf': True, 'native_db': True, 'export_matches_artifact': True, 'graph_matches_export': True}}。
逐端点连接/属性检查失败数：{'compile': 0, 'synthesis': 24, 'mapping': 60}。
受保护工程与旧 IP 文件：1022；活动输入 guard：741 个文件，差异 0。

gate 不可放行。实际 packing 失败绑定见 evidence/packing_failure.json。
最小有官方文档依据的对照改法：仅在 60 个相连的 GTP_DFF_CE/PE 原语实例上添加 syn_noprune=1，保留原记录，在独立对照中重新 compile/synthesis/map。官方 ADS 文档 PDF 第 90–91 页支持 instance 作用域；其文档说明综合保留，不能预先承诺阻止物理 packing。syn_preserve 的文档作用域是 module/port/register，syn_srlstyle 面向 inferred shift，均不能替代实际 60 单元证明。

逐对实证见 evidence/packing_pair_witnesses.json：28 对，合成阶段 Q→D、同 clock、同异步 reset 与实际 mapped 物理单元绑定核验全部通过：True。打包物理类型数量：{'SRL2': 16, 'LUT6QQ': 12}。

详证：evidence/final_result.json、independent_audit_result.json、mapping_artifact.json、mapping_topology.json、mapping_endpoint_details.json；恢复溯源见 mapping_recovery_receipt.json 与 attempts。
