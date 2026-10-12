本轮真实结果：FAIL_FRESH_MAP_QUALIFICATION

compile/synthesis/map及原生导出全部rc=0、errors=0。新mapped CDB确有4条15238ps datapath-only预算，逐对绑定1280动态关系；无旧CLKGP。

完整mapped图有1284 unique，要求1280，未通过。多出的4条是每路host_bank[480] ← mailbox[480]/Q；mailbox D接原生常量1，launch/capture无预算注解。本轮保留这些真实对象，没有删掉计数，也没有为它们加falsepath。

production60：60个独立sourcepath/site，PCF精确命中60/60；mapped类型 {"gopQ": 28, "gopQ_Cell_1": 24, "gopLUT6Q_Cell_179": 8}；原exact gopQ gate通过28/60，未放宽其类型检查。详细ports、params、PAP_LOC、PCF见FINAL_REAL_MAP_RESULT.json。

源码741与冻结build04逐文件字节一致，登记186，冻结保护drift=0。官方remove_dups/const_prop/control_set_num=0保持。

PNR未启动，global10未实测；旧Setup -0.071、Hold -1.711、Removal -0.038仍为失败事实。未bit、未远端操作。当前只能交付失败的真实fresh map，不能声明可用PNR输入或时序修复PASS。后续需要验证能在既定保持要求下消除残留签名storage并恢复60目标存储模型的官方流程；目前无该成功证据。
