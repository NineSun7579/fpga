# Six-camera thumbnail parity

Build only from the repository root on Windows:

```powershell
python fpga_zero_copy_delivery/build_thumbnail_six_parity.py
```

This uses `board_ssh`, stages the required headers from `build_host.py`, verifies
uploaded bytes, and compiles with C++17, `-O2 -Wall -Wextra -Werror -lrknnrt
-pthread`. It also compiles the current C5 thumbnail, pointer, and shared-input
callers without executing them. It does not program the FPGA, open a device,
stop the viewer, or run any parity/benchmark binary. The executable is:

`/userdata/linaro/fpga-zero-copy-host/thumbnail_six_parity`

The parent session owns hardware preparation and execution. Once the parent has
loaded the matching integrated_six contract and arranged exclusive device
ownership, run as root on the board:

```sh
sudo /userdata/linaro/fpga-zero-copy-host/thumbnail_six_parity 10 > /userdata/linaro/thumbnail_six_parity.jsonl 2> /userdata/linaro/thumbnail_six_parity.stderr
```

The argument is frames **per camera per output bank**, minimum 10, default 10.
Success requires exit 0, 120 per-frame JSON records at the default count, and a
final summary with `frames_passed: 120` and `pass: true`. Each pair must contain
10 successful frames; sequences must advance for each camera across both output
banks. Camera indices are 0..5 (physical C1..C6). Output banks are 0..1; RAW
source banks are chosen by published capture metadata and reported separately.

Each frame requires capabilities 7, support bitmap 0x3f, exact selector/source
bank/destination/size readbacks, an advancing generation, healthy frozen
admission value 4, and equality of +e0 and the RAW commit tag. The tool compares
both bytes of every thumbnail RGB565 pixel to RAW coordinates (2*x, 2*y), then
rereads the entire frozen RAW payload to check stability before release.

Sequence zero passes only with proven publication and matching frozen RAW tag
(uint32 wrap). An unpublished admission never produces a passing frame: after
three seconds, only diagnostics 2 and held/unfrozen/idle/incomplete status 1
permit safe release followed by failure. Other uncertain DMA/lease failures
print `QUARANTINE pid=...` and SIGSTOP the process, retaining mappings and device
ownership for parent-controlled hardware recovery. Do not blindly terminate a
quarantined process before quiescing hardware. Pixel comparison/freshness failures
release safely if the identity and idle checks still pass. Successful release
restores C5, output bank0, RGB mode and its original destination.

Build evidence is in `thumbnail_six_parity_build.log`,
`thumbnail_six_parity_compat_build.log`, and
`thumbnail_six_parity_build_manifest.json`. The manifest records executable,
uploaded-source, current RTL and viewer-contract SHA256 values. Hardware parity
remains unvalidated until the parent runs the tool.
