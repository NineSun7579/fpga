# TC04 stream/capture isolated candidates

**实际回归及最终审计：PASS。** 6 组 V5 差分共比较 **8,359,065** 周期；
四路 640×480 motion oracle 通过全部 10 阶段，运行 **3,378,505** 周期、
核对 39 次 publication 和 end+2/end+3 时序。自然触发 motion overflow
24 次、capture overflow 3 次；capture 成功 publication 12 次；32 位
capture carry/wrap 边界共 96 例。995 个受保护源文件/绑定/脚本的 SHA256
保持一致。机器可读证据为 `receipts/stream_capture/results.json` 和
`receipts/stream_capture/final_audit.json`。

中文交接要点：两个 `_tc04` 候选只改 pixel counter 的表示方式，用逐位
XOR/前缀进位替代共享条件自增 CE，保留原始 reset、SOF、overflow、帧尾和
publication 优先级及输出周期。capture pixel_count/pixel_limit 和原有
32 位统计计数没有缩位，测试包含高位进位及回绕。

必须注意真实父绑定：V5 的 `fpga_v8_capture_ov5640_ddr` 用于 cam5，违规
cam6 实例仍是 `ov5640_ddr`，本候选不能直接宣称消除了 cam6 整机路径。
cam6 需要另做原 `ov5640_ddr` 绑定差分：可以另建保留动态地址/长度接口的
隔离候选，或在独立 top 中按当前常量地址/长度映射固定 wrapper；当前这份
wrapper 对 wrapper 的差分不能替代该验证。

DMA residual 只读结论：flush 清零上游可用 credits，经 TC02 的
`data_in_available != available_q` 比较，触发 watchdog 同拍清零，最终映射
到 `wd_cnt[20]/RS`。full_detail 中逻辑 1.155ns、布线 6.023ns，主要成本在
布线；不是直接把 capture flush 当 DMA reset。可另建 DMA 候选，将 watchdog
clear/increment/saturation 改为每位 D 路径表达，保持原 24 位 watchdog、
WD_LIMIT 与 abort 周期。不可直接寄存比较结果，否则 progress 和 timeout
可能相差一拍。本任务未改 TC02 DMA，未启动 PDS。

This handoff covers only `motion_stream_adapter_tc04` and
`fpga_v8_capture_ov5640_ddr_tc04`. Neither production RTL, V5 inputs, TC03,
camera CDC, capture lease, whole-system runners nor project bindings are edited.
The tests use the **actual V5** adapter and capture wrapper as their reference.
The detector remains the unmodified V5 `block_motion_detector_tc03`.

## Candidate transformation

Both counters use unconditional per-bit data assignments:
`next[i] = (count[i] ^ (increment && &count[i-1:0])) & !clear`.
Bit zero has constant carry 1. This expresses exactly the original modulo
increment and reset priorities without expressing a shared conditional-adder CE.
No new clock of latency is introduced. The motion counter retains the V5
`$clog2(WIDTH*HEIGHT+1)` width. Capture pixel count and pixel limit remain **32
bits**. Source/active/publish sequences, overflow and short-frame counts, input
pixel diagnostics, fault snapshots and existing public debug words retain their
original widths. The packed two 16-bit reject counters retain their original V5
format; this candidate does not redefine the public statistics interface.

Motion FIFO, overflow recovery, dummy/excess tail handling, frame-end marker
drain and publication metadata remain unchanged. Capture admission, complete
predicate, lease gate, flush duration and the three existing `w_*` modules remain
unchanged. Keep all public output cycles unchanged when binding the candidates.

## Actual V5 binding boundary

`whole_candidate_v5_route_01/project.pds` binds `rtl/motion_stream_adapter.v`.
`inputs/source/ov5640/ov5640_top.v:409` instantiates the adapter for the passive
post-FIR/KF tap. Its VS register was merged with `diag_vs_q` in the routed design.

`rtl/fpga_v8_cooperative_top_v2_rfg01.v:1551` binds
`fpga_v8_capture_ov5640_ddr` for **cam5**. **cam6** at line 1647 binds the original
`ov5640_ddr`, whose implementation is
`inputs/source/ov5640/ov5640_ddr/ov5640_ddr.v`. The V5 failing cam6 pixel-count path
therefore does not belong to the candidate wrapper directly. The same bitwise
counter technique is applicable there. Integration can use a separately
authorized isolated `ov5640_ddr` candidate with the dynamic address/length
interface preserved. Alternatively the current cam6 parent actually binds
constant length 38400 and addresses `0x01c00000`/`0x01e00000`, with the
`prev_frame_base` output unused. An isolated top could map those constants to
the fixed wrapper's CAM_DATA_LEN/BANK0_ADDR/BANK1_ADDR and tie epoch_start and
lease_block low. That option still needs a dedicated differential regression
against the **original cam6 ov5640_ddr binding** before integration; the present
wrapper-versus-wrapper regression does not prove it. No parent binding is edited
by this task.

## DMA residual analysis (read only)

V5 residual path: `cam3_ov5640_top/ov5640_ddr/flush_count[2]` to
`cam3_axi_dma_write/wd_cnt[20]/RS`, slack **-0.001 ns**.
`full_detail` contains no CECO chain on this path. Its five logic levels take
1.155 ns; routing takes 6.023 ns (83.909% of the data path). The path traverses
the flush decode, local-reset-masked camera `data_available`, and DMA equality
comparison before the watchdog reset. This is **watchdog progress detection**,
not an external DMA reset directly wired to `flush_count`.

The relevant TC02 RTL is `axi_dma_write_tc02.v:241-251`:
when `waiting_source` is true, any change in `data_in_available` relative to
`available_q` resets `wd_cnt` on that same edge. Upstream `ov5640_ddr_w.v:314`
masks stored credits to zero whenever `axi_rst | capture_flush` is asserted.
Thus a flush changes credits combinationally and reaches the watchdog reset
through the 16-bit inequality and its control decode.

A feasible same-cycle isolated DMA fix is to compute explicit reset and
increment predicates, then express each watchdog bit as unconditional XOR
toggle plus data-path clear (as above). Preserve the original 24-bit watchdog
saturation at `24'hFFFFFF`, `WD_LIMIT` edge, `waiting_source` priority,
available-change progress rule and non-waiting progress/valid/ready behavior.
This targets RS mapping and permits local data logic instead of a shared reset
net. It requires its own differential tests at the saturation/timeout edges,
credit changes including flush, and AW/W/B backpressure before it can be accepted.
Mapping and slack still require later isolated PDS/route evidence.

The exact logical predicates to preserve in such a future candidate are:

```verilog
wd_clear = rst || abort_r ||
    (waiting_source ? (data_in_available != available_q) :
     (!burst_trans || w_progress || data_in_valid || !t_m_axi_wready));
wd_step = !wd_clear && (wd_cnt != 24'hffffff);
```

These are analysis pseudocode, not modified DMA RTL. In particular,
`!burst_trans` must be inside the non-waiting branch: applying it globally would
prevent the waiting-source watchdog from counting at all.

Do **not** just register the credits-change predicate: that delays watchdog
reset and may cause a timeout/abort on an edge where the original detects source
progress. Such a change is not cycle-equivalent unless the entire watchdog state
and its timeout consumers are retimed consistently. No TC02 DMA RTL was edited.

## Regression and receipts

Run `python project/fpga_v8_migration/timing_correction_04/run_regression.py`.
After it finishes, run
`python project/fpga_v8_migration/timing_correction_04/audit_stream_capture.py`
to verify all final pass markers, ten four-channel phases, input hashes and the
protected baseline before emitting `final_audit.json`.
The runner writes only under `receipts/stream_capture`, uses ModelSim and never
starts PDS. `results.json` is emitted only after all runs and protected SHA256
checks pass. Capture tests use frozen V5 FIFO RTL and the actual PANGO
`GTP_DRM36K_E1` primitive, not a behavioral replacement.

Motion differential cases cover two 640x480 seeds and a 64x48 seed, continuous
and randomly stalled complete frames, SOF+pixel0, short-frame restart, dummy and
excess tails, naturally reached FIFO overflow, recovery, reset and carry
boundaries. They compare the entire 320-bit public record every clock and compare
the pixel count, issued core tuple and 32-bit statistics.

Capture differential cases cover two 38400-beat seeds and a 2048-beat seed,
complete 307200-pixel frames, randomized AXI/command stalls, tag completion and
publication, short-frame restart, DMA abort, epoch reset, lease rejection,
naturally reached real-FIFO overflow, and all 32 carry/wrap boundaries using
paired state deposits. All 28 public output ports, including invalid-cycle
payloads and diagnostics, are compared every clock.

The existing full-resolution four-channel motion oracle is reused via a new
generated testbench binding under this candidate's receipts directory. It uses
the V5 frozen motion register bank and this adapter candidate. The original
testbench and all shared runner output directories remain untouched.

`v5_full_detail.json` retains the full reported paths; `path_summary.json` records
their original slack and CECO hops. The receipts explicitly set
`routed_timing_verified=false`: these are simulation-verified candidates, not a
claim of positive routed timing.

Additional independent receipts: `interface_audit.json` verifies identical
parameter/port declarations; `unchanged_logic_audit.json` removes only the old
pixel-counter assignments and the new generated counter block, then verifies
that every remaining RTL token equals V5. `counter_identity.json` checks 177756
integer cases over widths 1/2/3/4/8/12/19/32, including every 32-bit carry and wrap.
These checks supplement the actual RTL differential simulation and do not
replace it.
