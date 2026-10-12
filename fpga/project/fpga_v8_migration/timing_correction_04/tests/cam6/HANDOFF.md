# TC04 实际 cam6：ModelSim 与最终审计 PASS

候选：`../../rtl/ov5640_ddr_tc04.v`。

SHA256：`b6df963cf6619b0aa723fc7aa105a64f16306415dc8681f3e4309cc5fe520702`。

真实参考是 `whole_candidate_v5_route_01/inputs/source/ov5640/ov5640_ddr/ov5640_ddr.v`，
不是 fpga_v8_capture wrapper。路径 23/24 full_detail 两者 slack -0.005ns，
终点为 cam6 pixel_count[0]/CE 与 pixel_count[31]/CE，均有 7 级 CECO。
完整原报告保存在 `../../receipts/cam6/v5_paths_23_24_full_detail.json`。

只改原 32 位 pixel_count 表达：每位无条件时钟赋值，XOR 前缀进位与数据路径清零。
动态地址/长度、全部参数/端口、reset/flush/SOF 优先级、所有综合 debug 属性及其余
逻辑保持原样；`interface_logic_audit.json` 验证公共声明与非计数器 RTL token 一致。
原 tag 偏移的参数语义也保留，未偷偷改为动态长度或固定 cam6 wrapper。

独立测试以实际三个 V5 w_*、两个实际 FIFO IP、PANGO RAM/GRS primitive 绑定运行。
三组 ModelSim `(LEN,SEED)=(38400,1)/(38400,29)/(2048,202603)` 全部通过，
逐拍比较全部 20 个公共输出共 566 位（含无效周期），并核对内部计数器。

| 指标 | 实际结果 |
| --- | ---: |
| 比较周期 | 3,646,012 |
| 成功 publication | 24 |
| 自然实际 FIFO overflow 周期 | 3 |
| 每位 increment/hold/reset carry 与 wrap 案例 | 288 |
| 动态长度/地址场景 | 18 |
| 零长度拒绝 | 3 |
| 短帧 fault | 32 |
| 受保护文件 SHA256 一致 | 2,122 |

stall、完整帧、短帧 restart、DMA abort、实际 FIFO 满后 reset 恢复、动态
0/1/7/129/半长度/端口最大值，以及背压中地址/长度变化均由真实仿真覆盖。
`results.json` 仅在所有仿真和输入/保护 SHA 通过后生成；`final_audit.json` 再次
核对日志指标、实际模块加载、源文件 hash、父副本及 23/24 路径。
results SHA256：`da372f6fa37afa904923adad551dd1e34a81f660bb4eaa25fe6e1c79529ed1ac`。

实际父绑定在 `../../receipts/cam6/bindings`，对应清单 `parent_bindings.json`：

| V5 父文件 | 原 ov5640_ddr 实例（原行号） |
| --- | --- |
| rtl/fpga_v8_cooperative_top_v2_rfg01.v | cam6_ov5640_ddr (1647) |
| inputs/source/ov5640/ov5640_top.v | ov5640_ddr (499) |
| inputs/source/HDMI/hdmi_top.v | ov5640_ddr (242) |
| inputs/source/top.v | cam5_ov5640_ddr (1796), cam6_ov5640_ddr (1877) |
| inputs/source/insert_sfp_block.v | cam5_ov5640_ddr (63), cam6_ov5640_ddr (144) |

这 5 个副本仅将全部 7 个实例的模块类型替换为 ov5640_ddr_tc04，实例名、参数、
连接和全部原 GBK 字节保留；反向替换恢复原文件已审计。活动顶层 cam5 的
fpga_v8_capture_ov5640_ddr 不属于原 ov5640_ddr 实例，保持原绑定。
副本可作为后续隔离工程替换输入；未安装到生产或 V5，未改 PDS 工程。

复现：先执行本目录 `run_cam6.py`，再执行 `audit_cam6.py`。
已有 stream_capture runner/回执及生产、V5、TC03、TC02 均未修改。首次仿真
结束后因另一个独立 DMA 子任务更新自己的 tests/receipts，广义 hash 保护失败；
保留首次 baseline 和变动清单，然后明确排除非 cam6 输入的并发 DMA 产物完整重跑。
cam6 从未写 DMA 或其他候选/runner。

局限：高位 carry/wrap 使用双方配对 state deposit；仿真数据/AXI 宽度为 16/128，
地址/命令长度宽度为 32。全部父副本是字节绑定审计，未做整机层级 elaboration。
没有启动 PDS、综合或布线，故不声称 CECO 已被综合消除、slack 已改善或整机时序通过。
