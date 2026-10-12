# Optional FPGA inference read timing

This candidate copies `candidate_short_hold_viewer`, excluding build directories.
Deploy the short-hold candidate first; use this separate candidate if timing is
needed. No board operations, ARM build, RTL changes, or driver changes were made.

Set `DETVIEW_FPGA_INFER_TIMING=1` to enable one `qInfo` record per successful
`PangoDev::cameraReadFpga` call. Unset, `0`, and every other value disable it.
The clock must also report `QElapsedTimer::isMonotonic()`. OFF performs no
telemetry clock starts/reads or logging. Existing protocol timers/logs remain.

All phase fields are nanosecond offsets from this read's entry, using one
QElapsedTimer instance, rather than wall-clock timestamps:

| Field | Boundary |
| --- | --- |
| `acquisition_ns` | Initial transport lock acquired, before hold; includes initial transport waiting |
| `hold_command_issue_ns` | Immediately before issuing the hold register write |
| `hold_validated_ns` | Hold acknowledgement and same-frame identity validated |
| `raw_f2h_tag_ns` | RAW F2H and its commit tag checked |
| `converter_start_ns` | Immediately before issuing conversion command |
| `converter_done_ns` | Conversion completion and same-frame identity validated |
| `release_verified_ns` | Release command completed and idle-status acknowledgement checked |
| `raw_cpu_copy_ns` | RAW CPU copy completed after unlock and defaults restoration |
| `publish_ready_ns` | Input callbacks and selected tag prepared, before returning to caller |
| `total_read_ns` | Read entry through publish preparation, before formatting/logging |

`hold_command_to_release_ack_wall_ns` is release acknowledgement minus hold
command issue. This is measured host elapsed wall duration, including command
transport, FPGA polling, lock reacquisition, conversion and release transport.
It does not claim to measure the FPGA's internal hold cycles. Log formatting is
excluded from `total_read_ns`; the record is emitted with the lock released.
Golden RGB preparation, when verification is enabled, is included in the gap
between RAW CPU copy and publish readiness.

Inference queue waiting is omitted: the existing deferred input has no queue
enqueue timestamp in PangoDev. Initial transport waiting is visible in
`acquisition_ns`. Deferred input, model decoding and geometry are unchanged.
No additional DMA or register reads are used to obtain timing.

Native validation (Ubuntu WSL, Qt5, syscall fixtures; timings are host fixture
observations, not hardware performance measurements):

```sh
python3 local_timing_check.py
bash local_fair_check.sh
python3 local_short_hold_negative_check.py
```

All passed. Timing checks cover all six cameras at heights 480 and 640,
verification ON/OFF, 13 successful reads and one unpublished-hold timeout.
Each disabled run checks zero telemetry clock calls and zero timing records.
Enabled runs check 14 starts, 132 clock reads, 13 records, monotonic phase
ordering, hold subtraction/bounds and a real >=1ms delayed admission interval.
Every non-poll DMA command/address/offset/length/write value has the same trace
hash across all six runs; status polling is excluded because the fixture's
metadata thread changes the poll count through scheduling. Existing fixtures
also assert exact RAW/RGB transfer and lease counts, disjoint DMA, and RAW copy
after conversion/release. The negative test rejects the original early-copy
ordering. Existing class syntax and native verification checks pass.

`local_build/timed_viewer.diff` contains the production diff against short-hold.
`local_build/source_preservation.json` records the copied-source comparison;
only `main.cpp` changed, wholly within PangoDev. The timing test and this review
are the only added source files.
