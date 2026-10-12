# diagnostic_sync_register_map02 实际属性对照结论

结论：FAIL。实际 mapped 独立存储单元 4/60（同步 4/28，复位 0/32）。

只对 60 个显式原语实例加 syn_noprune=1；移除新增属性逐字节还原原 primitive 源。compact wrapper、输入输出、时钟和功能周期未变。

旧 synthesis 的 24 项端点失败为审计解析范围不足：12 项原信号已规范为真实 Q 引脚，12 项常零经过 INIT=10 的 LUT1。新审计按实际 pin/net、LUT INIT 求值并验证异步复位 OR 真值表，不跳过 INIT、reset polarity 或 CE。旧 compile/synthesis 重新核验均为 60 级全部通过，证据保存于本目录 baseline01_*，map01 无改动。

真实 mapped 失败类型：{'gopSRL2_Cell_2': 12, 'gopLUT6QQ': 12, 'gopSRL2_Cell_1': 4}。逐端点、属性传播与完整 hash 见 evidence/attribute_propagation.json、*_endpoint_details.json、final_result.json。

官方 User Constraint Editor 手册 PDF 第 94 页（页内编号 93）明确：PAP_DONT_TOUCH 作用于 GTP 实例/module，但 FF pack 无视该属性。安装的 19 本官方 PDF 全文检索记录在 official_packing_scope_search.json。该属性不能作为已证实 anti-FF-pack 方案；不得猜 packingdisable 或忽略 unknown option。

生产 gate 保持阻断。map01、build02 源/runtime、741 活动输入及 1022 原工程/旧 IP 文件 guard 均核验。未进行 PNR、时序放宽、设备、远程或烧录操作；不宣称 timing pass。

compile ADF SHA256: 0a0be4b0f0a375693c0779e071770a1b128b78dbd35d340082d87ab90109cccb
compile native DB SHA256: ebebeac59be997fdeea7d237a4fc1bd9b9958ff8d981833c17e4a5989ea7655c

synthesis ADF SHA256: bb26cb3141880fe37053bc0aa688186415d491840b1bfcca8e39cc20f3e2b60a
synthesis native DB SHA256: 3b829e1d1e612e80edbc4ca56431a2af5f685e72fad3029805f8911e66b38825

mapping ADF SHA256: 863916ca699d2142e45dc315227d66657cb9f11a57718ce950b087feaa00cf3a
mapping native DB SHA256: d2a076cd3d17401f415688eb45c37856462a1759fc8bcc4eed396fbc49272373
