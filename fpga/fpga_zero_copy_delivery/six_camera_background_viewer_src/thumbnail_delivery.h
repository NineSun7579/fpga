#pragma once
#include <cstddef>
#include <cstdint>
#include <chrono>

// Contract from integrated_six/source/delivery/delivery_regs.v.
// Hardware transport and payload parity still require board validation.
namespace thumbnail {
// Optional, transaction-local instrumentation. A null pointer never reads a clock.
struct StageStats {
    enum Stage { Admission, Conversion, Validation, Payload, Release, Restore, StageCount };
    enum Io { Snapshot, Scalar, Tag, Write, Pixel, Other, IoCount };
    struct Timing {
        uint64_t count = 0, sumNs = 0, maxNs = 0;
        void add(uint64_t ns) { ++count; sumNs += ns; if (ns > maxNs) maxNs = ns; }
    };
    Timing stages[StageCount]{}, calls[IoCount]{}, wait, hold;
    uint64_t polls[StageCount]{}, caps15 = 0, batch = 0, scalar = 0;
    static uint64_t nowNs() {
        return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
    }
};
class StageTimer {
    StageStats* stats;
    StageStats::Stage phase;
    uint64_t start = 0;
public:
    StageTimer(StageStats* s, StageStats::Stage p) : stats(s), phase(p) {
        if (stats) start = StageStats::nowNs();
    }
    void next(StageStats::Stage p) {
        if (stats) {
            const auto now = StageStats::nowNs();
            stats->stages[phase].add(now - start); start = now;
        }
        phase = p;
    }
    void poll() { if (stats) ++stats->polls[phase]; }
    ~StageTimer() { if (stats) stats->stages[phase].add(StageStats::nowNs() - start); }
};
constexpr uint32_t Base = 0x40020000, Signature = 0x444c5632;
constexpr uint32_t SignatureReg = 0x00, Status = 0x10, Command = 0x20;
constexpr uint32_t Source = 0x30, Destination = 0x40, Epoch = 0x50;
constexpr uint32_t OutputBytes = 0x60, InputBytes = 0x80, Jobs = 0x90;
constexpr uint32_t Caps = 0xa0, Mode = 0xb0, Camera = 0xc0, OutputBank = 0xd0;
constexpr uint32_t SourceSequence = 0xe0, Supported = 0xf0;
constexpr uint32_t Bank0 = 0x100, Bank1 = 0x110, Freeze = 0x120;
constexpr uint32_t SnapshotCap = 8, SnapshotBytes = 304;
constexpr uint32_t RequiredCaps = 7; // existing RGB/thumbnail + bit2 (value 4)
constexpr uint32_t SupportedMask = 0x3f, ErrorMask = 0x70;
constexpr uint32_t RgbDestination = 0x0a000000;
constexpr uint32_t RawBytes = 640 * 480 * 2, RgbBytes = 640 * 640 * 3;
constexpr uint32_t Bytes = 320 * 240 * 2;
constexpr uint32_t SourceBanks[6][2] = {
    {0x00800000, 0x00a00000}, {0x00c00000, 0x00e00000},
    {0x01000000, 0x01200000}, {0x01400000, 0x01600000},
    {0x01800000, 0x01a00000}, {0x01c00000, 0x01e00000}};
constexpr uint32_t Destinations[6][2] = {
    {0x0a280000, 0x0a2c0000}, {0x0a300000, 0x0a340000},
    {0x0a380000, 0x0a3c0000}, {0x0a400000, 0x0a440000},
    {0x0a200000, 0x0a240000}, {0x0a480000, 0x0a4c0000}};
// +120: bit0 drain pending, bit1 unpublished, bit2 frozen, bit3 flush,
// bit4 invalid RAW bank configuration. This is not the capture_hold bitmap.
constexpr bool frozen(uint32_t value) {
    return value == 4;
}
struct Geometry {
    int width = 640, height = 480;
    size_t bytes() const { return size_t(width) * size_t(height) * 2; }
    bool raw() const { return width == 640 && height == 480; }
    bool valid(size_t count) const {
        return (raw() || (width == 320 && height == 240)) && count == bytes();
    }
};
inline bool eligible(bool enabled, int camera, int fullCamera, int stereoMask, bool hdmi) {
    return enabled && camera >= 0 && camera < 6 && fullCamera != camera &&
           !(stereoMask & (1 << camera)) && !hdmi;
}
// Separate RAW and display cursors; selection/generation changes invalidate
// both, but neither transaction overwrites the other's tag/history.
struct Cursor {
    bool delivered = false;
    uint32_t tag = 0;
    int generation = -1;
    void reset(int value) { delivered = false; tag = 0; generation = value; }
    bool newer(uint32_t value) const {
        return !delivered || (value != tag && uint32_t(value - tag) < 0x80000000u);
    }
    void commit(uint32_t value) { delivered = true; tag = value; }
};

// One complete serialized transaction, owned-copy output only. Transport owns
// the existing fd/mutex; errors quarantine without destructor cleanup/release.
template<class Transport> class Reader {
    Transport& io;
    StageStats* stats;
    StageTimer* timer = nullptr;
    bool batch = false, snapshotValid = false;
    uint32_t snapshot[SnapshotBytes / sizeof(uint32_t)]{};
    void invalidate() { snapshotValid = false; }
    void refresh() {
        if (!batch) return;
        invalidate();
        if (!io.readSnapshot(snapshot, SnapshotBytes))
            io.quarantine("six thumbnail snapshot DMA failed");
        snapshotValid = true;
    }
    uint32_t get(uint32_t reg) {
        if (batch) {
            if (!snapshotValid) refresh();
            check(reg <= Freeze && !(reg & 15), "six thumbnail snapshot offset");
            return snapshot[reg / sizeof(uint32_t)];
        }
        uint32_t value = 0;
        if (!io.read(reg, value)) io.quarantine("six thumbnail MMIO read failed");
        return value;
    }
    void check(bool ok, const char* reason) { if (!ok) io.quarantine(reason); }
    void put(uint32_t reg, uint32_t value) {
        invalidate();
        if (!io.write(reg, value)) io.quarantine("six thumbnail MMIO write failed");
    }
    uint32_t status() {
        if (timer) timer->poll();
        refresh();
        const auto value = get(Status);
        check(!(value & ErrorMask), "six thumbnail error/config/quarantine");
        return value;
    }
    void wait(uint32_t mask, uint32_t value) {
        const auto start = io.nowMs();
        do {
            if ((status() & mask) == value) return;
            io.delay();
        } while (io.nowMs() - start < 2000);
        io.quarantine("six thumbnail lease/completion deadline");
    }
    void configuration(int camera, int bank) {
        refresh();
        check(get(Camera) == uint32_t(camera) && get(OutputBank) == uint32_t(bank) &&
              get(Mode) == 1 && get(Destination) == Destinations[camera][bank] &&
              get(OutputBytes) == Bytes && get(Bank0) == SourceBanks[camera][0] &&
              get(Bank1) == SourceBanks[camera][1], "six thumbnail selector/size readback");
    }
    void identity(int camera, int bank, uint32_t epoch, uint32_t source, uint32_t tag) {
        check((status() & 7) == 3 && get(Epoch) == epoch && get(Source) == source &&
              get(SourceSequence) == tag && frozen(get(Freeze)), "six thumbnail lease changed");
        configuration(camera, bank);
    }
    void restore() {
        if (timer) timer->next(StageStats::Release);
        put(Command, 0);
        wait(7, 0);
        check(get(Freeze) == 0, "six thumbnail release freeze acknowledgement");
        if (timer) timer->next(StageStats::Restore);
        put(Mode, 0); put(Camera, 4); put(OutputBank, 0);
        check((status() & 7) == 0 && get(Mode) == 0 && get(Camera) == 4 &&
              get(OutputBank) == 0 && get(Destination) == RgbDestination &&
              get(OutputBytes) == RgbBytes, "six thumbnail default RGB restoration");
    }
public:
    explicit Reader(Transport& transport, StageStats* instrumentation = nullptr)
        : io(transport), stats(instrumentation) {}
    // RTL freezes only published frames. At the admission deadline, an idle,
    // unsubmitted hold with only the unpublished diagnostic can safely release.
    // A published sequence of zero is valid after uint32_t wrap.
    bool read(int camera, int bank, void* destination, size_t capacity, uint32_t& tag) {
        StageTimer measurement(stats, StageStats::Admission);
        timer = stats ? &measurement : nullptr;
        check(camera >= 0 && camera < 6 && bank >= 0 && bank < 2 && destination && capacity == Bytes,
              "six thumbnail argument/size");
        batch = false;
        invalidate();
        const auto signature = get(SignatureReg), caps = get(Caps);
        batch = (caps & SnapshotCap) != 0;
        if (stats) { stats->caps15 += caps == 15; ++(batch ? stats->batch : stats->scalar); }
        check(signature == Signature && (caps & RequiredCaps) == RequiredCaps &&
              get(Supported) == SupportedMask, "six thumbnail capability/bitmap unsupported");
        check((status() & 7) == 0 && get(Freeze) == 0 && get(Mode) == 0 &&
              get(Camera) == 4 && get(OutputBank) == 0 && get(Destination) == RgbDestination &&
              get(OutputBytes) == RgbBytes && get(InputBytes) == RawBytes, "six thumbnail idle/default owner required");
        put(Camera, uint32_t(camera)); put(OutputBank, uint32_t(bank)); put(Mode, 1);
        configuration(camera, bank);
        check((status() & 7) == 0 && get(Freeze) == 0, "six thumbnail selector write active");
        put(Command, 1);
        const auto start = io.nowMs();
        while ((status() & 7) != 3) {
            if (io.nowMs() - start >= 2000) {
                if (get(Freeze) == 2 && (status() & 15) == 1) {
                    restore();
                    return false;
                }
                io.quarantine("six thumbnail lease/completion deadline");
            }
            io.delay();
        }
        const auto epoch = get(Epoch), source = get(Source), jobs = get(Jobs);
        if (timer) timer->next(StageStats::Validation);
        tag = get(SourceSequence);
        check(source == SourceBanks[camera][0] || source == SourceBanks[camera][1], "six thumbnail source camera mismatch");
        identity(camera, bank, epoch, source, tag);
        uint32_t sourceTag = 0;
        check(io.readTag(source + RawBytes, sourceTag) && sourceTag == tag, "six thumbnail source tag mismatch");
        invalidate(); // RAW tag DMA has reused metadata scratch.
        if (timer) timer->next(StageStats::Conversion);
        put(Command, 3); wait(15, 11);
        if (timer) timer->next(StageStats::Validation);
        check(get(Jobs) == uint32_t(jobs + 1), "six thumbnail jobs mismatch");
        identity(camera, bank, epoch, source, tag); // validate byte count BEFORE copy
        if (timer) timer->next(StageStats::Payload);
        check(io.readPixels(Destinations[camera][bank], Bytes, destination), "six thumbnail pixel DMA failed");
        if (timer) timer->next(StageStats::Validation);
        invalidate(); // Never carry a snapshot over payload DMA.
        identity(camera, bank, epoch, source, tag);
        check(io.readTag(source + RawBytes, sourceTag) && sourceTag == tag, "six thumbnail frozen tag changed");
        restore();
        return true;
    }
};
int runSelfTest();
} // namespace thumbnail
