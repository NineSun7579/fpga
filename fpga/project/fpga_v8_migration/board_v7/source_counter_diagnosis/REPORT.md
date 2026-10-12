# CAM1/CAM2 source counter 本地 RTL 诊断

2026-10-06，ModelSim SE-64 10.6e 实际执行。冻结源直接编译，未编辑生产或冻结文件；SHA256 在 source_hashes.txt，runner 比较运行前后字节哈希。全部新增文件位于此隔离目录。未 remote、未烧录、未处理 DDR 末拍门控。

复现命令（工作区根目录）：

```powershell
python project/fpga_v8_migration/board_v7/source_counter_diagnosis/run.py
```

## 结论与实测

未复现 slice/prefix counter 的 RTL 算术丢计。正常 1280 bytes × 480 lines，16-bit 打包，确实得到 307200 valid，源快照同为 307200、drop=0。现有证据不能选定硬件根因，也不能把板上稳定短帧解释成已证明的快照误差。

| 测试 | 实测结果 |
|---|---|
| 连续 valid 70000 拍（同时 full） | count=70000，drop=70000 |
| 交替 valid | count=35000，drop=17381 |
| 每 17 拍一个 valid | count=4118，drop=2037 |
| 固定种子伪随机 valid/full | count=34642，drop=17131 |
| 8 个 nibble 进位边界，包括 32-bit 回卷 | 全通过；一致预状态 deposit 后运行原 RTL 20 次真实递增 |
| 帧起始与 valid 同拍 | 旧窗口 31，新窗口 1，总计 32，无丢计 |
| 全尺寸窗口边界转移 | 快照 307199、307201，总计 614400 |
| 480 行，每行 1280 bytes | valid=307200，snapshot=307200，drop=0 |
| 1/2/7 行各减少一个 byte | 分别 307199/307198/307193，snapshot 与实际 valid 一致，drop=0 |
| VSYNC 与 16-byte 行重叠，偏移 0..16 | 每次均输出 8 valid；源窗口 scoreboard 全通过 |
| 一个 1280-byte 行拆成 HREF 高 1 byte + 低 1 拍 + 高 1279 bytes | 实际只有 639 valid，输入接受字节仍为 1280；真实打包损失 |
| 正常间隔 source snapshot，cam 周期 2ns/video 周期 10ns | 30 个事件全部接收，字段组合完整 |
| 极端每 4ns 一个帧事件、video 周期 10ns | 累计发出 130 个快照，只观察到 50 次 seq 更新、19 次 seq 跳变；无字段撕裂 |

simulation.log：ALL_PASS source_checks=3369986；snapshot.log：SNAPSHOT_ALL_PASS。编译 0 errors/0 warnings；仿真仅有环境已有 -novopt 性能提示。EXPECTED_LIMIT 是成功复现的功能限制，用断言确认存在，不代表正常协议下测试失败。

## 为什么窗口转移不等于丢 valid

ov5640_cdc_tc04.v:45、76-105：检测 s_vsync 上升沿时 snapshot 保存旧 src_count；当拍 s_valid 被写入新窗口的 count=0/1。它既不会被清掉，也不会双计。持续短计若仅由边界移动造成，连续完整窗口的总量应有补偿或边缘余量变化；本次直接构造 307199+307201 证明这一点。不能只读离散的几个短窗口就断言守恒，也不能用这个机制直接解释所有帧长期都 307199。

同文件 71-72：prefix 下一状态由旧 count 的高位全一和最低位 XOR increment 计算；increment=0 时保持全一条件，increment=1 时识别旧低位 ...1110。逐拍参考模型检查完整 32-bit count/drop、snapshot、全部七个 prefix。稀疏、连续、边界重合均与普通加法计数模型一致。

cmos_capture.v:104-119、124-149：每个连续 HREF 高片段每两字节产生一个 valid，HREF 低拍把 temp_cnt 清零。因此行长度 L 输出 floor(L/2)，多个高片段输出 sum(floor(L_i/2))。奇数字节尾部会被丢弃。上述 short_lines 和 1+1279 测试是输入条件下的可复现真实 deficit；未证明板上发生了相同输入条件，更未证明这些输入条件来自硬件。

## Snapshot CDC 检查

ov5640_cdc_tc04.v:109-140：96-bit snapshot 经过两级采样；toggle 经过三级同步后再比较 seen，数据比通知多一个目标周期的稳定余量。正常长帧间隔下，本次异步时钟和快慢时钟测试均无错误。

但这是没有 ack 的 bundled-data/toggle 方案。源数据没有等接收确认才允许改写；极短间隔帧事件会丢通知，实测已复现。零延迟 RTL 没有亚稳态、位间布线偏斜，不能证明物理实现绝无 96-bit 撕裂；仍需 CDC/时序约束证据才能闭合。不能把极端 4ns 帧事件的限制直接映射成板上正常帧频的 -1/-2。

此外 inputs/source/ov5640/ov5640_reg.v:270-273 按独立 AXI 读返回 input/output/drop/seq，没有把四次软件读自动锁成同一组。跨更新时刻的软件多寄存器读取可能混帧，属于读窗口一致性，区别于上述位级 CDC。应以 seq-before / counters / seq-after 相等为一致读依据；本次未模拟 AXI 主机读取。

## CAM1/CAM2 接线与参数静态对照

冻结顶层 rtl/fpga_v8_cooperative_top_v2_rfg01.v:1037-1100、1246-1305；共用模块 rtl/parent_tc04_c40cee500c37.v、rtl/ov5640_tc03_binding.v。

| 项目 | CAM1 | CAM2 |
|---|---|---|
| 外部 PCLK/VSYNC/HREF/data | cmos1_* | cmos2_* |
| source clock | 各自 cam_pclk，无源计数时钟分频 | 相同拓扑，各自独立输入 |
| video clock/reset | axi_clk / axi_rst | 相同 |
| 配置 clock/reset | clk_50m=free_clk / camera_ctrl_rst_n | 相同 |
| DATA_WIDTH / capture DELAY / WAIT_FRAME | 16 / 2 / 10 | 相同 |
| H/V / TOTAL_H/V | 默认 640/480、1896/984 | 显式相同值 |
| SENSOR_PLL_MULT | 默认 8'h54 | 默认 8'h54 |
| VSYNC_STABLE_CYCLES | 默认 0，直接旁路 | 默认 0，直接旁路 |
| IODELAY_STEP 默认参数 | 显式 140 | 默认 40 |
| MEDIAN_EN/KF_EN | 0/0 | 默认 0/0 |
| KF_RD_EN | 显式 0 | 默认 1；KF_EN=0，且不在 source 计数前 |
| BASE_ADDR / 帧缓冲地址 | 20000000 / 00800000、00A00000 | 20000200 / 00C00000、00E00000 |

IODELAY 的 DELAY_STEP_SEL="PORT"，实际由 reg_dly_step 驱动。140/40 是参数差异，不能代替运行时寄存器实值；用户已提供所有 runtime delay 均有 short 的证据，本报告不据此选择 delay 或硬件根因。

双路均有相同复位分工：capture.rst_n=ov_rst_n=rst_n & cam_init_done；source counter.cam_rst=!cam_rst_n，其中 cam_rst_n=i2c_start_en。capture 与 counter 的释放时刻并不相同，但没有发现 CAM1 独有的连接。capture 输出到 CDC 前还存在 negedge cam_pclk 寄存级（ov5640_tc03_binding.v:354-359），没有 reset。本 TB 复制该寄存级以保留正常运行的半周期关系；未模拟 I2C 初始化与分别释放复位的全过程。首帧、复位附近统计须独立于 stable 帧解释。

## 范围与下一步 RTL 证据

- 实际编译两个指定冻结模块；FIFO 使用明确标注的 full 可控、empty 恒高 stub。只验证 capture、source/drop 计数和 source snapshot；不验证 FIFO 存储、video output count、DDR 或 post-route timing。
- capture 采用真实默认 WAIT_FRAME=10，提供 11 个启动 VSYNC；全尺寸正常帧和受控异常输入均运行。高位进位测试使用 TB deposit 一致状态，未声称从零跑了 2^32 拍。
- 当前最有区分力的新增 RTL 观测是每帧 accepted-byte 总数、每行 HREF 高长度奇偶/最小值、HREF 分段数、capture valid 总数，以及连续 seq 的 source 快照累计量。这样可以区分“字节实际少/片段奇数导致打包少”与“只移动计数窗口”。这只是后续诊断建议，本目录未改生产 RTL 或插入探针。
- 未发现能在正常完整输入条件下稳定制造 307199 的 source counter 算术缺陷。板上 CAM1 的 short 根因仍未闭合，不能据本报告转为硬件归因。
