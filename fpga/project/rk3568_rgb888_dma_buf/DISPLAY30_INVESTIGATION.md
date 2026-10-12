# Display30 runtime investigation

Preserved display-fix executable SHA25673613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100 remains PID2090 on boot ecec42a0-46bc-434b-a12c-ec45433a8437. Original FPGA/driver retained. No viewer restart or code/FPGA change during these trials.

Historical restored_display30.log has171 aggregate windows totaling865.116s: camera1/2/5/6 fresh uploads34.23/34.15/32.09/32.08FPS. Current initial six-window sample had26.41/25.88/26.14/26.21FPS. These are fresh camera uploads, not composite swap counts or capture rates.

Source forces QT_XCB_GL_INTEGRATION=xcb_egl and QT_OPENGL=es2. Thus absence of EGL from an inherited launch environment did not prove a different backend. Previous commentary suggesting EGL omission explained regression is superseded by source evidence.

Initial GUI takes28.39/s vs publications40.30/s: 361 replaced mailbox snapshots in30.295s. About29.6% of publication snapshots were replaced before GUI consumption. Capture remained approximately45/45/26/26/40/40FPS. Paint cost alone does not explain the loss; paint timing excludes EGL swap.

Sequential same-process trials, exact window evidence in corresponding sample_window.log:

| Setting | Aggregate seconds | C1/C2/C5/C6 freshFPS |
| --- | --- | --- |
| Compositor enabled, before toggle |30.481|31.50/31.46/31.17/30.81|
| Compositor disabled |35.402|27.51/27.43/24.97/25.28|
| Compositor reenabled |35.289|27.35/27.26/25.99/26.64|
| CPU performance governor |30.382|32.42/32.22/30.22/30.18|
| CPU ondemand restored |30.519|31.32/31.59/29.98/29.23|

Aggregate windows overlap CPU sample boundaries; compositor transition windows can mix states. Scene/scheduling variation remains. The initial enabled run already recovered >30 before any mutation. Reenabling did not immediately recover; CPU ondemand also achieved~30. These trials do not establish either compositor or governor as sole root cause, nor sustained minimum30FPS.

HDMI1920x1080@60Hz and DSI720x1280@69.05Hz active; fullscreen viewer focused. No _NET_WM_BYPASS_COMPOSITOR property. Current xfwm4 compositing=true,vblank_mode=auto. Read-only60 clock samples: GPU800MHz every sample; CPU1.104-1.992GHz; temperature60.6-62.8C. No observed GPU downclock.

Five-second main-thread strace summary (-c -w, no other threads) shows3.081s elapsed in futex across1361 calls and0.023s in ppoll across178 calls. Trace detached normally. Profiling perturbs execution; these are diagnostic waits, not acceptance throughput. User-space stack unwinding unavailable in installed strace. Futex ownership is unresolved: cannot yet attribute to EGL/Mali synchronization, Qt synchronization or application locks. Determining that requires user-space call-stack profiling or separate diagnostic swap/event-loop timing.

All temporary settings restored: compositor=true, CPUgovernor=ondemand. Original viewer remains active. SPI Flash unchanged. Correct conclusion: preserved executable can again reach~30FPS, but runtime presentation varies; stable historical performance has not been reproduced across a long matched trial. No permanent tuning justified by these short samples.
# GUI swap wait attribution — continued debugging

## FlipFB investigation and bounded configuration trial

User accepted FlipFBnone as current version with known CPU cost, requesting
live screenshot. Adoption1791623759826415100 completed; originaldisplay30
executable unchanged, PID37468, persistentFlipFBnone, bothoutputs/sixcamera
health passed. The previous alwaysconfig is retained in adoption rollback files.
adopted_flipfb_screenshot/hdmi.png is an actualX11capture: HUDnew41fps,
C1/2/5/6image32/35/36/36 atinstant. This user selection supersedes the earlier
operational decision to retainalways; remaining strictstable30/capture/CPU/
optical acceptance limitations are unchanged. No furthertrial running.

Warmed repeat flipfb_trial_1791621823490481400 completed and original restored.
Each phase had separate60s warmup; original180s / none602.12s / restored180s.
FreshC1/2/5/6=31.65/31.50/29.49/29.52 ->36.54/36.65/34.63/34.73 ->
25.93/25.88/24.74/24.83FPS. None120completewindows (~607.50logseconds)
below30 counts1/1/1/2; minima28.82/28.24/25.88/26.27. Clear sustained
average display improvement repeats, but strict every-window30 remains unmet.
CPU214.59/233.65/202.09%: higher display workload has a CPU cost.
Capture C1/2/5/6 original44.98/44.99/40.36/40.36, none41.79/43.47/39.69/
39.71, restored44.43/44.53/40.16/40.20. Cam1 loss is ~7.1% vs preceding
original; cannot accept a whole-system fix while capture regression persists.
Inference3.83/3.85/3.89s; six errors zero. Matched appendedXorg fliptimeout
counts0/0/80. Original-before good performance without fliptimeouts shows
timeouts are not the sole explanation; FlipFB processing remains a contributor.
Result-age events absent; optical latency and tearing are unmeasured.
Postrestore original34196 same executable/config hashes, same output layout,
sixerrorszero; latest capture~45/45/26/26/40/40. No retained config change.
Next concrete direction: bound display work with none while preserving capture;
test existing publication/update pacing before any permanent acceptance.

First cycle completed: flipfb_trial_1791621146547396400/comparison.json.
Each phase ~180s, original / none / restored always freshC1/2/5/6:
22.59/22.67/21.86/21.94 ->36.45/36.25/33.51/33.59 ->
24.36/24.16/23.19/23.18FPS. None-phase36completewindows had2/2/2/3
windowsbelow30; lowwindows remain, so stable30 acceptance is still unmet.
Capture remained~42-44/43-44/25-26/25-26/39-40/39-40; inference means
3.65/3.83/3.86persecond. CPU258.9/235.7/214.1%, so do not claim reversible
CPU gain. No inference-age events were emitted: accepted-result age unavailable.
FlipFB=none confirmed in Xorg log; originalalways confirmed after restoration.
Saved timeout counts cover unequal Xorg uptimes, so not comparable rates.

Original viewer29876/hash73613d… and exact configSHAac4d85ee… restored;
posttrialhealth confirms6errorszero and identical HDMI/DSI output layout.
Strong reversible display improvement motivates a warmed longer repeat,
but restart/workload confounds and physical tearing/scanout remain unmeasured.
Prepared repeat:60s separately logged warmup perphase, baseline180s,
none600s, restored180s, distinct filenames and matchednew-Xorg-log intervals.

Original viewer24297 and Xorg1348 remained active at preflight on the same boot.
Installed20-modesetting.conf requests glamor, DRI2, and FlipFB=always.
Its performance-warning comment motivates a test, not a causal conclusion.
JeffyCN/xorg-xserver master reference files are saved under xorg_reference;
they are not matched to installed driver build
a366009ab34d413aceac73fe792ed473206968f4. Reference code selects FlipFB at
startup; its flip-timeout warning occurs after >=50ms.

Xorg trace/stack in xserver_waits_1791620783304725700 detached normally.
Snapshot: Mali glFenceSync -> glamor_block_handler -> msBlockHandler ->
WaitForSomething. Five-second trace:44SETPLANE calls total321.978ms,
mean7.318ms/max17.169ms;45PAGE_FLIP calls total8.434ms. Neither snapshot
nor traced timing establishes total server GPU cost or the cause of all waits.

trial_flipfb.py launched: original180s / FlipFB=none180s / restored180s.
Independent review found and corrected recovery, atomic-config-write,
launch-receipt, desktop-user and readiness issues; final static review found
no remaining concrete blocker. Generated remote Python syntax passed.
Results pending. Gates: helper hash, exclusive deployment lock, graceful
retirement, atomic hash-guarded config replacement, same executable/argv,
refreshed session environment, exact HDMI/DSI layout, six-camera zero errors,
and original config restore. Uncertain retirement blocks graphical restart;
unknown launch identity is preserved for review. No FPGA/driver changes.


Classificationtrial1791619891649084900 completed, exactenvrestoredPID24297.
Backend24151 all830reportedchecks classifyPresent/minoropcode1(Pixmap),
flags1/isvoid1, no unknowns/invalidclocks; mean17.3032ms/max71.1734ms,
replywallfraction47.62%. Same830EGLswapsmean23.9849ms/max85.2830ms,
interval0success, swapwallfraction66.05%. This identifies the slow request family,
not whether server GPUfence/flip/eventdispatch caused confirmation delay.
Probe/restoredfreshC1/2/5/6=25.30/24.62/23.53/23.53 vs28.94/28.68/26.77/25.98;
capturehealthy~44/45/26/26/40/40,inference3.83/s.

Read-only Xorglog shows manyhistorical modeset fliptimeouts. Matchednew30s
observation uptime7944.25 onward found1newcrtc72timeout and0crtc96. DRMstate
maps72->video_port0/HDMI1920x1080@60,96->video_port1/DSI720x1280@69.
Samewindowfresh30.44/30.48/29.26/29.26FPS withlowwindowsremaining. Oneflip
timeout cannot explain all~17msreplywaits; causalroot remains unproven. Evidence
xserver_present_config.log,flip_timeout_observation/*,flip_observed_*.
All runtimeoptions restored, original24297active; nooutputdisable/driverchanges.
Next useful experiment should distinguish Xorg dispatch/DRM fence wait on a
matched timeline; preserve bothHDMI/DSI until anydisplaytopologytrial is reviewed.

Combined EGL/XCBtrial1791619224546392600 completed, exactenvrestoredPID22571.
BackendTID22425:805checkedrequests/30.0955s mean19.1988ms/max50.2822ms,
357>=20ms, replywallfraction51.35%; mainTID22403 only6checkedcalls inreported
startupwindow. EGL806swaps/30.1473s mean25.7705ms/max68.5329ms,
swapwallfraction68.90%, interval0requestsuccessful. Closecount and largebackend
replytime strengthen XCBwait attribution, but concurrentdurations notadditive
and don't independently prove everycheckmapsone-to-onewithswap.
FreshC1/2/5/6probe24.11/24.27/23.35/23.48 vsrestored25.16/25.42/23.97/24.00;
sixcapture~44/44.6/25.7/25.7/40/40,inference3.83/s inboth. No tuningaccepted.
Mali imports include xcb_present_pixmap_checked, DRI2 swap/buffer APIs; exactslow
requesttype notyetidentified. XorgPID1348 lifetimeCPU35.5%(notmatchedsample).
Started isolated send-cookie/extension/opcode correlationprobe; unknowncross-thread
cookies must remainunknown. No serverqueries or behaviorchanges permitted.

Ring3 trial1791618617358225300 completed and exact originalenvrestoredPID20413.
Interval0success1,929swaps/30.063s, meanswap21.47ms,max53.21ms,
swapwallfraction66.35%; freshC1/2/5/6=27.05/27.35/26.49/26.40 vsrestored
28.94/28.91/26.34/26.40. No demonstratedringgain. Capture/inferencehealthy.

Bounded allthreadsgdb snapshotPID20413: mainlibmali eglSwapBuffers wait,
backend20421(mali-cmar-backe) libccondwait->libxcb xcb_request_check->libmali.
Four-second main/backendstrace normaldetach: mainswapfutex0x55a8071b18
79completedwaits1.6735s and79backendwakecalls on sameaddress. This directly
identifies Mali backend as observedmainwakeproducer. Backend XCB confirmation
participation is observed, but snapshot alone does not prove allwaits XCBbound
or exclude GPU fences/Xserver scheduling. Posttrace sixcameraerrorszero,
capture44.46/44.96/25.76/25.76/40.35/40.11FPS. Preserved display_all_stacks.txt,
display_swap_xcb.trace,gui_backend_posttrace_health.log. Started isolated perthread
xcb_request_check timer implementation toquantify actualreplywait. No settings
retained and no FPGA/driver/sourceproduction edits.

Bypass trial1791618494619340900 completed with exactpropertyrestore. SamePID
19091 freshC1/2/5/6 hint1=26.03/26.29/25.60/25.80 vs restored28.82/28.59/
27.34/27.57. Capture~44/44.5/25.7/25.7/40/40,inference4vs3.83/s. No bypass
gain or evidence WM actuallyunredirected. Began existingoriginaltexture_ring3
test with identicalEGLprobe (intervalbaseline0), then exactenvrestore. Source
rotates only changedcamera textures and selects the uploaded slot for drawing;
RAW/inference/latestcamera semantics unchanged. No source/executable modification.

Interval1 trial1791618342864638600 completed, request1success1 but603swaps/
30.169s, meanswap31.3215ms,max44.2715ms,595>=20ms. FreshC1/2/5/6
19.24/19.24/19.30/19.27FPS vsrestored25.54/25.11/23.80/23.30;
capture~45/45/26/26/40/40 maintained, inference3.5vs4/s. CPU183.2vs203%
is reducedwork, notacceptedgain. Exactenvrestore originalPID19091 healthy.
Interval0 remains baseline. Started sameprocessfullscreen bypasshint1 trial,
requiring windowPID/fullscreen verification and finally restoring originalhint.
Bypass hint may be ignored by windowmanager; propertysuccess alone proves no
actualunredirect. No program/FPGA/driverchange in bypass trial.

EGL probe trial1791618223497539800 completed with normal verified retirement
and exact originalenvrestorePID18602. Probe1031swaps over30.152293s:
intervalrequest0 succeeded, allclockpairsvalid, mean19.1166ms/max44.0312ms,
587swaps>=20ms, sumswap/wall=0.653655. Thus successfulzero request does not
eliminate swap blocking; internalqueue/scheduling/sync origin still undetermined.
Probe freshC1/2/5/6=30.83/30.76/28.33/28.56, restored30.96/30.80/29.48/29.05;
sixcapture~44.9/45/25.7/25.7/40.3/40.3, inference4/3.83s. No efficacyclaim.
Started same-original requestedinterval1 probe followed by exactenvrestore;
singleconfigchange plus identicaldiagnosticlibrary, results pending.

Current original viewer owner changed externally to PID9992, same SHA256
73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100,
boot19abd024…, runtime log `/userdata/surround360/evidence/grab_probe/restored.log`.
Restart cause remains unknown. Five-second GUI-only strace detached normally:
106 waits on futex0x5593f19af8 total2.6629s, max44.764ms. Two bounded gdb
snapshots (compositor ON and OFF) both show libc wait -> libmali -> eglSwapBuffers
-> Qt xcb EGL integration -> Qt paint/event loop. Debugger detached normally.
This directly attributes sampled main-thread waits to the swap path; it does not
prove all futex waits have this origin, or identify driver/compositor queue cause.
Debugger/strace intervals are excluded from performance observation windows.

Same-process compositor ON/OFF/ON30s fresh uploads C1/2/5/6:
25.41/25.25/24.86/24.39 ->29.04/29.07/27.19/27.26 ->
31.51/31.34/29.07/28.90FPS. Capture retained44-45/44-45/25.7/25.7/40/40,
inference3.83/4/4 persecond. Improvement continues after restoring ON, so no
reversible compositor-only cause established. Compositor restored true/vblankauto.
Original viewer remains active, SPI Flash unchanged, no program/driver deployment.
Files display_main_waits.trace, display_main_stack_compositor_on.txt,
display_main_stack.txt(OFF), gui_swap_comparison.json preserve evidence.
Next diagnostic needs actual eglSwapInterval/config bounds and per-swap walltime
with low-overhead sampled instrumentation, not another inference hold change.
