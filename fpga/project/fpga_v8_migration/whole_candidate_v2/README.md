# 第二版完整隔离候选：ARM 与 PCIe 修正集成

状态：Compile / Synthesize 均通过（exit 0）；仅供父会话审查，尚未验收。没有执行 PnR、SSH、上板、IP 生成、GUI 关闭或历史目录清理；所有写入均在本目录。

源基线是不可变 `whole_candidate` 第一版及其冻结 motion 输入，顶层源 SHA256 为 `ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2`，未采用 `dca…` production top。完整复制了 694 个冻结输入和 12 个第一版组件，另加 1 个 ARM 控制器、4 个 PCIe 生产克隆；这些是独立、只读、哈希受保护的快照。原控制器快照保留但不登记，实际登记 16 个组件。

顶层为 `rtl/fpga_v8_cooperative_top_v2.v`，工程为 `project.pds`。相对第一版仅有三项顶层字节修改：唯一顶层名、ARM 控制器模块绑定、PCIe FIFO 模块绑定。原 instance 名称、参数、全部 named ports 与连接不变。`artifacts/firstversion_to_v2.diff` 和 `v2_byte_change_manifest.json` 可直接审查；完整冻结 top 到 v2 的操作清单也可逐字节回放。第一版成功重试的 `_timespec` 工程登记修正已沿用，PDS 默认模型，无显式 configuration。

ARM 修正哈希为 `b65d5cc7a6e0bc1bdf765dfd6da0bb9488cc0ab27d95fe7e6db730170aa857e9`。PCIe FIFO 为 `507ef4c56999aac5356dd51f51a669232fb7c40070c67e3ab108da444b32640d`，controller 为 `dc87498f41e5c977962e131491d1e932dd716a91a7eb15f94e433f8363f67cd1`；两个 wrapper 克隆哈希同样与交付清单匹配。PDS 使用交付 production artifact 原始字节，没有 ModelSim normalization，没有 queue memory / signed function 的本地语义修改。仿真 shell/TB 未登记。

实际编译链为 `fpga_v8_cooperative_top_v2 → fpga_v8_pcie_fifo_h2f → fpga_v8_pango_pcie_top_h2f → fpga_v8_pcie_dma_h2f → fpga_v8_pcie_dma_controller_h2f`。原 shell instance 名称保持不变，实际 vendor IP 未改。编译日志确认新链全部 elaborated，旧 FIFO/controller/wrapper 模块未 elaborated。完整参数/端口方向/宽度 API 比较通过；PCIe wrapper 字节差异严格限于模块及 child 类型重命名。

结构检查通过 489 个 named-port 宽度项（原 436 项 + 53 个原 PCIe 顶层连接）。两个原本省略的 link-status 输出保持省略。无新增重名模块、隐式接口 net 或多 driver；冻结 IP 原有 11 组重名定义仍由 PDS 接受。六路相机、所有 DMA、四个本地 motion tap、motion 历史记录与寄存器路由均保留。112 个历史 GPIO/DDR PRR pads 和 14 个 HSST 位保留；没有生成新的布线引脚报告。

DDR/core 时钟与约束不变：`core_clk=ddrphy_sysclk`、`axi_clk=core_clk`、`axi_rst=~ddr_init_done`，25 MHz × 84 / 16 = 131.25 MHz，周期 7.619048 ns。未新增 false path 或环路抑制。最终 `compile_01/attempt_01/synthesize/snr.db` 的 CHECK 表给出 loops=0、latch_loops=0、latchs=0，资源消息亦为 Total Latches: 0。精确 CHECK、时钟、交互、各域 setup/hold/recovery/removal 表见 `evidence/check_timing_exact.json`。

| 综合资源 | 第一版 | v2 | 差值 |
| --- | ---: | ---: | ---: |
| LUT | 29733 | 31251 | +1518 |
| FF | 30889 | 31535 | +646 |
| DRM | 72.5 | 72.5 | 0 |
| APM | 0 | 0 | 0 |
| Tool I/O | 114 | 114 | 0 |

DDR/core 域 setup +0.597 ns，预估 142.4087 MHz；hold −0.004 ns、TNS −0.040 ns、10 个失败 endpoint。hold 数值及工具列出的 DDR `o_rid → prefetch FIFO` 代表路径与第一版一致。报告仍写明 `Some Constraints Violated`。这些是 pre-route 估计，不是时序闭合。外部 IO delay 缺失仍有 62 input / 71 output；时钟域约束未变，不能以同一 core 接线推断跨域 reset 或硬件正确性。

Compile 有 2306 条 warning，Synthesize 有 9885 条；逐行原文、代码、源分类与冻结基线匹配信息在本次 `evidence/` 中。constant-probe loop 文本是优化诊断；最终 CHECK 计数用于环路结论。endpoint `eligible.addr_end_1` warning 保留，仍需父会话 mapped eligibility 审查。

已核验 ARM 六套回归收据哈希：endpoint 499 operations / 4288 events，actual full-frame/core、同步 SOF priority、pending final-B、lease 套件。已核验 PCIe 50 cases（46 成功、4 故障不发 MSI）、4 次 F2H parity / 305 chunks；F2H parity 不证明 posted-write retirement。本集成没有新增语义修复，未冒称重跑完整 whole 回归。

受保护 union 的 3324 个文件 before/after/final 完全一致，包括旧 whole 完整树、冻结 motion、全部 capture ARM、全部 PCIe contract 文件，以及 production source/IP 和现有 PDS。第一版原 1091-file production guard 也单独复核一致。本次实数为 893 个 production source/IP 文件、219 个受保护 PDS 路径；用户提及的历史 1191 数量未在当前清单中复现，交接中明确记录实数及差异，不伪造统计。viewer 目录没有写入。

验收 blocker：独立 PCIe/controller/CPU/AXI/DDR reset 与 stale IRQ/reset epoch；上游 physical input identity；RX/output 分配互斥和 CAM1–4 动态地址；F2H posted-write retirement；Linux MSI/ioctl ordering 与 hard-IP 链路；继承 hold/外部 IO timing；whole mapped regression/硬件 paired RAW-output 比较。core DDR adapter 的 IRQ identification/reset epoch 问题未解决，独立 reset 仍不支持。

完整交接见 `artifacts/parent_handoff.json`。父会话先审查 source、最终 loop、resources，再决定 PnR。

```powershell
python project/fpga_v8_migration/whole_candidate_v2/audit_candidate.py
python project/fpga_v8_migration/whole_candidate_v2/summarize_pds.py attempt_01
python project/fpga_v8_migration/whole_candidate_v2/review_v2.py
python project/fpga_v8_migration/whole_candidate_v2/finalize_v2.py
```

已完成的 run 不可覆盖。`run_pds.py` 仅支持 prepare/compile/synthesize，每次启动前保存 tasklist；唯一授权运行在 `compile_01/attempt_01`，编译与综合顺序执行。PDS 自动格式化只发生在这个新 run 工程，前后副本均保留。
