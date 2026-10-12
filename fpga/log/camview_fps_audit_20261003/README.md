# Six-camera frame-rate investigation

Requested true-frame targets: C1/C2/C5/C6 >=40 fps; C3/C4 >=30 fps.
Source sequence rates, successfully read complete frames, composed frames and
actual GL uploads must be measured separately. Repeated display refreshes do
not establish sensor freshness or unique complete sensor frames.

The deployed viewer source matched project/host/camview/main.cpp before edits,
SHA256 82c46f204069481c7a290e593c2062754350e3299f83194e8f822b8a65c6dc6a.
The original source snapshot is main.cpp in this evidence directory.
baseline_screen.png records six-camera display at about 20.3 Hz, with reads
about 17.1/19.8/17.2/16.3/17.9/15.3 fps at the screenshot instant.
Historical independent source tag rates were 45/45/25.75/25.75/29.78/14.89.

Verified host defects:

- Each worker slept 6 ms while holding the common latest-frame mutex; failure
  paths also slept 25 ms while holding it.
- Composition added a 33-ms sleep to its own processing time.
- When both banks changed, bank A was always chosen regardless of sequence.
- Frame bank identity was not rechecked after the full DMA read.

The first candidate releases the common lock before sleeping, uses elapsed
time for a 25-ms composition interval, chooses the newer sequence bank, checks
the bank tag after reading and records read latency, delivered rate, sequence
advance and unstable reads. It retains serialization of the driver DMA buffer.
Candidate runs from /root/ov5640/camview_fps_candidate; original binary and
launcher remain available for rollback. No FPGA bit/IP changes in this test.

platform.txt: PCIe negotiated 5GT/s x2; CPU ondemand at its maximum 1.992 GHz;
initial SoC/GPU temperatures 63.3/58.3 C. Target raw payload is 135.168 MB/s
(220 frames/s * 640*480*2). Link specification alone is not a throughput result.

CAM3/4 and CAM5/6 source cadence currently falls short of the requested targets.
Host improvements cannot create missing sensor frames. Runtime SCCB is exposed
for CAM3/4; CAM1/2 nominal SCCB windows overlap PREP routing. CAM5/6 use the
50K initialization table and lack general host SCCB control in the inspected
top. Sensor timing changes require separate validation and preserve gray-edge
repair. The unconnected 100H is not being built or programmed.

Follow-up measurements separated capacity from CPU copying: no user copy is
approximately 510 MB/s, while libc copying drops aggregate transfer+copy to
126-128 MB/s. Therefore the latter is not a PCIe hardware bandwidth ceiling.
The four-vector LD1 experiment was slower and was not used by the viewer.
Paired Q-register loads/stores passed byte identity checks (614400-byte frame,
unaligned offsets and short tails), with transfer+copy about 168.74 MB/s versus
128.00 MB/s for memcpy in the isolated C++ benchmark. Its inclusion in the
viewer still requires six-stream measurements and screenshot review.

The serialized poll/select/frame+tag candidate eliminated observed unstable
tag reads during 30 seconds, delivering approximately 18.6 fps on C1-5 and
14.9 on C6. Actual GL uploads remained 20 fps even though compositions were
39 fps. Disabling HUD did not eliminate that 20-fps limit. HDMI is 1080p60,
and the renderer is Mali-G52. Cached GL HUD rendering and swap-interval
diagnostics are separate follow-up experiments, not evidence of target success.

CAM3/4 repeated SCCB reads were inconsistent, including incorrect OV5640 IDs
(expected 0x5640), despite ACK. The values in dma_capacity.json are retained
for diagnosis and must not be used as trustworthy sensor timing readback.
No sensor register writes were performed.

Six disjoint coherent-buffer slots permit overlap of CPU copies with the next
camera's DMA while retaining one DMA owner. Slot stride is 0x97000; each read is
614416 bytes. The last slot ends at 0x389010, below 4 MiB; all tag polling uses
the separate 0x3ff000 scratch region. One worker owns each slot and completes
its copy before reusing it. The read completion tag is checked before unlock.

The initial pipeline throughput experiment fetched about 45/45/25.7/25.7/29.8/
14.9 complete tagged frames per second. Actual GL uploads were still about 21.
Its experimental HUD shader failed to preserve alpha, so that build is not
accepted for image quality; the shader was corrected to preserve RGBA alpha
before the following screenshot/visual acceptance. Throughput counters alone
are not final display acceptance.

The actual linaro XFCE session has desktop compositing enabled (root's separate
xfconf query incorrectly returned false). Per-window _NET_WM_BYPASS_COMPOSITOR
is being evaluated with vblank synchronization retained; no desktop-global
compositing change or unsynchronized swap is required by the candidate default.

The independent-texture candidate removed CPU six-pane composition and uploads
only changed 640x480 images. It retained full frames and vblank synchronization.
Six-slot capture measured approximately 45/45/25.7/25.7/29.8/14.9 fps with no
tag instability during 30 seconds; actual per-pane uploads remained around
20/20/20/20/20/14.8 with the desktop compositor active. Per-pane upload counters
and truthful display HUD were added to avoid presenting capture/submission
counts as visible frame rates. A temporary desktop-compositor comparison saves
the linaro session's setting and restores it in finally.

The temporary compositor-off comparison improved uploads to about 28 fps;
turning swap interval off as well reached about 30 fps, still short of 40.
Those temporary settings were restored, and the candidate default keeps swap
interval 1. GPU was observed at its maximum 800 MHz; DMC at 1.56 GHz with the
performance governor. Continuous frame-swapped scheduling is the next measured
candidate; uploads remain counted only when a camera buffer changes.

Sensor-side blockers remain unresolved: the shared 50K table does not explicitly
write 3a00, so night mode cannot be assumed to explain CAM6. The 42/21 MHz
simulation is not a hardware measurement. Reliable sensor register readback and
VSYNC/PCLK/XVCLK evidence are needed before choosing timing changes. Current
work has not achieved the full 40/40/30/30/40/40 target.
