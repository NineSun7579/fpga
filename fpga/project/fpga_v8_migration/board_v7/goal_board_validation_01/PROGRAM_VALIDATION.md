# 新诊断候选 SRAM 与 RK3568 板验证准备

写入范围为实际已有目录 `project/fpga_v8_migration/board_v7/goal_board_validation_01/`。本轮不 program、不 remote、不启动 GUI/PDS。既有 `baseline.png`、`baseline.xwd`、`baseline_identity.json` 由主负责人维护；24bit baseline 已支持。本目录脚本不会读取或输出连接凭据，也不会调用 `board_host`。

候选来源固定为相邻 `source_diagnostics_timing_build_01/`，不是旧 V7 交付。当前没有合格的新 delivery manifest/bit，执行门槛关闭。`validated_delivery.prepare.json` 是新提议合同模板，`prepare_only` 必须被拒绝；不得把模板或旧通过证据填成成功交付。SRAM only，Flash 不变，无自动回退。

## 本地命令

从项目根目录运行（默认与显式 `--check` 都只读证据，不导入 vendor、不查进程、不连 socket）：

```powershell
python fpga_v8_migration/board_v7/goal_board_validation_01/new_program_candidate.py --check
python fpga_v8_migration/board_v7/goal_board_validation_01/new_program_candidate.py --check --manifest <新delivery_manifest.json绝对路径>
python fpga_v8_migration/board_v7/goal_board_validation_01/new_validate_board.py --evidence <运行验收JSON绝对路径>
```

每次候选脚本均将 `receipt.json` 留在本目录唯一 `candidate_run_时间_UUID/`。缺失 manifest 返回 1、`status=blocked`；检查成功仅 `validated_only`，绝不表示烧录或板验证成功。

## validatedDelivery/v1 的真实交付门槛

该 wrapper 是本目录新提出的消费合同，尚无 producer；底层审计 schema 来自 `physical_subagent_evidence_01/audit_fixed.py`、`verify_routed11.py`、`whole_candidate_v2_route_01/audit_final.py` 和 `source_diagnostics_route_01/audit_targets.py`。不调用它们的 main（包含 PDS/bitgen），也不调用硬绑定旧 V7 的 `timing_correction_05/verify_delivery.py`。

主负责人准备真实交付时填写：`contract=validatedDelivery/v1`、`status=validated`、具体 `candidate_id`、新 timing build 的绝对 `build_root`、`mode=sram`、`target=PG2L100H`、两个 pre-program 状态 false。`bitstream` 必须是此 build 下唯一明确选择的实际 .bit/.sbit；其 `path/sha256/bytes` 必须具体。`programmer` 绑定 `project/tools/program_100h_motion.py` 的绝对路径、大小和 SHA256。每个 artifacts 项同样使用 `{path,sha256,bytes}`，不能只给 passed 布尔值。

| artifact key | 真实证据及门槛 |
| --- | --- |
| route / sta_raw / sta_summary | 新 routed ADF、完整原始 RTR、final_sta_summary.json；route/report hash 一致。Setup/Hold/Recovery/Removal/Minimum Pulse Width × Slow/Fast 十组唯一、非空、端点数正、slack ≥ 0、TNS=0、failing=0；Production/multi corner，无 VIOLATED。不以 Design Summary 固定字符串作通过/拒绝条件 |
| mapping / mailbox_raw / mailbox_audit | synthesis manifest 的 resolved[].mapping(kind,launch_CLK,capture_D) 是 logical 名；先使用 coverage.pairs 的 logical→physical 完整一一转换，再核对原始 mailbox RTR。audit_fixed 的 passed/details/records；Slow/Fast 全部 routed pair 精确覆盖，非空、不多不少且每条 slack 合格，默认 1320 对 |
| reset_targets / reset_bindings / reset_raw / reset_audit | 真实 synthesis 目标 `{ends:[...]}` 和实际分类/映射导出的 `{bindings:[{logical,physical},...]}`（需独立评审）；physical 必须是 routed_graph 中存在、连网的端点，logical目标与binding完整一一对应；原始 reset RTR；passed/details。四组 Slow/Fast × Recovery/Removal 每个实际 routed 目标覆盖、slack 合格，禁止空报告算通过 |
| io_audit / hsst | io_audit.json 的 passed、pins=112、matches_frozen_v7；hsst_actual_phy_audit.json 的实际 site/专用连接非空、两项 baseline identical true、dump hash。baseline 比对用于 PCB 不变，不绑定旧候选 bit |
| motion / routed_dump / routed_verilog | motion_routed_resource_proof.json、实际 routed dump 与 Verilog；hash 一致，4×19200×8=614400bit、32 DRM、每路8 cell、read_first 和真实放置/定义 |
| coverage / routed_graph | coverageproof_routed.json 的 passed=true、errors 空、bindings 非空、physical_pair_count、pairs[].logical/physical/direct_Q_to_D。完整 logical pair 集合与 synthesis mapping 相同，经绑定得到 routed 期望，禁止比较不同阶段字符串；实际 graph.primitives/ports、pin_net 必须存在，launch cell/Q 与 capture D 的 net 必须相同 |
| protected_before/after / inputs_before/after | 非空真实保护与输入 SHA256 inventory，前后完全相同且当前磁盘 hash 匹配；保护键必须绝对路径，inputs 相对路径以新 build_root 解析 |
| acceptance | 独立评审绑定 wrapper，见下段；不代替上述原始报告 |

如实际映射不是1320，manifest 必须明确实际 `mailbox_expected_pairs` 和 `mapping_difference_reason`，独立验收还必须 `mapping_difference_accepted=true`。不能沿用旧1280或声称1320；新映射的全部 pair 双角都要验收。如果新 producer 字段不同，先明确并评审适配，不得造 schema 成功。

acceptance 使用新合同 `contract=validatedDeliveryAcceptance/v1`，要求由实际独立评审提供 `accepted=true`、非空 reviewer、candidate_id、build_root、bit_path、bit_bytes、bit_sha256、programmer_sha256，及 `artifact_sha256`：精确绑定 manifest 中除 acceptance 自身之外全部 artifact 名称与 hash。还需 `audit_sha256` 精确绑定 audit_sources 的所有脚本 hash，及 `limitations` 与交付一致。该人工评审必须核实 bit 确实由此 route 和输入生成、原始 IO/HSST/motion/coverage 审计正确；这是一份外部人工签核合同，当前没有密码学签名设施。消费脚本不是 PDS 重跑，也不把 hash 正确等同功能正确。

manifest 的 `limitations` 必须记录实际 `unscored_io_paths` 与非空 `unscored_io_note`，由原始 RTR 流式计数、summary 和独立签核三方一致确认。已验收旧 V7 为1674，不将该数量硬绑定到新候选，也不宣称这些路径已完成IO timing验收。Design Summary 会被保留供审阅；即使报告总括语因 unscoredIO 等不同，只要十组及数值验收合格，也不因固定字符串错误拒绝。

## owner / boot / driver preflight

既有 execute 授权保留，但本轮禁止实际执行。后续主负责人必须先通过完整 check，再提供当次 `boardOwnerPreflight/v1`。要求 accepted=true、reviewer、captured_unix（执行时5分钟内）、delivery_manifest_sha256、bit_sha256，以及 identity_matches_baseline/exclusive_owner/driver_ready 全 true。identity_matches_baseline 指物理板身份，不要求当前 boot_id 等于 baseline；允许PCIe恢复所需真实冷启动。`artifacts` 为实际文件条目的 path/hash/bytes，必须有 identity/boot_current/driver_current/ownership。

安全边界二选一：`boundary_kind=proven_dma_idle` 要求 dma_quiesced=true 与实际 dma_idle 附件；`boundary_kind=cold_reset_rebuilt` 要求 cold_reset_rebuilt=true，以及 cold_reset_action/boot_before/boot_after/pcie_reenumeration/driver_rebind 附件。后一分支核对前后boot不同且boot_after等于boot_current，证明真实重建，**不要求也不声称旧DMA已drain**。烧录后若再次冷启动，另在运行验收中留下动作、boot与重新枚举/绑定证据。

真实文件应含板连接 identity（只保存非秘密身份）、3568 boot_id、PCIe枚举与 BDF、驱动绑定、当前 viewer/DMA owner、驱动前置日志。主负责人可阅读既有身份脚本及 board_host 配置以连接，但不能把 credentials 放入 manifest/receipt/报告。停掉 viewer PID 只能证明进程结束；不能据此宣称 DMA drain。需要真实驱动/设备 idle 或 completion 证据；没有可证明的 drain 时停止并记录 blocker。

若必须 cold reset，应由主负责人实际执行并记录复位动作、前后 boot_id、PCIe重新枚举、驱动重新绑定与错误日志；不能把 kill 当 cold reset 或 drain。仅 FPGA SRAM重载不自动等于3568冷启动。

后续实际入口为 `new_program_candidate.py --execute --manifest <绝对路径> --owner-preflight <绝对路径>`，不另设虚构授权 token。该入口仍须所有证据通过，随后调用 vendor.run(mode=sram,timeout)。保留唯一PG2L100H扫描、final scan、DONE、program_success、全 stage true 及最终flush日志、PID归属清理。receipt 中 `success` 仅代表编程；`board_operation_verified` 始终 false，Flash接口不开放。

## viewer 启动后的验收

主负责人保留 program receipt、cfg/server/client真实日志及 hash；确认新 bit hash。记录 viewer 启动时间、二进制/配置身份、独占 owner，采集启动后实时帧/计数与驱动日志、无新 DMA timeout/错误/停帧证据，最后采集3568桌面24bit截图与metadata。检查四路画面、帧持续更新、显示正常；baseline截图不能当新bit成功截图。

`new_validate_board.py` 最终验收现严格要求 `boardValidation/v2`；v1 的 boolean + 单截图合同仅可归档为历史非final scope，不能再通过该入口。模板 `board_validation_v2.prepare.json` accepted=false 必须被拒绝。详见 [BOARD_VALIDATION_V2_REPORT_ZH.md](BOARD_VALIDATION_V2_REPORT_ZH.md) 的实际 schema、采集步骤和限制。

v2 重读实际 cfg stage 日志与receipt字段，要求真实烧录完成采集边界、前后 /proc PID/exe/hash/args/model/boot 身份、至少两组PNG/original XWD/原metadata及hash/geometry/24-bit depth核对（支持24/32-bit像素存储）、身份和时间绑定的真实 viewer journal、四 diagnostic source 和六 camera observations 原始日志评审。driving demo 主画面四路，C5/C6允许独立补采；缺证保持pending并拒绝final。视觉正常仍由reviewer看两图声明，图片/正fps不等于DMA full completion，也不新增AXI硬证书要求。冷复位仍需真实动作、前后boot、enumeration/rebind证据。输出 reviewed_evidence_complete 表示严格离线一致性与人工评审附件完整，非自动视觉/硬件认证。

板验证通过应由主负责人独立记录最终报告，本轮没有新bit烧录、新截图或运行验收结果。

## 本轮本地验证结果

`python .../goal_board_validation_01/local_negative_check.py` 已实际通过，详见 `local_validation.json` 与四个 `candidate_run_*/receipt.json`：两个候选脚本 py_compile PASS；显式check、默认check及execute在缺manifest时均返回1/blocked；prepare_only模板被拒绝；板验收缺证据被拒绝。拒绝路径没有生成 Tcl/server.log。没有进行成功交付的正向测试，因为新 delivery/bit 尚不存在；没有GUI/PDS/remote/program动作。

## 实际 artifact assembler

`new_prepare_delivery.py` 只写本目录，默认 --check，缺失任何artifact或独立签核即reject。填写 `delivery_sources.prepare.json` 的副本：具体 candidate_id、新build_root、实际bit绝对路径、mailbox_expected_pairs、limitations，以及全部22个必要artifact绝对路径；可以额外绑定 audit_execution 等真实执行来源receipt，签核须覆盖所有新增hash。该脚本只计算实际磁盘 hash/size，读取外部 acceptance，并调用同一 verify_document；不会制造 accepted/reviewer，也不会根据模板或某个 passed=true自动创建签核。

sources 的 `audit_sources` 必须明确填写实际执行/评审审计文件绝对路径，角色键为 audit_fixed、verify_routed11、summarize、raw_audit、consumer（当前消费脚本）。允许新producer的适配实现承担同一角色；assembler读取这些实际文件计算hash/size，独立 acceptance 的 audit_sha256 必须逐项匹配。旧参考脚本不会自动填成新构建执行来源；如使用动态 exec/字节替换重用，还应额外绑定真实 reuse/执行hash receipt，供独立评审核实原始/执行代码差异。

```powershell
python fpga_v8_migration/board_v7/goal_board_validation_01/new_prepare_delivery.py --check --sources <完整sources副本绝对路径>
python fpga_v8_migration/board_v7/goal_board_validation_01/new_prepare_delivery.py --write --sources <完整sources副本绝对路径>
python fpga_v8_migration/board_v7/goal_board_validation_01/new_program_candidate.py --check
```

--write 仅在所有真实验收通过后创建本目录 `delivery_manifest.json`，已存在则拒绝覆盖；可指定同目录新文件名。候选消费者默认读此同目录交付，bit来源仍固定为新 timing build。sources是路径描述，acceptance是先完成的外部签核，两者都不是自动成功模板。

## 兼容性复核与剩余门槛

`local_compatibility_check.py` 已实际通过，证据在 `compatibility_validation.json`：旧 V7 `whole_candidate_v7_route_01/final_export/report_timing/fpga_v8_cooperative_top_v2_rfg01.rtr` 正例为十组非空、零失败及1674 unscoredIO；exact09 `final_export/report_timing/v7_sdt_top.rtr` 因真实VIOLATED拒绝。报告hash均保留。

同时读取 exact09 真实 mailbox/reset target 报告的第一条完整记录，成功解析无括号 routed 端点、lowercase slow corner 和slack。只验证了真实格式，不声称全target验收：其文件约2GB/10GB，旧读法曾MemoryError。现在RTR流式处理，审计JSON仅读取 passed/details 元数据，避免加载GB级 records/detail；完整交付验收仍需扫描全部原始target报告与校验完整文件hash。exact09已有mailbox审计如实保持false/covered0。

tiny semantic phase测试证明 `/CLK`→`/opit_0/CLK`、`/D`→`/opit_1/D` 与reset `/P`→真实 `/opit_0/RS` 转换；重复pair、错logical、错Q→D网、physical多义、缺reset/不存在的物理reset全部拒绝。这些fixture不生成成功manifest或真实验收文件。固定Design Summary标签的语义变体只在本目录临时fixture测试，不改原报告。

vendor合同也已本地核对：AST确认真实 `run(args,receipt,directory,bit,digest)` 签名，只提取其纯 `parse_log` 与TARGET/ERROR常量，重解析历史 `board_v7/run_20261006_134504_c9abdebb/log/cfg.log`；全部6个stage与原receipt一致、errors空，源码/log hash已记录。没有导入vendor模块、调用run/idle或启动工具。owner语义fixture另证实真实冷启动重建分支不要求dma_quiesced=true，缺reset动作或idle证据时拒绝；fixture不是实际板证据。

剩余：新合并候选仍由其他agent做preflight；当前没有其最终route/bit、真实routed graph/reset binding、双角目标报告及独立签核。现有审计脚本的logical目标和parser缺陷可能导致target返回全设计或covered0，必须由负责构建/审计的agent修正并产出真实physical目标报告，本目录不会改他们的工程或testresults。完整新交付正例、实际program及3568 viewer/截图验收尚未进行，Flash保持不变。
# 定向报告解析补充

交付的 `target_logs` 必须包含 `mailbox` 和 `reset`，每项提供 `shell`、`run` 两个非空 artifact 名称列表；名称引用同一交付清单的哈希绑定附件。任一日志出现 Timing-4006、STA-3016 或 unknown arguments/options，交付核验即失败。批次查询可在各列表中列出多份日志。

Recovery/Removal 依据当前路径明细的行首 `Recovery time`、`Removal time` 识别，corner 仅取当前 `Path Type`。在 Slack 行提交记录，避免后续汇总表污染最后一条路径。真实 reset.snr 已复核为 16 Recovery、16 Removal；普通路径的 Clock Pessimism Removal 不会被识别为复位检查。证据见 reset_parser_validation.json。
# Routed data connection verification

The consumer recomputes each mailbox Q-to-D path from the bound routed graph. A direct wire requires a unique launch-Q driver. An intermediate `gopCLKROUTE/CR` is supported only with the actual effective INIT A/B/C/D values equal to zero/all-ones/zero/all-ones; its M input is traced recursively to the unique launch Q. Cycles, unknown primitive types, multiple drivers and different launch outputs reject the delivery. Buffered paths still require the original launch-CLK to capture-D timing reports, including buffer delay.

The `routed_connection` audit-source role must bind `routed_connection.py` alongside the consumer. Independent acceptance must include its actual hash. Saved build01 evidence in `routed_connection_check.json` covers 1320 connections and four negative checks; it cannot stand in for the final candidate graph or final timing acceptance.
