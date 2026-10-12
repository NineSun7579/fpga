# build01 相机2半周期 Setup 定位与独立 RTL 候选

结论：实际 final STA 的三条失败均属于 `cmos2_pclk`，下降沿发起、上升沿捕获；是相机 frame-vsync 对诊断计数器和 CDC drop-prefix 的同步清零路径。实际路径中没有 AXI 相机 read 地址译码，也没有 DMA 数据通路。优化优先级应是清零控制的最终布尔门控与物理局部性，不能把该故障归因于 DDR 或接入 DMA v2。

所有本轮新增/修改文件仅位于 `build01_global_sta_review01`。没有启动 PDS，没有重复轮询后台任务，没有修改 build01/build02/map02、控制器、队列、输入时序或原约束，没有远程/设备操作。原 final STA 工具成功，旧解析器因无 Slack 的未约束路径失败；修复后完全离线使用同一报告。

## 实际 routed 输入与十组核验

- routed ADF SHA256：`e3dd999b8b352ed34cc7d6f34faea48893d2ee626ead6b8a0004928c46d2e847`。
- final STA `.rtr` SHA256：`e87f8d8239e9fc2b0de63e6495ee1faa30598dc9455099dc0aa84a31c800d058`。
- 原冻结 `evidence/input_hashes.json` 共 **747** 项：再次逐项验证全部不变。
- final STA 的十组都有实际数据行；MPW Slow/Fast 各 **19** 个时钟行、各 **0** 失败端点，最差均 **+0.011 ns**。
- PNR after-hold-fix 内嵌值为 **−0.853 ns**；独立 final STA 为 **−0.882 ns**，TNS **−1.733 ns**。优化和复核使用 final 值，不能混用。

| 检查 | Slow 最差 ns | Fast 最差 ns | 失败端点 Slow/Fast |
|---|---:|---:|---:|
| Setup | −0.882 | +1.501 | 3 / 0 |
| Hold | +0.242 | +0.174 | 0 / 0 |
| Recovery | +1.429 | +2.373 | 0 / 0 |
| Removal | +0.287 | +0.247 | 0 / 0 |
| MPW | +0.011 | +0.011 | 0 / 0 |

这证明已报告路径的十类检查结果，不表示整机全部约束/功能 PASS。报告额外有 **1598** 条无 Slack 的路径，单独保存在 `final_unscored_paths.json`；sync packing 的失败也是独立门禁。

## 三条真实逻辑锥

共同 launch：`cam2_ov5640_top/ov5640/cmos_frame_vsync_r/opit_0_inv/CLK`。RTL 在负沿采样 cmos_frame_vsync；对应诊断与 CDC 正沿更新，名义数据窗口 `11.905 − 5.952 = 5.953 ns`。没有缺失一个周期的流水寄存器可直接插入；增加一级会改变帧边界、计数归属和 mailbox 快照，需要另一个功能契约。

| Endpoint | Slack ns | Logic ns | Route ns / 比例 |
|---|---:|---:|---:|
| `source_diagnostics/cameras[1].source/cg/q[10]/opit_0/D` | −0.882 | 0.504 | 7.746 / 93.891% |
| `source_diagnostics/cameras[1].source/cg/prefix[1]/opit_0/D` | −0.692 | 0.629 | 7.328 / 92.095% |
| `cam2_ov5640_top/ov5640/ov5640_cdc/drop_prefix[7]/opit_0_inv/D` | −0.159 | 0.684 | 5.023 / 88.015% |

第一条：`diag_capture_vsync[1]`（fanout 8）→ `N8` / `edge_vs`（fanout **174**）→ `N35` → `cg/N80[2]_2` → `cg/q[10]`。末端 `cg/N80[2]` 仅 fanout 1，仍有 **5.842 ns** 布线；因此不能仅凭“增加 carry pipeline”判断可修复。实际是帧清零选择经 LUT 到寄存器，非宽 ripple-carry 的串行传播。

第二条共享 edge_vs/N35，然后 → `cg/N84` → 数据信号经过 `CLKROUTE_151` → prefix[1]。两段布线分别 **2.881 + 2.540 ns**，数据 CLKROUTE 额外 **0.125 ns**；物理映射局部性是主要问题之一。

第三条：`diag_capture_vsync[1]` → CDC `N14` / `src_frame_start`（fanout **157**）→ `N391_13` / `N428` → `N391_16,N391_20` / `N404` → `N436_6` → `drop_prefix[7]`。`src_frame_start=s_vsync & !src_vs_q` 是晚到控制，不应放进 28 位 prefix 数据计算再经过多层清零选择。prefix 本身已经是提前预测的寄存器，不应再加一周期。

原始三条报告完整块及各自 SHA256 位于 `actual_negative_path_01/02/03.txt` 与 `camera_cone_evidence.json`，保留工具的真实 launch/capture、所有 LUT/net 名称和延迟。

## 独立可验证候选

候选在 `camera_boolean_candidate01`；golden 是实际冻结源仅重命名 module，候选用 Python 字节级 ASCII 替换生成，原 GBK 注释字节不经 decode/re-encode。生成脚本、diff 与全部源/候选哈希均保留。

1. gap `cg` 专用候选保留原饱和 inc 条件、同拍 clear 优先级和输出宽度，将每个 4-bit slice 写成 `q_bit_next=(q_bit XOR toggle_bit) & !href & (!capture_vsync | vs_q)`。carry 仍使用已注册 prefix；晚到 capture_vsync 只参与最终布尔门控，不经加法器。prefix 为 `predict_all_ones & !href & (!capture_vsync | vs_q)`。
2. 原通用 counter 的 clear mux 改为最终 bitmask，低 slice 的 seed 为 `clear & seed`。原 `next_q` 不受 clear 影响的组合输出保持不变，保护 odd_next 与 seq_next 的快照语义。
3. CDC count/drop-prefix 采用 `prefix_pred & (!s_vsync | src_vs_q)`；全计数、快照、toggle、video 同步与 FIFO 实例保持原始字节。高位 prefix 的 all-ones 预测来自旧 state，不增加延迟、不改变 wrap 或帧清零种子。

布尔恒等式：`!edge_vs = !capture_vsync | vs_q`。对 n>=4，计数下一状态全1的条件为 `(&q[n-1:1]) & (q[0] ^ inc)`；clear 后的新值至多1，故 prefix 必为0。这使晚到 clear 与已准备好的预测值在最后一级相遇。

这些写法给综合器更直接的最终门控表达，但工具可能重构成等价 LUT。由于现有负路径以 route 为主，当前 **只证明功能等价，没有证明 WNS 改善**，不得标记候选时序 PASS。后续若独立物理评估，应先检查 cg 的 fanout1长线、数据 CLKROUTE 与 clock packing，再比较相同约束下的全十组 STA。

## 实际仿真证据

ModelSim SE-64 10.6e；真实 frozen RTL golden/candidate 同时实例化。

- 通用16位 counter：全65536状态 × clear/seed/inc全部8组合 = **524288** 次转移，检查 q、组合 next_q、prefix 与独立加法参考；PASS。
- 专用gap counter：全65536状态 × capture_vsync/vs_q/href/inc全部16组合 = **1048576** 次转移，逐项检查 clear优先级、wrap及prefix不变量；PASS。
- 诊断与CDC完整RTL miter：**50000** 个相机周期、**85712** 次双时钟观察，确定 seed `643219ab`；随机reset/帧边界/href/valid/full/host读写/acquire/release，以及32位 FFFFFFFE→FFFFFFFF→00000000 定向 rollover。比较所有8个诊断计数、mailbox、host_bank、所有输出及CDC count/drop/prefix/snapshot；PASS。
- CDC FIFO 使用两侧相同的边界 stub，独立随机 full/empty 输入和固定 read data。该测试检验被修改的计数/状态逻辑，不是 FIFO IP 或整机像素链验证；原 FIFO 接线未修改。
- 两次最终仿真均 **Errors: 0**。唯一 warning 为环境 `-novopt` 的速度提示。gap TB 首次发现预期值在赋值同delta内读取旧wire clear的测试问题，改用直接控制表达式后全穷举通过；不是候选RTL故障。

最终日志：`camera_boolean_candidate01/miter.log`、`gap_exhaustive.log`；哈希与 PASS 原文见 `camera_cone_evidence.json`。可复现命令见各日志开头。

DDR final Setup Slow **+0.250 ns**，PCIe pclk/pclk_div2 **+1.090/+0.896 ns**。三条失败无 DMA endpoint：此轮不引入 DMA v2。可交主会话审阅的是已通过上述功能验证的独立布尔候选与真实逻辑锥证据，物理提升仍待独立排队验证。
