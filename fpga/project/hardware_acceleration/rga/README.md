# Private RK3568 RGA fixture probe

This directory is the delegated RGA work only. Local preparation never connects
to the board. The native probe uses librga and, in its default fd mode, allocates
private `/dev/dma_heap/system` buffers; it never opens the FPGA/PCIe DMA device,
DRM, RKNN, or a camera. The parent must defer the hardware runner until its
diagnostic build finishes and it declares the board slot available. No viewer
restart, driver reconfiguration, FPGA change, or integration is included.

## Input contract and acceptance

Frozen FPGA baseline is `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`.
The contract is a complete 640x480 little-endian RGB565 image, red in bits 15:11,
green in bits 10:5 and blue in bits 4:0. CPU output is RGB byte order with exact
5/6-bit replication: `r8=(r5<<3)|(r5>>2)`, `g8=(g6<<2)|(g6>>4)`, likewise blue.
The model input remains 640x640 RGB888, the entire image at `(0,80)`, and 114 in
all channels in the top/bottom 80 rows. No resize, crop, RGB swap, model or FPGA
change is accepted. RGB888 stride is 1920 bytes and width 640 is aligned to 16.

The six fixtures are copied from existing
`log/six_fps40_board_20261003_105717/cam[1-6].rgb565` and are individually hashed.
They are historical examples, **not evidence of a current e3da frame capture**.
The parent can regenerate the local manifest from another complete six-frame
log directory with `prepare_local.py --fixture-dir ...` and a new `--output`.

`reference.hpp` implements the reference, exhaustive gate, comparisons and
corrections. `reference_selftest.cpp` checks all 65536 colors, channel swaps,
position-dependent conversion, endian/channel landmarks, padding and scalar
tails. `prepare_local.py` independently checks the C++ results with Python and
records SHA256 for raw, full RGB and model RGB. WSL results are CPU evidence only.

`native_probe.cpp` tests both `RK_FORMAT_RGB_565` and `RK_FORMAT_BGR_565` on the
same 640x480 tiled gradient (all words, repeated at several positions), records
per-channel mismatch counts/max differences, and selects only an exact or
provably repairable channel-preserving interpretation. `imcheck` must pass
before every operation type. It separately validates:

- Full 640x480 conversion using `imcvtcolor`.
- One synchronous `improcess` conversion into destination `(0,80,640,480)`.
- `imcvtcolor` plus synchronous RGB888 `improcess` copy into that same ROI.

The 10-argument `improcess` signature matches the local legacy bridge call form.
The parent runner compiles against a private copy of the **actual board SDK
headers** and links the installed library; unsupported calls fail visibly. The
old bridge's BGR565 assumption and 1280x720 resize are not reused.

Direct output is reported even when it differs, but then has
`eligible_unchanged_input=false`. Exact left-shift expansion is corrected by a
NEON OR pass. A more general channel LUT is allowed only when all colors prove
it is deterministic, injective and within 7/3/7 quantization bounds; AArch64
uses byte-table NEON lookup with an unseen-value gate. Correction never touches
padding. Corrected gradient and every fixture frame must match the CPU bytes;
the runner additionally checks dumped output SHA256 against the independent
oracle. Unknown conversion, swapped channels or changed padding fails the run.

The default fd path uses DMA-heap allocation and mmap from the old viewer's
allocation layout, with `DMA_BUF_IOCTL_SYNC START/END` around **every** CPU
write/read/read-write access. Imports persist across frames. RGA calls are
synchronous; CPU access starts after completion. `--memory virtual` separately
tests `importbuffer_virtualaddr`, and `--memory both` records both paths. A
failed fd import or driver operation is retained as failure evidence and is
never silently replaced by a software conversion.
An unsupported ROI variant is explicitly recorded as `path_rejected`; the other
variant is still tested. Success requires full-frame conversion and at least
one complete model-letterbox variant, with all six fixtures passing. The receipt
lists the supported and rejected variants separately.

## Local commands (safe while the board is busy)

From this directory in WSL:

```bash
mkdir -p local_evidence
g++ -O3 -std=gnu++14 -Wall -Wextra reference_selftest.cpp -o local_evidence/reference_selftest
python3 prepare_local.py --selftest local_evidence/reference_selftest --bundle
python3 check_local.py --fetch-upstream-headers
```

Optional `python3 verify_aarch64.py` privately downloads/unpacks tools inside
`local_evidence/` and executes the CPU selftest under QEMU AArch64, including
the NEON branches. It installs no packages and executes no RGA operation. For
a later source check, `--reuse-tools` avoids downloading/unpacking again.

The public SDK download is an optional compile-only syntax check, pinned and
hashed in `local_evidence/local_checks.json`; it does not establish board SDK
compatibility. Once the parent has SFTP-captured the current headers under a
local root containing `rga/im2d.h`, it can run
`python3 check_local.py --headers-root /path/to/captured/include` without board
access. Do not substitute public headers in the hardware runner.

## Parent's future board command

SFTP `local_evidence/rga_board_bundle.tar.gz` to a new private board directory,
verify its SHA256 against `local_evidence/bundle_sha256.json`, and extract it
there. This package contains source and the six raw fixture files, **no native
hardware executable and no replacement library**. When the parent declares
the board slot available, run on the board:

```bash
python3 run_board.py --board-free --fixtures fixtures --headers-root /usr/include --frames 500 --warmup 30 --memory fd --output results_fd
```

If the installed SDK root differs, pass the actual root containing
`rga/im2d.h`. The runner copies/hashes all SDK headers, builds a private native
executable and CPU selftest, verifies the target CPU hashes, records `ldd` and
hashes actual dependencies, then invokes the RGA probe. It records the actual
`querystring`/`imquerystring` `RGA_ALL` string and available driver version
files/kernel messages; absent driver version is unknown, not inferred from the
Mali G52 GPU. No system governor, module or display setting is changed. Optional
`--cpu-core N` pins only the runner and its children and records affinity.

Use a **new** output directory for a second `--memory virtual` run, or use
`--memory both --output results_both` to collect both. No SSH/SFTP client is
embedded in the runner. Without `--board-free` it exits before executing a board
command or opening a device.

## Timing and integration limits

Each fixture/path/backend gets 30 warmup and 500 measured frames by default.
CPU baselines include current-style convert-plus-letterbox-copy and fused
conversion. Direct and corrected RGA use the same pinned raw bytes. Receipts
include monotonic wall and thread CPU mean/p50/p95/p99 and separate source
copy+sync, synchronous RGA call, destination sync and CPU correction costs.
Source upload is included. Padding is initialized once for both CPU and RGA,
matching the persistent baseline. Per-frame validation/snapshot/hash work and
allocation/import are outside the measured intervals and this is stated in
the output. Extra validation can affect cache state; CPU governor/frequency and
affinity are recorded, but no system frequency control is imposed. These are
preprocessing measurements, not completed-inference FPS or NPU detection parity.

Output `fixtureN_model_direct_roi_corrected.rgb888` and
`fixtureN_model_two_stage_roi_corrected.rgb888` are complete 1,228,800-byte model
inputs for the parent's separate RKNN parity probe. Integrate only after actual
board SDK/import/driver support, exact hashes, detection parity with the same
model, and matched completed-inference measurements pass. This worker leaves
the model input contract and active viewer untouched.
