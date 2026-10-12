# Isolated six-camera display candidate

Copied from `thumbnail_viewer_src`; only this new directory is edited. The
current C5 viewer, board/PDS artifacts, driver, production source and integrated
RTL are untouched by this subtask. Target: `detview_six_camera_candidate`.
Parent owns the complete RK3568 build and board validation; this candidate has
been reconciled with integrated_six RTL but is not deployed or measured.

## Build and selection

Use a fresh directory with the parent's normal RK3568 Qt5/OpenCV/RKNN/RGA
toolchain; regenerate moc from sources rather than using copied generated files:

```sh
mkdir six-viewer-build && cd six-viewer-build
qmake ../six_camera_viewer_src/detview.pro
make -j4
QT_QPA_PLATFORM=offscreen ./detview_six_camera_candidate --thumbnail-selftest
QT_QPA_PLATFORM=offscreen ./detview_six_camera_candidate --display-latency-selftest
QT_QPA_PLATFORM=offscreen ./detview_six_camera_candidate --vision-selftest
```

`DETVIEW_FPGA_SIX_THUMBNAIL=1` opts in. Default is RAW display. The older C5
environment variable is deliberately ignored in this separate candidate.
Startup and status messages identify whether six-thumbnail mode is enabled.
There is no new UI control or change to calibrated policies.

All six capture workers stay active in grid, single-camera and HDMI views;
explicit application pause still pauses capture. In grid mode, all six cameras
can display 320x240 RGB565 thumbnails (153600 bytes each). The selected YOLO
camera separately acquires full 640x480 RAW (614400 bytes) for RK3568 analytics.
Each worker owns a separate RAW buffer and thumbnail buffer, with independent
RAW and display tag cursors. Global vision frame IDs and per-camera display
publication counters remain separate. The bounded latest/display mailboxes
replace older owned buffers; no frame queue is added.

Single-camera view preserves full-resolution display for the selected camera.
Stereo cameras also use RAW for display and analytics. HDMI disables thumbnail
acquisition for all six; its analytics image construction and calibrated pairing
policies are unchanged. A RAW transaction is reused for display when exempt;
there is no second thumbnail acquisition for that camera. Generation or mode
changes discard mismatched display reads and reset cursors before the next read.
No thumbnail is converted/submitted to vision or calibration. RAW conversion,
vision packet construction and the complete inference thread are byte-identical
to the installed baseline; guards and acquisition scheduling change around them.

## DLV2 contract checked against integrated_six RTL

All constants/predicates live in `thumbnail_delivery.h`. Base `0x40020000`, DLV2
signature `0x444c5632`; register definitions were checked by byte-level reading of
`integrated_six/source/delivery/delivery_regs.v` (RTL may contain GBK comments).

| Offset | Candidate interpretation |
| --- | --- |
| +a0 | require bits 0,1,2 (mask 7); bit2 has value 4 |
| +b0 | mode 0 RGB888 default, mode 1 RGB565 thumbnail |
| +c0 | camera 0..5, default 4 (C5) |
| +d0 | output bank 0 or 1, default 0 |
| +e0 | frozen source sequence, equal to RAW source commit tag |
| +f0 | supported bitmap exactly 0x3f |
| +100/+110 | selected camera's RAW source banks; bank0 = `0x00800000 + camera*0x00400000`, bank1 = bank0 + `0x00200000` |
| +120 | bit0 drain pending, bit1 unpublished, bit2 frozen, bit3 flush, bit4 invalid RAW bank configuration; healthy frozen value 4, healthy idle 0 |

Selector writes are 16-byte DMA register writes with a full 32-bit value, while
idle/unheld only. On the existing bridge this must yield all four byte strobes.
Verify strobes against the final driver/RTL pair. The restored C5/bank0 RGB
destination is `0x0a000000`; it is serialized on the same mutex. RTL allocates
other RGB camera/bank combinations at `0x0b000000 + camera*0x00400000 +
bank*0x00200000`; this thumbnail reader restores C5/bank0 for the RGB provider.
Thumbnail destinations:

| Camera | Bank 0 | Bank 1 |
| --- | --- | --- |
| C1 | 0x0a280000 | 0x0a2c0000 |
| C2 | 0x0a300000 | 0x0a340000 |
| C3 | 0x0a380000 | 0x0a3c0000 |
| C4 | 0x0a400000 | 0x0a440000 |
| C5 | 0x0a200000 | 0x0a240000 |
| C6 | 0x0a480000 | 0x0a4c0000 |

Workers alternate their output banks only after successful completed reads.
No rendering DMA ownership is added: each read copies to an owned QByteArray
before releasing the mutex/lease, and GL uploads from that owned buffer.
The native DDR burst-slot payload gather must match deployed RAW camera reads;
parent must verify actual payload bytes and physical-gap handling on hardware.

The reader validates default RGB ownership before commands, selects camera/bank/
mode idle, checks source banks, destination and size, acquires hold, validates frozen
epoch/source/sequence/freeze, submits once and waits for completed with busy
clear and jobs incremented. It rechecks size before pixel DMA/copy and lease
identity afterwards. Complete verified reads release then restore default mode,
camera 4 and output bank 0. It never switches a held selector.

RTL freezes only a published RAW bank after writer/DMA retirement and 32 quiet
cycles. RAW source-bank selection is independent of the selected output bank.
The reader waits up to two seconds for admission. At the deadline, status 1
(held, unfrozen, idle, incomplete) and diagnostics 2 (unpublished only) permit
release of the unsubmitted hold and default restoration, returning no frame.
Pending retirement, flush, invalid banks or other freeze timeouts quarantine.
A published sequence of zero is delivered normally, including after sequence
wrap; zero is not an empty-frame marker. No-frame waits hold the shared mutex
for the full admission deadline; startup/unconnected-camera impact needs measurement.

All IO errors/timeouts, wrong contracts, malformed completion or changed leases
SIGSTOP the process while retaining fd/mappings/mutex and any lease. No automatic
release, mode escape, close/reopen or supervisor restart occurs. Quiesce/reset
fabric and DMA before terminating/restarting a quarantined process. SIGCONT
re-stops. No unbounded frame queue is present, but hardware lease waits can
serialize other workers for up to the explicit two-second deadline.

## RX layout for future same-process zero-copy input

This layout is deliberate preparation for the parent's zero-copy integration;
there is no RKNN memory binding, preprocess provider or PZ token management in
this subtask. `camera_dma.h` and its existing tests retain the baseline defaults;
the new application uses the separate `six_dma_layout.h` mapping.

| RX range | Owner/use |
| --- | --- |
| 0..614416 | reusable RAW frame + commit tag scratch; thumbnail uses its first 153600 bytes |
| 1048576..1052672 | reusable MMIO/tag/chunk scratch (1 MiB offset) |
| 2097152..3325952 | reserved shared RKNN RGB888 input, 1228800 bytes |

Every main.cpp H2F/F2H operation goes through a central range check requiring the
whole range below 2 MiB, including generic ddrRead and MMIO. Six cameras no longer
use per-camera mmap offsets. Their logical camera/bank/tag selection remains
independent. RAW metadata, DMA and exact owned copy occur under the DMA mutex;
only then can another camera reuse the scratch. The RKNN input reservation is
never overwritten by these operations, whether or not a future PZ_BEGIN token
is held. Driver enforcement and shared input token lifecycle remain parent work.

`PangoDev::withSharedInputSession(callback)` exposes borrowed `{fd, rx, rxBytes,
inputOffset, inputBytes}` under the existing mutex. The callback must not close
the fd, create another provider, call locking PangoDev methods, or retain scratch
pointers. It may retain the shared input mapping only through a separately
defined parent token/lifetime protocol. Callback exceptions quarantine. The
parent must make every future preprocess submission obey the same mutex and
explicitly handle uncertain DMA without releasing ownership. No second fd is
opened by this candidate.

## Rendering, metrics and validation

Per-camera dimensions and per-texture-ring allocation dimensions are inherited
from the C5 candidate. GL gets true 320x240 RGB565; normalized texture coordinates
scale it to the tile without CPU upsample. RAW/thumbnail transitions reallocate
only the selected texture slot when necessary. Upload byte counters reflect the
actual size. `DETVIEW_PERF=1` (default) and `DETVIEW_LATENCY_TRACE=1` report software
DMA-return-to-upload/draw intervals and frame dimensions. These exclude FPGA
wait/process time; use capture read_ms and full end-to-end measurements too.
The optional diagnostic PNG leaves thumbnail tiles blank instead of upsampling.
There is no CPU, throughput, optical latency or acceleration claim.

Host transport tests cover every camera/bank, unpublished release, wrapped zero
sequence delivery, delayed publication during admission, every healthy-path MMIO failure,
mode/capability/bank/freeze/epoch/sequence mismatches, deadlines, DMA failures,
separate RAW/display cursors and sequence wrap. A real copy-routine test preserves
RAW byte patterns through all six scratch reuses while checking the RKNN slot's
canary. Qt host extraction tests the actual owned late-latch methods. See
`local_test_results.txt`, `source_preservation.json` and `viewer_changes.diff`.
`verify_source_preservation.py` also statically checks all main DMA routes use
the new scratch layout and only one device open exists.

Parent checks still required: actual full viewer build/selftests, hardware
admission timing and bridge strobes, native-layout payload parity, same-fd
PZ token nonoverlap behavior, generation switching, full selected view, HDMI,
calibration, and existing stereo skew/pairing acceptance under per-camera holds.
RAW stereo cameras are exempt from thumbnail holds, but other-camera jobs still
serialize their host acquisition and may change skew/rate; measure rather than
altering calibrated thresholds. The parent owns integrated_six and all board/PDS
operations. None were performed by this subagent.
