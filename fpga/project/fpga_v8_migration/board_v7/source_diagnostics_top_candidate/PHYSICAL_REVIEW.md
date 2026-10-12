# 物理约束评审清单（未运行 PDS）

`hierarchy.txt` 来自完整 top 的 ModelSim `find instances`，不是根据模块名猜测。
`diagnostics_signals.txt` 来自实际加载信号；`physical_manifest.py` 对所有目标存在性断言，
生成 `physical_hierarchy.csv/json`。综合后需重新解析实际 cell/pin，不能把仿真寄存器向量
名字直接当成 PDS 综合 cell。当前没有 Fmax、面积、亚稳态或约束覆盖签核结论。

顶层实例相对路径为 `source_diagnostics/cameras[0..3]/source`。
物理清单逐路展开，不使用会误选其他候选的全工程通配符。
camera parent 的相对路径是 `ov5640_top/ov5640`、`cam2_ov5640_top/ov5640`、
`cam3_ov5640_top/ov5640`、`cam4_ov5640_top/ov5640`。

1. 根时钟保持 free_clk=25MHz，四个 DVP cmosN_pclk 及实际 DDR 输出 axi_clk
   使用原时钟树。不能沿用本 TB 的10ns host/14ns camera 周期作为板级约束。
2. request → req_sync[0]、ack → ack_sync[0]、sticky_overrun → overrun_sync[0]
   为异步控制路径；同步级间路径保留目标域正常时序，识别 ASYNC_REG 并限制布置间距。
3. mailbox[511:0] → host_bank[511:0] 是稳定数据邮箱，request 三级同步后另拍复制。
   要求 bundled-data max_delay 不大于两个实际 AXI 周期；必须检查例外优先级，
   禁止全局 async clock_groups/false_path 把这个 max_delay 静默屏蔽。
4. 每路 `source/cr`、`source/hr`、`cameras[N]/reset_pipe` 为异步置位、同步释放链。
   异步 reset 合并输入来自 binding 的 !ov_rst_n | !cam_rst_n，另有 host reset。
   必须签核最小脉宽、恢复/移除与跨域解除；2ns 数字仿真脉冲不是器件最小脉宽证明。
5. binding 内 cmos_frame_valid_r / cmos_frame_vsync_r 是原下降沿寄存器，
   到诊断 valid_d、vs_q 以及计数逻辑是同 PCLK 的半周期路径，不能 false-path。
   raw_vsync/HREF 是真正进入 capture 的信号；CAM3/4 VSYNC 经64拍资格化，
   HREF 保持 parent IODELAY 接线。保持输入延时合同。
6. epoch[0..3]、read_epoch、INDEX、AXI response 状态都是 AXI 域普通逻辑。
   reset不能把它们视为相机域逻辑；epoch32位加一及饱和检查仍需时序签核。
7. 原 RAW/6cam/motion/COOP/CAPL 时序约束继承，但新增扇出/放置可能改变其时序。
   实施物理流程前需评审这份实际层级清单；本候选没有替代物理签核或启动工具。
