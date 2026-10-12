# 相机 CDC 隔离候选

候选：`rtl/ov5640_cdc_tc03.v`，模块名 `ov5640_cdc_tc03`。源自 V4 冻结输入 `whole_candidate_v4_route_01/inputs/source/ov5640/ov5640/ov5640_cdc.v`，按字节读取并以 GBK 解码；隔离副本使用 UTF-8。不修改工程绑定或整机 runner。

V4 相机失败共 8 条，均为 cmos2_pclk falling→rising 半周期路径（5.952→11.905 ns）。完整路径显示 count[31]、drop[31] 各经过 7 次 CECO，后续每段 CECO 增加约 0.136 ns；drop 最差 slack −0.708 ns、count 最差 −0.170 ns，时钟偏斜分别 −1.826/−1.808 ns。drop 路径在公共帧条件后还有 drop 判定一级；不能只考虑算术进位。原始完整路径及逐条分析见 `camera_artifacts/camera_failing_paths.json`、`camera_path_analysis.json`。

只将 src_count/src_drop 拆成八个 4 位独立更新段。段 i 的增量条件为原计数使能与旧计数低 4i 位全 1；低段直接使用原使能。所有段同拍更新，相当于模 2^32 加一。cam_rst 异步清零优先于帧起始；帧起始仍先快照旧计数，再把该拍有效数据计入新帧。src_seq、采集/FIFO、同步、快照通知及全部公共接口保持原代码行为，不增加流水级。

执行：`python project/fpga_v8_migration/timing_correction_03/run_camera_tests.py`。可使用 MODELSIM_BIN/PANGO_SIM_LIB 指定工具路径。脚本仅启动 ModelSim，读取冻结 V4 FIFO IP 及厂商 GTP_DRM18K_E1/GTP_GRS 仿真模型；DATA_WIDTH=16，与实际 V4 FIFO 宽度匹配。

回归：3 组异步时钟比例 × 4 随机种子，每组 24,000 随机输入拍。覆盖自然 FIFO 填满/drop、排空/正常像素、vsync/hsync、同时 valid/frame/full 时的 reset、异步源统计清零、每个 4 位边界及 32 位回绕、帧起始与 full 组合。全部 8 个公共输出在两时钟正负边沿 NBA 后逐拍比较，同时检查内部统计快照及 FIFO 控制；另用独立 32 位加法 oracle 验证计数。32 个定向边界/组采用统计寄存器 deposit 和短期 full force 加速覆盖，自然 full 场景没有 force。

12 组通过。日志、测试输入 SHA256、覆盖计数和保护文件哈希清单见 `camera_artifacts/results.json`、各 `sim_*.log` 及 `protected_sha256.json`；可阅读 `camera_candidate.diff` 审查功能改动。

限制：这是 RTL 差分回归证据，不是穷举形式等价证明；没有验证亚稳态或物理 CDC 约束。尚未启动 PDS，不能断言综合一定保留分段 CE，也不能断言 8 条时序违例已经消除。需要后续在独立整机候选中检查综合 CE 映射、扇出和实际布线报告；本交付未改变 V4 输入或生产 source/ipcore。
