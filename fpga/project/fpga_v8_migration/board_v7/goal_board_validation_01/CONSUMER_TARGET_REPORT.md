# Consumer 当前 build03 gate 修复报告

结论：consumer/assembler 已加入必要证据与独立 raw/graph 重算；当前实际交付仍应 FAIL，未生成 accepted manifest，未执行 PDS、remote、DMA 或 program。

## 实际 schema 与强制 gate

- `routed_endpoint_audit` 对应 build03 `evidence/runtime/routed_endpoint_details.json`。离线重跑冻结源码中的纯 graph/endpoint 函数，再与该报告完整比较；检查 60 个独立 cell、实际 D/Q/CLK/reset、链路、时钟根、reset OR 真值表、INIT/GRS、异步形式、极性、CE、PAP_NOPRUNE。SRL/RAM/DRM、非 Q 实现与 latch 拒绝。
- coverage 的 `route_sha256` / `graph_sha256` 必须匹配当前绑定文件。
- reset 目标必须是重算所得 32 个实际 reset pin。`reset_bindings.json` 的每行必须精确匹配 `{logical, physical, clock_physical}`；四个 Recovery/Removal × Slow/Fast raw 集合完整且非负。
- `reset_mpw_raw` / `reset_mpw_audit` 强制提供。audit schema 为 `passed/details/clock_targets`；raw 必须非空，两个 corner 都覆盖实际 clock_targets，支持的 MPW 形式为同一 primitive clock pin 的 Startpoint/Endpoint。其他形式拒绝，不推定通过。保存 worst_slack 必须与 raw 重算相同。
- `sync_pairs` 的文件 schema 是 `sync_bindings.json` 的 `{bindings: [{logical: [launch_CLK,capture_D], physical: [launch_CLK,capture_D]}]}`。必须与当前 graph 重算的 16 个 ordinary_pairs 精确匹配；raw 每个 Slow/Fast × Setup/Hold 集合都覆盖全部 16 pair，无 unexpected/exception/负 slack，保存 worst_slack 与 raw 相同。
- 新目标 raw/endpoint/sync 文件必须位于当前 build，并且 mtime 不早于当前 route。内容哈希继续由实际独立 acceptance 完整绑定；mtime 单独不代表 acceptance。
- target_logs 的 `reset_mpw`、`sync_later` 与 mailbox/reset 同样强制 shell/run 两类非空绑定日志；大小写不敏感拒绝 Timing-4006/Timing4006、STA-3016/STA3016、unknown argument/option。
- 新 helper `endpoint_recompute` 及其读取的 `endpoint_graph`、`endpoint_logic`、`endpoint_parameters`、`endpoint_checker` 源码角色，在 consumer 和 assembler 都 mandatory 并由 acceptance audit_sha256 绑定。原 `routed_connection` 角色保留。

## 实测与测试

build01 实际 routed_reset：48 条 record，12 个 endpoint；Slow/Fast 的 Recovery/Removal 各 12 条。实际 routed_sync_later：32 条 record，8 个 pair；Slow/Fast 的 Setup/Hold 各 8 条。实际 graph 因打包存储不能满足 independent60 被拒绝；这些证据不能作为当前 32 reset / 16 pair gate 的 PASS。

检查时 build03 的实际 graph.json、endpoint audit、sync binding、MPW audit、目标 .rtr 均不存在，实际目标报告数为 0；build02 也没有这些实际报告。legacy build01/02 不享受证据缺项豁免。

`local_target_gate_check.py` 通过：真实 reset/sync parser 计数，以及 17 项拒绝检查（缺 corner、缺 Setup/Hold cell、错误端点、负 slack、不完整 record、无独立60、旧 graph、无效 target 日志）。Synthetic 仅测试拒绝语义，不称 final actual PASS。尚无真实 MPW targeted 样本可验证其实际 vendor 形式；不支持或缺失的实际形式必须 FAIL。

已有 `local_compatibility_check.py` 与 `local_negative_check.py` 通过；保留已有真实 V7 十组 summary 与 1674 条 unscored IO、历史 vendor parse_log 合约、旧失败报告拒绝、缺 manifest/template 拒绝等检查。未调用 vendor.run。

## 冻结 producer 的准确 handoff

不修改 build03 runtime/controller/inputs。其 `prepare_local_delivery.py` 已输出 `routed_endpoint_audit`、reset_mpw/sync_later raw/audit 和两个 target log group，但尚未输出 consumer 新强制角色 `sync_pairs`；应绑定现有实际路径 `EVIDENCE / 'sync_bindings.json'`，不是制造新的 pair。

producer `audit_sources()` 需要增加：

- `endpoint_recompute` → goal_board_validation_01/endpoint_recompute.py
- `endpoint_graph` → build03/runtime/analysis_tools/graph_adapter.py
- `endpoint_logic` → build03/runtime/libraries/endpoint_logic.py
- `endpoint_parameters` → build03/runtime/libraries/endpoint_detail.py
- `endpoint_checker` → build03/runtime/libraries/endpoints.py

它现有的 `graph_adapter`/`endpoint_audit` 源角色不能代替上述角色：前者可指向相同文件，后者当前指向 physical_flow.py，而实际逐 endpoint 检查在 endpoints.py。需在实际源码与实际证据齐全之后获得独立 acceptance，其 artifact/audit hashes 必须覆盖新增内容；本次不生成任何 accepted 内容。
