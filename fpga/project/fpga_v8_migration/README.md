# wb_v8_w25_nop2c2f FPGA NPU migration

Target: PG2L100H self-developed FPGA NPU, using the existing camera/DDR/PCIe design.

Source artifacts are mounted under `Z:/yolo_project`:

| Artifact | Mounted source | SHA-256 |
| --- | --- | --- |
| PT | `whiteboard_3cls_weights/wb_v8_w25_nop2c2f_best.pt` | `635e817b1b2710bd01523a75a5e05a0b62a9c28ad2a6e1c124762ebf9885d9e4` (local hash; no release-side PT hash) |
| ONNX | `whiteboard_3cls_v8_v9/wb_v8_w25_nop2c2f_raw_dfl6_clip10.onnx` | `b26ac863bc1acbde8b66531101ab1a530d4b1ba7e72e0109ff41f5fa36333399` |
| RKNN reference | `whiteboard_3cls_v8_v9/det-yolov8n-3cls-wb_v8_w25_nop2c2f-rk3568-raw-dfl6-int8.rknn` | `be7ee818eef1cb916c9706580a1b58426fc047c60df12b80d341646dfbbd2cf9` |

The RKNN is a functional reference, not an FPGA weight/instruction image.
The mounted model README specifies RGB input at 640x640, classes zebra/vehicle/person,
three detection scales, six raw outputs, and DFL with 16 bins. The actual ONNX
graph confirms these contracts: input `[1,3,640,640]`; box heads `[1,64,H,W]`
and class heads `[1,3,H,W]`, at H=W=80/40/20 and strides 8/16/32.

Work takes place in this isolated directory. The production PDS project and bitstreams
remain the camera baseline until graph, fixed-point, integration, and timing checks pass.

Verified preparation:

1. Copied and hashed PT/ONNX/RKNN in `artifacts/manifest.json`. Release ONNX/RKNN hashes match.
2. Audited 55 Conv, 49 SiLU, six clipped heads; lowered 89 semantic tasks.
3. Original ONNX, static specialized graph and independently rebuilt task graph produce
   identical six-head float outputs on the recorded zero/ramp/image cases.
4. Collected 16 road frames for development calibration. CPU affine Q/DQ and LUT
   references are distinct from candidate Q16 integer execution.
5. `numeric_layer/` holds shared layer-scale Q16 arithmetic assets. All 55 Conv
   multipliers and folded biases fit legacy u16/i32 fields, without scale underflow.
   Input-zero-point bias correction uses the encoded multiplier. Conv padding uses
   the input zero-point; MaxPool padding uses the minimum code.
6. `legacy_hwc16/` prepares pixel-major HWC16 weights/bias/LUT files and 14 materialized
   channel-copy tasks. `feature_layout.py` and `audit/buffers.json` describe the separate
   C16 proposal; they must not be mistaken for the legacy layout or executable instructions.
7. Isolated activation LUT, signed affine Add, convolution finish and channel-copy
   RTL have standalone ModelSim evidence in their own reports. Full NPU integration remains pending.
8. RAW RGB565-to-RGB888 letterbox/packer passed 23 isolated simulation cases,
   including 4,917,738 compared RGB bytes. The AXI reader/preprocessor/writer
   now rejects physical 256-MiB address aliases and passed 49 retired frames,
   1,231,008 compared output bytes, 45 address rejections and eight invalid
   configurations. These are
   standalone interfaces, without the production DDR arbiter or capture leases.
9. The isolated seven-owner write arbiter passed 716 retired transactions and
   161,504 compared bytes. The output/lease AXI-Lite controller passed 45,662
   cycles against its independent scoreboard, including 540 randomized frames.
   It requires an externally certified stable RAW lease; current camera ACK
   behavior does not supply that contract.
10. `cooperative_core/` connects the actual controller, corrected frame bridge
    and seven-owner arbiter. Five integrated ModelSim suites pass, with 1,229,088
    complete copied output bytes and 933,888 camera-memory/guard bytes verified
    independently. The full frame competes with all six synthetic camera write
    streams. This internal-IO core still lacks installed DDR/PCIe routes, a real
    certified capture lease, exclusive board/host allocations and host handoff.
11. `ddr_adapter_contract/` passes five suites with the actual generated DDR
    FIFOs and an independent vendor scheduling stub. The original BID=0 wire
    fails core ID checks; the candidate preserves accepted IDs. Complete output
    bytes and 19,200 camera words match. Existing read SID/full-FIFO gates pass
    their directed schedules. Physical DDR operation and timing remain external.
12. `capture_lease/` holds the actual admitted capture bank through independent
    cooperative and host claims/releases. Nine suites use unchanged camera/DMA
    RTL and official Pango FIFOs: 530,044 full W words and 7,831,968 bytes match
    the independent golden, with 26 certified images. Certification applies to
    the supplied unfiltered stream, not the identity of the currently loaded
    upstream fiber transmitter. Fresh reset generations remain external.
13. `cooperative_endpoint/` forwards each 16-byte PCIe control slot to one local
    32-bit operation. Its regression matches 419 operations / 3,803 events.
    `capture_endpoint/` adds explicit ARM and host RAW claim/release, and a
    two-child router: 499 operations / 4,288 events pass against actual managers
    and controllers with injected source events. These are separate from the
    physical camera and complete top-level routing.
14. `cooperative_host/` copies a claimed NHWC frame into caller-owned storage
    before matched ACK. Its abstract transport tests pass 51 cases / 5,085
    assertions; the ModelSim crossfixture matches 142 operations / 722 events.
    Real DMA retirement, exclusive allocation and loaded endpoints are mandatory
    prerequisites, not facts inferred by this helper.
15. `viewer_build_recovered/` freezes 61 files from the retained HDMI build
    directory. Its retained executable and installed viewer match SHA256
    `0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`.
    The full production decoder include matches the recovered main.cpp byte for
    byte. `viewer_rebuild_evidence/` independently reconstructs the exact
    installed executable; 12/12 objects and checked qmake/moc products match.
    This is a historical source/build binding. The later native build audit
    observes an externally changed live viewer (`496acc4f...`) and retained
    source directory; see `viewer_native_build_evidence/README.md`. Runtime
    driver exclusion, current FPGA identity and cooperative allocations remain
    separate requirements.
16. `capture_core_contract/` passes actual capture, dual leases, cooperative
    preprocessing and actual-FIFO DDR adapter simulation. Its full-frame suite
    retains five complete RAW/input pairs. The independent host C++ preparation
    matches all 6,144,000 input bytes; wrong image/sequence pairings are rejected
    in `raw_preprocess/host_pair_artifacts/results.json`.
17. `component_synthesis/endpoint_netlist_sim_01/` simulates the original
    connected endpoint mapped netlist with official Pango cells. RTL and mapped
    traces are byte-identical: 654 operations, 3,913 events, all 128 response IDs.
    The `eligible.addr_end_1` warning caused no observed deviation in the tested
    boundary/high-address cases. This is finite component functional evidence,
    not whole-design equivalence or timing acceptance.
18. `whole_candidate/compile_01/attempt_02/` completes compile and synthesis:
    29,733 LUTs (44.64%), 30,889 registers (23.19%), 72.5 DRM (46.77%), no
    latches. At the unchanged 131.25-MHz core clock, synthesis setup slack is
    +0.370 ns and hold slack is -0.004 ns at ten endpoints. No PnR or board
    acceptance; this preliminary candidate still contains the frozen PCIe path.
19. `viewer_native_build_evidence/` records successful isolated Qt viewer
    compilation/linking, SHA256 `ede9db5b0746a25d3adbe5e549fbe8c88e5d6b29cf7446b6ebb53b6cb7f1d81c`.
    Eleven of twelve objects match the frozen baseline; only main.o changes.
    No deployment or viewer FPS claim follows from this build.
20. `pcie_retirement_contract/` demonstrates frozen H2F MSI at 1.064 us before
    CLAIM at 1.495 us and full AXI B retirement at 1.735 us. The isolated
    final-B completion candidate passes covered aligned streams and controls.
    Inherited post-AW W-stall loss and host-offset PCIe 4KB crossing remain
     demonstrated defects requiring further correction before whole integration.
21. `pcie_h2f_transport_contract/` corrects the demonstrated H2F receive path
     in an isolated candidate: 50 cases pass, including arbitrary AXI W stalls,
     legal 4-KiB PCIe chunk boundaries, DWORD host offsets, partial tails and
     final-B completion credits. The 1,228,800-byte stream matches the oracle;
     four fault cases recover only through coordinated reset. F2H, Linux ioctl,
     hard-IP ordering and board timing remain unverified.
22. `paired_input_guard/` checks the RAW/output host helpers' owned frame types
    for complete copies, full source identity, expected generation and fixed
    allocations, then certifies exact software/FPGA input bytes. Five retained
    full simulation pairs pass (6,144,000 bytes); 80 corrupted identity/payload
    cases are rejected. Certification is outside performance timing or must be
     included explicitly in both profiles; it does not establish live transport.
23. `viewer_native_runtime_probe/` validates the candidate Qt profile gate and
     native decoding against the actual pinned RKNN runtime. Thirty retained
     inputs at four confidence values produce 120 strict comparisons with zero
     score/coordinate error and matching counts/classes/order. The certification
     invocation has 30 runs, 60 gets and 60 releases; an accidental duplicate
     30-run invocation is explicitly recorded, not additional independent data.
     This is runtime correctness evidence, not viewer deployment or FPS.
     The observed live executable has changed externally to
     `/userdata/detview-driving-demo/detview-driving-demo`; current source/build
     binding must be re-established before integrating into that newer viewer.
24. `capture_arm_contract/` breaks the new ARM/SOF combinational feedback by
     removing READY from request decoding and checking it at sequential dispatch.
     The endpoint suite, nine unchanged lease regressions and four corrected
     capture/core revisions pass, including exact full-frame bytes, synchronized
     SOF priority and pending camera final-B rejection. Connected component
     synthesis reports zero combinational/latch loops, zero latches, +1.203 ns
     setup and +0.619 ns hold at 131.25 MHz. This does not close whole timing.
25. `current_viewer_binding_02/` retrieves 91 files with matching before/local/
     after hashes. Current live driving-demo SHA256 is
     `f1fd98042a6f87c410cc44fbff574fc01f42e63a3f08827574cff3e51b6433b4`,
     rotating trafficlight-16cls and wb_v4_combo, neither covered by the pinned
     wb_v8 native guard. Recovered decoder adds trafficlight sigmoid/NMS and
     geometry/remapping semantics; the old candidate main cannot replace it.
     Retained ELF matches the live executable; independent rebuild is pending.
26. `current_viewer_rebuild_02/` now independently reproduces the current
     driving-demo executable exactly (`f1fd9804...`), with 17/17 matching
     objects, 29 matching authored compiler inputs and five matching generated
     products. All 91 recovered files remain unchanged. This establishes the
     frozen current source/build binding, preserving trafficlight, geometry and
     driving overlay semantics. No viewer execution, deployment or FPS result.
27. `whole_candidate_v2/` integrates both reviewed fixes with exact production
     artifact bytes. Compile/synthesis pass; actual PCIe candidate hierarchy
     and corrected ARM controller are elaborated. All 489 interface checks pass,
     and final combinational loops/latch loops/latches are zero. Resource use is
     31,251 LUTs, 31,535 FF and 72.5 DRM. At 131.25 MHz, pre-route core setup is
     +0.597 ns; ten inherited hold checks remain -0.004 ns. This is preliminary
     synthesis evidence only. Physical source identity, coordinated reset,
     host allocation and PCIe/Linux/F2H retirement still require validation.
28. `current_native_runtime_probe_02/` certifies the current adapter against the
     current recovered production decoder on actual pinned RKNN output: 120/120
     strict cases pass with zero score, coordinate, class-order and count
     differences. Exactly 30 runs, 60 gets, 60 releases and 360 buffers leave
     zero active leases. Eleven profile preparation checks pass, including
     actual trafficlight/wb_v4 hash rejection; no input/output attribute queries
     occur during preparation. This validates the standalone adapter, not full
     viewer runOnce orchestration or viewer/cooperative FPS.
29. `whole_candidate_v2_route_01/` completes fresh compile, synthesis, mapping
     and routing with final slow/fast STA. Timing is not closed: core slow setup
     -0.429 ns (39 endpoints), core hold -0.028/-0.015 ns slow/fast. All 611
     reported failing paths are retained. Routed resources are 29,856 LUTs,
     30,779 FF and 71.5 DRM; 112 GPIO/DDR pads and 14 HSST bits match baseline.
     All four 153,600-bit motion histories remain, with RAM mode and consumers
     checked. No bitstream was generated or loaded. Path-directed correction
     is required before final candidate build and board acceptance.
30. `whole_candidate_v3/` prepares exact reset-fault guard bindings with 512
     interface width checks and preserved external API/pins/clocks/constraints.
     Its 19 guard scenarios pass. It has not run PDS; full elaboration, CDC and
     routed timing remain required, along with physical reset/posted visibility.

Current performance decision:

`audit/performance_preflight.json` verifies the live RTL has two 16-input/2-output
MAC engines. At an assumed 150 MHz, optimistic full Conv work alone needs at least
105.64 ms; 3x3 Conv alone needs at least 33.62 ms, excluding all memory/other work.
Retained same-model RKNN execution is about 21.08 ms. Directly restoring these
engines for full V8 execution therefore cannot establish a RK3568 FPS improvement.
Work also evaluates FPGA RAW RGB565-to-RGB888 letterbox preparation with RK3568
RKNN execution and native quantized-head decoding. Only measured end-to-end board
results can accept that cooperative route.

Accuracy limits:

- The integer road smoke cases retain 6/6 and 3/3 matched boxes; they reuse calibration images.
- A separate 30-image retained set has zero file-hash overlap with calibration.
  The two-stage head quantization has 73/80 matched float boxes at IoU>=0.5,
  seven unmatched float boxes and six additional integer boxes. Fusing heads
  into their output quantization domain retains 73 matches, seven unmatched
  float boxes and five additional integer boxes. Matched coordinate error
  falls from 10.58 to 7.62 pixels; neither variant has accuracy acceptance.
  All float detections in this set are vehicle; zebra/person coverage is absent.
  Checked board manifests identify both sets as samples from the same MP4.
  File hashes/source indices are disjoint, while scene independence is absent;
  see `evaluation_frames/PROVENANCE.md`. These are decoded video images, not
  retained original camera RGB565 bytes.
- The held-out bright-camera case retains one detection but moves a box edge about
  123.85 pixels (IoU 0.7332). Development calibration is not accuracy acceptance.
- Python `raw_dfl.py` uses explicit sigmoid and class-aware NMS. The retained
  production decoder uses a sigmoid heuristic and class-agnostic NMS with pre-NMS
  top300. Decoder results from these contracts are not interchangeable.
- Six clipped heads currently quantize preactivation then use a Clip LUT. This
  two-stage specification is distinct from fused Conv/Clip/output quantization.
- CPU integer execution models proposed arithmetic, not legacy RAM bit truncation,
  DMA packing, cycle timing or installed FPGA behavior.

RK3568 decoder measurement:

`native_board_benchmark_retry/` pins and verifies the supplied V8 RKNN SHA256,
captures 30 fresh per-image RKNN outputs, then compares 3,000 pairs of CPU
decoder calls on the same immutable outputs. Full dequantization plus scalar
DFL/NMS averaged 3.357 ms; direct quantized decoding averaged 0.272 ms (12.35x).
All 30 explicit-sigmoid/canonical-tie comparisons pass. Five images differ
from the retained production decoder's score-only tie ordering. The opt-in
production compatibility path mirrors the heuristic and both score-only sorts;
`native_board_compatibility/` passes all 30 production comparisons with zero
discrepancy. It averages 0.295 ms versus 3.576 ms for its matching scalar
reference (12.13x). Acquisition contended with the unchanged running viewer.
This proves a decoder-stage improvement, not completed inference/viewer FPS.

The first paired full-pipeline board benchmark completed 240 timed jobs per
profile in AB/BA/AB/BA order: 14.243 baseline FPS versus 15.932 candidate FPS.
It deliberately returns FAIL because strict runtime-float compatibility fails;
those rates are diagnostic and cannot be accepted as a replacement speedup.
`runtime_dequant_probe/` compares both formats from the same completed run and
checks that a subsequent raw read is unchanged: 16,884,000 elements, 1,214
observed head/code pairs, zero ambiguous mappings. P3/P4 use FP16-rounded scales
in the runtime's float conversion; P5 matches fused float multiply-add with a
rounded zero-point offset. The conversion audit matches every observed float
bit. The pinned-runtime opt-in profile passes all 1,214 mappings bit-for-bit;
the general decoder still defaults to mathematical affine conversion.

`pipeline_board_runtime_compatible/` repeats the complete paired benchmark with
the runtime profile and returns PASS: 14.5684 baseline FPS versus 16.0670 native
FPS (**+10.29%**), 240 timed completions per profile. All 30 certification and
240 timed production comparisons pass with zero recorded coordinate/score
error. All four paired rounds improve FPS; the unchanged viewer continues
running concurrently. CPU preprocessing is timed, while camera/PCIe input and
display are excluded. This establishes an isolated RK3568 completed-inference
improvement and does not accept FPGA cooperation or deployed viewer FPS.
See `host_acceleration/BOARD_RESULTS.md` and the retained evidence audit.

Legacy engine audit:

`conv_contract/` verifies all 55 HWC16 weight/bias images, actual weight loaders,
input buffers and both Add stages. The official vendor primitive bypasses P_REG
when USE_POSTADD=0, exposing a one-register error in both existing multiplier
wrappers. The persistent isolated INT8 paired multiplier corrects the delay:
524,288 products pass at delays 2/3/4/6, six invalid configurations fail
elaboration, and 24,576 core MAC words pass across original/additional delay
streams. Production wrappers are unchanged. For the frozen model weights, independently calculated
accumulator bounds fit signed24, with maximum conservative absolute bound
7,636,485. This safety bound does not resolve scheduling, signed Add/Concat or
finish integration. `finish/model_validation/` matches 85,795 two-lane words
across all 55 exported convolution constants (49 SiLU, six Clip), with exact
counts, last markers, stalls and no unknown-value filtering.

Status: isolated implementation and verification in progress. FPGA hardware
inference, whole-design timing/resources, capture leases/DDR integration, and
measured cooperative completed FPS remain unaccepted. `component_synthesis/`
records an isolated bridge compile/synthesis: 764 LUTs, 874 registers, zero
latches/DRM/APM, with all IO virtual and no whole-board timing acceptance.
The corrected bridge was resynthesized with its current hash (764 LUTs,
874 registers), and controller/arbiter synthesized separately (782/672 LUTs,
938/89 registers), all with zero latches/DRM/APM. Integrated-core compile and
synthesis pass with **2,074 LUTs and 1,773 registers**, zero latches/DRM/APM,
and all six source hashes unchanged. Virtual IO and nominal clocks do not
establish whole-design timing or board operation.
Two additional component projects pass compile/synthesis: DDR adapter with actual
FIFO RTL, **370 LUTs / 158 registers** (139 distributed-RAM LUTs included), and
connected endpoint/controller, **1,008 LUTs / 1,127 registers**. Both have zero
latches/DRM/APM. An address-function optimization warning in the endpoint needs
mapped-logic equivalence review before synthesis is accepted for integration.
Paired completed-inference benchmarking passes as recorded above. Installed
FPGA routing, certified RAW capture and final end-to-end cooperation remain.
