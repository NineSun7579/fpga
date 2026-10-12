# Staged physical DDR address correction

This directory contains the tested `fpga_v8_raw_frame_axi_physical` module.
The original `../fpga_v8_raw_frame_axi.v`, original testbenches/runner, and
shared preprocessing sources are unchanged. Another agent is synthesizing
the original hash, so this correction is staged for promotion by the parent
after that run finishes. No PDS or agent status is polled here.

Live `project/source/top.v:626` forwards only
`ddr_axi_awaddr[27:0]`, and line 647 forwards only `ddr_axi_araddr[27:0]` to
DDR. Despite a 512 MiB crossbar decode, only 256 MiB of byte addresses reach
the physical adapter without aliases. `0x10001000` becomes `0x00001000`.

The corrected RTL adds:

```verilog
parameter [31:0] DDR_ADDRESS_LIMIT = 32'h10000000
```

The parameter must be nonzero, 16-byte aligned, and at most `0x10000000`.
A `0x20000000` override is invalid on this board. Wide source/destination
base-plus-rounded-footprint arithmetic rejects any end above the configured
limit, along with existing alignment, overlap, geometry, and wrap checks.
Ending exactly at the limit is legal. Invalid parameters reject all commands.
Rejection produces a one-cycle `cmd_error`, sticky `error`, no `busy`/`done`,
no AXI traffic, and no completed-ID update. There is no added error-code port.

All serializer, pipeline, AXI handshake, response drain, strobe, and retirement
logic is otherwise identical to the original. The staged module instantiates
the shared letterbox and packer from their original paths, read-only. Publish
only on `done && !error`; reset while AXI is outstanding still requires common
bridge/interconnect/slave reset.

Run from this directory:

```powershell
& 'C:/Users/NineSun/anaconda3/python.exe' run_tests.py
& 'C:/Users/NineSun/anaconda3/python.exe' validate_promotion.py
```

The first command tests this staged module with independent Python golden
bytes, complete small/error/reset/stall coverage, physical-limit boundaries,
invalid limit configurations, a legal smaller limit (`0x02000000`), and the
full 640x480 baseline. It reuses only golden-byte/helper functions from the
original runner; it compiles the staged uniquely named DUT and testbenches.
Its libraries, transcripts, vectors, dumps, and machine report are isolated
under this directory's `artifacts/`. The original/shared files are hashed
before and after the run. The second command validates the promotion patch
entirely in memory and compares its three proposed Verilog files with these
tested copies after restoring original module names and pass markers.

`REPORT.md` records current results. The frozen original bridge hash is:

```text
235f878ac7a35134f2ce9f8b9b56fecf66d033387715c46e953fa0a907df5b40
```

## Promotion handoff

1. The parent confirms the concurrent synthesis has finished. This task does
   not establish that condition and deliberately leaves the original frozen.
2. Run `validate_promotion.py` and check the frozen hash above. If originals
   changed meanwhile, reconcile the patch against the tested staged files.
3. Read `PROMOTE.patch` and apply its contents using `functions.patch`. It
   targets only the original bridge, original two testbenches, and original
   runner inside `cooperative_axi`. Do not rename/copy the physical module
   into board source or edit shared preprocessing files.
4. Run `../run_tests.py` from `cooperative_axi` to exercise the promoted
   original module name. The promoted suite expects 49 retired frames,
   1,231,008 compared bytes, 45 rejected address commands, and eight rejected
   parameter configurations.
5. Rerun isolated PDS synthesis for the promoted bridge hash. The original
   PDS run cannot validate changed address/configuration logic. Replace any
   old synthesis result used by integration with this new result.
6. Update parent documentation's staging note only after promotion and checks
   finish; retain this report's provenance as validation of the staged copy.

The patch was validated without applying it. Expected promoted bridge hash:

```text
c2bdc1a3622fa0c84fc487a9859ba27220ddad4c5d304bc4221157906c47bc6f
```

Original-name promotion and its PDS rerun remain the parent agent's work.
