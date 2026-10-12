# build02 preparation

PREPARED_NOT_MAPPED. Local copy, Python compilation and preflight only.
No PDS, ModelSim, mapping, bitstream, programming or device operation was performed.
There is no executable project.pds or physical controller in this delivery.

The independent RTL/inputs freeze contains 741 byte-hashed files and 186 registered sources.
Only rtl/v7_sfd_candidate.v and rtl/v7_sdt_bus.v are replaced by the regressed primitive candidate.
The actual v7_sdt_top parent, camera/control/lease optimizations and all other GBK bytes are preserved.
The registered source scan finds one bus binding, four camera source instances, 28 CE and 32 PE.
This syntax scan is preparation evidence; build02 has no new elaborated or mapped graph.

Topregression01: 123 deliverable hashes, real 14668-check logs, vendor inputs and equal trace hashes verified.
The active build01 project/controller/queue records can differ from the regression's historical frozen input inventory.
Every mismatch is recorded in preflight_result.json; INPUTPROOF_DRIFT blocks the physical evidence gate.
The regressed baseline differs from build01 only by the documented ASYNC_REG versus syn_preserve/syn_allow_retiming attributes.
The preflight checks the exact attribute substitution and byte identity elsewhere for both files.
No historical audit or active controller/source was rewritten.

map01 final result is currently absent: physical gate PENDING.
After a completion notification, the main session must re-read final_result.json, all three real ADF/native DB hashes,
official completion markers, input hashes, topology and detailed endpoint checks: PASS with 60 distinct cells, 28 sync, 32 reset.
The active user goal already authorizes physical construction, SRAM programming and RK3568 screenshot verification. After the evidence gates pass, the main session can launch the physical build with serial tool scheduling; no additional user authorization is required.
Historical frozen input drift needs a reviewed, hash-bound reconciliation with current registered sources; do not relabel it PASS.

Review templates are byte copies of build01 physical_flow.py, targeted_reports.py and routed_acceptance.py.
They are reference templates only: their imports/old bindings are not a build02 runner and no successful execution is assumed.
The accepted targeted query form uses explicit physical -from/-to lists, min_max, bounded batches,
both-corner coverage and a streaming parser which closes each record at Slack; unsupported/ignored filters fail the guard.
New build02 queries must prove one physical pair first and then full physical endpoint coverage.

The independent analysis patch is in analysis_tools/. graph_adapter resolves actual Q aliases/drivers through
unit KEEPBUFFER/KEEPBUF paths, recognizes cr_ff and cr[] anchors, rejects packed SRL/RAM and shared cells,
and keeps direct predecessor, clock, reset-release and first-stage source checks.
camera clock traversal includes GTP input/clock buffers and KEEPBUFFER, verifies one input/one output,
and fails on unknown sinks. resolve_manifest retains exhaustive actual LUT-cone evaluation and adds unit buffer traversal.
No old-name whitelist is deleted to obtain a PASS. These changes are Python-compiled only; validation on new graphs is pending.

Next authorized physical stage must derive constraints from its own compile/synthesis exports and re-derive after mapping.
2048 logical bits must resolve to the actual mapping: 1320 unique Q-D pairs (330/camera) for this expected contract.
The legacy 1280 count cannot be selected by presence/absence of a marker file; a different count blocks review.
Preserve all 368 directed U relationships, carve only the four camera-to-DDR budgets, prove the 364 retained U-B
relationships in actual clock interaction tables, and add no same-domain false exceptions.
Clock collections, reset32 and sync-later16 endpoints must be rebound from the new actual graphs and native provenance.

PNR needs new graph coverage and runtime U-B PASS. Signoff requires all ten Slow/Fast STA groups,
1320 mailbox pairs at 15.238 ns in both corners with nonnegative slack, exact physical filter proof,
32 independent resets with Recovery/Removal/MPW, same-domain synchronizer setup/hold, IO112,
HSST sites/dedicated links, motion32 DRM36K and production/IP protection checks.
No bit or device stage is included or permitted by this preparation.

Review manifest.json, source_binding_diff.json, the two byte-preserving RTL diffs,
analysis_patch.diff, analysis_patch_manifest.json, evidence/build01_frozen_inputs.json and preflight_result.json.
Local recheck: python preflight.py --verify. This command never starts tools and always reports physical_start_allowed=false.
