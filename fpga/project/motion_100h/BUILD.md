# Isolated sequential 100H motion build

This directory contains extracted 192245 inputs. Only preparation/build metadata
is written by these scripts; RTL and vendor IP are never modified. The immutable
archived PDS is the source of work/project.pds. Relative ../source and ../ipcore
paths resolve within this stage. Old output/status/timestamp nodes are removed;
command configuration is retained. PDS operates on mutable work/flow.pds.

Prepare after integration files are ready (preparation can also precede them):

```powershell
$stage = 'C:\Users\NineSun\Desktop\ov56401\project\motion_100h'
& 'C:\Users\NineSun\anaconda3\python.exe' "$stage\prepare_project.py"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$stage\build.ps1" -Check
```

The three required motion modules use plain Verilog registration. The optional
motion_result_cdc.v is registered if present. Every registered file must exist
inside source/ipcore for readiness. Preparation verifies every IP byte against
baseline_manifest.json. The final baseline route/pin report comes from the
diagnostic baseline with provenance hashes, never archive previous_place_route.
Existing source/constraints FDC files must also retain their archived hashes;
unexpected constraint edits block readiness for separate review.

After parent review, launch in a visible/background terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$stage\build.ps1"
```

No vendor launch occurs during preparation/check. Execution refuses any active
PDS, implementation, timing, bitgen or JTAG process; no parallel override exists.
An exclusive build.lock prevents two launchers from owning this stage. If the
launcher is forcibly killed, inspect process ownership before removing its stale lock.
Compile/synthesize/dev_map run sequentially, followed by a resource review gate,
slack-prioritized routing and placement logic optimization with multi-corner hold repair,
pin and actual HSST/dedicated pad comparison,
full min_max slow/fast STA, and bitgen from the exact hashed routed ADF. Expect
33 minutes or more, excluding review; hold repair may extend this.

Each run stores source/IP copies, input hashes, mutable-flow-independent PDS,
stage logs, Tcl commands, mapped provenance, routed artifacts, physical proofs,
STA proof and final bit SHA. All input inventories/hashes are rechecked before
and after each vendor stage. status.json records progress and failure. Errors
print a traceback and return nonzero; the PowerShell wrapper propagates failure.

## Resource review gate

Actual prior maps establish the vendor read-first RAM primitive format. The
runner deliberately stops after mapping until a reviewer provides this run's
resource_review.json. Global BRAM totals are insufficient: four local CAM1–4
distinct histories must each retain 19200 x 8 bits of BRAM with old-data/read-first
behavior. Inspect synthesis reports and mapped primitives, hierarchy, port
connections, widths/depth partitions and WRITE_MODE configuration; do not infer
this from source code or unrelated DDR/FIFO RAM usage. Compare overall resource
fit with the baseline and verify exactly four local detector instances survive
synthesis, with no CAM5/6 history. Their reserved motion records are zero; all
six video channels remain active. Previous six-detector map evidence cannot
satisfy this four-camera scope gate.

Copy the hash/requirement fields from resource_requirements.json, add reviewer
and four histories. Each row must identify the logical history and its actual
mapped BRAM instances, depth=19200, width=8, mode="read_first", and evidence:

```json
{
  "instance": "actual camera detector/history hierarchy",
  "depth": 19200,
  "width": 8,
  "mode": "read_first",
  "bram_instances": ["actual mapped primitive hierarchy"],
  "evidence": [{
    "file": "../work/synthesize/actual_report_name",
    "sha256": "SHA256 of this exact report",
    "quote": "exact attributable report excerpt showing primitive/mode/geometry"
  }]
}
```

Evidence paths are relative to the run directory (work is ../work). Quotes and
hashes are checked; their interpretation is a named parent-agent review, not automatic
proof of primitive semantics. No review template is pre-approved. Resume only
this mapping checkpoint, before any place_route exists. The special PHY-parser
failure recovery path may reuse the exact archived route after hash comparison;
failed timing requires a new build with preserved prior artifacts:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$stage\build.ps1" `
  -Resume "$stage\run_YYYYMMDD_HHMMSS"
```

Changed inputs or map/synthesis hashes prohibit resume. Preserve failed work
for diagnosis; do not reuse stale outputs or bypass resource gates. Full STA
proves constrained paths only: integration CDC and external input exceptions
need review, especially broad asynchronous clock groups. This runner does not
program hardware or establish on-screen acceptance.
