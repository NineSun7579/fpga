Prepared isolated 100H mode-0 diagnostics; no PDS or JTAG launched.

Run only after the active 50K color-bar flow and its vendor child processes finish.
Visible terminal (from any directory):

    powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File "C:\Users\NineSun\Desktop\ov56401\project\sfp_100h_diag_mode0\build.ps1"

Read-only readiness check:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\NineSun\Desktop\ov56401\project\sfp_100h_diag_mode0\build.ps1" -Check

The runner rejects any active pds/pds_shell/pnr/ta/bitgen process. No parallel
override exists. Expect 20+ minutes; historical full flows can take 33 minutes
or longer, and strong hold repair can extend this substantially.

Actual successful runner: ../tools/build_six_recovery.ps1. The 192245 run used
../project_build/project.pds, NOT ../project.pds (absent), and NOT the existing
../project/project.pds. Its command was pds_shell -project <absolute PDS>
-run pnr -work_dir <absolute work directory>. This private runner uses the same
project arguments for compile/synthesize/dev_map, then explicit strong pnr,
full min_max multi-corner STA, dedicated CDC STA, and bitgen from the EXACT
STA-proven top_pnr.adf. All runtime outputs and logs stay here. work/project.pds
is immutable; PDS may update work/flow.pds only. Runtime metadata was removed
from the copied PDS before use. All registered input/IP references resolve
inside this directory. Source and vendor IP are ordinary byte copies, NOT
hardlinks, junctions or shared writable metadata. Vendor IP is never patched.

source/top.v defaults SFP_NEW_PARSER=0. Only candidate top/link/prep and the
two new .sv modules replace copied production inputs. The existing decoder,
splitter, FIFOs, pins, reset logic, generated clocks and uncertainty values are
preserved. Regression copies live under sim/; no candidate-author files are
changed. Original and private source/IP/PDS hashes are checked before and after
every vendor stage. The readiness manifest excludes mutable regression logs.

CDC rationale: source captures all 512 bits into held and toggles ack on the
same RX edge; held stays stable until the next request returns. Host captures
held into data_sync0, then data_sync1, synchronizes ack through two stages, and
accepts data_sync1 on the following equality edge. This gives a full destination
cycle of margin when held's physical delay is bounded below one host cycle.
The isolated clock.fdc replaces original singleton async groups with equivalent
pairwise exclusions, except sfp_fabric versus ddrphy_sysclk. top.v assigns
axi_clk=core_clk, and DDR3 drives core_clk from its 7.619 ns system clock.
Leaving those
groups intact would override a data max-delay and silently mask this CDC.
Other declared clocks, including generated SCCB clocks, retain original
asynchronous separation. Only request/ack first-stage crossings are explicitly
false-pathed. Held-to-data_sync0 has max_delay 4 ns datapath-only and min_delay
0 ns; all second stages and host/RX local paths remain timed. Uncertainty is
unchanged. No blanket FIFO hierarchy false path is added.

Exposing RX/host also exposes existing crossings between those domains. They
remain timed deliberately: a legacy CDC violation blocks bitgen until its exact
endpoint is reviewed. Do not restore broad clock groups or relax uncertainty to
make this pass. The 4 ns bound and selector syntax are proposed physical
constraints, not a PDS-validated result: the requested no-launch preparation
cannot establish mapped object resolution, support for datapath-only, actual
route delay, resource fit, or final STA. The runner fails closed on vendor errors,
empty selectors, violations, missing clock summaries or inadequate CDC coverage.
The dedicated report must show >=481 distinct mode-0 data_sync0 endpoints
(15 full counter words plus link), up to 512; signature/reset bits can merge.
Actual synthesis may require reviewing these mapped names/coverage before the
strict gate can pass. No timing-fit or full-top elaboration claim is made.

Physical audit: baseline/top_prr.prt and top_pnr.adf were copied from the final
project_build route retained after 192245 (timestamp ~19:42), with SHA256.
The archive's previous_place_route is an OLDER run and is not used as baseline.
Pin audit compares all 112 routed port/ball/site/bank/direction/constraint rows
and every active source-FDC port PAP_IO_LOC/PAP_LOC assignment, rejecting
missing ports or any change. Baseline source-FDC comparison passed. Dedicated
ref_clk_p/n do not appear in the ordinary I/O report: their source FDC remains
F6/E6. At build time .switch_db exports both exact baseline and candidate routed
ADFs, and a separate gate compares actual HSST placements and all 14 dedicated
PCIe/SFP/reference-clock pad connections. This physical proof is pending until
the sequential build; unchanged source constraints alone are not physical proof.
Bit provenance records mapped PCF/ADF hashes, exact routed ADF hash, full and
CDC report hashes and final .sbit hash; routed hash must survive STA/bitgen.

Validation completed in private copies: run_tests.py, test_registers.py,
audit_top.py and verify_bundle.py. Exact CAM5/CAM6 baseline pixels (307200 each),
raw parser insertion/deletion/reset/link-loss cases, legacy ABI, independent
AW/W, strobes/backpressure, register aliases/routing and coherent CDC/counter
behavior passed. Top ModelSim audit has the same 174 baseline diagnostics and
zero new errors; full top ModelSim compile does not pass. The copied 36-case
boundary result is audited evidence, not rerun here.

Board diagnostic access after a later successful build/burn: capture once at
0x200001D0 with 0x100, then select indices 0..15 without recapture and read
0x200001E0; read sequence at 0x200001F0. The candidate read_snapshot.py accepts
the parent's existing read32/write32 transport. No board access happens now.
Mode 0 exposes status=010/001 cycles, mixed K=2/K=4 words, rotation changes,
disparity/decode errors, status>=4 cycles, overflow, link loss, SOFs, decoded
pixels and approximate K=0 pixel quota. Compare repeated frozen snapshots with
50K TX count/CRC/color bars. Mixed-K and errors provide evidence for raw-parser
decisions without a trace, but cannot establish the exact raw symbol grammar
or attribute payload loss. Word 9 omits mixed-word data and uses decoded SOF;
it is not an independent transmitted-pixel quota. Mode-0 malformed is tied low.

Mode 1 later, using this same preparation/build shell (NOT prepared now):

    python "C:\Users\NineSun\Desktop\ov56401\project\sfp_100h_diag_mode0\prepare.py" --mode 1

This creates a fresh sibling sfp_100h_diag_mode1 with parameter=1 and fresh
manifests; run its build.ps1 after separate review. Reconnection of JTAG is
needed only at later burn time. No burn script is invoked by this launcher.
