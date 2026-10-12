# Isolated background thumbnail reader

Implemented only `background_thumbnail_reader.hpp`, `background_thumbnail_reader_selftest.cpp`, and this report. No viewer, PCIe session, RTL, board, or existing build files were changed by this task. The header is standalone C++17 and has no Qt, driver, or hardware dependencies. This is an owned-copy display reader; it makes no host zero-copy claim.

## Exact integration interface

Namespace: `background_thumbnail`.

```cpp
class Transport {
public:
    virtual ~Transport() = default;
    virtual bool readGuard(unsigned camera, unsigned bank, std::uint32_t& value) = 0;
    virtual bool readSequence(unsigned camera, unsigned bank, std::uint32_t& value) = 0;
    virtual bool readPayloadOwned(unsigned camera, unsigned bank, OwnedPayload& payload) = 0;
};

struct OwnedPayload {
    std::vector<std::uint8_t> bytes;
    std::uint32_t tag;
    std::size_t transferredBytes;
    bool contiguousMappingConfirmed;
};

// Static methods on Reader:
Result read(Transport&, unsigned camera, std::uint32_t capabilities,
            const Cursor&, Frame& output);
bool commit(unsigned camera, const Frame&, Cursor&) noexcept;
```

`Frame` contains `camera`, `bank`, full `guard`, `sequence`, `tag`, and owned `bytes`. `Cursor` contains `committed`, `camera`, and `sequence`; the boolean distinguishes an uninitialized cursor from a committed sequence zero. Keep a cursor per physical camera. Camera indices are exactly 0..5 and bank indices 0..1. The reader validates camera before any IO, and tests verify every physical camera/bank combination. A committed cursor belonging to another camera is an invalid request.

`Result` reports `Outcome::{accepted,retry,transport_fault,invalid_request,unsupported}` with `Reason::{none,camera_out_of_range,cursor_camera_mismatch,missing_capability,metadata_io,payload_io,payload_contract,metadata_changed,no_fresh_bank,ambiguous_sequence,tag_mismatch}`. Every false transport return is a transport fault; invalid/busy metadata is a retry. No failure invokes another transport or an unsafe fallback. One call makes one bounded attempt. Caller owns retry scheduling.

Example caller order:

```cpp
Frame candidate;
Result result = Reader::read(adapter, physicalCamera, caps, cursor, candidate);
if (result.outcome == Outcome::accepted) {
    // Under the application's appropriate serialization, validate that this
    // request's source/configuration generation remains eligible for delivery.
    if (applicationGenerationStillEligible()) {
        // Commit before moving the candidate's bytes out of the Frame.
        if (Reader::commit(physicalCamera, candidate, cursor)) {
            deliver(std::move(candidate));
        }
    }
}
```

The application eligibility function and delivery function above are pseudocode. `commit` cannot validate application generations, because this pure reader does not know them. It validates frame shape/identity and cursor freshness. Caller must serialize cursor commits and source/configuration eligibility validation as required by its application. Reading never advances a cursor. A generation-ineligible candidate can be discarded and reread with the unchanged cursor. Rejected reads leave all fields and bytes of prior output untouched.

## Provisional hardware/adapter contract

The parent RTL task owns `integrated_six_background` and the final enable/disable and tag mapping. Those mappings were not finalized for this delivery; no adapter, hardware enable writes, selector changes, or hardcoded DDR tag address are implemented.

The header publishes **provisional metadata constants**, not a validated hardware ABI:

| Item | Proposed value |
| --- | --- |
| Capability mask | 16 (`1 << 4`) |
| Metadata base | `0x40020000 + 0x200` |
| Bank metadata address | base + `32 * (2 * physicalCamera + bank)` |
| Guard offset | 0 |
| Sequence offset | 16 |
| Guard busy | bit 0 |
| Guard valid | bit 1 |
| Guard generation | bits 31:2 |
| Owned RGB565 thumbnail bytes | 153600 |
| Expected contiguous tag offset | 153600 |
| Tag storage span | 16 bytes |
| Expected completed DMA length | 153600 + 16 = 153616 bytes |

Transport calls abstract the mapping by camera and bank. The adapter must confirm the actual bitstream capability, metadata mapping, payload bank mapping, contiguous frame/tag layout, and tag encoding before reporting success. It must decode the finalized tag into the 32-bit `OwnedPayload::tag`, report the actual completed transfer size, and set `contiguousMappingConfirmed` only after confirming the layout. Merely allocating 153616 bytes is not evidence of a completed transfer. The reader faults on unconfirmed mapping, short/long transfer, or short/long owned frame. A different finalized layout requires an explicit contract change, not a speculative address fallback.

Each transport operation is synchronous and ordered with respect to MMIO/DMA. `readPayloadOwned` must finish DMA and copy scratch into its detached vector before returning; the next metadata read must occur after that copy. It must not return a borrowed view or a vector aliasing scratch. Shared DMA scratch synchronization and hardware ordering belong to the adapter. No reverse lock design is introduced in this pure API.

The writer must change the full generation guard before any payload rewrite, including failed rewrites that leave sequence unchanged, expose busy while writing, and publish valid/nonbusy only after payload/tag completion. The reader's safety assumes the guard cannot complete an entire 30-bit generation cycle within one attempt; full guard ABA cannot be detected by this interface. Likewise, sequence freshness assumes the relevant publication distance is below half the 32-bit range. Reset/re-enable may require caller cursor reset and application generation invalidation under the final control contract.

## Read algorithm

Both banks are sampled in guard -> sequence -> guard order. A bank can be considered only if its full guard is unchanged, valid, and nonbusy. A changed bracket causes a retry; a transport failure causes an immediate fault even if another bank might be usable. Stable invalid/busy banks are excluded.

If the cursor is committed, freshness requires unsigned sequence delta in 1..`0x7fffffff`. Delta zero or a delta greater than `0x80000000` is not fresh. Exactly `0x80000000` is ambiguous and causes retry. Without a committed cursor, valid publication zero is eligible. The newest eligible bank wins by the same half-range ordering; equal bank sequences deterministically choose bank 0, and a half-range bank tie causes retry.

The selected bank is rebracketed immediately before the owned payload operation and again after it. Both brackets must match the initially selected full guard and sequence. The payload tag must equal sequence exactly, including zero. Only then are temporary detached bytes moved into the caller output. A writer starting after the final captured guard cannot corrupt the already detached frame.

This protocol yields a coherent owned snapshot, not synchronized six-camera capture or a guarantee that the selected bank remains globally newest while later reads run. Performance, hardware publication ordering, actual mapping, and board behavior remain integration validation work.

## Adversarial fake verification

The fake transport schedules writer actions at independent event ordinals around metadata operations and inside DMA/copy. It does not use the reader's decision logic to decide whether to mutate a bank. Both DMA and copy run in two halves so the schedules can create torn scratch/temporary content that must never reach accepted output.

**128 tests passed**:

- All 12 physical camera/bank mappings, invalid camera indices, cursor camera mismatch, and missing capabilities.
- 30 writer-entry event edges spanning every read boundary plus DMA/copy internals. The final post-guard event is accepted only with already detached original bytes; earlier unsafe edges retry without changing prior output.
- 28 complete same-sequence failed-rewrite edges, changing generation and payload while leaving tag/sequence unchanged; all are rejected by full guard comparison.
- All 13 IO failure positions (12 metadata reads plus payload operation), with immediate categorized failure and unchanged output.
- Busy/invalid guards, newest selection in either bank, equal-bank tie, half-range ambiguities against banks/cursor, stale/equal cursor cases, source wrap to zero, and generation wrap during DMA.
- Sequence-only change, exact tag matching, five malformed payload contracts, scratch overwrite before post metadata, isolation across later accepted and rejected reads, explicit delayed commit, commit rejection integrity, and zero wrap commit.

Compiler: Ubuntu g++ 13.3.0, run through WSL Ubuntu-24.04. Executables were placed in `/tmp`, outside the repository. Commands executed successfully:

```sh
g++ -std=c++17 -Wall -Wextra -Werror /mnt/d/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/host/background_thumbnail_reader_selftest.cpp -o /tmp/background_thumbnail_reader_selftest
/tmp/background_thumbnail_reader_selftest

g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer /mnt/d/race/fpga/git/fpga/fpga/fpga_zero_copy_delivery/host/background_thumbnail_reader_selftest.cpp -o /tmp/background_thumbnail_reader_selftest_sanitized
/tmp/background_thumbnail_reader_selftest_sanitized
```

Both runs returned exit status 0 with no compiler warnings or sanitizer diagnostics. Exact stdout for each run:

```text
PASS 128 meaningful adversarial tests
Coverage: 12 physical camera/bank mappings; 30 writer-entry edges; 28 same-sequence rewrite edges; 13 transport-failure positions; wrap, ambiguity, ownership, explicit commit and payload contract
```
