# 当前物理实现实证

新增独立 exact11 最小修正已实施并启动实际 route03 compile；详细补丁、完整 U-B/compile 透明图覆盖、1022保护和实际运行说明见 EXACT11_CORRECTION.md。当前父控制器 run_exact11.py PID30184；只读汇总器已排队等待其退出。不得并发 PDS，不得修改正在运行的 route03 约束，不得以离线证明代替实际 PNR/十组/1320双角预算门禁。

最终验收证据：physical_exact_09/acceptance_gates.json 已落盘。IO112脚位、HSST站点及专用连接均与冻结V7基线相同，motion RAM为32个routed切片。原定向report_timing的from/to过滤未形成所期望的窄报告，实际产生262383条路径、峰值7122MB；随后reset查询内存失败。已对现有真实报告流式解析，未重启该大查询：两角各完整1320个mailbox物理对全部带MaxDelay Path 15.238ns -datapath_only，WNS Slow13.942ns/Fast14.450ns，routed opit_0实例与dump逐一核对。1280原等价类+40新增等价物理对证据完整。同步后级只覆盖4/16、reset只覆盖20/32，缺口由routed dump实证部分同步/reset链被映射为20个gopSRL实例造成；不可把缺失FF当作验收成功。已观察到reset Recovery -7.555ns。最终所有1022保护文件与local输入hash无漂移，routed hash一致。十组时序与新CDC门禁未通过，bit_permitted=false/bit_generated=false，无remote/program。已完成实际修正、综合、map、PNR到routed DB；后续需要来源明确的CDC/reset/SRL映射修复与再验收，不能直接bit或用扩大false_path消除问题。

最新 exact09：已实际成功 dev_map、导出新综合、解析全部逻辑位、推导1320物理对补集、分类CDC、PNR和 final_export。新综合校验再次证明1280原等价类/1320实际物理对/40重复等价，映射一致后才启动PNR。真实 routed DB=source_diagnostics_route_02/place_route/v7_sdt_top_pnr.adf，34860354 bytes，SHA256=4b19b478080da9b5306b5c8c4875387c80697b7059efd427ad8cfd0a1c7c0ee7。post_route_guard.json 核对1022保护文件与本次输入全部无漂移。

十组最终时序已实测不收敛：Slow Setup 1486失败端点/WNS -12.219ns、Fast Setup 604/-8.460ns；Slow Recovery 132/-8.393ns、Fast Recovery 132/-5.177ns。Hold/Removal/Minimum Pulse Width两角均零失败。2354负裕量路径已完整保存，negative_path_classification.json 分类指出相机FIFO第一同步级176条、新diagnostic第一同步级8条、raw camera debug跨域172条、其他setup1734条和recovery264条；不能扩大false_path掩盖raw crossing或reset恢复问题。bit门禁关闭。

audit_fixed.py 初次停止于错误旧HSST基线路径，已修为 project/motion_100h/run_20261003_212303/phy_audit.json。支持只读复用已有final_export，核对routed hash后继续。再次启动被另一个独立 synthesis_epoch10 PDS34812/80256、父Python26164挡住；已安排timeout0后台等待后运行完整HSST/IO/1320 mailbox/reset/sync定向验收，尚待结果。绝无remote/program。

最新：native08 map 后的新综合真实保留了 40 个先前合并的重复寄存器配对，总物理对变成 1320，而原配对等价类仍为 1280。不是解析 bug。canonical_equivalence_preflight.json 对全部 40 个新增对实证类型、初始参数、时钟、CE、reset 相同，capture D 连接对应等价 launch Q；全部 2048 逻辑位仍完整解析，无错误。finish_native08 在 len(pairs)==320 门禁处停止，未启动 PNR。resume_exact09.py 为新 attempt，约束全部 1320 个真实对且保留 1280 等价类证据，重 map 后重新导出/验证，再 PNR 和全门禁。其首次启动被另一个独立 match_epoch09 的 PDS 84476/81056、父 Python 62444 阻止，没有修改运行工程。已安排 timeout0 后台等待这些进程退出后运行 exact09。勿另启动冲突 PDS。

原 PDS 5372/79684 与控制器 40036 已自然退出。未杀进程。旧 standard05 的源码、FDC、工程、日志、compile/synthesize DB 已保留于 fixed_06/standard_05_archive，SHA256 清单为 fixed_06/standard_05_archive_hashes.json；第一次准备断言失败也独立留档。

standard_flow_fixed.pds 删除 cmd_devmap 的非法 top_module，保留 cmd_compile 的 top_module 和 rtl/v7_sdt_top.v 的 top 标记；当前工程没有字面 _top_module 属性。cmd_pnr 未含 top_module。手册第 250、252、253 页已读取，旧 whole_candidate_v7_route_01/impl.tcl 的裸 dev_map 已核对并留哈希。运行时 help dev_map 虽列 top_module，但设备 Flow-0182 实测拒绝该选项，不能依 help 列表重新加入。

fixed06 实际完成 compile 并生成新 synthesis DB，但 FDC 导入报 mailbox from_list 为空，未实际 map；不能依据 shell exit0 宣称成功。新 DB 已经通过 native_probe_07 两阶段只读导出，输入 DB hash 不变。

native_probe_07/compile_actual/analysis/graph.json 证明 RTL compile 中 mailbox 是 mailbox[31:0] 等 17 个向量寄存器/路，host_bank 是 host_bank[511:0]。新 synthesis 图则为实际标量 GTP_DFF_CE：四路各 320 对、共 1280 个唯一 mailbox-to-host-bank 配对；complement=748/748/755/755。解析、全部 2048 逻辑位的 LUT 恒等/常量解析、1280 对直接连接和补集拓扑检查均实际执行，无错误，证据在 native_probe_07/synthesize_actual/analysis/。

run_native_fixed08.py 已写好两个阶段的显式对象联合集合以及 synthesis scalar whitelist 检查，预算仍为 15.238ns，不使用扩大 CDC 例外的模糊 wildcard。启动尝试被单实例保护阻止，未写新工程、未启动 map：已存在另一个 run_query_epoch08.py 的 PDS 20440/compile 33540，父 Python 54832。它在独立 query_epoch08 工程中实测 FDC importer 查询。已安排 Wait-Process 等待自然退出；必须先读 query_epoch08/result.json，再据实测修正/运行 native08，不得猜测接口或宣称它已经执行。

native08 已实际运行成功：physical_fixed_native_08/dev_map_result.json 记录 Compile、Synthesize、Device Map 均 started/done，successfully mapped，exit0，errors=[]。真实 map DB 为 source_diagnostics_route_02/device_map/v7_sdt_top_map.adf，7456822 bytes，SHA256=7e6602a3ffafd83962835c60f3fba787ab539303e227122c004eff7b6c60d6be；post_map_guard.json 证实全部 1022 保护文件及本次所有输入均无漂移，map receipt hash 一致。run_native_fixed08 已退出；finish_native08.py 在后台导出新 synthesis DB，重新证明 1280 对/补集一致后再串行 PNR，随后调用本地验收门禁。

保护 build01_guard 1022 个文件已再次校验，全部 SHA256 不变。未写生产/旧 V7/IP。没有 remote/program。PNR、routed DB、十组时序、新 CDC 与 IO 尚未验收；bit 尚未生成。audit_fixed.py 是待执行的本地全门禁脚本，只有验收全部成功后才允许 gen_bit_stream。
