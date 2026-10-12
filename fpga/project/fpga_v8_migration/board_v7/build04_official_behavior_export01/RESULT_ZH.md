结果：BLOCKED_OFFICIAL_MAPPED_BEHAVIOR_BINDING，不产生行为 PASS，不放行 bit。

实际原 mapped ADF SHA256：3a0478381bb9761f677937bf0a55374119fc2b6ce683d847d8a1dda2aacd5419。input/v7_sdt_top_map.adf 是该文件的逐字副本；copy_adf_binding.json 留存原路径、复制路径、大小和两个 hashes。所有 PDS 调用都只在此新目录执行，均先取得 Global\ov56401_PDS_single_instance mutex 并检查全机 PDS/GUI/TA 空闲。

help01 为真实官方 help 探索。此版 .switch_db 支持 -input/-output；.verilog.print 只打印 AST；create_vlog_netlist 没有注册，help 明确报 Flow-0160，故 help01 exit=1 是探索发现，不能当成功导出。gen_netlist 支持 -input_db_file/-func_sim_only/-sdf_annotate。

functional01 对副本实际运行 gen_netlist -force_to_run -input_db_file … -func_sim_only -sdf_annotate FALSE。exit=1，Flow-0013 明确要求 PNR phase；没有生成 sim.v，也没有运行 PNR。不能更改 ADF phase、猜写内部 DB 或调用未经支持的内部命令绕过。

native01 在架构启动期间受到外层 shell 60 秒超时终止，shell.log 尚无 .switch_db 执行记录，无完成 receipt。该窗口原样保留。已确认进程退出后，新 native02 后台运行真实 .switch_db -input 副本 -output mapped_dump.txt，exit=0，生成官方 mapped_dump.txt 及自动生成的 mapped_dump.v。不是手工重建模型。native02 的 launch/process/receipt、shell.log 和完整文件 hashes 均留存。

官方 .v 的全部 operator 模块是空 OPER 接口。没有 V_FFASYN/V_FFSYN/V_LUT 实例、always 或 assign；可证明参数/端口连接数据导出，不能证明行为。exact counts 与文件 SHA256 见 official_verilog_classification.json。重新复制原 parser 并解析该次实际 dump，绑定结果见 fresh_native_graph_binding.json；这是对新官方导出的检查，不能将既有 review02 的结构 PASS 偷换成行为 PASS。

可读 V_FFASYN/V_FFSYN/LUT/UDP 的语义分析见 OFFICIAL_MODEL_BOUNDARY_ZH.md，文件 hashes 单列保存。V_FFASYN 确实定义初值、低有效 GRS、高有效局部异步 SR、posedge CK、reset 优先于 CE 和撤销复位时保持的行为；但当前没有官方 gop -> V_* 实例/参数/极性连接绑定。60 独立 oneFF 和源 resetcone L5Q/L6Q/反相转换的行为缺口仍在。

最小所需支持：接受 MAP-phase ADF 的官方 verification/simulation exporter，输出 gopQ、gopQ_Cell_1、gopLUT6Q_Cell_139 及 resetcone 源存储到 V_* 的精确实例、INIT/GRS/LRS/SET_RESET/CE/CLK/QMUX 参数和连接；或官方可读且有版本对应的这些 gop 的完整语义。当前接口要求 PNR，任务禁止新增 PNR，因此不能在当前授权范围完成绑定。无须重跑 mapping、改 RTL 或伪造网表。

全树前后保护、review02 原始保护清单再核验、原 FAIL 保留结果见 protection_final.json、review02_protected_inputs_recheck.json、final_result.json。本轮不运行 compile/synthesis/mapping/PNR/bit/board。工具日志中的“Compiling architecture/library”是导出器加载库，不能解释成 RTL 构建通过。

review03 的独立外部审计交付见 REVIEW03_HANDOFF_ZH.md。本目录只提供审计包，不冒充独立 reviewer 或改写原 FAIL。
