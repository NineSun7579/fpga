# Motion-gated detview deployment

Prepared locally only. Parent review precedes board execution. This tool does not build, reset PCI, reload modules, write registers, inject keys, or force-kill processes.

Build `project/motion_scheduling/host/src` using `project/performance_100h/build_host.py --source project/motion_scheduling/host/src`. Use its successful immutable `builds/<snapshot>/receipt.json`; start requires this receipt, validates its source manifest, and pins the executable hash. Review the stereo file SHA256 independently and pass the full hash. The known wb_v4_combo model hash is pinned in the tool.

```text
python project/motion_scheduling/board_viewer.py self-test
python project/motion_scheduling/board_viewer.py check --build-receipt <build-receipt> --stereo-sha256 <full-hash>
python project/motion_scheduling/board_viewer.py start --build-receipt <build-receipt> --stereo-sha256 <full-hash>
python project/motion_scheduling/board_viewer.py observe --start-receipt <motion-viewer-start-receipt> --seconds 120
python project/motion_scheduling/board_viewer.py candidate_stop_restore --start-receipt <same-start-receipt>
```

After a successful restore, pass its receipt using `--cam-receipt` on the next
start so the new camview PID/starttime is verified. `resume_start` is only for
a saved first-start snapshot with no candidate sidecar, the original camview
absent and no DMA owners. Preserve both initial and recovery receipts.
The process-exit race guard treats a vanished /proc entry as absent but refuses
an unreadable identity while the PID still exists; seven local safety tests pass.

`check` and `self-test` do not connect. Defaults are texture ring 1, capture cap 30, DETVIEW_MOTION_GATING=1 and DET_BENCH=1. Candidate argv retains `--model wb_v4_combo --fullscreen --no-tracking --stereo-config /userdata/linaro/detview-todo-work/src/stereo_pairs.example.json`; cwd is `/userdata/linaro/detview-todo-work/build`. It inherits the current camview environment, including DISPLAY/XAUTHORITY. Model, stereo and immutable source hashes are checked before and after launch.

Start binds the current camview receipt `log/100h_motion/show_camview_ec0dadc39f9346a690b2df8f68470f31.json` to PID 51952/starttime 15757898 and the full dc9ca56440e3… executable hash. It captures live argv, cwd, full environment, UID/GID/groups and boot identity into an exclusive root-owned remote 0600 snapshot. Full environment never appears in local receipts or command arguments. Old viewer baselines are not used. A unique PID-associated WM_DELETE_WINDOW window and sole DMA ownership are required before close. Unsupported WM_DELETE or a 45-second graceful-close timeout fails closed; successful keyboard Q behavior alone is insufficient.

Candidate launch uses an open executable descriptor pinned by SHA256 and the saved credentials. Readiness requires five continuous seconds with the exact candidate identity, sole DMA ownership and one closeable window, within a 30-second readiness deadline. Every operation retains a unique local receipt, including validation, lock, SSH and readiness failures. The private candidate identity sidecar persists after launch; if readiness fails with a recorded candidate identity, the same start receipt can authorize graceful stop/restore. If launch occurred but no identity was captured, inspect manually before any retry. No automatic cleanup kills a launch left running.

Restore validates the start receipt, remote snapshot hash, operation/boot binding, and candidate sidecar PID/starttime/executable hash. It closes only that sole-owner candidate through WM_DELETE, then restores the captured camview argv/cwd/UID/GID/groups/full environment (including CAMVIEW_MOTION) using its pinned executable and a new private log. A stopped or reused PID, changed executable, unrelated owner or mismatched window blocks mutation. Restore receipts record the new camview PID/starttime; the original fixed camview identity cannot be reused for another switch.

Observation samples fresh bytes appended after its starting log offset, with a 16 MiB bound, rejecting rotation/truncation. It checks exact identities, full environment, sole ownership, compiler/extra inference interference during sampling and asset hashes at endpoints. Receipts retain byte offsets, monotonic duration and log chunks, including motion generations and policy statistics emitted by the host. Review these statistics for expected motion gating; receipt success proves stable collection, not application-level gating correctness. All operations share `log/100h_motion/board_session.lock`; builds do not use this lock, so observation checks runtime interference independently. Waits sleep at most one second.
