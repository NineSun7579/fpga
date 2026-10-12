# Bitstream and RK3568 verification goal

Goal: generate the diagnostic bitstream, program SRAM, and capture RK3568 screenshots to verify operation.

## Board baseline

- `baseline.png` and original `baseline.xwd` captured from RK3568 X11 root window, 1920x1080, 24-bit depth. Timestamp and host are recorded in `baseline.json`.
- Screenshot shows the desktop without a visible viewer window.
- Read-only `baseline_identity.json` records boot identity, kernel, viewer/device-owner query, loaded module listing and PCIe endpoint enumeration. At capture time, no viewer PID or device owner was returned; endpoint 0755:0755 was present.
- This baseline is not camera, DMA, model or newly programmed bitstream acceptance.
- `driver_identity_prebuild.json` subsequently confirms the fixed driver file SHA256 `0244c739f9758e0ab3296d14b72befbcf23050c7c02a97299531dfa514ce2861` and loaded build-id `1102cfd04acaeeea21ca4d03fe27ddbb32b7340a`. No viewer or device owner was returned; the boot identity and PCIe endpoint remain as recorded. This read-only observation does not prove DMA quiescence across FPGA reconfiguration.

## Build state

- exact09 completed actual mapping and placement/routing. Final timing failed; no diagnostic bitstream has been accepted or programmed.
- Independent audit identified incomplete migration of the original asynchronous timing exceptions and real same-domain setup failures. Constraint coverage repair and same-domain path analysis are in progress.
- Constraint repair is implemented in independent route03/exact11, with actual tool execution started. Runtime coverage and routed timing acceptance remain pending.
- Actual synthesis evidence now confirms 364 retained clock-pair exceptions, 3142 individually traced complement clock pins, and four mailbox max-delay records. The 20-clock universe matches the frozen V7 evidence; no same-domain false-path exemption was found. Routed coverage and both-corner mailbox acceptance remain pending.
- Three independent timing candidates passed actual RTL cycle comparisons: camera read decode (130,140 cycles), capture-control full-address decode (861,948 cycles plus 26,488 integration cycles), and lease count prefixes (319,624 cycles). The camera evidence auditor was rerun successfully; control and lease candidate hashes and completion logs were independently verified. Candidate physical timing remains unmeasured.
- Independent integration preparation is running in `source_diagnostics_timing_build_01`; all candidate and constraint evidence must be bound before actual tool execution.
- All three candidates are integrated into their actual registered sources in `source_diagnostics_timing_build_01`; preflight passed and the serial build controller is queued behind the prior physical validation.
- Candidate-only SRAM programming and board-evidence validators are prepared. Their delivery schema is being checked against actual synthesis/routed evidence naming before producing a validated manifest.
- build02 is independently prepared with the three regressed timing optimizations and two explicit-register replacements. Its complete diagnostic top regression passed 14,668 checks per version with equal cycle traces; the independent top evidence auditor passed all 123 delivery hashes.
- build02's queued controller was resealed after completion-marker and delivery-schema corrections. The recorded final controller revision binds actual query logs and audit sources and requires an unambiguous valid `.sbit`. It waits for map01's real 60-independent-endpoint result and prior tool controllers before launching.
- The programming consumer and delivery assembler now resolve only explicitly matched build01/build02 candidate names and absolute build roots; wrong candidate or root combinations were tested and rejected. No validated new manifest has yet been accepted.
- Generate a new delivery manifest only after complete timing, mailbox, reset, physical interface and protected-input acceptance. Bind programming receipt to that exact manifest and bitstream hash.

## Remaining board evidence

Current read-only RK3568 refresh retains boot dd39b8d1-cf2d-404e-914d-45eb87278794, PCIe 0755:0755 and the expected fixed-driver hash/build-id, with no returned viewer/owner. Actual XFCE session UID is 1000, DISPLAY=:0 and XAUTHORITY=/home/linaro/.Xauthority. Both model hashes still match the historical models. The current driving-demo ELF is now 1197608 bytes, SHA256 72cd352aba95fce2a9897fb3fefe7214940b080d3937a2c8bad8afa72f25a703, distinct from the historical executable. Its read-only ELF copy contains all prior launch flags and model-selector strings; board main.cpp was also retained and diffed. This establishes current artifacts and candidate argv support, not a reproducible ELF-to-source binding. No viewer or DMA was launched during these checks. New screenshots and runtime observations must use and record the actual executable identity rather than assuming the historical ELF is still deployed.

Latest real map01 result is FAIL: compile and synthesis each expose 60 logical storage cells, but device mapping packs 56 stages into 16 SRL2 pairs and 12 LUT6QQ pairs, leaving only four independent cells. The three tested devmap options were actually zero and did not prevent this packing. Build02 remains unaccepted; explicit primitive RTL and functional simulation do not establish physical independence. An isolated instance-level syn_noprune mapping comparison is underway, with the original map01 reports retained.

Build01 native PNR analysis identifies three cmos2_pclk Slow setup failures (worst -0.853 ns). DDR, pclk and pclk_div2 setup are positive in that analysis. Final detailed STA and nonempty MPW coverage remain required; the DMA v2 candidate stays isolated until actual paths justify adopting it.

Final STA is now available in build01_global_sta_review01. All ten groups are nonempty; MPW has 19 clock rows per corner and zero failures. Three Slow setup failures remain, worst -0.882 ns: camera2 falling-edge VSYNC launch to diagnostic gap q[10], gap prefix[1], and CDC drop_prefix[7]. These are half-cycle frame-clear paths dominated by routing; no DMA endpoint is implicated. There are 1598 unscored paths to retain as a limitation. The independent camera_boolean_candidate01 passes count/gap exhaustive transitions and RTL miter checks, but has no physical improvement evidence. A full-top regression03 using actual FIFO/IP models is underway before adoption; the smaller CDC miter used a FIFO boundary stub and cannot certify the full pixel pipeline.

Recheck current owners and driver identity before programming. Program the accepted candidate to SRAM, verify the programming receipt and DONE, rebuild the supported PCIe/viewer session, then retain post-program screenshots, viewer identity and runtime evidence. A screenshot alone is insufficient to establish camera frame integrity or DMA completion.

Repository review confirms the prior driving-demo argv and executable/model identities. The generic stereo viewer-session helper cannot be used for that executable. Obtain current desktop environment paths and record actual UID/PID identity when starting the demo after programming. No current DMA-idle certificate is established by the no-owner observations; historical endpoint remove/rescan and module unload procedures did not prove hardware drain. Any owner preflight must use concrete current idle evidence or a documented hardware-session reconstruction boundary rather than relabeling absence of open file descriptors as quiescence.
