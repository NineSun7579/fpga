# map02 最终交接

真实 compile/synthesis/map/export 和独立 audit/comparison 已完成，结论 FAIL。compile/synthesis 均 60 独立单元（28 sync、32 reset），全部端点核验失败为 0；mapping 仅 4 独立同步单元、0 复位独立单元。完整逐对证据 packing_pair_complete_witnesses.json 证明 28 对 packing（16 SRL2 + 12 LUT6QQ），共 56 级；其中 LUT6QQ 隐藏首级按实际 FFAPPMUX_SEL=SRQ、两级 INIT/SET 参数、L6QQ 后级输出/邻接核验。mapped PAP_NOPRUNE=TRUE 保留数为 0；综合实际 60 个目标均具有该属性。

map ADF SHA256：863916ca699d2142e45dc315227d66657cb9f11a57718ce950b087feaa00cf3a。

map native DB SHA256：d2a076cd3d17401f415688eb45c37856462a1759fc8bcc4eed396fbc49272373。

三个 dev_map 整数零选项真实执行；mapping 日志 exit 0、errors 空。compile/synthesis/map 的 DB、ADF、raw dump、graph hash 均独立通过。map01 全文件、1022 保护文件、741 活动输入与 build02 源/runtime guard 无差异；属性删除后字节逆变换精确。

后续官方接口 help probe 真实失败，不能算通过：顶层 Tcl 的 define_attribute -help 报 invalid command name 和 Flow-0163。完整错误见 evidence/mapping_api_help_result.json 与 mapping_api_help.log，已进入 final_result.json / independent_audit_result.json。该脚本里的 dev_map -help 已实际打印并完成；完整选项见 current_mapping_api_review.json，没有 FF pair/SRL2/LUT6QQ 禁止 packing 开关。define_attribute 顶层不可用不等于 LCF PAP_LOC 必然不可用；后者必须由隔离 map03 的实际 LCF 注册、目标绑定、PCF 与 export_fdc 证明，不猜测或忽略错误。

官方 ADS syn_noprune 的 scope 是综合保留；官方 UCE 明确 FF pack 无视 PAP_DONT_TOUCH。这些文档均不能承诺 anti-packing。map03 是主唯一 --run 条件 waiter 所有，未由本会话重复启动。twoFF 方法成功也不等于完整 60 单元 gate 成功；若方法有效，仍需全 60 的独立 map04 和 semantic regression。

生产 gate 保持阻断；没有设备、远程、烧录、PNR 或 timing PASS 声明。本任务未修改 build02/controller、主 consumer、生产 source、安装文件或旧 IP/DB。
