# Retained image provenance

The 30 evaluated PNGs are decoded frames from
`/userdata/linaro/detview-video-work/media/VID_20260912_151339_480p30.mp4`,
a 2,409-frame 30-FPS clip. Their source indices are uniformly selected from
1204 through 2408. All 30 local file hashes match the board's retained manifest
in `../board/retained_frames_eval30_manifest.json`.

The 16 development/calibration PNGs also come from this same clip, source
indices 0..2250 at step150. All 16 current calibration hashes match
`../board/retained_frames_manifest.json`. No selected source frame index or PNG
hash repeats across the two sets, but 26 evaluation frames lie within the
development set's temporal span. Scene independence is therefore not
established. The remote evaluation manifest's separate statement about a
first-half 100-frame parent calibration does not describe this migration's
16-image calibration.

These are unlabelled compressed-video-derived images, not retained original
614,400-byte camera RGB565 payloads. They support the reported same-input board
comparison and numerical diagnostics; they do not establish RAW-camera input
parity, scene-independent validation or class-accuracy acceptance. All float
detections in the 30-image integer comparison are vehicle; zebra/person
predicted-box coverage is absent.

The original `manifest.json` remains unchanged because existing experiment
reports pin its hash. This provenance supplements that immutable record.
