# IOCTL stall analysis — read-only evidence, 2026-10-04

## Finding and causal boundary

The severe freezes include long DMA attempts omitted by successful-frame timing.
Recovery has six application-failed attempts, 86,989.608 ms total. After clipping
the first interval to the receipt's observation bounds, those intervals occupy
85,884.415 ms of 120,501.548 ms (71.272%). This is elapsed wall time, not DMA engine
busy time or exclusive kernel CPU time. The first attempt began before sampling.
The corresponding successful-frame DMA report means remain 1.112–1.979 ms.

A device-wide serialization mechanism can propagate a stalled DMA to other DMA
callers. It cannot, by itself, explain the measured delay inside an unlocked pixel
copy, stereo computation and independent GUI paths. No evidence yet distinguishes
kernel/MMIO stalls from time off CPU or another common system interruption. It is
incorrect to close this as generic CPU contention, a 10-second driver timeout,
FPGA failure, or a proven GPU-global lock. The exact missing counters are stated
below; no viewer/driver/FPGA fix was deployed.

## Identity and provenance

Read-only SSH (sudo only for reading protected /proc and source files) retained
`board_provenance_readonly.json`: complete calibration C++/headers and per-file
SHA256, driver C/header, build filenames/hashes, module metadata, dmesg tail and
fresh executable identity. No device node was opened, no DMA reader was started,
and no process/configuration/programming action was performed.

Fresh identity is **PID 106193**, starttime **20290276**, executable
`/userdata/detview-hdmifull/detview-hdmifull`, SHA256
`0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`.
It has `--model wb_v4_combo --fullscreen --no-tracking --prefer-hdmifull auto`,
without a stereo-config argument. This is different from last-known PID 105250,
hash `bbf5de26...`, and the original calibration PID 95911, hash `0d717a43...`.
No new scheduling sample of this changed viewer is used to explain old stalls.

The calibration source `/userdata/linaro/detview-calibration-work/src/main.cpp`
still hashes to **d3a38d77338168b6d95a8731efe99e7b443f08b0dee7bcc831d33bc544a0fd23**.
Its existing build/detview still hashes to
**0d717a430e46e13d61553bf74c5ea7f13aff5c69db8587136aa227b5705ad153**.
Both match the source/binary pair captured in the a1b1cf and 1182d4 capture.json
receipts. This resolves the missing-source issue in CODE_ANALYSIS.md: the actual
recorded source is now available, rather than the swap branch. However, the
receipts are runtime snapshots, not compile receipts. No frozen manifest tying
all compiler inputs/options/object hashes to that executable was discovered.
The qmake Makefile exists (SHA f59ddfbf...), but its existence does not prove
which source bytes produced the binary. Full executable-to-source attribution
remains incomplete. **The critical scopes are additionally verified directly
in the pinned original binary**, with SHA256 checked before and after the
read-only disassembly; `original_binary_scopes.json` retains the evidence:

* ioctlTmo symbol 0x1e710: clock_gettime at 0x1e754, alarm at 0x1e75c,
  ioctl at 0x1e76c, errno snapshot, alarm cancel at 0x1e784, endpoint clock
  at 0x1e790. fprintf/fflush follow at 0x1e858/0x1e860. The alarm flag is
  tested at 0x1e7d8–0x1e7e0, with forced -1 at 0x1e8cc. Thus diagnostic
  timing and alarm-failure censoring are verified for original binary 0d717a.
* cameraRead symbol 0x1e8f0: QMutex::lock at 0x1e93c, metadata ioctl calls
  at 0x1e980/0x1e9c8, frame ioctl at 0x1ea88. QMutexLocker::unlock at
  0x1eadc precedes restart 0x1eae4, then the literal NEON ldp/stp loop
  0x1eaf0–0x1eb0c and elapsed read 0x1eb14. There is no user mutex inside
  this copy scope in the original executable. Metadata RX 0x3ff000 and
  full-frame slot stride 0x97000 are also present in these instructions.
* Worker cameraRead call 0x25970 is followed by branches for zero, unstable
  and negative results at 0x25974–0x25980. Only the succeeding path adds
  read/DMA/copy sums and increments delivered sample count at
  0x259a8–0x259d4. This establishes successful-only accounting in the binary.

These verified function behaviors do not imply that every other source line,
the separately built optimized viewer, or any kernel module is thereby bound.

## All long ioctl records

Every `pango_ioctl cmd=` record found in local `log/100h_motion/**/*.log` belongs
to the five observation logs below; 19 records total. Inspecting retained JSON
and JSONL embedded log strings adds six different long records and two shorter
successful records. Thus the examined retained streams contain 25 different
long record signatures and 2 additional short ones (not a process-wide count).
They are kept separately,
with hashes, raw lines, timestamps, display windows and observation byte-range
receipts in `failure_attempts.json`. JSON log chunks duplicate these records and
are not counted again as new observations. The full old log overlaps the first
recovery slice and is explicitly marked in JSON. No aggregation across different
processes or overlapping streams is implied.

Every row has `cmd=c0045305`, `rc=0`, and raw `errno=11`, except recovery line 165
which has raw `errno=0`. **errno is not valid when rc=0**. Alarm 1 becomes an
application failure under retained source; alarm 0 is a successful return.
Camera comes from DDR address and is not a recorded TID. Recorded RX offset,
TID, retry ID and actual retry count are absent and remain null. Separately,
`rx_offset_under_retained_source` derives metadata scratch 0x003ff000 and
full-frame camera slot `(camera-1)*0x97000` from the retained camera_dma.h;
it is conditional source inference, not a value recorded by the binary. Metadata offset
0x96000 is 614400 bytes from its camera bank; full-frame offset is zero.

| Log | Line | Completion monotonic s | Camera | DDR address | Bytes | Elapsed ms | Alarm | Gap from previous logged end to estimated start ms |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| candidate_early | 23 | 200312.508 | 1 | 0x00896000 | 16 | 11353.066 | 1 | unknown |
| candidate | 67 | 200371.992 | 4 | 0x01696000 | 16 | 12135.246 | 1 | unknown |
| candidate | 136 | 200407.745 | 1 | 0x00800000 | 614416 | 12053.456 | 1 | 23699.544 |
| candidate | 170 | 200418.984 | 6 | 0x01c96000 | 16 | 10151.208 | 1 | 1087.792 |
| candidate | 198 | 200431.309 | 6 | 0x01e96000 | 16 | 11359.212 | 1 | 965.788 |
| recovery | 5 | 200516.818 | 6 | 0x01e00000 | 614416 | 9532.960 | 1 | unknown |
| recovery | 55 | 200529.180 | 1 | 0x00a00000 | 614416 | 11243.738 | 1 | 1118.262 |
| recovery | 66 | 200551.561 | 3 | 0x01096000 | 16 | 21357.365 | 1 | 1023.635 |
| recovery | 105 | 200563.821 | 1 | 0x00a00000 | 614416 | 11327.211 | 1 | 932.789 |
| recovery | 165 | 200588.302 | 4 | 0x01400000 | 614416 | 12067.740 | 1 | 12413.260 |
| recovery | 199 | 200610.791 | 6 | 0x01c96000 | 16 | 21460.594 | 1 | 1028.406 |
| final_restored | 33 | 201583.436 | 2 | 0x00c96000 | 16 | 21782.948 | 1 | unknown |
| final_restored | 68 | 201596.537 | 1 | 0x00a96000 | 16 | 12232.464 | 0 | 868.536 |
| final_restored | 102 | 201619.253 | 5 | 0x01800000 | 614416 | 21669.319 | 1 | 1046.681 |
| final_restored | 203 | 201656.701 | 3 | 0x01200000 | 614416 | 11479.529 | 0 | 25968.471 |
| final_restored | 235 | 201667.987 | 4 | 0x01496000 | 16 | 10236.108 | 1 | 1049.892 |
| optimized | 353 | 201103.965 | 2 | 0x00c00000 | 614416 | 5417.459 | 1 | unknown |
| optimized | 622 | 201129.773 | 2 | 0x00c96000 | 16 | 4364.742 | 1 | 21443.258 |
| optimized | 646 | 201135.753 | 1 | 0x00896000 | 16 | 4819.277 | 1 | 1160.723 |
| diagnosis full_recovery_log | 407 | 200629.065 | 1 | 0x00a00000 | 614416 | 3266.835 | 1 | 15007.165 |
| diagnosis full_recovery_log | 467 | 200638.315 | 5 | 0x01a00000 | 614416 | 3497.757 | 1 | 5752.243 |
| diagnosis full_recovery_log | 502 | 200648.572 | 1 | 0x00a96000 | 16 | 3610.741 | 1 | 6646.259 |
| diagnosis full_recovery_log | 2059 | 200895.798 | 3 | 0x01000000 | 614416 | 10473.479 | 1 | 236752.521 |
| profile initial optimized recovery tail | 27 | 201757.897 | 2 | 0x00e00000 | 614416 | 9412.257 | 1 | unknown |
| profile initial optimized recovery tail | 82 | 201769.676 | 5 | 0x01896000 | 16 | 10647.671 | 1 | 1131.329 |

Estimated start = printed completion minus elapsed. Printed time is truncated
to milliseconds, so start/end are uncertain by approximately 1 ms. Gaps are
between logged slow attempts, not proof of continuous retries or idle DMA:
unlogged fast attempts occur in between. Several successive gaps are about one
second, but a retry cadence cannot be reconstructed from these records.

The first three logs are under `pll56_deploy_a1b1cf04843840d7b699d2ba769443cc`;
last two under `pll56_optimized_1182d414dcc7436f841bb2170ae93960`.
Diagnosis is `readonly_diagnosis_20261004.json:full_recovery_log`; table line
numbers refer to lines of the embedded string, not physical JSON file lines.
The profile tails are in `thread_stall_20261004_224736.jsonl:1:initial_log_tail`
under the optimized recovery remote log name. Their times precede sampler PID
105250's starttime 201784.96 s; they must not be assigned to its threads.
The other profile-header recovery tail adds successful alarm=0 records
`t=201048.819 addr=0x01400000 len=614416 ms=36.516` (embedded line 61) and
`t=201051.124 addr=0x01600000 len=614416 ms=31.855` (64), both rc=0 errno=11;
gap between them is 2273.145 ms. They are recorded without pretending the header
sampler identity establishes ownership of historical log content.

| Observation | Logged failed attempts | Failed elapsed ms | Logged successful elapsed ms |
| --- | ---: | ---: | ---: |
| candidate_early | 1 | 11353.066 | 0 |
| candidate | 4 | 45699.122 | 0 |
| recovery | 6 | 86989.608 | 0 |
| final_restored | 3 | 53688.375 | 23711.993 (2 attempts) |
| optimized | 3 | 14601.478 | 0 |
| diagnosis full recovery (overlaps recovery above) | 10 | 107838.420 | 0 |
| profile optimized recovery tail | 2 | 20059.928 | 0 |
| profile a1b1cf recovery tail | 0 | 0 | 68.371 (2 attempts) |

Restored_current and earlier rollback observation contain no slow diagnostics.
Zero logged failures does not establish zero attempts or zero shorter failures.

| Recovery camera | Logged failed attempts | Failed elapsed ms | Successful-frame DMA report means min–max ms |
| --- | ---: | ---: | ---: |
| 1 | 2 | 22570.949 | 1.112–1.692 |
| 2 | 0 | 0 | 1.148–1.939 |
| 3 | 1 | 21357.365 | 1.113–1.822 |
| 4 | 1 | 12067.740 | 1.176–1.979 |
| 5 | 0 | 0 | 1.345–1.687 |
| 6 | 2 | 30993.554 | 1.347–1.725 |

Each camera has nine capture mean reports. No report supplies auditFrames or
its start/end bounds. Therefore sample-weighted successful means, complete
attempt counts, and a true all-attempt mean cannot be calculated honestly.
The summarizer preserves null for those quantities instead of averaging means.

## Exact retained application timer scope

Line numbers below are remote calibration `src/main.cpp` at SHA d3a38d..., whose
full text is retained in board_provenance_readonly.json.

* `cameraRead:395` acquires dmaMutex before tag reads at 397 and full-frame
  submission at 406. `ioctlTmo:435–440` starts CLOCK_MONOTONIC, arms alarm,
  calls ioctl at 437, snapshots errno, cancels alarm, then reads the clock.
  **The diagnostic excludes application dmaMutex acquisition.** It includes
  alarm setup/cancel, ioctl syscall time, kernel semaphore waiting and all time
  descheduled inside the interval. It is not a pure kernel execution timer.
* Diagnostic fprintf/fflush at 443–448 happens after the endpoint clock, so it
  is excluded from diagnostic ms, although callers still hold dmaMutex there.
  The outer frame-DMA timer at 405–407 includes that logging overhead.
* `timeoutHit_` at 450–453 turns even `rc=0` into failure. Its process-wide
  `alarm(sec)` is not a guaranteed per-thread cancellation deadline: delivery
  may occur in another eligible thread. Alarm-handler execution and clock CPU
  were not timestamped. Long `alarm=0` rows disprove treating alarm as reliable
  proof that no long stall occurred. No signal policy was changed.
* Failed, no-new-tag and unstable results continue at 590–595. Only delivered
  frames accumulate readNs/dmaNs/copyNs at 601–602 and enter means at 640–643.
  Censoring is explicit in this recorded calibration source, not inferred from
  swap, and corroborated in original binary disassembly. read_ms includes buffer preparation and application lock acquisition;
  successful frame_dma_ms includes neither preceding tag ioctls nor lock wait.
* Lock unlock is at 413; copy timer restarts at 414, copyCameraPixels at 415,
  endpoint at 416. Allocation at 585, RGB conversion at 607–611 and publication
  lock at 621 are outside copy_ms. Thus that application's DMA mutex cannot
  directly account for 400–870 ms measured inside the pixel-copy scope.

## GUI and other concurrent paths

Recovery line 55: ioctl 11243.738 ms; display window [200516863,200529178),
gui_delay max 11247 ms (line 47), paint_total max 77.907 ms (45).
Recovery line 66: **16 bytes**, ioctl 21357.365 ms; display window
[200529178,200551564), gui_delay max 21359 ms (79), paint max 76.387 ms (77).
Differences are 3.262 and 1.635 ms. They support a common elapsed-time
interruption in independent paths; aggregate stage windows do not give precise
start/end times for the individual GUI event.

Not every stall lands in gui_delay. Recovery line 105 ioctl 11327.211 ms occurs
in a window with camera_upload max **11337.317 ms** (115), paint max 11362.076 ms
(122), NPU infer_service_ms **11337.62** (112), gui_delay max only 16 ms (124).
Line 165 ioctl 12067.740 ms accompanies camera_upload max **12077.757 ms** (176).
Another window, [200563874,200575173), has HUD raster max **10248.373 ms** (148)
and NPU service 10259.49 ms (143), but **no corresponding slow ioctl record**.
Thus slow ioctls are not necessary for every display stall. A GUI upload wall
timer is also not proof that GPU work itself executed for that duration.

Copy means include 424.606 ms on C3, 327.735 ms on C2 (167–168), and 870.662 ms
on C4 (200), while DMA delivery averages are small. Stereo wall outliers also
exist (recovery 102: max 21655.59 ms). These scopes need wall/CPU pairing.

## Driver source: sleeping waits, not a 10/20-second polling loop

Retained board source:
`/userdata/linaro/projects/fpga/RK3568/driver/pango_pci_driver.c`, SHA256
**b7f61d8f628e4db7e7d520742b1a195dea4f2b18292203ff9ef5104c16460b72**.
Header SHA 7bb7ee3a... . Root installed file `/root/ov5640/pango_pci_driver.ko`
hashes **0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861**,
matching the file named `pango_pci_driver_fixed_20260926.ko`. Several older
modules also exist. Loaded module reports taint O but no srcversion/version;
these on-disk hashes do not prove which bytes are currently loaded or were
loaded during an old interval. No source-to-module compile receipt was found.

* `pango_cdev_ioctl:435` uses `down_interruptible(&_sem)` before dispatch.
  `_sem` is held across DMA waits until `up:974`, with error-path releases.
  This is a sleeping device-wide semaphore. Its acquisition has no timeout
  of its own and is included in the application ioctl wall diagnostic.
* F2H (`PCI_DMA_WRITE_CMD`) waits at 622–624 for atomic g_dma_flag 0→1,
  timeout **800 ms**. Parameter copy_from_user at 640 occurs before spin_lock
  at 646 in this board source. Under the spin lock it programs MMIO registers
  through iowrite32 wrappers (336–357, 654–663), then unlocks at 664.
* MSI completion uses `wait_event_interruptible_timeout` at 669–671 with
  **120 ms**. old_w is sampled at 661 **before** trigger writes at 662–663,
  unlike the local migration version. There is no payload memcpy in this
  F2H command; it targets a coherent RX buffer subsequently mapped to user space.
* H2F has 120-ms idle and completion waits (546–548, 602–604). Image/NPU waits
  have 1000/6000-ms expressions (827–829, 850–852). Comments claiming 100 ms
  or 60 seconds disagree with constants; executable expressions are authoritative
  only after module binding. No 10000/20000-ms F2H wait was found.
* IRQ0 at 1166–1207 releases g_dma_flag, increments the appropriate completion
  counter, may submit queued image/NPU work, and wakes g_msi.queue. IRQ1/IRQ2
  at 1211/1238 schedule those work paths. No 10-second spin/msleep polling loop
  was found in these handlers. Normal spin_lock is not global IRQ masking;
  it disables preemption on its holder CPU, and is released before sleeping.
  Unmeasured MMIO/bus delays under that short region remain a possibility.

The local migration driver instead has 800-ms waits and parameter copy under
spinlock with unsafe early-error paths; it is a different source, not evidence
that the board source has the same bug. Its MSI counter-after-trigger race is
also already different in the retained board source. Do not propose that stale
fix for this executable/module without binding.

Retained dmesg contains module unload/reload at 200465/200485 and no timeout,
soft-lockup, RCU-stall or hung-task message in the retained tail covering the
listed recovery intervals. Silence does not exclude stalls or missing messages.
A semaphore wait or completion wait alone blocks the calling threads, not all
GUI/conversion/stereo execution on the other CPUs. Driver semaphore serialization
is a mechanism, not established root cause for the common 10–22-second pauses.

## PLL/CAM3–4 conclusion

Candidate log shows positive CAM3/4 tag_advance_rate records: candidate
lines 138/140 have C3 30.06 and C4 29.98, while lines 207/206 have C3/C4
54.70/54.78 and lines 4/167 fall to 2.43/2.77. These show observed tag
advances under the viewer's estimator, not independently timestamped sensor
frame counters. Do not claim a verified fixed PLL rate from an unweighted mean
of these inconsistent windows. Existing candidate metrics mean C3/C4 tag rates
are 30.766/32.530 and delivered rates only 2.199/2.203; targets were not met.
No new FPGA claim or CAM3/4 hardware timestamp progression was established.

`project/tools/measure_dualcam.py:162–173` read_tags returns values and individual
read durations, but this probe is for CAM1/2; its sampling prints only a shared
monotonic sample time (194–207), and exceptions replace durations with zero.
No matching candidate CAM3/4 per-tag timestamp capture was found in the inspected
observation receipts. It was not run: that would introduce another DMA reader.

## Reviewable next change and exact missing evidence

Implemented only an isolated offline summarizer, `summarize_ioctl_stalls.py`.
It counts alarm failures and negative-rc failures separately from successes,
preserves all distinct attempts, records address-derived cameras and unknown
fields, correlates display aggregate windows, and clips elapsed intervals to
observation receipts. It never imports the board helper or accesses a device.
Validation: synthetic success (40 ms), alarm failure (10000 ms), errno failure
(50 ms) remain three distinct attempts with failure sum 10050 ms; raw recovery
line/count/total and 16-byte/gui-delay/upload crosschecks pass (2 tests).

No driver bug has been causally established, so no unknown-source viewer or
driver patch was prepared for deployment. Before a runtime diagnostic build,
retain compiler-input hashes, Makefile/options, objects and link-output hash for
an isolated frozen copy of the now-retained calibration source. Keep that
candidate separate from the current parent-owned HDMI viewer.

Minimal instrumentation proposal for that reviewed frozen candidate:

1. For every ioctl, retain monotonic begin/end, CLOCK_THREAD_CPUTIME_ID deltas,
   gettid, sequence number, camera, command, DDR address, RX offset, requested
   bytes, rc, valid errno, and alarm state. Maintain success/failure count/sum/max
   and paired CPU sums; include both tag reads and frame reads. Measure syscall
   separately from watchdog setup/cancel and log cost.
2. At cameraRead:395, measure application mutex wait and complete locked section.
   At 414–416, pair copy wall and thread CPU. Capture allocation, conversion,
   publication wait and logger durations separately. Include all result categories
   and explicit capture-window bounds/sample counts; emit after releasing locks.
3. If low thread CPU accompanies high ioctl/copy wall, correlate with same-PID,
   same-starttime per-thread scheduler runtime/runnable-wait/wchan sampling.
   Runnable wait supports scheduler starvation; sleeping wait supports blocking;
   broad missing runtime needs kernel/IRQ evidence. High copy CPU instead calls
   for mapped-memory/frequency investigation. Neither wall time alone nor generic
   process CPU% supplies this distinction.
4. Only with a bound module, add driver timestamps around semaphore acquisition,
   idle wait, MMIO programming, completion wait and IRQ notification. This
   distinguishes unbounded semaphore wait from a delayed MMIO instruction,
   completion/interrupt latency and wake-to-run delay. No current counters expose
   those boundaries; none establishes global IRQ masking.

These measurements make a targeted correction reviewable without changing
priority, capture caps, OpenCV pools, rendering or FPGA state on speculation.

## Follow-up module binding and clock capture — 2026-10-05

`log/100h_motion/loaded_driver_20261005_001704.json` binds the current loaded
module's GNU Build ID `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a` to both
`/root/ov5640/pango_pci_driver.ko` and the retained `fixed_20260926.ko` file.
The file SHA remains `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861`.
This identifies the current loaded build; it does not retroactively bind every
historical interval. `loaded_driver_disassembly.json` retains actual module
instructions: the ioctl calls down_interruptible and schedule_timeout. F2H
idle/completion paths initialize 200/30 jiffies; retained CONFIG_HZ=250 makes
those 800/120 ms, consistent with the recorded source. Other dispatch branches
have their own limits. No current-module 10/20-second F2H wait was established.

`clock_stall_20261005_000249.summary.json` contains 116 samples over 120 seconds.
MONOTONIC, RAW, BOOTTIME, realtime and host receive intervals agree; maxima
were about 1.087 seconds, with no multi-second jump. Maximum vDSO/syscall clock
skew was 0.748 ms. The sampled viewer PID 109952 is the separate HDMI binary,
SHA `0301f690...a737`, so this excludes a reproduced current clock fault only.
CONFIG_SCHEDSTATS is available but its runtime sysctl was 0; zeros must not be
reported as measured zero scheduling wait. The runtime diagnostic candidate
uses thread CPU clocks without changing that sysctl.
