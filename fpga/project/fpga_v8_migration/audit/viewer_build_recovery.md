# Exact HDMI viewer source/build recovery

Independent reconstruction now binds the recovered sources to the installed
HDMI executable. All 12 compiled objects and checked qmake/moc products match
the retained build byte for byte; the independently linked executable matches
SHA256 `0301f6901330ff161b76f1fb343edb5f0acbf93064b04794c98147da6e92a737`.
See `../viewer_rebuild_evidence/README.md` for complete compiler, header, linker,
library and source identities. This supersedes the earlier local-only search
that did not locate the actual source directory.

`../viewer_build_recovered/manifest.json` freezes 61 files retrieved read-only
from `/userdata/linaro/detview-hdmifull-src`. Main source SHA256 is
`f91893ec34c014eb4f14a9631dc2ed4d2c248eb69a9e4411b307a05d3261516f`;
project file SHA256 is
`62741039205b03dd0f082d10b037d58d1c4780ca75696ec534ee426bca80a4a3`.
The benchmark's 11,102-byte production decoder include is present in main.cpp
without any byte differences (SHA256
`bf268b78139e0489fe00ed5b7f0ef5e6a59fbc49d02b8424a6e5d63369e19700`).
The previously reviewed independently built `ed49b9ed...` viewer is a different
candidate and is not the installed HDMI viewer.

The recovered source requests 4 MiB each for Pango TX/RX, with six 0x97000-byte
camera slots and scratch at 0x3ff000. The latest read-only process inventory in
`../board/live_dma_layout_20261005.json` observes exactly two 4 MiB mappings and
one driver owner, PID 139571, starttime 24603902, on boot
`d167174d-777b-4f93-bc1d-ea01ffc83a9a`. `/proc` reports zero file offsets for both
driver mappings, so those offsets do not identify TX versus RX. The mmap source
requests use file offsets zero and 1 MiB respectively. Neither source nor mapping
inventory establishes exclusive ownership against future processes.

The recorded argv selects `wb_v4_combo`, fullscreen, tracking disabled and
`--prefer-hdmifull auto`. Source inspection establishes that `auto` waits for an
F-key choice; it does not automatically detect an optical HDMI source. HDMI full
mode joins C5/C6 into 1280x480, scales to 640x360 and pads the 640x640 model input
with 140 rows per side. A cooperative single-C5 640x480 input with 80-row padding
therefore has a different input contract. Single-camera cooperation cannot be
accepted as a drop-in replacement for merged HDMI inference. Full details are
in `../viewer_rebuild_evidence/SOURCE_RUNTIME_NOTES.md`.

Historical programming receipts identify a motion bitstream restored after the
PLL56 experiment: `e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`.
The complete frozen inputs are under `motion_100h/run_20261003_212303/inputs`.
That history is not a fresh identity check of current FPGA contents. The older
six-camera top hash `dca00ca2...` and frozen motion top hash `ba90f966...` must be
kept distinct when producing a new whole-design candidate.

Remaining integration evidence: current FPGA identity/reset domain, exclusive
DDR/RX/controller reservations, proven DMA retirement, exact optical stream
format, whole-design timing, and board coexistence/completed-inference FPS.
Recovery compiled only an isolated copy and did not execute or replace a viewer.
