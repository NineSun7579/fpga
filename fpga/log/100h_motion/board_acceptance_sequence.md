# Four-camera board acceptance sequence

Scope: CAM1–4 motion detection on this 100H board. All six video channels remain
visible. CAM5/6 motion slots are reserved zero. This is an execution checklist;
none of the future steps below is evidence that programming has happened.

1. Require completed build status, the exact candidate bit, matching route,
   mapped RAM, pin/PHY, input and full STA proof hashes. Run
   `program_100h_motion.py --bit <candidate> --build-status
   project/motion_100h/status.json --check` before disturbing the board.
2. Revalidate the current detview with `current_viewer_session.py --preflight`.
   Use `--stop` for its exact PID/starttime/hash/window; retain the stop receipt.
3. Run `motion_board_session.py quiesce` after graceful detview exit. This unloads
   the DMA module and removes the endpoint, with no active device owner.
4. Program the same bit with `program_100h_motion.py --bit <candidate>
   --build-status project/motion_100h/status.json --mode sram`. Require a single
   PG2L100H both before and after programming, successful operation and DONE=1.
   Preserve vendor logs and final receipt. Flash persistence is not required.
5. Run `motion_board_session.py reconnect --identity-json
   log/100h_motion/board_identity.json`; require the original 0755:0755 endpoint,
   pango driver and DMA character node.
6. Run `motion_board_session.py start` using the verified four-camera
   `viewer_build.json` and retained camview launch environment. Confirm one DMA
   owner, magic/geometry/config probes and only CAM1–4 motion polling.
7. Capture candidate screen using `capture_motion_screen.py motion_four_live`.
   Inspect all six panes and compare with saved pre-candidate screenshots.
8. Run `observe_motion_runtime.py motion_four_live --seconds 120`, then
   `audit_motion_runtime.py log/100h_motion/motion_four_live_observation.json`.
   Require four advancing valid motion records, bitmap/count/bbox consistency,
   at least one valid moving region, six advancing video streams, no unstable
   reads, and stable process identity. Review display metrics and Xorg timeouts.
9. If switching back to detview after acceptance, first stop the candidate with
   the board-session helper and reconnect, then restore detview using its exact
   stop receipt with `current_viewer_session.py --restore --stop-receipt <path>`.
   On a candidate hardware failure, restore the verified baseline SRAM bit
   before restoring the saved viewer; keep all failure logs.

Completion requires actual receipts, screenshots and runtime evidence for
these steps, plus the four-camera simulations and final timing closure.
