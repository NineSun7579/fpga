# Independent 100H baseline SRAM rollback review

Owned implementation: `project/tools/rollback_100h_motion.py`; pure tests:
`project/tools/test_rollback_100h_motion.py`. Candidate programmer is unchanged.

The tool requires no candidate build/status/acceptance. It fixes the image to
`project/bitstream_six_recovery_20261002_192245/top.sbit` and requires SHA256
`c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a`.
It also checks the saved absolute image path and digest in
`project/motion_100h/baseline_manifest.json`, retaining the manifest hash in each
receipt. This is the baseline identity contract; historical programmer logs are
not substituted for fresh rollback evidence. The baseline is read only; execution
programs a verified copy in its unique run directory.

The shared `program_100h_motion.py` SRAM renderer, parser and owned-process runner
are reused. A private function globals mapping gives that same runner stricter
rollback render/parser functions without changing the candidate module globals.
Both scans require exactly one PG2L100H and one DONE record. Initial DONE must be
asserted before assignment/programming; final DONE and explicit program-success
records must be present in freshly flushed logs. Missing or contradictory evidence
blocks success. SRAM only; flash is untouched.

Execution holds the existing `motion_board_session.Operation` lock, then uses
`board_host.ssh_connect` and existing read-only `Remote.owners/Remote.viewers`
checks. An absent device, query error, DMA owner or viewer blocks launch. No remote
quiesce action or SSH configuration change is performed. The board must first be
quiesced through the authorized existing lifecycle workflow. The lock serializes
cooperating lifecycle operations; independent external processes must also remain
quiesced during rollback.

The shared runner checks Windows/vendor availability, rejects active vendor jobs
(including PDS/PnR), and checks port 65426 before launch. Each execution has a new
cwd, cfg.log/server.log/client.log and receipt; there is no reuse of prior logs.
Cleanup uses only its Popen-owned PIDs and WM_CLOSE/owned-PID termination, with
the shared runner's unresolved-GUI behavior preserved. No broad kills occur.
Retained files receive SHA256 identities in the final rollback receipt.

Commands from `C:\Users\NineSun\Desktop\ov56401`:

```powershell
python -m unittest discover -s project/tools -p test_rollback_100h_motion.py -v
python project/tools/rollback_100h_motion.py --check
# Only after board quiesce and all vendor jobs/PnR have stopped:
python project/tools/rollback_100h_motion.py --execute --timeout 300
```

Validation: eight pure/mock tests passed, including actual baseline hash,
wrong hash, wrong manifest path, wrong chain target, initial DONE deasserted,
final DONE deasserted/absent, missing final scan, pre-DONE Tcl ordering,
unique check receipts, forbidden process/socket/board access during check,
active-owner rejection before runner invocation, and private runner isolation.
No hardware execution or vendor launch was performed.

Actual `--check` receipt:
`log/100h_motion/rollback/run_20261003_231755_4913a638711c456e95573d3b65e95254/receipt.json`
reported `validated_only`, exact baseline digest, manifest SHA256
`fba2fc58e7f2f4a46ef0b14c6029225904434b39163dc7d7b168b798cf954f5f`.
`validated_only` establishes local identity/rendering, not board rollback success
or runtime camera/PCIe acceptance. Execution has not been tested on hardware.
