# Host-only converter / RAW overlap candidate

Base: `../candidate_prefetch_lead_viewer`, copied without local build outputs or Python caches. The original candidate is unchanged. Production diff: only `main.cpp`, moving the jobs-counter read and converter trigger ahead of the existing complete RAW F2H.

Acquisition order:

1. Freeze the selected camera and validate the complete lease identity, including its initial source commit tag. Preserve the existing already-delivered tag rejection before any conversion trigger.
2. Read the current jobs generation; trigger conversion with the camera hold still asserted.
3. Transfer the same complete RAW payload plus all 16 bytes of appended metadata to the same camera RX slot. Check its appended tag against the frozen sequence.
4. Poll for completion status and **exactly** `uint32_t(jobs + 1)`, then repeat the complete identity validation. Release only after both RAW and conversion have passed these gates; verify release and default selector restoration before copying RAW.
5. Preserve deferred RGB transfer / BEGIN, synchronous consumer run / END, admission, backing lifetime, and latest-RAW pipeline behavior.

No DMA was added. RAW DMA time still measures only its F2H, captured time still marks its completion, and `holdValidated` still precedes trigger/capture/release. The 30 ms lead default, cadence, environment settings, geometry, copy boundary, and pipeline source are unchanged.

Failure review: this base has no `cancelLease` recovery path. A bad RAW tag after triggering, DMA error/alarm, converter deadline, or identity mismatch goes directly to the existing process quarantine: SIGSTOP followed by an infinite pause. It does not release the hold, restore selectors, retire admission, close transport ownership, or reuse the converter. This remains a fail-stop candidate requiring parent hardware quiescence/recovery; it is not a recoverable failed-frame path. An uncertain converter is never assumed idle. No driver changes were made.

Host verification command (WSL/Linux with Qt5 and g++):

```sh
bash local_overlap_check.sh
```

Verified results:

- Actual extracted PangoDev syscall fixtures pass with RGB disabled, enabled, timing enabled, and byte-parity verification enabled; six cameras and both geometries preserve RAW slots and deferred RGB/BEGIN/END counts.
- Conversion now starts busy rather than completing inside the trigger ioctl. A separate worker signals completion while RAW is still in its ioctl for the 480 geometry, or after RAW finishes when the completion poll starts for the 640 geometry. The fixture asserts trigger-before-RAW and prevents release without observed exact completion. Existing metadata transport fairness and post-release copy probes still pass.
- Sixteen cases pass: initial tag mismatch, already-delivered tag, appended RAW tag mismatch, source/camera/sequence/epoch/destination/mode changes, stale completion, skipped jobs generation, early release, FPGA error, RAW DMA error, RAW timeout alarm, and converter timeout. Fatal cases assert no release, RGB transfer, BEGIN, input publication, or new admission. Initial-tag and already-delivered rejection assert no trigger.
- Three compiled mutations are rejected by assertions: RAW-before-trigger, trigger-before-initial-validation, and accepting a skipped jobs generation.
- Actual classes syntax, fair DMA selftest, native output helper checks, prefetch selftest, and comparison against the lead parent pass. Only `main.cpp` and the protocol fixture differ among inherited source files.

Review conclusion: the small production diff preserves the prior completion and identity gates and keeps the hold across both operations. Host evidence establishes ordering and fail-stop ownership, not FPGA/PCIe concurrency correctness or measured latency. Any anticipated 1–3 ms improvement remains unproven. ARM full-pipeline validation and hardware measurement are deferred to the parent; this work made no board calls, RTL/driver changes, deployments, or commits.

Use `local_overlap_check.sh` for this candidate. Inherited review documents and parent-specific preservation/negative scripts describe earlier candidates and are not overlap acceptance evidence. Generated logs and binaries remain under `local_build` and are excluded from source comparisons.

Parent independent review found no production-code blocker for a bounded exact
parity trial, conditional on this exact candidate passing ARM pipeline tests.
Review inspected code and saved fixture evidence; it did not rerun host tests.
The recovery precedent is `../lead_trial_reboot_recovery`: an uncertain DMA
lifetime required reboot, followed by original SRAM programming and original
module/viewer recovery. Never reopen or forcibly unload a quarantined process.
On trial failure preserve process/boot identity, runtime and kernel logs, then
use that authorized reboot recovery sequence. Verify six-camera capture and
inference after recovery; successful programming/launch alone is insufficient.
On normal retirement, verify actual restored runtime health as well. Previous
normal rollback hit a DMA timeout; do not treat a restore receipt as proof of
healthy capture. SPI Flash remains untouched.

## Board trial — not accepted

ARM build `1791612684241983800` (executable SHA256
`e2d7280c50e0f0711c13461d5bafd978fe5dbac4556210e89ff96c06510d41e9`)
passed all six target selftests. Deployment `1791613638189975800` retained
129 same-frame exact input/native-output pairs for Cam1/MVP only.

Verification-off ON/OFF/ON windows measured Cam1 capture 38.14/44.86/38.72
FPS. ON mean hold was 23.81/23.15 ms and accepted-result age p95 was
140/121 ms, versus OFF 143 ms. Other cameras retained their usual rates.
The prior serial lead trial's 25.58 ms mean hold is a historical comparison,
not a matched demonstration of overlap benefit. Fresh display varied materially
between windows; the final ON sample above 30 FPS does not prove stability.

Capture acceptance failed. Original recovery was started; see `../ACCEPTANCE.md`
for actual recovery health. No production adoption or performance gain claim.
