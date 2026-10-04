# 50K HDMI / dual OV5640 optical link result

2026-10-04: ModelSim/Questa behavioral verification, PDS routed timing,
PGL50H JTAG programming and RK3568 actual GL screenshots completed.
The user confirmed the image is correct and the physical keys can switch.

Implemented behavior:

- Production reset/default: dual OV5640. Key1 K18 selects both cameras and
  holds MS7200 HDMI input in reset. Key2 L15 latches HDMI and holds both
  camera reset outputs low. Keys use10ms debounce and preserve selection
  after release; simultaneous presses giveKey2 priority.
- SourcePC: NineSun, progressive1920x1080@60.720p is also supported.
  Optical transport remains1280x480 RGB565.1080p retains two of every three
  columns and rows0,2,4,7 of every nine.100H splits each line into C5/C6.
- Globalinputclock plusPLLphase241.875degrees meets the explicit0..4ns
  assumed externalarrival budget at148.5MHz. Bothslow/fast setup,hold,
  recovery/removal pass. This budget was not externally measured.

Preserved production image (defaultdual camera):

`project/validation_20261004_185843/hdmi_ddr_ov5640_top_PRODUCTION.sbit`

SHA256: `a4d3b58fc38c6c4247fa1e17e34965cf9d6477e676b173f004097082fdda7a52`

Currentlyprogrammed diagnostic image adds one100ms internalKey2press after
200ms startup, because the keys were initially inaccessible. Physical keys
remainusable. User later askedtoleaveHDMImodeandconfirmedphysicalswitching.
The productionartifact remainsdefaultdualcam; it was not restored after
thatlatestinstruction.

`diagnostic/generate_bitstream/hdmi_ddr_ov5640_top.sbit`

SHA256: `4c45ec6bf4c08771c1096e2a4eead4a5a2b7f1ddcf12818e71e803131eebe1b9`

Evidence:

- ProductionPDS: project/validation_20261004_185843; worstdesignsetup/hold
  +0.411/+0.101ns. DiagnosticPDS: diagnostic/validation_20261004_190617.
- Freshmatchingfullsimulation: project/sim/capture_pll_combined_final.log,
  full720p/1080p receiverpixelcomparisons, mode/formattransitions, lockloss,
  defaults/debounce/isolation and actual100H decoder, zeroerrors/warnings.
- program_production_default_20261004_190636 and
  program_hdmi_diagnostic_20261004_191533: singlePGL50Hscan,100%program,
  successfulcfg_verify, programmerwindowclosedaftercompletion, exit0.
- verify_hdmi_loaded.log: laterreadonlyJTAGverificationstillmatches the
  diagnosticimage. No reprogramming orcamera restoration wasperformed.
- production_default_gl_20261004_111426.png: newproductionimageC5/C6camera
  pictures. hdmi_gl_20261004_111709.png: receivedWindowsdesktop inC5/C6.
- hdmi_gl_20261004_111709_C5_C6.png: extractedleft/rightHDMI view; preserve
  originalfullGLscreenshotasprimaryevidence. Userconfirmedphysicalkeys.

Board filename times areUTC; developmentPC times areUTC+8. Otherworkflow
video-playerwasleftintact. Existingcamera viewer usedonlywithfreecapture
device; livecameraGLviewer wasleftavailableforviewing. No driver edits.

Programming was JTAG SRAM, notflash. No power-cyclepersistence claim.
The five-minute implementation task should skip futurejobs oncompleted
marker, retainingalllogs/artifacts. Furtherburning requiresnewuserwork.
