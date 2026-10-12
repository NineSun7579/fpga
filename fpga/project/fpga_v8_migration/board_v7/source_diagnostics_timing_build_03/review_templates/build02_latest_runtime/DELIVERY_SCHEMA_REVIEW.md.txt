# build02 producer contract review

Only this runtime producer is changed. The assembler/consumer are owned by the main session.

deliverySources/v1 now contains audit_sources, target_logs and every actual artifact path.
Audit roles point to actual sources: audit_fixed adapter source; verify_routed11 role uses this runtime's
routed_acceptance.py (actual new graph binding); summarize/raw_audit use their actual executed parser sources;
consumer points to new_program_candidate.py. Extra roles bind the actual targeted parser, graph resolver,
endpoint checker, producer and assembler. Executed in-memory adapter hashes remain in the bound provenance artifacts.
The acceptance request hashes exactly descriptor.audit_sources; no nonexistent assembler.AUDITS is referenced.

All 21 mailbox batch shell/run pairs and their filter guards are artifacts and target_logs members.
Reset Recovery/Removal, reset MPW, sync-later and single-pair shell/run logs, raw reports and audit proofs are bound too.
Reset targets retain the exact routed logical set used by reset_bindings; synthesis P/C pins never overwrite that set.

Bit selection is never bits[0]. Each fresh generated output is checked for the actual Pango binary container,
complete design/device/compiler header and payload presence, then bound by SHA256 and bytes to the successful official
generation result/log and unchanged routed DB. Default selection requires exactly one complete actual .sbit.
Ambiguous/missing .sbit selection fails closed and emits bit_candidates.json; the main session can supply
bitSelection/v1 with reviewer, exact path/hash/bytes and route_sha256. Selection does not imply JTAG/device acceptance.
No programmer is invoked by this producer.

The independent_review_request is explicitly accepted=false/reviewer=null. No acceptance is generated.
After main acceptance exists, --check and the actual consumer verifier must pass before a validated local manifest is written.
Assembler/consumer build-root compatibility is checked against the current main-owned code during review; this producer
does not monkeypatch BUILD, write external code, or import a legacy V7 bit/program verifier.
