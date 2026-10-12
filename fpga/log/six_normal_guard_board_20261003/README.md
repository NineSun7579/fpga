Normal-image restoration uses prepared 50K archive 023911. The only input change from verified guard archive 015705 is source/rtl/hdmi_ddr_ov5640_top.v, with COLOR_BAR_TEST=0 (top SHA256 88dc3630d558de1c7934ac7ad91f5e277c7514c690c11dca9f497bfa5ce084d5). TX guard inputs remain unchanged. No 100H production IP is edited.

The runner waits for the existing build and checks immutable inputs, physical proofs, STA, exact route/report and bit hashes. It scans only PGL50H and programs only archive 023911. Programming requires 100%, done bit 1 and command success before closing the window and checking its separate exit.

Board acceptance retains six fresh streams over 30 seconds, CAM5/6 input counts 307200, stable short counts, no overflow and no newly asserted fault masks. Old unchanged DMA/tag sticky bits are interpreted together with continuous accepted frame tags. Dark normal images are expected; identical rows and colorbar geometry are not normal-image requirements. Both RGB565 frames are retained and converted to PNG with row metrics.

The root viewer is restored and an actual X11 screenshot is captured. workflow_result.json remains needs_visual_review until the parent reads rk3568_normal_screen.png, cam5.png and cam6.png and checks scene correspondence and obvious tearing. Script booleans do not close the user objective.

Verified guard rollback is archive 015705, bit SHA256 8b2efca59e7a428d25e6ea14b072f0796d68ebe6af6b3b49da82088c4375fe57. The parent owns further 50K repair and final visual acceptance.

Launch verified at 2026-10-03 02:47:33: actual Python runner PID 49712, stage waiting_build, status running. Script: project/tools/finish_normal_023911.py. Live handoff: log/six_normal_023911_handoff.json. Durable output: log/six_normal_023911_autorunner.log. The existing visible normal build is owned by PowerShell PID 35312; this runner does not launch another PDS build.

Prelaunch checks passed: both new Python tools are ASCII and parse successfully, normal input manifest matches production, only the top differs from the guard manifest, rollback hash is intact, exact 023911 flash Tcl matches, and Pillow/NumPy are available. Prior guard owner PID 53928 exited with verified handoff; no cdt_js or cdt_cfg was active. Diagnostics are sampled during acceptance as well as before and after, and their chronological order is restored before comparing short counters and fresh fault bits.


Single-owner diagnostics correction: restarted waiting-only postrunner 49712 as PID 18000 at 2026-10-03 02:56:09. Acceptance now samples aligned diagnostic slots on its existing DMA mapping; before/during/after samples all enter interval gates. Offline fake-DMA and transient-fault tests pass. See dma_diagnostics_patch_restart.json. No build or burn process stopped.
