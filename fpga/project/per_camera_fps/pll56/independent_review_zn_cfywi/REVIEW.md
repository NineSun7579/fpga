Independent audit: PASS. Programmer readiness: BLOCKED.

Bit: C:\Users\NineSun\Desktop\ov56401\project\per_camera_fps\pll56\build_counter_9caopnhe\top.sbit
SHA256: bc40afff4210bee0333feff7754d8fd5fd45207b1a04a301cdf8add54d7465b0

All 126 STA rows pass; full 1861255422 byte report contains zero violated paths. CAM3/4 periods are 17.857 ns. Pins (112), protected PHY and 32 read-first motion banks match. Actual counters: 128 synthesized async-clear FFs and 128 routed FFs, all LCE_EN FALSE, zero connected CE pins. Empty physical .CE() ports are unconnected. Saved counter proof binds pre-device-map bak files; current synthesis independently passes too. All 694 frozen inputs verified; candidate differs only in top PLL parameters, clock constraints, capture adapter, counter RTL.

Programmer blocker: Existing adapter requires FPS-only receipt.candidate, parent/protected/reused-map provenance and reroute logs. PLL56 candidate has four intended source changes and fresh synthesis/map/strong_pnr. Adapter cannot truthfully assemble this manifest unchanged.
Actual unchanged programmer --check exits 1: Build status is not completed. No compatible manifest or successful readiness is claimed.

Exact executed check:
C:\Users\NineSun\anaconda3\python.exe -B C:\Users\NineSun\Desktop\ov56401\project\tools\program_100h_motion.py --mode sram --check --bit C:\Users\NineSun\Desktop\ov56401\project\per_camera_fps\pll56\build_counter_9caopnhe\top.sbit --build-status C:\Users\NineSun\Desktop\ov56401\project\per_camera_fps\pll56\build_counter_9caopnhe\receipt.json --log-dir C:\Users\NineSun\Desktop\ov56401\project\per_camera_fps\pll56\independent_review_zn_cfywi\checks

Check receipt: C:\Users\NineSun\Desktop\ov56401\project\per_camera_fps\pll56\independent_review_zn_cfywi\programmer_check_receipt.json
Hardware operations: 0. Builds: 0. Parent owns hardware next; adapter support must be expanded and rechecked before programming.
