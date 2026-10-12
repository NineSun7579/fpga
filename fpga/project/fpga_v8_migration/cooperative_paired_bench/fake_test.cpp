#include "bench.hpp"
#include "exit_policy.hpp"
#include <iostream>
#include <map>
using namespace paired_bench;
class FakeTransport final : public coop_host::Transport {
public:
    std::map<std::uint32_t,std::uint32_t> regs;
    std::uint32_t generation=0,sequence=1;
    bool raw_bound=false,out_bound=false,raw_done=false,out_done=false,fault=false,busy=false;
    bool short_copy=false,bad_rgb=false,bad_identity=false,uncertain_ack=false,vary_raw=false;
    bool fault_after_raw=false;
    unsigned reads=0,writes=0,copies=0,ack_attempts=0;
    static std::uint32_t local(std::uint32_t p) { return (p-coop_host::kControlBase)/4; }
    std::uint32_t value(std::uint32_t l) {
        using namespace capture_host;
        if (l==0x100) return kDeviceId;
        if (l==0) return coop_host::kDeviceId;
        if (l==0x108 || l==8) return kVersion;
        if (l==0x104) return kConfigOK | (fault ? kProtocolFault : 0) |
            (generation ? kArmed : kConfigReady) | (raw_bound ? kBound : 0) |
            (generation && !raw_bound && !raw_done && !busy ? kOffered : 0);
        if (l==0x170) return generation;
        if (l==0x118) return raw_bound ? 0 : kNoBank;
        if (l==0x11c) return sequence;
        if (l==0x120) return generation;
        if (l==0x124) return kRawBytes;
        if (l==0x128) return 0x01800000;
        if (l==0x12c) return 4;
        if (l==0x130) return sequence;
        if (l==0x134) return generation;
        if (l==4) return out_bound ? 8 : 0;
        if (l==0x0c) return !out_done && !busy && generation ? 0 : kNoBank;
        if (l==0x10) return out_bound ? 0 : kNoBank;
        if (l==0x14) return sequence+(bad_identity ? 1 : 0);
        if (l==0x18) return generation;
        if (l==0x1c) return coop_host::kFrameBytes;
        if (l==0x20) return 0x08000000;
        if (l==0x24) return 4;
        if (l==0x28) return 0;
        if (l==0x2c) return 0x01800000;
        if (l==0x34) return sequence;
        if (l==0x38) return generation;
        return regs[l];
    }
    coop_host::IoStatus read16(std::uint32_t p,coop_host::Beat& b) override {
        ++reads; b=coop_host::encode_word(value(local(p))); return coop_host::IoStatus::KnownOK;
    }
    coop_host::IoStatus write16(std::uint32_t p,const coop_host::Beat& b) override {
        ++writes; auto l=local(p),v=coop_host::decode_word(b); regs[l]=v;
        if (l==0x110) { generation=regs[0x10c]; ++regs[0x174]; }
        if (l==0x114) { raw_bound=true; ++regs[0x17c]; }
        if (l==0x30) out_bound=true;
        if (l==0x150 || l==0x4c) {
            ++ack_attempts;
            if (uncertain_ack) return coop_host::IoStatus::Uncertain;
            if (l==0x150) { raw_done=true; raw_bound=false; ++regs[0x178]; }
            else { out_done=true; out_bound=false; }
        }
        return coop_host::IoStatus::KnownOK;
    }
    coop_host::DmaResult copy_ddr_blocking(std::uint32_t address,std::uint64_t offset,
                                          std::vector<std::uint8_t>& dest) override {
        ++copies;
        require(offset==(address==0x01800000 ? 0x1000U : 0x97000U),"RX slots changed");
        std::vector<std::uint8_t> raw(capture_host::kRawBytes, vary_raw ? std::uint8_t(sequence) : 0x35);
        if (address==0x01800000) dest=raw;
        else { dest=fpga_v8_raw::prepare(raw.data(),raw.size()); if (bad_rgb) ++dest[17]; }
        if (fault_after_raw && address==0x01800000) fault=true;
        return {coop_host::IoStatus::KnownOK,dest.size()-(short_copy ? 16 : 0)};
    }
    void next() { require(raw_done && out_done,"reuse while obligations active");
        ++sequence; raw_done=out_done=false; }
};
struct FakeRunner final : Runner {
    FakeTransport& transport;
    unsigned completes=0;
    bool fail_get=false,fail_release=false;
    explicit FakeRunner(FakeTransport& t):transport(t) {}
    Inference complete(Profile,const std::vector<std::uint8_t>& rgb) override {
        require(rgb.size()==coop_host::kFrameBytes,"inference partial input");
        require(!fail_get,"injected outputs_get failure");
        require(!fail_release,"injected outputs_release failure");
        ++completes;
        return {{{1,2,3,4,0.5f,1}}, {}};
    }
    void close() override {}
};
// Publication happens on the first status poll after both ACKs. This keeps
// descriptor registers stable through ACK observation; no synthetic host ACK.
class AdvancingTransport final : public coop_host::Transport {
    FakeTransport& fake_;
public:
    explicit AdvancingTransport(FakeTransport& f):fake_(f) {}
    coop_host::IoStatus read16(std::uint32_t p,coop_host::Beat& b) override {
        // The output ACK's final reads are HOST_BANK and STATUS, so defer next
        // source until a later RAW device identity read.
        if (p==coop_host::physical_address(0x100) && fake_.raw_done && fake_.out_done) fake_.next();
        return fake_.read16(p,b);
    }
    coop_host::IoStatus write16(std::uint32_t p,const coop_host::Beat& b) override { return fake_.write16(p,b); }
    coop_host::DmaResult copy_ddr_blocking(std::uint32_t p,std::uint64_t o,std::vector<std::uint8_t>& b) override {
        return fake_.copy_ddr_blocking(p,o,b);
    }
};
capture_host::Config raw_config() {
    capture_host::Config c; c.control_rx_slots_end=0x1000; c.raw_rx_offset=0x1000;
    c.output_rx_offset=0x97000; c.rx_capacity=c.output_rx_offset+coop_host::kFrameBytes; return c;
}
coop_host::Config output_config() {
    coop_host::Config c; c.expected_generation=7; auto r=raw_config();
    c.control_rx_slots_end=r.control_rx_slots_end; c.rx_capacity=r.rx_capacity;
    c.frame_rx_offset=r.output_rx_offset; return c;
}
struct FakeOwner final : PlatformOwner {
    FakeTransport backend;
    unsigned& destroyed;
    unsigned quarantines=0,idle_observations=0,recovery_observations=0;
    mutable std::optional<ExitReceipt> idle,recovery;
    explicit FakeOwner(unsigned& count):destroyed(count) {}
    ~FakeOwner() override { ++destroyed; }
    coop_host::Transport& transport() noexcept override { return backend; }
    ActivationEvidence activation_evidence() const override {
        return {"fake-session","fake-bounded-driver-test","fake-deadline-record","fake-retention-record"};
    }
    std::optional<ExitReceipt> retired_idle_receipt() const override { return idle; }
    void quarantine(const char*) noexcept override { ++quarantines; }
    std::optional<ExitReceipt> authorized_recovery_receipt() const override { return recovery; }
};
static unsigned lifecycle_tests() {
    unsigned cases=0,destroyed=0,reports=0,signal_decisions=0;
    {
        auto owner=std::make_unique<FakeOwner>(destroyed);
        auto activation=owner->activation_evidence(); require(activation_valid(activation),"fake activation evidence");
        ExitPolicy policy(*owner,activation,7);
        require(!policy.known_idle(false),"missing receipt allowed exit");
        owner->idle=ExitReceipt{ExitAuthority::RetiredIdle,"fake-session","retired DMA/lease record",7};
        require(policy.known_idle(false) && !policy.known_idle(true),"uncertain lease accepted idle receipt");
        policy.enter("uncertain DMA",[&] { ++reports; });
        policy.enter("second failure",[&] { ++reports; });
        require(reports==1 && owner->quarantines==1 && !policy.known_idle(false),"quarantine/report repeated");
        // Finite injected passes; no waiting, hardware recovery, constructor or ARM.
        for (unsigned pass=0;pass<3;++pass) {
            require(!policy.hold_once(true,[&] { ++signal_decisions; }),"signal caused unsafe exit");
            require(destroyed==0 && owner->backend.writes==0,"owner released or hardware I/O in hold");
        }
        require(signal_decisions==1,"repeated signal decision");
        owner->recovery=ExitReceipt{ExitAuthority::RetiredIdle,"fake-session","ordinary idle",7};
        require(!policy.hold_once(false,[] {}),"idle receipt substituted for physical recovery");
        owner->recovery=ExitReceipt{ExitAuthority::ExternalPhysicalRecovery,"other-session","physical proof",7};
        require(!policy.hold_once(false,[] {}),"other controller session proof accepted");
        owner->recovery=ExitReceipt{ExitAuthority::ExternalPhysicalRecovery,"fake-session","physical proof",8};
        require(!policy.hold_once(false,[] {}),"other generation proof accepted");
        owner->recovery=ExitReceipt{ExitAuthority::ExternalPhysicalRecovery,"fake-session","",7};
        require(!policy.hold_once(false,[] {}),"empty recovery record accepted");
        owner->recovery=ExitReceipt{ExitAuthority::ExternalPhysicalRecovery,"fake-session","authorized physical proof",7};
        require(policy.hold_once(false,[] {}),"physical recovery proof rejected");
        require(owner->backend.writes==0,"recovery auto ARM/ACK/reset"); ++cases;
    }
    require(destroyed==1,"owner not released after verified physical recovery");
    {
        FakeOwner owner(destroyed); auto activation=owner.activation_evidence();
        activation.bounded_driver_test.clear(); require(!activation_valid(activation),"unbounded backend activated");
        activation=owner.activation_evidence(); activation.persistent_owner_contract.clear();
        require(!activation_valid(activation),"missing persistent holder activated"); ++cases;
    }
    {
        FakeOwner owner(destroyed); ExitPolicy policy(owner,owner.activation_evidence(),7);
        policy.enter("evidence write failure",[] { throw std::runtime_error("disk failed"); });
        require(!policy.hold_once(false,[] {}) && owner.quarantines==1,"report failure unwound retention"); ++cases;
    }
    {
        termination_requested=0;
        install_hold_signals(); std::raise(SIGTERM); std::raise(SIGTERM);
        require(termination_requested==SIGTERM,"repeated termination handler did not retain process");
        termination_requested=0; ++cases;
    }
    return cases;
}
int main() {
    try {
        unsigned cases=0;
        auto test=[&](auto inject,bool fail,bool run_full=false) {
            FakeTransport fake; AdvancingTransport backend(fake); std::mutex mutex;
            Receiver receiver(backend,mutex,raw_config(),{true,true,true,true,true,true,true,true,true,true},
                              output_config(),{true,true,true,true,true,true,true});
            receiver.arm({7,true,true}); inject(fake); FakeRunner runner(fake);
            bool threw=false;
            try {
                if (run_full) {
                    auto e=run(receiver,runner,4,1,2);
                    require(e.paired.size()==4 && e.blocks.size()==4 && runner.completes==16,"counts/ABBA");
                    require(e.input_sequence_equal!=fake.vary_raw,"inventory did not detect changing inputs");
                    require(!e.acceptance,"fake accepted hardware speedup"); report(std::cout,e);
                } else { receiver.acquire(std::chrono::milliseconds(8)); }
            } catch (...) { threw=true; }
            require(threw==fail,"failure expectation");
            if (fail) {
                require(receiver.terminal(),"receiver not terminal");
                auto before=fake.writes; try { receiver.acquire(); } catch (...) {}
                require(fake.writes==before,"retry after terminal");
                if (fake.uncertain_ack) require(fake.ack_attempts==1 && receiver.evidence().raw.complete,"ACK bytes/retry");
                if (fake.short_copy) require(fake.ack_attempts==0,"ACK partial copy");
                if (fake.busy) require(fake.reads<100,"busy polling storm");
            }
            ++cases;
        };
        test([](auto&){},false,true);
        test([](auto& f){f.vary_raw=true;},false,true);
        test([](auto& f){f.short_copy=true;},true);
        test([](auto& f){f.uncertain_ack=true;},true);
        test([](auto& f){f.fault=true;},true);
        test([](auto& f){f.bad_rgb=true;},true);
        test([](auto& f){f.bad_identity=true;},true);
        test([](auto& f){f.busy=true;},true);
        test([](auto& f){f.fault_after_raw=true;},true);
        for (bool get_failure : {true,false}) {
            FakeTransport fake; AdvancingTransport backend(fake); std::mutex mutex;
            Receiver receiver(backend,mutex,raw_config(),{true,true,true,true,true,true,true,true,true,true},
                              output_config(),{true,true,true,true,true,true,true});
            receiver.arm({7,true,true}); FakeRunner runner(fake);
            runner.fail_get=get_failure; runner.fail_release=!get_failure;
            bool threw=false; try { run(receiver,runner,1,1,1); } catch (...) { threw=true; }
            require(threw && runner.completes==0,"failed get/release counted as completion"); ++cases;
        }
        {
            FakeTransport fake; AdvancingTransport backend(fake); std::mutex mutex;
            Receiver receiver(backend,mutex,raw_config(),{true,true,true,true,true,true,true,true,true,true},
                              output_config(),{true,true,true,true,true,true,true});
            bool threw=false; try { receiver.arm({7,false,true}); } catch (...) { threw=true; }
            require(threw && fake.reads==0 && fake.writes==0,"implicit fresh generation authorization"); ++cases;
        }
        {
            FakeTransport fake; AdvancingTransport backend(fake); std::mutex mutex;
            Receiver receiver(backend,mutex,raw_config(),{true,true,true,true,true,true,true,true,true,true},
                              output_config(),{true,true,true,true,true,true,true});
            receiver.arm({7,true,true}); const auto& first=receiver.acquire();
            auto owned=first.raw.bytes; const auto* reserved=first.raw.bytes.data(); receiver.recycle();
            const auto& second=receiver.acquire();
            require(second.raw.bytes.data()==reserved && owned.front()==0x35,"owned preallocated storage lost");
            receiver.recycle(); ++cases;
        }
        std::cout << "fake cases passed=" << cases << '\n';
        std::cout << "quarantine lifecycle cases passed=" << lifecycle_tests() << '\n'; return 0;
    } catch (const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
