#ifndef FPGA_V8_COOP_HOST_PROTOCOL_HPP
#define FPGA_V8_COOP_HOST_PROTOCOL_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <utility>
#include <vector>

namespace coop_host {

inline constexpr std::uint32_t kControlBase = 0x40010000U;
inline constexpr std::uint32_t kDeviceId = 0x434f4f50U;
inline constexpr std::uint32_t kVersion = 0x00010000U;
inline constexpr std::uint32_t kNoBank = 0xffffffffU;
inline constexpr std::uint32_t kHostClaimBit = 1U << 3;
inline constexpr std::size_t kFrameBytes = 640U * 640U * 3U;
inline constexpr std::uint64_t kRawBytesWithTag = 640U * 480U * 2U + 16U;
inline constexpr std::uint64_t kPhysicalDdrBytes = 256ULL * 1024ULL * 1024ULL;
using Beat = std::array<std::uint8_t, 16>;

struct Register { const char* name; std::uint32_t local; };
inline constexpr std::array<Register, 27> kRegisters{{
    {"DEVICE_ID", 0x00}, {"STATUS", 0x04}, {"VERSION", 0x08},
    {"READY_HINT", 0x0c}, {"HOST_BANK", 0x10}, {"SOURCE_SEQ", 0x14},
    {"GENERATION", 0x18}, {"OUTPUT_LENGTH", 0x1c}, {"OUTPUT_ADDRESS", 0x20},
    {"SOURCE_CAMERA", 0x24}, {"SOURCE_CAMERA_BANK", 0x28}, {"SOURCE_ADDRESS", 0x2c},
    {"CLAIM", 0x30}, {"LEASE_TOKEN_LOW", 0x34}, {"LEASE_TOKEN_HIGH", 0x38},
    {"ACK_BANK", 0x40}, {"ACK_SOURCE_SEQ", 0x44}, {"ACK_GENERATION", 0x48},
    {"ACK_DOORBELL", 0x4c}, {"REJECTED_ACK_COUNT", 0x50},
    {"REJECTED_CLAIM_COUNT", 0x54}, {"REJECTED_RAW_COUNT", 0x58},
    {"BRIDGE_FAILURE_COUNT", 0x5c}, {"COMPLETED_COUNT", 0x60},
    {"SOURCE_RELEASE_COUNT", 0x64}, {"ACCEPTED_COUNT", 0x68}, {"LAST_ERROR", 0x6c}
}};

constexpr std::uint32_t physical_address(std::uint32_t local) noexcept {
    return kControlBase + 4U * local;
}
inline Beat encode_word(std::uint32_t value) noexcept {
    Beat beat{};
    for (unsigned i = 0; i != 4; ++i)
        beat[i] = static_cast<std::uint8_t>(value >> (i * 8));
    return beat;
}
inline std::uint32_t decode_word(const Beat& beat) noexcept {
    std::uint32_t value = 0;
    for (unsigned i = 0; i != 4; ++i)
        value |= static_cast<std::uint32_t>(beat[i]) << (i * 8);
    return value;
}

// KnownRejected means a definite response with NO requested ownership side effect.
// DeliveryKnownUnknownResponse means the singleton transaction has retired and
// subsequent reads are ordered after it, but BRESP/RRESP was not exposed. It is
// NEVER an alias for Uncertain (timeout, partial transfer, possibly pending bus work).
enum class IoStatus { KnownOK, KnownRejected, DeliveryKnownUnknownResponse, Uncertain };
struct DmaResult { IoStatus status = IoStatus::Uncertain; std::size_t bytes = 0; };

class Transport {
public:
    virtual ~Transport() = default;
    // Exactly one aligned full AXI128 beat: LEN=0, SIZE=4, LAST=1 for writes.
    // read16 returns the low little-endian word and zero upper 96 bits.
    virtual IoStatus read16(std::uint32_t physical, Beat& destination) = 0;
    virtual IoStatus write16(std::uint32_t physical, const Beat& source) = 0;
    // Uses the already reserved RX slot, then COPIES into destination. KnownOK
    // with destination.size() bytes certifies ALL DMA retired and a stable complete
    // copy. Never retain a pointer to destination, even on error; quarantine any
    // outstanding activity in the externally reserved DMA mapping instead.
    virtual DmaResult copy_ddr_blocking(std::uint32_t physical,
                                      std::uint64_t reserved_rx_offset,
                                      std::vector<std::uint8_t>& destination) = 0;
};

// External attestations, not allocations or discoveries. Every flag defaults false.
// The caller/backend must keep these facts true for the helper's entire lifetime.
struct RuntimeReservation {
    bool exclusive_controller_client_lock = false;
    bool exclusive_output_banks = false;
    bool exclusive_rx_frame_slot = false;
    bool transport_control_buffers_reserved = false;
    bool endpoint_loaded_and_decode_reserved = false;
    bool coordinated_reset_fresh_generation = false;
    bool single_camera_identity_domain = false;
};
struct Config {
    std::uint32_t expected_generation = 0;
    std::uint32_t camera = 4; // cam5, zero based; this candidate accepts one camera.
    std::array<std::uint32_t, 2> output_addresses{{0x08000000U, 0x08200000U}};
    std::array<std::uint32_t, 2> raw_addresses{{0x01800000U, 0x01a00000U}};
    std::size_t frame_bytes = kFrameBytes;
    std::uint64_t rx_capacity = 0; // Actual externally established driver capacity.
    std::uint64_t control_rx_slots_end = 0; // End of ALL reserved read16 scratch slots.
    std::uint64_t frame_rx_offset = 0;
};
struct Descriptor {
    std::uint32_t bank = kNoBank, sequence = 0, generation = 0, length = 0;
    std::uint32_t address = 0, camera = 0, source_bank = 0, source_address = 0;
    std::uint64_t token = 0; // Opaque. No implicit generation/sequence arithmetic.
};
enum class State { Idle, Claimed, Owned, Faulted };
enum class Result { OK, Busy, Rejected, WrongState, InvalidBuffer, Faulted };
enum class Fault {
    None, TransportRead, TransportWrite, TransportException, Identity,
    Descriptor, ClaimObservation, LeaseChanged, DmaIncomplete, AckObservation
};
struct Snapshot {
    State state = State::Idle;
    Fault fault = Fault::None;
    bool claim_may_exist = false;
    bool descriptor_valid = false;
    bool stable_copy_completed = false;
    std::optional<std::uint32_t> requested_bank;
    std::optional<Descriptor> held_lease; // May be partial if descriptor_valid=false.
};
struct OwnedFrame {
    Descriptor descriptor;
    std::vector<std::uint8_t> bytes;
    bool complete = false; // False on partial/error. Never hand that frame to inference.
};
struct CopyResult {
    Result result = Result::WrongState;
    std::optional<OwnedFrame> frame; // Preserves even partial bytes on a DMA failure.
};

class Candidate {
public:
    // Constructor validates reservations/configuration BEFORE any transport I/O.
    Candidate(Transport& transport, Config config, RuntimeReservation reservation)
        : transport_(transport), config_(config) { validate_config(config, reservation); }
    Candidate(const Candidate&) = delete;
    Candidate& operator=(const Candidate&) = delete;
    ~Candidate() = default; // No ACK, I/O, cancellation or fabricated reset.

    Snapshot snapshot() const {
        std::lock_guard<std::mutex> lock(mutex_);
        return snapshot_;
    }

    // One poll, no sleeps or retries. Caller supplies its own bounded scheduling.
    Result claim_one_poll() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (snapshot_.state == State::Faulted) return Result::Faulted;
        if (snapshot_.state != State::Idle) return Result::Busy;
        try {
            std::uint32_t id = 0, version = 0, status = 0, hint = 0;
            if (!read_word(0x00, id) || !read_word(0x08, version)) return Result::Faulted;
            if (id != kDeviceId || version != kVersion) return fail(Fault::Identity);
            if (!read_word(0x04, status)) return Result::Faulted;
            if (status & kHostClaimBit) return Result::Busy;
            if (!read_word(0x0c, hint)) return Result::Faulted;
            if (hint == kNoBank) return Result::Busy;
            if (hint > 1) return fail(Fault::ClaimObservation);
            snapshot_.requested_bank = hint;
            snapshot_.claim_may_exist = true; // Set before invoking possibly throwing backend.
            const IoStatus delivered = transport_.write16(physical_address(0x30), encode_word(hint));
            if (delivered == IoStatus::KnownRejected) {
                snapshot_ = Snapshot{};
                return Result::Busy;
            }
            if (delivered == IoStatus::Uncertain) return fail(Fault::TransportWrite);
            Descriptor desc;
            if (!read_word(0x10, desc.bank)) return Result::Faulted;
            snapshot_.held_lease = desc;
            if (!read_word(0x04, status)) return Result::Faulted;
            if (delivered == IoStatus::DeliveryKnownUnknownResponse &&
                desc.bank == kNoBank && !(status & kHostClaimBit)) {
                snapshot_ = Snapshot{}; // Ordered observation proves no bound host lease.
                return Result::Busy;
            }
            if (desc.bank != hint || !(status & kHostClaimBit))
                return fail(Fault::ClaimObservation);
            snapshot_.state = State::Claimed;
            // Update diagnostic metadata after each read, including on an early failure.
            auto field = [&](std::uint32_t local, std::uint32_t& value) {
                const bool ok = read_word(local, value);
                snapshot_.held_lease = desc;
                return ok;
            };
            std::uint32_t low = 0, high = 0;
            if (!field(0x14, desc.sequence) || !field(0x18, desc.generation) ||
                !field(0x1c, desc.length) || !field(0x20, desc.address) ||
                !field(0x24, desc.camera) || !field(0x28, desc.source_bank) ||
                !field(0x2c, desc.source_address) || !field(0x34, low) || !field(0x38, high))
                return Result::Faulted;
            desc.token = (static_cast<std::uint64_t>(high) << 32) | low;
            snapshot_.held_lease = desc;
            if (!valid_descriptor(desc)) return fail(Fault::Descriptor);
            if (!verify_held(desc)) return Result::Faulted;
            snapshot_.descriptor_valid = true;
            return Result::OK;
        } catch (...) { return fail(Fault::TransportException); }
    }

    // Supply a caller-allocated vector of EXACTLY kFrameBytes. Returned storage
    // belongs entirely to the caller, independently of the transport RX mapping.
    // No ACK here. A returned complete frame remains usable after ACK/readback faults.
    CopyResult copy_owned(std::vector<std::uint8_t> destination) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (snapshot_.state == State::Faulted) return {Result::Faulted, std::nullopt};
        if (snapshot_.state != State::Claimed) return {Result::WrongState, std::nullopt};
        if (destination.size() != kFrameBytes) return {Result::InvalidBuffer, std::nullopt};
        OwnedFrame frame{*snapshot_.held_lease, std::move(destination), false};
        try {
            if (!verify_held(frame.descriptor)) return {Result::Faulted, std::move(frame)};
            const DmaResult copied = transport_.copy_ddr_blocking(
                frame.descriptor.address, config_.frame_rx_offset, frame.bytes);
            if (copied.status != IoStatus::KnownOK || copied.bytes != kFrameBytes ||
                frame.bytes.size() != kFrameBytes) {
                fail(Fault::DmaIncomplete);
                return {Result::Faulted, std::move(frame)};
            }
            frame.complete = true;
            snapshot_.stable_copy_completed = true;
            if (!verify_held(frame.descriptor)) return {Result::Faulted, std::move(frame)};
            snapshot_.state = State::Owned;
            return {Result::OK, std::move(frame)};
        } catch (...) {
            fail(Fault::TransportException);
            return {Result::Faulted, std::move(frame)};
        }
    }

    // Explicit retry is permitted ONLY after a definite rejection. Uncertain
    // outcomes fault permanently; constructing another helper is not recovery.
    Result acknowledge() {
        std::lock_guard<std::mutex> lock(mutex_);
        if (snapshot_.state == State::Faulted) return Result::Faulted;
        if (snapshot_.state != State::Owned) return Result::WrongState;
        try {
            const Descriptor desc = *snapshot_.held_lease;
            if (!verify_held(desc)) return Result::Faulted;
            const std::array<std::pair<std::uint32_t, std::uint32_t>, 3> stages{{
                {0x40, desc.bank}, {0x44, desc.sequence}, {0x48, desc.generation}
            }};
            for (const auto& stage : stages) {
                const IoStatus status = transport_.write16(physical_address(stage.first),
                                                           encode_word(stage.second));
                if (status == IoStatus::KnownRejected) return Result::Rejected;
                if (status == IoStatus::Uncertain) return fail(Fault::TransportWrite);
            }
            // Also necessary when a legacy backend cannot report staged-write BRESP.
            for (const auto& stage : stages) {
                std::uint32_t value = 0;
                if (!read_word(stage.first, value)) return Result::Faulted;
                if (value != stage.second) return fail(Fault::AckObservation);
            }
            if (!verify_held(desc)) return Result::Faulted;
            const IoStatus delivered = transport_.write16(physical_address(0x4c), encode_word(1));
            if (delivered == IoStatus::KnownRejected) return Result::Rejected;
            if (delivered == IoStatus::Uncertain) return fail(Fault::TransportWrite);
            std::uint32_t bank = 0, status = 0;
            if (!read_word(0x10, bank) || !read_word(0x04, status)) return Result::Faulted;
            if (bank == kNoBank && !(status & kHostClaimBit)) {
                // Capture may already reuse the released bank as WRITING/READY.
                snapshot_ = Snapshot{};
                return Result::OK;
            }
            if (delivered == IoStatus::DeliveryKnownUnknownResponse && bank == desc.bank &&
                (status & kHostClaimBit) && verify_held(desc)) return Result::Rejected;
            return fail(Fault::AckObservation);
        } catch (...) { return fail(Fault::TransportException); }
    }

private:
    static bool bounded(std::uint64_t address, std::uint64_t length) noexcept {
        return address <= kPhysicalDdrBytes && length <= kPhysicalDdrBytes - address;
    }
    static bool overlaps(std::uint64_t a, std::uint64_t an,
                         std::uint64_t b, std::uint64_t bn) noexcept {
        return a < b + bn && b < a + an;
    }
    static void validate_config(const Config& c, const RuntimeReservation& r) {
        if (!r.exclusive_controller_client_lock || !r.exclusive_output_banks ||
            !r.exclusive_rx_frame_slot || !r.transport_control_buffers_reserved ||
            !r.endpoint_loaded_and_decode_reserved || !r.coordinated_reset_fresh_generation ||
            !r.single_camera_identity_domain)
            throw std::invalid_argument("external runtime reservations were not confirmed");
        if (!c.expected_generation || c.camera != 4 || c.frame_bytes != kFrameBytes)
            throw std::invalid_argument("fresh nonzero generation and cam5 RGB640x640 required");
        for (const auto address : c.output_addresses)
            if ((address & 15U) || !bounded(address, kFrameBytes))
                throw std::invalid_argument("output outside physical DDR or misaligned");
        for (const auto address : c.raw_addresses)
            if ((address & 15U) || !bounded(address, kRawBytesWithTag))
                throw std::invalid_argument("RAW plus tag outside physical DDR or misaligned");
        if (overlaps(c.output_addresses[0], kFrameBytes, c.output_addresses[1], kFrameBytes) ||
            overlaps(c.raw_addresses[0], kRawBytesWithTag, c.raw_addresses[1], kRawBytesWithTag))
            throw std::invalid_argument("bank regions overlap");
        for (const auto output : c.output_addresses)
            for (const auto raw : c.raw_addresses)
                if (overlaps(output, kFrameBytes, raw, kRawBytesWithTag))
                    throw std::invalid_argument("RAW and output regions overlap");
        if (c.output_addresses != std::array<std::uint32_t, 2>{{0x08000000U, 0x08200000U}} ||
            c.raw_addresses != std::array<std::uint32_t, 2>{{0x01800000U, 0x01a00000U}})
            throw std::invalid_argument("candidate reservations must match specified cam5 banks");
        const std::uint64_t aligned_bytes = (static_cast<std::uint64_t>(kFrameBytes) + 15U) & ~15ULL;
        if (c.control_rx_slots_end < 16 || (c.control_rx_slots_end & 15U) ||
            (c.frame_rx_offset & 15U) || c.frame_rx_offset < c.control_rx_slots_end ||
            c.frame_rx_offset > c.rx_capacity || aligned_bytes > c.rx_capacity - c.frame_rx_offset)
            throw std::invalid_argument("RX slot not aligned, disjoint or within supplied capacity");
    }
    bool valid_descriptor(const Descriptor& d) const noexcept {
        if (d.bank > 1 || d.source_bank > 1 || d.camera >= 6 || d.camera != config_.camera ||
            !d.sequence || !d.token || d.generation != config_.expected_generation ||
            d.length != kFrameBytes) return false;
        if (d.address != config_.output_addresses[d.bank] ||
            d.source_address != config_.raw_addresses[d.source_bank] ||
            !bounded(d.address, d.length) || !bounded(d.source_address, kRawBytesWithTag)) return false;
        for (const auto raw : config_.raw_addresses)
            if (overlaps(d.address, d.length, raw, kRawBytesWithTag)) return false;
        return true;
    }
    Result fail(Fault fault) noexcept {
        if (snapshot_.state != State::Faulted) snapshot_.fault = fault;
        snapshot_.state = State::Faulted;
        return Result::Faulted;
    }
    bool read_word(std::uint32_t local, std::uint32_t& value) {
        Beat beat{};
        const IoStatus status = transport_.read16(physical_address(local), beat);
        if (status == IoStatus::Uncertain || status == IoStatus::KnownRejected) {
            fail(Fault::TransportRead);
            return false;
        }
        for (std::size_t i = 4; i != beat.size(); ++i)
            if (beat[i]) { fail(Fault::TransportRead); return false; }
        value = decode_word(beat);
        return true;
    }
    bool verify_held(const Descriptor& d) {
        std::uint32_t bank = 0, sequence = 0, generation = 0, status = 0;
        if (!read_word(0x10, bank) || !read_word(0x14, sequence) ||
            !read_word(0x18, generation) || !read_word(0x04, status)) return false;
        if (bank != d.bank || sequence != d.sequence || generation != d.generation ||
            generation != config_.expected_generation || !(status & kHostClaimBit)) {
            fail(Fault::LeaseChanged);
            return false;
        }
        return true;
    }

    Transport& transport_;
    const Config config_;
    mutable std::mutex mutex_; // Serializes this object's complete public operations.
    Snapshot snapshot_;
};

} // namespace coop_host
#endif
