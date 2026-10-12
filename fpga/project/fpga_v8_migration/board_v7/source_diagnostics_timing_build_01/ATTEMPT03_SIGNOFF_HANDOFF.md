# attempt03 实测交接：尚未完整签核，禁止 bit

实际路线：route_attempt_03/place_route/v7_sdt_top_pnr.adf，SHA256 `7a12da9bc428b398a3d38a60f1ae53d85913e1fa621026d42ca0a62368d2a9cc`。官方 compile/synth/map/PNR 已完成，seed2 与 route constraint iteration 实际进入 impl.tcl。最终 compile/synthesis 图重新 derive，clock.fdc 与原 routed 输入字节相同；完整 U368、364+4、2048逻辑映射/1320配对与实际 receiver CDB 继承证据保留。

已实测通过：

- 十组 STA 全部无失败端点。Slow Setup +0.342ns，Hold +0.021ns；Fast Setup +2.278ns，Hold +0.082ns。全局 MPW 最差+0.011ns。
- mailbox 21 batch，Slow/Fast 各1320/1320，无缺失或意外配对，最差13.774/14.356ns；实际预算15.238ns，shell/run过滤日志无Timing4006/STA3016/unknownoptions。
- HSST位置/专用连接与基线相同，motion 32 DRM36K（614400逻辑bit）实测证据完整。
- IO112全部pin/位置/电气属性相同，全部实际IOB/IOL物理site与attempt01一致。新报告bank列全为BANKL6，与冻结报告不符；该工具报告异常未删改，必须独立审查。io_audit保存逐port异常与实际site对照。
- reset共享物理CLK的High/Low脉宽：Slow/Fast各20/20物理时钟、对应32逻辑级，High最差3.609ns，Low最差3.610ns；80个真实MPW表格行及行号保留。MPW是表格，不是Startpoint/Slack record；-to不筛选全局MPW表，精确物理目标在表内匹配，不能宣称MPW target filter筛选表已生效。
- 外部sync两角实际报告通过。

仍阻断签核：

1. reset Recovery/Removal只覆盖12个物理RS（对应24个逻辑级），8个camera cr[0]/cr[1]仍无报告记录；单物理RS小报告也无记录，日志无目标忽略标记。不得把空报告当PASS。
2. 8个SRL打包内部sync路径没有外部D pin。当前证明仅为同CLK、两级直连、异步入口/参数/INIT与RS信号来源，不是独立实际时序检查。
3. IO bank列异常需独立审查，实际物理位置对照并不授权伪造bank行或覆盖冻结表。

缺失reset的原因线索：最终真实synthesis图逆向扇入中camera0 cr/P的发起寄存器为cfg/init_done、ddrphy_dfi/dfi_init_complete、i2c_start_en、camera_ctrl_rst_n。runtime_clockpair_proof的实际clock interaction显示ddrphy_sysclk→cmos1_pclk为False Path。这是保留U-B约束的一部分，当前不能修改冻结例外来制造签核；其余camera与SCCB/free_clk扇入应继续逐一证明，不能仅凭该线索宣称全部缺失原因已确定。

实际结果：route_attempt_03/evidence/actual_result.json 与 evidence/reset_mpw_routed_audit.json。所有原始报告保留，无bit、remote/program、accepted/reviewer。当前没有待运行的本代理PDS任务。要完成原门槛，仍需取得工具支持的SRL内部级实际检查及被保留异步例外影响的reset检查证据，或由主会话明确改变验收范围；未经变更不签核、不产validatedDelivery。
