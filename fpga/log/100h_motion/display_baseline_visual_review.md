# Retained detview screenshot visual comparison

Reviewed `detview_before_motion.png` before candidate programming. Six panes
contain camera imagery in a 3x2 layout. CAM1/2 show the desk, CAM3 is rotated
toward the room and keyboard, CAM4 points toward the ceiling, CAM5/6 show the
board and wiring. Those orientations and fields of view are baseline behavior.
The top HUD reports approximately 19 new frames/s; per-pane capture HUD values
are 38, 38, 26, 26, 37 and 34. This is detview performance, not a candidate
motion-overhead measurement.

CAM6's bottom-right corner contains a black rectangle with white patterned
content already in this retained baseline. Candidate image comparison must
account for this pre-existing overlay/artifact instead of attributing it to
new FPGA detection without further evidence. No wholly blank pane or general
loss of image is visible. Static inspection cannot establish update continuity
or physical scan-out without tearing; candidate runtime logs remain required.

This screenshot is pre-candidate evidence only. Candidate screenshots and
120-second live observation have not yet been collected.
