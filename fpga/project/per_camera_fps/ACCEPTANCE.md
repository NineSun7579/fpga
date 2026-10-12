User target: actual fresh display uploads40fps forCAM1/2/5/6 and30fps
forCAM3/4, retaining sixvideo, correct full-frame inference and stereo.

Measurement uses per-camera fresh texture uploads, delivered frames and source
tag advancement separately. Composite displayFPS or repeatedswaps do not meet
this target. Successful inference completions/errors must be retained; static
motion deferrals are not inference-throughput improvements.

Historical logs indicateCAM1/2 source publication~45fps, CAM5/6~40.4fps and
CAM3/4~25.7fps. Camera tags count DDR publication, not necessarily raw sensor
VSYNC; source timing versus DDR admission must be distinguished before changing
sensor configuration.40fps onCAM5/6 leaves very little tolerance for drops.

Current isolated board baseline: build4550d74c95942794, gating1, HUDbatch1,
DET_BENCH0, globalcapturecap40. Start receipt:
log/100h_motion/motion_viewer_experiment_switch_9baa5eb83a364b0b9e6542d25497641d.json.
120s observation is in progress. Keep this identity until observation completes.
The observation has now completed; see cap40 baseline results below.
Original viewer/stereo/model settings and camview recovery remain snapshotted.

Independent workstreams: frozen RTL source-rate analysis and isolated host
NEON conversion/per-camera pacing optimization. No claim of target completion
before actual per-camera rates meet target across a>=120s observation.
Board code selftests must confirm byte-identical conversion, all6 display,
successful inference and source/controller safety before a candidate deployment.

## cap40 baseline complete

Observation8a71731400c34b0d8034d4b20206d943 completed; exact complete-window
metrics are retained in cap40_baseline.json. Compositefresh21.956fps,
successfulinference9.810/s, imageDMA117.594MB/s; allcamera readerrorszero.

| Camera | Delivered capture/s | Fresh display uploads/s | Target |
|---|---:|---:|---:|
|1|34.797|21.140|40|
|2|35.046|21.020|40|
|3|25.712|20.049|30|
|4|25.730|19.878|30|
|5|34.935|21.063|40|
|6|35.159|21.261|40|

Raising cap alone increases image load without meetingdisplaytargets. Proceed
with host conversion/display optimization and source-publication investigation.

CAM3/4 frozen sensor configuration uses PLL0x30 (48MHz), HTS1896 and VTS984;
nominal frame rate48e6/(1896*984)=25.728fps. CandidateVTS843 predicts30.031fps
without changing pixelclock. This is a register-timing calculation, not live
sensor readback or a confirmed publication/display rate. Exposure maxima and
raw VSYNC/DDR publication counters must still be checked. FPGA source work is
isolated from the deployed motion bit and originalIP directory.

Host candidate now includes explicit per-camera capture limits, exact RGB565
NEON expansion and latest-frame GUI consumption. Local63 checks passed; board
application build and AArch64 conversion validation are pending. Neither a
capture limit nor a timer interval is evidence of meeting freshdisplaytargets.

## Target host validation in progress

Initialbuild e7f30ed6779d2b0f passed all targetapplication selftests and actual
AArch64 NEON conversion63 checks. Microbenchmarkbaseline0.682ms/frame versus
candidate0.752ms/frame does not support a NEONspeedup claim. Initial25ms display
publication/GUI cadence lacked40fps margin and was corrected to16ms.
Correctedbuild983d1abe9acfe5c3 binary
76ecf38af0dd41740d34ff70bfab3fa22f88c4b48cb299ed7c60971e5fc87a55
passed targetapplication suites and is now running with40,40,30,30,40,40 caps,
motiongating1, HUDbatch1, DET_BENCH0. Startreceipt:
log/100h_motion/motion_viewer_experiment_switch_22a77aa06baf4fdd8dcc4c359a3364fa.json.
Identity-pinned120s observation is in progress. CAM3/4 still use deployedVTS984;
isolatedVTS843 FPGA build is active locally and has not been programmed.

Correctedhost observation6e78ea58777f4f37bf86d46c2ba8e950 now completed:
freshdisplayCAM1–6=21.028/21.242/19.835/19.826/21.200/21.105fps;
capture=34.605/34.993/25.643/25.636/34.809/34.867fps. Zero readerrors.
Composite21.878fps, successfulinference10.706/s, imageDMA117.086MB/s.
Exact completewindows storedhost16_result.json. No target met.
Mean paint23.816ms, camera upload7.907ms/frame; perHUD rebuild raster14.971ms,
pack4.320ms, upload9.566ms. Stage means use different count denominators and
must not be naively summed. Separating overlay rendering from video updates
is the next isolated host investigation; retain correctness/expiry/UI handling.

Low-overhead observatione1e9d9147fa4440db976da9200fc7341 completed with
identity/ownership checks every5s instead of1s, retaining start/end file hashes,
monotonic boundaries and progress coverage. Samehostcandidate and settings;
freshdisplay=22.275/22.378/20.601/20.730/22.172/22.267fps,
capture=36.430/36.499/25.717/25.681/36.512/36.581fps. Zero readerrors.
Composite22.799fps, successfulinference10.944/s, imageDMA121.304MB/s.
Storedlow_overhead_result.json. Scene differences prevent assigning the entire
change to observer overhead. Future paired tests use the same5s observer interval.
The40/30 per-camera freshdisplay objective remains unmet.

GPU overlay build030373f8af80e72b passed target application suites and actual
Mali-G52 GPU_HUD_TEST_PASS. Deployed opt-in GPUHUD1; identity-pinned receipt
log/100h_motion/motion_viewer_experiment_switch_f9bc12b53fde4254842ed9279b54c00f.json.
120s observation is active. Screenshot overlay/board_gpu_hud.png confirms all
six videos, labels, boxes and stereo preview. No target rate claim yet.

FPGA VTS843 build_ny4i9z_e failed strict final STA validation (missing
All Constraints Met). No candidate bit deployment. Diagnose actual paths and
recover routing with original clock constraints; retain deployed motion bit.

GPUHUD observationc35e5c7047f24fb0a6279c09c34093b5 completed:
freshdisplay=23.548/23.608/20.959/21.871/23.582/23.617fps,
capture=37.079/37.187/25.700/25.714/37.186/37.147fps. Zero readerrors.
Composite24.064fps, successfulinference11.316/s, imageDMA122.898MB/s.
Meanpaint11.510ms, camera upload7.049ms, HUDraster4.364ms perrebuild,
HUDupload1.092ms. See overlay/board_result.json for completewindow evidence.
Compared with earlier low-overhead baseline, display improves but scene changes
limit causal attribution. No camera meets40/30 target.

Testing existing3slot texture ring with identicalGPUHUD candidate/settings;
receipt motion_viewer_experiment_switch_9168e2b1c5de41abbe96f86e13492113.json.
This measures whether rotating upload textures reducesGPU reuse stalls.

Ring3 observation125f938c7d8740d68af97358f10f3da7 completed:
freshdisplay=23.296/23.270/21.186/21.685/23.304/23.391fps,
capture=37.140/37.215/25.720/25.711/37.220/37.223fps; zero readerrors.
Composite23.916fps, inference11.541/s, DMA123.031MB/s, meanupload7.268ms,
meanpaint11.135ms. No clear benefit; restoredring1 withreceipt
motion_viewer_experiment_switch_aa134d50a7cd4598aa095a434dd47cfb.json.
Next isolateddirect_display candidate removes GUIpollingtimer and consumes
bounded latest-frame mailbox directly on queued displayAvailable notifications.
Producer cadence remains16ms, GPUHUD unchanged, no added buffers or framecopies.

FPGA failure diagnosis: router hold repair aborted at15,733 paths above its
15,000-path limit. Setup passed; CAM3/4 hold failed in bothcorners (worstslow
-0.170/-0.332ns). Isolated recovery_0s32b_lb now reroutes identicalplacement
with50,000-path repair limit; no clock/constraint/RTL changes. StrictfullSTA,
pin/PHY equivalence and candidate32bank motionmemory audits gate bitgeneration.
Details TIMING_RECOVERY.md. Recoveryowns vendorbuildlock; do not start another
PDS instance. No candidate has been programmed.

Directnotification builde86e58a8b3be55ad passed targetapplication suites and
deployed withGPUHUD1, ring1, gating1, bench0, per-camera40/40/30/30/40/40 caps.
BinarySHA587c25ddcc7290dbebf2ace279ea63cb7849b677579972efe6b6221aba6c4ed8.
Startreceipt motion_viewer_experiment_switch_b3aa178429d0410caad59bff148e2769.json;
identity-pinned120s observation inprogress. Userrequested localvisible realtime
terminal: live_progress.py shows actual vendorlogs, taskoutputs and boardreceipt
states, with no manufactured completionpercentage or hardware mutation.

Directnotification observationf1fc68966ddd4109aa627179c5f9da91 completed:
freshdisplay=24.151/24.176/21.601/21.867/24.134/24.194fps,
capture=37.040/37.051/25.666/25.676/37.078/37.134fps; zero readerrors.
Composite24.838fps, successfulinference9.088/s, imageDMA122.672MB/s.
Meanpaint9.625ms, upload6.748ms, GUIqueue6.754ms, capture-to-upload26.416ms.
Producer[panes] submission~60/s whileQtpaint~25/s. LiveXrandr confirms
1920x1080@60Hz, but requested swapinterval0 does not establish actualswapwait.
Result direct_display_result.json. Per-camera40/30 objective remains unmet.
Nextcandidate instruments paint-to-frameSwapped andbetween-paint timing without
adding redraws or changing capture/inference/stereo, to distinguishQt scheduling
from driver/presentation delays before selecting further optimization.

Presentation tracing candidate prepared in presentation/src and targetbuild
launched. OptinDETVIEW_PRESENTATION_TRACE=1 measures between-paint cadence,
applicationupdate-to-paint andpaint-end-to-frameSwapped delays, plusGUIthreadCPU
andcontext metadata every10s. It changes no rendering/capture/inference cadence.
Portabletimingstate selftest andsourceaudit passed; targetbuild/testing pending.
Boardlauncher supports--presentation-trace0|1 and ownershipselftests7passed.

Presentationbuild0297f6db187f0c93 passed targetapplication suites; deployed with
trace1 and allpreviousGPUHUD/ring1/gating/camera limits retained. BinarySHA
65dcf5c39bc6997d734a8091e95d32cf34ead5546feb647ecc5e96ad9e12867e.
Startreceipt motion_viewer_experiment_switch_6797eda41063455493c58285f2bfd396.json;
120s identity-pinned observation is active. Evaluate actualswap-after-paint and
update-to-paint distributions alongside eachcamera's freshuploads; pending
measurement does not establishQt/driver cause or40/30 completion.

Presentationobservationd0d208a6dc8d46f887dbcdcc2091a32f completed:
freshdisplay=23.960/23.882/21.630/21.561/23.934/23.951fps,
capture=37.200/37.222/25.714/25.686/37.253/37.183fps; zero readerrors.
Composite24.553fps, successfulinference10.331/s. Tracewindows show
swap-after-paintmean23.7–26.3ms, update-to-paint5.8–6.0ms,
betweenpaints39.5–42.2ms, GUIthreadCPU20.4–23.1percent of onecore.
presentation/board_trace.log retains observations; Qtcontext reports swap0,
not proof of driver interval. GPU governor simple_ondemand at800MHzmaximum.
Desktopxfwm4 configuse_compositing=true/unredirect_overlays=true; detview
_NET_WM_BYPASS_COMPOSITOR absent. Identityverified PID68396/start17220738/
binaryhash andwindowPID, then setwindow-only bypassCARDINAL1 for120s experiment.
No desktopsettings changed. Restore by removingproperty aftersameidentitycheck;
property automaticallydisappears on normalwindowclose. Actualeffectpending.

Bypassobservation97cefc9e95af47048138f9f3868b93e6 completed:
freshdisplay=24.508/24.525/21.870/22.017/24.568/24.603fps;
capture=37.265/37.323/25.711/25.718/37.288/37.297fps, zero readerrors.
Composite25.172fps, successfulinference9.041/s. Mean swap-after-paint24.314ms,
betweenpaints39.731ms, update-to-paint5.898ms. Bypassdidnotremove measuredwait;
scene variation preventscrediting smallFPSdifference to bypass. Result/trace
storedpresentation/bypass_result.json andbypass_trace.log.
Normalclose removedtemporarywindowproperty. Nextswapinterval1 experiment
211cb0bee05d4a8a9c5386a83b847bd5 retains samecandidate and baselineabsentbypass;
compare against originalpresentation interval0 baseline (not bypassrun).
120s observationactive. Capture/inference/stereo settings retained.

Swapinterval1 observation0ff2419700d9406e960b6d8b09fee34c completed:
freshdisplay=19.973/19.973/19.827/19.853/19.991/19.991fps;
capture=37.909/37.927/25.723/25.728/37.936/37.923fps, zero readerrors.
Composite19.999fps, inference9.819/s. Meanswap-after-paint30.411ms,
betweenpaints50.001ms, update-to-paint5.741ms. Interval1 worseneddisplay;
restored0 and launchedidle0 test4e5a63987d8b465fa51174c9d428dfd5.
Compareidle0 against originalpresentation baseline interval0/defaultidle5,
not interval1 run. Samecandidate/camera/inference/stereo/GPUHUD/ring retained;
120s observationactive. Windowbypass remains absent on thesefresh launches.

Idle0 observation78a65b4f8f4c417f942c1ac10fcf13e2 completed:
freshdisplay=26.352/26.575/23.062/23.183/26.635/26.309fps;
capture=36.220/36.250/25.719/25.667/36.425/36.311fps; zero readerrors.
Composite29.083fps, successfulinference10.536/s. Mean update-to-paint0.527ms,
swap-after-paint22.069ms, betweenpaints34.440ms. Keepidle0 while optimizing
remainingwait; composite29.083 doesnot satisfyper-camera40/30 objective.
Savedpresentation/idle0_result.json andidle0_trace.log.
Filteredliveprocessenvironment confirms startupQT_QPA_UPDATE_IDLE_TIME0,
DETVIEW_SWAP_INTERVAL0 andnoinheritedQT_QPA_EGLFS_SWAPINTERVALoverride.
Boardxfwm4 is4.18.0-1; earlier4.16.1sourcebehavior mustnotbeassumedidentical.
Xlibtargetheadersavailable for beforemapbypass candidate; no globaldesktopchange.

Beforemap compositorhint candidate preparedswap/src; isolatedtargetbuild active.
Sourceaudit confirms39baselinefiles unchanged andonlywindowlifecycle/build
additions. Originalproperty savedandrestoredconditionallybeforedestruction;
optinbypass1 appliedbeforefirstshow, handlesnativesurfacerecreation.
Portablepropertytests passed; actualLinuxbuild/LP64test/readbackanddisplay
comparison pending. Launcher--bypass-compositor0|1 supported;7ownershiptests
passed. Preserveupdateidle0 andswapinterval0 for nextcontrolledcomparison.

Beforemapbypass builde896c57888522673 passed targetapplication suites and
LP64BYPASS_PROPERTY_SELFTEST_PASS. Startedreceipt6344253697db4ee590c319c9357ff7a7,
binarybcd9650360c7a5f4902722a5612e91b8c63b30315d6b95739ccdd51cfd2d2f60.
Startup confirmsproperty_set1/readback1/before_map1; xpropconfirmsownedPID71064
andCARDINAL1. Mali-G52 actualrenderer. Theseconfirmhinttiming, not compositor
unredirecting. Sameidle0/swap0/ring1/GPUHUD1/gating1/camera caps retained.
120s identity-pinned observationactive; files swap/target_startup.log,
swap/target_property_readback.log andtarget_property_selftest.log retained.

Beforemapbypass observation7ac1b4be63ec407190718c6fe14cab74 completed:
freshdisplay=26.194/26.030/23.002/22.984/25.883/26.228fps;
capture=36.073/36.131/25.678/25.675/36.227/36.180fps; zero readerrors.
Composite28.817fps, successfulinference10.868/s. Meanswap-after-paint22.327ms,
betweenpaints34.648ms, update-to-paint0.550ms. Compared withidle0 baseline,
no demonstratedbenefit; targetremainsunmet. Results swap/board_result.json
andswap/board_trace.log. Windowhintreadback alone doesnot establishunredirecting.
Nextisolated EGLcallprobe measures actualeglSwapBuffers calls andaccepted
eglSwapInterval arguments plusactualconfig minimum/maximum interval andalpha;
Qtmetadata cannot establishthese. Probeimplementationpending.
Probe nowcompiledonRK3568; sourceSHA20b17b7afca7c147e7722a35f8ea042194dfca1c713a1c24a02efd998b4244c2,
librarySHA9b895aab656b97612cee31ed3558aa50d06a577623cea85d6a57412b3bf9f91b.
Identity/filesverified launcher enabledshim againstsamee896candidate,
startreceipta04e8125a2b24a2ca8a858600cc030ef. Idle0/swap0/GPUHUD1/ring1/
gating1/bypass0/camera caps retained;120s observationactive.
The shimforwardsoriginalarguments/results, nevercalls eglGetError; failed
metadataqueries mayset EGLerrorstate. Actualinterceptionneedslogconfirmation.

EGLprobe observation4486def0712045708c35dc6b00094091 failed: candidateprocess
absent. Retainedtargetlog showsrepeated eglSwapBuffersfailed3000 afterpreload;
these are invalidperformancedata, notdriverdelay evidence. Removedprobe and
restartedonlyafter confirmingcandidateabsent andDMAunowned viaidentity-bound
launcher; receipt03fa9d347aee4f62936eab9a32cec16b. Restoredscreenshot confirms
sixvideos andstereo. Recoveryobservation1a302e2597d041efbb22855ad3707566 completed:
freshdisplay=25.555/25.607/22.704/22.455/25.650/25.409fps,
capture=35.668/35.818/25.624/25.652/35.786/35.853fps; zero readerrors andzero
eglSwapBuffersfailurelogs. Composite28.045fps, successfulinference11.012/s.
Result egl_probe/restored_result.json; probe isnotloaded. Objectiveunmet.

FPGAstatus correction: recovery_0s32b_lb finishedrerouting14:04:24 in7min,
thenstoppedatpin-equalitygate. Earlierstatements thatrecoverywasstillrunning
wereincorrect. Noacceptablebitgenerated; exactpindifferencesarebeingdiagnosed.

FPGA successfulrecovery_0so0ct0h now independentlyreviewed: completed14:26:16,
duration20m05s. Pin/PHY/motionresourceproofsPASS,126STAsummaryrows no violations,
actualtop.sbitSHAa323d6dfad78aff2a4da975bad7c317dc7f6755d56c6a667c08c694893222a3d
matchesreceipt. Priorpincheckfailure involved112banklabelmetadata differences,
not ball/site/function/direction changes. Successfulreroute omittedplacementreuse
andpassesstrictfrozenpincomparison withoutrelaxingconstraints.
Preparing evidenceadapter for existingfail-closedSRAMprogrammer; noFPGA hardware
changesyet, noFlashwrite. ActualCAM34publication/displayratesremainunmeasured.

VTS843 candidate subsequently programmed but failed runtime: CAM3/4 hadzero
freshframes. Frozenmotion e3da image has now been restored inSRAM, Flashuntouched.
Recovery receiptrollback_current_3fb258dc1b1a492a97df74118ca68ff6/receipt.json
andmetrics.json confirm121.96s allsix advancing, CAM3/4 capture25.73/25.71fps,
inferencecounter160to1340, stereo248success0failures, allread/unstableerrors0.
Currentcalibrationviewer restoredexactargv/env,34filehashesverified.

Revisedsource-rate approach: retainVTS984 andfullsensorwindow; evaluateonly
CAM3/4PLL0x30to0x38 (nominal48to56MHz), tightenCAM34clockconstraints accordingly.
VTS843 was likely shorterthan approximately972readoutrows beforeISPdownscaling;
exactphysicalfailuregate remainsunmeasured. PLLcandidate preservesfieldofview
but mustpass ROMsimulation, FPGAclocktiming andfreshhardwareacceptance separately.
Isolatedpll56 preparation/build delegated; nosecondhardwaredeploymentyet.

PLL56 candidate ROMsimulationpassed1584transactions;694frozeninputhashesverified.
Fullvendorbuildpll56/build_po3co5wg started16:20:37local, reportedstagecompile
atlaunch. CAM34PLL0x38, VTS984/HTS1896/DELAY40 retained; stricterCAM34clock
constraints requirecleanmin/maxSTA pluspin/PHY/motionchecks beforebitgeneration.
Updatedvisiblelive_progress.py tofollowpll56/build_* stagelogs andopened
PLL56progressconsole. Completionis pending; noPLL56hardwareprogrammingperformed.

FirstPLL56build_po3co5wg stopped17:03:58 atfinaltimingverification after43m24s.
All126summaryrows contain7setupfailures, zeroholdfailures: CAM1capturevalid
toCDCsrc_drop enables worst-0.385ns; CAM3motionchanged_q toblocks_workenables
worst-0.034ns. Exact112pin/PHY/32motionbank checks passed. Nobitgenerated.
Seed1recovery build_aai6kbmf started17:22:36; onlyplacementseedchanges,
RTL/VTS984/DELAY40/strictCAM34clocksandacceptancegates retained.
Authoritativecurrentstatepll56/current_run.json; noPLL56hardwareactionyet.

## PLL56 runtime and intermittent host stalls (2026-10-04/05)

Completed build `pll56/build_counter_9caopnhe` generated bit
`bc40afff4210bee0333feff7754d8fd5fd45207b1a04a301cdf8add54d7465b0`.
Independent review verifies all 126 STA rows, no violated paths in the full
report, CAM3/4 17.857 ns clocks, pin/PHY equivalence, 32 motion RAM banks and
128 counter FFs without connected CE. SRAM programmer readiness subsequently
passed with `readiness_evidence_ox3p7nss`; programmer gates were unchanged.

SRAM deployment `pll56_deploy_a1b1cf04843840d7b699d2ba769443cc` failed runtime
acceptance: six delivered rates were about 2.2–2.7 fps in 120.59 seconds.
Automatic recovery restored frozen motion SRAM `e3da6e1f...e96f7`; Flash was
untouched. The first recovery window also stalled, then the same viewer PID
recovered. This does not establish FPGA causality or a successful PLL rate.

`host_stall/IOCTL_STALL_ANALYSIS.md` and `failure_attempts.json` correct the
successful-only DMA averages: six recovery alarm failures consumed 86.990 s
of elapsed time; their clipped union covers 71.272% of the observation.
Independent GUI, pixel-copy, HUD, inference and stereo paths also show long
elapsed intervals. Original binary disassembly verifies ioctl timer scope,
alarm-failure censoring and an unlocked copy loop. A slow ioctl wall timer
alone does not distinguish kernel waiting from descheduling.

Separate read-only clock capture `clock_stall_20261005_000249` collected 116
samples over 120 seconds on HDMI viewer PID 109952 / SHA `0301f690...a737`.
Largest board interval was 1086.513 ms, local receive interval 1078 ms,
vDSO-to-syscall skew 0.748 ms; no multi-second interruption was observed.
This is a different executable/configuration from the stalled calibration
viewer. Kernel schedstats were disabled. Historical stall root cause and the
original 40/30 fresh-display targets remain unresolved. A private diagnostic
source adds paired wall/CPU timers and all-attempt accounting for recurrence.
