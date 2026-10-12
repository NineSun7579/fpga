#include "provider.hpp"
#include "cooperative_linux_transport/driver_abi.hpp"
#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <csignal>
#include <iostream>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <thread>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <unistd.h>

namespace delivery {
namespace {
constexpr std::uint32_t Base=0x40020000, RawBytes=640*480*2, RgbBytes=640*640*3;
constexpr std::size_t Window=4*1024*1024;
void check(bool ok,const char* why) { if (!ok) throw std::runtime_error(why); }
// Retained driver has global buffers and open/release side effects. A separate
// benchmark must run as root after the coordinated viewer stop, never overlap it.
void no_existing_owner() {
    check(::geteuid()==0,"run as root to audit every driver owner before open");
    for (const auto& process:std::filesystem::directory_iterator("/proc")) {
        const auto name=process.path().filename().string();
        if (name.empty() || name.find_first_not_of("0123456789")!=std::string::npos) continue;
        std::error_code ec;
        std::filesystem::directory_iterator fds(process.path()/"fd",ec);
        if (ec==std::errc::no_such_file_or_directory) continue;
        check(!ec,"cannot audit process descriptors");
        for (const auto& fd:fds) {
            auto target=std::filesystem::read_symlink(fd.path(),ec);
            if (ec==std::errc::no_such_file_or_directory) continue;
            check(!ec,"cannot inspect process descriptor");
            check(target.string()!="/dev/pango_pci_driver","driver still owned by another process");
        }
    }
}
class LinuxProvider final:public Provider {
    int lock_=-1,fd_=-1;
    std::uint8_t *tx_=nullptr,*rx_=nullptr;
    bool terminal_=false,leased_=false,closed_=false,parked_=false;
    bool trace_=std::getenv("DELIVERY_TRACE_DMA")!=nullptr;
    Lease lease_{};
    std::uint32_t signature_=0;
    void io(unsigned long command,cooperative_linux::DMA_OPERATION& op) {
        check(!terminal_ && !closed_,"provider terminal");
        if (trace_) std::cerr<<"dma-submit ioctl="<<std::hex<<command
                            <<" address="<<op.ddr3_addr<<std::dec
                            <<" cmd="<<op.cmd<<" bytes="<<op.total_length<<std::endl;
        if (::ioctl(fd_,command,&op)!=0) {
            terminal_=true;
            throw std::runtime_error("DMA ioctl failed; session quarantined errno="+std::to_string(errno));
        }
        if (trace_) std::cerr<<"dma-complete"<<std::endl;
        std::atomic_thread_fence(std::memory_order_seq_cst);
    }
    std::vector<std::uint8_t> read(std::uint32_t addr,std::uint32_t bytes) {
        check(bytes && bytes<=Window && !(addr&15) && !(bytes&15),"DMA range/alignment");
        cooperative_linux::DMA_OPERATION op{};
        op.cmd=1; op.ddr3_addr=addr; op.total_length=bytes;
        io(cooperative_linux::PCI_DMA_WRITE_CMD,op);
        return {rx_,rx_+bytes};
    }
    std::uint32_t read32(std::uint32_t address) {
        auto data=read(address,16); std::uint32_t value;
        std::memcpy(&value,data.data(),4); return value;
    }
    std::uint32_t reg(std::uint32_t offset) { return read32(Base+offset); }
    void audit_camera_ranges() {
        // Cameras 1..4 have writable bank addresses. Read the real registers,
        // conservatively reserve 2 MiB per bank, and reject destination overlap.
        for (unsigned camera=0;camera<4;++camera) for (auto offset:{0x80u,0xc0u}) {
            const auto address=read32(0x20000000+camera*0x200+offset);
            const std::uint64_t end=std::uint64_t(address)+0x200000;
            check(end<=0x10000000 && (end<=0x0a000000 || address>=0x0a12c000),
                  "live camera bank overlaps reserved RGB destination");
        }
    }
    void write_reg(std::uint32_t offset,std::uint32_t value) {
        std::memset(tx_,0,16); std::memcpy(tx_,&value,4);
        std::atomic_thread_fence(std::memory_order_seq_cst);
        cooperative_linux::DMA_OPERATION op{};
        op.cmd=0; op.ddr3_addr=Base+offset; op.total_length=16;
        io(cooperative_linux::PCI_DMA_READ_CMD,op);
    }
    template<class Predicate> std::uint32_t poll(Predicate match) {
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
        do {
            const auto status=reg(0x10);
            check(!(status&0x70),"hardware error/config/quarantine status");
            if (match(status)) return status;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        } while (std::chrono::steady_clock::now()<deadline);
        terminal_=true; throw std::runtime_error("status deadline; capture remains held, no DMA retry");
    }
    void validate(const Lease& l) {
        check(leased_ && l.generation==lease_.generation && l.sequence==lease_.sequence &&
              l.camera==5 && l.source_ddr==lease_.source_ddr,"wrong lease");
        check((reg(0x10)&3)==3 && reg(0x30)==l.source_ddr && reg(0x50)==l.generation,
              "capture lease changed");
    }
public:
    LinuxProvider() {
        try {
        // Keep lock before touching the driver's global state.
        lock_=::open("/run/lock/delivery-pango.lock",O_RDWR|O_CREAT|O_CLOEXEC,0600);
        check(lock_>=0 && ::flock(lock_,LOCK_EX|LOCK_NB)==0,"exclusive benchmark lock unavailable");
        no_existing_owner();
        fd_=::open("/dev/pango_pci_driver",O_RDWR|O_SYNC|O_CLOEXEC);
        check(fd_>=0,"open pango driver");
        cooperative_linux::DMA_OPERATION op{}; op.total_length=Window;
        op.cmd=0; io(cooperative_linux::PCI_MAP_ADDR_CMD,op);
        op.cmd=1; io(cooperative_linux::PCI_MAP_ADDR_CMD,op);
        tx_=static_cast<std::uint8_t*>(::mmap(nullptr,Window,PROT_READ|PROT_WRITE,MAP_SHARED,fd_,0));
        rx_=static_cast<std::uint8_t*>(::mmap(nullptr,Window,PROT_READ|PROT_WRITE,MAP_SHARED,
                                           fd_,cooperative_linux::RX_MMAP_OFFSET));
        check(tx_!=MAP_FAILED && rx_!=MAP_FAILED,"coherent mapping failed");
        if (std::getenv("DELIVERY_DMA_PREFLIGHT")) {
            // Read-only contrasts distinguish the shared DMA path from MMIO.
            // A timeout stops the constructor immediately; never retry DMA.
            for (const auto address:{0x00800000u,0x20000000u}) {
                const auto value=read32(address);
                std::cerr<<"preflight address="<<std::hex<<address
                         <<" value="<<value<<std::dec<<std::endl;
            }
        }
        signature_=reg(0);
        check(signature_==0x444c5632 && reg(0x60)==RgbBytes && reg(0x80)==RawBytes,
              "wrong FPGA candidate/geometry");
        check(reg(0x40)==0x0a000000 && (reg(0x10)&0x77)==0,
              "candidate not idle at ownership boundary");
        audit_camera_ranges();
        } catch (...) {
            if (fd_>=0) quarantine();
            else if (lock_>=0) ::close(lock_);
            throw;
        }
    }
    ~LinuxProvider() override {
        // Ordinary exit closes only after finish. Any exception deliberately
        // leaves driver ownership to process teardown; do not replay or resume.
        if (lock_>=0 && closed_) ::close(lock_);
    }
    std::uint32_t rtl_signature() const override { return signature_; }
    Lease claim() override {
        check(!leased_ && !terminal_,"already leased/terminal");
        audit_camera_ranges();
        write_reg(0x20,1); poll([](auto s){return (s&3)==3;});
        lease_={reg(0x50),0,5,reg(0x30)};
        check(lease_.source_ddr==0x01800000 || lease_.source_ddr==0x01a00000,"invalid published bank");
        auto tag=read(lease_.source_ddr+RawBytes,16);
        std::memcpy(&lease_.sequence,tag.data(),4);
        check(lease_.sequence!=0,"unpublished frame sequence");
        leased_=true; return lease_;
    }
    std::vector<std::uint8_t> read_raw(const Lease& l) override {
        validate(l); auto raw=read(l.source_ddr,RawBytes); validate(l); return raw;
    }
    std::vector<std::uint8_t> preprocess_and_read_rgb(const Lease& l) override {
        validate(l); const auto before=reg(0x90); write_reg(0x20,3);
        poll([&](auto s){return (s&0xc)==8 && reg(0x90)==before+1;});
        auto rgb=read(reg(0x40),RgbBytes); validate(l); return rgb;
    }
    void release(const Lease& l) override {
        validate(l); leased_=false; // no retry after an uncertain release
        write_reg(0x20,0); poll([](auto s){return (s&3)==0;});
    }
    void quarantine() noexcept override {
        terminal_=true;
        if (!parked_) {
            parked_=true;
            // Retained release() frees GLOBAL coherent buffers even after a
            // timeout. Preserve the fd/mappings until parent quiesces hardware.
            std::cerr<<"QUARANTINE pid="<<::getpid()<<": SIGSTOP; quiesce hardware before SIGCONT/exit\n";
            ::raise(SIGSTOP);
        }
    }
    void finish() override {
        check(!terminal_ && !leased_,"cannot finish uncertain session");
        check((reg(0x10)&7)==0,"hardware not idle");
        check(::munmap(tx_,Window)==0 && ::munmap(rx_,Window)==0,"unmap failed");
        tx_=rx_=nullptr;
        check(::close(fd_)==0,"close failed"); fd_=-1; closed_=true;
    }
};
}
std::unique_ptr<Provider> bind_provider() { return std::make_unique<LinuxProvider>(); }
}
