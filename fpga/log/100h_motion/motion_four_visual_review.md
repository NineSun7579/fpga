# Candidate display review

Directly inspected motion_four_live.png and motion_four_live_final.png.
Both are 1920x1080 six-tile viewer captures with legible HUD and no obvious
tile corruption. CAM1/2 show a laptop display and keyboard; CAM4 shows a
small illuminated diagonal object. CAM5/6 contain faint but discernible
scene content, with visibly different illumination in the second capture.
CAM3 is nearly black and cannot establish normal scene detail visually.
The earlier baseline.png shows a different, brightly illuminated scene,
so it is not a controlled comparison of brightness.

The 120-second motion_four_live_observation.json audit passes: 123 valid
advancing records per local camera, matching bitmap/count/bbox, no frame
error or unstable read; CAM1/2 maximum changed blocks 5/9. CAM3/4 have
advancing valid records but no changed region in this observation.
All six capture channels sustain positive rates; average display upload
35.82fps, swap 35.86fps. These establish update continuity, not an explanation
of CAM3 darkness.

Same-scene baseline comparison completed: baseline bit c3f07533… programmed
successfully with post-operation single PG2L100H/DONE=1, receipt directory
rollback/run_20261003_233409_480f6211550546cf81ce867e8dc0062e. Inspected
motion_same_scene_baseline.png directly: CAM3 is also nearly black; CAM1/2
show the same laptop/keyboard, CAM4 the same illuminated object, CAM5/6
the same faint scene. No candidate-specific darkness or corruption observed.
The viewer correctly reports motion unavailable on the baseline bit. The
same-scene comparison supports display compatibility, without claiming that
dark CAM3 contains visibly discernible scene detail. Candidate reprogramming
and original detview restoration completed successfully. Directly inspected
detview_restored_motion.png: original fullscreen six-camera viewer active,
HUD reports 21fps new images, all six acquisition rates positive. Visible
scene matches candidate/baseline comparison. Existing lower-right CAM6
black/white overlay remains consistent with the previously recorded detview
baseline behavior; the motion camview did not show that overlay.
