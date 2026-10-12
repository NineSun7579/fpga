# Capture lease verification report

The isolated candidate passes all nine ModelSim suites using **official Pango
DRM/FIFO primitives**, unmodified production camera `w_en/w/w_ctrl`, and the
original `axi_dma_write` with WAIT_FOR_DATA=1 and 16-beat bursts. Production and
candidate RTL compile as Verilog-2001; only the testbench uses SystemVerilog.
No PDS/synthesis, SSH, board work, NPU tests, production registration, DDR
adapter or host adapter changes were performed.

Run: `python run_tests.py` from this directory. Exact commands, source hashes,
trace hashes and all oracle counts are in `artifacts/results.json`.

| Suite | Sensor frames | Certified images | W words | AW / B | DMA errors | Public state snapshots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small_dual, 128x128 RGB565 | 26 | 12 | 26,685 | 1,681 / 1,680 | 4 | 68 |
| full_dual, 640x480 RGB565 | 26 | 12 | 499,261 | 31,217 / 31,216 | 4 | 68 |
| small_coop_only, 128x128 RGB565 | 3 | 2 | 4,098 | 258 / 258 | 0 | 9 |
| invalid overlap | 1 | 0 | 0 | 0 / 0 | 0 | 1 |
| invalid 256 MiB bounds | 1 | 0 | 0 | 0 / 0 | 0 | 1 |
| invalid base alignment | 1 | 0 | 0 | 0 / 0 | 0 | 1 |
| invalid odd CAM_DATA_LEN | 1 | 0 | 0 | 0 / 0 | 0 | 1 |
| invalid DATA_WIDTH=24 | 1 | 0 | 0 | 0 / 0 | 0 | 1 |
| invalid geometry/length | 1 | 0 | 0 | 0 / 0 | 0 | 1 |

Totals: **530,044 strict 128-bit W comparisons**, comprising 529,956 pixel
words, 28 tag words and 60 zero-strobe abort words. Entire certified DDR images
include **489,498 words / 7,831,968 bytes**, with all 128 tag bits checked.
All 26 images remained frozen through lease ownership and were explicitly
released. The oracle checked 151 public state snapshots, 50 descriptor claims,
89 release requests (50 accepted, 39 rejected), and the TB completed 210 explicit
checks. The two AW/B count differences are the deliberately accepted AWs
cancelled by coordinated DMA/memory-model resets, one in each dual suite.

Both dual suites exercise banks held by both consumers, indefinite descriptor
backpressure, whole-frame drops without writes, cooperative-first and host-first
release, premature/wrong-camera/wrong-bank/wrong-sequence/wrong-generation/
wrong-token/duplicate/stale release rejection, legacy ACK after bank reuse,
natural overflow of the official FIFOs, short source with advertised AW stalled,
source errors held until actual B retirement, early SOF during retirement,
payload/tag B errors, successful tag B held through another full sensor frame,
recovery, accepted-AW reset, fresh-generation arm, old token rejection and
sequence-wrap disarm/rearm. Simultaneous invalid releases increment rejection
by two; simultaneous exact releases free a bank atomically. Sequence rollover
is accelerated by TB-only deposits into near-limit counters.

Python derives ownership from admitted sensor-frame events, completed AXI
obligations and consumer transactions, then checks public state snapshots.
It does not inspect DUT storage. Full published DDR images are compared to an
independent RGB565 golden, and AW to any frozen lease is forbidden. Verilog
checks AW/W and both descriptor stability under stalls, X/Z on every W bit,
strict final strobe/last, no flush during live DMA obligations and no publication
before successful tag B.

The initial 22-file hashes and expanded **42-file production scope** both match
before/after. The expanded scope contains all 18 active `source/ov5640/*.v`
files recursively, all four AXI DMA files, all 13 generated camera FIFO IP
Verilog files, top.v, and six official vendor primitive models. Candidate module
names are unique in a byte-regex scan across production source and active
migration candidates, excluding generated artifacts.

| Current file | SHA-256 |
| --- | --- |
| fpga_v8_capture_lease.v | `04e908f9be9aa10ebf4eb19604d747c7dd7d2e48bd8aa52dbe069fc6e246865c` |
| fpga_v8_capture_ov5640_ddr.v | `a69152c43fd67ae074c4801d778e2b0afab82b8af4c6695267a89e60d71b42d8` |
| production ov5640_ddr_w.v | `f3725466c6eb50ca1eb141bee017a415060f50727c9bf16d520f8b16407e6524` |
| production ov5640_ddr_w_ctrl.v | `f90858a84018960102a57dc63578f82d53188bc9b0f811cc2c5e7150cf0b6b44` |
| production ov5640_ddr_w_en.v | `a2f1c3f48d2e0d46b44ea98ab5394e6a486ed193c1c71716a1959fb0ad1160ce` |
| production axi_dma_write.v | `b897bdcc7b28c1f91e9dfa7303a81ada24639de80bcb2248c9e3fcf9f234edc0` |

Integration still must bind the common capture/core clock or supply a correct
descriptor/release CDC bridge; coordinate reset across capture, DMA, cooperative
core and DDR obligations; persistently allocate fresh nonzero generations;
implement explicit host RAW claim, immutable descriptor reads and exact release
after all reads drain; reserve the fixed source ranges against other writers;
and connect the actual cam5 unfiltered SFP stream using CAM_ID=4. The manager
cannot remember epoch history across reset/power loss and cannot detect reuse
of older non-current generations. HOST_REQUIRED=0 is allowed only for an
isolated cooperative-only path with no other readers. Full cooperative-core/
DDR-fabric/host integration and synthesis remain parent-session work.
