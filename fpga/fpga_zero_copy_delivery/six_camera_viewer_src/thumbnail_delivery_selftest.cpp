#include "thumbnail_delivery.h"
#include "six_dma_layout.h"
#include "camera_dma.h"
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <algorithm>

namespace thumbnail {
namespace {
struct Stopped : std::runtime_error { using std::runtime_error::runtime_error; };
struct Fake {
    uint32_t mode = 0, camera = 4, bank = 0, state = 0, epoch = 42, jobs = 9, tag = 123;
    int64_t clock = 0;
    int reads = 0, writes = 0, copies = 0, releases = 0, restores = 0;
    int failRead = 0, failWrite = 0;
    bool badSignature = false, badCaps = false, badSize = false, badSource = false;
    bool failDma = false, changedEpoch = false, changedTag = false, fault = false;
    bool freezeTimeout = false, completionTimeout = false, releaseTimeout = false;
    bool wrongJobs = false, ignoredMode = false, badBitmap = false, badFreeze = false;
    bool badBank = false, badActualBank = false;
    bool unpublished = false, pending = false, flushing = false, invalidBanks = false;
    int sourceBank = 0;
    int publishAt = -1;
    bool read(uint32_t reg, uint32_t& value) {
        if (++reads == failRead) return false;
        switch (reg) {
        case SignatureReg: value = badSignature ? 0 : Signature; break;
        case Caps: value = badCaps ? 3 : RequiredCaps; break;
        case Supported: value = badBitmap ? 0x1f : SupportedMask; break;
        case Status: value = state; break;
        case Mode: value = mode; break;
        case Camera: value = camera; break;
        case OutputBank: value = bank ^ (badBank ? 1 : 0); break;
        case Bank0: value = SourceBanks[camera][0] + (badActualBank ? 16 : 0); break;
        case Bank1: value = SourceBanks[camera][1]; break;
        case Freeze:
            value = ((state & 3) == 3 ? (badFreeze ? 0x3f : 4u) : 0u) |
                    ((state & 1) && unpublished ? 2u : 0u) |
                    ((state & 1) && pending ? 1u : 0u) |
                    (flushing ? 8u : 0u) | (invalidBanks ? 16u : 0u);
            break;
        case Destination: value = mode ? Destinations[camera][bank] : RgbDestination; break;
        case InputBytes: value = RawBytes; break;
        case OutputBytes: value = mode ? (badSize ? Bytes + 16 : Bytes) : RgbBytes; break;
        case Source: value = badSource ? 0xdead0000 : SourceBanks[camera][sourceBank]; break;
        case SourceSequence: value = tag + ((changedTag && copies) ? 1 : 0); break;
        case Epoch: value = epoch + ((changedEpoch && copies) ? 1 : 0); break;
        case Jobs: value = jobs; break;
        default: throw std::logic_error("unexpected register");
        }
        return true;
    }
    bool write(uint32_t reg, uint32_t value) {
        if (++writes == failWrite) return false;
        if (reg == Mode || reg == Camera || reg == OutputBank) {
            if (state & 7) throw std::logic_error("selector changed while held/busy");
            if (reg == Mode) {
                if (!ignoredMode) mode = value;
                if (!value) ++restores;
            } else if (reg == Camera) camera = value;
            else bank = value;
            state &= ~8u;
        } else if (reg == Command && value == 1) state = (freezeTimeout || unpublished) ? 1 : 3;
        else if (reg == Command && value == 3) {
            if (unpublished) throw std::logic_error("submitted unpublished frame");
            state = fault ? 0x53 : (completionTimeout ? 7 : 11);
            if (!wrongJobs) ++jobs;
        } else if (reg == Command && value == 0) {
            if (!((state == 11 && copies == 1) || (state == 1 && unpublished &&
                  !pending && !flushing && !invalidBanks && copies == 0)))
                throw std::logic_error("unsafe release");
            ++releases;
            if (!releaseTimeout) state = 8;
        } else throw std::logic_error("unexpected command");
        return true;
    }
    bool readTag(uint32_t address, uint32_t& value) {
        if (address != SourceBanks[camera][sourceBank] + RawBytes) throw std::logic_error("wrong source tag address");
        value = tag;
        return true;
    }
    bool readPixels(uint32_t address, uint32_t count, void* output) {
        if (state != 11 || mode != 1 || address != Destinations[camera][bank] || count != Bytes)
            throw std::logic_error("wrong DMA size/address/lease");
        ++copies;
        if (failDma) return false;
        std::memset(output, 0x5a, count);
        return true;
    }
    int64_t nowMs() { return clock; }
    void delay() {
        clock += 100;
        if (publishAt >= 0 && clock >= publishAt && state == 1) {
            unpublished = false;
            state = 3;
        }
    }
    [[noreturn]] void quarantine(const char* reason) { throw Stopped(reason); }
};
}
int runSelfTest() {
    int failures = 0, cases = 0;
    auto expect = [&](bool ok, const char* description) {
        ++cases;
        if (!ok) { ++failures; std::fprintf(stderr, "[six-thumbnail-selftest] FAIL %s\n", description); }
    };
    std::vector<uint8_t> buffer(Bytes + 32, 0xa5);
    auto execute = [&](Fake& io, int camera = 0, int bank = 0, size_t capacity = Bytes) {
        uint32_t tag = 0;
        try { return Reader<Fake>(io).read(camera, bank, buffer.data() + 16, capacity, tag) ? 1 : 0; }
        catch (const Stopped&) { return -1; }
    };
    Fake healthy;
    for (int camera = 0; camera < 6; ++camera) for (int bank = 0; bank < 2; ++bank) {
        Fake io;
        io.sourceBank = 1 - bank; // RAW bank is independent of output bank.
        expect(execute(io, camera, bank) == 1 && io.releases == 1 && io.restores == 1 &&
               io.mode == 0 && io.camera == 4 && io.bank == 0, "all six cameras, both output banks, defaults restored");
        Fake empty; empty.unpublished = true;
        expect(execute(empty, camera, bank) == 0 && empty.copies == 0 && empty.releases == 1 &&
               empty.restores == 1 && empty.jobs == 9 && empty.clock == 2000,
               "unpublished: bounded admission, no submission/copy, safe release");
        Fake wrapped; wrapped.tag = 0;
        expect(execute(wrapped, camera, bank) == 1 && wrapped.copies == 1 && wrapped.jobs == 10,
               "published zero sequence after wrap is delivered");
    }
    expect(execute(healthy) == 1, "healthy transaction");
    Fake delayed; delayed.unpublished = true; delayed.publishAt = 1000;
    expect(execute(delayed) == 1 && delayed.clock == 1000 && delayed.copies == 1,
           "publication during admission wait delivers normally");
    expect(buffer[0] == 0xa5 && buffer[15] == 0xa5 && buffer[16] == 0x5a &&
           buffer[Bytes + 15] == 0x5a && buffer[Bytes + 16] == 0xa5 && buffer.back() == 0xa5,
           "153600-byte payload and owned-copy guards");
    Fake argument;
    expect(execute(argument, 6) == -1 && argument.writes == 0, "camera bounds");
    expect(execute(argument, 0, 2) == -1 && argument.writes == 0, "bank bounds");
    expect(execute(argument, 0, 0, RawBytes) == -1 && argument.writes == 0, "capacity bounds");
    auto preflight = [&](bool Fake::*field, const char* name) {
        Fake io; io.*field = true;
        expect(execute(io) == -1 && io.writes == 0, name);
    };
    preflight(&Fake::badSignature, "signature before commands");
    preflight(&Fake::badCaps, "bit2 capability before commands");
    preflight(&Fake::badBitmap, "six-camera support bitmap");
    for (auto state : {3u, 4u, 0x40u}) {
        Fake io; io.state = state;
        expect(execute(io) == -1 && io.writes == 0, "held/busy/quarantined selector guard");
    }
    auto faultCase = [&](bool Fake::*field, const char* name) {
        Fake io; io.*field = true;
        expect(execute(io) == -1 && io.releases == 0 && io.restores == 0, name);
    };
    faultCase(&Fake::badSize, "size before DMA");
    faultCase(&Fake::badSource, "source camera identity");
    faultCase(&Fake::badBank, "output selector identity");
    faultCase(&Fake::badActualBank, "RAW source bank configuration identity");
    faultCase(&Fake::badFreeze, "freeze diagnostic identity");
    faultCase(&Fake::freezeTimeout, "freeze timeout quarantine");
    faultCase(&Fake::completionTimeout, "completion timeout quarantine");
    faultCase(&Fake::fault, "FPGA fault quarantine");
    faultCase(&Fake::wrongJobs, "jobs completion identity");
    faultCase(&Fake::failDma, "DMA failure keeps lease");
    faultCase(&Fake::changedEpoch, "epoch after DMA");
    faultCase(&Fake::changedTag, "sequence after DMA");
    faultCase(&Fake::ignoredMode, "mode readback before hold");
    for (auto field : {&Fake::pending, &Fake::flushing, &Fake::invalidBanks}) {
        Fake io; io.unpublished = true; io.*field = true;
        expect(execute(io) == -1 && io.releases == 0 && io.restores == 0,
               "unpublished with drain/flush/config fault cannot release");
    }
    Fake release; release.releaseTimeout = true;
    expect(execute(release) == -1 && release.restores == 0, "release acknowledgement before restore");
    for (int n = 1; n <= healthy.reads; ++n) {
        Fake io; io.failRead = n;
        expect(execute(io) == -1, "each MMIO read failure quarantines");
    }
    for (int n = 1; n <= healthy.writes; ++n) {
        Fake io; io.failWrite = n;
        expect(execute(io) == -1, "each MMIO write failure quarantines");
    }
    Cursor raw, display;
    raw.reset(10); display.reset(10); raw.commit(100); display.commit(102);
    expect(raw.tag == 100 && display.tag == 102 && raw.newer(101) && !display.newer(101),
           "RAW analytics and display sequences are independent");
    raw.reset(11); display.reset(11);
    expect(!raw.delivered && !display.delivered && raw.newer(1) && display.newer(1), "generation reset");
    raw.commit(0xffffffffu);
    expect(raw.newer(1) && !raw.newer(0xfffffffeu), "sequence wrap");
    for (int c = 0; c < 6; ++c) {
        expect(eligible(true, c, -1, 0, false) && !eligible(false, c, -1, 0, false) &&
               !eligible(true, c, c, 0, false) && !eligible(true, c, -1, 1 << c, false) &&
               !eligible(true, c, -1, 0, true), "all-six grid on; single/stereo/HDMI RAW fallback");
    }
    expect(Geometry{}.valid(RawBytes) && !Geometry{}.valid(Bytes) &&
           Geometry{320, 240}.valid(Bytes) && !Geometry{320, 240}.raw(), "geometry separation");
    // Exercise real copy routine and reusable layout with a reserved-slot canary.
    std::vector<uint8_t> rx(sixdma::Allocation, 0xa7), rawOwned(RawBytes), thumbOwned(Bytes);
    std::vector<uint8_t> original(RawBytes);
    for (size_t n = 0; n < original.size(); ++n) original[n] = uint8_t((n * 37) ^ (n >> 8));
    for (int c = 0; c < 6; ++c) {
        std::memcpy(rx.data() + sixdma::RawSlot, original.data(), RawBytes);
        tdm::copyCameraPixels(rawOwned.data(), rx.data() + sixdma::RawSlot, RawBytes);
        std::memset(rx.data() + sixdma::Metadata, c, 16);
        std::memset(rx.data() + sixdma::RawSlot, 0x5a, Bytes);
        tdm::copyCameraPixels(thumbOwned.data(), rx.data() + sixdma::RawSlot, Bytes);
        expect(rawOwned == original && std::all_of(thumbOwned.begin(), thumbOwned.end(),
               [](uint8_t v) { return v == 0x5a; }), "RAW bytes owned before shared scratch reuse");
    }
    expect(std::all_of(rx.begin() + sixdma::SharedInput,
           rx.begin() + sixdma::SharedInput + sixdma::SharedInputBytes,
           [](uint8_t v) { return v == 0xa7; }), "RKNN shared input canary survives all six scratch copies");
    expect(sixdma::scratchRange(0, RawBytes + 16) && sixdma::scratchRange(sixdma::Metadata, 4096) &&
           !sixdma::scratchRange(sixdma::SharedInput, 16) &&
           !sixdma::scratchRange(sixdma::SharedInput - 16, 32) &&
           !sixdma::scratchRange(0xffffffffu, 16), "all viewer DMA ranges below reserved input");
    std::fprintf(stderr, "SIX_THUMBNAIL_SELFTEST_%s cases=%d failures=%d\n", failures ? "FAIL" : "PASS", cases, failures);
    return failures ? 2 : 0;
}
} // namespace thumbnail
#ifdef THUMBNAIL_STANDALONE_SELFTEST
int main() { return thumbnail::runSelfTest(); }
#endif
