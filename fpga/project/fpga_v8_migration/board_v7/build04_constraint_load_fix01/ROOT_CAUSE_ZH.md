# 约束加载根因与必要构建阶段

冻结的 build04_replacement_clock_route01/actual_review_handoff.json 显示旧 mapADF SHA256 为 3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419；PNR 成功返回 0，但原生 CDB 不含 15238，四个 camera pclk 仍有 ASYNC，1280 对目标的 15.238 覆盖为零。pnr.tcl 实际仅登记新约束，然后通过 -input_db_file 明确消费旧 mapADF；它未执行 compile/synthesize/dev_map。旧 CDB 的 FN 指向 build04 原始 constraints_live/clock.fdc，CLKGP 对 cmos1..4_pclk 的 ASYNC 均为 1。因此“add_constraint 成功”不是替换 input_db_file 内 timingDB 的证据。

官方 pnr help 无 replacement SDC 入口；.switch_db 为格式转换，TA 不能写回该映射数据库。用户允许必要重建，本次不再继承旧 compile/syn/map ADF。在隔离 candidate02 中复制 build04 的 inputs/rtl，核对 741 文件字节和 186 工程登记。使用已实测的 -project project.pds -run compile/synthesize 接口，让工程 constraints_live/clock.fdc 在编译入口生效，随后 dev_map 只读取本次产生的 synthesis ADF。

首个 candidate 的真实 compile rc=1，Flow-0001 显示脚本模式 -file 未加载复制的源登记，生成空工程。此目录、compile.log、receipt 和失败记录全部保留；修正后的 candidate02 使用官方工程模式。该失败没有被视为约束成功，也没有改写旧工件。

compile 约束只包含实际 compile 图的层级 pin；get_pins -hierarchical 使用点分隔层级和末尾 /port。production60_site_DRAFT.lcf 使用原生 slash 实例路径和 PAP_LOC，不能把两者相互替换。保留 replacement 的 U364、datapath_only 15.238 和 mailbox hold 例外；不增加同域时序豁免。DDR master 25MHz，84/16 对应 131.25MHz。新 compile 图要与原 source 图核对，新 synthesis/map 图重新绑定全部真实 mailbox Q→host D；不得按旧 alias 推定新 CDB 已写入。

candidate02 实际 compile 返回 0，图与 build04 compile 图完整一致，SHA256 8a5fd6e2d07c1de21fb62c341e2c933be63ac6c0c2f6d296cbbea816d092befa。完整原生 compile 导出显示 `(CDB )` 为空；这证实本版本的 compile 工程入口完成源编译，真正 timing 约束的加载应在 synthesis 阶段核验，而不能要求 compile CDB 已包含 MaxDelay。fresh synthesis 与 map 必须分别核验，不以空 compile CDB 放行。

实际 `-project ... -run synthesize` 自动先 compile，再 Synthesize；当前版本的工程流程行为已记录在 synthesize02.log，不把该必要前序当作违规重建。本任务接受必要完整重建，也不猜测 phase 字段去绕过它。synthesis 实际开始执行本地 replacement FDC 的 compile 层级对象；是否成功转化为优化后真实对象，仍需 synthesis/map 原生核验。

官方 ADS Synthesis User Guide 第 5 章（PDF page 53 / 正文 52）也明确：FDC 中 attribute 作用在 synthesize 阶段；需在 compile 生效的 attribute 应写在 HDL，syn_keep/syn_noprune/syn_preserve 等只支持 HDL 设置。本任务保留原 HDL 字节与已有属性，不尝试用 FDC 新添 syn_preserve 冒充源码保护。

V7SRAM 优先任务 qualifiedV7_sram.receipt.json 返回 0，stdout 的 device_done/program_success 均为 true。每次真实工具启动均重新记录全机进程并拒绝 PDS/TA/programmer 或相关构建/编程 controller，同时获取 Global\ov56401_PDS_single_instance。中文 live_log.ps1 只读取本任务日志。

本任务仅 compile/synthesis/map/原生导出与 timing exception 核验；不 PNR、不 bit、不板卡操作。旧真实 Setup -0.071、Hold -1.711、Removal -0.038 保持失败事实，下轮 PNR 必须实测解决。
