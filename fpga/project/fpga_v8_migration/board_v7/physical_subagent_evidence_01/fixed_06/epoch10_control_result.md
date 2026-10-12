# 新综合拓扑对照成功

`synthesis_epoch10/topology_validated.json`、synthesize_result.json 和独立导出/解析结果确认：未加载 mailbox compile实例约束的真实新综合恢复1280实体对，每路320，补集748/748/755/755，manifest/exact_complement无错误，保护1022文件未变。

结合native08的1320实体对及40逐位映射差异，该对照支持compile阶段约束改变寄存器合并的解释。后续应在独立副本验证综合后约束加载及传递，确认1280实际对全覆盖，再map/pnr。当前epoch10只关闭综合拓扑对照，不授权直接map/pnr。

exact09已产生实际routed DB，其签核仍在活动audit_fixed.py进程75608中；failed父控制器并不证明所有子进程已结束。后续工具启动需检查audit控制器和PDS/TA/de空闲，避免在audit两次PDS调用之间抢占。
