#ifndef FPGA_V8_CAPTURE_HOST_PROTOCOL_HPP
#define FPGA_V8_CAPTURE_HOST_PROTOCOL_HPP

#include "../cooperative_host/coop_host_protocol.hpp"

namespace capture_host {

using coop_host::Beat;
using coop_host::Transport;
using coop_host::IoStatus;
using coop_host::DmaResult;
using coop_host::encode_word;
using coop_host::decode_word;
using coop_host::physical_address;
inline constexpr std::uint32_t kDeviceId = 0x4341504cU;
inline constexpr std::uint32_t kVersion = 0x00010000U;
inline constexpr std::uint32_t kNoBank = coop_host::kNoBank;
inline constexpr std::size_t kRawBytes = 640U * 480U * 2U;
inline constexpr std::uint32_t kArmed = 1U, kConfigOK = 2U, kProtocolFault = 4U;
inline constexpr std::uint32_t kBound = 8U, kOffered = 16U;
inline constexpr std::uint32_t kConfigPending = 32U, kReleasePending = 64U;
inline constexpr std::uint32_t kConfigReady = 128U, kOfferBank = 1024U;
using Register = coop_host::Register;
inline constexpr std::array<Register, 32> kRegisters{{
    {"DEVICE_ID",0x100},{"STATUS",0x104},{"VERSION",0x108},{"STAGED_GENERATION",0x10c},
    {"ARM_DOORBELL",0x110},{"RAW_CLAIM",0x114},{"RAW_BOUND_BANK",0x118},
    {"RAW_SOURCE_SEQ",0x11c},{"RAW_GENERATION",0x120},{"RAW_LENGTH",0x124},
    {"RAW_ADDRESS",0x128},{"RAW_CAMERA",0x12c},{"RAW_TOKEN_LOW",0x130},{"RAW_TOKEN_HIGH",0x134},
    {"RAW_ACK_BANK",0x138},{"RAW_ACK_SEQ",0x13c},{"RAW_ACK_GENERATION",0x140},
    {"RAW_ACK_TOKEN_LOW",0x144},{"RAW_ACK_TOKEN_HIGH",0x148},{"RAW_ACK_CAMERA",0x14c},
    {"RAW_ACK_DOORBELL",0x150},{"REJECTED_HOST_CLAIMS",0x154},{"BAD_HOST_ACKS",0x158},
    {"REJECTED_CONFIGS",0x15c},{"MANAGER_PUBLISHED_COUNT",0x160},{"MANAGER_FAILED_COUNT",0x164},
    {"MANAGER_REJECTED_RELEASE_COUNT",0x168},{"MANAGER_BANK_STATES",0x16c},
    {"ACCEPTED_GENERATION",0x170},{"ACCEPTED_CONFIG_COUNT",0x174},
    {"ACCEPTED_HOST_RELEASE_COUNT",0x178},{"ACCEPTED_HOST_CLAIM_COUNT",0x17c}
}};

// External attestations only. All default false, checked before any I/O.
struct RuntimeReservation {
    bool exclusive_controller_client = false;
    bool shared_operation_coordinator_confirmed = false;
    bool backend_transport_mutex_authoritative = false;
    bool fixed_source_and_output_layout_validated = false;
    bool exclusive_disjoint_raw_and_output_rx_slots = false;
    bool transport_control_buffers_reserved = false;
    bool capture_endpoint_loaded_and_decode_reserved = false;
    bool coordinated_reset_and_external_lease_recovery = false;
    bool selected_unfiltered_rgb565_stream_validated = false;
    bool single_camera_identity_domain = false;
};
struct Config {
    std::uint32_t camera = 4; // Integration identity; no physical camera assertion.
    std::array<std::uint32_t,2> raw_addresses{{0x01800000U,0x01a00000U}};
    std::array<std::uint32_t,2> output_addresses{{0x08000000U,0x08200000U}};
    std::size_t width = 640, height = 480, raw_bytes = kRawBytes;
    std::uint64_t ddr_limit = coop_host::kPhysicalDdrBytes;
    std::uint64_t rx_capacity = 0; // Actual externally established backend capacity.
    std::uint64_t control_rx_slots_end = 0;
    std::uint64_t raw_rx_offset = 0, output_rx_offset = 0;
    std::uint64_t raw_rx_slot_bytes = kRawBytes; // May reserve an extra 16-byte tag.
};
struct ArmRequest {
    std::uint32_t generation = 0;
    bool fresh_persisted_generation_allocated = false;
    bool all_host_cooperative_and_dma_work_quiescent = false;
};
struct Descriptor {
    std::uint32_t bank=kNoBank, sequence=0, generation=0, length=0, address=0, camera=0;
    std::uint64_t token=0;
};
enum class State { Idle, Claimed, Owned, Faulted };
enum class Result { OK, Busy, Rejected, WrongState, InvalidBuffer, InvalidRequest, Faulted };
enum class Fault {
    None, TransportRead, TransportWrite, TransportException, Identity, HardwareStatus,
    ArmObservation, ClaimObservation, Descriptor, LeaseChanged, DmaIncomplete, AckObservation
};
struct Snapshot {
    State state=State::Idle;
    Fault fault=Fault::None;
    bool armed_confirmed=false, arm_may_be_pending=false, claim_may_exist=false;
    bool release_may_be_pending=false, descriptor_valid=false, stable_copy_completed=false;
    std::uint32_t accepted_generation=0;
    std::optional<std::uint32_t> requested_bank;
    std::optional<Descriptor> held_lease; // May be partial while descriptor_valid is false.
};
struct OwnedRawFrame {
    Descriptor descriptor;
    std::vector<std::uint8_t> bytes; // Exact little-endian RGB565 payload; never RX mapping storage.
    bool complete=false;
};
struct CopyResult { Result result=Result::WrongState; std::optional<OwnedRawFrame> frame; };

// Use this around EACH complete existing cooperative Candidate public operation.
// Do not wrap CandidateRAW calls: they already acquire the same nonrecursive lock.
template<class Function>
decltype(auto) with_exclusive_io(std::mutex& coordinator, Function&& function) {
    std::lock_guard<std::mutex> lock(coordinator);
    return std::forward<Function>(function)();
}

inline bool same_source(const OwnedRawFrame& raw, const coop_host::OwnedFrame& output) noexcept {
    const auto& r=raw.descriptor;
    const auto& o=output.descriptor;
    return raw.complete && output.complete && raw.bytes.size()==kRawBytes &&
        output.bytes.size()==coop_host::kFrameBytes && r.length==kRawBytes &&
        o.length==coop_host::kFrameBytes && r.bank==o.source_bank &&
        r.address==o.source_address && r.sequence==o.sequence && r.generation==o.generation &&
        r.camera==o.camera && r.token==o.token;
}

class CandidateRAW {
public:
    CandidateRAW(Transport& transport, Config config, RuntimeReservation reservation,
                 std::mutex& shared_coordinator)
        : transport_(transport), config_(config), coordinator_(shared_coordinator) {
        validate_config(config,reservation);
    }
    CandidateRAW(const CandidateRAW&)=delete;
    CandidateRAW& operator=(const CandidateRAW&)=delete;
    ~CandidateRAW()=default; // No I/O, ACK, retry, cancellation or synthetic reset.
    Snapshot snapshot() const {
        std::lock_guard<std::mutex> lock(coordinator_);
        return snapshot_;
    }

    // One attempt. An allocator/epoch barrier must authorize every arm explicitly.
    Result arm(const ArmRequest& request) {
        std::lock_guard<std::mutex> lock(coordinator_);
        if(snapshot_.state==State::Faulted) return Result::Faulted;
        if(snapshot_.state!=State::Idle) return Result::Busy;
        if(!request.generation || !request.fresh_persisted_generation_allocated ||
           !request.all_host_cooperative_and_dma_work_quiescent) return Result::InvalidRequest;
        try {
            if(!identity()) return Result::Faulted;
            std::uint32_t status=0,banks=0,old_gen=0,accepted=0,rejected=0;
            if(!read_word(0x104,status) || !read_word(0x16c,banks) ||
               !read_word(0x170,old_gen) || !read_word(0x174,accepted) ||
               !read_word(0x15c,rejected)) return Result::Faulted;
            if(!(status&kConfigOK) || (status&kProtocolFault)) return fail(Fault::HardwareStatus);
            if((status&(kBound|kConfigPending|kReleasePending)) || !(status&kConfigReady) || banks)
                return Result::Busy;
            if(old_gen==request.generation) return Result::Rejected;
            const auto stage=transport_.write16(physical_address(0x10c),encode_word(request.generation));
            if(stage==IoStatus::KnownRejected) return Result::Rejected;
            if(stage==IoStatus::Uncertain) return fail(Fault::TransportWrite);
            std::uint32_t staged=0;
            if(!read_word(0x10c,staged)) return Result::Faulted;
            if(staged!=request.generation) return fail(Fault::ArmObservation);
            snapshot_.arm_may_be_pending=true; // Before a backend can throw.
            const auto delivered=transport_.write16(physical_address(0x110),encode_word(1));
            if(delivered==IoStatus::KnownRejected) {
                snapshot_.arm_may_be_pending=false;
                return Result::Busy;
            }
            if(delivered==IoStatus::Uncertain) return fail(Fault::TransportWrite);
            std::uint32_t gen=0,now_accepted=0,now_rejected=0;
            if(!read_word(0x170,gen) || !read_word(0x104,status) ||
               !read_word(0x174,now_accepted) || !read_word(0x15c,now_rejected)) return Result::Faulted;
            if(gen==request.generation && (status&(kArmed|kConfigOK))==(kArmed|kConfigOK) &&
               !(status&(kProtocolFault|kBound|kConfigPending|kReleasePending)) &&
               now_accepted==accepted+1U && now_rejected==rejected) {
                snapshot_.arm_may_be_pending=false;
                snapshot_.armed_confirmed=true;
                snapshot_.accepted_generation=gen;
                return Result::OK;
            }
            if(delivered==IoStatus::DeliveryKnownUnknownResponse && gen==old_gen &&
               now_accepted==accepted && now_rejected==rejected+1U &&
               !(status&(kConfigPending|kReleasePending))) {
                snapshot_.arm_may_be_pending=false;
                return Result::Busy;
            }
            return fail(Fault::ArmObservation);
        } catch(...) { return fail(Fault::TransportException); }
    }

    Result claim_one_poll() {
        std::lock_guard<std::mutex> lock(coordinator_);
        if(snapshot_.state==State::Faulted) return Result::Faulted;
        if(snapshot_.state!=State::Idle) return Result::Busy;
        if(!snapshot_.armed_confirmed) return Result::WrongState;
        try {
            if(!identity()) return Result::Faulted;
            std::uint32_t status=0,gen=0,accepted=0,rejected=0;
            if(!read_word(0x104,status) || !read_word(0x170,gen)) return Result::Faulted;
            if(!(status&kConfigOK) || (status&kProtocolFault)) return fail(Fault::HardwareStatus);
            if(gen!=snapshot_.accepted_generation) return fail(Fault::LeaseChanged);
            // Sequence exhaustion may disarm the manager with a final valid offer.
            if((status&(kBound|kConfigPending|kReleasePending)) || !(status&kOffered)) return Result::Busy;
            const std::uint32_t bank=(status&kOfferBank) ? 1U : 0U;
            if(!read_word(0x17c,accepted) || !read_word(0x154,rejected)) return Result::Faulted;
            snapshot_.requested_bank=bank;
            snapshot_.claim_may_exist=true;
            const auto delivered=transport_.write16(physical_address(0x114),encode_word(bank));
            if(delivered==IoStatus::KnownRejected) { clear_lease(); return Result::Busy; }
            if(delivered==IoStatus::Uncertain) return fail(Fault::TransportWrite);
            Descriptor desc;
            if(!read_word(0x118,desc.bank)) return Result::Faulted;
            snapshot_.held_lease=desc;
            std::uint32_t now_accepted=0,now_rejected=0;
            if(!read_word(0x104,status) || !read_word(0x17c,now_accepted) ||
               !read_word(0x154,now_rejected)) return Result::Faulted;
            if(delivered==IoStatus::DeliveryKnownUnknownResponse && desc.bank==kNoBank &&
               !(status&kBound) && now_accepted==accepted && now_rejected==rejected+1U) {
                clear_lease();return Result::Busy;
            }
            if(desc.bank!=bank || !(status&kBound) || now_accepted!=accepted+1U || now_rejected!=rejected)
                return fail(Fault::ClaimObservation);
            snapshot_.state=State::Claimed;
            if(!descriptor_fields(desc)) return Result::Faulted;
            if(!valid_descriptor(desc)) return fail(Fault::Descriptor);
            if(!verify_held(desc)) return Result::Faulted;
            snapshot_.descriptor_valid=true;
            return Result::OK;
        } catch(...) { return fail(Fault::TransportException); }
    }

    // Exactly 614400 payload bytes. A reserved optional tag slot is never read here.
    CopyResult copy_owned(std::vector<std::uint8_t> destination) {
        std::lock_guard<std::mutex> lock(coordinator_);
        if(snapshot_.state==State::Faulted) return {Result::Faulted,std::nullopt};
        if(snapshot_.state!=State::Claimed) return {Result::WrongState,std::nullopt};
        if(destination.size()!=kRawBytes) return {Result::InvalidBuffer,std::nullopt};
        OwnedRawFrame frame{*snapshot_.held_lease,std::move(destination),false};
        try {
            if(!verify_held(frame.descriptor)) return {Result::Faulted,std::move(frame)};
            const DmaResult dma=transport_.copy_ddr_blocking(frame.descriptor.address,config_.raw_rx_offset,frame.bytes);
            if(dma.status!=IoStatus::KnownOK || dma.bytes!=kRawBytes || frame.bytes.size()!=kRawBytes) {
                fail(Fault::DmaIncomplete);return {Result::Faulted,std::move(frame)};
            }
            frame.complete=true;snapshot_.stable_copy_completed=true;
            if(!verify_held(frame.descriptor)) return {Result::Faulted,std::move(frame)};
            snapshot_.state=State::Owned;
            return {Result::OK,std::move(frame)};
        } catch(...) { fail(Fault::TransportException);return {Result::Faulted,std::move(frame)}; }
    }

    Result acknowledge() {
        std::lock_guard<std::mutex> lock(coordinator_);
        if(snapshot_.state==State::Faulted) return Result::Faulted;
        if(snapshot_.state!=State::Owned) return Result::WrongState;
        try {
            const Descriptor desc=*snapshot_.held_lease;
            if(!verify_held(desc)) return Result::Faulted;
            const std::array<std::pair<std::uint32_t,std::uint32_t>,6> stages{{
                {0x138,desc.bank},{0x13c,desc.sequence},{0x140,desc.generation},
                {0x144,static_cast<std::uint32_t>(desc.token)},
                {0x148,static_cast<std::uint32_t>(desc.token>>32)},{0x14c,desc.camera}
            }};
            for(const auto& stage:stages) {
                const auto result=transport_.write16(physical_address(stage.first),encode_word(stage.second));
                if(result==IoStatus::KnownRejected) return Result::Rejected;
                if(result==IoStatus::Uncertain) return fail(Fault::TransportWrite);
            }
            for(const auto& stage:stages) {
                std::uint32_t value=0;
                if(!read_word(stage.first,value)) return Result::Faulted;
                if(value!=stage.second) return fail(Fault::AckObservation);
            }
            if(!verify_held(desc)) return Result::Faulted;
            std::uint32_t accepted=0,rejected=0;
            if(!read_word(0x178,accepted) || !read_word(0x158,rejected)) return Result::Faulted;
            snapshot_.release_may_be_pending=true;
            const auto delivered=transport_.write16(physical_address(0x150),encode_word(1));
            if(delivered==IoStatus::KnownRejected) {
                snapshot_.release_may_be_pending=false;return Result::Rejected;
            }
            if(delivered==IoStatus::Uncertain) return fail(Fault::TransportWrite);
            std::uint32_t bank=0,status=0,now_accepted=0,now_rejected=0;
            if(!read_word(0x118,bank) || !read_word(0x104,status) ||
               !read_word(0x178,now_accepted) || !read_word(0x158,now_rejected)) return Result::Faulted;
            if(bank==kNoBank && !(status&(kBound|kReleasePending)) &&
               now_accepted==accepted+1U && now_rejected==rejected) {
                clear_lease();return Result::OK;
            }
            if(delivered==IoStatus::DeliveryKnownUnknownResponse && bank==desc.bank &&
               (status&kBound) && !(status&kReleasePending) && now_accepted==accepted &&
               now_rejected==rejected+1U && verify_held(desc)) {
                snapshot_.release_may_be_pending=false;return Result::Rejected;
            }
            return fail(Fault::AckObservation);
        } catch(...) { return fail(Fault::TransportException); }
    }

private:
    static bool fits(std::uint64_t addr,std::uint64_t bytes,std::uint64_t limit) noexcept {
        return addr<=limit && bytes<=limit-addr;
    }
    static bool overlap(std::uint64_t a,std::uint64_t an,std::uint64_t b,std::uint64_t bn) noexcept {
        // Call only after fits guards have ruled out end arithmetic overflow.
        return a<b+bn && b<a+an;
    }
    static void validate_config(const Config& c,const RuntimeReservation& r) {
        if(!r.exclusive_controller_client || !r.shared_operation_coordinator_confirmed ||
           !r.backend_transport_mutex_authoritative || !r.fixed_source_and_output_layout_validated ||
           !r.exclusive_disjoint_raw_and_output_rx_slots || !r.transport_control_buffers_reserved ||
           !r.capture_endpoint_loaded_and_decode_reserved || !r.coordinated_reset_and_external_lease_recovery ||
           !r.selected_unfiltered_rgb565_stream_validated || !r.single_camera_identity_domain)
            throw std::invalid_argument("external RAW/paired-output runtime reservations were not confirmed");
        if(c.camera!=4 || c.width!=640 || c.height!=480 || c.raw_bytes!=kRawBytes ||
           c.raw_addresses!=std::array<std::uint32_t,2>{{0x01800000U,0x01a00000U}} ||
           c.output_addresses!=std::array<std::uint32_t,2>{{0x08000000U,0x08200000U}} ||
           !c.ddr_limit || c.ddr_limit>coop_host::kPhysicalDdrBytes)
            throw std::invalid_argument("fixed candidate identity/layout/dimensions/DDR_LIMIT required");
        for(const auto a:c.raw_addresses)
            if((a&15U) || !fits(a,coop_host::kRawBytesWithTag,c.ddr_limit))
                throw std::invalid_argument("RAW payload plus tag exceeds validated DDR_LIMIT");
        for(const auto a:c.output_addresses)
            if((a&15U) || !fits(a,coop_host::kFrameBytes,c.ddr_limit))
                throw std::invalid_argument("output bank exceeds validated DDR_LIMIT");
        for(const auto raw:c.raw_addresses) for(const auto output:c.output_addresses)
            if(overlap(raw,coop_host::kRawBytesWithTag,output,coop_host::kFrameBytes))
                throw std::invalid_argument("RAW/output DDR regions overlap");
        if(c.raw_rx_slot_bytes!=kRawBytes && c.raw_rx_slot_bytes!=coop_host::kRawBytesWithTag)
            throw std::invalid_argument("RAW RX reservation must be payload or payload plus tag");
        if(c.control_rx_slots_end<16 || (c.control_rx_slots_end&15U) ||
           (c.raw_rx_offset&15U) || (c.output_rx_offset&15U) ||
           c.raw_rx_offset<c.control_rx_slots_end || c.output_rx_offset<c.control_rx_slots_end ||
           !fits(c.raw_rx_offset,c.raw_rx_slot_bytes,c.rx_capacity) ||
           !fits(c.output_rx_offset,coop_host::kFrameBytes,c.rx_capacity) ||
           overlap(c.raw_rx_offset,c.raw_rx_slot_bytes,c.output_rx_offset,coop_host::kFrameBytes))
            throw std::invalid_argument("control/RAW/output RX slots lack alignment, separation or capacity");
    }
    void clear_lease() noexcept {
        const auto generation=snapshot_.accepted_generation;
        const auto armed=snapshot_.armed_confirmed;
        snapshot_=Snapshot{};snapshot_.accepted_generation=generation;snapshot_.armed_confirmed=armed;
    }
    Result fail(Fault fault) noexcept {
        if(snapshot_.state!=State::Faulted) snapshot_.fault=fault;
        snapshot_.state=State::Faulted;return Result::Faulted;
    }
    bool read_word(std::uint32_t local,std::uint32_t& value) {
        Beat beat{};
        const auto result=transport_.read16(physical_address(local),beat);
        if(result==IoStatus::Uncertain || result==IoStatus::KnownRejected) { fail(Fault::TransportRead);return false; }
        for(std::size_t i=4;i<beat.size();++i) if(beat[i]) { fail(Fault::TransportRead);return false; }
        value=decode_word(beat);return true;
    }
    bool identity() {
        std::uint32_t id=0,version=0;
        if(!read_word(0x100,id) || !read_word(0x108,version)) return false;
        if(id!=kDeviceId || version!=kVersion) { fail(Fault::Identity);return false; }
        return true;
    }
    bool descriptor_fields(Descriptor& d, bool retain_partial=true) {
        auto field=[&](std::uint32_t local,std::uint32_t& value) {
            const bool ok=read_word(local,value);
            if(retain_partial) snapshot_.held_lease=d;
            return ok;
        };
        std::uint32_t low=0,high=0;
        if(!field(0x11c,d.sequence) || !field(0x120,d.generation) || !field(0x124,d.length) ||
           !field(0x128,d.address) || !field(0x12c,d.camera) || !field(0x130,low) || !field(0x134,high)) return false;
        d.token=(static_cast<std::uint64_t>(high)<<32)|low;
        if(retain_partial) snapshot_.held_lease=d;
        return true;
    }
    bool valid_descriptor(const Descriptor& d) const noexcept {
        return d.bank<2 && d.sequence && d.generation==snapshot_.accepted_generation &&
            d.length==kRawBytes && d.address==config_.raw_addresses[d.bank] && d.camera==config_.camera &&
            d.token==((static_cast<std::uint64_t>(d.generation)<<32)|d.sequence) &&
            fits(d.address,coop_host::kRawBytesWithTag,config_.ddr_limit);
    }
    bool verify_held(const Descriptor& expected) {
        Descriptor d;
        std::uint32_t status=0,gen=0;
        if(!read_word(0x118,d.bank) || !descriptor_fields(d,false) || !read_word(0x104,status) ||
           !read_word(0x170,gen)) return false;
        if(!(status&kBound) || !(status&kConfigOK) || (status&kProtocolFault) ||
           gen!=snapshot_.accepted_generation || d.bank!=expected.bank || d.sequence!=expected.sequence ||
           d.generation!=expected.generation || d.length!=expected.length || d.address!=expected.address ||
           d.camera!=expected.camera || d.token!=expected.token) {
            fail(Fault::LeaseChanged);return false;
        }
        return true;
    }
    Transport& transport_;
    const Config config_;
    std::mutex& coordinator_; // Shared operation lock, NOT a per-object substitute.
    Snapshot snapshot_;
};

} // namespace capture_host
#endif
