# build03 完整本地物理 runtime 与串行启动交接

最新实际状态：**BLOCKED，controller PID 20616 已退出，未启动 build03 PDS**。map02 最终实际mapping为FAIL：compile/synthesis各60独立端点（28sync/32reset），mapping仅4独立端点（4sync/0reset），不满足门禁。最终结果SHA256=`b1acda6eed22d63e2ef74d610aeb7f3d8d983e37a9c137dbfc7e7c1dbe66bef7`。build03门禁正确拒绝，`evidence/runtime/blocked_reason.json`与`failure.txt`保留原因；只有controller_launch记录，无工具launch及compile/synthesis/device_map/place_route/generate_bitstream目录。以下PENDING/等待描述为启动时历史，不能代表最新状态。未重启、未绕过门禁、未修改map02或冻结runtime，未生成bit或accepted=true。继续真实构建须先解决上游mapping失败并取得满足全部独立审计条件的新实际最终PASS。

源候选状态 **PLANNED**；完整 runtime **EXECUTABLE_SEALED_LOCAL_ONLY**，不再是 prepare stub。独立源 manifest 保留原封存字节，其中历史 `runtime_port_status` 不覆盖新增的真实 `evidence/runtime/runtime_port_status.json`。本次用户已授权本地 compile/synthesis/map/PNR/STA/bit；controller不执行远程、SRAM、设备或主 consumer 验收。

已启动唯一等待控制器：**PID 20616**，父 PID 46932，命令 `python -u controller03.py --run`，工作目录为本 build03 的 `runtime`。启动事实见 `evidence/runtime/controller_launch.json`；controller SHA256=`b0241833ce451381f190609f60a5beae8cfaaff4d2a47a28bb0d7d3ab594dd4c`；新版冻结 ledger SHA256=`5f169df70fd54f1bba07f5e6582aae2407407f49c9ac503c3d38b82b8b6ec662`。schema修订前已实际确认旧PID53384仍PENDING、无工具launch/compile/synthesis目录，只停止自身等待进程。旧queue/ledger/launch与审计归档于 `evidence/runtime_revisions/schema_sync_pairs_4246ba1c59c1/`，未触碰map02/PDS/前序进程。报告撰写时真实 map02 final_result 尚不存在，门禁 **PENDING**，未启动 build03 PDS。实际进度以 `controller_status.json`、`queue_build03.json`、各 stage launch/result/log 和实际 ADF/native DB为准，不以本报告静态状态代替结果。

## 独立输入与源摘要

根：`C:\Users\NineSun\Desktop\ov56401\project\fpga_v8_migration\board_v7\source_diagnostics_timing_build_03`。741份 RTL/IP/inputs实际hash、186项 RTL登记均保留；源集合摘要=`b931125ce79f7baa27382f971c270317713c6bad6408f5d86b92af2aae52034b`。`sourcehash.json`、`source03hash.json`和原manifest未因 runtime port改写。runtime冻结29份代码/本地解析库/小型baseline资料；不复制旧物理graph、DB或GB trace。

相对 build02 恰好三项 RTL delta，738文件相同：

| 路径 | build03 SHA256 | 意义 |
|---|---|---|
| rtl/ov5640_cdc_tc04.v | `9e4e186a43b04c2a5a446c0d7a78fbfe9beb75f3e339d22d7d160cea0b3f2625` | regression03/src actual module byte-identical |
| rtl/v7_sfd_candidate.v | `dd4f6327633ce7f634d71139cd92fbafdce11e2fee5780f940e476540e5b741b` | regression03 boolean actual module + 11个primitive-only noprune |
| rtl/v7_sdt_bus.v | `08822426617f6b77b76780d159808798c0b11843bc1fefb3f21a6c9b6529b292` | build02 explicitprimitive bus + 4个primitive-only noprune |

15个属性只贴GTP_DFF_CE/PE实例，四相机预期60端点（28 CE/32 PE）。诊断源去掉属性后hash=`e4dd36babf9d42eab0bdd318f5b0b418df8e0a3d01cad9ba3103c4546a85f500`，与regression03/src一致；bus逆变换回build02原字节。map02旧counter/gap逻辑未被覆盖到build03。camera/control/lease三项原时序优化与actual top hash均重新核对。

regression03实际两侧243 compiled RTL/IP/model已重新逐份hash，241相同、2delta；功能回归PASS和整体外部保护冻结FAIL分别保留。186登记中76项处于实际仿真闭包，全部与actual candidate一致（primitive属性逆变换）；110项不在仿真闭包，保持build02 frozen bytes，不能宣称也经过该仿真。登记模块188、duplicate=0。

本地 `project.pds`从封存template生成，186个源与6个 `constraints_live`登记均为build03 root内相对路径；未来stage输出只登记本地路径。project_guard不允许绝对/`..`路径、旧constraints_pending/template或旧variant源绑定。192项实际工程输入绝对路径在启动ledger的project记录中。

741冻结输入的绝对引用共379行/16文件，完整保留于 `evidence/absolute_path_inventory.json`。历史生成日志/仿真脚本/patch脚本和INIT_FILE未漏报。登记PCIE RAM源中的E盘INIT_FILE常量实际下级 `.c_INIT_FILE("NONE")`；不消费旧E盘文件。其余辅助仿真绝对路径未作为当前PDS源登记。生产/IP和旧冻结字节不改。

## 硬绑定解决与本地库

已逐项处理原 `evidence/runtime_port_hardbindings.json` 中的工作绑定：

- controller03、preflight、physical_flow、constraints、evidence、ledger和candidate_id全部绑定自身解析得到的build03 root。frozen_guard核验本地741源、source03 digest及186登记，不调用旧build02 PREP/frozen_guard，也不从旧variant读取运行RTL。
- 原map01 gate改为map02最终actual mapping+independent_audit_result；run/audit_final/endpoint_logic纯函数复制成本地libraries并hash绑定，运行时不动态导入旧run/controller、不写旧evidence。
- 原BASE/ORIGIN/generator动态执行与dead legacy derive均移除。clock XML、全局raw STA、summary、endpoint cone evaluator和truth reference均是本地冻结库。baseline只复制clock interaction、IO表、小型HSST参考和1022保护hash，供不变量比较，不能代替新graph。
- 原routed truth reference保留原字节hash，作为本地 `.txt`。只AST执行十个纯函数与2048bit循环；旧文件的global graph读取、review写入、SRL相关全局主流程都不执行。
- verify_identity_adapter中的build01读路径仅用于明确标记的只读校准；读取前后hash相同，不能作为build03 stage或signoff。实际构建只消费本次fresh exports。
- delivery producer改为candidate03及本地AUDIT库角色；主assembler/consumer/routed_connection只作为真实audit source路径，producer不导入、运行或修改它们。各来源hash见runtime_port provenance。

## 真实mapping门禁与队列

门禁要求map02最终status=PASS、all_verified_checks_passed=true、独立auditor/dependency hash与当前文件一致、三个实际stage均60/28/32、真实dev_map三个整数0选项有日志证明。重新读取每个stage的ADF/nativeDB、official done、result/log、dump/graph export hash、真实源/active/mapping输入guard，并用本地pure checker重算全部端点与INIT/GRS/异步极性/前驱/clock root/PAP_NOPRUNE。最后只比对两候选的primitive实例参数接线及属性作用域，不把map02旧功能逻辑强行整文件等同于build03。

PENDING不占用PDS mutex且不启动工具；FAIL/审计或hash失败写blocked_reason并退出，保留真实原因。map02背景guard和脚本未改。controller03命令使用runtime工作目录下的basename，避免map02把依赖自己的等待进程当成全限定board_v7前序executor而造成反向等待；工具启动时仍采用全部绝对本地project/workdir路径。

唯一controller mutex=`Global\ov56401_build03_controller`。等待所有实际prior controller/finisher生命周期、GUI/PDS/TA结束；只排除自身、父launcher和显式等待自身的观察者。全部空闲且门禁PASS后获取已有全局 `Global\ov56401_PDS_single_instance`，再次核验空闲、ledger与门禁。每次工具启动前再验保护hash和mapgate。

## 新图约束与签核

初始clock为冻结logical clock输入，非旧physical叶名字。已修复本地派生器对实际FDC前导空格的解析漏洞：20clocks、16groups形成完整368 U；仅四camera→DDR划出后保留364 U-B。冻结源约束字节未改。

真正compile/synthesis必须fresh且official done，保留shell/nativeDB错误扫描及stage snapshot。实际导出并重新解析2048logical bits，目标1320唯一mailbox对（330/camera）与728zero；完整clocks/ACK首级、16对same-domain后级和camera complements动态推导，四预算15.238ns。legacy1280、old leaf fallback和缺图不会放行。

dev_map采用真实map02受验API：明确input_db_file和constraints上下文、force_to_run、devmap_remove_dups/const_prop/control_set_num三个整数0。mapping后fresh重新导出compile/synthesis/mapped图，重证大工程actual60端点与INIT/GRS/极性/前驱/clockroot/属性；重新派生约束必须字节相同，否则阻止PNR。U-B同时要求actual clock interaction保留已连接关系与本次ADIF CDB完整364双SU/HD、四条15238ps datapath预算，以及每个complement叶的真实FDC/CDB来源。

PNR后首先fresh导出全局raw STA、负slack逐路径明细、十组Slow/Fast summaries、motion32 DRM36K、HSST sites/dedicated links和IO112。随后重新证明routed2048truth、1320唯一物理Q-D及CLKROUTE identity parameters、camera clock完整叶集合、严格等价clone和日志证明的dangling清理；大工程routed60独立端点与reset32再次审计，并证明routed364 CDB/complement继承。

targeted query使用真实physical -from/-to和min_max，先单pair证明再21个有界mailbox batches；流式parser在每个Slack结束记录，识别actual max/min slow/fast suffix、Recovery/Removal/MPW/Setup/Hold。mailbox需双角1320覆盖、15.238预算且slack非负；reset32 Recovery/Removal与MPW双角覆盖；16对same-domain后级分别验证Setup/Hold双角覆盖。所有未知/忽略选项、属性、phaseDB错误都拒绝，并保留stageDB及unknownoption日志。

任何全局或target/routed门禁失败，不生成bit；全局实际timing结果先保存，供主修复。全部实际signoff通过后才gen_bit_stream，验证官方完成、fresh vendor envelope、device/top/compiler、route/input不变以及唯一实际.sbit选择；不得用bits[0]或重命名wrapper冒充。producer只生成真实 `delivery_sources.json`、actual_result和accepted=false/reviewer=null审阅请求，不制造acceptance true，也不调用设备工具。

## 已完成离线核验

`runtime/controller03.py --prepare`已完成runtime pycompile、741/186/192实际输入/hash/root审计、producer audit-role schema及门禁negative检查。真实旧routed校准重新算出2048=1320register+728zero、12个日志清理叶、1个双clone与1条identity路径；packed独立60仍预期FAIL。所有校准都标明build03_physical_pass=false。Synthetic输入只用于PENDING/FAIL/syn-only/missing-independent、unknown-option/phaseDB、残缺timing记录、假bit和缺失delivery artifact拒绝，不生成任何正面物理证明。

主consumer目前两版本限制及ALLOWED_BUILDS扩展仍需主单独review，用户授权已覆盖实现；本子任务未改主consumer。producerAUDIT角色已包括主 `routed_connection.py` 和其余六个required roles。独立主验收后才能形成validatedDelivery并执行授权的设备步骤；本controller止于本地bit和真实source descriptor。

最新主 `CONSUMER_TARGET_REPORT.md` 已完整读取。producer已新增强制 artifact `sync_pairs`，精确绑定实际 `EVIDENCE/sync_bindings.json`，不制造新的pair。新增五个独立AUDIT角色：endpoint_recompute→主goal的endpoint_recompute.py；endpoint_graph→本地analysis_tools/graph_adapter.py；endpoint_logic→本地libraries/endpoint_logic.py；endpoint_parameters→本地libraries/endpoint_detail.py；endpoint_checker→本地libraries/endpoints.py。原角色保留，不能用graph_adapter/physical_flow角色替代新角色。request的audit_sha256遍历完整audit_sources，artifact_sha256遍历全部真实sources，因此新角色与sync_pairs一起参与主独立acceptance完整hash绑定，仍accepted=false/reviewer=null。

新版离线检查从当前主assembler AST提取全部ARTIFACTS与包含 `*ENDPOINT_ROLES` 的AUDIT_ROLES，核对新helper的实际ROLES、所有准确本地路径及生产artifact表达式；只读取schema定义，不导入主controller或执行accepted构造。首轮检查因旧literal_eval不支持主新版starred set拒绝，失败日志已原样归档；修复本地安全AST展开后，全部pycompile/offline/schema/拒绝检查与实际2048校准重跑PASS。741源、186登记、source03hash及controller代码hash不变，只producer与offline schema检查改变。主consumer/assembler/helper未覆盖，当前实际MPW/sync16/independent60仍须新图/raw真实验证，不因准备检查通过而放行。

工具证据位置：`evidence/runtime/controller_launch.json`、`runtime_hash_append.json`、`offline_runtime_checks.json`、`identity_adapter_review.json`、`queue_build03.json`、`map02_launch_gate.json`、各 `<stage>_launch.json/_process.json/_result.json/.log`、`failure.txt/blocked_reason.json`。每次工具记录controller PID、实际工具PID、command SHA256、launch SHA256和ledger SHA256。不要重新运行prepare重置冻结ledger或覆盖失败artifact。
