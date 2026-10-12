// Included only by local_protocol_check.py's extracted test unit.
#include <cassert>
#include <cstdarg>
#include <map>
#include <vector>
#include <stdexcept>
#include <thread>
#include <string>
#undef copyCameraPixels
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
std::atomic<bool> delayFreeze{false}, freezePolled{false}, scratchServed{false};
int begins = 0, ends = 0, rawReads = 0, rgbReads = 0;
bool shortHoldCopyProbe = false;
PangoDev* activeDev = nullptr;
int selectedCamera = -1, postReleaseCopies = 0;
std::string fault;
std::atomic<bool> rawEntered{false}, rawFinished{false}, conversionPolled{false}, completed{false}, stopWorker{false};
std::thread converter;
bool rawFirst = false, triggered = false, initialTagValidated = false, completionObserved = false;
uint32_t startJobs = 0;
int triggers = 0, releases = 0;
void joinConverter() { stopWorker = true; if (converter.joinable()) converter.join(); }
void applyCompletion() {
    if (!triggered || !completed || regs[0x10] != 7) return;
    regs[0x10] = 11;
    if (fault != "stale") regs[0x90] = startJobs + (fault == "generation" ? 2 : 1);
    if (fault == "source") regs[0x30] += 0x200000;
    if (fault == "camera") ++regs[0xc0];
    if (fault == "sequence") ++regs[0xe0];
    if (fault == "epoch") ++regs[0x50];
    if (fault == "destination") regs[0x40] += 16;
    if (fault == "mode") regs[0xd0] = 1;
    if (fault == "error") regs[0x10] |= 0x10;
    if (fault == "early-release") { regs[0x10] = 0; regs[0x120] = 0; }
}
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
    if (held) {
        assert(command == H2F_CMD || command == F2H_CMD);
        if (command == F2H_CMD)
            assert(uint64_t(op->offset_addr) + op->total_length <= scheme2::Offset ||
                   op->offset_addr >= scheme2::Offset + scheme2::SquareBytes);
    }
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
                joinConverter();
                triggered = initialTagValidated = completionObserved = false;
                rawEntered = rawFinished = conversionPolled = completed = stopWorker = false;
                ++regs[0x50]; regs[0x10] = 3; regs[0x120] = 4;
                regs[0x30] = regs[0x110]; regs[0xe0] = 100 + regs[0x50];
                if (unpublished) { regs[0x10] = 1; regs[0x120] = 2; }
            } else if (value == 3) {
                assert(regs[0x10] == 3 && initialTagValidated && !rawEntered);
                triggered = true; ++triggers; startJobs = regs[0x90]; regs[0x10] = 7;
                converter = std::thread([] {
                    while (!stopWorker && !(rawFirst ? conversionPolled.load() : rawEntered.load()))
                        std::this_thread::yield();
                    if (!stopWorker && fault != "timeout" && fault != "raw-dma" && fault != "raw-timeout") completed = true;
                });
            }
            else {
                assert(value == 0 && ((regs[0x10] & 7) == 3 || (unpublished && regs[0x10] == 1)));
                if (triggered) assert(rawFinished && completed && completionObserved && regs[0x90] == uint32_t(startJobs+1));
                ++releases;
                if (shortHoldCopyProbe) assert(regs[0x10] == 11 && regs[0x90] == regs[0x50]);
                regs[0x10] = 0; regs[0x120] = 0;
            }
        } else assert(false);
    } else {
        assert(command == F2H_CMD);
        uint8_t* out = rx.data() + op->offset_addr;
        if (op->ddr3_addr >= Base && op->ddr3_addr <= Base + 0x120) {
            if (triggered && rawFinished && op->ddr3_addr == Base + 0x10) conversionPolled = true;
            applyCompletion();
            if (op->ddr3_addr == Base + 0x90 && triggered && regs[0x10] == 11 && regs[0x90] == uint32_t(startJobs+1)) completionObserved = true;
            assert(op->total_length == 16); uint32_t value = regs[op->ddr3_addr-Base];
            // FPGA drain stays pending until another caller gets transport
            // service. This fails if the actual poll sleeps holding the lock.
            if (op->ddr3_addr == Base + 0x10 && value == 3 && delayFreeze && !scratchServed) {
                freezePolled = true;
                value = 1;
            }
            memcpy(out, &value, 4);
        } else if (op->ddr3_addr >= 0x20000000) {
            assert(op->total_length == 16); const uint32_t bank = 0x800000; memcpy(out, &bank, 4);
        } else if (op->ddr3_addr == regs[0x30] + scheme2::RawBytes) {
            assert(op->total_length == 16);
            uint32_t tag = regs[0xe0] + (fault == "initial-tag" ? 1 : 0);
            memcpy(out, &tag, 4); initialTagValidated = tag == regs[0xe0];
        } else if (op->ddr3_addr == regs[0x30]) {
            if (shortHoldCopyProbe || ((!fault.empty() || triggered) && !rawFinished)) {
                assert(triggered && initialTagValidated && regs[0x10] == 7);
                if (shortHoldCopyProbe || !fault.empty()) assert(regs[0xc0] == uint32_t(selectedCamera));
                rawEntered = true;
                if (!rawFirst && fault != "raw-dma" && fault != "raw-timeout") {
                    while (!completed) std::this_thread::yield();
                    applyCompletion();
                }
                if (fault == "raw-dma" || fault == "raw-timeout") {
                    if (fault == "raw-timeout") PangoDev::alarmHandler(SIGALRM);
                    errno = EIO; return -1;
                }
                if (rawFirst) assert(!completed);
            }
            assert((held || (regs[0x10] & 3) == 3 || regs[0x10] == 0) && op->total_length == scheme2::RawBytes + 16);
            memset(out, uint8_t((regs[0xe0]-101)%6+1), scheme2::RawBytes);
            uint32_t tag = regs[0xe0] + (fault == "raw-tag" ? 1 : 0);
            memcpy(out + scheme2::RawBytes, &tag, 4); ++rawReads;
            rawFinished = true;
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
        if (op->offset_addr == scheme2::Offset) {
            readyOffset = op->offset_addr; readyLength = op->total_length;
        }
    }
    return 0;
}
namespace tdm {
void fixtureCopyCameraPixels(void* destination, const void* source, size_t size) {
    using namespace fixture;
    if (shortHoldCopyProbe) {
        // Exercise the actual acquisition's copy boundary. The old fair order
        // fails here: it copies while status=3, before conversion and release.
        assert(regs[0x10] == 0 && regs[0x120] == 0 && regs[0x90] == regs[0x50]);
        assert(regs[0xc0] == 4 && regs[0xd0] == 0 && !held);
        assert(source == rx.data() + cameraSlotOffset(selectedCamera));
        assert(size == scheme2::RawBytes);
        shortHoldCopyProbe = false; // nested ordinary copy is not selected
        scheme2::admission().arm((selectedCamera+1)%6, 7);
        assert(!scheme2::admission().claim((selectedCamera+1)%6, 7));
        const auto before = regs;
        uint32_t magic = 0;
        assert(activeDev->regRead(Base, magic) && magic == 0x444c5632);
        std::vector<uint8_t> other(scheme2::RawBytes);
        uint32_t tag = 0; qint64 dma = 0, copy = 0, capture = 0;
        assert(activeDev->cameraRead((selectedCamera+1)%6, regs[0x30], regs[0x30], false, 0,
            other.data(), tag, dma, copy, capture) == 1);
        assert(regs == before && rgbReads == begins && !held);
        assert(std::all_of(static_cast<const uint8_t*>(source),
            static_cast<const uint8_t*>(source)+size,
            [](uint8_t value) { return value == selectedCamera+1; }));
        ++postReleaseCopies;
    }
    copyCameraPixels(destination, source, size);
}
}
int main(int argc, char** argv) {
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
    PangoDev dev; assert(dev.openDev()); activeDev = &dev;
    if (argc > 1) {
        fault = argv[1]; rawFirst = true; selectedCamera = 0;
        scheme2::admission().publish({480,"fault",1}); scheme2::admission().arm(0,7);
        assert(scheme2::admission().claim(0,7));
        std::vector<uint8_t> raw(scheme2::RawBytes);
        uint32_t tag=0; qint64 dma=0,copy=0,capture=0;
        std::shared_ptr<scheme2::Input> input;
        bool rejected = false;
        try { dev.cameraReadFpga(0,7,480,fault == "old-tag",UINT32_MAX/2,raw.data(),tag,dma,copy,capture,input); }
        catch (const std::runtime_error&) { rejected = true; }
        joinConverter();
        if (fault == "old-tag") { assert(!rejected && triggers == 0 && releases == 1); }
        else {
            assert(rejected && !input && begins == 0 && rgbReads == 0 && releases == 0);
            assert(triggers == (fault == "initial-tag" ? 0 : 1));
            scheme2::admission().arm(1,7); assert(!scheme2::admission().claim(1,7));
        }
        std::printf("overlap rejection %s PASS (no unsafe release/reuse)\n", fault.c_str()); return 0;
    }
    for (uint32_t address : {0x20000000u, 0x20000040u, 0x20000100u, 0x20000180u})
        assert(dev.regWrite(address, 0x12345678));
    for (int height : {480, 640}) for (int camera = 0; camera < 6; ++camera) {
        rawFirst = height == 640;
        scheme2::admission().publish({height,"model",1});
        scheme2::PrefetchTiming timing;
        auto* timingPtr = scheme2::prefetchTimingEnabled() ? &timing : nullptr;
        scheme2::admission().arm(camera, 7, timingPtr ? monotonicMs() : -1);
        assert(scheme2::admission().claim(camera, 7, timingPtr).height == height);
        if (timingPtr) timing.claim = monotonicMs();
        std::vector<uint8_t> raw(scheme2::RawBytes);
        uint32_t tag = 0; qint64 dma = 0, copy = 0, capture = 0;
        std::shared_ptr<scheme2::Input> input;
        delayFreeze = true; freezePolled = false; scratchServed = false;
        std::thread metadataCaller([&] {
            while (!freezePolled.load()) std::this_thread::yield();
            uint32_t magic = 0;
            assert(dev.regRead(Base, magic) && magic == 0x444c5632);
            scratchServed = true;
        });
        selectedCamera = camera; shortHoldCopyProbe = true;
        const int beforeRaw = rawReads, beforeRgb = rgbReads;
        assert(dev.cameraReadFpga(camera, 7, height, false, 0, raw.data(), tag, dma, copy, capture, input, timingPtr) == 1);
        // Selected RAW plus the existing nested disjoint-camera copy probe.
        assert(rawReads == beforeRaw + 2 && rgbReads == beforeRgb);
        if (timingPtr) {
            // Actual wrapped PangoDev supplied these stages, before Input exists.
            assert(timing.arm <= timing.claim && timing.claim <= timing.holdCommand);
            assert(timing.holdCommand <= timing.holdValidated && timing.holdValidated <= capture);
            assert(capture <= timing.release && timing.release <= monotonicMs());
            assert(input->timing.release == timing.release && input->timing.arm == timing.arm);
            input->timing.publish = monotonicMs();
            input->timing.request = monotonicMs();
            assert(input->timing.ordered());
        } else {
            assert(input->timing.arm == -1 && input->timing.claim == -1 &&
                input->timing.holdCommand == -1 && input->timing.holdValidated == -1 &&
                input->timing.release == -1 && input->timing.publish == -1 && input->timing.request == -1);
        }
        metadataCaller.join(); assert(scratchServed); delayFreeze = false;
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
        const std::vector<uint8_t> reserved(rx.begin()+scheme2::Offset,
            rx.begin()+scheme2::Offset+scheme2::SquareBytes);
        const auto converterRegs = regs;
        uint32_t ignored; assert(dev.regRead(Base, ignored) && ignored == 0x444c5632);
        assert(dev.regWrite(0x20000000, 0x12345678));
        uint32_t metadata = 0; assert(dev.ddrRead(Base, 4, &metadata) && metadata == ignored);
        for (int ordinaryCamera = 0; ordinaryCamera < 6; ++ordinaryCamera) {
            std::vector<uint8_t> ordinary(scheme2::RawBytes);
            uint32_t ordinaryTag = 0;
            assert(dev.cameraRead(ordinaryCamera, regs[0x30], regs[0x30], false, 0,
                ordinary.data(), ordinaryTag, dma, copy, capture) == 1);
            assert(ordinaryTag == tag && ordinary == raw);
        }
        scheme2::admission().arm((camera+1)%6, 7);
        assert(!scheme2::admission().claim((camera+1)%6, 7));
        assert(regs == converterRegs && rgbReads == begins);
        assert(std::equal(reserved.begin(), reserved.end(), rx.begin()+scheme2::Offset));
        input->complete(); assert(!held); input.reset();
    }
    assert(begins == 12 && ends == 12 && rawReads == 96 && rgbReads == 12 && postReleaseCopies == 12);
    std::vector<uint8_t> raw(scheme2::RawBytes);
    uint32_t tag=0; qint64 dma=0,copy=0,capture=0;
    std::shared_ptr<scheme2::Input> cancelled;
    scheme2::admission().publish({480,"cancelled",2}); scheme2::admission().arm(0,8);
    assert(scheme2::admission().claim(0,8));
    assert(dev.cameraReadFpga(0,8,480,false,0,raw.data(),tag,dma,copy,capture,cancelled)==1);
    assert(!held); cancelled->complete(); cancelled.reset();
    assert(begins==12 && ends==12 && rgbReads==12 && rawReads==97);
    unpublished=true;
    scheme2::admission().arm(1,8); assert(scheme2::admission().claim(1,8));
    assert(dev.cameraReadFpga(1,8,480,false,0,raw.data(),tag,dma,copy,capture,cancelled)==0);
    assert(!cancelled && !held && regs[0x10]==0 && regs[0xc0]==4 && regs[0xd0]==0);
    assert(begins==12 && ends==12 && rawReads==97);
    joinConverter();
    scheme2::admission().arm(1,8); assert(scheme2::admission().claim(1,8)); scheme2::admission().retire();
    std::puts("scheme2 actual PangoDev mode0 RAW/RGB acquisition + lease contract PASS (6 cameras, both geometries)");
    std::puts("fair actual FPGA poll yields transport to waiting metadata caller PASS (12 acquisitions)");
    std::puts("short hold actual RAW copy after conversion/release/default restore, disjoint DMA and sole admission PASS (12 acquisitions)");
    std::puts("prefetch timing actual PangoDev ordering and unchanged RAW/deferred RGB DMA counts PASS (12 acquisitions)");
}
