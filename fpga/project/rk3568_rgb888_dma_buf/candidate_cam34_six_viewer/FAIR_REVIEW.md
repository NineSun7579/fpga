# Fair concurrent viewer review

This directory is a separate copy of `candidate_concurrent_viewer`, excluding
`local_build` and Python caches. Existing viewer and driver sources are unchanged.
No board calls, deployment, FPGA edits, driver edits, or commits were made.
`fair_original_sha256.json` records the copied source's hashes.

## Evidence and limits of the diagnosis

`concurrent_performance_runtime.log` lines 47–52 show camera 2 delivered 10.38 fps,
tag advancement 10.58/s, successful read 12.519 ms, frame DMA 1.501 ms, copy
7.374 ms, and zero unstable frames. Lines 99–104 show 6.33 delivered and 6.33 tag
advancement with successful read 14.824 ms. Other cameras remain near their sensor
rates. A mutex bottleneck that simply skips published frames would normally leave
tag advancement high; these windows instead suggest loss of FPGA publications.
The successful-read timing excludes empty-tag attempts and therefore does not
prove the absence of scheduling stalls. No hardware reject counters are recorded
here, so this is evidence for a mechanism, not proof of camera 2's root cause.

Byte-level inspection of the copied FPGA sources found:

- `delivery/delivery_regs.v:65` makes the capture hold one-hot for lease_camera;
  `top.v:1353` connects cam1 to bit 0 and `top.v:1570` cam2 to bit 1. The logged
  camera=1 converter lease does not directly assert cam2's hold.
- `axi_crossbar/ddr_w_arb.v:199–215` implements round-robin camera write grants;
  the inspected design is not a fixed-priority camera-write arbiter.
- `ov5640/ov5640_ddr/ov5640_ddr.v:82–86,136,153` rejects incomplete/overflow frames
  and flushes failed captures. `ov5640_ddr_w_ctrl.v:57–58,240–249` increments frame
  tags for good frames. Extra PCI/FPGA converter read load can plausibly reduce
  publications through capture backpressure/rejection, but live diagnostic
  evidence is needed to establish that specifically for camera 2.

Confirmed scheduling defects in the concurrent viewer are an unfair shared
QMutex, converter polling sleeping under that mutex, copying selected RAW pixels
under the mutex, and END competing with the whole queue of ordinary transfers.

## Implemented mitigation

`fair_dma.h` supplies FIFO ordinary admission and priority consumer retirement.
END cannot interrupt an active transport section, but enters before queued ordinary
sections. A camera read section includes two tag reads and a frame DMA; FPGA
validation also groups register operations between yield points. All PCI submission
paths share this gate, so the kernel's existing
transfer-completion mutex still protects each DMA; no new driver is required.
END remains behind the current section and DMA completion, including any existing timeout.
This is bounded ordering, not a real-time scheduling guarantee.

`cameraReadFpga` releases/reacquires transport around poll sleeps and the owned
RAW-slot CPU copy, and releases transport before constructing the queued Input
and optional CPU golden image. Scratch reads/copies and TX writes remain locked.
Ordinary camera copies already occur outside transport. One worker per camera
still owns its RX slot until its copy completes.

The converter is never made available by these unlocks: the unchanged sole
Admission remains occupied from claim through queued input, BEGIN, NPU consumer,
and verified END/cancellation. The RGB DDR destination cannot be reused before
retirement. FPGA camera hold remains asserted during the selected RAW copy and
conversion; release/default restoration still precedes deferred RGB F2H/BEGIN.
BEGIN reserves the full 1,228,800-byte input range even for a 921,600-byte crop.
All six RAW slots and scratch remain below 4 MiB and disjoint from that lease.
Model selection, generation/tag identity, geometry, RKNN imports, native output
comparison, and decoders are unchanged.

## Local validation

Run `bash local_fair_check.sh` under Linux/WSL with g++ and Qt5 development files.
Generated binaries and logs are confined to this candidate's `local_build`.

- Real threaded gate test: six queued callers enter in FIFO order; END enters
  first after active DMA unlock; 6,000 camera iterations and 1,000 retirements
  preserve exclusion and progress, including unlock/relock.
- Actual extracted PangoDev with syscall fixtures: flag-off, flag-on, and golden
  verification pass; all six cameras at heights 480 and 640 preserve exact input
  bytes, tags, deferred BEGIN and full reserved RX bytes while disjoint traffic
  runs during the lease. Allocation failure, cleanup rejection, cancelled input,
  and unpublished-camera handling still pass.
- Added poll test holds simulated FPGA drain pending until a waiting metadata
  caller receives transport service. All 12 actual acquisition paths pass. A
  transport lock held across the poll sleep cannot satisfy this test.
- `python3 local_fair_negative_check.py` restores the old lock-held poll only in
  a generated test unit. The fixture correctly rejects it at the FPGA deadline.
- Classes-only Qt syntax check and actual extracted native output helper pass
  (raw4/raw6/raw10 byte capture, last-byte corruption, unsupported sizes).
- `local_build/source_preservation.json` verifies all original concurrent viewer
  hashes remain intact, 47 copied files remain identical, and all main.cpp bytes
  after PangoDev plus the geometry/model/camera-base region before it are identical.

Host fixtures do not establish DMA coherency, IRQ ordering, board native parity,
ARM linking, frame-rate recovery, or CPU improvement. Parent must build this
candidate with the existing concurrent driver, repeat at least 16 exact live
input/native-output pairs, and compare all-six rates and CPU with originals.
If cam2 tag advancement remains low, sample its read-only input-pixel,
overflow/short, fault snapshot and successful-frame counters under load; changing
driver lease ownership is not supported by the present evidence.
