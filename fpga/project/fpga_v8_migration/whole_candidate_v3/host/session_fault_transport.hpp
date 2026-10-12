#pragma once
#include "../cooperative_host/coop_host_protocol.hpp"

namespace reset_fault_guard {
// Candidate decorator for BOTH existing helpers, under their existing owner/mutex.
// read16 must be an ordered, actually retired read with a stable CPU copy.
// It is not a DMA fence or an independent-reset recovery receipt.
class SessionFaultTransport final : public coop_host::Transport {
    coop_host::Transport& backend_;
    const std::uint32_t raw_status_physical_;
    bool stopped_=false;
    bool check() {
        if(stopped_) return false;
        coop_host::Beat beat{};
        try {
            if(backend_.read16(raw_status_physical_,beat)!=coop_host::IoStatus::KnownOK ||
               (beat[0]&4U)) stopped_=true;
        } catch (...) { stopped_=true; throw; }
        return !stopped_;
    }
public:
    SessionFaultTransport(coop_host::Transport& backend, std::uint32_t raw_status_physical)
        :backend_(backend),raw_status_physical_(raw_status_physical) {}
    bool stopped() const { return stopped_; }
    coop_host::IoStatus read16(std::uint32_t address, coop_host::Beat& beat) override {
        if(!check()) return coop_host::IoStatus::Uncertain;
        try {
            const auto result=backend_.read16(address,beat);
            if(result==coop_host::IoStatus::Uncertain) stopped_=true;
            return result;
        } catch (...) { stopped_=true; throw; }
    }
    coop_host::IoStatus write16(std::uint32_t address,const coop_host::Beat& beat) override {
        if(!check()) return coop_host::IoStatus::Uncertain;
        try {
            const auto result=backend_.write16(address,beat);
            if(result==coop_host::IoStatus::Uncertain) stopped_=true;
            return result;
        } catch (...) { stopped_=true; throw; }
    }
    coop_host::DmaResult copy_ddr_blocking(std::uint32_t address,std::uint64_t offset,
                                        std::vector<std::uint8_t>& bytes) override {
        if(!check()) return {coop_host::IoStatus::Uncertain,0};
        try {
            const auto result=backend_.copy_ddr_blocking(address,offset,bytes);
            if(result.status!=coop_host::IoStatus::KnownOK || result.bytes!=bytes.size()) stopped_=true;
            return result;
        } catch (...) { stopped_=true; throw; }
    }
};
}
