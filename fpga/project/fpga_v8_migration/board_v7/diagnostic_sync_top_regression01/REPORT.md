# 完整 v7_sdt_top primitive 候选 RTL 回归

结论：本地真实 ModelSim SE-64 10.6e 完整top回归与原版/primitive逐拍四态比较通过。检查数量、实际实例绑定和输入 hash 见 `results.json`、`audit.json`、`actual_parent_bindings.json`、`hashlog.json`。

| 实测检查 | 原版 | primitive版 |
|---|---:|---:|
| 原完整suite检查 | 14540 | 14540 |
| 追加四路reset后检查 | 14668 | 14668 |
| M01 reads / writes / legacy reads | 1234 / 214 / 17 | 1234 / 214 / 17 |
| host posedge采样 | 1158545 | 1158545 |
| camera posedge采样 | 827533 | 827533 |
| 异步reset变化采样 | 18 | 18 |
| 硬件RTL/TB编译 errors / warnings | 0 / 0 | 0 / 0 |
| 仿真 errors / warnings | 0 / 633 | 0 / 633 |

精确逐行四态trace比较6792条（含连续相同采样的无损压缩和总采样数），原始trace共14036839 bytes，SHA256均为 `e5da4bf3e24ec027e319950d793378b336779ba3af12884e5235eb90593ec12f`。1881项冻结输入前后hash一致。实际候选60个GTP触发器绑定通过：28 CE +32 PE。最终hashlog包含123项交付文件，独立audit逐项复查。

## 冻结合同与独立登记

原套件来自 [source_diagnostics_top_candidate](../source_diagnostics_top_candidate/REPORT.md)。完整 `compile.f` 的硬件 RTL、真实 DDR sim_lib、其他原 IP/interface models 及官方加密 vendor library 沿用原版本。两个版本各自建立独立 `work` library；原 vendor library 只读绑定，未更新它。安装的真实 GTP_DFF_CE、GTP_DFF_PE、GTP_GRS 来自 PDS 官方 simulation models，不提供自写 stub。vendor 与所有原编译输入在 `frozen_inputs.json` 中前后 SHA256 核验。

只替换登记表中 `v7_sfd_candidate.v`、`v7_sdt_bus.v` 两项：baseline 字节复制原 top 套件实际登记文件；primitive 字节复制 `../diagnostic_sync_register_timing_candidate/rtl_primitive/` 两文件。每个库的模块登记唯一性由字节级 module 扫描断言。实际完整源列表见各目录 `compile.f`、`registered_modules.json`；替换来源和字节 hash 见 `replacement_contract.json`。GBK RTL 使用 read_bytes/write_bytes，不做编码转换。

未修改 source_diagnostics_timing_build01、独立 map project、production、IP 或任何原套件文件；未运行 PDS、映射、远程或设备编程。活动 timing build 与可识别的 primitive map 输入亦加入只读冻结核验。

旧 primitive frozen manifest 中活动 `source_diagnostics_timing_build_01/project.pds` 与其历史hash已不同，详见 `historical_input_differences.json`。该文件不是本次编译输入；记录其当前字节用于本次前后核验。原top实际编译输入及原source合同的历史hash均需完全一致，不能用此例外放过仿真输入变化。

## 完整套件与补充比较

原 `tb_sdt.sv` 和 `scenario.vh` 的全部刺激、期望及原 `SDT_ALL_PASS checks=14540` 输出保持不变；只加入观测 monitor，并在原通过输出之后、结束仿真之前追加四路各一次 2ns camera reset。补充逐路检查 epoch 恰好加一、源读返回 SLVERR、AXI/真实 camera_ctrl 启动状态保持。原全局 AXI reset、R/B 背压承诺、承诺前复位、其他相机 lease 保持合同继续按原 suite 执行。原 65536 拍启动计数、四路真实 binding/capture/negedge、640x480 全帧全部16字段、lease/previous、ADDR aperture、六相机完整实例、motion、legacy AXI、PREP、COOP/CAPL 路由均未简化。

baseline 与 primitive 完整 top 在各自独立库中分别实际运行相同 suite。监测从本地复位已生效的 20ns 起，在 host/camera 每个 posedge 后2/3ps及实际异步 reset 变化后4ps采样。逐拍观测全部28同步级、32复位级、request/ack、四组512-bit mailbox/host_bank、源读响应/lease、序号、epoch、diagnostic legacy master接口及顶层 AXI 响应和复位状态。只省略连续相同采样值，变化记录保留时间、采样类型和完整四态值；结束记录总采样数量。两份 trace 按行严格相等断言，保留 gzip 文件和原始 trace SHA256，不以 hash 相等替代实际逐行比较。

候选实际 parent binding 从本次 `vsim -voptargs=+acc` 的 `find instances -recursive /*` 结果提取：`/tb_sdt/dut/source_diagnostics/cameras[g]/source` 下逐级 ack_sync/req_sync/overrun_sync/cr/hr，以及其 parent cameras[g] 的 reset_pipe_ff0..3。断言实际实例数60；28 CE /32 PE对应原候选声明。完整实际层级保存在 `primitive/hierarchy.txt`。这里是 RTL 仿真绑定证据，不能替代 mapped/routed cell/pin 证明。

## 原 evidence 和 INIT 边界

原独立 source/bus 检查的 evidence 链接保留于 `evidence_links.json`：source 2038、bus 原版/修正版11986，以及 primitive 原版并排 source/bus 结果。此次新增工作是完整 top 回归；未把旧2038/11986日志伪称为此次重跑结果。

无本地复位 time0，原行为RTL没有 initial，其未初始化寄存器可为X；显式primitive使用硬件 INIT。原60级参数已在 `../diagnostic_sync_register_timing_candidate/evidence/primitive_parameter_audit.json` 与旧真实综合实例核对：28 CE INIT=0、32 PE INIT=1、GRS_EN=TRUE、CE=1，复位clear/set类型对应原实现。time0硬件INIT匹配引用该实证；此次完整 top 严格等价范围从本地reset之后开始。真实GTP_GRS的GRS_N保持1。无本地复位上电RTL等价、全芯片GRS事件和模拟亚稳态均不在结论内。

完整 top 原套件提供 AXI/控制时钟、DDR init、I2C完成，free_clk停止；不验收PCIe训练、DDR校准或RAW帧完整DDR流。本次两份独立新库的仿真各633个 warning，不能沿用旧报告298的数字。完整消息及vopt/vsim类别见 `warnings.json`；原冻结模型连接/位宽 warning 未被当作物理签核通过，两版完整log均保留。

## 复现与交接

在工作区根目录运行 `python project/fpga_v8_migration/board_v7/diagnostic_sync_top_regression01/run.py`，随后运行同目录 `audit.py` 检查完整交付并封存hashlog。脚本只使用 vmap/vlib/vlog/vsim。本次完整suite无需为修正层级证据筛选而重跑：首次封存把DFF内部NOT门计入，已改为精确匹配官方GTP_DFF_CE/PE实例，既有实际仿真证据重新封存并独立audit通过。

可交下一版 full integration 使用两份已冻结 primitive RTL；必须先有该版独立 map 成功与60级独立物理端点、参数、setup/hold和复位签核证据，不能由此次RTL仿真声称物理禁止打包成立。
