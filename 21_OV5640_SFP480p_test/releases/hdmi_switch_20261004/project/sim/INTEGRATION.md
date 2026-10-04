HDL handoff (2026-10-03)

Default/KEY1 K18: both OV5640 cameras, unchanged cam2_merge RGB565
1280x480 output on SFP0 / HSST CH2. KEY2 L15: latched MS7200 HDMI input;
both camera RESET outputs assert low and capture/merge FIFOs are reset.
KEY1 holds the MS7200 physical RESET low and disables its configuration and
capture. Keys are active low, synchronized, and debounced for 500000 sys_clk
cycles (10 ms) on both press and release. KEY2 wins simultaneous presses and
dominates while held. Releasing a key does not change the selection.

HDMI mapping: progressive RGB888 DVP, positive VS, automatically qualify
1280x720 or 1920x1080, nominal pixel clock <=148.5 MHz. For 720p, keep source
rows 0,1,3,4,...,717,718 and all columns. For 1080p, keep columns 0,1 of each
three and rows 0,2,4,7 of each nine. Convert each RGB888 pixel to
{R[7:3],G[7:2],B[7:3]}. Output remains 1280x480 RGB565, so the real 100H
receiver still splits x=0..639 into C5 and x=640..1279 into C6. These are the
left and right halves of the computer image. This is row decimation, with no
filtering, aspect correction, or frame RAM. Thin features may be lost.
720p60 and 1080p60 are simulated; 720p30/50 fall within the nominal capture rate
but are not independently simulated. Interlaced, 640x480 and arbitrary input
dimensions are unsupported. Configure the computer explicitly for 1280x720
or 1920x1080 progressive output: the supplied MS7200 register/EDID table remains
unchanged and does not itself enforce this desktop resolution.

Capture measures a whole input frame before admitting payload. Wrong width
or height stays unqualified; geometry loss during an admitted frame or FIFO
overflow aborts it and flushes capture. A changed source cannot be fully
validated before its pixels arrive, so a sudden geometry change or unplug
can leave an incomplete final old frame on the receiver. The next valid
source VS resets the receiver count. No protocol metadata or receiver RTL
was changed. A normal key switch waits for 614400 pixels before committing;
a frame with stopped pixels times out after 100 ms. An unqualified no-pixel
HDMI frame is allowed to finish measurement; it can still be switched away
after the timeout. All sources use fixed clocks; the mux is data-only in
the 62.5 MHz merge domain. FIFO reset assertions are common, release is
two-edge local synchronization, and packet output drains for 32 merge edges
before reset. Both capture FIFO sides and all packetizer pipeline state are
flushed. The 100H receiver's pixel count is reset by the next selected VS.

Source files added: video_reset_sync.v, video_mode_keys.v,
video_mode_switch.v, hdmi_720p_capture.v, ms7200_config.v.
Top replaced the dormant DDR/local-HDMI/diagnostic blocks with the optical
mode integration. sfp_video_tx.v, cam2_merge.v, camera generated clock
constraints, PLL and HSST IP are retained. power_on_delay.v keeps the original
5.24/1.31/20.97 ms startup intervals and now asserts both camera resets and
initial_en asynchronously. ms7200_config uses the supplied ms7200_ctl and
iic_dri, with SDA driven open drain. Initialization completion is the demo
sequencer's completion flag; it is not proof of an acknowledged physical chip.

BOARD PINS RESOLVED: original MES50HP 06_hdmi_loop.rar was copied from
NineSun's pangok50/50k/2_Demo and preserved under vendor_50k/. Its PDS
confirms Logos PGL50H -6 FBG484. The final active FDC mapping matches
MES50HP hardware manual Table3-6 pp.28-29: HDMI pixelclockAA12, VS W13,
HS V13, DE U13, SCL V19, SDA V20, RX RESET R17 and all24RGB input pins.
hdmi_in_mes50hp.fdc contains31LOCs and161exact original attributes.
review_hdmi_pins.py confirms no collisions across73active boardLOCs.
Source-synchronous input constraints currently use an explicit assumed
0..4ns arrival budget because the public MS7200 datasheet contains no
AC timing table. This is not measured hardware timing qualification.
Capture now uses Logos GTP_PLL_E3 and two GTP_CLKBUFG outputs for sampling
and zero-phase global feedback. Physical sample phase is43/64 of the input
period (241.875deg); first I/O registers and geometry/FIFO writer share that
clock. PDS infers its phase through rename-only generated-clock constraints.
Lock gates both FIFO resets; loss after acquisition faults the merge-domain
controller and flushes the shared transmitter. Capture readiness cannot
block PLL acquisition. PDS verifies the retained0..4ns input budget.
pixclk_in has a6.734ns clock. CDC constraints select first-stage D pins and
first reset-stage clears; FIFO held-data exceptions select memory launch
into the receiving clock. Local write/read addresses and second stages stay timed.

Fresh simulation commands, from project/sim:

    E:\questasim64_2021.1\win64\vsim.exe -c -do run_hdmi_modes.do -l hdmi_modes.log
    E:\questasim64_2021.1\win64\vsim.exe -c -do run_camera_disable.do -l camera_disable.log
    E:\questasim64_2021.1\win64\vsim.exe -c -do compile_top.do -l compile_top.log

run_hdmi_modes compiles ../../receiver/sfp/sfp_video_rx.v read-only. It uses
unrelated 50/62.5/125/74.25/148.5 MHz clocks, compares all 614400 output pixels
against the expected retained rows, then compares the actual RX output.
It covers debounce, press/release latching, simultaneous/held-key priority,
both switch directions during active frames, no stale pixels, repeated
switches with unplugged HDMI clock, unsupported width and mid-frame unplug.
run_camera_disable checks asynchronous physical reset assertion and full
startup delay on re-enable. compile_top compiles production RTL and generated
PLL/HSST wrappers; it is not a vendor primitive or analog link simulation.
Current timing and simulation qualification is recorded in ../timing_closure.md.
The timing agent ran PDS; hardware programming remains parent-owned.

Final fresh results: hdmi_modes.log at 23:49:21..23:50:00, TEST PASS,
131743380 ns simulated, 1536009 payload packets, Errors: 0 / Warnings: 0.
camera_disable.log at 23:47:06..23:47:13, TEST PASS, 55050410 ns simulated,
Errors: 0 / Warnings: 0. compile_top.log at 23:50:24, TOP RTL COMPILE PASS,
both compile invocations Errors: 0 / Warnings: 0.

Diagnostic variant: DIAGNOSTIC_HDMI_BOOT defaults to0 in production.
When enabled in a separately built diagnostic copy, it waits200ms then
generates a100ms virtual KEY2 press through the real10ms debouncer.
run_diagnostic_boot.do passes startup/no-automatic-selection for production,
exact pulse thresholds, latching and both key directions in simulation.
Test uses digital PLL/HSST mocks and cannot verify the analog optical IP.
2026-10-04 diagnostic_boot.log: TEST PASS, zero errors;54missing optional
testbench-port connection warnings. compile_top_after_diagnostic.log: zero
errors/warnings using actual generated wrappers. User cannot reach the
physical keys; physical button electrical acceptance remains pending.
For current long HDMI tests, compile input_clock_model.v: it supplies a fast
phase-following GTP_PLL_E3 model and global buffers. Vendor PLL/GRS/global
models are compiled separately by run_input_pll.do at10fs resolution, which
checks both rates, actual phase, 0/4ns arrivals and acquired-lock loss.
Native Questa runners must replace the obsolete input_buffer_model.v input
stage with this clock model (or use actual vendor PLL plus named GRS_INST).
