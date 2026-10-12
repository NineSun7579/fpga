# Fresh graph identity/clock coverage contract

coverageproof_routed.json pairs keep `logical` and `physical` timing endpoints as
original mailbox CLK -> host_bank D. Buffer delay stays in the timing query.
Each pair includes `launch_Q`, `capture_Q`, `connection_semantics: identity_path`,
`driver_trace` ordered from host D net backwards to mailbox Q, and `direct_Q_to_D`
computed from actual endpoint net equality. A buffered pair has false, never true.
Each trace entry includes actual net, driver, primitive type, identity_input and
actual INIT parameters for CLKROUTE. Only CR <- M with INITABCD=[0,all1,0,all1]
is accepted. Single-driver/cycle/direction checks remain mandatory.

Every fresh routed graph is tested with the reviewed read-data LUT exhaustive
function algorithm for all 2048 bits. The reference review.py source is pinned by
SHA256 and only its pure functions/data loop execute against this run's graphs
and manifest; no old review.json is read. 1320 register and 728 zero, 330/182 per
camera, 1320 unique original timing pairs and manifest Q identity all must match.

Clock bindings contain `logical`, `physical` endpoint list and status. Equivalent
fanout copies retain every clock endpoint, exact D/CLK/reset/CE nets, full effective
parameters and output fanout evidence. Missing leaves require this actual run's
exact Public-4008 Instance warning and absence of the cell in the actual graph.
Camera-root traversal records actual clock buffer/IOL mode/polarity and enumerates
storage clock pins; the surviving endpoint sets must equal bound copies/cleanup.

Data/clock coverage PASS is separate from physical independent storage. Only after
endpoint_audit and classify prove all 60 distinct storage cells, 28 sync and 32
distinct reset endpoints is independent_storage_gate_passed recorded true and any
target STA launched. SRL/RAM packing stays rejected. Build01 calibration data PASS
does not qualify build02 or any STA group. Actual signoff remains mandatory.

Delivery audit_sources includes main-owned routed_connection.py, consumer and
assembler paths plus actual runtime truth producer/reference. Review requests
hash those exact disk paths, never manufacture acceptance. The main consumer owns
its independent actual-net identity validation; this task does not edit it.

Queue tracks map01 run.py/recover.py/audit_final.py and build01 resume_actual_graph.py
by qualified script path for their entire lifetime, including tool-free gaps.
No stale PID is a queue identity. Controller lease excludes duplicate build02,
launcher ancestors and self-dependent observers; PDS global mutex is held only
after final real map01 PASS and all prior controllers exit.
