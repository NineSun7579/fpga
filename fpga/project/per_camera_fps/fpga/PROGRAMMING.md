# SRAM handoff for CAM3/4 VTS 843

`prepare_program_evidence.py` assembles completed recovery artifacts into a new
`deploy_evidence_*` directory. It never starts PDS or connects to hardware. Its
only subprocess is the unchanged `program_100h_motion.py --mode sram --check`.
The programmer's existing gates remain intact. `status.json` complete means
artifact/build validation complete; hardware programming and runtime acceptance
remain pending. No acceptance record or SRAM success receipt is generated.

Prepared run: `deploy_evidence_c0l0p_o6`. Bit SHA256:
`a323d6dfad78aff2a4da975bad7c317dc7f6755d56c6a667c08c694893222a3d`.
The check returned `validated_only`, `check_only: true`, empty stages and errors.
Full stdout is retained in `readiness_check.stdout.txt`; its receipt is
`checks/run_20261004_152603_31144772/receipt.json`.

Verification uses the inherited direct pin, PHY, timing and resource validators,
the actual candidate source/input manifest, protected parent hashes, reused
map/synthesis/PCF hashes, successful exact-input vendor logs and Tcl, and exact
bitgen-output hash equality. Timing has 126 passing rows across all ten
check/corner sections; the entire report was scanned with zero violated paths.
Route SHA256 is `b644efa55771d54936c640c26f47d21fbfb117fa3b05f9e86aa88235358fb19c`;
report SHA256 is `23807659d378edc39825cd02072d20aca1b3c0ca46558122a6eabb0e1012b5d8`.
Timing proves constrained paths; existing external-input/CDC exceptions remain.

The RAM proof attributes four logical 19200 x 8 read-first histories to CAM1–4,
eight 32K x 1 READ_BEFORE_WRITE DRM banks per instance, and all 32 physical
routed banks. Hash-bound synthesis excerpts, copied RTL, map and routed export
are retained. The named review is explicitly automated artifact verification of
the parent-reviewed recovery; it does not impersonate a human runtime reviewer.
There are no CAM5/6 detector histories. The candidate differs from the deployed
motion baseline only in CAM3/4 VTS 984 -> 843; all six video channels and the
existing motion ABI are retained. Input/route/report/bit files are byte copies,
not links. `original/` retains the original recovery evidence unchanged.
`assembly_provenance.json` records every copied source path and hash.

To assemble another new isolated package, from the workspace root:

```powershell
& 'C:\Users\NineSun\anaconda3\python.exe' -B 'project\per_camera_fps\fpga\prepare_program_evidence.py'
```

Parent-owned hardware sequence: save the current viewer executable hash, PID,
starttime, window, launch environment and log. Close only that verified window
normally and wait for the process and DMA ownership to end. An unresponsive or
mismatched viewer blocks programming; do not force-kill processes. Quiesce PCIe
through the existing guarded workflow: no viewer or DMA owner, unload
`pango_pci_driver`, remove the expected endpoint, then program SRAM. Do not reuse
old viewer PID/window identities. `motion_board_session.py quiesce` was written
for its saved motion viewer baseline; the current detview needs the parent's
current identity-aware close workflow before applying the same PCIe guard.

Run this local check again immediately before the parent-owned SRAM operation:

```powershell
$py = 'C:\Users\NineSun\anaconda3\python.exe'
$root = 'C:\Users\NineSun\Desktop\ov56401'
$run = "$root\project\per_camera_fps\fpga\deploy_evidence_c0l0p_o6"
& $py "$root\project\tools\program_100h_motion.py" --mode sram --check --bit "$run\top.sbit" --build-status "$run\status.json" --log-dir "$run\checks"
```

After normal viewer shutdown and the PCIe guard, the exact programming command
is the following. It was **not executed** during evidence preparation:

```powershell
& $py "$root\project\tools\program_100h_motion.py" --mode sram --bit "$run\top.sbit" --build-status "$run\status.json" --log-dir "$run\program"
```

The programmer checks idle vendor processes, cable-port availability, a single
PG2L100H, programming success and final DONE. Retain its new receipt/logs and
require `status: success` before reconnecting. Flash remains untouched.

Reconnect uses the existing identity guard, rescan, driver loading and endpoint
binding validation. The previously established identity is BDF `0002:21:00.0`,
vendor/device `0x0755/0x0755`, driver `pango_pci_driver`, node
`/dev/pango_pci_driver`, decimal device number `511:0`; compare with the parent's
fresh pre-program identity. The existing guarded reconnect command is:

```powershell
& $py "$root\project\tools\motion_board_session.py" reconnect --identity-json "$root\log\100h_motion\board_identity.json"
```

It refuses viewer/DMA ownership, verifies PCI identity before loading the module,
and requires the expected driver and character node. A missing binding fails
closed; inspect the endpoint and driver rather than using a blind bind. Restore
the parent's saved current viewer/settings only after successful reconnect;
the old motion viewer `restore` default is not the current detview baseline.
Observe all six live channels, CAM3/4 rate change and errors, and CAM1–4 valid
advancing motion records with bitmap/count/bbox consistency. Motion registers
use independent 16-byte DMA transactions in one DMA lock, low 32-bit words;
CAM5/6 records remain reserved zero. Retain runtime evidence separately.

For SRAM recovery, keep both the deployed motion baseline
`project/motion_100h/run_20261003_212303/top.sbit` (SHA256
`e3da6e1fbc7d0bb2abcc2ee57342906e395fb74cecd1f3163e9ada33e89e96f7`) and
the programmer's retained six-video rollback baseline (SHA256
`c3f07533e37e77ab734d37a5a4ba4ed8ebc8af0841e09fa43f2dcc076f16a44a`).
The rendered rollback Tcl targets the latter. Recovery is parent-owned and
requires the same normal viewer close, PCIe quiescence, idle/single-target/DONE
checks, guarded reconnect and saved viewer restoration. No automatic rollback
or Flash operation is part of this package.
