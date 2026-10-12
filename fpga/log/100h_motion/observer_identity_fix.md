# Observer identity fix — local evidence

Changed only `project/tools/observe_motion_runtime.py` and
`project/tools/capture_motion_screen.py`, plus this requested evidence log.
No SSH connection, hardware mutation, RTL/PDS change, build, or build polling
was performed during implementation or verification. All remote operations in
the tests used in-memory mocks; credentials were neither printed nor recorded.

## Identity and observation behavior

Both tools use `pgrep -x 'camview|camview_motion_'`, matching the board-session
tool and Linux's truncated private-viewer comm. Selection requires exactly one
numeric PID. The shared validator records PID, `/proc/PID/stat` field 22
(starttime), and the exact `/proc/PID/exe` target. Stat parsing supports spaces
and parentheses in comm. It rejects deleted executable targets.

Baseline observation requires the executable recorded in
`log/100h_motion/viewer_launch_baseline.json`; the current baseline is
`/root/ov5640/camview_display_optimized/camview`. Baseline validation does not
require or read the candidate manifest. Other processes must match the exact
`binary` and running `/proc/PID/exe` SHA256 in `viewer_build.json`:

- Executable: `/userdata/linaro/100h_motion/viewer_eaf579139acf/camview_motion_private`
- SHA256: `dc9ca56440e3b10e2241ef52ad99e1e8fd8e692d0bebda27b9e20fcf88d2e5e9`

Stat/executable and viewer selection are reread around each validation to
reject changes during hashing or selection. Identity is compared before,
throughout, and after the bounded runtime observation, including after reading
the log. Same PID with a new starttime is rejected. The default duration remains
120 seconds, with at most 20-second sleeps and flushed checkpoint output, so
the existing external background-launch workflow remains available.

Existing JSON fields `before`, `after`, `metrics`, `logfile`,
`unstable_nonzero`, and `log` are preserved. `viewer_identity` is additive.
Labels, output names, and metric calculations remain compatible.

## Screenshot behavior

Previously the screenshot captured the root desktop without selecting a viewer.
It now selects exactly one viewable X11 client whose `_NET_WM_PID` matches the
verified viewer PID and captures that window with `xwd -id`. It checks process
identity and window selection after capture and after runtime evidence
collection, before saving. Existing PNG and `_runtime.txt` filenames remain;
the runtime text adds `viewer_identity` and `viewer_window` records. Both viewer
names appear in the runtime process listing, and log reads target the verified
PID. This deliberately changes image scope from the desktop to the viewer.

Live prerequisites (`xprop`, `xwininfo`, `xwd`, X11 client PID properties and
exactly one viewable viewer window) were not checked on hardware. Missing or
ambiguous window identity fails instead of publishing an unverified screenshot.
The checks establish identity at their checkpoints; they are not a claim of an
atomic snapshot of all Linux/X11 state.

## Executed local verification

Python `unittest` scripts ran from stdin with mocked remote commands and
temporary output directories. The first suite reported **14 tests PASS**:

1. Exact candidate executable and manifest hash accepted.
2. Recorded baseline accepted without reading the candidate manifest.
3. Zero, multiple, duplicate, and malformed PID selection rejected.
4. Wrong executable, legacy candidate `/camview`, wrong private path, and deleted executable rejected.
5. Wrong candidate hash rejected.
6. Same-PID restart (starttime change) rejected.
7. Same-PID executable change rejected.
8. Restart during candidate hashing rejected.
9. Additional viewer appearing during hashing rejected.
10. Candidate hash change at a subsequent checkpoint rejected.
11. Visible X11 window owned by the intended PID selected.
12. Wrong owner, hidden window, and multiple matching visible windows rejected.
13. Full observer `main()` with mocked clock completed the default 120 seconds
    in six 20-second sleeps, preserved all six existing JSON fields, produced
    the expected metric, recorded candidate identity, and closed the client.
14. Full screenshot `main()` decoded a mocked XWD into a PNG and recorded the
    exact candidate executable and selected window in runtime evidence.

The final failure-path suite reported **2 tests PASS**:

1. Restart during runtime observation causes `main()` to reject, closes its
   client, and publishes no observation JSON.
2. Restart during `xwd` capture causes screenshot `main()` to reject, closes its
   client, and publishes neither PNG nor runtime evidence.

Python AST parsing passed for both final files. Source SHA256 fingerprints:

```text
observe_motion_runtime.py b3884f5bfd539887a087e84b82ad29c58b30e984eebdbdf4ee75154e569d623c
capture_motion_screen.py aabf2272855bda3347ce1bb99b2fbf28428c4e8fab61e4d3cd82803d7d1e77dc
```
