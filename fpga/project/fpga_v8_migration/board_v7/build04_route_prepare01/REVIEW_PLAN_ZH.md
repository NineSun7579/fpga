# build04 后续 PNR / 全签核 / bit producer 准备（仅草案）

准备根：`C:/Users/NineSun/Desktop/ov56401/project/fpga_v8_migration/board_v7/build04_route_prepare01`。
所有本次写入均在此新目录；没有 import 原 controller/preflight，没有启动 PDS/TA/GUI，也没有设备操作。`bound_reused_scripts_and_evidence.json` 绑定实际读取的 build03/build04 runtime、基线、约束、映射证据、官方文档 SHA256；`additional_dependency_binding.json` 补充离线依赖。不得以准备结果代替 mapping、PNR 或签核 PASS。

## 1. 实际状态与必须保持的 gate

用户提供状态是 mapping export 在运行。只读查看时生产器已写 `source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/final_result.json`：**FAIL**，不是 mappingPASS。compile/synth60 的 `final_receipt_review.json` 为既有独立 PASS；映射工具 exit0/export exit0 不改变最终失败。`mapping60_01/FAILURE_DIAGNOSIS_ZH.md` 明确三种实际类型：gopQ 28、gopLUT6Q_Cell_139 12、gopQ_Cell_1 20，60位置可诊断性对应但 reset Q driver/语义证明未通过。不得改 checker 接受全部 gopQ 前缀，也不得重写 final_result 或把位置 PASS 升格为语义 PASS。任何后续合法 mapping60 PASS 必须有新的主审认可、绑定本次实际 DB 的精确 primitive 证明与独立审计；本草案不授权重map。

离线用 build04 **自己的** compile/actual graph + objects 重跑 resolve。`offline_fresh_synthesis/analysis/manifest.json` 是新解析结果，不是 build03 manifest。`actual_offline_inventory.json` 给出另一个硬阻断：2048逻辑位、无 resolve errors，每相机512条（330 register resolution rows +182 constant_zero），但去重 Q-D/CLK-D pairs 实际只有320，相机合计**1280**，不是1320。330条不等于330个独立物理对。必须保留1320唯一对的要求，不改为1280，不复制 build03 1320证据，不允许预算集合以重复条目凑数。若新导出证明结构改变，应使用新绑定图重新求解并主审；如果确实只有1280，需要单独明确需求/结构变更，不在本 producer 中放宽。

既有 derive 未成功。先遇到离线依赖缺失（两次失败原样保留），补充本地只写 prepare 的 preflight bridge 后 classify 成功。随后 derive 在 fresh compile graph 的 `ND12/I[0]`、`ov5640_top/ov5640/ND18/I[0]` 拒绝 `bmsKEEPBUF_Cell_1` 非clock sink：见 `offline_bridge_step1.log`。尚无新 clock.fdc，尚无合格 complement。即使证明 KEEPBUF 的精确非存储/透明语义，后面的唯一330/camera检查仍会因实测320失败。不能通过跳过 clock sink 或宽泛名字判断绕过。

IO 当前 gate 同样关闭：`diagnostic_io_bank_join02/REPORT.md` 为107/112实际连接，差分契约1/3；未闭合 mem_dqs[0/1]、mem_dqs_n[0/1]、sfp_tx_disable。原生IO-report及pinout都是 BANKL6=112，FuncName描述推导为L4=6/L5=27/L3=29/R5=28/R4=22，112/112冲突；internal_bank_metadata_verified=false、usedIO_internal_bank_objects_verified=false、IO_gate_passed=false。这些是旧诊断证据，不是 build04 新 route 证据；新 route 必须重新证明完整112连接、3差分契约、内部bank对象、VCCIO/IOSTANDARD/VREF/终端/驱动与PCB约束一致，解释实际矛盾。不得用FuncName替代内部bank，不得只复用原生112行相等就签核，不得豁免。

## 2. root/candidate guard 必须移植的有限范围

新 producer 候选标识建议 `build04_route_prepare01`，实际只写新执行子目录 `execution01`；输入身份另记 `source_candidate_id=source_diagnostics_timing_build_04`、`mapping_attempt_id=mapping60_01`。执行子目录只在主审批准准备产物后建立，禁止把 HERE 指回 build04。

| 原 runtime | 已核实差别 / 外部移植要求 |
| --- | --- |
| build03 preflight.py/controller03.py | HERE/DATA/root/candidate_id、source03hash、manifest741、186工程登记、runtime_hash_append/offline_checks/identity_calibration、map02 gate 均绑定build03；不得原样import或修改原map02FAIL gate。新 preflight 单独绑定build04 immutable manifest/source04hash及完整源复制hash，另绑定 mapping60 独立PASS，不用map02替代或改其状态。 |
| physical_flow.py | protected()导入controller03并要求map02 PASS；run()只准build03-local；derive()写constraints_live；stage()会重compile/synth/map。新工具runner只准execution01，导入自己的guard，显式DB/约束，禁止compile/synth/dev_map，保留全日志/native errors/fresh artifacts/input unchanged与互斥。 |
| build04 controller04.py / flow04.py | scope仅compile/synth/export60；manifest immutable_hashes含constraints_live/runtime，tool cwd必须build04；实际 export resolve=False。不得修改白名单，不得往其constraints_live写新clock，不得触全树运行guard。仅复用算法，外部复制/端点依赖不导入controller04。 |
| mapping60 run_mapping60.py | 保护build03全树、map02全树及build04除当前mapping证据的完整集合；mapping内部project.pds只是原project字节复制，不能作为外部PNR项目（相对rtl/inputs无对应树）。不得往isolated_mapping_work写新clock、pnr或bit。 |
| graph_adapter.py / derive_new_constraints.py | 纯算法优先逐字节复用；只有精确 KEEPBUF/operator证明、实际映射类型语义支持可以提请局部修改。未知sink、唯一pairs、同域链/reset语义约束保持；1320阻断不修改。 |
| routed_acceptance.py | 读取actual_post_constraints/analysis、dev_map.log、pnr.log与coverageproof_synthesis；要显式映射到build04 fresh synthesis/mapping receipt/log，不能创建虚假的dev_map.log或伪称post_constraints synth。truth reference只能作为绑定算法参考；新的对象/图/manifest必须来自build04。 |
| global_audit.py + libraries | summarize_route.HERE通过preflight绑定evidence/runtime；raw_audit导入run_route保护桥与baseline_data/hsst_phy。新桥仅写execution01；复制绑定的真实baseline只比较IO/HSST物理恒等，不当作新图。global IO112 equality需增加full bank gate（上节）。 |
| targeted_reports.py | 物理过滤/stream parser/batch规则保留，项目标签timing03改独立标签；同一个route hash贯穿。最大21批1320对；首个单pair必须双方corner和15.238真实exception证明。 |
| prepare_local_delivery.py | HERE、candidate_id、actual_post_constraints路径、bit cwd、source_descriptor全改新候选；用显式route DB bitgen代替project -run。accepted/reviewer字段保持待独立主审，禁止自动烧录或调用program工具。 |

新guard需要冻结：build03/map02全树（不改失败事实）、build04已结束后完整全树、生产RTL/IP/protected1022、build04 manifest的741/186与full source hashes、PDS及官方models；记录copy source→destination SHA。当前若controller/watcher仍写证据，**不得冻结动态全树并抢跑**，只读等待其全部结束后新snapshot。前/后/每次工具启动及结束复验。运行时用 `python -B`，不往旧树生成pycache。复用与修改文件的新SHA和diff登记到新的ledger，原ledger一字不改。不要以sys.path猴补让旧模块指向新root。

有限主审项：①外部root/candidate/input-copy/receipt guard桥；②KEEPBUF精确operator与三种mapped storage的语义证明（当前不做放宽）；③mailbox唯一1320实际证据问题；④official timing reload/PCF导入能否保留mapped graph的验证；⑤IO full bank gate；⑥routed targeted/delivery路径与bit显式DB入口。所有修改都在外部新runtime，新hash重新sealed，不沿用build03 ledger。

## 3. 输入路径与不重map的条件分支

已存在真实输入（当前失败，只能诊断）：

```
board_v7/source_diagnostics_timing_build_04/compile/v7_sdt_top_comp.adf
board_v7/source_diagnostics_timing_build_04/compile/cmr.db
board_v7/source_diagnostics_timing_build_04/synthesize/v7_sdt_top_syn.adf
board_v7/source_diagnostics_timing_build_04/synthesize/snr.db
board_v7/source_diagnostics_timing_build_04/evidence/runtime/compile/analysis/graph.json
board_v7/source_diagnostics_timing_build_04/evidence/runtime/actual/analysis/{graph.json,objects.json}
board_v7/source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/isolated_mapping_work/device_map/{v7_sdt_top_map.adf,dmr.db,v7_sdt_top.pcf}
board_v7/source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/isolated_mapping_work/constraints/{clock.fdc,production60.lcf}
board_v7/source_diagnostics_timing_build_04/evidence/runtime/mapping60_01/mapping/analysis/graph.json
board_v7/production60_target_prepare01/{constraint_draft_binding.json,site_candidate_plan.json,production60_site_DRAFT.lcf}
```

实际PCF197行含def_port/def_inst_site等物理命令，没有clock/false_path/max_delay；不能靠它覆盖旧timing exception。未来 mapping60 独立PASS后，验证mapping_artifact/graph_binding/native_pcf_exact60_audit/endpoint_details/exact_clock_identity及独立receipt哈希，然后**完整复制**device_map原生树、compile/synthesize原生树及源/输入/原约束为execution01只读input副本（不得把ADF反导出合成一个新map替代），逐文件验证copy哈希；device_map树之外写所有新产物。

fresh graph derive要求：2048 exhaustive mailbox无errors、每相机330唯一Q-D对/总1320、exclusive Q-D、compile与synthesis clock leaf集合穷举，补集精确set difference；U=368，只刻出4个 camera→ddr，保留364有向关系，没有同域false path。保留所有原create_clock/create_generated_clock、uncertainty、DDR multicycle；DDR25*84/16=131.25MHz，15.238ns不得改为宽预算。ACK第一跳例外仅精确证明集合；同域后级16对必须实测Setup/Hold。只替换原一次set_clock_groups为新precise U-B关系，禁止加载旧clock后追加新false/max_delay叠加（旧异步group会压过15.238预算），禁止重复删clock或删除未知leaf。先输出外部完整replacement clock.fdc及proof，原逻辑clock完整归档。

## 4. 官方命令、约束加载和graph有效性的边界

官方证据：PDS安装 `doc/Pango_Design_Suite_User_Guide.pdf` PDF页166-167（书页165-166）说明 `-file` 精确脚本执行与 `-project -run pnr` 是“运行到”阶段，页248（书247）add_constraint文件；已有真实SP6.4 `whole_candidate_v3_timing_route_01/pnr_help.log` 确认 `pnr -input_db_file/-force_to_run/-optimize_multi_corner_timing/-fix_hold_violation`。显式bit DB命令有 `whole_candidate_v7_route_01/bitstream_01/bitgen.tcl` 先例。后续使用官方命令 `pds_shell.exe -file <tcl> -work_dir <external> -project_name v7_sdt_top`，不使用原build04 `-project -run pnr` 自动级联。

`commands/PNR_RELOAD_DRAFT.tcl` 是具体路径草案，开头error锁住，默认不能执行。主审确认 gate 后才由新producer生成不含锁的真实脚本。应新建空白shell工程/session，只登记replacement clock、5非clock FDC及实际mapped PCF；`pnr -force_to_run -input_db_file {execution01/inputs/device_map/v7_sdt_top_map.adf}` 明确从既有map输入，无dev_map命令，不再登记production60.lcf与PCF同时叠加同一位置（保留LCF哈希与PCF 60位置一致证明）。PCF中的60 def_inst_site用实际mapped cell匹配；路由后再证明不丢位置。

**这不是已证实的无重maptiming reload。** 官方help确认PNR显式DB输入，但未给出“更改FDC必定替换mapped ADF内旧CDB且不改变前序action”的承诺；旧map使用旧logical clock，所以不能仅说add_constraint就合格。本阶段禁止启动PDS，尚无法提供build04实测reload receipt。新producer必须将首轮外部PNR作为带严格拒绝条件的验证：shell实际执行日志不得出现compile/synthesize/dev_map或implicit prerequisite，原/copied compile/syn/map的hash和graph必须不变，新routed dump/CDB与原生clock interaction/clock summary证明旧4对全域异步不再覆盖mailbox、新364/precise complement存在、15.238真实MaxDelay exception、DDR131.25及同域关系未变；任何空集合、Timing-4006/STA-3016、ignored/unsupported/unresolved均拒绝。若PCF被拒绝、旧CDB无法替换、图名字不能解析、mapping前序被重新运行或mapped semantics发生变化，则无重map分支不成立，保留失败，停止bit链。

build03 controller03.py:125-126原来也是“post-map derive bytes不一致→拒绝PNR直到单独review remap”。这里逻辑clock→derived必然不同，不能套用其同字节通过条件，也不能删其guard。新外部producer只有**已实证官方PNR重新读timing而不变mapped graph**时允许新timing版本作为独立输入revision；否则必须主审另行授权从fresh synthesis按新clock/原60LCF重新dev_map，产生新的attempt与60独立证据；当前任务不授权重map。无需人为编辑/invalidating旧ADF，禁止load/save内部命令猜测或手改CDB来消除旧group。

## 5. 路由后签核顺序与拒绝条件

先保存PNR exit码、官方Place & Route done、fresh ADF/prr.db、全run.log/error/fatal与native messages；输入map/PCF/fdc hash前后不变。新route所有导出/report绑定同一ADF hash。

1. `.switch_db`导出新routed graph/verilog；全局 `report_timing -input_db_file <route> -force_to_run -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0 -input_pins TRUE -report_exception FALSE`。保存十组Setup/Hold/Recovery/Removal/Minimum Pulse Width ×Slow/Fast；每组非空、WNS>=0/TNS=0/failing_endpoints=0/端点数>0，排查report截断/未计分IO，不把没有path视作PASS。先保存失败全局报告再做targeted。
2. 新图重算60独立storage=28sync+32reset，D/Q/CE/reset/clock精确primitive语义、精确clock root identity、位置/PCF/PAP_LOC，不能接受只有60名字。routed clone/cleanup仅实际tool log绑定，无旧leaf whitelist删除。新CDB验证完整U-B/complement/预算。
3. mailbox1320唯一对，两corner每对有分数/exception=MaxDelay Path15.238，首pairfilter先证明，然后64对/批共21批；来自实际图的from/to集合、返回pair属于精确pair列表（from/to笛卡尔积不能混入交叉对），不漏不重。
4. reset32精确物理RS/P/C pins，Recovery/Removal Slow/Fast四格全覆盖；32reset CLK目标MPW Slow/Fast全覆盖；same-domain later-stage16 sync pairs Setup/Hold Slow/Fast四格全覆盖。filter unsupported/ignored/空报告/缺corner均FAIL。其余sync第一跳单独例外证明而非对28同步寄存器整体false path。
5. IO112完整bank gate（第1节）；HSST实际sites及专用连接与绑定baseline精确相等；motion32真实DRM36K history geometry/read_first/数据地址连接。任何gate失败均无bit，即使十组STA PASS也不能豁免IO或语义。

## 6. bit/manifest绑定

只有全部真实签核gate、input/guard复验后才运行单独bit shell：`gen_bit_stream -input_db_file {execution01/place_route/v7_sdt_top_pnr.adf} -force_to_run -create_bit_file TRUE`，外部bit_work目录，不走原工程级联。复验route hash不变、官方bit done、fresh非空实际vendor .sbit/header/top/v7_sdt_top/device/版本，不改名包装冒充；多个候选显式选择。

deliverySources/v1 manifest同时绑定：source04hash/741/186/full-tree、独立mapping60/native DB/PCF/60位置、map原clock revision、新replacement clock及derive proof/fresh compile/syn graphs/objects/mailbox manifest、reload证明、route/prr.db/graph/CDB、全部十组/targeted reports及shell/run/filter日志、IO full bank、HSST/motion、bit生成输入/日志/bit hash/bytes与执行过的新runtime ledger。candidate_id/build_root/source_candidate_id明确分开。`accepted=false/reviewer=null/board_verified=false`，主独立consumer复算后再接受；本producer不改主consumer、不写remote/device/Flash动作。

## 7. 当前可review产物与下一步

本目录包含SHA绑定清单、离线resolve manifest/classification、实际1280 vs1320重复对诊断、derive阻断原始日志、外部preflight bridge及锁住的官方PNR/STA/bit脚本。没有PNR输入副本和可运行的自动controller，避免在FAIL/未知reload条件下产生可误启动链。下一步主审应先解决mapping语义、KEEPBUF/1320和IO bank gate，再封外部runtime并授权真实工具验证；不能把此prepare目录标作PASS。
