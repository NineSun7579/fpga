# Isolated configurable lead candidate

Copied from candidate_prefetch_checked_viewer, excluding local builds and build
outputs. No board calls, deployment, RTL/driver changes or commits. The display30
baseline and every existing candidate are preserved. Earlier copied review notes
describe their respective ancestors; this note describes the current delta.

The fixed 120 ms lead had measured age p95 204 ms versus OFF 138 ms. This candidate
makes preparation lead configurable; it claims no performance gain.
DETVIEW_FPGA_PREFETCH_LEAD_MS defaults to 30, accepts ASCII decimal 0..120
(leading zeros allowed), and rejects signs, empty input, overflow, junk, and any
leading/trailing whitespace. Invalid input warns once and uses zero lead without
terminating production. Effective lead is clamped to the current interval.
The parser is reached only inside the RGB-enabled preparation branch. Request
cadence still uses the actual submission timestamp and original urgent/bypass
policies. Admission, model revision, stop/ready, exact history and overflow/latest
RAW handling are otherwise unchanged.

DETVIEW_FPGA_PREFETCH_TIMING=1 opts into CLOCK_MONOTONIC millisecond timestamps
for arm, claim, hold_command, hold_validated, release, publish, and request. Arm
belongs to the first successful arm under the admission mutex. The capture job
carries the stages until Input construction, then copies them into plain int64_t
fields before publication. The controller writes request and logs source frame ID,
generation, camera (zero based), and tag before inferenceRequested. No other
thread reads the request timestamp. Disabled instrumentation performs no extra
clock calls, logging or DMA. hold_validated is after the full lease/tag identity
validation; release is after verified release and default selector restoration.
Only completed frames actually submitted produce a timing record; cancelled or
unpublished captures have no source-ID timing log.

Validation: run bash local_prefetch_check.sh on a Linux host with Qt5. It tests
parser policy, lead 0/30/50/120 cadence boundaries including short/urgent intervals
and bypass, acquisition-delay clocks, lifetime, model revision, and actual wrapped
PangoDev protocol with timing OFF/ON and verification. Fixed RAW/RGB DMA count
assertions remain. Protocol timestamps use the production monotonicMs().
The full vision_pipeline_selftest requires OpenCV; if the host lacks it, this is
explicitly pending together with the ARM build/full pipeline run. Host syscall
fixtures cannot establish board behavior or performance. No board run is authorized
by this candidate's creation.

Observed local validation: local_prefetch_check.sh passed, including default,
valid and invalid environment subprocesses, warning-once and RGB-OFF silence,
protocol timing OFF/ON, classes syntax and native verification fixtures.
local_fair_negative_check.py and local_short_hold_negative_check.py passed (old
lock-held polling and pre-release copy ordering are rejected). The full pipeline
build was attempted in WSL and failed because opencv4.pc and OpenCV headers are
absent. ARM compilation and full pipeline tests remain pending for the parent.
