# Build03 功能输入绑定独立审查04

结论：**仅限定 scope 的功能输入绑定得到实证；不作总 PASS。regression03 原整体 freeze FAIL 保留，final signoff = PHYSICAL_GATE_PENDING。** 本次只读取既有源码、receipts、compile.f、compile/test logs 和 hierarchy；没有运行仿真、重算解压 22M trace、调用 PDS、远程或设备/DMA，也没有修改既有 runtime/source/IP/regression/consumer/controller、schema 或 contracts。知识服务不可连接，依据均来自实际文件。

## 一、四种数量不可混同

| 范围 | 实际关系及本次验证 |
|---|---|
| build03 冻结库存 741 | manifest.local_hashes 中 741 项当前 SHA256 全部匹配；库存含生产 RTL、IP wrapper/model、约束、备份、生成管理文件等。不是 741 个被仿真模块。source_set_sha256=`b931125ce79f7baa27382f971c270317713c6bad6408f5d86b92af2aae52034b`。 |
| 工程注册 RTL 186 | 全部为 .v、无 ipcore 路径；由 project.pds 的 .v 注册项核对。IP 通过工程其它机制及库存存在，不能用 186 代替所有 IP/model 输入。 |
| regression03 每版 compile-input 243 | 实际 compile.f 与 replacement_contract 对应项一致；两版合计 486 项当前 SHA256 全匹配。两版 241 项同字节，只有 ov5640_cdc_tc04.v、v7_sfd_candidate.v 的候选逻辑改变。 |
| 每版 14668 checks / 22663089 trace records | 原 simulation.log 两侧均有 TOP_FOUR_RESET_PASS checks=14668、四相机 reset 标记、Errors: 0；编译及 TB 日志无 Error/Fatal。22663089=6792+8323690+14332607，来自既有 results/audit 的三种 trace 比较记录，不是本次新跑样本，也不是 22663089 个不同功能断言。 |

每版 243 个输入与 build03 库存的对应是 **236 项同路径同字节 + 2 项属性逆变换精确还原 + 5 项 sim_views 精确复算**。236 中包含工程注册生产 RTL 68 项，另 168 项为额外 IP/wrapper/RTL/model 编译闭包；这不表示每项都实际 elaborated 或每项行为都被断言覆盖。

库存扩展名实计：.v 465、.vp 142、.fdc 35、无扩展名 32、.idf 16、.vhdl 16、.do 8、.txt 6、.f 6、.pds 4、.vh 3、.bat 3、.log 2、.py/.tcl/.sweep_backup 各1。备份、其它语言实现、约束和管理文件未在本次 ModelSim 闭包内是正常 scope 差别，不能因库存 hash 匹配就宣称已测。

## 二、186 项逐项绑定及 receipt 口径纠正

配套 JSON 的 `registered_row_partition` **完整且互斥覆盖原 registered_source_audit.json 的零基行号 0..185**。每个行号唯一绑定该行 `path`、`absolute_build03_path`、`sha256`，其顺序同时核对 manifest.registered_sources；原 receipt 文件 SHA256 在 JSON 中固定。各分类的匹配规则、实际编译目标和功能限制均写明，不能把未绑定项默认为已测。这种引用保留原始逐项来源与哈希，不改写 frozen receipt。

| 分类 | 行数 | 本次实证 |
|---|---:|---|
| DIRECT | 68 | build03/path 与 candidate/path 字节相同；该 candidate/path 真正在 compile.f；至少一个定义模块出现在实际 hierarchy。 |
| ATTRIBUTE | 2 | 183=v7_sdt_bus.v、184=v7_sfd_candidate.v；删除明确的新增属性后精确还原实际编译 candidate/rtl 文件；模块确实绑定。 |
| VIEW | 5 | 176..179 四个 PCIe RTL 与185 top；真实 compile.f 指向 sim_views 而非 raw/rtl；下节给出精确变换和哈希，两侧 raw 副本不是额外编译证据。 |
| COPIED_UNUSED | 1 | 80=inputs/source/npu/npu_cdc_top.v，副本存在但不在 compile.f，模块不在 hierarchy。**未被此回归测试。** |
| UNCOPIED | 110 | 没有 candidate 同路径副本、没有 compile.f 输入、定义模块均不在实际 hierarchy；与 build02 同字节只能证明未新增源码漂移，不能证明已测试。 |

因此，原 `regression03_closure_receipt.actual_compiled_registered=76` 实际按**文件存在**计数，准确含义是 70 个直接编译文件 + 5 个 raw→view 文件 + 1 个仅复制的 npu_cdc_top。原 `uncompiled_registered=110` 少计这个已复制但未编译的文件；实际 **75 个注册文件具有输入和 hierarchy 绑定，111 个没有本回归编译绑定**。原 receipt 不修改，本审查单独纠正其采用口径。

111 项没有 observed elaboration。包含原 motion/block_motion_detector、motion_result_cdc、ddr_w_arb、CDC bridges、axi_dma/read、HDMI 全链、NPU 全链及 npu_cdc_top、原 ovreg_axil_decode、preprocess 像素算法、pcie2npu、旧版 pcie_fifo/pango/controller/DMA 等生产源。不能称这些生产 RTL 已被 regression03 功能测试：实际使用的是 tc/rfg 版本、当前 raw/cooperative/diagnostic 链及其选定分支。替代模块名不同、同属某子系统或来自 build02 均不能作为未编译原版的功能等价证明。

分支证据：top 定义 USE_OV5640，HDMI 分支不进入该配置；top 的 preprocess_top 实例为注释，CAM/PREP 路由检查证明相关寄存器访问而非全部像素算法；camera 默认 MEDIAN_EN=0、KF_EN=0，top 显式保持0，vip 的 generate 分支未 elaborated。npu_cdc_top 无 hierarchy，NPU 内部源没有对应输入绑定。本结论不外推启用 HDMI/median/KF/NPU 的其它配置。仅凭词法可达图会把未激活 generate 的 vip 或同名实例误算成模块；本次以实际 compile path 和 hierarchy 为绑定证据，不用这种误算补齐 scope。

## 三、五个 sim_views 的精确来源

读取既有 source_diagnostics_top_candidate/sim_order.py，只在内存运行其读取/变换部分，截断 mkdir/write/diff 输出；未写入原目录、未编译。这五份 build03 raw 的内存变换结果分别**逐字节等于已编译 candidate/sim_views**，也继承 regression03 两侧相同的 view 输入。配套 JSON 固定 raw/view SHA256。

变换不是 primitive 替身：移动模块级 wire/reg/localparam/integer 声明；有初始化的 net 声明转成等价 continuous assign；补原本隐式的 wire（top: core_clk、ddr_init_done；FIFO: fifo_rx_almost_full；controller: total_length_cfg_done）；top 选择既有 USE_OV5640 分支，移除与既有 reg prep_frame_cnt 冲突的一份 wire 声明。原 .diff 可能显得移动了很多逻辑行，是声明抽取后的文本位置差异；本次验证的是既有变换精确复算。此证据绑定当前配置的仿真兼容 view，不声称未经变换的 raw 被直接 ModelSim 编译，也不把 view 的兼容处理提升为对所有配置的形式等价证明。

## 四、camera boolean 与 primitive-only delta

build03/rtl/ov5640_cdc_tc04.v 与 regression03 candidate 实際编译版、src 版字节一致：`9e4e186a43b04c2a5a446c0d7a78fbfe9beb75f3e339d22d7d160cea0b3f2625`。v7_sfd_candidate 删除新增属性后字节一致：`e4dd36babf9d42eab0bdd318f5b0b418df8e0a3d01cad9ba3103c4546a85f500`。四路 cg 在实际 candidate hierarchy 绑定 v7_camera_gap_boolean，四路 CDC 绑定 ov5640_cdc_tc04；没有把 boolean 候选换回 map02 的旧 counter 实现。

相对**实际仿真候选**只有以下源码 delta：

| 文件 | 新增属性 | 实例 |
|---|---:|---|
| v7_sfd_candidate.v | 11 处 `(* syn_noprune=1 *) ` | PE: cr_ff0/1、hr_ff0/1；CE: ack_sync_ff0/1、req_sync_ff0/1/2、overrun_sync_ff0/1 |
| v7_sdt_bus.v | 4 处同属性 | PE: reset_pipe_ff0/1/2/3 |

属性只在 GTP_DFF_CE/PE primitive 实例前，没有新增在 generic reg/wire 或 counter 模块上。四路 elaboration 为 44+16=60 个 primitive，即 28 CE、32 PE；PE 的 INIT=1、CE 的 INIT=0，所有 GRS_EN="TRUE"，Q/D/CLK/P或C/CE 接线及其它源码逐字节保持。两文件移除确切属性字符串后的**全文件字节相等**证明没有端口、init、GRS 或逻辑语义 delta；属性本身是综合保留意图，映射、优化和物理效果仍待门禁，不是功能结果或 timing PASS。

注意 manifest.changes_from_build02 的三文件差异包含 boolean/CDC 的功能实现变换，不能与“build03 相对 regression03 仿真候选只差属性”混用。

## 五、真实 primitive/IP model 与测试限制

实际 logs 加载 `vendor.GTP_DFF_PE(fast)`、`vendor.GTP_DFF_CE(fast)`；vendor_binding.log 映射至既有 source_diagnostics_top_candidate/vendor，既有 vendor.f 来源为 PDS_2022.2-SP6.4/arch/vendor/pango/verilog/simulation。actual hierarchy 同时存在 GTP primitive、真实 FIFO、DDR3、PCIe/HSST wrapper/IP。243 项中的 IP/model 输入按 contract 当前 hash 全部匹配，未发现把本次待证的 diagnostic primitive/FIFO 换成自制 behavioral stub。sim_views 不定义新 GTP primitive。

这个“真实模型”结论仍仅为**既有编译/加载证据**：本次没有重建 vendor library，没有倒推所有厂商库内部二进制的原始编译来源，也没有把加密 model 的功能加载等同于生产综合 RTL 或芯片实物验证。236 个同字节编译输入之外的库存 IP 分支、备份与其它语言模型不自动已测。

TB 实际 force AXI/control clocks、DDR init、PCIe AXI master 输入和四路 I2C completion；free_clk 停止。故本回归能绑定当前四相机输入、diagnostic/register/reset/control/lease 观察范围，不能证明 DDR 校准、PCIe training、完整 DMA 帧 DDR 写入、主机链路吞吐或 cooperative/NPU 端到端处理。75 份已绑定生产源也不是每条功能路径已全面覆盖。

## 六、trace、freeze 和管理漂移

既有三份结果两侧 equal=true，记录总数22663089；results 的解压内容 SHA256 见 JSON，X/Z 分别0、18397994、12，两侧一致且没有新增屏蔽。原 comparison/integrated 还记录与 regression02 exact match，boolean 为新增观察。此次核对日志、封存 receipt 与 results 的采用关系，**不重新解压遍历22M记录**，不宣称本次独立重做了全部逐记录比较。

原 freeze_audit 的五个变化保留为 FAIL：map02/audit_comparison.py、audit_final.py、controller.py、evidence/queue_latest.json、run.py；其前后完整 SHA256 见 JSON。它们不在两侧实际 compile.f/contract 的486项中，也不是新增属性移植的两个 map02 RTL 输入。因此它们不使已封存仿真源码闭包变成另一套输入，但**仍是原冻结违规，不能擦除、豁免、重置 frozen_before 或替换为总PASS**。

还存在必须保留的证据差别：results.freeze_failure 字符串中的 queue_latest.after=`f7b8c159c4a73b6427efbc02beb28128d06bc0ec6d5b6941956e7946deb8c527`，而 freeze_audit/audit 的 after=`a57cab8b46055705620c2bad2b981eead7fb10eef9e3c8c2d885ea9e2b3925e2`。原记录确有不同的管理文件观察值，其具体时点及因果本次未独立确认；不改写任一记录，不编造统一 after。其它实时管理文件或设备观察文件的 drift 不可拿来否定同字节仿真输入，也不可借“不相关”恢复其原冻结合规。此次对486项输入未发现 RTL/IP/model hash 漂移；不能将未编译库存模型的变化一律宣布不相关，须先证明其不是当前配置的输入。

## 七、采用结论与前后证据

可采用的功能绑定是：本次核实的486个实际 compilation receipts；build03 的75个当前配置、实际 hierarchy 可见注册RTL（68精确字节、2确切 primitive 属性逆变换、5精确 sim_view）；与其相关的选定 camera boolean/CDC、diagnostic/reset、register/control/lease 仿真观察。111个未编译注册RTL、其它库存/模型配置及库来源或物理门禁的未证部分不纳入功能 PASS。

JSON 保存输入 evidence SHA256、本次核对值、原封存的前后 delta，以及只读检查后的最终复查结果。最终验收仍 **PHYSICAL_GATE_PENDING**；原 regression03.functional_pass=true 和 pass=false 分别保留。没有生成 bitstream 接受结论，没有新 schema/contracts 或新的测试框架。
