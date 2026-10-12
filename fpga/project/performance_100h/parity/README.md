Prepared locally only. Actual RKNN parity is pending the parent session's launch after the active performance observation ends.

From the workspace root:

```powershell
python project/performance_100h/parity/run_later.py --after-observation
```

The flag asserts that all performance observations have ended. The runner refuses an existing board-session lock and checks the SDK header. The parent explicitly authorized brief overlap with its separate full build after observation; the runner does not poll that build. It compiles baseline then candidate using make -j1, executes tests sequentially, and never stops a viewer or constructs a camera controller in parity mode.

`manifest.json` pins full original and harness file inventories, the frozen candidate build `053c691e05d07408…` / main `f3406080…`, the fixed whiteboard model SHA256, and two identical-per-harness 640x480 RGB scene crops. The candidate screenshot crop is dark; the brighter baseline screenshot is included as a second scene. Both crops retain screenshot labels/overlays. No resizing or synthetic detections are used.

Only each isolated harness `main.cpp` differs from its original source. The inserted `--parity-selftest IMAGE --model EXACT_ABSOLUTE_MODEL_PATH` branch runs before the camera/controller path. Baseline reproduces the original controller's RGB888 640-square allocation, gray-114 fill and row copies at y+80. Candidate submits raw RGB888 640x480 to its existing worker preprocessor. Both use the original `InferenceThread::runOnce`, decode and NMS, with three sequential frame IDs. Coordinates are in the 640-square model input space.

The runner executes the parent `build_host.py` implementation with two private adaptations: build receipts/logs go under `parity/builds/`, and `make -j2` becomes `make -j1`. Its existing complete SDK include path `/userdata/linaro/detview-todo-work/sdk` and SHA-isolated remote source/build paths are retained. Adaptation hashes are saved as `builder_baseline.json` and `builder_candidate.json`. No parent/candidate tools are edited. Existing successful matching parity build receipts can be reused.

The runner reuses `board_session.remote_run` for the established sudo stdin credential pattern. Credentials are absent from command arguments and retained logs. Both processes run with the same explicit minimal environment and `QT_QPA_PLATFORM=offscreen`; no DISPLAY is supplied. Scene/model/binary hashes are checked before and after all tests.

Results are retained under `parity/run_<manifest-prefix>_<timestamp>/`: raw per-scene/per-harness logs, a nonsecret request manifest and `report.json` containing counts, errors, repeat stability and full tuples. Exact matching ignores tuple order. Tolerance matching requires a one-to-one same-class assignment with absolute score tolerance 1e-6 and coordinate tolerance 1e-4 pixels. Failed loads, nonfinite tuples, incomplete runs and timeouts are errors. All-empty agreement is `empty_only_inconclusive`, never a positive detection-parity claim.

Individual retained logs can be compared without SSH:

```powershell
python project/performance_100h/parity/compare.py BASELINE.log CANDIDATE.log
```
