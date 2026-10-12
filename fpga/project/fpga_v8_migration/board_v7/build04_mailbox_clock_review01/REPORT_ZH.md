# build04 mailbox / KEEPBUF clock sink 外部只读核验

输出根仅为 `board_v7/build04_mailbox_clock_review01`。没有改 build04、build04_route_prepare01、冻结 producer/consumer 或其他 agent 文件；没有启动 PDS、远程、PnR、STA。所有 PASS 字样仅描述指定离线检查；`constraints_qualified=false`、`runtime_STA_passed=false`，物理执行 gate 仍关闭。

## 2048 位对应的真实集合

fresh resolve 对本次完整 synthesis graph/objects 重新运行，2048 位无 errors：1320 条 register resolution rows，728 条 constant_zero。每相机 register rows=330，真实 unique Q→D / CLK→D pairs=320；四相机 unique=1280。不能把1320条逻辑记录写作1320个物理pair。

`logical_to_physical_2048.json` 包含全部2048逻辑位、1280唯一物理对的反向logical列表、728零位及4个共享alias组。每相机相同的共享组为：

```
240, 480, 490, 494, 497, 498, 502, 504, 505, 508, 510
```

其中240=word7 bit16；其余10位=word15 `32'h53464401` 的10个置1位。它们都指向**本相机** `mailbox[240]/Q -> host_bank[240]/D`，11条logical记录共享1对，增加10条重复logical alias；四相机合计40。四个camera共享组的source/capture/clock均属于各自作用域，不是相邻camera串链。1280条 source Q 网逐条检查完整netpins恰好为 `{source Q, receiver D}`。

这11位不是可无条件折为constant_one：RTL reset `mailbox<=0`，在 `edge_vs && armed && !busy` 的同一成功snapshot分支，word7 bit16赋 `1'b1`，word15赋magic word；其他时候保持。11位具有相同“reset为0、写入为1、保持”的轨迹。host_bank同一host clock/reset/acquire分支逐位采样这些相等值，因而也具有相同轨迹。`rtl_field_alias_contract.json` 保存完整控制组合的单步归纳和RTL行号。

word0..14有效宽度依次为 `32,24,16,16,24,24,24,24,24,24,24,16,8,16,24`。这些字段高位补零合计160位/camera；word15另有22个零位，总182位/camera=728。逐位零集合与fresh LUT-cone穷举manifest精确相等，既没有给728补寄存器，也没有假造40个pair。

`analysis/manifest.json` 保留2048个read-word/bit cone的support、所有support赋值穷举结果、实际sender/receiver和共享LUT-output证明。`complete_mailbox_primitives_netpins.json` 保存完整1280 sender+receiver primitive记录及port→net引用，`complete_connected_nets_synthesis.json` 按唯一net保存**完整**netpins/aliases，避免重复嵌入同一个高扇出clock网。

## 原始ADIF及mapped边界

`independent_adif_check.py` 不导入既有parser，以原始ADIF字节读取CELL/PORT/INSTANCE/CONNECT，独立构建完整hierarchical pin等价类，再与全部primitive和connected pin集合比较。`independent_raw_actual.json`、`independent_raw_compile.json`、`independent_raw_mapping60_01_mapping.json` 是实际执行结果，必须与 `final_review_receipt.json` 一起审阅。原始byte-offset/节点证据在 `raw_*_nodes.json`，均绑定原始dump SHA256；重复位独立cell在实际syn/mapped原始ADIF中不存在。

mapped graph实际有 `/opit_0` 和 `opit_0_L6Q` 等新primitive名，部分source Q由LUT+Q打包输出驱动。`mapped_1280_connectivity.json` 通过实际mailbox alias-net、唯一output driver和实际receiver D建立对应，保存真实mapped primitive/ports/网。它只证明连接，不批准gopQ/gopLUT6Q的储存、reset或clock语义；完整60端点、mapped模型语义和clock identity签核由其他agent承担。本核验不会把既有mapping FAIL提升成PASS。

## build01 → build04变化

build01绑定的actual manifest确有1320唯一对。`build01_mapping_diff.json` 逐位保存新旧映射、消失/新增pair；`build01_duplicate_original_primitives.json` 和 `complete_connected_nets_build01.json` 保存旧11组lane的真实primitive/port/net。实际变化是每相机word15的10个独立pair合并到已经存在的bit240 pair，即40对消失，无补造。

`build01_equal_lane_structural_proof.json` 进一步逐组验证：旧11个mailbox cell的D全部为同一个constant1网，CLK/C/CE及default参数完全相同；旧11个host cell的CLK/C/CE/default参数完全相同，11个D来自上述相等mailbox lane。旧图已经具备相同值轨迹，新图把它们共享到一对真实寄存器。

`build01_to_source03_boolean.diff` 保存RTL全量差异：计数clear表达式改为boolean、gap模块改为boolean最终门、同步/reset链显式primitive等；mailbox字段赋值/位布局本身没改。本次build04的candidate RTL与source03 boolean版本逐字节相同。相同轨迹允许优化合并，这是结构变化的根因；不能仅凭导出图断言编译器内部哪条优化heuristic或某一项RTL重写单独触发了合并。

`final_review_receipt.json` 复验原manifest的741 local hashes和186 registered sources；`source_identity.json` 另验证full-source-copy表的742条真实hash。742是另一张完整复制表的entry数，不冒充741候选登记数，也没有修改原manifest。

## KEEPBUF类型/端口与实际derive

官方安装模型 `arch/lib/bms/verilog/bmsPrim.v` 的 `bmsKEEPBUF`：integer WIDTH、vector I/Z、`assign Z = I`；没有storage/enable/inversion。截取字节及模型绑定见 `official_bmsKEEPBUF_model.v` 与input ledger。原始ADIF Cell specialization的WIDTH和精确I/Z schema是实际参数，Cell编号**不等于WIDTH**。

新adapter只对白名单中本次实测specialization验证精确WIDTH及全部port schema；clock traversal新增支持仅限 `bmsKEEPBUF_Cell_1 / WIDTH=1`。原data identity支持的vector lanes保留并加强为同样严格schema；未知类型/参数、错误WIDTH、额外control、方向或clock/state接口改变均FAIL。`identity_counterexamples.json` 保存真实执行的8个反例，包括未知clock sink。

阻断中的 `ND12` 与 `ov5640_top/ov5640/ND18` 实测 `I[0]` 在camera1 clock网，而 `Z[0]` 在pin_net和完整netpins中均没有连接。这是identity primitive的无下游输出终点，具有KEEP/DEBUG属性，不是storage clock sink。新adapter明确记录 `identity_terminal_no_output_net_no_storage`，不把它当作storage、不删除unknown leaf、不添加false path。其余camera对应terminal同样逐个记录在 `keepbuf_clock_details.json` 和coverageproof。若Z有实际网则沿真实网继续遍历，并拒绝额外output driver。

新副本 `analysis/derive_new_constraints.py` 与原prepare derive字节相同，330/camera和1320 gate均未改。最早外部attempt因新增adapter遗漏原vector支持失败，原样日志保留；补齐严格vector schema、显式处理已证明identity terminal后，fresh derive抵达并实际拒绝 `legacy 320/camera (1280 total)`，见最后一次 `fresh_derive_frozen_gate_attempt*.log`。没有让被冻结gate接受1280。

`review_mailbox.py` 的独立诊断分支根据实测2048共享映射计算完整 `diagnostic_constraint_DRAFT/clock.fdc` 与coverageproof。它没有更新任何candidate acceptance expectation，仅生成待独立review草案。

## 约束草案的精确不变量

`constraint_draft_exact_audit.json` 独立复算并验证380条新增命令的完整列表：364条原U-B有向clock关系，以及每相机3条数据/补集命令+1条已有ACK-first精确例外。U=368，只刻出4个camera→DDR关系；没有新clock-pair falsepath、没有同域clock-pair falsepath。原全部create_clock/create_generated_clock、uncertainty及DDR multicycle等32条命令保持原字节内容。

预算固定 `set_max_delay -datapath_only 15.238`，保留原精确hold数据例外与ACK-first集合。DDR从free_clk 40ns和84/16计算得到131.25MHz。对每相机，补集实际为 `(compile_leaves - compile_mailbox) ∪ (synthesis_leaves - physical_launch_CLK)`，穷尽并拒绝unknown sink：

| camera | compile leaves | syn leaves | compile mailbox CLK | unique syn pairs | 精确补集 |
|---|---:|---:|---:|---:|---:|
| 0 | 227 | 1068 | 17 | 320 | 836 |
| 1 | 227 | 1068 | 17 | 320 | 836 |
| 2 | 229 | 1075 | 17 | 320 | 844 |
| 3 | 229 | 1075 | 17 | 320 | 844 |

本草案是compile/synthesis逻辑图的完整replacement clock，不是已在mapped DB中加载成功的FDC。原clock不能先加载再叠加此草案，因为旧asynchronous groups会覆盖预算。PnR准备必须结合实际mapped pin对应及另一agent的clock/endpoint语义复核，再证明vendor loader/reload确实把旧CDB例外替换且未重compile/syn/map；本任务未授权工具执行，故这里没有runtimeSTA或reload PASS。

## 明确有限阻塞与交接

1280 unique在本次图及RTL合同中属于合法同值优化，仍需主独立审阅以**新candidate**单独更新期望。原producer/consumer1320 gate保持关闭，不自动改数字，旧1320 path报告不能继承。

后续真实routed图必须重新建立2048映射和真实1280物理集合，并取得1280×Slow/Fast=2560条有分数的精确pair报告，逐pair证明真实 `MaxDelay Path 15.238` exception和corner。报告pair集合必须与实际routed集合精确相等，不能用from/to笛卡尔积混入交叉pair，也不能把11个logical alias重复计为11条物理path；再以共享合同展开覆盖全部1320 register逻辑位，另以728零位证明覆盖全部2048。

mapping语义、完整端点、IO bank、全局STA、真实PnR timing reload仍是各自gate，不因mailbox/KEEPBUF离线核验解除。本目录交付可用于新PnR准备的完整逐位合同、图/模型/hash证据和约束草案；没有可运行的PnR/remote入口。
