# PLL56 explicit primitive source-drop experiment

Owned directory for the 2026-10-04 follow-up to `build_counter_bwnmjek8`.
Original board sources and frozen IP remain untouched. No SSH, hardware probe,
Flash, or board action is part of this experiment. Files are generated through
byte operations to preserve the original GBK content and line endings.

The failed attribute build stopped at counter mapping at 20:24:01, before route.
It is not a final STA result. `attribute_diagnosis.json` binds the actual vendor
guide, compiler recognition, control-set report, and synthesized netlist hashes.

| Evidence | Verified result |
| --- | --- |
| ADS guide section 5.17, PDF pages 96--100 | Module/global scope supported; not a reg-versus-wire scope mistake |
| compile/synthesize/dev_map logs | Attribute recognized and converted to `PAP_MIN_CONTROLSET_SIZE` |
| Four counter specializations | 128 total `GTP_DFF_CE` cells, all `.CE(N11)` |
| Actual counter control sets | Each camera has 32 flops, asynchronous C, dynamic N11 CE |
| N11 Boolean cone | `frame || (s_valid && full)`; same function in LUT3 or shared LUT6D |
| Guide applicability | Describes CLK/CE/synchronous SET/RESET, partial/all control removal; does not guarantee this asynchronous-clear case |

PDS does not report why its optimizer leaves this CE in place. Unsupported
attribute, wrong module scope, and a control-set count of at least 64 are not
supported explanations for the four 32-flop N11 sets. Do not claim a vendor
optimizer root cause beyond this evidence. The same control-set report also
contains 97-flop frame-enabled sets on CAM3/4 whose CE net is named
`u_src_drop.frame`; a net name inside the counter hierarchy does not by itself
establish that those flops are counter storage.

The alternative instantiates the vendor's documented `GTP_DFF_C` with INIT=0,
GRS enabled and active-high asynchronous clear. Its installed simulation model
has no CE port. The arithmetic is `sum = Q + increment` (increment as carry-in),
then `next_Q = frame ? {31'b0, increment} : sum`. This replaces an inferred
hold/increment enable without adding a registered flag, changing clock phase,
or pipelining the carry. Frame load is on the original rising edge and the
snapshot still observes old Q. The full design's mapped arithmetic and final
STA must establish whether this improves timing; source algebra cannot do so.

ModelSim uses the actual installed `GTP_DFF_C.v` and `GTP_GRS.v`, not a behavioral
stand-in for the primitive. The existing integration comparison and stimulus
are retained, with overflow seeding directed to each primitive's real `qout`
storage. The identical FIFO interface model isolates this counter and does not
revalidate production FIFO behavior. On 2026-10-04 at 20:37:16, it passed:

- 327708 camera edges and 768005 destination edges;
- one complete 307200-pixel offered frame with full/valid coincidences and gaps;
- 32-bit overflow, asynchronous source reset, independent destination reset;
- exact source state, bundled 96-bit snapshot, toggle/data pipeline and outputs.

`simulation/receipt.json` binds original, candidate, testbench, vendor model and
log hashes. Candidate SHA256 is
`24a98c042e66ca2fb248c2f315509b4c2affcd34791e6e1b00f850e55236e174`.

`build_counter_p1crc4an` launched at 20:38:36 using the existing seed1 as a fixed
comparison setting. Its `input_diff_proof.json` verifies the 694-file inventory
against `build_capture_538dxoxa`, with only
`source/ov5640/ov5640/ov5640_cdc.v` changed. The prior adapter overlay is retained.
All PLL56 clock periods and exceptions, including 17.857 ns camera clocks and
the real falling-edge-to-rising-edge half-cycle paths, are unchanged.

The generated `build.py` runs compile/synthesize, then fails closed unless all
four counter specializations contain 32 `GTP_DFF_C` cells each with no CE pins.
It additionally traces counter-related CE names in the control-set report.
The only accepted alias is `u_src_drop.frame`, with an exact hierarchy/port
connection to CDC `N14` and exactly 32 `src_seq`, 64 `src_snapshot`, and one
`src_toggle` endpoint. Any different alias, endpoint family/count, or counter
CE pin fails. It does not turn an attribute into assumed mapping evidence.
Only a passing mapping proof permits device-map and route. Exact 112-pin and
dedicated PHY equality, all 32 attributed read-before-write motion banks, and
zero failures across all 126 final timing summary rows still gate bitgen.
No random seed sweep is scheduled.

The independent DDR detector, reset, and diagnostic paths from the rejected
capture run remain separate problems. A clean counter CE mapping would not
establish their timing closure. No timing improvement or deployable bitstream
is claimed by the simulation or launch receipt.

Build progress and terminal status are recorded in this owned
`current_run.json` and the new build's `receipt.json`; the parent PLL56
`current_run.json` is deliberately left unchanged. Stage logs and artifacts
live in the build named by the owned status. A failed gate prevents bitgen and preserves
the report for diagnosis.

## Mapping outcome and gate correction, 20:54

`build_counter_p1crc4an` stopped at 20:51:39 before device-map or route because
the conservative report-name check flagged two `u_src_drop.frame` aliases.
Its actual four counter specializations contain 128 `GTP_DFF_C` cells with no
CE pins. The two flagged 97-flop control sets resolve to CDC sequence/snapshot/
toggle state, not counter storage. The gate now requires the exact endpoint
proof described above instead of assuming every counter-prefixed net drives
counter flops. `mapping_recheck.json` binds both netlists: the failed attribute
build still FAILS, while the explicit primitive build PASSES with two proven
non-counter aliases. The original failed receipt is preserved unchanged.

`build_counter_9caopnhe` launched at 20:54:32 with the corrected gate and the
same candidate and fixed seed1. Fresh compile/synthesis binds the revised gate
hash through the full build; no prior failed build is silently resumed. All
strict route/STA/bitgen checks remain. Final STA is pending, and this local
mapping result does not resolve the independent DDR paths.

## Completed result: ready for parent review

`build_counter_9caopnhe` finished at 21:41:00 on 2026-10-04 with status
`built_for_parent_review`. Final STA passed all 126 slow/fast setup, hold,
recovery, removal and minimum-pulse-width summary rows, with zero violated
paths. Report and bitstream hashes were independently checked after completion.

| Final STA metric | Slack ns |
| --- | ---: |
| CAM1 slow setup | +1.624 |
| CAM2 slow setup | +2.349 |
| CAM3 slow setup | +3.517 |
| CAM4 slow setup | +3.093 |
| DDR slow setup (worst setup domain) | +0.199 |
| Worst slow hold | +0.221 |
| Worst fast hold | +0.156 |
| PHY minimum pulse width (both corners) | +0.011 |

Clock audit PASS: CAM1/2 periods remain 11.905 ns, CAM3/4 17.857 ns,
DDR 7.619 ns; exceptions and clock phases retain the strict baseline checks.
All 128 source-drop flops have no CE. Exact 112-pin equality and dedicated
HSST PHY site/pad equality pass. All 32 motion-history physical banks retain
attributed read-before-write mapping. The 694-file inventory has the same
single RTL difference documented above. Shared lock was released.

The separate DDR paths also pass in this completed route; no detector/reset
RTL change was made and no claim of a repeatable structural DDR fix is made.
This is verified closure for this exact artifact, pending parent hardware
acceptance. ModelSim verifies counter semantics; it does not establish sensor
frame rates or board behavior. No hardware/SSH/Flash access occurred.

Artifact: `../build_counter_9caopnhe/top.sbit`, 3791112 bytes.

- Bit SHA256: `bc40afff4210bee0333feff7754d8fd5fd45207b1a04a301cdf8add54d7465b0`
- STA report SHA256: `9f15a103e11459a6143b753d8c96a418ebe52c4e62ae62c8782f11578b33cec1`
- Routed ADF SHA256: `3d4d549014d23985e8a2c3be7e7c169bbba5e5886877565015a5470e72d4531e`

Parent handoff evidence is in the build's `receipt.json`, `strict_timing.json`,
`clock_audit.json`, `counter_mapping_proof.json`, `input_diff_proof.json`,
`pin_audit.json`, `phy_audit.json`, and `motion_resource_proof.json`. The original
failed attribute and conservative-alias receipts remain preserved.
