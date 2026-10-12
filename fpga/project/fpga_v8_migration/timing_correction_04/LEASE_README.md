# TC04 lease 时序候选

候选：`rtl/fpga_v8_capture_lease_tc04.v`，模块名独立，参数、端口顺序与宽度保留 V5。

SHA-256：`a2f59e9e6f09d92e47e26dd0b59bcbd2124d3ee2bc946dfd2671e68abf7678a5`

参考：`../whole_candidate_v5_route_01/rtl/fpga_v8_capture_lease.v`。
参考 SHA-256：`04e908f9be9aa10ebf4eb19604d747c7dd7d2e48bd8aa52dbe069fc6e246865c`，
与已有 `capture_lease/fpga_v8_capture_lease.v` 字节一致。

## 实际路径与改动

V5 `evidence/all_reported_failing_paths.json` 中 17 条 lease 失败路径的完整
`full_detail` 保存于 `receipts/lease/v5_lease_failing_paths_full.json`。
最差路径 #4 从 cam5 `last_cnt[0]` 出发，经实际 wrapper 的
`publish_seq = dbg_last_cnt + 1`、进位链、序号比较、银行选择，进入 sequence
寄存器的 CECO/CECI 级联，slack 为 -0.256 ns。路径 #6 的 published_count CE
为 -0.223 ns；路径 #7 的 armed 为 -0.130 ns。#6/#7 经共享 N552（fanout=34）。
因此这里同时处理晚到序号数据、资格逻辑与计数器结构。

- `writing_eligible` 精确表示当前 `state[writing_bank]==WRITING`，从与状态寄存器
  完全同优先级的下一状态计算。`next_nonzero` / `next_last` 同步维护当前
  next_sequence 的非零/末序号资格，不把外部 publish 或 publish_seq 延后一拍。
- 仍当拍比较外部 publish_seq 与内部 next_sequence；合法且非零才发布。
  已校验后把内部 next_sequence 写入银行 sequence，避免晚到外部加法结果直接
  作为 sequence 寄存器数据。无效 descriptor 字段也保留原逐拍值。
- published_count 拆成八个四位无条件更新加法器。各块进位资格来自原计数低位，
  当拍 publish_success 只进入局部加法，不成为一个 32 位自增的入端进位。
- release 匹配、双消费者 claimed/released、offer 仲裁和 lease_block 保留。
  状态更新仍使用原边沿前状态，按 SOF、发布/retired_error、最终释放顺序覆盖。
  publish 为 1 时，无效发布也禁止 retired_error 分支；非法 SOF 仍当拍故障并
  disarm；末序号发布当拍 disarm，wrap 后禁止捕获。

## 真实测试

在仓库根目录执行：

```text
python project/fpga_v8_migration/timing_correction_04/tests/run_lease_tests.py
```

ModelSim 10.6e 已真实编译运行。参考和候选分别以 Verilog-2001 编译；只有
testbench 以 SystemVerilog 编译。全部 9 个用例通过，总计 319,272 拍。
36 个公共输出在上升沿前后比较，包括 valid 为 0 时的全部 descriptor 字段。
每次比较还检查三个冗余资格位与当前状态的一致性。

覆盖默认双消费者、HOST_REQUIRED=0、7 类非法参数（重叠、越界、未对齐、奇数长度、
数据宽度、geometry、camera ID）；真实经过 reset/arm/SOF/publish/claim/release
的双 HELD 状态、两种消费者释放先后、同拍 claim/release 拒绝、重复/错误/过期身份、
descriptor 背压、128 种同拍事件组合、ARM/SOF、SOF/publish、有效及无效
publish/retired_error 优先级、四位块全部进位边界、32 位计数回绕、sequence
0xfffffffe → 0xffffffff → 0、完成租约后 rearm，以及零序号拒绝。
两种正常配置各有 20,000 拍无故障随机运行和 30,000 拍异常事件随机差分。
边界加速仅在 TB deposit 内部 sequence/count；同时设置冗余资格位以维持不变量。

`receipts/lease/results.json` 保存确切命令、返回码、测试源码哈希、候选/参考哈希、
输出清单、完成标记和模块重名扫描结果。相邻日志保存完整编译/仿真输出。
保护快照覆盖生产 source、V5 RTL、TC03 RTL、已有 lease 仿真源码和生产工程文件，
共 442 个文件，运行前后字节哈希一致。GBK source 只进行字节读取/扫描。

## 局限

这是独立 lease RTL 差分回归，未运行相机/DMA集成仿真、整机 runner、PDS、综合或
布局布线。预计算资格增加三个寄存器及下一状态逻辑，可能把关键路径转移到资格
寄存器 D 端；综合器也可能重新共享 CE 或合并局部加法器。外部 publish_seq 的当拍
32 位等值校验和 next_sequence 的更新路径仍存在。不能据此宣称负 slack 已修复。

测试证明所运行序列的逐拍一致性，不是形式等价证明，也不覆盖资格位被独立故障
翻转或不一致的层次强制赋值。生产事件来源仍必须满足实际 tag B 成功发布和
coordinated reset 协议。本候选没有增加权限延迟，也没有将异常序号视作有效。
任何集成或最终时序验收应另行由父会话安排；本目录不登记到工程。
