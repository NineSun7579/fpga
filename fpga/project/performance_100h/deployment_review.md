# Candidate detview deployment review

`board_session.py` implements candidate start/stop and bounded read-only observation. This work performs **no SSH, board mutation, build, vendor launch, or process switch**. The parent owns isolated builds and the original viewer stop/restore. PID 42262 and `current_viewer_restore_e023...` are context, not sufficient process identity; use the full actual restore receipt when stopping the original viewer.

Run local safety tests with:

```powershell
python project/performance_100h/board_session.py --self-test
```

Before deployment, retain the complete original restore receipt and private `log/100h_motion/current_viewer_baseline.json`. Do not print its environment. Record the final source-tree hash, independently obtain the candidate executable SHA256 from the isolated build receipt, and inventory/pin **all files consumed by the original model**, including its weights/instructions/configuration. `--asset` is repeatable and requires at least one pin; the tool cannot determine whether the supplied model inventory is complete. Existing baseline stereo/settings/source hashes are also checked remotely. It preserves exact original cwd, argv after argv[0], model selector, stereo config, credentials, groups and full captured environment. Relative model paths continue to resolve in the original cwd; the parent must ensure they resolve to the pinned assets.

The following is a recipe with placeholders, **not a command to run during this subagent task**:

```powershell
# SOURCE_HASH identifies the isolated source/build directory; BINARY_HASH pins its executable.
python project/performance_100h/board_session.py --check --exe /userdata/linaro/100h_performance/SOURCE_HASH/build/detview --sha256 BINARY_HASH --asset /absolute/model/weights=WEIGHTS_HASH --asset /absolute/model/instructions=INSTRUCTIONS_HASH

# Parent first stops the actual original restored viewer with its full identity receipt.
python project/tools/current_viewer_session.py --stop --target-receipt log/100h_motion/current_viewer_restore_FULL_TOKEN.json

# Only after the successful stop receipt verifies unowned DMA:
python project/performance_100h/board_session.py --start --exe /userdata/linaro/100h_performance/SOURCE_HASH/build/detview --sha256 BINARY_HASH --asset /absolute/model/weights=WEIGHTS_HASH --asset /absolute/model/instructions=INSTRUCTIONS_HASH --env DET_BENCH=1
python project/performance_100h/board_session.py --observe --start-receipt log/100h_motion/candidate_start_FULL_TOKEN.json --seconds 120
python project/performance_100h/board_session.py --stop --start-receipt log/100h_motion/candidate_start_FULL_TOKEN.json

# Parent restores the original with its original-viewer stop receipt, after candidate stop succeeds.
python project/tools/current_viewer_session.py --restore --stop-receipt log/100h_motion/current_viewer_stop_FULL_TOKEN.json
```

The source directory component and executable hash are separate pins. The
directory may use the full source digest or build_<16 hex> from build_host.py;
the executable is pinned by its full SHA256. Local --check validates bindings
without connecting. Allowed overrides are DET_BENCH, DETVIEW_TEXTURE_RING and
DETVIEW_CAPTURE_MAX_FPS; stop/observe reuse the launch receipt. Candidate code
reads capture FPS as an integer in 0..120, so use an integer value for experiments.

Observation checks /proc at entry, each one-second identity checkpoint and
endpoint for compilers/linkers/make and exact parity/rotation test arguments.
Interference fails the receipt instead of contributing acceptance metrics.
This sampling cannot exclude a brief job between checkpoints. Eight local
safety tests pass, including compiler/harness rejection and avoiding false
matches in Python script arguments. check_measurement_host.py performs the
same read-only pre-measurement inspection without printing environments.

Start requires an unowned DMA device, no existing candidate process, unchanged boot/config/model hashes, a canonical nonsymlink candidate path, and an independently pinned opened executable. It launches one owned child under sudo, with original uid/gid/groups/cwd and a unique exclusive log beside the original log; it never truncates the original log. Readiness requires the exact child PID/starttime/executable hash/argv/credentials/environment, sole DMA ownership and one PID-associated window supporting WM_DELETE_WINDOW to remain ready for three seconds (configurable), within a maximum 60-second deadline. This establishes lifecycle readiness, not valid pictures, correct detections, or performance acceptance.

Stop verifies the launch identity, current executable/settings/assets hashes, unique candidate process, sole DMA ownership and unique closeable window immediately before sending **WM_DELETE_WINDOW only**. It waits for verified exit and an unowned device. There are no force kills, signals, broad process-name kills, module/register operations or vendor controls. Timeouts leave the process untouched. A failed start may leave a child running; its failed receipt retains launch PID/log and captured identity when available. Stop deliberately requires a successful start receipt. Inspect any failed launch and use a separately reviewed exact-identity recovery procedure; do not forge a success receipt, force-kill, or launch a competing viewer.

Each action retains a unique local `candidate_{start,stop,observe}_*.json` receipt, including failures after lock acquisition, with candidate binary hash, source path, argv/settings/spec/config/baseline digests, explicit overrides, model pins and remote log path. No private captured environment is retained in those receipts or command arguments. All SSH actions hold `log/100h_motion/board_session.lock`, shared with `current_viewer_session.py`. An existing lock is a refusal, never automatically removed; the local lock coordinates cooperating tools, so external board actors must remain quiescent.

Observation tails only bytes appended after its starting offset, checks identity/DMA ownership every second, rejects log rotation/truncation and retains raw chunks plus parsed `[display-perf]`, `[display-events]`, `[display-upload]`, `[infer-perf]` and `[tdm]` records in its JSON receipt. The verified monotonic interval is at least 120 seconds, at most 1800 seconds, with a default 16 MiB payload ceiling (maximum 64 MiB) and an additional 60-second action bound. Partial records at interval boundaries are excluded from the parsed summary. Explicit inference counts/timing in future `[infer-perf]` records are retained verbatim; cumulative `[tdm]` completion counters are clearly not exact inference FPS. Metric windows can straddle observation boundaries; do not divide cumulative counters by observation duration or interpret upload payload bytes as physical DDR bandwidth. Missing metrics remain missing evidence. Fresh log text may itself contain application data; keep receipts local for review.

Local tests cover malformed paths/hashes/overrides, invalid/unbound receipt identity, changed process starttime/executable hash, wrong PID refusal before close, occupied DMA refusal before launch, log truncation, and metric parsing without fabricated FPS. Actual remote lifecycle/readiness and the 120-second observation require later parent deployment validation; they have not been exercised on hardware here.
