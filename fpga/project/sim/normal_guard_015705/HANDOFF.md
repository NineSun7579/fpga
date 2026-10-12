Prepared isolated normal counterpart to guard+sensor-bars build 015705.
No production sources, PDS projects, hardware, viewer or active runner changed.

Exact review: normal.patch changes only top COLOR_BAR_TEST default 1 -> 0.
Original bytes: original/. Candidate source bytes: normal/.
manifest.json records original, normal and alternative per-file SHA256 values.
source_tree_hashes.json additionally records all 292 production RTL-tree files
and both candidate maps. Normal canonical source-map SHA256:
559be1556a4fe63410e23817729fc968d26523335de74b4397489c29037e0cc6
Normal top SHA256:
88dc3630d558de1c7934ac7ad91f5e277c7514c690c11dca9f497bfa5ce084d5
TX remains 29a637f725a48323b8f8351221183cf823afa5917a41098bc748cd61969793cc.
reg_config remains 305b82b140c880c5ccdb43589629f792d1e3a181f58e612faa08e07eedc33d0c.

All parameter defaults are explicit in manifest.json:
normal: top COLOR_BAR_TEST=0, reg_config COLOR_BAR_TEST=0, TX_GE_SKIP_ENABLE=1.
failure isolation: top COLOR_BAR_TEST=1, reg_config COLOR_BAR_TEST=0,
TX_GE_SKIP_ENABLE=0; both top sensor instances explicitly pass the top mode.

Run from C:\Users\NineSun\Desktop\ov56401:

    powershell -NoProfile -ExecutionPolicy Bypass -File project/sim/normal_guard_015705/run.ps1
    C:\Users\NineSun\anaconda3\python.exe project/sim/normal_guard_015705/test_apply_helper.py

Serial regression reuses the original independent golden stream and TB.
It extracts both actual instance blocks from this candidate top and checks
two initialization rounds per sensor: normal=357 original SCCB writes;
diagnostic=358 writes with final 78503d80. Enable gating, START/STOP/ACK totals
and reset with source clock stopped are checked. verify.py checks wiring and
the exact one-anchor top edit. This is configuration lint/serial simulation,
not full-top elaboration, PDS timing/physical proof, or hardware acceptance.
The inherited power_on_delay duplicate-port warning is unchanged.

Parent-only apply command, AFTER owner finish and guard board PASS:

    C:\Users\NineSun\anaconda3\python.exe project/sim/normal_guard_015705/prepare_apply.py apply-normal

ASCII helper performs byte operations, verifies candidate test proof and all
five original/candidate source hashes and the complete original RTL tree before
writing only the top. It requires
workflow_result pass with no failures, owner handoff finished/verified,
matching owner result, geometry pass, actual PNG screenshot and matching
last-burn/archive bit SHA. Missing or failed evidence refuses application.
Subagent has not invoked apply-normal against production.

The existing 300882 software reset remains command index 1. A newly programmed
normal image must replay initialization/reset to remove already-running bars;
changing the default in source does not clear a live sensor by itself.

After applying, parent must create a NEW immutable source/build archive and
run the established single-owner 50K compile, exact STA/route/physical/pin and
source-provenance gates, then program that new bitstream. Preserve 015705
diagnostic archive/evidence. Run a fresh 30-second six-camera acceptance capture
with CAM1 delay 140 and diagnostics bounding the interval; check complete
frames/FPS/missing packets and CAM5/6 count=307200 with no short-count increase.
Restore the actual viewer and save a new actual RK3568 X11 screenshot.
Real-camera imagery can be dark in current illumination; bars are no longer
the normal-mode acceptance target. Hardware/build work remains the parent's.

Report labels belong in archive/evidence metadata, not viewer application
code/text overlays. Label 015705 evidence guard_plus_skip_sensor_bars;
new evidence normal_acquisition, including explicit defaults, source hashes,
bit SHA, capture duration, timestamp, screenshot path/hash and acceptance result.

If 015705 guard fails, DO NOT apply normal. guard_only_diagnostic/ is a future
failure-isolation alternative that changes only TX_GE_SKIP_ENABLE 1 -> 0,
retaining identical wire pipeline and sensor bars. See its review patch and
guard_only_prior_evidence.json: its TX bytes equal the prior tested candidate
(614400 exact pixels, 307200 guards, zero BC50 matches/overflow). Recommend this
alternative only if skip is implicated by the failing evidence. No alternative
apply command is supplied; parent must review the failure and use a new archive
and the same gates before any future build/burn.
