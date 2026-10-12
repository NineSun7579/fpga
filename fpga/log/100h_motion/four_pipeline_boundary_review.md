# Independent four-camera pipeline boundary review

## Verdict and scope

**Scoped PASS: no actual RTL protocol defect found in the reviewed core/adapter boundary paths.** The final local-camera integration implements CAM1–4 motion only, reserves CAM5/6 motion slots as zero, and retains all six video paths. This is a read-only source review with inspection of existing regression evidence; it does not certify the active PDS build, physical RAM mode, timing closure, or hardware behavior.

Reviewed `project/motion_100h/source/motion/block_motion_detector.v`, `motion_stream_adapter.v`, actual `source/top.v` and `source/ov5640/ov5640_top.v`, plus `project/sim/motion/tb_block_motion_detector.sv`, `tb_motion_stream_adapter.sv`, `tb_four_motion.sv`, runners, integration checker, and existing result/fault logs. No sources, PDS files, existing logs, simulator libraries, or build inputs were changed. No tests were rerun; no build was polled and no hardware was accessed. This report is the only written artifact.

## Core boundary trace

Line references below are to the reviewed final detector.

For the hardest case, let E be a complete frame's end edge and let its last pixel, accepted at E−1, also be sampled. Values in this trace refer to pre-edge state unless explicitly described as a resulting assignment.

| Edge | Sample/decision/update behavior | Frame/publication behavior |
| --- | --- | --- |
| E−1 | RAM reads the old byte and writes the new luma. `compare_pending` becomes 1; current luma and destination are registered. | Last image pixel advances `pixel_count` to TOTAL_PIXELS. |
| E | Registered old RAM byte and current luma produce `changed_q`; `select_q` decodes that sample's block; `update_pending` becomes 1. | End does not consume a pixel. Complete end sets `end_pending`, snapshots reference validity, makes reference valid, and deactivates the frame. |
| E+1 | The old final decision commits to local hits, sample count, bitmap, block count, and bbox using pre-edge `update_pending/changed_q/select_q`. | Earliest legal new start sees `end_pending=1`, resets position and both pending stages, and sets `clear_after_publish=1`. The work-clear condition is false, so the old final update is preserved. `publish_pending` becomes 1. |
| E+2 | New pixel zero can read/write history and enter the comparison stage. It cannot yet update work. | Publication reads the settled old work using nonblocking-assignment pre-edge values. Deferred clear resets the work counters/bitmap/bbox in the same edge. |
| E+3 | New pixel zero's changed decision and destination are registered. | Old result strobe/valid return low. |
| E+4 | New pixel zero updates the cleared new-frame work. | No old-frame state enters the new result. |

This follows directly from acceptance gating at lines 54–57, stage scheduling at 158–172, publication at 177–189, start at 191–203, and mutually exclusive work clear/update at 207–237. In particular, assigning `update_pending <= 0` on E+1 does not cancel the pre-edge old final update in that same edge. Conversely, deferred clearing at E+2 cannot erase pixel zero's future update, which occurs at E+4.

A start at E+2 also works: publication snapshots the settled old work, while the start clears work immediately and consumes no marker pixel. With no new start, work remains settled until a later start clears it. A 1×1 frame is covered by the same trace: pixel zero at E+2 can be the entire next frame, whose end is E+3, update E+4, and publication E+5.

## Local thresholds, consecutive samples, and stale selection

The RAM output, current luma, and block destination advance together. For consecutive accepted samples A at T and B at T+1, the decision at T+1 uses A's pre-edge registers/history byte; at T+2 A updates work while B's decision is registered. At T+3 B reads the local counter after A's increment. Thus consecutive hits in the same block require no counter forwarding and do not lose increments.

`mark_block[b]` requires all of `update_pending`, `changed_q`, `select_q[b]`, and local `block_hits[b] == BLOCK_THRESHOLD−1` (102–103). Each local counter saturates at BLOCK_THRESHOLD (224–225), so only the crossing hit marks/counts the block; later hits still increment `samples_work` but cannot increment `blocks_work` again. This also works for BLOCK_THRESHOLD=1. Split hits across different blocks cannot pool toward a threshold.

`select_q` and `changed_q` may remain nonzero or stale during idle clocks. That is harmless: work mutation requires `update_pending && changed_q`, and mark logic independently requires `update_pending`. Start clears both pipeline-pending flags. Ordinary restart also takes the work-clear branch, suppressing a pre-edge pending update on that edge. Reference invalidation makes the first new-frame sample register `compare_enabled=0`; consequently stale history and selection cannot leak a changed hit into a seed result.

## Restarts, malformed frames, and tails

An active start invalidates reference (193–194), resets coordinates/address/count, and discards both pipeline stages. A complete pixel stream without an end remains active and is therefore an aborted frame on restart, rather than a usable reference. A short explicit end does not schedule publication and invalidates reference (248–254). Its last accepted sample can still settle internally, but there is no result strobe; the next start clears that work before any new sample can update it. RAM need not be restored because the reseeding complete frame overwrites every sampled address with comparison disabled.

Marker edges and surplus raw pixels never access history: `accept_pixel` excludes start/end and requires count below TOTAL_PIXELS. The adapter excludes tails from `fire` after the image count completes. One tail is tolerated. On the second tail, `excess` issues a synthetic core start without a pixel and sets sticky error/tail_bad. That leaves the core active; the next real start is an active restart and invalidates reference. Further tails do not issue repeated synthetic starts. All tail pixels bypass RAM, and error belongs to the next completed adapter record.

## Adapter issue, capture, and FIFO overflow

For the last FIFO pixel issued at T, the complete registered tuple is accepted by the core at T+1. The adapter issues end at T+1, consumed by the core at T+2. Core publication is T+4, and the adapter observes that registered strobe and captures all 320 bits at T+5. Setting `marker_idle=4` at T prevents a queued new boundary from issuing during T+1 through T+4. It can issue at T+5 and be consumed at T+6. Therefore old publication metadata remains stable through capture; a new first pixel cannot race the old record.

Coincident source VSYNC/pixel zero is kept as one FIFO tuple. Its start is issued first; `head_started` retains the same head for pixel issue on the next clock. For a start without a valid pixel, the tuple pops immediately. Consecutive image pixels remain one per cycle. In a full FIFO with a simultaneous pop, push is legal: pre-edge head data/sequence are captured before the same array slot is rewritten by nonblocking assignment, while occupancy stays 16.

Overflow is `push && queued==16 && !pop` (55). On the overflow edge, `fire` is false, and the outer `overflow || overflow_reset` branch bypasses both normal issue and record capture (101–112 versus 153–158). Even if the old core strobe is high on that edge, it is not captured. The edge sets `overflow_reset`, asynchronously asserting the detector's local reset through `rst_n && !overflow_reset`; this clears its end/publication pipeline and reference without clearing history RAM. The following clock also takes the flush branch and suppresses capture. FIFO pointers/occupancy, issued tuple, boundary state, and acquisition are cleared; the held public record survives.

Recovery requires a fresh source VSYNC after flushing. Mid-frame pixels are excluded because acquisition is false. Source-start counting continues even for dropped starts, so the recovery record sequence can jump, as documented. `error_pending=1` survives until the first complete recovery frame snapshots it into `publish_error`; that frame is a comparison-invalid seed. The next complete frame can compare normally. Existing coverage demonstrates recovery and held-record behavior; the exact artificial coincidence of overflow with an already-high core strobe is established here by branch/reset analysis rather than a dedicated directed test.

## Oracle independence and actual regression evidence

The core scoreboard works in image/frame space: it samples image coordinates, computes luma/difference, accumulates unrestricted per-block hits, and scans the completed hit array for threshold/bbox results (TB 153–185). It does not reproduce the DUT's pipeline, saturating local update implementation, decoded selector, or publish/clear state. More importantly, `literal_check` (137–150) compares published fields directly against passed constants, independently of `gray`, reference storage, hit accumulation, and the frame scoreboard.

The default and packed-dimension core configurations both explicitly check the six-frame oracle: black seed; black static; eight white sampled pixels in block 0; the same eight static; black removing those eight; all-white changing 19,200 samples and marking 192 blocks with bbox (0,0)–(15,11). Additional literal checks distinguish seven hits from eight, eight hits split four/four across blocks 0/1, and a final sampled hit marking block 191 at raw (636,476). Unsampled-only changes produce zero hits. Single-pixel literal cases independently check differences ±15, ±16, and ±17 around threshold 16.

The small core configurations exercise dense consecutive samples, partial edge geometry, immediate restart after a sample, complete-without-end abort, reset with populated history, and the earliest legal start/first-pixel/publication overlap (TB 304–339). Their expected boundary payloads use the frame model; the default-size literal final-sample case itself is not a sample immediately adjacent to end because the default final sampled coordinate precedes the last raw pixel. The dense and 1×1 configurations supply that immediate-end pipeline coverage. This distinction matters when interpreting the default literal test.

Adapter content checks compare the entire 320-bit ABI against constants (TB 49–57, 66–95, 124–128, 188–222). These include last-pixel contrast, short restart, dummy/excess tails, overflow/reacquisition, source sequences, and 20 alternating tiny frames with five idle clocks between frames. The expected-event-tuple monitor (21–30) does mirror FIFO issue wires; it checks the register-boundary alignment only. It is not the independent motion oracle, and the independent packet checks provide the content evidence.

The four-camera `expected(f,c)` function (55–79) contains fixed packet counts/flags and predetermined bitmap/bbox positions for blocks 0,17,34,51. It does not read detector work state. In phase 4, all-white compared with eight previous white samples correctly expects 19,192 changed samples (`0x4af8`), rather than 19,200. Phase 7 camera index 2 retains phase 6 sequence/content because its frame is short; phase 8 reseeds with error flag 4; phase 9 compares again. Every record change is checked against this oracle, and phase-end checks/publication counts prevent silently missing publications. Direct timing assertions require core end+2 and adapter end+3 for all 39 completed frames.

Existing evidence inspected:

- `motion_results.log`: PASS all core checks; default and packed cases each 16 publications/5,094,401 cycles, sparse 28, dense 28, single 35; explicit literal PASS lines. Zero errors, one inherited simulator optimization warning.
- `adapter_pipeline_results.log`: final adapter suite PASS, including forced overflow, recovery, last-sample ABI, default 640×480 bitmap/count/bbox, and sustained five-clock blanking. The older `adapter_results.log` lacks the final sustained-blanking PASS and was not used for that claim.
- `four_motion_results.log`: all ten phases PASS and final PASS at 3,378,505 cycles; 10/10/9/10 completed camera publications, enforced by TB counters. Zero errors, one simulator optimization warning.
- `four_motion_fault.log`: deliberate expected snapshot-bit corruption fails at camera 0 word 0 (`actual=00000001`, `expected=00000000`, TB line 135). This proves the frozen snapshot checker rejects that injected fault; it does not prove every possible detector mutation is detected.
- `four_motion_integration.log`: static actual-top integration PASS (UTF-16 encoded file).

Provenance qualification: `run_motion.do` and its inspected core transcript compile `../../source/motion/block_motion_detector.v`, not the motion_100h path. Both current detector files were independently compared byte-for-byte and are identical. Adapter/four runners and transcripts explicitly compile the motion_100h files. Existing transcripts do not embed source hashes, so this review does not claim cryptographic proof of historical source identity. No rerun was needed to resolve a suspected RTL defect.

## Actual local-only integration and video preservation

Actual top declares CAM5/6 motion records as `320'b0` (1193–1194) and orders the six-slot record bus `{cam6,cam5,cam4,cam3,cam2,cam1}` (1195–1196). Four local `ov5640_top` instances connect distinct CAM1–4 records at 1289,1501,1573,1674. The camera wrapper instantiates one passive adapter at 409–414, tapping `kf_video_data/valid/vsync` in `video_clk`, with reset from `video_rst`. All four local instances connect that clock/reset to `axi_clk/axi_rst`; the tap has no ready/backpressure output.

CAM5/6 retain enabled `ov5640_ddr` video engines at top 1803 and 1884, including positive `s_data/s_data_valid/s_vsync` connections to their pixel/de/vs streams at 1816–1819 and 1897–1900. Their separate `axi_dma_write` instances remain at 1839 and 1920. Local cameras retain their video wrapper/stream connections. No direct top-level motion adapter adds detectors to the fiber cameras. The integration checker and four-camera TB corroborate reserved slots 4/5 and ABI ordering; the TB intentionally simulates only the four local adapters and register bank, not the vendor top or six video engines.

## Remaining scope limits

The supported contract requires positive geometry/block thresholds, pixel threshold 0–255, non-overridden derived geometry, synchronous inputs, read-first history RAM, and at least five source idle clocks per frame for sustained adapter throughput. Below-contract blanking can overflow and is handled as loss/reacquisition, not uninterrupted motion service. The fixed record format is reviewed for the default 16×12 block geometry. Full-top vendor-IP simulation, all-six video runtime validation, BRAM inference/mode, active fresh-build results, and on-board verification remain outside this review. No required RTL fix was identified within the requested scope.

## Reviewed snapshot SHA-256

| File | SHA-256 |
| --- | --- |
| motion_100h/source/motion/block_motion_detector.v | `d6afdc1661772d39cbeb09e90465da1141c77e2f349253c6a0e7ac290ac1f80a` |
| motion_100h/source/motion/motion_stream_adapter.v | `70960e885ffd390b19594b4cd258ac2de3d47180d7d1fac225e3552134103d22` |
| sim/motion/tb_block_motion_detector.sv | `f067b2fad0a513a4dd29982d86a9e8fa1e8daa9c3ee882cc95300a27a45f58b6` |
| sim/motion/tb_motion_stream_adapter.sv | `00a79c15d48da16e4ac204bfec70143b90abfaab8dd8e19e704ca56eb9d85d49` |
| sim/motion/tb_four_motion.sv | `e2a917fc95e3f792d0f2ab287e4beaf932a9ec04ebdc67227baf3ed006732c40` |

Paths in this table are relative to `project/`.
