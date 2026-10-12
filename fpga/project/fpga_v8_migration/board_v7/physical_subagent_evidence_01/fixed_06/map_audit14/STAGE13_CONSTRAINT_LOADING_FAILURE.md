# Stage13 mapped constraint loading audit

The saved mapped dump was parsed read-only with the existing `prove_cdb11.parse_cdb` parser. Its CDB contains FN=1, CLOCK=1, MCP=4, CLKGP=11 and UNCTNT=28; it contains no MMD records. Consequently the appended 15.238 ns datapath-only mailbox budget is absent. Device Map completion and successful `add_constraint` registration do not establish stage13 constraint loading or coverage. Stage13 must not be accepted for routed signoff on this evidence.

Machine-readable evidence: `stage13_cdb18_audit.json`; reproduction: `audit_stage13_cdb18.py` in the evidence root. The dump SHA256 is recorded in the JSON.

Official documentation was extracted locally with PyMuPDF from `C:/pango/PDS_2022.2-SP6.4/doc/User_Constraint_Editor_User_Guide.pdf`. PDF page 11 (printed page 10), section 1.2, states that ADS Pre Synthesize UCE reads/writes FDC for synthesis, while Post Synthesize UCE reads/writes LCF and SCF, which MAP consumes. PDF page 12 (printed page 11) describes SDC/LCF for designs without a synthesis tool. This distinguishes constraint stages and provides the next interface investigation; it does not prove a runtime command or successful loading.

The export17 retry was rejected before export while `recover_compile_attempt.py` PID 57416 owned PDS children 68724/81632. A subsequent background job waits for the complete parent controller to exit before invoking export17, whose own idle guard remains active. No busy source/project/constraint was edited. Bit generation remains prohibited.
