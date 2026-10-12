# Capture lease prefix 时序候选与实际 RTL 等价验证

已实施独立候选，ModelSim SE-64 10.6e 的 9 组实际 RTL miter 全部 PASS，共 319,624 拍。未运行 PDS、远程任务或烧录；候选尚无综合/布局布线时序数据，不能宣称 WNS 改善或时序收敛。

## 冻结源定位及实际路径

`source_diagnostics_route_02/rtl/fpga_v8_cooperative_top_v2_rfg01.v` 的 `u_v8_capture_lease` 实例使用 **fpga_v8_capture_lease_tc04**，不是旁边同接口的 `fpga_v8_capture_lease.v`。实例采用 axi_clk/axi_rst、CAM_ID=4、HOST_REQUIRED=1。

exact09 冻结清单为 `physical_subagent_evidence_01/fixed_06/physical_exact_09/input_hashes.json`。本次逐字节验证上述实际模块和实例所在 top 的 SHA256 均与清单一致，完整路径记录于 [frozen_binding.json](evidence/frozen_binding.json)。

| 项目 | SHA256 |
|---|---|
| exact09 input_hashes.json | `45e3b1d5ed79ac8b0782f64a9f12f1ad8a463306f4688a864269534e7470fe89` |
| route02 实际模块／独立 original 副本 | `a2f59e9e6f09d92e47e26dd0b59bcbd2124d3ee2bc946dfd2671e68abf7678a5` |
| 实例所在 cooperative top | `ca02da78385c7b9f156373748c5e46cc47f9a104b006778a99a35200d2991841` |
| 新候选 RTL | `0461af04c40f6c3bbdea0367d084fa6e4d33647c17bede58ea341323779017ed` |
| 真实 miter TB | `6b91f2d27597eb7f3a035bbff7510858125a9a88fbfba594a505c79300e1db9f` |
| candidate.diff | `7f81640c55cb3896b1d24bebb2e2d5d41dd686e4c4de6f477c7ead67674b48e4` |

从 exact09 的 `evidence/all_reported_failing_paths.json` 提取了 151 条以 `u_v8_capture_lease/` 为终点的负路径，全部属于 ddrphy_sysclk。最差路径为 −2.716 ns：`cam5_ov5640_ddr/ov5640_ddr_w_ctrl/last_cnt[4]/.../CLK` → `u_v8_capture_lease/published_count[25]/.../I4`，数据到达 15.438 ns、要求 12.722 ns。从数据 tco 后到 Data arrival 的单元 td 行计数为 20 层；包含相机计数进位、publish_seq 比较/授权，以及 mapped published_count 相关链。完整实际路径保存在 [actualexact09_lease_paths.json](evidence/actualexact09_lease_paths.json)，没有用估计时序替代它。

## 修改与逐拍归纳证明

[original/fpga_v8_capture_lease_tc04.v](original/fpga_v8_capture_lease_tc04.v) 是字节完全一致的原版。[candidate/fpga_v8_capture_lease_prefix.v](candidate/fpga_v8_capture_lease_prefix.v) 仅改独立模块名、增加 7 个冗余寄存器和替换高位块的 carry gating；完整修改见 [candidate.diff](evidence/candidate.diff)。原有 8 个 4-bit incrementer、publication 判定及所有授权接口不变，publish 不增加一拍。

对 w∈{4,8,12,16,20,24,28}，定义 C=当前 published_count，E=原版的 publish_success，P_w=&C[w−1:0]。新增寄存器使用：

```
rst:       C'=0, P_w'=0
!rst && E: C'=C+1 (mod 2^32)
           P_w'=(&C[w-1:1]) && !C[0]
!rst&&!E:  C'=C, P_w'=P_w
```

reset 后不变式成立。无成功 publish 时 C 和 P 同时保持。成功 publish 时，w 位低位加一结果全 1，当且仅当旧低位为 2^w−2，即 bit0=0、其余全 1；旧低位全 1 则结果回到 0，P 正确清零。因此每个时钟沿后 `P_w == &C[w−1:0]`，并保持到下个沿。由此高位 4-bit 块的 `E && P_w` 与原 `E && &C[w−1:0]` 完全相同。最低块仍使用 E；所有块同一沿更新，32 位自然回卷。

候选把 late publish 到高位 carry 的宽 reduction 换为与寄存器的 gating。prefix 的宽 decode 仅来自旧计数；late publish 在其更新路径上仅选择 decode/hold。这是 RTL 结构上的时序优化候选，综合器是否保留结构、相机计数和 32 位 publish_seq 比较能否成为后续瓶颈，需另行综合/布线确认。

## 所有 count 事件及优先级

| 输入／事件 | 冻结原版 published_count 行为 | prefix 行为及验证 |
|---|---|---|
| rst，包括同拍 config/publish/error | 清零，优先于所有事件 | 清零；定向 RESET_PRIORITY_PASS |
| 成功 publish | 加一 | 更新到新 count 的谓词；全部 nibble 与 32 位边界 |
| config 接受／拒绝、generation 重启 | 不单独修改 count | 保持；wrap 后 rearm、过期 generation release 拒绝 |
| publish 与 retired_error 同拍 | publish 分支优先；有效才加 count，无效则 fault，failed_count 不加 | 使用同一个 E；有效／无效 publish/error 均回归 |
| 无 publish 的 retired_error／abort rollback | 回收 WRITING、failed_count 加一，published_count 保持 | 保持；abort 后重新采集、双消费者释放、满计数回卷 |
| SOF、claim/copy ack、coop/host release | 不单独修改 count | 保持；同拍 claim/release 拒绝、双 bank、单消费者先释放、双消费者同拍完成 |
| busy config 与成功 publish 同拍 | config_ready 为假；成功 publish 仍按旧状态加 count | 128 组事件组合覆盖 |
| idle 接受 config 与无效 publish 同拍 | 接受 config，随后 publish fault/disarm；count 保持 | 定向 CONFIG_PUBLISH_PRIORITY_PASS |

成功 config 需要 all_free，成功 publish 需要当前 WRITING；二者不能同时成立。没有人为建立互相矛盾的合法性谓词来制造这种状态。lease 模块没有独立的 decrement、count rollback 或软件清零入口；abort/rollback 指 retired_error 回收 bank，不可擅自把它解释成 count 清零。

## 真实 miter、初始化和日志

[tb_lease_prefix.sv](tb_lease_prefix.sv) 并排实例化 actual tc04 原版和候选，两者全部输入使用同一信号。每拍上升沿前和 NBA 完成后比较 36 个公共输出，包括三个计数器；同时比较 generation、next_sequence、两个 bank 的 state/sequence、coop/host claimed/released、writing_bank、offer_bank、轮转和原有冗余谓词。候选 7 个 prefix 在两次检查中都必须满足当前 count 的 reduction。

复用 `timing_correction_04/tests/lease_stimulus.svh` 的真实 lease 激励，路径和 hash 见 [reused_regression.json](evidence/reused_regression.json)。保留双消费者 claim/release、descriptor 背压、身份错误、序列回卷、generation rearm、128 组事件组合、20,000 拍持续合法随机交通和 30,000 拍含非法事件的随机回归，并增加本报告中的边界/优先级测试。

定向边界使用**一次性层次 deposit，不使用 force**。在 idle、两 bank FREE、无 descriptor/publish/reset/epoch 条件下，两侧同时设置相同 count 和 next_sequence；两侧原有 next_nonzero/next_last 随之初始化，候选 prefix 按实际低位 reduction 初始化。零序列时两侧同时 disarm，符合序列耗尽状态。计数代表省略的既往已完成 publication 历史，随后完全由实际 RTL 更新；不在时钟边沿重复 deposit，也不修补运行中的 prefix。

每个宽度额外覆盖 `2^w−2 → 2^w−1 → 2^w`，检查进入全 1、保持、离开全 1；w=32 包含 `fffffffe → ffffffff → 00000000`。reset/config/error 同拍、abort 回收以及双消费者同拍 copy/release ack 均使用真实端口驱动，未 force bank、publish_qualified 或授权条件。

| 运行 | 拍数 | 结果 |
|---|---:|---|
| HOST_REQUIRED=1，合法参数 | 52,684 | PASS；1,691 publications、403 retirements、coop/host 各 1,553 accepts |
| HOST_REQUIRED=0，合法参数 | 52,684 | PASS；1,877 publications、392 retirements、coop 1,739 accepts |
| 7 种非法参数 | 各 30,608 | 全部 PASS；无 publication |

[host1_bad0.log](evidence/host1_bad0.log) 的实际标记包含：

```
PREFIX_CARRY width=28 count=10000000 prefix=0000000
PREFIX_CARRY width=32 count=00000000 prefix=0000000
PREFIX_ENTER_ONES width=32 count=ffffffff prefix=1111111
PREFIX_LEAVE_ONES width=32 count=00000000 prefix=0000000
PREFIX_RESET_PRIORITY_PASS
PREFIX_CONFIG_PUBLISH_PRIORITY_PASS
PREFIX_ABORT_COPY_ACK_ROLLOVER_PASS count=00000000 prefix=0000000
LEASE_PREFIX_ACTUAL_RTL_DIFF_PASS cycles=52684 public_outputs=36 ...
```

另外在独立 negative 仿真库把 prefix 成功 publish 后的更新故意改成恒 0。相同 miter 在 cycle=1906、count=0000000f 报 `Fatal: prefix invariant width=4`，且没有 PASS。这证明 checker 能识别错误更新；故障副本仅在 build 内，交付候选未被改变。见 [negative_control.log](evidence/negative_control.log)。

## 保护范围、复现与界限

生产 source、ipcore、route02 的 rtl/inputs/exact09 约束、冻结清单及工程文件共 1,641 个文件在运行前后逐字节 SHA256 完全一致。见 protected_before/after.json 及 [results.json](evidence/results.json)。原版直接 read_bytes/write_bytes，候选只在 ASCII 副本做修改；未重编码 GBK 生产文件。候选独立 module 名按字节扫描唯一，见 module_collision_scan.json。没有修改 route02 的任何 RTL、工程或其他代理产物，没有登记候选到生产工程。

从仓库根目录复现：

```
python project/fpga_v8_migration/board_v7/capture_lease_prefix_timing_candidate/run.py
```

工具默认为 `C:/modeltech64_10.6e/win64`，可用 MODELSIM_BIN 覆盖。脚本仅创建本独立目录内的 RTL 副本、TB、仿真库、波形和证据。完整命令及返回码记录在 results.json；正常 9 组日志均 Errors: 0，工具既有 vsim-8891 优化关闭警告不影响结果。negative 库的 Fatal 是期望的故障控制结果。

证明为 count/prefix 归纳论证加真实 RTL 有限仿真 miter，并非对全部输入序列的形式等价工具证明；本次没有完整相机/DMA 整系统仿真。151 条负路径和 −2.716 ns 都属于冻结原版的实际 exact09 布线结果，候选的最终面积、扇出和 WNS 尚未测量。
