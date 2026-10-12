# Background thumbnail parity (future hardware test)

`host/background_thumbnail_parity.cpp` compares completed autonomous thumbnail
pixels to the exact selected-camera frozen RAW publication. Defaults are physical
C1,C2,C3,C4, ten distinct fresh samples in each of two background output banks:
80 full 153600-byte comparisons. It reports only the selected camera scope. C5/C6
may be explicitly selected after their source health is established.

No board execution, upload, driver change or target compilation was performed by
this implementation. The known caps-15 board cannot exercise this test. Exact
caps 31, camera mask 0x3f and RAW geometry are required before any FPGA write;
caps 15 exits without selector/control/lease writes. This is pixel parity, not an
inference or zero-copy acceptance claim.

The host sequence for every capture attempt is:

1. Read a stable baseline record for the selected output bank; enable background
   admission through the existing `PcieSession` fd.
2. Await a fresh, completed record (new generation and newer sequence than a
   valid baseline), then disable and observe exact disabled/quiescent status.
3. Claim the selected camera with legacy **RGB mode 0**. This freezes RAW; no RGB
   submit or on-demand thumbnail command is issued. Require publication and the
   next lease generation. If the stable background record's RAW sequence does
   not equal the claim sequence, release/restore and retry the capture.
4. Validate both 16-byte record halves: guard, physical camera, bank, destination,
   sequence, payload length, geometry and tag address. Copy RAW and background
   payload/tag into owned host vectors through low DMA scratch. Check the full
   tag (32-bit sequence, upper 96 bits zero), identical metadata before/after,
   and unchanged RGB565 bytes at even RAW x/y. Reread RAW under the same lease
   after thumbnail DMA. Optional frozen snapshot/scalar checks cover all 19
   original registers. Release/restore before committing the bank's cursor.

Sequence zero is valid. Unsigned wrap uses strict half-range ordering; equal or
older samples cannot count, and the exact half-range is rejected. Each physical
camera/background-bank cursor is independent. No newest-bank-only reader choice
can exclude the older output bank from coverage.

`--cameras 1,2,3,4 --count 10 --attempts 128 --timeout 30 --snapshots` configures
the future target utility. Count must be at least ten; timeout is seconds per
accepted sample, bounding publication/alignment retries. Disable and RAW claim
each have the existing additional three-second deadline; ioctl bounds depend on
the driver. Partial successful JSON rows do not imply acceptance: require exit
zero and the final summary with all requested samples.

All reads and controls share one exclusive audited `PcieSession`. Restricted
background read allowlists cover only metadata beats and established thumbnail
destinations. Copies use scratch offset zero, below the reserved 2 MiB inference
slot. Neither this utility nor its helper creates an inference consumer. Normal
comparison/alignment failures disable/drain, safely release any lease and close.
Transport uncertainty, mutated ioctl metadata, unknown control bits, background
quarantine, or failed drain/release preserve fd/mappings/lock and SIGSTOP the
owner through the existing quarantine path. A stopped owner must be resolved by
coordinated hardware/driver recovery; killing it is not recovery.

Local validation only:

```
python run_background_parity.py
```

On Windows this compiles locally in WSL Ubuntu-24.04, runs `--self-test`, `--help`
and invalid CLI cases (all before opening a device), and compiles existing legacy
session callers. `--abi-dir` supplies the directory containing
`cooperative_linux_transport/driver_abi.hpp`. Source/binary hashes and check
receipts are in `background_parity_local_manifest.json` and
`background_parity_local_build.log`. The local binary is not an ARM64 artifact.
Self-tests cover wrap/zero/half-range ordering, record identity corruption,
busy/invalid records, full tag corruption and actual pixel mismatch rejection;
they do not prove DMA safety or physical camera timing.

Parent-owned future target build, with the manifest's headers staged together:

```
g++ -std=c++17 -O2 -Wall -Wextra -Werror -pthread -I. background_thumbnail_parity.cpp -o background_thumbnail_parity
```

The Python helper deliberately has no SSH/hardware mode. The parent must handle
driver identity, source upload verification, ARM64 compilation and later board
execution. Any future SSH runner must refuse quarantined owners, stop only a
known running viewer gracefully, obtain real RAW health logs before/after,
and preserve unknown-DMA owners. This helper does not implement or claim that
orchestration or recovery.

Host disable/read/claim timing may never align on a particular board. Bounded
failure is the correct outcome and preserves meaningful parity. If repeated
captures, including the opt-in freeze-first procedure below, cannot match,
a future separately reviewed protocol may need an
atomic stop-after-publication/RAW-bank hold operation tied to a requested camera
and completed sequence, with bounded drain acknowledgement. That would allow
the matching RAW bank to remain immutable until claim. Such a protocol change
is outside this host implementation; using a nearby/latest frame or deriving a
thumbnail from unrelated RAW must never be reported as parity.

Opt-in `--diagnostics` emits one failure-only JSON line to stderr before the
existing error/cleanup path. It aggregates exact attempt outcomes
(`no_fresh_publication`, `frozen_not_fresh`, `raw_sequence_mismatch`, `exception`)
and mutually exclusive publication-poll rejection counts (torn guard, busy guard,
invalid guard, cursor not fresh, baseline not advanced). Successful publication
polls are included in `poll_counts.total` but not in rejection counts. Each
attempt includes baseline, last running and frozen guard/sequence observations,
including the reread guard before any torn record is invalidated, last running
control, post-drain control, claimed control/status, and RAW sequence/generation/
source/publication. Unreached observations are null; exceptions identify the
stage alongside the existing error text. A zero sequence is never a missing
observation. Only the final running record is retained, not every poll. These
diagnostics add two control/status reads after claim and one after drain, so
their timing impact must be considered; limits and acceptance checks remain
unchanged. The existing generic alignment error alone cannot identify which
retry path occurred. Self-tests also check aggregate counts, torn/zero sequence
serialization, absent observations and disabled diagnostic output.

Design for parent review only: background disable drains all background cameras
but does not freeze RAW. The current lease holds the selected camera, waits its
writer/DMA drain and quiet interval, then freezes `prev_base` and its sequence.
Register 0xe0 exposes the frozen sequence, not live per-bank sequences; 0x120
exposes admission state, not per-bank publication bits. `selected_bank` selects
the output destination, not the RAW source. A sequence mismatch can therefore
show RAW has advanced relative to a thumbnail, but these observations cannot
prove whether that advance occurred during background drain or before RAW
freeze. No publication alone also cannot distinguish absent input from producer
drop/failure. Snapshot failures are identified separately by their stage.

Reading the other RAW bank would require verified full writer freeze/drain,
stable per-bank published metadata and its matching sequence, and exact tag
validation before/after payload DMA under the same lease. The current host ABI
does not expose those per-bank facts; a matching old DDR tag alone is insufficient
because a bank can have been invalidated or partly overwritten. Existing `raw()`
and `validate()` intentionally bind the source to the frozen lease. There is no
alternate-bank lookup or guard change here. An extension needs separate parent
review and meaningful lookup tests for unpublished banks, overwritten/stale tags,
sequence zero/wrap, metadata changes and exact sequence mismatch rejection.

## Opt-in RAW freeze before background drain

`--freeze-first --diagnostics --snapshots` uses the existing RGB lease with a
new explicit host claim policy; the default procedure and default session callers
still require disabled/drained background before claiming. Only owned, enabled
background with exact caps 31 and RGB mode 0 permits the new policy. Disabled,
quarantined, unknown control states and on-demand thumbnail claims reject it.

For each attempt, read both disabled baseline records, enable background and
wait for a fresh publication in a bank still needing samples (the existing
bounded producer-progress trigger). Claim RAW **before disabling background**.
While that lease remains held, disable/drain background, then read both records.
Select only a usable, fresh record whose sequence equals the frozen RAW lease,
whose usable baseline has both a different guard and older sequence, and whose
bank still needs samples. A matching other background bank is allowed; its own
cursor and sample count are used. Duplicate eligible sequence claims reject.
Without an eligible exact match, release and retry within the existing limits.
Every selected camera still needs at least ten distinct samples in each bank.
The snapshot/scalar checks, full tag checks, metadata rereads, full pixel compare,
RAW reread and generation/source validation remain mandatory as before.

RTL evidence in `integrated_six_background/source`:

* `delivery/delivery_regs.v:67` asserts the selected-camera capture hold as soon
  as held. Lines 88-94 wait for writer/DMA drain and 32 quiet cycles, then freeze
  `prev_base` and sequence. Lines 103-105 block enabled-background claims only in
  thumbnail mode, so RGB freeze is supported by the existing hardware ABI.
* `ov5640/ov5640_top.v:508` gates admission with `!capture_hold`.
  `ov5640/ov5640_ddr/ov5640_ddr_w_en.v:44` and `:94` gate new frame/SOF admission;
  an admitted DATA frame continues to its normal quota/retirement. After claim
  returns, no further selected-camera RAW frame can be admitted or publish until
  release. Other cameras continue until background disable, but cannot alter
  this selected camera's frozen RAW source.
* `delivery/background_producer.v:78` sets the expected sequence to the admitted
  source sequence plus one. Lines 97 and 47 require matching RAW publication and
  a complete frame/drained payload before requesting the tag. Lines 123-126 mark
  the record valid only after successful tag retirement. Disable prevents new
  admission without cancelling this pending completion.
* `delivery/background_six.v:59` retires on the AXI B handshake after AW/W finish;
  line 66 requires all producers idle and no active AXI transaction for quiescence.
  The existing exact control==2 drain therefore precedes all parity payload reads.

This uses either **thumbnail** bank and the original leased RAW source, not an
alternate RAW-bank tag lookup. No new per-RAW-bank metadata ABI is needed for
this ordering. Producer drops can still leave no exact thumbnail, so bounded
failure remains valid and hardware success is not established by local tests.
Diagnostics retain prior fields and add both baseline/frozen bank observations;
`no_exact_eligible_bank` distinguishes no eligible exact match from the default
procedure's RAW sequence mismatch.

The parent hardware diagnostic
`background_alignment_diagnostic_1791554267708741900/parity.stderr` recorded 16
stable valid frozen records, 16 RAW sequence mismatches and zero exceptions:
RAW was ahead by two in 15 attempts and by three in one. This proves that run's
failure was alignment, not missing publication or snapshot parity. It does not
prove where in the old disable/claim interval RAW advanced.

Local self-tests cover claim policy rejection, pending/failed tag publication,
exact bank1 selection over adjacent bank0, stale baseline/cursor, guard-only
changes, full-bank quota exclusion, tenth-sample eligibility, zero/wrap and
half-range ambiguity, duplicate sequence claims, and the existing tag/pixel/
diagnostic checks. Local compilation also checks legacy session callers. Parent
owns target compilation, hardware execution and RAW restoration; C5/C6 remain
deferred. No build helper or RTL changes accompany this procedure.
