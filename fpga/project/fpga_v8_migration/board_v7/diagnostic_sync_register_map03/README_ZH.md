# twoFF placement method probe（仅离线准备）

默认入口 `python check.py` 或 `python check.py --check`，只读取文件并打印 JSON。没有 run 选项，也不调用 PDS、remote 或 device。`prepare_reference.py` 和原 official_site_probe_basis.json 保持原样。没有改 map02、build03 frozen、生产 source/IP、旧 DB、其它 agent 报告或窗口。

baseline 与 site 各有隔离 RTL、工程和 Tcl 模板。RTL、project.pds、clock.fdc、stages.tcl 字节相同，唯一差异是 site.lcf 的位置请求以及不加载的 site_reference.pcf 对照文本。两侧均正确注册 FDC 和 LCF；工程的 post-map PCF 登记指向本侧新生成的 `device_map/map03_twoff_probe.pcf`，不是预填约束文件。所有输入哈希见 evidence/prepared_hashes.json。

功能为正边沿 `q0 <= d; q1 <= old(q0)`。两级 GTP_DFF_CE 均 syn_noprune=1、CE=1、C=rst（高有效异步清零）、INIT=0、GRS_EN=TRUE。vendor 模型中的内部 RS 是 GRSNET 取反，RS 异步恢复 INIT。q0/q1 都是此微型功能设计的正常 primary outputs，避免未使用裁剪；没有 dummy load、keep buffer、时钟门控改动或时序放宽。clk 周期 7.619 ns，沿用 map02 最快根时钟周期。check.py 从实际 RTL 提取两级接线，对照固定 vendor 模型哈希，检查二态转换和全部 6 拍二进制输入序列；这是初步防错检查，不是 HDL 仿真、CDC 模拟、时序或 physical PASS。

器件注册为 `Logos2 / PG2L100H / -6 / FBG484`。Tcl 的 set_arch 完整写出 family/device/speedgrade/package；compile 使用官方 top_module；综合使用已见 ADS/selected_syn_tool_opt=2；map 使用本地已见 input_db_file，官方 override_pcf=true、devmap_remove_dups=0、devmap_const_prop=0、devmap_control_set_num=0。不猜测未知选项，也不声明项目/Tcl 已通过当前 PDS 解析。

## 位置约束的边界

官方依据是同级 physical_pack_control_reference01 的 help_2/help_4/help_5.html，以及 actual_routed_register_sites.json；原 evidence/official_site_probe_basis.json 保存了提取和哈希。真实历史 PLACE 样本为 CLMA_33_450、CLMA_45_462，均带 impl_devCQ0。它们证明器件上曾有这些实际位置；尚不证明 impl_devCQ0 可直接作为命令参数。

help_5 的 PAP_LOC 文档说明 LCF 属性在 map 转化为 PCF def_inst_site，形式如 `define_attribute {i:instance} {PAP_LOC} {CLMA_5_4:FGA}`。本候选依此写 `i:ff0/ff1` 和实际 site:impl；普通 GTP FF 识别、impl token 合法性、属性经 packing 传递、禁止合并效果都必须由实际日志与导出证明。文档对象通常为特殊可放置资源，不能据此承诺普通 FF 支持。

help_2 的物理命令是 `def_inst_site inst_name site_name [impl_name]`。site_reference.pcf 保留这个正确形式供审阅，不登记为 map 前输入。help_4 官方示例在 dev_map 后才 add_constraint PCF/RCF，不能推断 pre-map PCF 能识别逻辑 GTP。若仅 map 后加载/route 后位置不同，不能算 map 阶段成功，更不能算生产 map60 成功。不得使用 no_check、隐藏 export_fdc 日志、静默忽略缺失 target 或擅自改 impl 为 FGA。

## 未来实际序列（本次不执行）

stages.tcl 第一条有效命令无条件报 OFFLINE_ONLY，避免绕过队列；这里只提供可审模板，没有自动 runner/controller。未来由主 session 集成现有队列 controller，持有 single-PDS idle mutex 至进程及导出全部结束，确认 PDS GUI/shell 都 idle、map02 最终 FAIL/独立审计与队列前序条件已满足，禁止 duplicate launch。单进程串行执行，每一步检查完才进入下一步，使用两个新隔离目录，不清理或复用旧 DB。

1. baseline compile、site compile，分别保存实际日志、ADF/native DB 与 topology 导出，验证 ff0/ff1 的 Q、D、CLK、CE、C、INIT、GRS、Q0→D1 以及功能 primary outputs，target 缺失即 FAIL。
2. baseline synthesis、site synthesis，同样导出实际两级与控制语义；位置请求不得改变 RTL、控制连接或 timing。每份来源/产物记录 SHA256，保留原始 target 名与转化映射。
3. baseline unconstrained map、site 同源 map（LCF 已在 compile/syn 前登记，map 也登记并加载；相同 FDC/选项）。收集 map 完成日志、实际 ADF/native DB、CDB/topology、实际生成 PCF、`export_fdc -file device_map/actual_roundtrip.fdc` 的原始输出和日志。逐一验证原 i:ff0/ff1 到实际 mapped cells 的 binding、两个位置/impl 与 D/CLK/RS/Q 和 Q→D 邻接，INIT/GRS/CE/复位极性不得改变；不能仅比较 cell 数或抄参考 PCF。
4. 未知/无效 impl、target 不存在、约束被忽略、packing 后无法回绑、map 阶段不能起作用，都如实判此方法 FAIL。未执行或缺少日志/导出保持 PENDING，不填 physical PASS。若后续另做 post-map 布局验证，要另述作用阶段，不能改写这次 map 判据。

当前没有 compile/syn/map 日志、实际 PCF、CDB 或 export_fdc；所有 physical/target binding pending。即使 twoFF 方法最终有效，它也只证明 scope=method probe；仍需独立完整 60 个生产寄存器实验和最终证据。
