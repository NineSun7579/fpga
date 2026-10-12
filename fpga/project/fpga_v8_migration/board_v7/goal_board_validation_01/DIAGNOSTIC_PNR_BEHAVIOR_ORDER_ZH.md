# 官方行为导出的 PnR 依赖处理

export01实际gen_netlist拒绝MAP阶段，明确要求PNR phase；switch_db导出的5199 OPER仅接口空模块，无V_*行为绑定。安装可读V_FFASYN等模型存在，但不能凭模型文件存在推定实际gop参数和连接。

为补足证据，新build04_diagnostic_behavior_route01已获本会话执行授权并交独立执行：复制真实fullsource/compile/synth/map/native/PCF与旧映射约束到隔离目录，只从实际mappedADF执行官方PNR再gen_netlist功能仿真导出，不compile/synth/dev_map、不修改旧文件，不bit/烧录/远程。

这次diagnostic PNR不采用尚未独立核准的新1280 clock草案。即使PNR完成，也不是最终准确预算/完整时序/IO签核，不可作为新bit交付放行。原始STA负slack或IO bank异常保存，不能覆盖失败；行为证明和位置/端点跨阶段对应才是本次使用范围。

先做诊断PnR避免“需要完整行为模型才能PnR、导出行为模型却要求PnR”的循环。最终仍须新candidate-specific2048/1280合同、15.238ns/U-B/DDR精确实际加载证明、60完整语义及全部物理时序门禁；随后才能生成bit并SRAM烧录、采集至少两组RK烧录后截图与帧运行证据。
