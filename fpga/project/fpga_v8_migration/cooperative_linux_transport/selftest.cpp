#include "transport.hpp"
#include <algorithm>
#include <iostream>
#include <limits>

using namespace cooperative_linux;
static_assert(std::is_same<decltype(&coop_host::Transport::read16),
    IoStatus (coop_host::Transport::*)(std::uint32_t, Beat&)>::value, "read16 signature preserved");
static_assert(std::is_same<decltype(&coop_host::Transport::write16),
    IoStatus (coop_host::Transport::*)(std::uint32_t, const Beat&)>::value, "write16 signature preserved");
static_assert(std::is_same<decltype(&coop_host::Transport::copy_ddr_blocking),
    DmaResult (coop_host::Transport::*)(std::uint32_t, std::uint64_t,
        std::vector<std::uint8_t>&)>::value, "DmaResult signature preserved");
static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
struct FakeSys final : Syscalls {
    std::vector<std::uint8_t> tx = std::vector<std::uint8_t>(static_cast<std::size_t>(capacity));
    std::vector<std::uint8_t> rx = tx;
    struct Trace { Command cmd; DMA_OPERATION op; };
    std::vector<Trace> trace;
    int opens = 0, closes = 0, unmaps = 0, locks = 0;
    int error = 0; bool owners_absent = true, lock_available = true;
    int owner_lock(const std::string&) override { ++locks; return lock_available ? 7 : -1; }
    bool no_device_owners(const std::string&) override { return owners_absent; }
    int open_device(const std::string&) override { ++opens; return 8; }
    int ioctl_until(int, Command cmd, DMA_OPERATION& op, Clock::time_point) override {
        trace.push_back({cmd, op});
        require(op.data.read_buf == nullptr && op.data.write_buf == nullptr, "no vector DMA pointers");
        if (error) return error;
        if (cmd == Command::F2H) {
            if (op.ddr3_addr == coop_host::physical_address(0x104))
                std::fill(rx.begin(), rx.begin()+16, std::uint8_t{0});
            else std::fill(rx.begin()+op.offset_addr, rx.begin()+op.offset_addr+op.total_length,
                std::uint8_t{0x5a});
        }
        return 0;
    }
    std::uint8_t* map(int, bool receive, std::size_t bytes) override {
        require(bytes == capacity, "actual mapped capacity"); return receive ? rx.data() : tx.data();
    }
    void unmap(std::uint8_t*, std::size_t) noexcept override { ++unmaps; }
    void close_fd(int) noexcept override { ++closes; }
};
struct FakeProvider final : EvidenceProvider {
    bool admit = true, visible = true, retired = true, response = true, exact = true;
    int completed = 0;
    Evidence preflight(const std::string&, const std::string&, const std::string&,
                       Clock::time_point) override {
        Evidence e;
        if (admit) {
            e.device_identity="fake-device"; e.image_identity="fake-image";
            e.platform_contract="FAKE TEST ONLY"; e.receipt="fake-preflight";
            e.exclusive_quiescent_domain=e.image_loaded_decode_verified=e.fixed_driver_abi_verified=true;
            e.coherent_mapping_verified=e.h2f_retirement_ordered=e.f2h_visibility_fence_verified=true;
        }
        return e;
    }
    Completion wait_completed(Command, const DMA_OPERATION& op, Clock::time_point) override {
        ++completed;
        return {retired, true, visible, response, exact ? op.total_length : 0U, "fake-completion"};
    }
    bool close_allowed_idle(const Evidence&, Clock::time_point) override { return true; }
};
static void run() {
    require(!Evidence{}.valid(), "default evidence refuses activation");
    Plan{}.validate();
    for (auto value : {std::uint64_t{1}, capacity, std::numeric_limits<std::uint64_t>::max()}) {
        Plan invalid; invalid.raw_offset=value;
        bool rejected=false;
        try { invalid.validate(); } catch (const std::invalid_argument&) { rejected=true; }
        require(rejected, "invalid/overflow plan rejected");
    }
    auto s=std::make_shared<FakeSys>(); auto p=std::make_shared<FakeProvider>();
    {
        Backend backend(s, {}, "domain", "stable-path");
        require(!backend.preflight() && !backend.open_checked() && s->opens==0 && s->locks==0,
            "absent provider zero syscalls");
    }
    {
        p->admit=false; Backend backend(s,p,"domain","stable-path");
        require(!backend.preflight() && !backend.open_checked() && s->opens==0, "absent evidence");
        p->admit=true;
    }
    {
        s->owners_absent=false; Backend backend(s,p,"domain","stable-path");
        require(backend.preflight() && !backend.open_checked() && s->opens==0 && s->trace.empty(),
            "existing owner refuses BEFORE device open"); s->owners_absent=true;
    }
    {
        s->lock_available=false; Backend backend(s,p,"domain","stable-path");
        require(backend.preflight() && !backend.open_checked() && s->opens==0, "second owner refused");
        s->lock_available=true;
    }
    s=std::make_shared<FakeSys>(); p=std::make_shared<FakeProvider>();
    {
        Backend backend(s,p,"domain","stable-path");
        require(s->opens==0 && s->trace.empty(), "constructor performs no IO");
        require(backend.preflight() && backend.open_checked(), "fake open");
        require(s->trace.size()==2 && s->trace[0].op.cmd==0 && s->trace[1].op.cmd==1 &&
            s->trace[0].op.total_length==capacity, "TX/RX allocation ABI");
        auto& transport=backend.guarded_transport();
        auto word=coop_host::encode_word(0x12345678);
        require(transport.write16(coop_host::physical_address(0x30),word)==
            IoStatus::DeliveryKnownUnknownResponse, "legacy no BRESP");
        require(s->trace.back().cmd==Command::H2F && s->trace.back().op.total_length==16 &&
            s->trace.back().op.offset_addr==0, "singleton aligned 16B H2F");
        require(std::equal(word.begin(),word.end(),s->tx.begin()), "TX upper96 zero");
        word[15]=1;
        const auto before=s->trace.size();
        require(backend.write16(coop_host::physical_address(0x30),word)==IoStatus::KnownRejected &&
            s->trace.size()==before, "reject nonzero upper96 before DMA");
        Beat beat{};
        require(backend.read16(coop_host::physical_address(0),beat)==IoStatus::KnownOK &&
            coop_host::decode_word(beat)==0x5a5a5a5aU && beat[4]==0, "read low32 zero upper96");
        std::vector<std::uint8_t> raw(614400), output(1228800);
        const auto raw_result=transport.copy_ddr_blocking(0x01800000,256,raw);
        require(raw_result.status==IoStatus::KnownOK && raw_result.bytes==raw.size() &&
            s->trace.back().op.total_length==614400, "RAW exact payload excludes reserved tag");
        const auto output_result=transport.copy_ddr_blocking(0x08000000,614672,output);
        require(output_result.status==IoStatus::KnownOK && output_result.bytes==output.size() &&
            s->trace.back().op.total_length==1228800, "output exact bytes");
        std::fill(s->rx.begin(),s->rx.end(),std::uint8_t{0xff});
        require(raw.front()==0x5a && raw.back()==0x5a && output.front()==0x5a && output.back()==0x5a,
            "owned copy survives immediate RX overwrite");
        require(backend.copy_ddr_blocking(0x01800000,std::numeric_limits<std::uint64_t>::max(),raw).status==
            IoStatus::KnownRejected, "overflow offset rejects");
        require(backend.close_allowed_idle() && s->closes==2 && s->unmaps==2, "explicit idle close");
    }
    for (int failure=0; failure<4; ++failure) {
        s=std::make_shared<FakeSys>(); p=std::make_shared<FakeProvider>();
        {
            Backend backend(s,p,"domain","stable-path");
            require(backend.preflight() && backend.open_checked(), "failure setup");
            if (failure==0) s->error=110; // ETIMEDOUT shim, not a hardware test
            if (failure==1) p->visible=false;
            if (failure==2) p->retired=false;
            if (failure==3) p->exact=false;
            std::vector<std::uint8_t> raw(614400,0x33);
            require(backend.copy_ddr_blocking(0x01800000,256,raw).status==IoStatus::Uncertain &&
                raw.front()==0x33, "uncertain copy never publishes bytes");
            auto state=backend.snapshot();
            require(state.quarantined && state.active, "active quarantine snapshot");
            const auto before=s->trace.size();
            require(backend.write16(coop_host::physical_address(0x4c),coop_host::encode_word(1))==
                IoStatus::Uncertain && s->trace.size()==before && !backend.close_allowed_idle(),
                "uncertain no ACK/retry/release");
        }
        require(s->closes==0 && s->unmaps==0, "destructor retains fd/maps");
    }
    s=std::make_shared<FakeSys>(); p=std::make_shared<FakeProvider>();
    {
        Backend backend(s,p,"domain","stable-path");
        require(backend.preflight() && backend.open_checked(), "unknown response setup");
        p->response=false;
        std::vector<std::uint8_t> raw(614400,0x33);
        const auto result=backend.copy_ddr_blocking(0x01800000,256,raw);
        require(result.status==IoStatus::DeliveryKnownUnknownResponse && result.bytes==0 &&
            raw.front()==0x33, "F2H unknown response never KnownOK/copy");
        Beat beat{};
        require(backend.guarded_transport().read16(coop_host::physical_address(0),beat)==
            IoStatus::Uncertain, "STATUS guard requires KnownOK, unknown RRESP refuses");
        const auto before=s->trace.size();
        require(backend.guarded_transport().write16(coop_host::physical_address(0x4c),
            coop_host::encode_word(1))==IoStatus::Uncertain && s->trace.size()==before,
            "stopped status guard emits no ACK");
    }
    s=std::make_shared<FakeSys>(); p=std::make_shared<FakeProvider>();
    {
        Backend backend(s,p,"domain","stable-path"); s->error=16; // EBUSY allocation
        require(backend.preflight() && !backend.open_checked() && backend.snapshot().quarantined &&
            backend.snapshot().error==16 && s->trace.size()==1, "EBUSY stops allocation");
    }
    require(s->closes==0 && s->unmaps==0, "EBUSY cannot release global foreign allocation");
}
int main() {
    try { run(); std::cout << "PASS portable fake-syscall transport tests; no hardware accessed\n"; }
    catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
