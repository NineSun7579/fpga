# Independent pin audit, 2026-10-04 21:35

`independent_audit.py` reads the existing artifacts without invoking PDS. Its
`independent_pin_proof.json` records hashes, all synthesized pin maps, the four
parent-to-counter instance connections, exact report alias endpoints, and all
128 routed instance names, physical cell definitions, and connected pin nets.

The explicit primitive survived. Both `build_counter_p1crc4an` and
`build_counter_9caopnhe` contain exactly 32 `GTP_DFF_C` cells in each of four
counter specializations, covering every `value[0]` through `value[31]` once.
Each specialization resolves to its own camera CDC instance. None has a CE pin.

The routed `9caopnhe/routed_phy.txt` also proves 128 unique counter FF instances,
32 per camera, all with `LCE_EN="FALSE"`, asynchronous reset enabled, one clock,
one reset connection, one output connection, and **zero connected physical CE
pins**. These FFs operate unconditionally at their source clock edges. This is
stronger than a report-name inference or a claim that an RTL attribute worked.
The physical operator combines arithmetic/LUT logic with FF storage, so the
routed names use `gopAL6Q`/`gopLUT6Q` rather than the synthesis primitive name.

The two suspicious 97-FF report rows are CAM1/2, not CAM3/4. Each frame alias
resolves through the counter `.frame(N14)` connection to 32 `src_seq`, 64
`src_snapshot`, and one `src_toggle` register in its CDC parent. None is counter
storage. The earlier `p1crc4an` failed receipt remains intact; its report-scope
failure does not establish a dynamic counter CE. The previous attribute build
`bwnmjek8` is a different result: all 128 `GTP_DFF_CE` cells retain `.CE(N11)`.
The existing fail-closed gate remains unchanged by this independent audit.

The installed `ADS_Synthesis_User_Guide.pdf` was read directly with PyMuPDF:
PDF page 53 documents HDL-only `syn_keep` and `syn_preserve`; pages 84--85
document `syn_keep` on nets/ports, preserving nets through keep buffers; pages
92--93 document `syn_preserve` on modules/ports/registers for sequential
preservation. These statements do not promise a CE-free implementation of an
inferred asynchronous-clear counter. No guessed `dont_touch`, instance-scoped
keep declaration, or new preservation attribute has been added. None is needed
for the actual CE-free primitive implementation already observed.

The prior vendor-model simulation receipt and log hashes were independently
verified against the current candidate: PASS, 327708 source edges, 768005
destination edges, full frame, wrap, asynchronous reset, coherent snapshot.

`minimal_proof.py` prepares one isolated 32-bit counter using byte-identical
counter-module content, the same primitive parameters, device and ADS tool.
It adds no preservation attributes and checks 32 mapped `GTP_DFF_C` cells with
no CE pins or CE control sets before declaring PASS. It acquires the existing
shared `fpga/build.lock` and checks vendor idleness before launching PDS.
The first attempt, `minimal32__cjtu5az`, is explicitly
`blocked_vendor_busy`: the existing full run owns the lock. **No minimal
synthesis PASS is claimed.** Rerun only after the shared vendor lock is released.

No new full build, SSH, hardware access, Flash, clock/constraint edit, or seed
change was performed by this audit. The already-running `9caopnhe` advanced to
`full_sta` at 21:34:57; no terminal STA result was available at this checkpoint.
Its existing 126-row STA, exact pins/PHY, and 32 motion-bank gates still decide
whether bitgen is permitted. No timing closure or deployment is claimed.
