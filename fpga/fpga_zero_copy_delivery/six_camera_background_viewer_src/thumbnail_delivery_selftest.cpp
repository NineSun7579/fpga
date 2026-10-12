#include "thumbnail_delivery.h"
#include "six_dma_layout.h"
#include "camera_dma.h"
#include "endpoint_locks.h"
#include <condition_variable>
#include <thread>
#include <future>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include <algorithm>

namespace thumbnail {
namespace {
struct Stopped : std::runtime_error { using std::runtime_error::runtime_error; };
struct Fake {
    static bool defaultBatch;
    bool batching = defaultBatch;
    int snapshots = 0, failSnapshot = 0, mutateSnapshot = 0;
    uint32_t mutateReg = 0, mutateValue = 0;
    std::vector<uint32_t> snapshotStates;
    bool readSnapshot(void* output, size_t count) {
        if (!batching) throw std::logic_error("snapshot sent to old hardware");
        if (!output || count != SnapshotBytes) throw std::logic_error("snapshot size");
        ++snapshots;
        snapshotStates.push_back(state);
        if (snapshots == failSnapshot) return false;
        std::memset(output, 0, count);
        auto* words = static_cast<uint32_t*>(output);
        for (uint32_t reg = 0; reg <= Freeze; reg += 16) {
            if (reg == Command || reg == 0x70) continue;
            if (!read(reg, words[reg / 4])) return false;
        }
        if (snapshots == mutateSnapshot) words[mutateReg / 4] = mutateValue;
        return true;
    }
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
        case Caps: value = badCaps ? 3 : (RequiredCaps | (batching ? SnapshotCap : 0)); break;
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
bool Fake::defaultBatch = false;

// Exercise the actual Reader and production lock type with shared RX/TX.
struct ConcurrentTransport : Fake {
    sixdma::EndpointLocks<std::mutex> locks;
    std::vector<uint8_t> rx = std::vector<uint8_t>(sixdma::Allocation, 0xa7);
    std::vector<uint8_t> tx = std::vector<uint8_t>(sixdma::Allocation, 0xb8);
    std::mutex gateMutex;
    std::condition_variable gateCv;
    int reached = 0, proceed = 0;
    bool gates = true;
    bool read(uint32_t reg, uint32_t& value) {
        auto lock = locks.dma();
        uint32_t word = 0;
        if (!Fake::read(reg, word)) return false;
        std::memcpy(rx.data() + sixdma::Metadata, &word, 4);
        std::memcpy(&value, rx.data() + sixdma::Metadata, 4);
        return true;
    }
    bool readSnapshot(void* output, size_t count) {
        auto lock = locks.dma();
        if (!Fake::readSnapshot(rx.data() + sixdma::Metadata, count)) return false;
        std::memcpy(output, rx.data() + sixdma::Metadata, count);
        return true;
    }
    bool write(uint32_t reg, uint32_t value) {
        auto lock = locks.dma();
        std::memset(tx.data(), 0, 16);
        std::memcpy(tx.data(), &value, 4);
        uint32_t actual = 0;
        std::memcpy(&actual, tx.data(), 4);
        return Fake::write(reg, actual);
    }
    bool readTag(uint32_t address, uint32_t& value) {
        auto lock = locks.dma();
        uint32_t word = 0;
        if (!Fake::readTag(address, word)) return false;
        std::memcpy(rx.data() + sixdma::Metadata, &word, 4);
        std::memcpy(&value, rx.data() + sixdma::Metadata, 4);
        return true;
    }
    bool readPixels(uint32_t address, uint32_t count, void* output) {
        auto lock = locks.dma();
        if (!Fake::readPixels(address, count, rx.data() + sixdma::RawSlot)) return false;
        tdm::copyCameraPixels(output, rx.data() + sixdma::RawSlot, count);
        return true;
    }
    void delay() {
        if (!gates) { Fake::delay(); return; }
        std::unique_lock<std::mutex> gate(gateMutex);
        const int phase = ++reached;
        gateCv.notify_all();
        if (!gateCv.wait_for(gate, std::chrono::seconds(5), [&] { return proceed >= phase; }))
            throw std::runtime_error("RAW interleave blocked by thumbnail wait");
        // Hardware-driven publication/drain acknowledgement and completion.
        if (phase == 1) { unpublished = false; state = 3; }
        else if (phase == 2) state = 11;
        else throw std::logic_error("unexpected wait phase");
        clock += 1;
    }
    void waitPhase(int phase) {
        std::unique_lock<std::mutex> gate(gateMutex);
        if (!gateCv.wait_for(gate, std::chrono::seconds(5), [&] { return reached >= phase; }))
            throw std::runtime_error("Reader failed to reach wait phase");
    }
    void resume(int phase) {
        std::lock_guard<std::mutex> gate(gateMutex);
        proceed = phase;
        gateCv.notify_all();
    }
};

bool concurrencyCase(bool batch, bool corruptEpoch = false) {
    ConcurrentTransport io;
    io.batching = batch; io.unpublished = true; io.completionTimeout = true;
    io.changedEpoch = corruptEpoch;
    std::vector<uint8_t> thumb(Bytes + 32, 0xa5), raw(RawBytes + 32, 0xc6);
    uint32_t selected = 0;
    auto thumbnailWorker = std::async(std::launch::async, [&] {
        auto owner = io.locks.lease();
        return Reader<ConcurrentTransport>(io).read(0, 1, thumb.data() + 16, Bytes, selected);
    });
    bool ok = true;
    // Admission/conversion release DMA, never endpoint ownership. Include RAW
    // from the leased camera and the other five cameras, reusing both RX slots.
    for (int phase = 1; phase <= 2; ++phase) {
        io.waitPhase(phase);
        auto rawWorker = std::async(std::launch::async, [&] {
            bool valid = !io.locks.tryLease().owns_lock();
            for (int camera = 0; camera < 6; ++camera) {
                auto dma = io.locks.dma();
                std::vector<uint8_t> original(RawBytes);
                for (size_t n = 0; n < original.size(); ++n)
                    original[n] = uint8_t((n * 37) ^ (n >> 8) ^ camera);
                const uint32_t tag = 123 + camera;
                std::memcpy(io.rx.data(), original.data(), RawBytes);
                std::memcpy(io.rx.data() + RawBytes, &tag, 4);
                std::memset(io.rx.data() + sixdma::Metadata, 0xdf, SnapshotBytes);
                uint32_t actual = 0;
                std::memcpy(&actual, io.rx.data() + RawBytes, 4);
                tdm::copyCameraPixels(raw.data() + 16, io.rx.data(), RawBytes);
                valid &= actual == tag && std::equal(original.begin(), original.end(), raw.begin() + 16);
                valid &= io.state == (phase == 1 ? 1u : 7u) && io.camera == 0 && io.bank == 1;
            }
            return valid;
        });
        ok &= rawWorker.get();
        io.resume(phase);
    }
    bool stopped = false, completed = false;
    try { completed = thumbnailWorker.get(); }
    catch (const Stopped&) { stopped = true; }
    if (corruptEpoch) return ok && stopped && !completed && io.releases == 0 && io.restores == 0 && io.state == 11;
    ok &= completed && !stopped && selected == 123 && io.releases == 1 && io.restores == 1;
    ok &= std::all_of(thumb.begin(), thumb.begin() + 16, [](uint8_t v) { return v == 0xa5; }) &&
          std::all_of(thumb.end() - 16, thumb.end(), [](uint8_t v) { return v == 0xa5; }) &&
          std::all_of(raw.begin(), raw.begin() + 16, [](uint8_t v) { return v == 0xc6; }) &&
          std::all_of(raw.end() - 16, raw.end(), [](uint8_t v) { return v == 0xc6; });
    ok &= std::all_of(thumb.begin() + 16, thumb.end() - 16, [](uint8_t v) { return v == 0x5a; });
    ok &= std::all_of(io.rx.begin() + sixdma::SharedInput, io.rx.end(), [](uint8_t v) { return v == 0xa7; });
    ok &= std::all_of(io.tx.begin() + 16, io.tx.end(), [](uint8_t v) { return v == 0xb8; });
    // Direct-ioctl borrowed callbacks use the SAME lease -> DMA locks.
    // A different thread proves both unavailable, without timing assumptions.
    {
        auto borrow = io.locks.borrow();
        auto contender = std::async(std::launch::async, [&] {
            auto lease = io.locks.tryLease();
            auto dma = io.locks.tryDma();
            return !lease.owns_lock() && !dma.owns_lock();
        });
        ok &= contender.get();
        std::memset(io.rx.data() + sixdma::SharedInput, 0x39, sixdma::SharedInputBytes);
    }
    // Subsequent thumbnail restores normally without changing detection bytes.
    io.gates = false; io.completionTimeout = false; io.copies = 0;
    {
        auto owner = io.locks.lease();
        ok &= Reader<ConcurrentTransport>(io).read(5, 0, thumb.data() + 16, Bytes, selected);
    }
    ok &= std::all_of(io.rx.begin() + sixdma::SharedInput,
        io.rx.begin() + sixdma::SharedInput + sixdma::SharedInputBytes, [](uint8_t v) { return v == 0x39; });
    auto borrower = std::async(std::launch::async, [&] {
        auto borrow = io.locks.borrow();
        return io.state == 0 && io.camera == 4 && io.mode == 0;
    });
    return ok && borrower.get();
}
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
    for (bool batchMode : {false, true}) {
    Fake::defaultBatch = batchMode;
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
    if (batchMode) {
        expect(healthy.snapshots > 0 && healthy.copies == 1, "caps bit3 enables snapshot transport");
        std::fprintf(stderr, "BATCH_HEALTHY snapshots=%d scalar_or_model_reads=%d states=", healthy.snapshots, healthy.reads);
        for (auto state : healthy.snapshotStates) std::fprintf(stderr, "%u,", state);
        std::fprintf(stderr, "\n");
        for (int n = 1; n <= healthy.snapshots; ++n) {
            Fake io; io.failSnapshot = n;
            expect(execute(io) == -1, "each snapshot failure quarantines");
        }
        // Corrupt every field used in idle, selector, held, completed, post-copy,
        // and restore validation. Fresh snapshots must expose each mutation.
        struct Mutation { int snapshot; uint32_t reg, value; int maxCopies; };
        const Mutation mutations[] = {
            {1, Supported, 0x1f, 0}, {2, InputBytes, RawBytes+16, 0},
            {2, Status, 0x40, 0}, {2, Mode, 1, 0}, {2, Camera, 0, 0},
            {2, OutputBank, 1, 0}, {2, Destination, RgbDestination+16, 0},
            {2, OutputBytes, RgbBytes+16, 0}, {2, Freeze, 4, 0},
            {3, Camera, 1, 0}, {3, OutputBank, 1, 0}, {3, Mode, 0, 0},
            {3, Destination, Destinations[0][0]+16, 0}, {3, OutputBytes, Bytes+16, 0},
            {3, Bank0, SourceBanks[0][0]+16, 0}, {3, Bank1, SourceBanks[0][1]+16, 0},
            {4, Freeze, 4, 0}, {5, Source, 0xdead0000, 0},
            {6, Epoch, 99, 0}, {6, SourceSequence, 999, 0}, {6, Freeze, 0, 0},
            {7, Bank0, 0xdead0000, 0}, {8, Jobs, 99, 0},
            {9, Epoch, 99, 0}, {9, SourceSequence, 999, 0}, {9, Freeze, 0, 0},
            {10, OutputBytes, Bytes+16, 0},
            {11, Epoch, 99, 1}, {11, SourceSequence, 999, 1}, {11, Freeze, 0, 1},
            {12, Bank1, 0xdead0000, 1}, {13, Freeze, 4, 1},
            {14, Mode, 1, 1}, {14, Camera, 0, 1}, {14, OutputBank, 1, 1},
            {14, Destination, RgbDestination+16, 1}, {14, OutputBytes, RgbBytes+16, 1}
        };
        for (const auto& mutation : mutations) {
            Fake io; io.mutateSnapshot = mutation.snapshot;
            io.mutateReg = mutation.reg; io.mutateValue = mutation.value;
            int result = execute(io);
            if (result != -1) std::fprintf(stderr, "MUTATION_MISSED snapshot=%d reg=%x\n", mutation.snapshot, mutation.reg);
            expect(result == -1 && io.copies <= mutation.maxCopies, "stage snapshot mutation quarantines before unsafe copy");
        }
    } else expect(healthy.snapshots == 0, "caps7 preserves scalar fallback");
    } // both scalar fallback and batching run the entire existing fault suite
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
    for (bool batch : {false, true}) {
        try { expect(concurrencyCase(batch), "RAW admission/conversion interleave, lease exclusion, scratch and RKNN canaries"); }
        catch (const std::exception& e) { expect(false, e.what()); }
        try { expect(concurrencyCase(batch, true), "interleaved RAW cannot hide post-payload epoch fault or release uncertain lease"); }
        catch (const std::exception& e) { expect(false, e.what()); }
    }
    std::fprintf(stderr, "SIX_THUMBNAIL_SELFTEST_%s cases=%d failures=%d\n", failures ? "FAIL" : "PASS", cases, failures);
    return failures ? 2 : 0;
}
} // namespace thumbnail
#ifdef THUMBNAIL_STANDALONE_SELFTEST
int main() { return thumbnail::runSelfTest(); }
#endif
