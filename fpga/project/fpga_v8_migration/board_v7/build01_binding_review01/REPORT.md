build01 只读 binding 审计：失败来自旧适配器对清理、复制、buffer、packing 的错误假设，未发现 mailbox logical bit 丢失。

仅新增本目录 review.py / review.json / REPORT.md。未调用 PDS、remote，未修改 build01/build02 控制器或约束。运行：`python project/fpga_v8_migration/board_v7/build01_binding_review01/review.py`。本报告的 build01 路径基准为 `../source_diagnostics_timing_build_01/`。

|实际复核项目|count / 结果|
|---|---|
|actual_post_constraints manifest|2048 resolved，1320 register，728 constant_zero，0 errors|
|独立 routed 读数据 LUT 穷举|2048 resolved，1320 register，728 constant_zero，0 errors|
|每路 camera 0..3|512 = 330 register + 182 constant_zero|
|真实 mailbox Q → host_bank D unique pair|1320；1319 直连，1 经 gopCLKROUTE|
|穷举输入赋值总数 / 访问物理 output|3368 / 1785|
|diagnostic sync logical stage|28，12 普通 Q stage + 16 SRL2 内的 stage；8 个内部 Q0 无 fabric net|
|sync later logical edge|16 = 8 外部 Q→D + 8 SRL2 内部 Q0→CR0|
|reset logical endpoint|32 = 8 普通 FF + 24 SRL2 stage；20 个 distinct 物理 RS|

proof 方法：从实际 routed `read_data` 寄存器的 L6Q/L5Q 对应组合输入函数出发，读取该实例实际 INIT / INITA / INITB 与已排列的 I0..I5 / A0..B5 / M，固定 snapshot_valid=1、word_sel=0..15，穷举剩余 support。结果必须是 manifest 所指定 host_bank 的 Q 恒等函数或零，再从其 D 逆向追溯唯一 mailbox Q driver。覆盖全部 4×16×32 位，未拿 cell prefix 或旧 manifest 代替读数据函数证明。读 strobe 表示读寄存器已使能的契约，本次证明组合数据值；未证明读 CE/reset 的时序协议。ADIF `$constant_y` 按未定变量建模，没有强制置零；所有最终函数均消除了其影响。read_data 部分合并 LUT cone 引入的 IO 信号也按自由变量穷举。

14 条原始 errors 的根因：

1. 12 条无候选：四路各 `cmos_capture/cam_href_d[0]`、`[1]`、`cmos_frame_href_r`。`evidence/dev_map.log:34674,34684,34694,34740,34750,34751,34772,34773,34794,34795,34816,34817` 均有 Public-4008，明确 `dangling and will be cleaned`。同一日志还记录下游 hsync_sync[0:1] 清理；详细行保存在 review.json.cleanup_warnings。routed 原始 ADIF 中 cam_href_d / cmos_frame_href_r / hsync_sync token 均为 0，图中也不存在：这是工具删除无使用的链，不是 parser 丢失祖先层次。旧 camera clock leaf 集合不能要求删除后的名称仍存在。
2. 1 条双候选：`cam2_ov5640_top/ov5640/cmos_frame_valid_r/{opit_0_inv,opit_0_inv_1}/CLK`。两实例 D、CLK、RS、CE net 和全部 FF 参数相同，CLK_POL=TRUE；输出分别驱动 `/@diag_capture_valid[1]` 与 `/@_N126`。是合法 fanout 复制，应保存两个实际 CLK endpoint，不能选一个或要求 prefix 唯一。完整记录在 valid_clone_evidence。
3. 1 条 Q→D 不同 net：camera=3、logical_bit=102、word=3、bit=6。真实路径：`source_diagnostics/cameras[3].source/mailbox[102]/opit_0/Q` → `/@source_diagnostics/cameras[3].source/mailbox[102]` → `CLKROUTE_291/M` → `CLKROUTE_291/CR` → `/@ntR11798` → `source_diagnostics/cameras[3].source/host_bank[102]/opit_0/D`。gopCLKROUTE 的 INITA/C=全0、INITB/D=全1；本适配器仅在该 identity 配置下透传。raw export 中没有 keepbuf 字样，此处实际 buffer 名为 CLKROUTE，而非 KEEPBUF。host_bank[102]/Q 经实际读 LUT 仍对应 word3.bit6，完整 trace 见 buffered_pairs。

28sync / 32reset packing 是下一道潜在失败，**不是这次 14 errors 的来源**：build01 在 routed_acceptance.py:39 就早退，尚未到 :44..54。

实例：`source_diagnostics/cameras[0].source/req_sync[0]/opit_0_srl` 为 gopSRL2，stage0 是内部 Q0（未连接外部 pin_net），stage1 的 net alias 为 `/@source_diagnostics/cameras[0].source/req_sync[1]`，实际输出是同一实例 CR0；CR0 再直连 req_sync[2]/opit_0/D。ack_sync 两阶段保持普通 FF；每路 req 和 overrun 各一个 SRL2。

reset 每路：cr[0:1] 两个普通 FF；hr[0:1] 一个 SRL2；reset_pipe[0:1]、[2:3] 各一个 SRL2。故 8 logical reset stage → 5 physical RS，四路 32→20。hr[0] 与 hr[1] 都映射 hr[0]/opit_0_srl/RS。应保存 logical_stage、物理 cell、内部 stage index 与 RS 的多对一映射，不能把 20 条物理 report row 机械判为少于 32。SRL2 的 FF0/FFAPP0 reset/init、RS_MODE、LRS_POL/EN、GRS_EN 必须逐级核对；review.json.resets 保留全部物理参数。结构可映射不等于已通过 recovery/removal/MPW。

准确 adapter 修法（本目录仅交付参考实现，不修改现有控制器）：

- 用实际 Q net aliases 建 logical-stage→physical output 索引；规范化 synthesis `hier/@signal` 与 routed `/@hier/signal`，保留原始 alias，检查歧义。名称只作锚点，不能作为独一身份。复制输出用 D、CLK、reset/enable、INIT、polarity 与 fanout 验证等价，返回 endpoint 集合。
- 对普通 FF / LUT5Q / LUT6Q / SRL2 提供显式 primitive schema。SRL2 stage0=内部 Q0、stage1=CR0；内部 stage 间用 packing 参数和状态结构证明，外部边仍做实际 driver tracing；不可伪造不存在的 Q/D pin 来查询 STA。应核查厂商 report 对内部 stage 的表示方式并保留实际证据。
- 数据 buffer 逆向遍历只接受已验证 identity primitive/配置，检查每 net 单 driver、cycle、实际输入与输出方向。加入 `gopCLKROUTE: CR←M`（核对上述 INIT）；不能将名字含 BUF 的所有实例一概透传。timing pair 仍是 mailbox CLK→host_bank D，包含 buffer 延迟，不能把 buffer CR 当 launch 或宣称 direct_Q_to_D。
- 对所有 2048 logical bit 重跑 routed 实际 LUT function proof，输出每位 kind、physical capture_Q、launch_Q、完整 buffer trace，再去重统计真实 pair；当前应为 1320+728。零常量示例 camera0.logical_bit56。禁止只检查1320个旧名称而跳过728常量/优化位。
- camera clock coverage 应从 routed 根时钟穿越已确认的 clock buffer/gate 枚举真实 storage clock pins，保存复制与清理证据，核对 surviving exceptions 的覆盖。12 条已获 Public-4008 清理证明；未获清理或等价证据的 missing 必须继续失败。时钟反相要保留 polarity，不能按数据 identity 合并。
- parser 的 walk 只保存 primitive 的本层 attributes/cdb_entries，祖先来源会丢失；另存 ancestors + accumulated provenance，保留层级继承语义。当前这些连接在原始导出中可核对，14 条失败不是该问题造成。物理 OPER port 的 clock 标记常为 False，`GTP_DFF` 类型筛选也无法识别 `gop*` storage：须 schema 标注，不能把所有 CLK 名称直接视作合法时钟。

build02 的当前风险位置（只读确认）：`../source_diagnostics_timing_build_02/runtime/routed_acceptance.py:17..39` 仍要求 prefix 唯一及直接同 net；:51 要求 32 distinct RS。`runtime/analysis_tools/graph_adapter.py:48` 仅认旧层级 alias；:57 明确拒绝 SRL；:131 要求60 distinct physical storage cells；transparent():11..16 不认 gopCLKROUTE，clock_ports()/clock_leaves() 也不完整识别 gopSRL2 / LUTxQ 与物理 clock route。build02 RTL可能有意避免packing，需其自身最终图证明；不能拿 build01 的20RS直接作为 build02预期。但当前模板没有覆盖本次已见变换，单补 `k==cell` 不足以防止同fail。

关键输入路径 / SHA256（完整绝对路径、大小及更多hash在 review.json.inputs）：

|路径（相对build01）|SHA256|
|---|---|
|evidence/routed/analysis/graph.json|d909dfee342ccfb2810633474b78dd6782be5818425846abeecc6f3bde616112|
|evidence/routed/synthesis_export/synthesis_dump.txt|b617f6afbd507dc32958a947c9fb42c25b9fee860b08141211b19e04ffe25d24|
|evidence/routed/synthesis_export/synthesis_dump.v|e1b526738e54dc032234c694e2f22dc0a2cc01dee005633202ce4e5dc52af3e9|
|evidence/actual_post_constraints/analysis/manifest.json|0a0eba353be252df158fdc85d05551dd6cc68744be1afd82b2b5f43b549d7ef5|
|evidence/coverageproof_routed.json|40a57257b9a4ed0d43d1e19f6aa9adb2d04f25a5278f0de052b70bf5f807ef0d|
|routed_acceptance.py|f0ab2acb109f461734659a6d0483fc9295833b635ee7e7538bd7880c35e605aa|

当前结论限于数据功能及结构绑定。build01 recovery_failure.txt 指向 coverage failed 早退，target STA / global ten-group STA 尚未知；本审计没有 PDS timing 结果。不能据此签时序、默认接入 DMA 候选，也不能认定 map01/build02 等待的 route03 final export 已完成。
