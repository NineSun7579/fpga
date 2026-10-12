#pragma once
#include "driver_abi.hpp"
#include "../capture_host/capture_host_protocol.hpp"
#include "../reset_fault_guard/session_fault_transport.hpp"
#include <chrono>
#include <cstring>
#include <memory>
#include <string>

namespace cooperative_linux {
using Clock = std::chrono::steady_clock;
using coop_host::IoStatus;
using coop_host::Beat;
using coop_host::DmaResult;
inline constexpr std::uint64_t capacity = 4ULL * 1024 * 1024;
struct Plan {
    std::uint64_t control_end = 256, raw_offset = 256, output_offset = 614672;
    static bool fits(std::uint64_t offset, std::uint64_t bytes) {
        return !(offset & 15U) && offset <= capacity && bytes <= capacity - offset;
    }
    void validate() const {
        if (control_end < 16 || !fits(0, control_end) || (control_end & 15U) ||
            raw_offset < control_end || !fits(raw_offset, 614416) ||
            output_offset < raw_offset + 614416 || !fits(output_offset, 1228800))
            throw std::invalid_argument("disjoint aligned 4MiB RX reservations required");
    }
};
struct Evidence {
    // Provider must validate live receipts, not deserialize these from a manifest.
    std::string device_identity, image_identity, platform_contract, receipt;
    bool exclusive_quiescent_domain = false, image_loaded_decode_verified = false;
    bool fixed_driver_abi_verified = false, coherent_mapping_verified = false;
    bool h2f_retirement_ordered = false, f2h_visibility_fence_verified = false;
    bool valid() const {
        return !device_identity.empty() && !image_identity.empty() &&
            !platform_contract.empty() && !receipt.empty() && exclusive_quiescent_domain &&
            image_loaded_decode_verified && fixed_driver_abi_verified &&
            coherent_mapping_verified && h2f_retirement_ordered && f2h_visibility_fence_verified;
    }
};
struct Completion {
    bool retired = false, ordered = false, cpu_visible = false, response_ok = false;
    std::size_t exact_bytes = 0;
    std::string receipt;
};
class EvidenceProvider {
public:
    virtual ~EvidenceProvider() = default;
    // No device I/O: externally verified identity must precede every device open.
    virtual Evidence preflight(const std::string& physical_domain,
        const std::string& stable_lock_path, const std::string& device, Clock::time_point) = 0;
    // Called after actual bounded ioctl/MSI wait; must prove retirement and, for
    // F2H, a posted-write visibility fence. MSI count/CPU atomic fence is insufficient.
    virtual Completion wait_completed(Command, const DMA_OPERATION&, Clock::time_point) = 0;
    virtual bool close_allowed_idle(const Evidence&, Clock::time_point) = 0;
};
class Syscalls {
public:
    virtual ~Syscalls() = default;
    virtual int owner_lock(const std::string&) = 0; // flock, OFD lifetime, 0600/NOFOLLOW
    virtual bool no_device_owners(const std::string&) = 0; // exhaustive /proc; fail closed
    virtual int open_device(const std::string&) = 0;
    virtual int ioctl_until(int, Command, DMA_OPERATION&, Clock::time_point) = 0;
    virtual std::uint8_t* map(int, bool rx, std::size_t) = 0;
    virtual void unmap(std::uint8_t*, std::size_t) noexcept = 0;
    virtual void close_fd(int) noexcept = 0;
};
struct Snapshot { bool opened = false, quarantined = false, active = false; int error = 0; };
class Backend final : public coop_host::Transport {
    struct Owner {
        std::shared_ptr<Syscalls> sys;
        std::shared_ptr<EvidenceProvider> provider;
        std::mutex io, coordinator;
        int lock = -1, fd = -1;
        std::uint8_t *tx = nullptr, *rx = nullptr;
        Evidence evidence;
        Snapshot snapshot;
    };
    std::shared_ptr<Owner> owner_;
    Plan plan_;
    std::string domain_, lock_path_, device_;
    reset_fault_guard::SessionFaultTransport guarded_;
    static void pin(const std::shared_ptr<Owner>& owner) {
        // Deliberately never destroyed at static teardown. Explicit idle close is
        // the ONLY resource release. Keeps provider/syscalls alive after errors.
        static auto* pins = new std::vector<std::shared_ptr<Owner>>;
        static auto* mutex = new std::mutex;
        std::lock_guard<std::mutex> lock(*mutex);
        pins->push_back(owner);
    }
    void quarantine(int error = 0) noexcept {
        owner_->snapshot.quarantined = true;
        owner_->snapshot.error = error;
    }
    bool ready() const { return owner_->snapshot.opened && !owner_->snapshot.quarantined; }
    static bool control(std::uint32_t address) {
        for (const auto& reg : coop_host::kRegisters)
            if (address == coop_host::physical_address(reg.local)) return true;
        for (const auto& reg : capture_host::kRegisters)
            if (address == coop_host::physical_address(reg.local)) return true;
        return false;
    }
    Completion transfer(Command command, std::uint32_t address, std::uint64_t offset,
                        std::size_t bytes) {
        DMA_OPERATION op{};
        op.offset_addr = static_cast<unsigned int>(offset);
        op.ddr3_addr = address; op.total_length = static_cast<unsigned int>(bytes);
        // current_len/cmd/data all zero, matching frozen PangoDev DmaOp submissions.
        owner_->snapshot.active = true;
        const auto deadline = Clock::now() + std::chrono::seconds(4);
        try {
            const int error = owner_->sys->ioctl_until(owner_->fd, command, op, deadline);
            if (error) { quarantine(error); return {}; }
            auto completion = owner_->provider->wait_completed(command, op, deadline);
            if (Clock::now() > deadline || !completion.retired || !completion.ordered ||
                completion.exact_bytes != bytes || completion.receipt.empty() ||
                (command == Command::F2H && !completion.cpu_visible)) {
                quarantine(); return {};
            }
            owner_->snapshot.active = false;
            return completion;
        } catch (...) { quarantine(); return {}; }
    }
public:
    Backend(std::shared_ptr<Syscalls> sys, std::shared_ptr<EvidenceProvider> provider,
            std::string physical_domain, std::string stable_lock_path,
            std::string device = "/dev/pango_pci_driver", Plan plan = {})
        : owner_(std::make_shared<Owner>()), plan_(plan), domain_(std::move(physical_domain)),
          lock_path_(std::move(stable_lock_path)), device_(std::move(device)),
          guarded_(*this, coop_host::physical_address(0x104)) {
        plan_.validate();
        if (!sys || domain_.empty() || lock_path_.empty() || device_.empty())
            throw std::invalid_argument("explicit physical domain and stable lock required");
        owner_->sys = std::move(sys); owner_->provider = std::move(provider);
    }
    Backend(const Backend&) = delete;
    Backend& operator=(const Backend&) = delete;
    ~Backend() override = default; // No device release, unmap, ACK, or retry.
    // Runtime gate is not independent board proof: provider is a trusted boundary.
    bool preflight() {
        std::lock_guard<std::mutex> lock(owner_->io);
        if (!owner_->provider || owner_->snapshot.opened || owner_->snapshot.quarantined) return false;
        const auto deadline = Clock::now()+std::chrono::seconds(4);
        owner_->evidence = owner_->provider->preflight(domain_, lock_path_, device_, deadline);
        if (Clock::now() > deadline) owner_->evidence = {};
        return owner_->evidence.valid();
    }
    bool open_checked() {
        std::lock_guard<std::mutex> lock(owner_->io);
        if (!owner_->evidence.valid() || owner_->snapshot.opened || owner_->snapshot.quarantined)
            return false;
        // Refresh external identity immediately before ownership acquisition.
        const auto deadline = Clock::now()+std::chrono::seconds(4);
        owner_->evidence = owner_->provider->preflight(domain_, lock_path_, device_, deadline);
        if (Clock::now() > deadline || !owner_->evidence.valid()) return false;
        owner_->lock = owner_->sys->owner_lock(lock_path_);
        if (owner_->lock < 0) return false;
        pin(owner_); // Before any possible side effect, including throwing open/map.
        try {
            if (!owner_->sys->no_device_owners(device_)) {
                owner_->sys->close_fd(owner_->lock); owner_->lock = -1; return false;
            }
            owner_->fd = owner_->sys->open_device(device_);
            if (owner_->fd < 0) {
                owner_->sys->close_fd(owner_->lock); owner_->lock = -1; return false;
            }
            for (unsigned int side = 0; side < 2; ++side) {
                DMA_OPERATION op{}; op.cmd = side; op.total_length = static_cast<unsigned int>(capacity);
                const int error = owner_->sys->ioctl_until(owner_->fd, Command::Map, op,
                    Clock::now()+std::chrono::seconds(4));
                // EBUSY cannot be cleaned up by release: it may free someone else's pages.
                if (error) { quarantine(error); return false; }
            }
            owner_->tx = owner_->sys->map(owner_->fd, false, static_cast<std::size_t>(capacity));
            owner_->rx = owner_->sys->map(owner_->fd, true, static_cast<std::size_t>(capacity));
            if (!owner_->tx || !owner_->rx) { quarantine(); return false; }
            owner_->snapshot.opened = true; return true;
        } catch (...) { quarantine(); return false; }
    }
    // The shared helper coordinator must be held across entire helper operations.
    // Lock order: coordinator -> helper mutex -> backend io. RAW already locks it;
    // wrap cooperative operations with capture_host::with_exclusive_io.
    std::mutex& coordinator() { return owner_->coordinator; }
    coop_host::Transport& guarded_transport() { return guarded_; }
    Snapshot snapshot() const {
        std::lock_guard<std::mutex> lock(owner_->io); return owner_->snapshot;
    }
    bool close_allowed_idle() {
        std::lock_guard<std::mutex> operation(owner_->coordinator);
        std::lock_guard<std::mutex> lock(owner_->io);
        const auto deadline = Clock::now()+std::chrono::seconds(4);
        if (!ready() || owner_->snapshot.active || !owner_->provider->close_allowed_idle(
                owner_->evidence, deadline) || Clock::now() > deadline) return false;
        owner_->sys->unmap(owner_->tx, static_cast<std::size_t>(capacity));
        owner_->sys->unmap(owner_->rx, static_cast<std::size_t>(capacity));
        owner_->sys->close_fd(owner_->fd); owner_->sys->close_fd(owner_->lock);
        owner_->tx = owner_->rx = nullptr; owner_->fd = owner_->lock = -1;
        owner_->snapshot.opened = false; owner_->evidence = {}; return true;
    }
    IoStatus read16(std::uint32_t address, Beat& destination) override {
        std::lock_guard<std::mutex> lock(owner_->io);
        if (!ready()) return IoStatus::Uncertain;
        if (!control(address)) return IoStatus::KnownRejected;
        const auto result = transfer(Command::F2H, address, 0, 16);
        if (!result.retired) return IoStatus::Uncertain;
        destination.fill(0); std::memcpy(destination.data(), owner_->rx, 4);
        return result.response_ok ? IoStatus::KnownOK : IoStatus::DeliveryKnownUnknownResponse;
    }
    IoStatus write16(std::uint32_t address, const Beat& source) override {
        std::lock_guard<std::mutex> lock(owner_->io);
        if (!ready()) return IoStatus::Uncertain;
        if (!control(address)) return IoStatus::KnownRejected;
        for (std::size_t i = 4; i < source.size(); ++i)
            if (source[i]) return IoStatus::KnownRejected;
        std::memset(owner_->tx, 0, 16); std::memcpy(owner_->tx, source.data(), 4);
        const auto result = transfer(Command::H2F, address, 0, 16);
        if (!result.retired) return IoStatus::Uncertain;
        // Legacy H2F has no BRESP. Never upgrade ioctl success to KnownOK.
        return IoStatus::DeliveryKnownUnknownResponse;
    }
    DmaResult copy_ddr_blocking(std::uint32_t address, std::uint64_t offset,
                               std::vector<std::uint8_t>& destination) override {
        std::lock_guard<std::mutex> lock(owner_->io);
        if (!ready()) return {IoStatus::Uncertain, 0};
        const bool raw = (address == 0x01800000U || address == 0x01a00000U) &&
            offset == plan_.raw_offset && destination.size() == 614400;
        const bool output = (address == 0x08000000U || address == 0x08200000U) &&
            offset == plan_.output_offset && destination.size() == 1228800;
        if ((!raw && !output) || !Plan::fits(offset, destination.size()))
            return {IoStatus::KnownRejected, 0};
        const auto result = transfer(Command::F2H, address, offset, destination.size());
        if (!result.retired) return {IoStatus::Uncertain, 0};
        if (!result.response_ok) return {IoStatus::DeliveryKnownUnknownResponse, 0};
        std::memcpy(destination.data(), owner_->rx + offset, destination.size());
        return {IoStatus::KnownOK, destination.size()};
    }
};
}
