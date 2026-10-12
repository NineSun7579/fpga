# build02 executable runtime

已授权本地 compile/synthesis/device-map/PNR/十组 STA/bit；无远程、设备或 SRAM 操作。
执行入口：`python -u runtime/controller02.py --run`。

`runtime/controller02.py --prepare` 已构造独立 `project.pds`，核对186项实际源登记、全部本地输入与约束资产，重置 flow 状态。
冻结741份 RTL/inputs、原 manifest、原 analysis_tools 和原 preflight_result 不改；新增 runtime 与 project/constraints_live 由 `evidence/runtime/runtime_hash_append.json` 追加登记。
原失败证明保留。`evidence/runtime/reviewed_reconciliation.json` 按两套真实 compile.f、vendor.f 和封存 include 文件逐项核验；活动 project/controller/queue 不属于仿真编译输入，不再永久阻塞。
历史 metadata 原字节未在旧审计中保存，因此不虚构它的逐行内容差异；证明的是它不被该回归消费，全部真实编译输入及其 hash 不变。

map01 最终 result + audit_final 尚需实际 PASS：重新读取三个阶段真实 ADF/DB/graph/export hash，在 build02 内只读重算60独立端点及 INIT/GRS/复位极性/前驱/时钟根。
map01 FAIL 将写 `blocked_reason.json` 并拒绝任何 build02 工具启动；不会把实验启动或计数摘要当成 PASS。
队列检查 map01 全限定 run.py/audit_final.py、build01/route03 前序控制器、PDS/TA；跳过自身及等待自身的观察者。排队时不占全局工具 mutex，避免阻塞 map01。

获准门禁后新跑 compile/synthesis，测试 adapter 实际新图，完整2048逻辑位重新映射；目标实际1320唯一 mailbox 对，禁止 legacy1280 marker fallback。
仅按本次 compile/synthesis图推导 U-B/精确 ACK 首级；保持16对后级同域时序，368关系中364保留，四个15.238ns预算独立验证。
dev_map 使用实际实验的合法三个整数选项；各 stage 要求官方 done、零实际 errors、fresh 非空 ADF/native XML DB、输入 snapshots 不变，拒绝 no-op。
map后重新导出图并验证60独立物理端点和重新推导约束字节一致性；U-B runtime PASS 后才 PNR。

实际 routed graph 重新绑定1320对、reset32、sync16；以正确 physical filter、小批次和逐 Slack 收束 parser 验收 Slow/Fast覆盖、十组STA、reset Recovery/Removal/MPW、IO112、HSST、motion32及保护hash。
全部签核成功才生成本地 bit 和 delivery_sources/independent_review_request，交主独立审阅；脚本不制造 accepted/reviewer，也不执行设备操作。
当前实际阶段、中文日志与失败证据见 `evidence/runtime/controller_status.json`、`controller02_console.log`、`failure.txt`、`blocked_reason.json`。
