# detview C5 UI repair (2026-10-24)

## Evidence before repair

- The boot launcher uses the October 18 binary. The October 22 binary supports C5 switching and passes `--c5-runtime-selftest`.
- Following RK3568 reboot, checked VGA recovery passes with C5/C6 about 22.5 fps and six-view `err=0/0/0/0/0/0`.
- `--camera-resolution C5=720` does not commit HD. Existing project notes (`FIX_720P_SWITCH_20261020.md`, section 3.8) document that this option queues before C5 capability detection and is unusable.
- `--prefer-hdmifull` does not select sensor resolution. Earlier statements to the contrary were wrong.
- Correct manual operation: Tab (settings), Down six times to row 6, Right three times to select C5, Down once to row 7, then **Right** requests 720P. `F` changes view/composition and `H` opens help. Use Right rather than Enter for deterministic direction.
- Settings previously retained `m_settingRow`; blind Down/Right input can operate unintended rows.

## Minimal change

`host/viewer/main.cpp` resets `m_settingRow=0` when opening settings. The existing touch selftest additionally checks that revisiting settings resets row 0 after reaching row 6. No FPGA, sensor, mailbox, capture admission or fault-gate change.

Isolated source: `settings_row_reset_20261024/source`; board build directory: `/userdata/linaro/detview-settings-row-reset-20261024`. Existing binaries and service launchers are not overwritten. Initial upload failed with EACCES in the newly created directory only; permission to this isolated test directory was corrected before retrying.

Frozen `main.cpp` SHA256: `68066cbad6cd4df41a754ab2f2c06996fa7419c841ac20d5934b7fcfe99575dc`; verified byte-identical to the edited production host source at freeze time.

## Build layout correction

The first ad-hoc packages were incomplete: `host/viewer/main.cpp` includes five sibling headers from `host/`, and the old flattened source package does not preserve that layout. The initial failure also showed that the package alone lacked implementation `.cpp` files. The corrected frozen `full_layout/` retains `host/` plus `host/viewer/`, supplies `detview.pro`, and adds only previously absent supporting sources from the October 22 frozen package. It never overwrites files already in the authoritative host tree. No source logic was changed to bypass include failures. Build target: `/userdata/linaro/detview-c5-settings-layout-20261024/build/detview_motion_cam134`.

## Actual C5 capability startup failure

The first rebuilt viewer starts with healthy C5 DMA but logs `[c5] mailbox snapshot unavailable; C5 stays disabled`. Therefore its settings cannot select C5; further key injection is not evidence of an HD switch failure. `c5::snapshot()` performs one generation-fenced read during startup after other-camera initialization. The host previously had no bounded retry for that startup race.

Added `c5::snapshotWithRetry()` for **startup admission only**: at most eight complete generation-fenced snapshots, with the existing board wait between attempts. Persistent incoherence/read failure still disables C5. Capability, VGA geometry, recovery, capture-mask, drain, publication and fault gates are unchanged; `transact()` still uses single-attempt `snapshot()`.

Selftest additions: first snapshot torn and second coherent is accepted as attempt 2 (all 11 slots reread, one wait, no writes/drain); persistent tearing is rejected after exactly eight attempts with seven waits and no writes/drain.

Startup-retry frozen source hashes: `viewer/main.cpp=e3402d62b748ad5c12c3f009cd8847595aab5bf87cbd9abc873d5a993656d16c`, `c5_transaction.h=0d25bcfde480ffb3356d2b01a8da3e96a1f4e67df5e8637d7def59863d6afe6a`, `c5_runtime_selftest.h=6375aa0b5f949baa5509e76593ef407c510485522c8615d1e61dba2309f3b4b9`; local host and frozen copies verified byte-identical.

## Board result: C5 HD UI transaction passed

Built `eaf491e4ce8e0f9222e63e3a4835ec21299e09aa5c92257de370021e7ca360a0`; `--touch-selftest` and `--c5-runtime-selftest` pass. The startup no longer logs `C5 stays disabled`. Through the repaired settings UI (Tab, Down*6, Right*3, Down, Right), actual result:

- `[resolutionChanged] camera=5 hd=1 ok=1 reason=C5 native geometry committed`
- C5 `width=1280 height=720`, 1843200-byte frame payload, about 11.2 fps, `unstable=0`, zero read errors.
- C6 remains `width=640 height=480`, about 11.2 fps, `unstable=0`.
- Six-camera pane health `err=0/0/0/0/0/0`; `detview-c5-settings-fixed.service` remains active.

This is a transient tested viewer, not a persistent boot-service launcher replacement. It confirms the host-side C5 switch path and UI repair. Native-row image verification belongs to the separate FPGA acceptance record and is not re-established solely by these host logs.
