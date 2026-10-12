官方可读模型边界（尚未绑定实际 mapped cell）

证据来源是安装目录 arch/vendor/pango/verilog/bsim 的 V_FFASYN.v、V_FFSYN.v、V_LUT5.v、V_MUX2LUT6.v、INT_LUTMUX2_UDP.v、INT_LUTMUX4_UDP.v。此文是源码分析笔记，不是官方导出网表，也不是 reconstructed mapped model。不得将其直接用于宣称 60 个 mapped FF 已通过。

V_FFASYN 的精确行为：参数默认 GRS_EN="TRUE"、SET_RESET="SET"、LRS_EN="FALSE"、INIT=0；initial 设置 qout=INIT。GRS_INST.GRSNET 为全局网络，GRS_EN 严格等于 "TRUE" 时采用该网络，否则 GRS 被禁用；GRS 是低有效。LRS_EN 严格等于 "TRUE" 时 ntLRS=SR，否则 ntLRS=0。触发集合是 posedge CK、posedge ntGRS、posedge ntLRS。执行优先级是 GRS -> INIT；否则 LRS -> SET_RESET 严格等于 "SET" 时置 1、其余值置 0；否则 CE 的 if 分支成立时采样 D；否则保持。赋值均是非阻塞赋值。SR 为高有效局部复位/置位且不受 CE 限制。

SR 撤销和 GRS 撤销本身不在事件集合中，不会立即采样 D。CE 或 D 改变不独立触发；仅在触发事件发生且优先级允许时影响 qout。二值情况下 CE=1 才采样，CE=0 保持。四态情况下 if 的 X/Z 不算真；不得把该模型替换为遇到未知复位/CE 就必然传播 X 的自制模型。边沿的 X/Z 转换应遵守 Verilog posedge 定义。参数连接必须先由真实官方导出证明。

V_FFSYN 使用相同的初始化、GRS、LRS 参数选择与 if 优先级，但触发集合只有 posedge CK 和 posedge ntGRS。局部 SR 的上升沿单独发生不会更新；SR 在 CK 触发时生效。不能从 gop 名称推定使用异步还是同步模型。

V_LUT5 的二值地址由 I4..I0 组成，最低地址位是 I0，Y 对应 INIT[address]。V_MUX2LUT6 用 S 在 I0/I1 间选择；它自身没有存储和 INIT。组成 LUT6 时两个 LUT5 分别对应上下半区，但实际哪个输入接 S、上下 INIT 及输入极性仍须官方连接证据。INT_LUTMUX2_UDP 对未知选择且两条数据相同为 0/1 时仍产生该值，数据不同则为 X；四态评估不可仅用二值 truth table代替。INT_LUTMUX4_UDP 同样必须按实际 UDP 表分析。

尚缺的行为绑定包括：gopQ/gopQ_Cell_1/gopLUT6Q_Cell_139 到 V_FFASYN/V_FFSYN 的选择；实际 GRS_EN、LRS_EN、SET_RESET、INIT；Q/QMUX、D/集成 LUT 输出、CK/极性、SR/极性、CE/常量的精确连接；源 resetcone L5Q/L6Q 和反相寄存器的内部 LUT、FF 初始化/复位值与输出反相连接。仅得到 primitive 可读源码无法消除此缺口。
