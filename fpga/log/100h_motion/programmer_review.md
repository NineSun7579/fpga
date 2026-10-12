# Programmer compatibility review

Read-only review of `project/tools/program_100h_motion.py`; no vendor executable launched, hardware accessed, process queried/stopped, or parent build polled. Only this note was created. Reviewed script SHA256: `01ad31ddc7cc3a1a04a78575d5760fab0052f36c11c683f1ac10b697c4dcbf88` (parent may subsequently change it).

## Readiness

Historical SRAM parsing and the Tcl scan guard are compatible with the retained single-PG2L100H logs. Flash automation needs the completion-order fix below before use. Real vendor execution of the new multiline Tcl wrapper and in-process cfg.log flush is not established by historical flat-command scripts; local Tcl evaluation establishes syntax/CRLF compatibility only.

## Confirmed bug: flash can report success before its final scan (high)

At lines 198–204, flash stage matches search the whole log and `rfind('Executing : cfg_scan_chain\n')` can refer to the initial scan. Once verify completes, every stage becomes true using the initial DONE=1, although the generated script's final `cfg_scan_chain` has not started. Lines 292–294 can then send WM_CLOSE while the final operation remains pending or active.

Reproduction using the actual retained `log/cfg.log` (40 lines): it ends with `cfg_jtag_flash_verify ... successfully.`, contains only one initial scan, and `parse_log(text, 'flash')` returns every stage true and no errors. `log/100h_spi_program_verify.log` (34 lines) reproduces the same result. The old `project/flash_100h_spi_verified_20261003.tcl` intentionally has no trailing scan, so historical success does not prove the new script's last operation completed.

Suggested fix: find the exact verify completion, then require a distinct scan start strictly after it, its matching successful completion, and exactly one PG2L100H / exactly one DONE=1 in that scan block. Require ordered stage completions for device index 0. Prefer an unambiguous end-of-script completion marker after all commands before sending WM_CLOSE. No success or GUI close should occur on initial-scan + verify-only input.

Related confirmed gap: appending a completed `PG2L50H`, DONE=1 scan to the historical log still returns all stages true: `target_single` checks only the first scan. Appending PG2L100H DONE=0 correctly returns device_done=false. The final scan must bind target identity as well as DONE.

## Confirmed cleanup behavior: timeout can terminate active programming (high for flash)

Lines 299–308 call `stop_owned(client)` when stages are incomplete. Lines 239–245 send WM_CLOSE and, after 10 seconds, terminate the owned PID. If a flash erase/program/verify exceeds `--timeout`, this interrupts an active hardware operation; receipt status becomes merely `blocked`. PID ownership prevents collateral process termination but does not make interrupting flash programming safe. Historical `finish_normal_023911.py:88` explicitly leaves an active programming PID untouched on timeout.

Suggested fix: after programming starts, timeout/error should retain the client and its server for inspection, record their PIDs and the last observed operation, and mark the operation outcome unknown. Restrict termination to proven pre-program failures or a separately authorized recovery. Ensure the unconditional server cleanup does not disconnect a retained active client. Distinguish evidence-gate rejection (no hardware operation) from uncertain/partial execution, so a blocked receipt cannot invite an automatic retry.

## GUI exit and final diagnostics

The success path uses normal WM_CLOSE and requires returncode=0, with no forced client termination after complete stages. This matches recorded historical 50K evidence: `log/50k_fps40_handoff.json`, `50k_fps_guard_handoff.json`, `six_margin_20261003_033106_handoff.json`, and `six_normal_023911_handoff.json` each record `cfg_exit_code: 0`; their helper calls CloseMainWindow, waits up to ten seconds, and leaves a stuck success window open. No retained 100H exit-code receipt was located, so zero exit after WM_CLOSE for this exact new wrapper remains unverified, not a demonstrated bug.

Lines 285–294 inspect error logs before WM_CLOSE, then accept success without rereading logs after exit. A trailing Tcl/client diagnostic produced during shutdown can escape `stage_errors` if the GUI exits zero. Suggested fix: after normal client exit, read all logs again, rerun ordered completion/error gates, and retain both client and server exit codes. Treat socket-disconnect messages produced solely by normal shutdown separately only if historical evidence justifies that classification; do not broadly suppress vendor errors.

## Historical format and baseline evidence

- `log/six_jtag_verified_flash.log:12–23` records a single PG2L100H, `cfg_assign_file` of `project/bitstream_six_recovery_20261002_192245/top.sbit`, `The done bit is 1`, `COMMAND[Program] execute successfully`, and exact `cfg_program -device_index 0 successfully.`. The current SRAM parser returns all four stages true with no errors.
- Independently computed retained top.sbit SHA256: `c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a`, exactly the script's BASELINE_SHA256. Historical log binds the path; it does not contain a contemporaneous bit hash or prove the board's current state. This review establishes retained-file identity and historical programming success only.
- `log/cfg.log:18–40` is the documented primary log with header identifying PDS 2022.2-SP6.4 build 146967. It confirms unindented `PG2L100H`, `This device configure situation (done bit): 1`, exact command markers, and 1MHz flash command syntax. Erase/program inner messages say `execute finish`; outer `Executing ... successfully.` lines are the useful gates. Timings were erase 20.3s, program 89.7s, verify 31.5s, within default 300s.
- Raw successful logs use CRLF plus bare carriage returns for progress. Python CRLF normalization works. Evaluating the exact `scan_guard` in an in-memory standard Tcl interpreter with cfg_scan_chain stubbed and the existing primary log opened read-only passes, including its Tcl regexp and text-channel newline conversion.
- `project/log/cfg.log` contains a different target and is rejected by the current SRAM target_single gate. Primary and stdout logs duplicate evidence; do not concatenate them for device counting.
- `log/100h_flash_server.log` includes real `E: JtagServer-0336` flash-id/frequency errors and socket errors. The script's ERROR regexp catches them. Use unique fresh logs as the script does; never reuse those failed-session logs as success evidence.

## Unproven assumptions and smaller operational issues

1. Successful historical TCL files are flat cfg command lists. They do not demonstrate that cdt_cfg's `-file` reader supports one multiline `if {[catch {...}] ...}` evaluation, flushes `cwd/log/cfg.log` before returning cfg_scan_chain, or logs nested cfg commands identically. The wrapper fails closed if the primary log is absent/unflushed, but that can block every otherwise valid run. Vendor runner compatibility remains a focused execution uncertainty; no vendor test was permitted here. If vendor logs echo the entire wrapper including the literal MOTION_GUARD text, the broad ERROR matcher may also reject a successful session; this is conditional, not observed.
2. `rollback_command` contains no working-directory instruction. Its Tcl guard reads the unique run's `log/cfg.log`, while the vendor writes its primary log relative to cwd. A manual invocation from another directory can read a missing/stale log. Record required cwd, create a fresh rollback log/session, and bind the rollback guard to that fresh log. `--check` creates no log subdirectory, so its rollback command is not directly executable as supplied.
3. Exact bit, route, STA and resource provenance gates are present. This review did not evaluate them against the active parent build or change them. The immutable copied programming input and single-target pre-write guard are useful safeguards, subject to the vendor runner/flush uncertainty above.

## Local verification performed

Imported script with Python `-B` (no bytecode writes), hashed retained baseline/script, replayed actual successful/other-target logs through parse_log, evaluated scan_guard against the existing primary log using standard Tcl with a no-op cfg_scan_chain, and replayed synthetic final-scan DONE=0 / wrong-target variants in memory. No test files, vendor sessions, or hardware changes were created.
