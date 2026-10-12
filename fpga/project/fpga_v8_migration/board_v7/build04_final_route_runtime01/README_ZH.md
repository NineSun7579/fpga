# build04 最终 route runtime01（外部、离线准备）

本目录的 `controller.py prepare` 是可运行离线 producer。首次安装运行 `python -B bootstrap.py`，然后 `python -B controller.py prepare`、`python -B regress.py`、`python -B seal.py`。只在本目录写入；不 import build04/03 controller，不启动 PDS，不生成 bit，不执行远程或设备命令。

输入合同逐字复制 review02 的 `candidate_specific_expectation_contract.json`。校验源741、登记186、742完整副本、compile/synthesis/mapped graph/raw、原生 ADF/DB、官方模型和独立复核 hash。fresh resolve 从 build04 的 graph/objects 重新计算2048逻辑行；校验精确728 zero、1320 register逻辑行、1280独立Q-D、每相机320和完整反向alias成员集合。共享逻辑位不被删掉，也不重复计入物理 targets；双corner恰好2560。

`runtime/derive_new_constraints.py` 是有限修改副本。旧 derive 的1320 guard、build02/03/04及map失败证据均未修改。新副本仅改为绑定本合同的精确1280/320，并在derive之前校验精确mapping。KEEPBUF保留review01严格WIDTH/ports/方向/无clock identity schema和无输出net的no-storage终端分支。clock leaf sink进一步收窄为绑定compile/synthesis实际已复核类型的精确集合，拒绝未知前缀类型；未给gop行为开白名单。

实际生成 `constraints/clock.fdc`、`coverageproof.json`、`physical_targets2560.json`、`route_copy_plan.json` 和 `commands/*.tcl`。clock审计比较已签reference的完整命令序列及全部compile/synthesis leaf、complement、maxdelay pair成员，保留所有原始create/generated clock、uncertainty和DDR multicycle字节；U368−B4=364、15.238ns、DDR131.25MHz。离线匹配不代表生产mapped CDB已替换。

`reuse_ledger.json` 与每个 `.diff` 给出复用脚本before/after SHA256和完整差异。`input_before.json`/`input_after.json` 覆盖旧runtime、完整source、protected原始生产/IP、build03原始冻结集合、ADF/raw/map DB/失败receipt等实际输入；没有扫描或冻结另一个正在运行的诊断agent目录。执行前仍需主会话确认动态producer结束；若任何绑定漂移，重新建独立revision，不覆盖旧证据。

生成Tcl首行 `error` 默认锁死。`controller.py check-gates`、`copy`、`route` 要求本目录由主会话明确提供 `main_enable.json`（schema `main-session-route-enable/v1`、enabled=true、reviewer、session_id、candidate_id、contract_sha256、runtime_seal_sha256）。`evidence` 必须逐项绑定 `mapping60`、`IO112bank`、`timing_reload` 独立receipt路径及SHA；不能用resultfile存在或status PASS代替。receipt schema为 `independent-physical-evidence/v1`，含kind、independent=true、reviewer、source_candidate_id、contract_sha256、map_adf_sha256。coverage精确keys见 `runtime/gates.py REQUIREMENTS`；每项都必须有verified、method和非空raw_files（path/bytes/sha256）。另外检查实际60 logical/physical/site精确覆盖、IO112/3及内部bank电气字段、实测replacement clock hash与364精确关系。主会话必须审查这些语义receipt和原始证据，runtime不从名字推断vendor primitive行为。

当前没有创建main_enable，所有物理门禁关闭。特别是timing reload要求真实工具证明新clock替换旧CDB、旧4对全域async消失、15.238实测exception、364/complement集合、DDR/同域关系和mapped graph不变。这个独立实测必须在生产route启用之前完成；本目录不假定 add_constraint 能覆盖旧CDB，不执行诊断PNR，不操作另agent目录。

启用之后 `copy` 按实际逐文件source→destination hash计划复制到全新 `execution01`，`route` 仅调用官方 `pds_shell -file`/显式mapped ADF `pnr`。禁止前序compile/synthesis/dev_map；保留shell/native日志、exit、新鲜ADF/prr.db、官方done及输入前后hash；新失败不能覆盖重跑。原project只归档为DO_NOT_RUN，新session只登记replacement clock、5非clock FDC和native PCF，不同时加载LCF。复制阶段和route都不会运行bit。

`commands` 中targeted脚本是synthesis端点模板；真实route必须从原始routed graph重新证明2048语义/1280分组并重绑定实际CLK/D/reset端点后才使用。20批×64对，先single-pair两corner/MaxDelay15.238，再2560精确评分记录；拒绝笛卡尔cross pair、重复、缺corner、无分数、错budget或负slack。不得把本目录的合成fixture当真实STA。

`signoff_manifest.json` 保留global10、targeted60/32reset/16later、IO112 full bank、HSST sites/专用连接、motion32 geometry/read_first/数据地址、实际CDB reload各原gate。`signoff.py` 是未来证据的离线consumer入口：要求route hash一致、独立原始routed解析证明、精确2560实际报告、global10非空/非负WNS/零TNS、reset四格/MPW双corner/later四格、语义独立复核/raw hash、HSST基线精确恒等和motion32内容。输出仅 `delivery_sources_NO_BIT.json`，accepted=false/reviewer=null/board_verified=false；不能代替主独立consumer签收，不能生成bit。

最小剩余blocking evidence：mapping60官方primitive/clock/cr alias身份闭合；IO112完整内部bank/差分3/电气/PCB矛盾闭合；独立真实timing reload/no-remap实测并绑定本replacement clock；主会话明确hash绑定enable。之后仍需本新route的全部global/targeted/语义/IO/HSST/motion签核。所有既有FAIL保留。
