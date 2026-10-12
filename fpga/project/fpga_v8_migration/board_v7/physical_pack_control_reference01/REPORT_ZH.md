# 官方物理打包控制证据

已使用 Python SQLite 只读打开安装目录 `bin/helpDoc_pango.qch`，对 FileDataTable 的 Qt 压缩数据去除四字节长度头并 zlib 解压。原始 HTML 保存为 help_0.html 等；qch_search.json、site_constraint_context.json 保留文档名称和实际上下文。未启动 PDS 或修改安装文件。

ADS Synthesis User Guide 5.14 明确说明 syn_noprune 保留综合实例，并注明只能保持到综合阶段，未连接的实例在 dev_map 仍可能优化。该说明不构成禁止串联寄存器物理 packing 的承诺。

PDS User Guide 的布局约束章节给出 `def_inst_site inst_name site_name [impl_name]`，包括寄存器实例示例 `def_inst_site TempFF CLMA_77_35 FGA`。该示例证实寄存器位置约束语法，不能证明本器件同名 site 合法，不能证明约束在 packing 前生效，也不能证明它必定阻止 SRL2/LUT6QQ 合并。实际实验仍需核验器件资源、目标解析和映射网表。

常用命令 dev_map 9.9 未找到禁止 FF packing 的公开选项。安装属性和 Option 文件按字节搜索未命中相关文本；这些文件可能不是明文，不能据此判定接口不存在。

当前 map02 的真实最终结果仍为待完成。60 个编译/综合独立实例不能代替 mapped 60 独立端点证明。若保留属性实验失败，应保留失败证据，在隔离实验先核验合法 site 与两级寄存器映射，再决定是否扩展位置约束。
