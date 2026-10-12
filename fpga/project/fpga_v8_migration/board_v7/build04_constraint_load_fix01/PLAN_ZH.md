# 必要阶段与实测收据

1. 先等待指定 V7SRAM 的 DONE / program_success；全机 PDS/programmer/controller 空闲且取得全局锁后才启动本任务。已从 qualifiedV7_sram 原始 receipt/stdout 验证。
2. 从冻结 build04 复制 inputs、rtl 到隔离 candidate02，核对 741 哈希、186 源登记。保留六个非源码约束入口，并用 compile 图推导 replacement clock；冻结 1432 文件保护清单。
3. 官方工程模式 compile；完整 `.switch_db` 导出和原生图解析；核对源图一致性。此阶段实际已返回 0，图 SHA256 与 build04 完全相同。原生 compile CDB 为空，不能作为 replacement 成功证据。
4. 官方工程模式 synthesize；保留原综合配置与源码 preserve/noprune 属性，完整导出 fresh synthesis 图/CDB。实际日志显示工具先 compile，再 Synthesize。本阶段未结束前不消费 partial DB。必须核验 15238 与无旧 CLKGP。
5. 对 fresh synthesis 直接从 host D→mailbox Q→CLK 完整重新绑定。本轮实际综合保留1320对，其中40对是签名字常量1寄存器，已逐个核验原生D常量网；不得删掉这些真实连接。mapped和routed阶段继续要求1280 unique硬断言。精确检查 production60 草案的 60 sourcepaths 是否仍是独立 C/P storage，若路径改变则拒绝直接复用草案。用新图重新推导 synthesis phase 的时钟 complement、MaxDelay、mailbox hold 和 ack-first 绑定。
6. dev_map 仅使用本轮 fresh synthesis ADF，登记已验证 production60 LCF，执行官方 `-override_pcf TRUE -devmap_remove_dups 0 -devmap_const_prop 0 -devmap_control_set_num 0`。完整导出新 map CDB/图，核对原生 PCF 60 唯一 site 与目标、重新绑定 1280 对、拒绝旧 constraint 文件来源。
7. 原生 report_timing 对实际 1280 对显示 MaxDelay 15.238、无四组旧 async、DDR requested 131.2500MHz；保留真实 rc、全部 CDB、reports、阶段原生错误表。只有满足实际写入和精确绑定后才生成 PASS 交接。
8. 用户现已授权本子任务执行真实PNR：将fresh map/PCF及阶段隔离复制到route_attempt01，官方multi_corner、fix_hold、fix_hold_violation_in_route TRUE、iterations=12，随后原生导出与global10/mailbox报告。MAP report_timing已知要求PNR阶段，延后执行不作为MAP CDB失败。原先 Setup -0.071、Hold -1.711、Removal -0.038 仍是旧失败事实；以新实测完整十项非负为准，禁止豁免。若固定site不收敛，提交具体最差路径、clock skew和相关site候选；不改功能/clockfreq，不生成bit、不远端操作。

candidate 的首次空工程 compile 失败已保留，不会覆盖成成功。所有未知接口或真实加载/绑定失败都保留日志并拒绝放行；不猜 DB 字段、不 no_check、不 bit、不上板，不引入额外内部形式 gate。
