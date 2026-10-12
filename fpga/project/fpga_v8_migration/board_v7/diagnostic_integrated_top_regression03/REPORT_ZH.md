# camera boolean 候选真实整合回归03

结论：**功能回归 PASS；整体冻结门禁 FAIL**。黄金严格来自 regression02 的实际 integrated 源闭包；黄金与布尔候选均用 ModelSim SE-64 10.6e、真实原 FIFO/IP 模型完成原套件及四相机 reset 扩展，每侧 **14668** 检查。所有 trace 逐记录四态一致。没有 PDS、远程或设备操作，不主张时序改善。

## 源闭包与实例绑定

每侧实际编译 **243** RTL/IP/model 文件，**241** 文件字节相同；仅 `rtl/v7_sfd_candidate.v` 与 `rtl/ov5640_cdc_tc04.v` 改变。黄金沿用 regression02 原 camera/control/lease 三项优化及当前 explicit primitive。counter 的 actual module 名保持 `v7_sfd_counter`，其他八个 counter 仍按原 W 参数使用通用实现，q 的最终 clear bitmask 来自 isolated 候选，组合 next_q 的原语义不变。四路 cg 从 `v7_sfd_counter #(.W(16))` 精确改绑 `v7_camera_gap_boolean`；gap 模块字节和候选相同，不改其它参数。

四路实际 CDC 绑定 `ov5640_cdc_tc04`；其内容与 isolated candidate 仅 module 名不同。所有计数/快照/FIFO 接线保持原语义。真实 compile.log 和 hierarchy.txt、results.json 证明诊断 source、专用 gap、CDC、FIFO/IP 被编译和加载。诊断 primitive 实例保持 **28 CE / 32 PE**；属性和 primitive 实例文本独立按字节验证相同。没有接入 map02。

## 真实 trace 审计

保留原 **976** 信号表达式、36组 integrated trace 和原 comparison monitor；额外 **468** 表达式、12组 boolean trace 观察四路 gap q、八个通用 counter q/next_q/prefix、诊断计数/mailbox/host_bank/reset握手及 CDC count/drop/prefix/snapshot/FIFO状态。专用 gap 内部 prefix 不要求与原层级同名，q 必须一致。

所有 host/camera 正沿、camera 负沿和 control 正沿均采样，post-NBA偏移2/3/4/5ps。原 trace 沿用20ns复位后起点；新 boolean trace 从第一时钟沿开始，包含初始未知、seed和reset行为，没有新增 X 屏蔽或延迟补偿。以四态 !== 检测记录变化，连续相同值无损省略，每次采样仍计数；两侧逐记录及最终 SAMPLES 比较相同。

| Trace | 记录数 | 解压字节 | SHA256 |
|---|---:|---:|---|
| comparison.trace | 6792 | 14036839 | `e5da4bf3e24ec027e319950d793378b336779ba3af12884e5235eb90593ec12f` |
| integrated.trace | 8323690 | 1341671801 | `787c45fb650404edbfea6e54c9e84584cec48afb0e0efe44e199b9b9e8fb3426` |
| boolean.trace | 14332607 | 2801560737 | `4e940b8d1af6d43cccc8e5fc94a5b834d86258c924a9e380e99146ea9c51ddbc` |

两项原 trace 的黄金 SHA256 还与 regression02 已封存结果完全一致，防止重新生成的黄金漂移。boolean trace 从首个边沿开始比较。X/Z 原值保留；下列为实际记录数据十六进制字符数，不等同于独立未知信号数量：

- comparison.trace：黄金/候选 X/Z 十六进制字符数 0/0。
- integrated.trace：黄金/候选 X/Z 十六进制字符数 18397994/18397994。
- boolean.trace：黄金/候选 X/Z 十六进制字符数 12/12。

新增 boolean trace 的12个X/Z字符均位于首次host采样（原始日志timestamp=5000000）：四路diag组各1个、四路CDC组各2个。initial_unknown_locations.json 保留记录号、组名及原始payload；所有未知值在两侧完全相同，未屏蔽。原 integrated trace 的未知值也与 regression02 的原封存哈希一致。

警告黄金/候选 **633/633**；原文存 warnings.json 和真实日志，不能作为物理验收。每侧原计数 M01_reads=1234、M01_writes=214、legacy_reads=17；四路640x480帧检查及全部reset标记保存在 results.json。原边沿 counts 和额外 SAMPLES 均保留于 trace 尾及仿真日志。

实际 integrated 每侧 host=1158545、camera posedge=827533、camera negedge=827532、control=289637；comparison host=1158545、camera=827533、reset=18。新 boolean trace 的每侧实际总采样尾记录为 `SAMPLES 3103251`，两侧完全一致，含20ns前初始采样。

## 冻结与采用范围

实际编译的 **243** 个黄金源文件/IP模型及候选副本全部与开跑冻结哈希一致，源闭包无漂移；**1814 / 1819** 个其它保护输入前后相同。frozen_before/after.json、freeze_audit.json、replacement_contract.json、compile_delta.json、audit.json 为依据。唯一排除的观察文件为 `source_diagnostics_timing_build_02/STATUS.md`，其前后哈希及任何漂移仍记录于 freeze_audit.json；该例外不适用于 RTL、IP/model、脚本、工程、manifest 或其它证据。没有重置 frozen_before。本子会话全部写入限定 regression03。`src/` 内两份 actual module RTL 可供未来独立 build03 使用，src/sourcehash.json 记录字节；本子会话未写活动 build02、生产 RTL 或 map02。

保护输入冻结 **FAIL**。以下非状态文件在本回归期间发生外部变化，原始 frozen_before 保留，未重置黄金、未忽略变化：

- `diagnostic_sync_register_map02/audit_comparison.py`：`5d01c490395deb3695d22d09532d3db8007517a8477e7cdfdf599a4d4fdf5210` → `ac236bce1b0be9982eb52a6ed992c85e39c3a37c44a8201d1261c37f9092fbaf`。
- `diagnostic_sync_register_map02/audit_final.py`：`551ee52e8fbd01d6dc4265dd921a0d4ed0d3d762084506c15aee764326f98042` → `e82637285a682028117de9455d8733fe76f5bd4a882c18c6020cc6803a45dc2d`。
- `diagnostic_sync_register_map02/controller.py`：`079a18c5155e47b025f624cde00e0064616f9fb447a93abd8fe22eeda6404da0` → `3d2c3a6adbe87b6cd1d552f8bb9cf163201242699c14483b5d4dc5722825abd1`。
- `diagnostic_sync_register_map02/evidence/queue_latest.json`：`bf1162775df9d883a06793e56abcda267c20ec2012c21fc57a8525d6d2e95874` → `a57cab8b46055705620c2bad2b981eead7fb10eef9e3c8c2d885ea9e2b3925e2`。
- `diagnostic_sync_register_map02/run.py`：`7b61290d9d849e7963322bbdcc086ff3ce1f6a80c281ce1e3da11a8108588d75` → `53178e12cdeeda26684301e04303a5708bd6fa3c2ec9456504a832eee33bffc2`。

限制继承原整合TB：强制 AXI/control 时钟、DDR init 和 I2C completion，free_clk 停止。虽使用真实 FIFO/IP models，此套件仍不能证明完整 DMA 帧 DDR 写入、DDR校准、PCIe训练、整机吞吐或 cooperative 端到端处理。motion history 为四路8bit×19200 RTL数组，非32个已验收物理RAM primitive。不包含综合、布局布线、STA或时序 PASS。

复现：`C:/Users/NineSun/anaconda3/python.exe project/fpga_v8_migration/board_v7/diagnostic_integrated_top_regression03/run.py`，完成后运行同目录 `seal_delivery.py`。hashlog.json 封存全部交付文件（排除work、__pycache__、vsim.wlf、transcript及hashlog本身）。
