// Included only by local_protocol_check.py's extracted test unit.
#include <cassert>
#include <cstdarg>
#include <map>
#include <vector>
#include <stdexcept>
namespace fixture {
constexpr uint32_t Base = 0x40020000;
std::vector<uint8_t> tx(0x1000), rx(scheme2::Window);
int failSelector = -1, mapCalls = 0, unmapCalls = 0, exports = 0, closes = 0;
bool allocated[2] = {}, failCleanup = false, interruptMap = false;
std::map<uint32_t, uint32_t> regs{{0,0x444c5632},{0xa0,15},{0xf0,63},{0x80,614400},
    {0x10,0},{0xb0,0},{0xc0,4},{0xd0,0},{0x120,0},{0x50,0},{0x90,0}};
uint32_t readyOffset = 0, readyLength = 0;
bool held = false;
bool unpublished = false;
int begins = 0, ends = 0, rawReads = 0, rgbReads = 0;
uint32_t destination() { return regs[0xc0] == 4 ? 0x0a000000 : 0x0b000000 + regs[0xc0]*0x400000; }
void selectors() {
    regs[0x40] = destination(); regs[0x60] = scheme2::SquareBytes;
    regs[0x100] = 0x800000 + regs[0xc0]*0x400000;
    regs[0x110] = 0xa00000 + regs[0xc0]*0x400000;
}
}
extern "C" int __wrap_open(const char* name, int, ...) {
    assert(std::strcmp(name, "/dev/pango_pci_driver") == 0); return 100;
}
extern "C" int __wrap_close(int fd) { assert(fd == 100 || fd == 101); ++fixture::closes; return 0; }
extern "C" int __wrap_raise(int sig) {
    assert(sig == SIGSTOP); throw std::runtime_error("quarantined");
}
extern "C" void* __wrap_mmap(void*, size_t size, int, int, int fd, off_t offset) {
    assert(fd == 100 && size == (scheme2::enabled() ? (offset ? scheme2::Window : 0x1000) : 0x400000));
    assert(offset == 0 || offset == 0x100000);
    return offset ? fixture::rx.data() : fixture::tx.data();
}
extern "C" int __wrap_munmap(void* address, size_t size) {
    assert(address == fixture::rx.data() || address == fixture::tx.data());
    assert(size == (address == fixture::rx.data() ? scheme2::Window : 0x1000)); return 0;
}
extern "C" int __wrap_ioctl(int fd, unsigned long command, ...) {
    using namespace fixture;
    assert(fd == 100);
    va_list args; va_start(args, command); void* data = va_arg(args, void*); va_end(args);
    if (command == PZ_EXPORT_RX) { assert(!held); ++exports; return 101; }
    if (command == PZ_BEGIN) {
        auto* lease = static_cast<pz_lease*>(data);
        assert(!held && readyOffset == scheme2::Offset);
        assert(readyLength == 921600 || readyLength == scheme2::SquareBytes);
        assert(lease->offset == scheme2::Offset && lease->length == scheme2::SquareBytes);
        assert(regs[0x10] == 0 && regs[0xc0] == 4 && regs[0xd0] == 0);
        held = true; lease->token = ++begins; return 0;
    }
    if (command == PZ_END) {
        auto* lease = static_cast<pz_lease*>(data);
        assert(held && lease->token == uint64_t(begins)); held = false; ++ends; return 0;
    }
    auto* op = static_cast<DmaOp*>(data);
    assert(!held); // no scratch or ordinary camera DMA between BEGIN and END
    if (command == MAP_CMD) {
        ++mapCalls; assert(op->cmd <= 1);
        assert(op->total_length == (scheme2::enabled() ? (op->cmd ? scheme2::Window : 0x1000) : 0x400000));
        if (int(op->cmd) == failSelector) { errno = ENOMEM; return -1; }
        allocated[op->cmd] = true;
        if (interruptMap) PangoDev::alarmHandler(SIGALRM);
        return 0;
    }
    if (command == UNMAP_CMD) {
        ++unmapCalls; assert(op->cmd == 3);
        if (failCleanup) { errno = EBUSY; return -1; }
        allocated[0] = allocated[1] = false; return 0;
    }
    assert(op->total_length && op->offset_addr + op->total_length <= scheme2::Window);
    if (command == H2F_CMD) {
        assert(op->offset_addr + op->total_length <= tx.size());
        if (op->ddr3_addr < Base) {
            assert(op->offset_addr == 0 && op->total_length == 16);
            uint32_t value; memcpy(&value, tx.data(), 4);
            assert(value == 0x12345678); return 0;
        }
        const uint32_t offset = op->ddr3_addr - Base;
        uint32_t value; memcpy(&value, tx.data(), 4);
        assert(op->total_length == 16 && op->offset_addr == 0);
        if (offset == 0xc0 || offset == 0xd0) {
            assert((regs[0x10] & 7) == 0); regs[offset] = value; selectors();
        } else if (offset == 0x20) {
            if (value == 1) {
                ++regs[0x50]; regs[0x10] = 3; regs[0x120] = 4;
                regs[0x30] = regs[0x110]; regs[0xe0] = 100 + regs[0x50];
                if (unpublished) { regs[0x10] = 1; regs[0x120] = 2; }
            } else if (value == 3) { assert(regs[0x10] == 3); regs[0x10] = 11; ++regs[0x90]; }
            else { assert(value == 0 && ((regs[0x10] & 7) == 3 || (unpublished && regs[0x10] == 1))); regs[0x10] = 0; regs[0x120] = 0; }
        } else assert(false);
    } else {
        assert(command == F2H_CMD);
        uint8_t* out = rx.data() + op->offset_addr;
        if (op->ddr3_addr >= Base && op->ddr3_addr <= Base + 0x120) {
            assert(op->total_length == 16); const uint32_t value = regs[op->ddr3_addr-Base];
            memcpy(out, &value, 4);
        } else if (op->ddr3_addr >= 0x20000000) {
            assert(op->total_length == 16); const uint32_t bank = 0x800000; memcpy(out, &bank, 4);
        } else if (op->ddr3_addr == regs[0x30] + scheme2::RawBytes) {
            assert(op->total_length == 16); memcpy(out, &regs[0xe0], 4);
        } else if (op->ddr3_addr == regs[0x30]) {
            assert((regs[0x10] & 7) == 3 && op->total_length == scheme2::RawBytes + 16);
            memset(out, uint8_t(regs[0xc0]+1), scheme2::RawBytes);
            memcpy(out + scheme2::RawBytes, &regs[0xe0], 4); ++rawReads;
        } else {
            assert(op->offset_addr == scheme2::Offset);
            const uint32_t oldCamera = (regs[0xe0] - 101) % 6;
            const uint32_t ddr = oldCamera == 4 ? 0x0a000000 : 0x0b000000 + oldCamera*0x400000;
            assert(op->ddr3_addr == ddr + (op->total_length == 921600 ? 153600 : 0));
            if (scheme2::verify()) {
                std::vector<uint8_t> raw(scheme2::RawBytes, uint8_t(oldCamera+1));
                const auto golden = scheme2::golden(raw.data(), op->total_length == 921600 ? 480 : 640);
                memcpy(out, golden.data(), golden.size());
            } else memset(out, uint8_t(oldCamera+1), op->total_length);
            ++rgbReads;
        }
        readyOffset = op->offset_addr; readyLength = op->total_length;
    }
    return 0;
}
int main() {
    using namespace fixture;
    selectors();
    if (!scheme2::enabled()) {
        tx.resize(0x400000); rx.resize(0x400000);
        PangoDev legacy; assert(legacy.openDev());
        assert(mapCalls == 2 && exports == 0);
        assert(legacy.regWrite(0x20000000, 0x12345678));
        std::puts("flag-off legacy TX/RX MAP and mmap remain 4 MiB PASS");
        return 0;
    }
    for (int selector : {0, 1}) {
        failSelector = selector;
        const int beforeMaps = mapCalls, beforeUnmaps = unmapCalls, beforeCloses = closes;
        { PangoDev failed; assert(!failed.openDev());
          assert(std::strcmp(failed.lastErr(), selector ? "map rx failed" : "map tx failed") == 0); }
        assert(mapCalls - beforeMaps == selector + 1 && unmapCalls == beforeUnmaps + 1);
        assert(closes == beforeCloses + 1 && !allocated[0] && !allocated[1]);
        assert(exports == 0 && rawReads == 0 && rgbReads == 0 && begins == 0);
    }
    failSelector = -1; interruptMap = true;
    { PangoDev interrupted; assert(!interrupted.openDev()); }
    assert(!allocated[0] && !allocated[1] && exports == 0);
    interruptMap = false;
    // An idle check rejected by the driver preserves the fd/allocation.
    failSelector = 1; failCleanup = true;
    const int beforeCloses = closes;
    auto* uncertain = new PangoDev;
    bool quarantined = false;
    try { uncertain->openDev(); } catch (const std::runtime_error&) { quarantined = true; }
    assert(quarantined && allocated[0] && !allocated[1] && closes == beforeCloses);
    // Fixture releases preserved resources only after observing quarantine.
    failCleanup = false; failSelector = -1; delete uncertain;
    allocated[0] = false;
    std::puts("scheme2 actual preflight: TX/RX ENOMEM and interrupted MAP clean idle UNMAP; rejected cleanup preserves ownership PASS");
    PangoDev dev; assert(dev.openDev());
    for (uint32_t address : {0x20000000u, 0x20000040u, 0x20000100u, 0x20000180u})
        assert(dev.regWrite(address, 0x12345678));
    for (int height : {480, 640}) for (int camera = 0; camera < 6; ++camera) {
        scheme2::admission().publish({height,"model",1});
        scheme2::admission().arm(camera, 7);
        assert(scheme2::admission().claim(camera, 7).height == height);
        std::vector<uint8_t> raw(scheme2::RawBytes);
        uint32_t tag = 0; qint64 dma = 0, copy = 0, capture = 0;
        std::shared_ptr<scheme2::Input> input;
        assert(dev.cameraReadFpga(camera, 7, height, false, 0, raw.data(), tag, dma, copy, capture, input) == 1);
        assert(input && input->tag == tag && input->camera == camera && input->sourceGeneration == 7);
        assert(input->height == height && input->base == rx.data() && input->fd == 101);
        assert(!held && rgbReads == begins); // queues have no RX payload and no kernel lease
        uint32_t scratch = 0; assert(dev.regRead(Base, scratch)); // queue delay keeps scratch DMA alive
        input->consume(); input->start();
        assert(raw.front() == camera+1 && raw.back() == camera+1);
        if (scheme2::verify()) {
            assert(input->goldenRgb == scheme2::golden(raw.data(), height));
            assert(scheme2::mismatch(input->goldenRgb.data(), rx.data()+scheme2::Offset, input->goldenRgb.size()) == input->goldenRgb.size());
        } else assert(rx[scheme2::Offset] == camera+1 && rx[scheme2::Offset+scheme2::bytes(height)-1] == camera+1);
        uint32_t ignored; assert(!dev.regRead(Base, ignored)); // globally blocked while consumer owns RX
        input->complete(); assert(!held); input.reset();
    }
    assert(begins == 12 && ends == 12 && rawReads == 12 && rgbReads == 12);
    std::vector<uint8_t> raw(scheme2::RawBytes);
    uint32_t tag=0; qint64 dma=0,copy=0,capture=0;
    std::shared_ptr<scheme2::Input> cancelled;
    scheme2::admission().publish({480,"cancelled",2}); scheme2::admission().arm(0,8);
    assert(scheme2::admission().claim(0,8));
    assert(dev.cameraReadFpga(0,8,480,false,0,raw.data(),tag,dma,copy,capture,cancelled)==1);
    assert(!held); cancelled->complete(); cancelled.reset();
    assert(begins==12 && ends==12 && rgbReads==12 && rawReads==13);
    unpublished=true;
    scheme2::admission().arm(1,8); assert(scheme2::admission().claim(1,8));
    assert(dev.cameraReadFpga(1,8,480,false,0,raw.data(),tag,dma,copy,capture,cancelled)==0);
    assert(!cancelled && !held && regs[0x10]==0 && regs[0xc0]==4 && regs[0xd0]==0);
    assert(begins==12 && ends==12 && rawReads==13);
    scheme2::admission().arm(1,8); assert(scheme2::admission().claim(1,8)); scheme2::admission().retire();
    std::puts("scheme2 actual PangoDev mode0 RAW/RGB acquisition + lease contract PASS (6 cameras, both geometries)");
}
