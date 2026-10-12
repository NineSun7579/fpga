# v3 独立 timing route 01

本目录只从已准备、冻结的 `whole_candidate_v3` 构建，保留原有 `_rfg01` 全绑定。完整流程的最终状态以 `pnr_result.json` 和最终 `parent_handoff.json` 为准；启动不等于时序通过。

仅应用 `timing_correction_01/parent_handoff.json` 的两处实例类型替换，每处命中一次。新增模块哈希分别为 `109a04b0714c3a0cc302686171e4776abe31351ce0ccdd19927c27d1347952ca` 和 `8e77852f4e969984ad7e333445acc067c7cac0714f6b5adaf8156a4a4fbd5c5e`。原适配器保持在 `inputs/source/motion/`，不再登记该路径；登记的是本目录 `rtl/motion_stream_adapter.v` 的修改副本。两个修改文件的只读原始快照另存 `original_snapshot/`，原始与修改哈希见 `source_changes.json`。

694 个输入文件与 v3 原件逐字节一致，包括硬 IP。六个 source FDC 以及登记的 IP FDC 均未修改；核心时钟仍为 131.25 MHz，根时钟 free_clk 为 25 MHz。没有新增 false path、hold cut 或放松时钟。保持 31 个顶层实例 API、原有 512 项端口宽度检查；扩展后 616 项。PCB 保持 112 个 GPIO/DDR 引脚及 14 个 HSST 位。适配器原六端口 API 与 detector 原参数/端口定义相同。四路 history 各 19200×8 = 153600 bit；最终物理 DRM、READ_BEFORE_WRITE 和阈值元数据的保留须以 routed DB 导出为证。

`pnr_help.log` 是本目录独立帮助工程实际执行 `pnr -help` 的完整输出，证明容量 CLI 为 `-max_hold_violated_paths_num`。物理设置：multi-corner 开启、hold repair 开启、500 次、100 ps margin、route hold 开启、cross-SRB 200 ps、clock-tree 200 ps、最大 hold 修复路径 30000。容量和非默认设置采用 PDS 自己生成的 serialization；所有设置写在本工程物理选项中。`full_flow.tcl` 保留明确的全流程审阅命令；实际运行采用 `-project project.pds -run pnr`，PDS 逐阶段更新 `impl.tcl`。

两次 CLI 调用失败分别留在 `failed_cli_attempt_01/`、`failed_cli_attempt_02/`：前者互斥参数被拒，后者 `-file` 创建无源工程而编译前停止。均未进入综合/map/物理路由，不涉及 seed 重试。恢复的是本目录完整源登记，并使用工具实际序列化的选项；旧工程未改动。

保护哈希覆盖原 v2 的全部 4175 文件及 v3/交接/完成路由目录，共 6082 文件。`baseline4175_coverage.json` 与 `protected_changes.json` 给出证据。每次 PDS 启动前记录全局 tasklist；发现其他 PDS 实例立即停止，不杀 GUI、不等待抢占。

最终成功导出位于 `final_export_03/`，证据位于 `evidence_02/`。只读导出实际新 routed ADF，运行 `report_timing -delay_type min_max -nworst 1 -max_path 200000 -slack_less_than 0`。选项来自完成 v2 的实际帮助，200000 上限由本工具实际校验错误确认；没有使用不存在的 `-num_paths`。初次 1000000 上限拒绝的所有输出保留在 `failed_export_01/`；`final_export_02/` 因外层 120 秒超时中断，文件完整保留。成功的 `_03` 使用无超时后台工具，等待自动完成通知后执行审计；未重跑路由。`audit_final.py` 复用原 v2 物理证据检查，全部输出重定向本目录，核对五类 slow/fast 汇总与全部负 slack 端点路径数，不以 500 条上限遮蔽失败。

必须逐项审查 loops、latches、no_clock、clock interaction、matched/short constraints 及未评分 IO。`fpga_v8_reset_fault_guard` 的 bad_event 异步置 fault、close_admission 异步关闭 permit、free_clk 及 alive/link 短脉冲路径需要实际 recovery/removal/CDC 证据。保持原时钟组，不能为这些新 FF 虚构切除。如果 routed timing 仍失败，完整失败路径是下一次实现的依据。

即使所有已评分检查通过，也只是实现审阅就绪；未评分 IO 不算 IO signoff，F2H/no-host-drain reset 仍未认证，不表示板级接受。本任务未执行 SSH、IP generation、bitgen 或上板。

## 最终实测：未闭合，guard 映射也阻塞签核

Compile、Synthesize、Device Map、Place & Route 全部完成且退出 0；无错误行。实际 routed ADF SHA256 为 `3be26aacf3369a18e5b2022decb834fd3313481d045f999a53911860353ee543`，只读导出前后相同。Router hold repair 确实执行 6 次，未出现 Route-2037/容量跳过，随后 hold 优化迭代一次并报告无 hold 违例。PDS 生成实际命令包含 multi-corner、hold fix、100 ps、clock-tree 200 ps、max_hold_violated_paths_num 30000；500 次、route hold true、cross-SRB 200 ps 是原基线/PDS 默认值，预运行工程明确写入后被 PDS 规范化省略，不能声称日志显式打印了这些默认项。

| 检查 | Slow 最差 slack/ns | Slow 失败 | Fast 最差 slack/ns | Fast 失败 |
|---|---:|---:|---:|---:|
| Setup | -0.548 | 7 | 2.253 | 0 |
| Hold | 0.159 | 0 | 0.115 | 0 |
| Recovery | 1.192 | 0 | 2.204 | 0 |
| Removal | 0.272 | 0 | 0.249 | 0 |
| Minimum pulse | 0.011 | 0 | 0.011 | 0 |

全部 7 条负 slack 路径与十组汇总失败端点数完全一致，详见 `evidence_02/all_reported_failing_paths.json`。DDR/AXI 两条为 write_arbiter `awlen_reg[3]` 经 DDR adapter 到 camera DMA `len[31]`/`len[30]` CE，分别 -0.222/-0.085 ns；PCIe 五条为 `o_ddr3_length[2]` 到接收 byte-pack/mask 的 N925/rx_pack_data 端点，分别 -0.548/-0.278/-0.131/-0.081/-0.045 ns。原 39 个 motion/decoder setup 失败端点未再出现。

实际 elaboration 含全套 `_rfg01` 链及两个 `_tc01`，原 detector/decoder 没有 elaborated。GPIO 112 行与完成 v2 的所有属性完全一致，HSST sites/dedicated connections 也完全一致。四路 history 仍为 153600 bit/路，总 614400 bit，实际 32 个 DRM36K 均 READ_BEFORE_WRITE。另有每路 192 位 mark_q，总 768 位阈值元数据，已从实际 routed gop FF 定义及 placement 逐位核验，均不是 latch。全工程物理报告 DRM 用量 71.5，CLMA FF 24466、CLMS FF 7132。

但 guard `fault_cp` 和 `reconfiguration_required_cp` 实际成为两个 gopLATCH，clock 输入分别为 bad_event 与 N165。最终 no_clock=9：两个 latch clock pin 加七个控制传播节点，包含 DDR init/link up/runtime_active/perst/core reset/N165；这不等同九个缺失根时钟端口。N165 形成 size-7 反馈环，实际经过 reconfiguration_required_cp 和 axfault 逻辑；STA 自动切断环上 timing arc。loops=1、latchs=2、latch_loops=0，不能用 recovery/removal 的评分零失败来覆盖未评分 latch。`evidence_02/guard_actual_routed_cells.json` 保存真实单元和位置，`guard_mapping_blocker.json` 保存综合原始证据。

时钟仍为 free_clk 40 ns、AXI 7.619 ns、PCIe pclk_div2 8 ns。最终 clock interaction 保留原有 pair 分类，新增 guard 所产生的 DDR→free、PCIe→free、free→PCIe pair 均由原 FDC asynchronous groups 排除，未新增时钟切除。N165 不在 declared/generated clock 表中，是实际 latch 的控制驱动。62 个 input/71 个 output delay 缺失，1594 条未评分 IO 路径单列保留，不算签核通过。

下一次独立 candidate 必须缩短两个 same-clock setup 路径簇，并把 guard 异步故障/持久 reconfiguration 改为 PANGO 支持的顺序结构、消除 latch/control-clock 反馈，同时保留短脉冲捕获和 admission closure 契约，再做契约回归和全流程路由 STA。此目录最终已冻结的 RTL、硬 IP 和 FDC 均未为消除失败而修改。`parent_handoff.json` 的状态为 `ROUTED_TIMING_NOT_CLOSED_AND_GUARD_MAPPING_BLOCKED`；`review_manifest.json` 可供下一次修复审阅，不能用于板级接受。
