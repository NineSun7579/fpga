# Isolated background viewer candidate

Target: `detview_six_camera_background_candidate`, from `detview.pro`.
Baseline: adjacent `six_camera_async_viewer_src`. Default operation remains RAW.
Enable background display only with both
`DETVIEW_FPGA_BACKGROUND_THUMBNAIL=1 DETVIEW_FPGA_SIX_THUMBNAIL=1`.
No driver or hardware access occurs in `--background-selftest`.

The immutable copied pure reader is `background_thumbnail_reader.hpp`; its
upstream SHA256 and all baseline/candidate hashes are in
`background_source_manifest.json`. `background_transport.h` validates complete
128-bit record halves and implements the deployed burst256/contiguous host
mapping. `checkedCopy` is shared by the production callback and adapter tests.

Local tests use MinGW g++ with C++17, Wall/Wextra/Werror. Build
`background_transport_selftest.cpp` with `BACKGROUND_SELFTEST_STANDALONE` and
`-pthread`. Build `background_thumbnail_reader_selftest.cpp` separately for the
unchanged 128-case reader regression. Existing thumbnail/snapshot, frame metrics,
MVP and temporal tests retain their original standalone switches.

Full Qt/OpenCV/RKNN/RGA target build and vision/display integration self-tests
are parent-owned. Inherited README and verification scripts describe their
original async/batch baselines; use this manifest for background preservation.
No synthesis, device open, programming or board acceptance is claimed here.
