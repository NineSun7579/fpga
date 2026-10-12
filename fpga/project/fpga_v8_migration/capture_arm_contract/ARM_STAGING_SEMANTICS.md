# ARM request contract

The candidate is `fpga_v8_capture_control_axil_arm_v2`. It retains every
original parameter and port, in the original order and widths. Only the module
name and two functional expressions change. `control.diff` records the exact
change against the immutable original controller.

The existing independent AW/W holding registers are the sequential boundary.
`config_valid` decodes a committed ARM from those immutable slots without
depending on READY. A commit exists only when both slots are full and no B
response or manager acknowledgment is outstanding. READY is sampled by the
sequential decision: `config_valid && config_ready` enters ARM_WAIT; a false
READY rejects the bus command immediately with SLVERR and increments the
rejected-config counter. The slots clear at that edge, so a rejected request
cannot remain queued or strand a later host ACK.

An ARM decoded at the same edge as an otherwise admissible SOF blocks SOF
through the existing manager `config_valid -> lease_block` path. This makes
the wrapper idle predicate true when its registered engine is idle, giving
ARM deterministic priority. A start captured at an earlier edge has registered
engine busy and/or WRITING ownership, so it rejects ARM. A request whose AW/W
slots are only partially populated has no priority; SOF can proceed until
there is a complete committed request. No accepted request occurs while the
engine is busy, during flush, during epoch_start, or while either bank is held.

READY indicates eligibility, not success. Only the manager's registered
accept/reject completes the ARM bus response. The original manager validates
nonzero fresh generations, parameter geometry, and protocol faults. Delayed
acknowledgment cannot redispatch the cleared holding slots. Sustained bus VALID
under stalled B cannot refill them until the response is consumed. When VALID
remains asserted after READY reopens, AXI defines a new transaction.

The lease and capture modules remain byte-identical to their frozen bindings.
There is no added false path, delay primitive, registered approximation of
idle, or change to publication, final-B, or release matching.
