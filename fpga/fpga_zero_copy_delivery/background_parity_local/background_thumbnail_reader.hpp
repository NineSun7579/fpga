#ifndef BACKGROUND_THUMBNAIL_READER_HPP
#define BACKGROUND_THUMBNAIL_READER_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <utility>
#include <vector>

namespace background_thumbnail {

constexpr unsigned kCameraCount = 6;
constexpr unsigned kBankCount = 2;
constexpr std::uint32_t kCapability = 16u;
constexpr std::size_t kFrameBytes = 153600;
constexpr std::size_t kTagBytes = 16;
constexpr std::size_t kTransferBytes = kFrameBytes + kTagBytes;
constexpr std::size_t kExpectedTagOffset = kFrameBytes;
// PROVISIONAL metadata contract only; never a DDR payload/tag address.
constexpr std::uint32_t kProvisionalMetadataBase = 0x40020000u + 0x200u;
constexpr std::uint32_t kProvisionalMetadataStride = 32u;
constexpr std::uint32_t kProvisionalGuardOffset = 0u;
constexpr std::uint32_t kProvisionalSequenceOffset = 16u;

inline bool usableGuard(std::uint32_t guard) noexcept {
    return (guard & 3u) == 2u; // busy bit 0, valid bit 1, generation bits 31:2
}

enum class Order { equal, newer, older, ambiguous };
inline Order sequenceOrder(std::uint32_t candidate, std::uint32_t reference) noexcept {
    const std::uint32_t delta = candidate - reference;
    if (delta == 0) return Order::equal;
    if (delta == 0x80000000u) return Order::ambiguous;
    return delta < 0x80000000u ? Order::newer : Order::older;
}

struct OwnedPayload {
    std::vector<std::uint8_t> bytes; // exactly kFrameBytes; detached from DMA scratch
    std::uint32_t tag = 0; // adapter decodes the finalized tag representation
    std::size_t transferredBytes = 0;
    bool contiguousMappingConfirmed = false;
};

// All methods complete synchronously. false means transport fault, never "busy".
// Adapter must order MMIO/DMA, validate camera/bank mappings, confirm contiguous
// payload+16-byte tag mapping, and finish copying scratch BEFORE returning.
// No borrowed buffer, detached worker, hardware selector, or DDR tag address here.
class Transport {
public:
    virtual ~Transport() = default;
    virtual bool readGuard(unsigned camera, unsigned bank, std::uint32_t& value) = 0;
    virtual bool readSequence(unsigned camera, unsigned bank, std::uint32_t& value) = 0;
    virtual bool readPayloadOwned(unsigned camera, unsigned bank, OwnedPayload& payload) = 0;
};

struct Cursor {
    bool committed = false;
    unsigned camera = 0;
    std::uint32_t sequence = 0;
};

struct Frame {
    unsigned camera = 0;
    unsigned bank = 0;
    std::uint32_t guard = 0;
    std::uint32_t sequence = 0;
    std::uint32_t tag = 0;
    std::vector<std::uint8_t> bytes;
};

enum class Outcome { accepted, retry, transport_fault, invalid_request, unsupported };
enum class Reason {
    none, camera_out_of_range, cursor_camera_mismatch, missing_capability,
    metadata_io, payload_io, payload_contract, metadata_changed,
    no_fresh_bank, ambiguous_sequence, tag_mismatch
};
struct Result {
    Outcome outcome;
    Reason reason;
};

class Reader {
    struct Sample { std::uint32_t guard = 0; std::uint32_t sequence = 0; };
    static Result sample(Transport& io, unsigned camera, unsigned bank, Sample& out) {
        std::uint32_t lastGuard = 0;
        if (!io.readGuard(camera, bank, out.guard) ||
            !io.readSequence(camera, bank, out.sequence) ||
            !io.readGuard(camera, bank, lastGuard))
            return {Outcome::transport_fault, Reason::metadata_io};
        if (out.guard != lastGuard)
            return {Outcome::retry, Reason::metadata_changed};
        return {Outcome::accepted, Reason::none};
    }
    static bool same(const Sample& a, const Sample& b) noexcept {
        return a.guard == b.guard && a.sequence == b.sequence && usableGuard(b.guard);
    }
public:
    // One bounded attempt, no polling, fallback, or cursor mutation. Output is
    // replaced only after every validation succeeds. Caller owns retry policy.
    static Result read(Transport& io, unsigned camera, std::uint32_t capabilities,
                       const Cursor& cursor, Frame& output) {
        if (camera >= kCameraCount)
            return {Outcome::invalid_request, Reason::camera_out_of_range};
        if (cursor.committed && cursor.camera != camera)
            return {Outcome::invalid_request, Reason::cursor_camera_mismatch};
        if ((capabilities & kCapability) == 0)
            return {Outcome::unsupported, Reason::missing_capability};

        std::array<Sample, kBankCount> banks{};
        int chosen = -1;
        for (unsigned bank = 0; bank < kBankCount; ++bank) {
            const Result r = sample(io, camera, bank, banks[bank]);
            if (r.outcome != Outcome::accepted) return r;
            if (!usableGuard(banks[bank].guard)) continue;
            if (cursor.committed) {
                const Order order = sequenceOrder(banks[bank].sequence, cursor.sequence);
                if (order == Order::ambiguous)
                    return {Outcome::retry, Reason::ambiguous_sequence};
                if (order != Order::newer) continue;
            }
            if (chosen >= 0) {
                const Order order = sequenceOrder(banks[bank].sequence,
                                                  banks[static_cast<unsigned>(chosen)].sequence);
                if (order == Order::ambiguous)
                    return {Outcome::retry, Reason::ambiguous_sequence};
                if (order != Order::newer) continue; // ties choose bank 0
            }
            chosen = static_cast<int>(bank);
        }
        if (chosen < 0) return {Outcome::retry, Reason::no_fresh_bank};
        const unsigned bank = static_cast<unsigned>(chosen);
        Sample before;
        Result r = sample(io, camera, bank, before);
        if (r.outcome != Outcome::accepted) return r;
        if (!same(banks[bank], before))
            return {Outcome::retry, Reason::metadata_changed};

        OwnedPayload payload;
        if (!io.readPayloadOwned(camera, bank, payload))
            return {Outcome::transport_fault, Reason::payload_io};
        Sample after;
        r = sample(io, camera, bank, after);
        if (r.outcome != Outcome::accepted) return r;
        if (!same(before, after))
            return {Outcome::retry, Reason::metadata_changed};
        if (!payload.contiguousMappingConfirmed || payload.transferredBytes != kTransferBytes ||
            payload.bytes.size() != kFrameBytes)
            return {Outcome::transport_fault, Reason::payload_contract};
        if (payload.tag != before.sequence)
            return {Outcome::retry, Reason::tag_mismatch};

        Frame accepted;
        accepted.camera = camera;
        accepted.bank = bank;
        accepted.guard = before.guard;
        accepted.sequence = before.sequence;
        accepted.tag = payload.tag;
        accepted.bytes = std::move(payload.bytes);
        output = std::move(accepted);
        return {Outcome::accepted, Reason::none};
    }

    // Call ONLY after application source/configuration generation eligibility
    // validation. That eligibility is outside this pure reader's knowledge.
    static bool commit(unsigned camera, const Frame& frame, Cursor& cursor) noexcept {
        if (camera >= kCameraCount || frame.camera != camera || frame.bank >= kBankCount ||
            !usableGuard(frame.guard) || frame.tag != frame.sequence ||
            frame.bytes.size() != kFrameBytes ||
            (cursor.committed && (cursor.camera != camera ||
             sequenceOrder(frame.sequence, cursor.sequence) != Order::newer))) return false;
        cursor.camera = camera;
        cursor.sequence = frame.sequence;
        cursor.committed = true;
        return true;
    }
};

} // namespace background_thumbnail
#endif
