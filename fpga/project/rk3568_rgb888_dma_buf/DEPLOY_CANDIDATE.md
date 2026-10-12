# Parent review: SRAM trial lifecycle

`deploy_candidate.py` is the single local entry point. By default, including with
`--deploy`, it validates local copied image/build/source identities and the reviewed
ARM64 module, then prints a plan. It performs no SSH, board query or JTAG call.
`deploy_remote_helper.py` is uploaded only on an explicitly executed deployment.
Nothing in these scripts overwrites a production executable, module file, source
snapshot or SPI flash.

Parent must review the viewer build receipt, flag names, model/MVP environment and
fullscreen arguments before supplying `--execute`. PID 5650 and ACTIVE hash
73613d525541939ea493a9bb87eeeae10879c4a08eede36a7ee298777fb32100 are prior
observations, rechecked against the exact process and sole device ownership at
execution. No live identity was rechecked while implementing this script.

Example local plan (placeholders must be filled from parent receipts):

```powershell
python deploy_candidate.py --deploy --viewer-remote /userdata/linaro/ov56401-rgb888-VIEWER_BUILD/detview --module-remote /userdata/linaro/ov56401-rgb888-driver_build_1791563854046563100/pango_zc.ko --viewer-sha256 FULL_VIEWER_SHA256 --baseline-owner-pid 5650 --feature-env EXACT_FEATURE_FLAG --verify --verify-env EXACT_VERIFY_FLAG --seconds 30
```

Add `--execute` only for a later authorized trial. Flag names are deliberately
required rather than guessed. Feature flag is set to `1`; `--verify` sets its
reviewed flag to `1`. The default candidate argv/cwd/environment reuse the captured
ACTIVE launch (including existing MVP/fullscreen selection). Use `--env-json` for
explicit model/MVP overrides and `--viewer-args-json` for a reviewed argument array.
Candidate scratch uses userdata TMPDIR. Remote candidate executable/module paths
must be isolated `/userdata/linaro/ov56401-*` paths, with matching hashes.

Deploy sequence:

1. Check local image copy receipt, successful original PDS/build/generation
   receipts, unchanged copied build inputs, passing timing, rollback image and
   candidate module SHA256. Check Windows has no PDS/PDS-shell/cdt_cfg conflict.
2. Recheck exact ACTIVE executable/PID/start time and sole real device owner.
   Capture its argv/env/cwd/user/groups/boot ID for restoration. Verify candidate
   remote hashes and candidate module vermagic/kernel release. Use a timestamp
   userdata directory with at least 128 MiB free;
   acquire an exclusive deployment lock. Copy the current staged original module
   to this directory, hash it and compare its srcversion with the loaded module.
   ELF srcversion/vermagic are extracted with `readelf -p .modinfo` under LC_ALL=C;
   no modinfo executable is required. Missing, empty or duplicate fields fail the
   gate. The original ELF srcversion must equal `/sys/module/pango_zc/srcversion`.
3. Query the X11 tree for exactly one `_NET_WM_PID` window matching the verified
   process. Send `q` KeyPress/KeyRelease through ctypes XSendEvent. Wait up to
   45 seconds for exit, no device owner and pango_zc module refcnt zero.
4. Unbind and remove `0002:21:00.0`, recheck retirement. Copy candidate image to
   the local timestamp evidence directory. Recheck PDS conflicts before invoking
   the copied JTAG helper, overriding TCL/LOG/JSLOG within that directory. TCL
   only assigns/programs SRAM. The helper may clear stale cdt_js only after this
   preflight; it never runs on the plan path.
5. With endpoint removed and no owner/refcount, unload original pango_zc; insert
   exact 8 MiB module; only then rescan. Allow probe's automatic bind or explicitly
   bind if absent. Do not rescan with the old module still available.
6. Launch the candidate under a small supervisor, with separate userdata logs.
   Record the actual child PID/start time/hash only after its exec, and require
   it to be the sole device owner. Preserve production binaries.

`--seconds 1..300` requests a bounded smoke: after that duration the same graceful
q/exit/retirement gates stop the candidate. It does **not** automatically restore
hardware. Use the resulting receipt explicitly:

```powershell
python deploy_candidate.py --restore deploy_TIMESTAMP/receipt.json
python deploy_candidate.py --restore deploy_TIMESTAMP/receipt.json --execute
```

Restore accepts only `candidate_running` or `smoke_stopped`, checks unchanged local
artifacts/helper, boot ID and exclusive lock ownership, then gracefully quits the
known candidate if still running. Candidate exit must be recorded as return code
zero, with no device owner and module refcnt zero. The driver's active token or
quarantine permanently pins the module; zero references rejects abandoned leases,
imports or mappings. This verifies the cooperative END/lifetime contract, not an
independent hardware NPU completion fence. The reviewed viewer must join workers,
wait synchronous inference completion and END each lease before normal exit.

After retirement, restore unbinds/removes PCI, unloads candidate, programs exact
rollback SRAM image, inserts the saved original module, then rescans/binds. It
verifies the captured ACTIVE executable is still exactly SHA73613..., relaunches
the unchanged binary with its captured argv/env/user/cwd, and records its real
device-owning PID. Only successful restoration releases the remote deployment
lock. ACTIVE environment is restored exactly.

Every phase is saved atomically in a local timestamp receipt. Treat receipts and
remote launch configs as private: they contain captured environment. On failure,
there is no SIGTERM/SIGKILL, unknown-owner stop or automatic universal rollback.
The process, removed endpoint or loaded module is left at the failing phase for
parent review. An uncertain consumer/lease/quarantine cannot pass automatic
restoration. A stale remote lock is intentionally retained; reconcile the receipt
and live state separately before clearing it. This script does not provide recovery
from arbitrary interrupted phases or a rebooted board.

Local validation: `python -m py_compile deploy_candidate.py deploy_remote_helper.py
test_deploy_candidate.py`, then `python test_deploy_candidate.py`. These tests mock
lifecycle mutations and prove local guards/order only, not X11, JTAG, module or
board behavior. No deployment was executed during implementation.
