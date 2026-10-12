# build04 mailbox / clock 独立审阅02

结论：本候选离线核验全部通过，接受绑定 source_candidate04 原始字节与实际图的 1280 唯一物理 pair 身份，交付新的 candidate-specific expectation contract。旧 1320 gate 未修改，实际重跑仍拒绝1280；旧1320报告不可继承。未启动PDS、PnR或板操作。mapped60官方行为由另一agent负责，本报告不重复签核。

58个封存产物逐文件重算SHA256（目录共60文件，另2个是封存账本）；中间账本55项也全部复验。原manifest的741 local hashes、186注册source、742 full-source-copy项、775 input bindings和prepare fresh图绑定逐项核对。实际CMR的186 source输入与manifest路径及顺序完全相等，另含15个IP IDF；编译后PDS实际为185个source加1个CMR入口替换顶层RTL，已单独核对封存，不将其混报成186 RTL直接入口。证据见 artifact58_rehash.json、source741_registered186_rehash.json、registered186_actual_CMR_binding.json。结束再次核对旧58文件及741/775输入未变。

fresh resolve重新穷举2048个read cone并与原manifest逐字段相等。独立集合计算确认2048=1320逻辑寄存器记录+728精确零；1320=1280唯一物理pair+40共享alias；每camera320。所有实际source Q网完整pin集合恰为{Q,D}，无跨camera。四个11位组精确为240及magic 53464401的10个置1位；240是word7 bit16。没有把这些顺序状态当恒1。

共享轨迹证明绑定实际RTL全文哈希与原始/build01完全相同的16条mailbox字段赋值。32个完整mailbox控制组合及128个host控制组合做单步归纳：共同reset0、成功snapshot写1、否则hold；host同reset/acquire采样。182零/camera亦reset0/write0/hold0。新增仿真用官方GTP模型，四camera各40000周期，246899次观察，逐次比较实际build04、build01及原始模型的全部512 mailbox、512 host位和总线输出，均一致；见 cycle_simulation.log、sharedlaneRTL_contract.json。另重跑实际build01/build04计数器524288、gap1048576个完整16bit状态/控制转移，含prefix/next_q检查均通过，见 boolean_exhaustive.log。仿真是有限轨迹，共享/零覆盖另由归纳和fresh read-cone穷举证明。

原始ADIF字节reader独立于生产graph parser，重新展开compile/synthesis/mapped全部primitive连接类，逐pin与完整图比较。额外对build01原始ADIF全部连接类复验；四阶段另外逐cell核对原始leaf type与完整port name集合，防止连接相同但类型错误。旧11条独立mailbox有同D=1、CLK/C/CE/default参数，host同控制并各自连接旧Q，精确40旧pair消失且没有新增pair。见 independent_raw_*.json、independent_build01_raw_and_trajectory.json；mapped仅复验连接，不作官方storage模型签核。

KEEPBUF核对安装官方模型原字节assign Z=I，无storage；另从原compile ADIF提取14个实际specialization完整CELL字节、offset、hash与WIDTH/I/Z精确schema，Cell编号不视为WIDTH。fresh adapter保留严格vector数据支持，clock新增仅Cell_1/WIDTH1。8个恶意类型/schema/control/unknown-sink反例重新执行全部拒绝。所有无输出终点在pin_net及完整netpins确无Z连接，明确记录no-storage终点，不删除未知sink。见 independent_KEEPBUF_raw_schema.json、fresh_keepbuf_counterexamples8.json。

fresh compile/synthesis clock traversal与原coverageproof完整相等；独立重建实际补集，camera0/1=836、camera2/3=844，预算launch不在补集中。原368有向关系仅刻4条camera→DDR，保留364；新增380条命令逐条精确相等，15.238ns/DDR131.25MHz固定；原create_clock/create_generated_clock/uncertainty/DDR multicycle32条保持字节。无新增同域falsepath。见 fresh_clock_exact_audit.json。

candidate_specific_expectation_contract.json绑定本真实source/graph和独立证明hash，要求后续新producer/consumer显式绑定合同hash；fresh route必须从原始图独立重建相同2048语义集合、728零集合、四共享组、实际1280及320/camera，否则拒绝。要求独立routed1280 pair×Slow/Fast精确2560条有分数记录，每pair为真实MaxDelay Path15.238；拒绝缺失、多余、重复、笛卡尔积、hash/count/semantic mismatch及旧1320报告。保留原预算及精确hold/ACK例外，不提供any_count策略。

这是新候选身份限定的物理期望合同，不是旧条件修改。constraints_qualified=false、runtime_STA_passed=false。实际route、vendor timing replacement/no-remap、mapped60官方行为、IO/full STA仍需各自证据；本离线通过不解除它们。新合同SHA256及证据hash见decision_ZH.json和review02_hashes.json。
