# 实际候选集成状态

三项候选全部已核验并实际集成。物理签核尚未通过。
lease: rtl/v7_sdt_top.v 唯一 u_v8_capture_lease -> fpga_v8_capture_lease_prefix; 9/319624 PASS。
camera: inputs/source/ov5640/ov5640_reg.v; 6/130140 PASS; CSV 全输出逐行差异 0。
control: rtl/fpga_v8_capture_control_axil_arm_v2.v; 18/861948/49 signals + 26488 cycles/499 ops PASS。
只有上述三项源差异，其余冻结输入逐字节保持。无 CDC 修正候选。
约束 exact11 仅作候选；新 compile/syn graph 必须重新推导完整叶节点、U-B、1320 mapping。
无物理 graph coverage PASS 不得 PNR；无十组/IO112/HSST/motion32/mailbox1320 SlowFast/reset32/sync 实测 PASS 不得 bit。
实际阶段与启动日志见 controller_status.json 和 evidence/。无 remote/program。
