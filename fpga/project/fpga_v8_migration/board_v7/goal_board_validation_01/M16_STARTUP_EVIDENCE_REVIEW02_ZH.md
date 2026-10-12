# M16 与配置启动复位证据补充

本次读取本地两份 PDF 并保存提取文本、源文件 SHA256，以及硬件手册 PDF 第17、18页渲染图；未执行 GPIO、烧录或 DMA。原始索引为 board_hardware_manuals_perst_review01.json。

硬件手册 RK3568_MES2L50H_100H_硬件使用手册_v1.1.pdf 的 SHA256 为 fe7017cc64fdad56ece2bed92391a9071b2d0b8fb92bdc195baea0d987b395f5。PDF第17页（印刷页14）说明按键未按下为高、按下为低；图中 FPGA_USER_KEY1 网络标为 FM16，R87=10K_1% 上拉至 VDD_1V8_MAIN，C59=1uF_25V，SW8 按下接地。PDF第18页（印刷页15）明确 KEY0=M15、KEY1=M16。PDF第26–27页的 RK—FPGA连接表未列这条按键网络。第二份产品手册没有补出 M16 的主机控制连接。

因此，该手册描述的板上 M16 是按键输入，不能仅根据 RTL 命名 perst_n 推断它连接 RK 主机 PERST 或可用软件 GPIO 拉低。尚无当次实物 PCB revision 识别记录，不能把手册电路无条件当成当次板的完整网表。

还需保留电平差别：手册按键图标注 1.8V 上拉，而冻结 pcie.fdc 为 M16 声明 LVCMOS33/3.3V。此次未修改 IO 约束，未测量板上电压，也未将这一差别判为硬件故障或当前短帧根因；后续需以实际 PCB版本及原始电气资料核对，不能静默消除差别。

配置启动的独立 RTL依据来自 qualified V7 的真实综合网表：synthesize/fpga_v8_cooperative_top_v2_rfg01_syn.vm 的 refclk_perstn_debounce 内 rs1/rs2、延迟链、rstn_out/rstn_sync 都映射为 GRS_EN=TRUE、INIT=0（模块约第691230行起）。顶层 u_refclk_perstn_debounce 接物理 perst_n 与 ref_clk，产生 sync_perst_n（约第693310行）；冻结 wrapper 第559–560行把它同时接硬核 power_up_rst_n 和 perst_n。soft PHY external_rstn 也继承该信号，其 TX FSM 从 HSST_IDLE、PLL/lane/PMA/PCS复位与 power-down 状态启动。

这证明已映射的 fabric 具有配置初始化为低、随后同步延迟释放的路径，补充 RECOVERY_ORDER_REVIEW_ZH.md 中仅讨论外部低脉冲的不足。它不证明当次 SRAM配置 GRS时序、held-SBR期间桥持续保持或 release后的首次训练结果；这些仍需真实恢复试验。当前已执行清 BME及sysfs bus reset，完整 recovery SRAM重载、reboot、最终新bit烧录与截图仍未完成。
