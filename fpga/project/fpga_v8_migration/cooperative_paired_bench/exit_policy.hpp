#pragma once
#include "bench.hpp"
#include <csignal>
#include <memory>
#include <string>
#if defined(__linux__)
#include <signal.h>
#endif

namespace paired_bench {
// These are references to externally verified provider records, not CLI flags.
struct ActivationEvidence {
    std::string controller_session, bounded_driver_test, transaction_deadline_contract,
                persistent_owner_contract;
};
enum class ExitAuthority { RetiredIdle, ExternalPhysicalRecovery };
struct ExitReceipt {
    ExitAuthority authority;
    std::string controller_session, evidence_record;
    std::uint32_t original_generation=0;
};
class PlatformOwner {
public:
    virtual ~PlatformOwner() = default;
    virtual coop_host::Transport& transport() noexcept = 0;
    virtual ActivationEvidence activation_evidence() const = 0;
    // No I/O: return only a receipt validated from authoritative retired DMA,
    // transport and lease records. No receipt if ANY ownership is uncertain.
    virtual std::optional<ExitReceipt> retired_idle_receipt() const = 0;
    // Latch/quarantine only; MUST NOT ACK/reset/retry/close/unmap/unlock ownership.
    virtual void quarantine(const char* reason) noexcept = 0;
    // Only consume a separately authorized, physically verified recovery record.
    // Never probe/reset hardware or manufacture recovery by elapsed time/signals.
    virtual std::optional<ExitReceipt> authorized_recovery_receipt() const = 0;
};
inline bool activation_valid(const ActivationEvidence& e) {
    return !e.controller_session.empty() && !e.bounded_driver_test.empty() &&
        !e.transaction_deadline_contract.empty() && !e.persistent_owner_contract.empty();
}
inline bool receipt_matches(const ExitReceipt& r,const ActivationEvidence& a,
                            std::uint32_t generation,bool physical_required) {
    return !a.controller_session.empty() && r.controller_session==a.controller_session &&
        r.original_generation==generation && !r.evidence_record.empty() &&
        (!physical_required || r.authority==ExitAuthority::ExternalPhysicalRecovery);
}
class ExitPolicy {
    PlatformOwner& owner_;
    ActivationEvidence activation_;
    std::uint32_t generation_;
    bool held_=false, signal_reported_=false;
public:
    ExitPolicy(PlatformOwner& owner,ActivationEvidence activation,std::uint32_t generation)
        :owner_(owner),activation_(std::move(activation)),generation_(generation) {}
    bool known_idle(bool lease_uncertain) const noexcept {
        if (lease_uncertain || held_) return false;
        try {
            auto r=owner_.retired_idle_receipt();
            return r && receipt_matches(*r,activation_,generation_,false);
        } catch (...) { return false; }
    }
    template<class Report> void enter(const char* reason,Report&& report) noexcept {
        if (held_) return;
        held_=true; owner_.quarantine(reason);
        // Called once, after quarantine latch, before the foreground hold loop.
        try { report(); } catch (...) {} // Evidence failure must NEVER unwind the owner.
    }
    // One finite, fake-testable pass. Production repeats with a short sleep.
    // true permits destruction/exit only after external physical recovery proof.
    template<class SignalReport> bool hold_once(bool signal,SignalReport&& report) noexcept {
        if (!held_) return false;
        if (signal && !signal_reported_) {
            signal_reported_=true;
            try { report(); } catch (...) {}
        }
        try {
            auto r=owner_.authorized_recovery_receipt();
            return r && receipt_matches(*r,activation_,generation_,true);
        } catch (...) { return false; }
    }
};
inline volatile std::sig_atomic_t termination_requested=0;
inline void hold_signal(int signal) {
    termination_requested=signal;
#if !defined(__linux__)
    std::signal(signal,hold_signal); // CRT one-shot handlers need reinstallation.
#endif
}
// Installed before binding, and kept installed until process exit. Signal
// handlers set one flag only: no allocation, I/O, destructor or termination.
inline void install_hold_signals() {
#if defined(__linux__)
    struct sigaction action{};
    action.sa_handler=hold_signal;
    sigemptyset(&action.sa_mask);
    for (int signal : {SIGINT,SIGTERM,SIGHUP,SIGQUIT})
        require(sigaction(signal,&action,nullptr)==0,"cannot install persistent signal hold");
#else
    require(std::signal(SIGINT,hold_signal)!=SIG_ERR,"cannot hold SIGINT");
    require(std::signal(SIGTERM,hold_signal)!=SIG_ERR,"cannot hold SIGTERM");
#if defined(SIGHUP)
    require(std::signal(SIGHUP,hold_signal)!=SIG_ERR,"cannot hold SIGHUP");
#endif
#if defined(SIGQUIT)
    require(std::signal(SIGQUIT,hold_signal)!=SIG_ERR,"cannot hold SIGQUIT");
#endif
#if defined(SIGBREAK)
    require(std::signal(SIGBREAK,hold_signal)!=SIG_ERR,"cannot hold SIGBREAK");
#endif
#endif
}
} // namespace paired_bench
