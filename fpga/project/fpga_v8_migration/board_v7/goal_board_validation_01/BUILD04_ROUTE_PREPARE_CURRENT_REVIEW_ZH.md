# 当前生产映射与路由准备边界

build04_route_prepare01/REVIEW_PLAN_ZH.md是准备时快照，不能当作实时结果。保留其封装hash，不改原sealed报告。

IO join02现在已完成112/112精确连接、三组差分契约、482段原始字节证据独立核验，未解端口0；准备报告中的107/112、1/3与5未解是较早快照，不能再用来表示当前覆盖。内部usedIO bank对象仍未核实，IOgate=false不变。

build04 mapping60_01最终FAIL是旧逻辑cr[0] alias找不到唯一Qdriver。实际mapped cr_ff0/opit_0_L6Q输出L6Q接cr_d1及cr_ff1/opit_0/D；新独立mapped_endpoint_review02必须证明全部60实际storage类型/初始化/复位/CE/LUT语义/时钟/链与位置，不能单靠实例仍在视为PASS，也不重写原FAIL。

fresh mailbox1320解析记录只给1280唯一物理pairs及KEEPBUF clock sink拒绝正在新build04_mailbox_clock_review01核验。2048逻辑位完整覆盖、15.238ns预算、DDR131.25及原U-B关系不变；物理pair数量必须由新真实图解释，不能复制旧1320报告或重复记录凑数。若合法共享或结构变更被证实，需重新绑定独立consumer期望和全部真实时序记录，而不是静默修改数量门禁。

mailbox review01实际完成更新：每camera的word7bit16与word15魔数10个置1位具有完全相同reset=0/成功snapshot写1/其他保持轨迹，共11逻辑位共享1真实pair。四camera共40重复逻辑记录，1320逻辑寄存器记录对应1280唯一物理pair，另728零位；原始ADIF/完整netpins/RTL归纳和old→new映射支持该等价共享。已交review02独立复核并生成仅适用于新source04身份的expectation合同；旧1320producer gate与历史报告不改、不继承。后续要求新route独立重建2048映射并取得1280×2=2560真实精确双角path记录。

KEEPBUF官方assign Z=I与精确WIDTH/port schema已核验，compile clock上的若干KEEP/DEBUG终点输出实际未连网，无storage；8拒绝反例通过。review01新副本补充该已证实identity类型后，原未改derive仍在1320门禁拒绝，保留失败。诊断clock草案维持15.238ns/U368−B4=364/DDR131.25，仅为待独立复核输入，未证明实际STA/reload有效。

最终交付仍缺新route/签核/bit、真实SRAM烧录及DONE、烧录后两组RK截图与帧运行证据。上述准备和离线核验不构成交付验收。

## 新覆盖合同独立复核后进展

build04_mailbox_clock_review02已完成独立复算、四相机周期对照和反例检查，并生成candidate_specific_expectation_contract.json。该合同绑定第四版741源/186登记和真实图，固定2048逻辑位、1320寄存器逻辑记录、1280唯一物理pair、728零位、40重复alias及2560条双角期望；原1320门禁和旧报告不改。最终新runtime在build04_final_route_runtime01单独准备，必须显式校验该合同及新route实际集合，不能仅改数量常量或继承旧报告。

官方行为导出MAP阶段受限的诊断PnR在build04_diagnostic_behavior_route01推进；只有实际PNR/gen_netlist及mapped→routed精确桥接才能补行为证明，当前无语义PASS。独立准备板级恢复执行链于recovery_execution_prepare05，只读刷新/演示，不运行programmer、不操作Flash，不暂停误认MP4进程。遵循project/AGENTS.md单实例/字节级RTL/保护IP/RAW契约。

| 用户交付 | 需要的实际证据 | 当前状态 |
|---|---|---|
| 生成新bit流 | 第四版实际60语义、路由及全部时序/IO/HSST/motion门禁，新sbit及独立delivery绑定 | 未完成，诊断PnR与最终runtime准备进行中 |
| 自行烧录 | 当次合格manifest/preflight、输入hash、SRAM vendor成功回执、DONE=1 | 未完成，未烧录新候选 |
| RK3568截图验证正常 | 同一编程/boot会话下两组XWD/PNG/metadata，真实driving-demo身份、六路及帧进展/错误记录 | 未完成，旧MP4画面不能用作验收 |

## 诊断路由完成后的实际推进

build04_diagnostic_behavior_route01已实际完成PNR/gen_netlist/switch_db，三阶段exit0。真实官方网表绑定60 storage/site/V_FFASYN、32reset锥；19行SR alias及上游reset边界变换交build04_official_behavior_review04独立闭合。setup/hold/removal负slack原样保留，不能签最终bit。

主会话实际读取新诊断route原生v7_sdt_top.prr，M15为BANKL4、Y18为BANKL5，与旧attempt03全部BANKL6不同；不把部分样例升级为IO112 PASS。build04_diagnostic_io_review01正在独立全量比较112项原生bank/电气与连接，最终新clock route仍须重新签核。

build04_final_route_runtime01已完成可执行离线producer和19反例，物理执行保持关闭。新build04_timing_reload_probe01将实际核验replacement clock/CDB/no-remap，在全机工具空闲及互斥条件下执行，不能以Tcl文本正确推定工具实际加载正确。

recovery_execution_prepare05已实际只读确认boot仍dd39b8d1-cf2d-404e-914d-45eb87278794、EP0402/BME0、父桥SBR0，真实MP4身份未变。recovery_execution_actual06已获授权先审查具体脚本，随后工具空闲时执行持久admission→实际reset/BME回读→完整qualifiedV7 SRAM→真实reboot/post-refresh。仅本次完整成功/DONE后允许reboot，未执行前不能声称新boot；不Flash、不暂停误认MP4、不运行最终candidate或viewer。
