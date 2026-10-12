# Isolated whole-design cooperative candidate

The candidate top is `rtl/fpga_v8_cooperative_top.v`; its PDS is `project.pds`.
Both are new files under this directory. The top comes from the complete frozen
motion build at `motion_100h/run_20261003_212303/inputs`, with top SHA-256
`ba90f96605423210f9563990a470e0d9585529c4f7edcda1c086bf3fae3c45b2`.
The production top (`dca00ca2...`) was not used as the source base.

The builder verifies and independently copies all **694 frozen input files**,
including generated IP and constraints, plus **12 isolated component files**.
Copied inputs/components are read-only and hash-guarded on subsequent runs.
Historical provenance files outside `inputs` account for eight additional
entries in the original 702-entry manifest; these are listed explicitly in the
build manifest. Every registered candidate PDS path resolves inside this
directory. IP IDF paths also resolve locally; no IP generation is performed.

```powershell
python project/fpga_v8_migration/whole_candidate/build_candidate.py
python project/fpga_v8_migration/whole_candidate/audit_candidate.py
```

The builder refuses a different frozen baseline or changed immutable component
copy. A component owner changing its API requires an explicit new reviewed
binding; rerunning does not silently overwrite the captured component snapshot.

The candidate connects the actual physical cam5 SFP output
`cam5_pix/de/hs/vs` into `fpga_v8_capture_ov5640_ddr`. This is the downstream
RGB565 stream, with no local FIR/KF filter on that branch. No claim is made about
the upstream 50K FPGA certificate, bitstream, or upstream processing. The fixed
capture layout is 640x480 RGB565, 614400 bytes, banks `0x01800000` and
`0x01a00000`, camera identity 4. The original cam5 `axi_dma_write` remains
byte-identical, including its frame/tag command path, 16-beat bursts, and
original 4-bit ID `0011`. The legacy ACK remains the baseline `2'b00` and is
independent of ownership.

All five other physical capture paths, all six camera DMA write instances,
all four local motion taps, motion records, and motion register routing are
preserved. The motion page stays at `0x20000800..0x200008ff` on M01. Every
motion source and constraint is copied without byte changes. `axi_clk` remains
`core_clk`; `axi_rst` remains `~ddr_init_done`; all new interfaces share that
clock/reset.

The cooperative core replaces the six-camera write arbiter and packs all six
original AW/W/B interfaces in slot order CAM1 through CAM6. Its seventh writer
is the RGB888 conversion output at `0x08000000` / `0x08200000`, each reserving
2 MiB. The mixed original AWLEN widths are handled explicitly: cam3/cam4 are
already 8 bits, and the other four camera fields are zero-extended from 4 bits.
The cooperative read master uses legacy S02 (`npu_s0`) with the original 4-bit
ID; the 8-bit cooperative LEN is checked before its 4-bit legacy connection.
Its current RAW bridge always requests a single 128-bit beat. S00 PCIe and S05
KF connections remain intact. The frozen cam1 KF enable parameters are zero;
the retained KF implementation uses 8-beat reads if activated in a later scope.

The old write FIFO/B response fabrication and the entire old read FIFO/SID
reconstruction are removed from this top. `fpga_v8_ddr_adapter` connects the
actual generated 16-word FIFOs and vendor DDR3 AW/W/AR/R signals. It stages
every accepted write burst, observes vendor WID/WLAST, preserves original
4-bit camera write IDs, and retains the full 7-bit crossbar read route until
the final R response is consumed. M00 addresses/LEN reach its checks at full
32/8-bit width. Supported DDR transactions are aligned 128-bit INCR bursts of
at most 16 beats below the 256 MiB exclusive end. Unsupported DDR requests
set diagnostics and remain unaccepted; host configuration must avoid them.

M02 was entirely response-tied-off in the frozen motion top. Its original
`0x40000000` decode with 29 address bits is preserved. The AXI128 endpoint
receives the entire M02 request stream and reserves exactly
`0x40010000..0x40010fff`. It returns error responses for requests outside its
window. M02 now has explicit full 7-bit AW/B/AR/R IDs and 8-bit AW/AR LEN,
including previously implicit request signals. A local 32-bit register at
offset `x` occupies one 16-byte physical DMA slot at `0x40010000 + 4*x`.
The AXI-Lite router sends local `0x000..0x0ff` to cooperative control and
the capture page at local `0x100..0x17f` to capture control. Config generation,
arm results, host descriptor/claim/release, capture bank states, protocol
faults, and counters connect directly to the capture manager. No external
top-level port is added.

`HOST_REQUIRED=1` is explicit. Capture starts disarmed. Host policy must reserve
the output allocations, constrain all writable CAM1-4 bank addresses, allocate
a fresh nonzero never-reused generation across resets, claim each host RAW
descriptor, drain all reads, and release the matching identity. Cooperative
and host obligations both hold the RAW bank. Default camera/output ranges are
disjoint; runtime exclusivity has not been established.

The structural audit passes all new named-port/width checks and finds no new
duplicate modules, implicit interface nets, or multiple interface drivers.
All **112 historical PRR pads** remain in the unchanged RTL header and copied
constraints; another **14 HSST serial pins** are separately represented in
that header (126 total bits). This is source/constraint preservation, not a new
post-route pin report. The registered vendor IP list inherits **11 duplicate
module definitions** from the frozen PDS. They are recorded with hashes;
PDS accepted the inherited registrations in the isolated compile without IP edits.
Reachability is a byte-based source graph; conditional branches and encrypted
vendor modules require later compiler/elaboration verification.

Capture-endpoint completion was received: its receipt reports **499 operations /
4288 events PASS**, and final source hashes match both immutable candidate copies.
The fresh structural audit still passes **436 interface-width checks**.
PDS **Compile and Synthesize both passed (exit 0)** on **PG2L100H-6FBG484** in
`compile_01/attempt_02`, with the top explicitly recognized as
`fpga_v8_cooperative_top`. All 12 cooperative modules were elaborated.

The initial `compile_01` attempt stopped at project parsing (Flow-0130): fresh
source registrations lacked mandatory `_timespec` fields. The generator now
includes them. The failed project/log/receipts remain intact; the retry used a
fresh nested work directory, with all sources/IP/constraints inside this candidate.
Only the new run project's PDS autoformat is allowed and preserved before/after.
No historical run directory was cleaned and no PDS process was killed.

The synthesis `.snr` reports:

| Resource | Used | Available | Utilization |
| --- | ---: | ---: | ---: |
| LUTs | 29733 | 66600 | 44.64% |
| Registers | 30889 | 133200 | 23.19% |
| DRM (36K equivalents) | 72.5 | 155 | 46.77% |
| APMs | 0 | 240 | 0% |
| Tool I/O ports | 114 | 285 | 40% |

These are synthesis counts, not post-route fit or hardware acceptance. The tool
I/O count differs from the unchanged 126-bit RTL header; the pin audit preserves
112 historical PRR pads and 14 HSST bits and does not claim a new routed pin report.
All active `get_ports` queries in the frozen constraints resolve to the candidate.

`core_clk = ddrphy_sysclk`, and `axi_clk = core_clk`. Frozen RTL/constraints give
**25 MHz * 84 / 16 = 131.25 MHz**, period 7.619 ns. Synthesis estimates
137.9492 MHz and **+0.370 ns setup slack** for this clock. Slow-corner hold remains
**-0.004 ns**, total -0.040 ns at 10 endpoints. The report explicitly says
`Design Summary : Some Constraints Violated.` No clock or constraint was changed.

Exact warnings are saved in `compile_01/attempt_02/evidence/`: 2294 compile and
9562 synthesis warning lines, including vendor/legacy diagnostics, constant-probe
loops and nine I/O-constraint warnings also present in the frozen synthesis log.
All candidate-top warnings match frozen compile warnings after normalizing paths,
line numbers and the top rename. The endpoint warning repeats in both stages:
`Verilog-2021: Net eligible.addr_end_1 ... does not have a driver, tie it to 0`.
It remains **unaccepted**, pending the parent's mapped ModelSim eligibility check.
The 31-net structural output list includes legacy crossbar consumers, debug aliases,
assertions and retained internal diagnostics; it is not 31 missing connections.

The original `pcie_fifo.v` remains preserved, and its writer completion/host
retirement contract is **unproven**, pending the parent's new candidate. Whole
mapped simulation, place/route, timing closure, board load and host RAW/output
comparison remain outstanding. This is a **preliminary, unaccepted candidate**.
No SSH, board tools, production/IP/PDS writes or component-synthesis writes were
performed. No FPGA FPS or hardware acceptance is claimed.

Commands executed for the successful fresh attempt (completed runs cannot be
overwritten by the guarded runner):

```powershell
python project/fpga_v8_migration/whole_candidate/run_pds.py prepare attempt_02
python project/fpga_v8_migration/whole_candidate/run_pds.py compile attempt_02
python project/fpga_v8_migration/whole_candidate/run_pds.py synthesize attempt_02
python project/fpga_v8_migration/whole_candidate/summarize_pds.py attempt_02
python project/fpga_v8_migration/whole_candidate/audit_candidate.py
python project/fpga_v8_migration/whole_candidate/finalize_evidence.py
```

Evidence is in `artifacts/`: build/input/component hash manifests,
replayable byte edits and ASCII review diff, connection manifest, interface
width audit, structural/pin audit, address/burst audit, IDF path audit, and
production/IP/PDS hashes before/after/final. `artifacts/pds_evidence.json` contains
stage returns, exact warning references, resource/STA extraction, source binding,
pin checks and remaining gates. Tasklist snapshots, run-project autoformat copies,
and 1404 source/frozen plus 1091 external protected hashes are retained in the run.
`artifacts/final_verification.json` records the final audit, and
`artifacts/all_candidate_final_sha256.json` hashes the complete candidate tree,
including run outputs, except that hash manifest itself.
