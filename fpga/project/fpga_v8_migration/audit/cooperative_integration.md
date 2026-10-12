# Cooperative raw preprocessing integration audit

Read-only audit, 2026-10-04. Root/project AGENTS and RTL were read through Python `read_bytes()` and ASCII decoding; no RTL, production host files, PDS, IP, board files, processes, NPU execution or JTAG were changed. Only this report was written. References below are project-relative. These are **current source routes**, not a verified source-to-loaded-bitstream binding.

**Recommendation:** candidate DDR reader on **S02 / `npu_s0`**, output writer through a **new owner in `ddr_w_arb`**, explicit completed-input leases, and independent NHWC output double buffering. Preserve S05/KF. There is no functioning spare crossbar DDR write route today. Integration is conditional on buffer ownership and recovery of the running viewer's complete build inputs.

## Verified routes

| Route | Current ownership / evidence | Candidate use |
|---|---|---|
| S00 AR/R | `pcie_fifo` host F2H DMA; `top.v:2680`; PCIe TX FIFO accepts only RID 0 (`pcie_fifo.v:719,747`) | Host reads completed NHWC through existing F2H command/address route; do not replace or share its signals |
| S01 | Camera crossbar port retired/tied (`top.v:2701`); DDR read mask excludes it | Not a ready DDR master |
| S02 AR/R | `npu_s0`, ARVALID=0/RREADY=1 (`top.v:2593,2769`); M00 read enabled | Preferred candidate input reader; remove ties only in an isolated candidate top, drive complete AR/R interface |
| S03 AR/R | `npu_s1`, tied idle (`top.v:2596,2812`) | Spare alternative reader |
| S04 AR/R | `npu_s2`, tied idle (`top.v:2599,2856`) | Spare alternative reader; cam2 **writes** no longer use this crossbar port |
| S05 AR/R | `npu_s3` connected to cam1 KF (`top.v:1348,2899`) | Reserved, even with current `KF_EN=0`, `KF_RD_EN=0` (`top.v:1278`) |
| S06 AR/R | `npu_s4`, tied idle (`top.v:2603,2942`) | Spare, unnecessary for initial candidate |
| S02 AW/W/B | Former `npu_out`, tied idle (`top.v:2590,2745`) | Wires available, **no DDR destination** |
| S03 AW/W/B | `prep2` writer instantiated, command/data tied idle (`top.v:2359,2387,2789`) | Also **no DDR destination**; stale “stays active” comment is misleading |
| Physical DDR writes | `ddr_w_arb` m0..m5 = cam1..cam6 (`top.v:432-506`), directly feed DDR glue (`top.v:509`) | Extend to seventh owner m6 for NHWC writer; all six present owners are occupied |

`M00_CONNECT_READ=7'b1111101`, `M00_CONNECT_WRITE=0` (`top.v:2630-2632`). Crossbar M00 AWREADY/WREADY are hard zero (`top.v:2978,2984`). Re-enabling that historical write path is not a wiring-only integration: the custom arbiter was installed for a documented crossbar W ownership failure. Keep the established staged-AW/FIFO/B bridge and round-robin ownership through accepted B (`ddr_w_arb.v:298-313`).

`axi_dma_read.v` is an available interface pattern, **not an instantiated spare DMA channel in current top**. Its command length is bytes; it splits 4-KiB boundaries and supplies 128-bit words, but `len` is not reset and AR generation is not gated by `trans` (`axi_dma_read.v:82-89,156`), and RRESP is swallowed. Candidate reader must reset all transaction state, reject zero/unaligned requests, validate responses/beat count and drain accepted reads on cancellation. Unpack each accepted word into eight little-address-order RGB565 pixels; assert source LAST only on pixel 307199, excluding the frame tag/dummy.

For candidate output use the existing `axi_dma_write` contract: `cmd_len=1228800`, burst <=16 beats, real FIFO beat credits and `WAIT_FOR_DATA=1` (`axi_dma_write.v:157-166`). Add sufficient buffering so a granted write owner never waits for future pixels. Its `data_in_last` is an **output success pulse after final B**, not incoming stream TLAST (`axi_dma_write.v:322`); observe `data_in_abort`, count packed bytes/LAST, and publish no partial output. The full image is 76800 full 16-byte beats; byte strobes are carried through the DDR FIFO (`top.v:241,246`).

## Formats and current frame map

OV5640 configuration writes `4300=61`, `501f=01` (`ov5640_i2c_rgb565_cfg.v:178-179`). `cmos_capture.v:88` assembles the sensor's two bytes into a 16-bit pixel. Defaults and cam2..4 overrides are **640x480, 16-bit RGB565**, 614400 bytes = 38400 AXI beats (`ov5640_top.v:18-27`; `top.v:1482,1551,1651`). Host conversion replicates bits: R/B `(v5<<3)|(v5>>2)`, G `(v6<<2)|(v6>>4)` (`motion_scheduling/host/src/main.cpp:582-591`).

**RAW naming caveat:** every FMC `ov5640_top` instance unconditionally instantiates `cam_fir3`, followed by optional KF, then DDR (`ov5640_top.v:386-396,408-462,515`). Thus current cam1..4 DDR contains FIR-filtered RGB565, with KF bypassed; comments calling cam2..4 “raw passthrough” do not remove FIR. `top.v:2354` taps the already processed DDR stream. If RAW means literally before FIR/KF, provide a separately completed RAW bank from the pre-filter stream, or begin with cam5/6, whose SFP path writes 16-bit pixels directly without FIR/KF (`top.v:1761-1817,1863-1898`). SFP sender RGB565 encoding still requires confirmation; local receiver width alone does not prove color ordering.

| Camera | Bank 0 | Bank 1 | Completion tag |
|---|---|---|---|
| 1 | `0x00800000` | `0x00A00000` | each base + `0x96000`, 16 bytes |
| 2 | `0x00C00000` | `0x00E00000` | same |
| 3 | `0x01000000` | `0x01200000` | same |
| 4 | `0x01400000` | `0x01600000` | same |
| 5 | `0x01800000` | `0x01A00000` | same |
| 6 | `0x01C00000` | `0x01E00000` | same |

Addresses verified in `ov5640_top.v:26-27` and `top.v:1484,1555,1655,1798,1879`; host map agrees (`motion_scheduling/host/src/main.cpp:80-82`). Banks are a DDR ping-pong pair, separate from host RX slots and GPU texture rings. Cam1..4 base registers are writable, so compile-time defaults do not certify current runtime allocations.

## Ownership and proposed output allocation

Frame payload completion advances to a separate tag transaction. Only `dma_done` in `WAIT_TAG_DONE` publishes the frame and flips `w_ping` (`ov5640_ddr_w_ctrl.v:56-58,165,235-248,260`). Start preprocessing from that completed descriptor, not VSYNC, a frame command, stream LAST, or tag W acceptance.

**Existing ACK is not a lease.** `ov5640_ddr_w_en.v:9` declares `frame_pending` but never uses it; admission only tests enabled/idle/not-stopped (`:44,53,94`). The controller picks `w_ping` without checking pending ownership (`ov5640_ddr_w_ctrl.v:211`), and clears the old request when starting that bank again even without host ACK (`:269-273`). Cam5/6 ACK is permanently zero. The inspected retained host polls two tags, transfers frame+tag and checks equality, then copies into owned CPU storage (`main.cpp:368-403`); equality cannot exclude a partial overwrite while the old tag remains unchanged.

Candidate requirements:

1. Claim `(camera, bank, source_sequence, reset_generation)` atomically at publish/descriptor acceptance; prevent capture from selecting a claimed bank. Drop whole incoming frames at SOF when no bank is free. Multiple readers (preprocessing, display DMA, and any KF history use) need separate references. If strict pre-filter RAW preservation needs another capture writer, budget an eighth arbiter owner rather than borrowing a camera owner.
2. Release the preprocessing RAW reference only after the final source pixel has entered owned internal storage and every accepted read has retired. Host ACK must retire only the host's own completed DMA/copy reference. A tag match or host early ACK must never clear the preprocessing reference. If these ownership changes are absent, do not call the current ring stable.
3. Output states: FREE -> WRITING -> READY -> HOST_READING -> FREE. Reserve a free output before input acquisition; publish READY only after the final successful B and committed sequence/length/error metadata. ACK must match output bank + sequence + generation and follow completed host DMA into owned storage. Keep host RX memory alive through `rknn_inputs_set`/run as required; never let another DMA overwrite a referenced pointer. No free output means defer/drop the request, never overwrite READY/HOST_READING.
4. Cancellation/errors stop new requests, drain irrevocable AR/AW/W/B, invalidate output and then release references. A local timeout/reset must not abandon an active DDR owner; coordinate global AXI reset or drain first.

Proposed **candidate-only** pair, each with a 2-MiB reservation:

| Buffer | RGB888 NHWC payload inclusive | Suggested metadata start |
|---|---|---|
| O0 | `0x08000000..0x0812BFFF` | `0x0812C000` |
| O1 | `0x08200000..0x0832BFFF` | `0x0832C000` |

Each payload is `0x12C000` = **1228800 bytes**, tight `[1,640,640,3]`, RGB, UINT8; full 640x480 content at y=80, 80 gray-114 rows above/below, no resizing. Candidate letterbox/packer currently encode R in byte lane 0 (`raw_preprocess/fpga_v8_raw_letterbox.v:53-55`, `fpga_v8_rgb888_pack128.v:29-31`); components remain under construction, and this audit does not certify their tests.

These ranges are disjoint from all twelve current camera bank reservations, dormant preprocessing buffers `0x0A000000/0x0A1C2000` (`cam_prep_link.v:24-25`) and injection default `0x06000000` (`prep_regs.v:206`). No current non-NPU RTL writer uses the proposed pair. `audit/buffers.json` explicitly has **no board DDR assignment**. Crossbar DDR decode is 29 bits (`axi_crossbar_7x3.v:102`), while the DDR latch truncates addresses to `[27:0]` (`top.v:626,647`): keep allocations below `0x10000000` to avoid aliases. **Runtime exclusivity is not verified**: programmable camera addresses, the loaded bitstream and the HDMI viewer's unseen map remain unresolved. Do not substitute `0x00A00000` (cam1 bank 1) or the old `0x0A000000` display bypass.

Host `camera_dma.h:8-11` reserves six RX slots at stride `0x97000` in a 4-MiB mapping, with metadata scratch `0x3FF000`; an NHWC transfer exceeds a slot and remaining spare space. Provide distinct validated NHWC RX storage/offsets or redesign allocation; do not change only `total_length`. The former M02 register window at `0x40000000` is available as a candidate control endpoint, but the current stub never returns BVALID/RVALID (`top.v:2605-2622`): implement actual transactions before using it for descriptors/ACK.

## Clocks, resets and RK3568 handoff

Run reader, letterbox, byte packer, buffered writer and lease FSM on `axi_clk=core_clk`, reset `axi_rst=~ddr_init_done` (`top.v:395-398`); adapt candidate active-low `rst_n` with controlled synchronous release. Preserve the single-outstanding DDR read gate and ID reconstruction (`top.v:540-547,595-606`): S00, S02 and S05 serialize at DDR and need fairness/backpressure verification. Keep root `free_clk`/PLL untouched. Sensor PCLK->video CDC already exists; SFP RX->AXI CDC is at `top.v:1765-1773`. PCIe is another clock/reset domain; use existing F2H command/TX FIFO CDC (`pcie_fifo.v:475-486`), never forward AXI pulses directly across it.

Initial RK3568 path should read tight output through existing S00 F2H, retain owned CPU storage and submit `RKNN_TENSOR_UINT8`, `RKNN_TENSOR_NHWC`, `pass_through=0`, size 1228800; retained host already supports tight square RGB888 (`main.cpp:1524-1555`). This is not PCIe-to-NPU zero-copy. Native RKNN memory needs queried stride/size and sync certification; neither library symbols nor an AXI output format prove its native layout.

## PCIe cost versus preprocessing benefit

NHWC output is exactly **2x** the 614400-byte RGB565 frame. Replacing one inference raw transfer adds 614400 bytes/job. Keeping raw display/analytics transfers and adding model output adds 1228800 bytes/job: same-frame display+inference is 3x the former raw payload. Extra DDR traffic includes 614400 bytes read + 1228800 bytes written per job, plus output host reads competing with S00/KF.

Historical read-only artifact `../log/camview_fps_audit_20261003/dma_capacity.json` records capacity-only 614416-byte DMA: 125.99 MB/s with user copy (median 4.837 ms), 510.03 MB/s without user copy (median 1.183 ms). It is not a measurement of this candidate or simultaneous camera/KF operation. At 126 MB/s, replacement adds approximately **4.9 ms/job**; an additional output transfer adds **9.8 ms/job**, before FPGA compute, arbitration and host work. Six cameras at 30 fps already require 110.592 MB/s raw payload; another 15 output jobs/s adds 18.432 MB/s, totaling 129.024 MB/s. CPU bit expansion/letterbox savings must exceed added end-to-end cost, and display freshness must survive shared DMA contention. A preprocessing speedup is **not established** by this audit; schedule offload at inference demand, then compare completed FPS/latency, CPU time and raw-display freshness on matched inputs in a separately authorized experiment.

## Board read-only evidence and build gap

SSH used only `project/board_ssh.py` imported `connect/run`; privileged reads were needed for root-owned process/source paths. No credentials or auth-file contents were printed. Commands inspected `/proc` executable identity, targeted directory listings/hashes, tool/pkg-config availability and library exports; no device IOCTL, process stop, upload, build or NPU benchmark was issued.

At board time **2026-10-04T19:32:18+00:00**, Linux 6.1.99 aarch64, live PID **116090** was:

`/userdata/detview-hdmifull/detview-hdmifull --model wb_v4_combo --fullscreen --no-tracking --prefer-hdmifull auto`

Running executable SHA256: `0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`. At 19:40:39, its directory contained only that executable and `detview-hdmifull.before-full-yolo`; adjacent `main.cpp`, `src/`, `.pro`, `Makefile` and `sdk/` were absent. **Its complete source/compiler-input hash binding and HDMI memory map remain missing.** Older sources cannot be assumed to reproduce it.

| Retained board item | Verified SHA256 |
|---|---|
| `/userdata/linaro/detview-todo-work/build/detview` (not live executable) | `dbbe29cf09c2954df421f9d826f61040e8efaa22d35b2845b7a134038719eada` |
| same tree `src/main.cpp` | `6477821f639f2f7f878b90d4e4782ff469833dce0a0de91a86deb8749e45d941` |
| `/root/npu/detview/main.cpp` (another older four-camera source) | `df861c852a2b452c43b07641f6f573a15851f3b47150e1d5b4e1a0ab98fd0167` |
| `/usr/lib/librknnrt.so`, 7259064 bytes | `73993ed4b440460825f21611731564503cc1d5a0c123746477da6cd574f34885` |
| todo-work `sdk/rknn_api.h` and `/root/npu/detview/rknn_api.h`, 35707 bytes | `c48e11a6f41b451a5fd1e4ad774ea60252d3d94f78bee9b21ea3d21b21deba9a` |
| retained wb_v4_combo model under `/root/npu/whiteboard_3cls/`, `det-yolov8n-3cls-wb_v4_combo-rk3568-raw-dfl6-int8.rknn` (loaded model bytes not queried) | `21451a51f680ececd9ee75bcbb4db3e4ccee05d210ef9ffef2f1b99da61a8b31` |

Board tools: GCC 12.2.0, qmake/Qt5Core/Qt5Gui 5.15.8, pkg-config 1.8.1; `opencv4=4.6.0`, `librga=2.1.0`. RGA/OpenCV headers exist. No system RKNN header at `/usr/include/rknn_api.h`, `/usr/local/include/rknn_api.h` or `/usr/include/rknn/rknn_api.h`; use a pinned retained SDK include path. `rknnrt.pc` was unavailable; runtime library exists and exports `rknn_inputs_set/query/run/create_mem/set_io_mem/mem_sync`. `ldconfig` resolves RKNN to `/lib/librknnrt.so` and RGA to `/lib/aarch64-linux-gnu/librga.so`. Availability supports preparing a candidate build, not live-viewer parity or native tensor compatibility.

Current local source pins (top reread unchanged at end):

- `source/top.v`, 126929 bytes: `dca00ca2ecbc0b1418a32fc9abb09c673e522960a0150ef568f1e528a1681347`.
- `source/axi_crossbar/ddr_w_arb.v`: `b2401c87315d544a7ab85859b7c66d4a7c5822818f32e0f7b42a3f17e35ef10d`.
- `source/ov5640/ov5640_ddr/ov5640_ddr_w_ctrl.v`: `f90858a84018960102a57dc63578f82d53188bc9b0f811cc2c5e7150cf0b6b44`.
- `source/ov5640/ov5640_ddr/ov5640_ddr_w_en.v`: `a2f1c3f48d2e0d46b44ea98ab5394e6a486ed193c1c71716a1959fb0ad1160ce`.
- Retained local `motion_scheduling/host/src/main.cpp`: `2fa9479f42023b11d1810250041e4f8d080b48e7f1ee95b343243aebf0dd3942`, different from both inspected board sources.

Next candidate integration work: recover/hash the live HDMI viewer's complete compiler inputs and loaded RTL map; implement actual RAW/input/output leases; reserve the output pair and host RX allocation; connect S02 reader + added arbiter writer in an isolated top; verify byte parity, final-B publication, random backpressure, reset/abort draining and coexistence with host/KF reads. Production deployment/PDS registration is outside this audit.
