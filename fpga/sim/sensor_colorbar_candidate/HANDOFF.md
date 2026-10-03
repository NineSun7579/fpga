The candidate changes only reg_config.v and hdmi_ddr_ov5640_top.v. Production
files, shared regression inputs, PDS projects and bitstreams are untouched.

Reproduce preparation from the workspace root:

    C:\Users\NineSun\anaconda3\python.exe project/tools/prepare_50k_sensor_colorbar.py
    powershell -NoProfile -ExecutionPolicy Bypass -File project/sim/sensor_colorbar_candidate/run.ps1

minimal.patch is the review diff; before_*.v are exact original bytes and
production_hashes.json records their SHA256. The generator uses bytes for all
RTL replacements, preserving existing non-ASCII text. It refuses to target the
production RTL directory or its descendants.

reg_config gains COLOR_BAR_TEST=0. Normal mode completes 357 commands, exactly
as before. Test mode completes 358, appending index 357 = 24'h503D80 after
index 356 = 24'h350300. Device address remains 8'h78. The top gains the same
default-off parameter and passes it to BOTH coms1_reg_config/coms2_reg_config.
diagnostic_hdmi_ddr_ov5640_top.v is the same patched top with its parameter
default explicitly set to 1 for a concrete diagnostic build.

The TB includes both real top instance blocks extracted by the generator.
Two full initialization rounds per mode decode the 32 serial SCCB payload
bits independently, compare the first 357 commands against an untouched
production-derived golden table, check the added 78503D80 only in test mode,
count START/STOP/completions/ACK bits, enforce enable gating and reset while
the configuration source clock is stopped. Real power_on_delay and i2c_com
are used unchanged. Full FPGA top elaboration and hardware images are not
covered by this configuration-only regression.

Register evidence: Linux drivers/media/i2c/ov5640.c defines 0x503d as
PRE_ISP_TEST_SET1, bit 7 as TEST_ENABLE, standard bars as (0 << 2), and
bar pattern as (0 << 0). Thus 0x80 enables standard stationary sensor bars.
Linux's menu uses 0x84 for its different vertical-change variant.
https://github.com/torvalds/linux/blob/master/drivers/media/i2c/ov5640.c

No 0x4741 write is included. RGB formatting is selected by 0x4300 and 0x501f;
existing production writes 430060 and 501F01. Linux documents RGB565 formats
there (430061 for its BE format and 43006F for LE). This candidate preserves
the current format/byte ordering to keep the experiment limited to sensor
pattern enable. Bar palette/ordering still requires actual capture validation.

Parent next steps after deciding to integrate:

1. Check production_hashes.json against current sources. If another agent
   changed these files, regenerate/review the byte patch against that revision.
2. Apply the two reviewed modifications by byte operations, preserving exact
   backups. Keep normal defaults 0; for a diagnostic build set the top parameter
   default to 1 using the provided diagnostic top or a verified PDS override.
3. Run required combined regressions and physical/pin audit. Prepare a NEW
   immutable build snapshot with the existing build_50k_final flow; do not modify
   or rerun the 235509 snapshot as though it represented the diagnostic inputs.
   Check PDS is idle before launching the single vendor flow. This subagent
   has not launched PDS or burned a bitstream.
4. Program the newly audited diagnostic image using the already-authorized
   parent hardware workflow. Wait until both configurations complete, then
   capture CAM5 and CAM6 in the actual RK3568 X11 viewer and save screenshots
   plus per-channel frame completeness/FPS/missing-packet statistics.
5. Evaluate bar edge continuity, row alignment, frame size and CAM6 gaps.
   Dark ambient illumination is expected and is not a brightness defect.
6. Restore normal default 0 and compile/program the normal image after the
   experiment, or restore the previously verified 235509 correct-pins image.
   FPGA reset replays the sensor's existing software reset command 300882;
   disabling the parameter alone without reinitialization does not clear an
   already-running sensor pattern.
