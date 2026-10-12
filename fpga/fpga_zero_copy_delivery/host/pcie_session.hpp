#pragma once
#include "bound_rknn.hpp"
#include "cooperative_linux_transport/driver_abi.hpp"
#include <atomic>
#include <array>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <optional>
#include <thread>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <unistd.h>

namespace offload {
struct Lease {
    uint32_t generation, sequence, source, mode;
    uint32_t camera=4, output_bank=0, destination=0;
    bool published=false;
};
enum class BackgroundClaim { disabled, enabled_rgb_freeze };
inline bool backgroundClaimAllowed(BackgroundClaim policy,uint32_t mode,uint32_t caps,
                                   uint32_t control,bool touched,bool uncertain) {
    if (policy==BackgroundClaim::disabled) return control==2 && !uncertain;
    return policy==BackgroundClaim::enabled_rgb_freeze && mode==0 && caps==31 &&
           (control==1 || control==3) && touched && uncertain;
}
class PcieSession {
    int lock_=-1,fd_=-1;
    uint8_t* tx_=nullptr;
    uint8_t* rx_=nullptr;
    bool held_=false,failed_=false;
    bool dma_started_=false;
    bool six_=false;
    bool background_touched_=false,background_uncertain_=false;
    Lease lease_{};
    static constexpr uint32_t Base=0x40020000,RawBytes=640*480*2;
    void io(unsigned long command,cooperative_linux::DMA_OPERATION& op) {
        require(fd_>=0 && !failed_,"PCIe session failed");
        if (::ioctl(fd_,command,&op)) {
            failed_=true;
            throw std::runtime_error("DMA ioctl failed errno="+std::to_string(errno));
        }
        std::atomic_thread_fence(std::memory_order_seq_cst);
    }
    void read(uint32_t ddr,uint32_t size,uint32_t offset) {
        require(size && size<=Window && offset<=Window-size && !(ddr&15) &&
                !(size&15) && !(offset&15),"Invalid F2H range");
        cooperative_linux::DMA_OPERATION op{};
        op.ddr3_addr=ddr; op.total_length=size; op.offset_addr=offset;
        dma_started_=true;
        io(cooperative_linux::PCI_DMA_WRITE_CMD,op);
        if (op.cmd!=0 || op.ddr3_addr!=ddr || op.total_length!=size || op.offset_addr!=offset) {
            failed_=true;
            throw std::runtime_error("F2H returned transaction metadata changed; retain owner");
        }
    }
    uint32_t read32(uint32_t address) {
        read(address,16,0);
        uint32_t value; std::memcpy(&value,rx_,4); return value;
    }
    void write_reg(uint32_t offset,uint32_t value) {
        std::memset(tx_,0,16); std::memcpy(tx_,&value,4);
        std::atomic_thread_fence(std::memory_order_seq_cst);
        cooperative_linux::DMA_OPERATION op{};
        op.ddr3_addr=Base+offset; op.total_length=16;
        dma_started_=true;
        io(cooperative_linux::PCI_DMA_READ_CMD,op);
        if (op.cmd!=0 || op.ddr3_addr!=Base+offset || op.total_length!=16 || op.offset_addr!=0) {
            failed_=true;
            throw std::runtime_error("H2F returned transaction metadata changed; retain owner");
        }
    }
    template<class Test> uint32_t poll(Test test) {
        const auto limit=Clock::now()+std::chrono::seconds(3);
        do {
            const auto status=reg(0x10);
            require(!(status&0x70),"FPGA error/config/quarantine");
            if (test(status)) return status;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        } while (Clock::now()<limit);
        failed_=true;
        throw std::runtime_error("FPGA deadline; keep DMA resources leased");
    }
    void validate() {
        require(held_ && (reg(0x10)&0x77)==3 && reg(0x30)==lease_.source &&
                reg(0x50)==lease_.generation,"Changed frame lease");
        if (six_) {
            require(reg(0xc0)==lease_.camera && reg(0xd0)==lease_.output_bank &&
                    reg(0xb0)==lease_.mode && reg(0x40)==lease_.destination &&
                    reg(0x60)==(lease_.mode ? 320*240*2 : BoundRknn::InputBytes) &&
                    reg(0xe0)==lease_.sequence && reg(0x120)==4 &&
                    reg(0x100)==0x00800000+lease_.camera*0x00400000 &&
                    reg(0x110)==0x00a00000+lease_.camera*0x00400000 &&
                    read32(lease_.source+RawBytes)==lease_.sequence,
                    "Changed six-camera configuration/publication/tag");
        }
    }
    void restore_defaults() {
        if (lease_.mode || six_) write_reg(0xb0,0);
        if (six_) { write_reg(0xc0,4); write_reg(0xd0,0); }
        require(reg(0xb0)==0 && reg(0x60)==BoundRknn::InputBytes &&
                reg(0x40)==0x0a000000,"Failed to restore RGB mode");
        if (six_) require(reg(0xc0)==4 && reg(0xd0)==0 && reg(0x120)==0,
                          "Failed to restore six-camera defaults");
    }
    static void no_owner() {
        require(::geteuid()==0,"Root required for complete device-owner audit");
        for (const auto& process:std::filesystem::directory_iterator("/proc")) {
            const auto name=process.path().filename().string();
            if (name.empty() || name.find_first_not_of("0123456789")!=std::string::npos) continue;
            std::error_code ec;
            std::filesystem::directory_iterator fds(process.path()/"fd",ec);
            if (ec==std::errc::no_such_file_or_directory) continue;
            require(!ec,"Cannot audit process fds");
            for (const auto& item:fds) {
                auto target=std::filesystem::read_symlink(item.path(),ec);
                if (ec==std::errc::no_such_file_or_directory) continue;
                require(!ec,"Cannot audit fd symlink");
                require(target!="/dev/pango_pci_driver","PCIe device already owned");
            }
        }
    }
public:
    static constexpr uint32_t Window=4*1024*1024,InputOffset=2*1024*1024;
    PcieSession(const PcieSession&)=delete;
    PcieSession& operator=(const PcieSession&)=delete;
    PcieSession() {
        lock_=::open("/run/lock/delivery-pango.lock",O_RDWR|O_CREAT|O_CLOEXEC,0600);
        require(lock_>=0 && ::flock(lock_,LOCK_EX|LOCK_NB)==0,"Exclusive benchmark lock unavailable");
        try {
            no_owner();
            fd_=::open("/dev/pango_pci_driver",O_RDWR|O_SYNC|O_CLOEXEC);
            require(fd_>=0,"Cannot open PCIe device");
            cooperative_linux::DMA_OPERATION op{}; op.total_length=Window;
            op.cmd=0; io(cooperative_linux::PCI_MAP_ADDR_CMD,op);
            op.cmd=1; io(cooperative_linux::PCI_MAP_ADDR_CMD,op);
            tx_=static_cast<uint8_t*>(::mmap(nullptr,Window,PROT_READ|PROT_WRITE,MAP_SHARED,fd_,0));
            rx_=static_cast<uint8_t*>(::mmap(nullptr,Window,PROT_READ|PROT_WRITE,MAP_SHARED,fd_,cooperative_linux::RX_MMAP_OFFSET));
            require(tx_!=MAP_FAILED && rx_!=MAP_FAILED,("Cannot map coherent windows errno="+std::to_string(errno)).c_str());
            require(reg(0)==0x444c5632 && (reg(0x10)&0x77)==0,"Wrong FPGA signature or active lease");
        } catch (const std::exception& e) {
            std::cerr<<"PCIe initialization failed: "<<e.what()<<std::endl;
            if (fd_>=0 && dma_started_) quarantine();
            if (!dma_started_) {
                if (tx_ && tx_!=MAP_FAILED) ::munmap(tx_,Window);
                if (rx_ && rx_!=MAP_FAILED) ::munmap(rx_,Window);
                if (fd_>=0) ::close(fd_);
                fd_=-1;
                if (lock_>=0) { ::close(lock_); lock_=-1; }
            }
            throw;
        }
    }
    ~PcieSession() { if (lock_>=0 && fd_<0) ::close(lock_); }
    int fd() const { return fd_; }
    uint8_t* mapping() const { return rx_; }
    uint32_t reg(uint32_t offset) { return read32(Base+offset); }
    // Background-only owned reads use the existing fd and low scratch. Never
    // touch the reserved inference input at InputOffset or open a second fd.
    std::vector<uint8_t> background_read(uint32_t address,uint32_t bytes) {
        require(reg(0xa0)==31,"Background capability 31 required");
        const bool metadata=address>=Base+0x200 && address<=Base+0x370 && bytes==16;
        bool payload=false;
        for (uint32_t slot=0;slot<6;++slot) for (uint32_t bank=0;bank<2;++bank)
            payload=payload || (address==0x0a200000+slot*0x80000+bank*0x40000 &&
                                bytes==320*240*2+16);
        require(!(address&15) && (metadata || payload) && bytes<InputOffset,
                "Invalid background read allowlist");
        read(address,bytes,0);
        return std::vector<uint8_t>(rx_,rx_+bytes);
    }
    void background_enable() {
        require(reg(0xa0)==31 && !held_,"Background enable contract");
        const auto control=reg(0x180);
        require(control==2 && (reg(0x10)&0x77)==0,"Background not disabled/quiescent");
        background_touched_=true; background_uncertain_=true;
        write_reg(0x180,1);
        require((reg(0x180)&~2u)==1,"Background enable rejected/quarantined");
    }
    void background_disable() {
        require(reg(0xa0)==31,"Background capability 31 required");
        background_touched_=true; background_uncertain_=true;
        write_reg(0x180,0);
        const auto limit=Clock::now()+std::chrono::seconds(3);
        do {
            const auto control=reg(0x180);
            require(!(control&~3u),"Background quarantine/unknown control bits");
            if (control==2) { background_uncertain_=false; return; }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        } while (Clock::now()<limit);
        failed_=true;
        throw std::runtime_error("Background drain deadline; retain DMA owner");
    }
    std::array<uint32_t,19> register_snapshot() {
        require((reg(0xa0)&8)!=0,"Register snapshots unsupported by this image");
        read(Base,0x130,0);
        std::array<uint32_t,19> values{};
        for (size_t index=0;index<values.size();++index) {
            std::memcpy(&values[index],rx_+index*16,4);
            for (size_t byte=4;byte<16;++byte)
                require(rx_[index*16+byte]==0,"Register snapshot upper bits changed");
        }
        return values;
    }
    // Omitted selectors preserve legacy C5/output-bank0 calls and ABI.
    Lease claim_rgb(uint32_t mode=0, std::optional<uint32_t> camera=std::nullopt,
                    std::optional<uint32_t> output_bank=std::nullopt,
                    BackgroundClaim background=BackgroundClaim::disabled) {
        require(!held_,"Frame already held");
        require(mode<=1,"Unknown endpoint mode");
        const auto caps=reg(0xa0);
        require(background==BackgroundClaim::disabled || caps==31,
                "Enabled background RAW freeze requires exact caps 31");
        if (caps&16) require(backgroundClaimAllowed(background,mode,caps,reg(0x180),
                                                  background_touched_,background_uncertain_),
                             "Background RAW claim policy/control mismatch");
        six_=(caps&4)!=0;
        const auto cam=camera.value_or(4), bank=output_bank.value_or(0);
        require(cam<6 && bank<2,"Invalid camera/output bank");
        require(six_ || (!camera && !output_bank),"Six-camera selectors unsupported");
        if (six_) {
            require((caps&7)==7 && reg(0xf0)==0x3f && reg(0x80)==RawBytes,
                    "Six-camera capabilities/geometry unsupported");
            require((reg(0x10)&0x77)==0 && reg(0x120)==0 && reg(0xb0)==0 &&
                    reg(0xc0)==4 && reg(0xd0)==0,"Six-camera idle defaults required");
            write_reg(0xc0,cam); write_reg(0xd0,bank);
        }
        if (mode) {
            require((reg(0xa0)&3)==3 && reg(0xb0)==0 && (reg(0x10)&7)==0,"Thumbnail mode unavailable");
            write_reg(0xb0,mode);
        }
        const auto slot=cam==4 ? 0 : (cam<4 ? cam+1 : 5);
        const uint32_t destination=mode ? 0x0a200000+slot*0x80000+bank*0x40000 :
            ((cam==4 && bank==0) ? 0x0a000000 : 0x0b000000+cam*0x400000+bank*0x200000);
        const uint32_t bytes=mode ? 320*240*2 : BoundRknn::InputBytes;
        require(reg(0x60)==bytes && reg(0x40)==destination,"Endpoint mode mismatch");
        if (six_) require(reg(0xc0)==cam && reg(0xd0)==bank && reg(0xb0)==mode &&
                          reg(0x100)==0x00800000+cam*0x400000 &&
                          reg(0x110)==0x00a00000+cam*0x400000,
                          "Six-camera selector/source readback mismatch");
        // Audit destinations against live writable camera-bank configuration.
        for (uint32_t camera=0;camera<4;++camera) for (auto offset:{0x80u,0xc0u}) {
            const auto address=read32(0x20000000+camera*0x200+offset);
            const uint64_t end=uint64_t(address)+0x200000;
            require(end<=0x10000000 && (end<=destination || address>=destination+bytes),"Endpoint destination overlaps camera bank");
        }
        const auto epoch=reg(0x50);
        lease_={0,0,0,mode,cam,bank,destination,false};
        write_reg(0x20,1); held_=true;
        if (six_) {
            const auto deadline=Clock::now()+std::chrono::seconds(3);
            while ((reg(0x10)&0x77)!=3) {
                require(!(reg(0x10)&0x70),"FPGA error/config/quarantine");
                if (Clock::now()>=deadline) {
                    // Only an idle, unsubmitted, unpublished hold can be released.
                    if (reg(0x120)==2 && (reg(0x10)&0x7f)==1) {
                        write_reg(0x20,0); poll([](auto s){return (s&7)==0;});
                        held_=false; restore_defaults();
                        throw std::runtime_error("Unpublished source: safely released; parity not passed");
                    }
                    failed_=true;
                    throw std::runtime_error("Six-camera admission deadline; keep DMA resources leased");
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
        } else poll([](auto s){return (s&3)==3;});
        lease_.generation=reg(0x50); lease_.source=reg(0x30);
        require(lease_.generation==uint32_t(epoch+1),"Lease generation did not advance");
        require(lease_.source==0x00800000+cam*0x400000 ||
                lease_.source==0x00a00000+cam*0x400000,"Unknown camera source bank");
        lease_.sequence=six_ ? reg(0xe0) : read32(lease_.source+RawBytes);
        if (six_) { validate(); lease_.published=true; }
        else { require(lease_.sequence!=0,"Unpublished source frame"); lease_.published=true; }
        return lease_;
    }
    std::vector<uint8_t> raw() {
        validate(); read(lease_.source,RawBytes,0);
        std::vector<uint8_t> result(rx_,rx_+RawBytes);
        validate(); return result;
    }
    const uint8_t* rgb_to_input_slot() {
        require(lease_.mode==0,"Expected RGB lease");
        validate(); const auto before=reg(0x90);
        write_reg(0x20,3);
        poll([&](auto s){return (s&0xc)==8 && reg(0x90)==before+1;});
        read(reg(0x40),BoundRknn::InputBytes,InputOffset);
        // Metadata uses slot0, not the live shared input slot at2MiB.
        validate(); return rx_+InputOffset;
    }
    std::vector<uint8_t> thumbnail() {
        require(lease_.mode==1,"Expected thumbnail lease");
        validate(); const auto before=reg(0x90);
        write_reg(0x20,3);
        poll([&](auto s){return (s&0xc)==8 && reg(0x90)==before+1;});
        validate();
        require(reg(0x60)==320*240*2 && reg(0x40)==lease_.destination,"Thumbnail output changed");
        read(lease_.destination,320*240*2,InputOffset);
        std::vector<uint8_t> result(rx_+InputOffset,rx_+InputOffset+320*240*2);
        validate(); return result;
    }
    void release() {
        validate(); require((reg(0x10)&7)==3,"Cannot release busy frame");
        write_reg(0x20,0); poll([](auto s){return (s&7)==0;});
        held_=false;
        if (lease_.mode || six_) restore_defaults();
    }
    // Data comparison failures may close safely; uncertain DMA/identity faults quarantine.
    bool close_if_safe() noexcept {
        try {
            if (failed_) return false;
            if (background_touched_) background_disable();
            if (held_) release();
            finish(); return true;
        } catch (...) { return false; }
    }
    void finish() {
        require(!failed_ && !held_ && fd_>=0 && (reg(0x10)&7)==0,"Cannot close active/uncertain session");
        require(!background_uncertain_ &&
                (!(reg(0xa0)&16) || reg(0x180)==2),
                "Cannot close active/uncertain background");
        require(::munmap(tx_,Window)==0 && ::munmap(rx_,Window)==0,"Unmap failed");
        tx_=rx_=nullptr;
        require(::close(fd_)==0,"Close failed"); fd_=-1;
    }
    void quarantine() noexcept {
        failed_=true;
        std::cerr << "QUARANTINE pid=" << ::getpid() << ": quiesce hardware before exit\n";
        ::raise(SIGSTOP);
    }
};
} // namespace offload
