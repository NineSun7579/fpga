# Production timing status

The final production build `validation_20261004_185843` passes every native
timing summary section and includes the acquired-lock-loss flush correction.
Matching full receiver/mode/preset/boot simulations now pass and are archived
with the routed evidence. This production image is ready for parent-owned
programming qualification, conditional on the assumed0..4ns input budget.
Hardware has not been programmed. Earlier
generic-IDDR, I/O-clock and regional-clock attempts are historical experiments.

The target remains 1920x1080p60 at 148.5MHz, with automatic 1280x720 support
and 1280x480 RGB565 through the existing 100H receiver. Production defaults
to cameras, KEY1 K18 / KEY2 L15, `DIAGNOSTIC_HDMI_BOOT=0`.

## Latest routed result

| Check | Slow corner | Fast corner |
| --- | ---: | ---: |
| HDMI external input setup | +0.575ns | +0.411ns |
| HDMI external input hold | +0.476ns | +0.994ns |
| HDMI internal setup | +1.133ns | +1.854ns |
| HDMI internal hold | +0.202ns | +0.116ns |
| Camera local hold | Pass | Pass |

All setup, hold, recovery, removal and pulse-width summary sections passed. The
HSST first-stage exception repair passed; later synchronizer stages remain
timed. Native routing hold repair fixed the three short camera pipeline paths.

The complete report, review, path evidence, input manifest and failing image
are retained under `validation_20261004_185843`. The production image SHA256 is
`a4d3b58fc38c6c4247fa1e17e34965cf9d6477e676b173f004097082fdda7a52`.
The stable production-v2 candidate is
`0a6023d090cffd54dfbb28c13df08afe0606215466c42ae9bc0fdaddc94e6432`.
Current capture SHA256 is
`65530e080b33f278c46527080fd19970b1f8968b7da9ac60be5d5e1533ed8a39`.
The earlier phase43 timing-only image is preserved under184937; the failed
phase51 report and image remain under184258. None has been programmed.

## Current repair under verification

`GTP_PLL_E3` drives a global sampling clock and a separate zero-phase global
feedback clock. Input registers and all HDMI processing use the sampling
clock. PLL lock gates both local reset synchronizers. PDS has successfully
placed and routed this topology from the fixed AA12 input.

The routed 51/64-cycle sampling phase was 5.366ns. Its slow-corner I/O clock
skew was +2.355ns and input hold was -0.366ns. The current physical PLL phase
is 43/64-cycle, 241.875 degrees / 4.524ns at 148.5MHz, advancing capture by
0.84175ns. The phase43 route established the margins above. Native routing hold
repair is enabled with threshold zero for ordinary short camera paths.

PLL generated-clock constraints use PDS's documented rename-only syntax,
preserving inferred ratios and physical phase (User Guide section6.2.2).
The input period remains 6.734ns, external arrivals remain 0..4ns, and
explicit uncertainty remains 0.200ns. No HDMI dedicated-routing override,
ordinary input-data cut, blanket asynchronous group, or budget relaxation
has been added.

## Validation

The unmodified vendor PLL/global-buffer test verified both HDMI rates,
source-relative phase, lock/reset, and 0/4ns external arrivals. Updated tests
inject lock loss after acquisition and require a fault and resets in both
FIFO domains. Full current receiver/mode/preset/boot regressions must pass
before qualification. Tests wait through PLL acquisition before supplying
a complete geometry-measurement VS; interrupted frames are discarded.

The final full receiver/mode snapshot is `format_sim_20261004_185614_34560`.
Its six shared RTL files and clock model match the frozen production sources
exactly. Three720p and two1080p frames each contain614400 correct RGB565 pixels
at the actual100H receiver; peak capture FIFO occupancy is477/2048. Key,
format/mode transitions, unsupported geometry, partial-frame abort, unplug,
timeout, legacy preset and production/diagnostic boot checks pass.

Ten passing logs and the refreshed simulation manifest are archived with the
final report/image. Manifest SHA256 is
`73be1b1b0c7537577d8941c79b142f90c021c8a8117cf22b06b804e8aaba6ce4`.
The original build-time short-test manifest is preserved separately as
`simulation_manifest_at_build.json`. Production candidate identity is still
unchanged, so no repeat route is required for the expanded simulation archive.
Actual generated-wrapper compilation passes with zero errors/warnings.
Known optional-port warnings remain54 in boot and7 in the actual PLL test;
all simulations report zero errors.

The PLL reset depends only on the mode request. FIFO resets depend on that
request and PLL lock; `capture_ready` cannot stop lock acquisition or reset
release. PLL lock status crosses two FFs into the merge domain. Only the
first D pin is excepted; stage two and the lock-loss fault path remain timed.

Production identity now covers explicit build inputs only; historical format
snapshots and testbenches are excluded. Simulation evidence is maintained
separately in `sim/simulation_manifest.json`. Updating tests or logs does not
require another unchanged production route.

The banked FIFO commits on the falling write edge and publishes its Gray
pointer on the next rising edge. Exact first-stage Gray/control exceptions
and first reset-stage clear exceptions preserve later-stage timing. Held
FIFO memory launch exceptions preserve local addresses and writes. Camera
byte/divided-clock transfers use a timed falling-edge bridge for data/DE/VS.

The original full timing report remains in
`validation_20261004_115333/hdmi_ddr_ov5640_top_original.rtr`. Detailed history
is retained in `timing_work_notes.md`. There is no known GUI blocker; the
parent-owned programmer and dedicated Questa project have not been touched.
