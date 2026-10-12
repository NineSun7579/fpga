#include "thumbnail_delivery.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

namespace thumbnail {
namespace {
struct Stopped : std::runtime_error { using std::runtime_error::runtime_error; };
struct Fake {
    uint32_t mode = 0, state = 0, epoch = 42, jobs = 9, tag = 123;
    int64_t clock = 0;
    int reads = 0, writes = 0, copies = 0, releases = 0, restores = 0;
    int failRead = 0, failWrite = 0;
    bool badSignature = false, badCaps = false, badSize = false, badSource = false;
    bool failDma = false, changedEpoch = false, changedTag = false, fault = false;
    bool freezeTimeout = false, completionTimeout = false, releaseTimeout = false;
    bool wrongJobs = false, ignoredMode = false;
    std::vector<std::string> events;
    bool read(uint32_t reg, uint32_t& value) {
        if (++reads == failRead) return false;
        switch (reg) {
        case SignatureReg: value = badSignature ? 0 : Signature; break;
        case Caps: value = badCaps ? 1 : 3; break;
        case Status: value = state; break;
        case Mode: value = mode; break;
        case Destination: value = mode ? ThumbDestination : RgbDestination; break;
        case InputBytes: value = RawBytes; break;
        case OutputBytes: value = mode ? (badSize ? Bytes + 16 : Bytes) : RgbBytes; break;
        case Source: value = badSource ? 0x00800000 : 0x01800000; break;
        case Epoch: value = epoch + ((changedEpoch && copies) ? 1 : 0); break;
        case Jobs: value = jobs; break;
        default: throw std::logic_error("unexpected register");
        }
        return true;
    }
    bool write(uint32_t reg, uint32_t value) {
        events.push_back(std::to_string(reg) + "=" + std::to_string(value));
        if (++writes == failWrite) return false;
        if (reg == Mode) {
            if (state & 7) throw std::logic_error("mode changed while held/busy");
            if (!ignoredMode) mode = value;
            if (!value) ++restores;
            state &= ~8u;
        } else if (reg == Command && value == 1) {
            state = freezeTimeout ? 1 : 3;
        } else if (reg == Command && value == 3) {
            state = fault ? 0x53 : (completionTimeout ? 7 : 11);
            if (!wrongJobs) ++jobs;
        } else if (reg == Command && value == 0) {
            if (state != 11 || copies != 1) throw std::logic_error("unsafe release");
            ++releases;
            if (!releaseTimeout) state = 8;
        } else throw std::logic_error("unexpected command");
        return true;
    }
    bool readTag(uint32_t address, uint32_t& value) {
        if (address != 0x01800000 + RawBytes) throw std::logic_error("wrong source tag address");
        value = tag + ((changedTag && copies) ? 1 : 0);
        return true;
    }
    bool readPixels(uint32_t address, uint32_t count, void* output) {
        if (state != 11 || mode != 1 || address != ThumbDestination || count != Bytes)
            throw std::logic_error("wrong DMA size/address/lease");
        ++copies;
        if (failDma) return false;
        std::memset(output, 0x5a, count);
        return true;
    }
    int64_t nowMs() { return clock; }
    void delay() { clock += 100; }
    [[noreturn]] void quarantine(const char* reason) { throw Stopped(reason); }
};
}
int runSelfTest() {
    int failures = 0, cases = 0;
    auto expect = [&](bool ok, const char* description) {
        ++cases;
        if (!ok) { ++failures; std::fprintf(stderr, "[thumbnail-selftest] FAIL %s\n", description); }
    };
    std::vector<uint8_t> buffer(Bytes + 32, 0xa5);
    auto execute = [&](Fake& io, size_t capacity = Bytes) {
        uint32_t tag = 0;
        try { Reader<Fake>(io).read(buffer.data() + 16, capacity, tag); }
        catch (const Stopped&) { return false; }
        return tag == 123;
    };
    Fake healthy;
    expect(execute(healthy) && healthy.releases == 1 && healthy.restores == 1 && healthy.mode == 0 &&
           healthy.events == std::vector<std::string>{"176=1", "32=1", "32=3", "32=0", "176=0"},
           "one complete frame lease and default RGB restoration");
    expect(buffer[0] == 0xa5 && buffer[15] == 0xa5 && buffer[16] == 0x5a &&
           buffer[Bytes + 15] == 0x5a && buffer[Bytes + 16] == 0xa5 && buffer.back() == 0xa5,
           "153600-byte payload and copy guards");
    Fake wrongCapacity;
    expect(!execute(wrongCapacity, RawBytes) && wrongCapacity.writes == 0, "reject oversized output before commands");
    Fake signature; signature.badSignature = true;
    expect(!execute(signature) && signature.writes == 0, "signature guard before commands");
    Fake caps; caps.badCaps = true;
    expect(!execute(caps) && caps.writes == 0, "capability guard before commands");
    Fake held; held.state = 3;
    expect(!execute(held) && held.writes == 0, "never switch a held mode");
    Fake busy; busy.state = 4;
    expect(!execute(busy) && busy.writes == 0, "never switch a busy mode");
    Fake wrongMode; wrongMode.mode = 1;
    expect(!execute(wrongMode) && wrongMode.writes == 0, "require default RGB owner");
    Fake ignored; ignored.ignoredMode = true;
    expect(!execute(ignored) && ignored.writes == 1, "read back selected mode before hold");
    Fake bytes; bytes.badSize = true;
    expect(!execute(bytes) && bytes.copies == 0 && bytes.releases == 0, "bytecount mismatch before copy");
    Fake source; source.badSource = true;
    expect(!execute(source) && source.copies == 0 && source.releases == 0, "unknown C5 bank quarantined");
    Fake freeze; freeze.freezeTimeout = true;
    expect(!execute(freeze) && freeze.releases == 0 && freeze.restores == 0, "freeze timeout retains lease/mode");
    Fake completion; completion.completionTimeout = true;
    expect(!execute(completion) && completion.releases == 0 && completion.restores == 0, "busy timeout retains lease/mode");
    Fake fault; fault.fault = true;
    expect(!execute(fault) && fault.releases == 0 && fault.restores == 0, "FPGA fault retains lease/mode");
    Fake jobs; jobs.wrongJobs = true;
    expect(!execute(jobs) && jobs.copies == 0 && jobs.releases == 0, "completion job count verified");
    Fake dma; dma.failDma = true;
    expect(!execute(dma) && dma.releases == 0 && dma.restores == 0, "uncertain DMA never releases or restores");
    Fake epoch; epoch.changedEpoch = true;
    expect(!execute(epoch) && epoch.releases == 0, "lease epoch revalidated after DMA");
    Fake tag; tag.changedTag = true;
    expect(!execute(tag) && tag.releases == 0, "frozen tag revalidated after DMA");
    Fake release; release.releaseTimeout = true;
    expect(!execute(release) && release.restores == 0, "release acknowledgement required before mode restore");
    // Inject failures at every MMIO operation in a successful frame transaction.
    for (int n = 1; n <= healthy.reads; ++n) {
        Fake io; io.failRead = n;
        expect(!execute(io), "every MMIO read failure quarantines");
    }
    for (int n = 1; n <= healthy.writes; ++n) {
        Fake io; io.failWrite = n;
        expect(!execute(io) && (n > 4 || io.restores == 0), "every MMIO write failure quarantines");
    }
    expect(Geometry{}.raw() && Geometry{}.valid(RawBytes) && !Geometry{}.valid(Bytes) &&
           Geometry{320, 240}.valid(Bytes) && !Geometry{320, 240}.raw() &&
           !Geometry{640, 240}.valid(640 * 240 * 2), "strict RAW and thumbnail geometry");
    expect(eligible(true, 4, 0, 0, false) && !eligible(false, 4, 0, 0, false) &&
           !eligible(true, 0, 1, 0, false) && !eligible(true, 4, 4, 0, false) &&
           !eligible(true, 4, 0, 16, false) && !eligible(true, 4, 0, 0, true),
           "default off, C5 only, vision/stereo/HDMI RAW fallback");
    std::fprintf(stderr, "THUMBNAIL_SELFTEST_%s cases=%d failures=%d\n", failures ? "FAIL" : "PASS", cases, failures);
    return failures ? 2 : 0;
}
} // namespace thumbnail
#ifdef THUMBNAIL_STANDALONE_SELFTEST
int main() { return thumbnail::runSelfTest(); }
#endif
