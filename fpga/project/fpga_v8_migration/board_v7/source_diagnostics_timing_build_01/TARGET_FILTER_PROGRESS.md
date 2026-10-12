# 定向报告实测进度

本目录实际 Compile、Synthesize、Device Map、PNR 已完成，真实 ADF/native DB 及启动日志保存在 evidence。PNR 最终 synthesis/compile 图重新推导得到 1320 配对，生成 clock.fdc 与实际 routed 输入逐字节相同；runtime U-B 继承检查通过。生产源、IP、route02/03 未修改，无 remote/program。

diagnostic_single_pair_result.json 证明一个实际物理 pair 精确命中双角 15.238ns MaxDelay：Slow slack 14.448ns，Fast slack 14.784ns。shell 和 report_timing/run.log 的 Timing-4006、STA-3016、unknown argument/option 扫描均无命中。该证明不代表完整签核。

targeted_reports.py 使用行首 Recovery time/Removal time 分类，每个记录在 Slack 行提交；corner 只取该记录 Path Type。既有真实 reset.snr 16 Recovery + 16 Removal 回归通过，Clock Pessimism Removal 与记录后 summary 反例通过。

audit_physical_mailbox.py 已完成实际 routed 根时钟遍历、逐 receiver 的 FDC 行号/CDB 继承检查，以及 64 对一个 batch 的全部 1320 pairs Slow/Fast 报告。21 个 batch 全部实测通过：Slow 覆盖1320/1320，最差13.306ns；Fast覆盖1320/1320，最差14.036ns；缺失/意外配对均0。保存原始报告与逐 batch shell/run 日志，不用报告 canonical pair 替换绑定。actual_mailbox_completion.json 的 full_signoff=false。

尚未签核：原 coverageproof_routed.json 保留失败结果；新的实际 receiver proof 单独保存，避免删除 synthesis 叶节点来迁就旧断言。32 个逻辑 reset 寄存器到20个物理单元（含双级SRL）的参数、级联、异步网来源映射通过；原始定向报告仅覆盖12个物理RS / 24个逻辑级，camera域cr[0]/cr[1]共8个逻辑级未返回Recovery/Removal，不能宣称reset32时序通过。sync外部路径双角通过，8个打包内部路径仍需要真实时序证据。

全局实测IO112、HSST专用连接和motion32通过。十组STA中Slow Setup有3个失败端点，slack=-0.882/-0.692/-0.159ns，均从camera2 cmos_frame_vsync_r发出；其他九组无失败端点。最差路径93.891%的数据延迟为布线，完整原始path保留在 evidence/evidence/all_reported_failing_paths.json。不得放松时钟或例外掩盖违例。

run_route_attempt02.py 已启动独立route_attempt_02物理尝试：不改RTL/FDC或mapped DB，使用工具帮助已实证的seed2与route constraint iteration，串行mutex保护，generate_bitstream=FALSE。本次全部产物保留。新route完成后必须重新导出物理图并重新完成全部实测验收，不能沿用本次routed绑定/报告作为新route的签核。

交付 sources 入口已添加 target_logs：mailbox/reset 各 batch 的 shell/run 均以 artifact name 引用实际 hash 附件；最终再计算 consumer/audit 源 hash。没有创建 accepted/reviewer，也没有 bit。
