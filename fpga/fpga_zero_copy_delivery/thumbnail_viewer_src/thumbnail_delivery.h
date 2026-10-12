#pragma once
#include <cstddef>
#include <cstdint>

// Candidate MMIO contract. Keep hardware-dependent constants in this file.
// Transport MUST hold the existing PangoDev DMA mutex for the entire call.
// readPixels uses the deployed PCIe reader's native burst-slot gather, just
// like RAW cameraRead; output is logical RGB565, not a physical DDR dump.
namespace thumbnail {
constexpr uint32_t Base = 0x40020000, Signature = 0x444c5632;
constexpr uint32_t SignatureReg = 0x00, Status = 0x10, Command = 0x20;
constexpr uint32_t Source = 0x30, Destination = 0x40, Epoch = 0x50;
constexpr uint32_t OutputBytes = 0x60, InputBytes = 0x80, Jobs = 0x90;
constexpr uint32_t Caps = 0xa0, Mode = 0xb0;
constexpr uint32_t RgbDestination = 0x0a000000, ThumbDestination = 0x0a200000;
constexpr uint32_t RawBytes = 640 * 480 * 2, RgbBytes = 640 * 640 * 3;
constexpr uint32_t Bytes = 320 * 240 * 2, ErrorMask = 0x70;
struct Geometry {
    int width = 640, height = 480;
    size_t bytes() const { return size_t(width) * size_t(height) * 2; }
    bool raw() const { return width == 640 && height == 480; }
    bool valid(size_t count) const {
        return (raw() || (width == 320 && height == 240)) && count == bytes();
    }
};
inline bool eligible(bool enabled, int camera, int visionCamera, int stereoMask, bool hdmi) {
    return enabled && camera == 4 && visionCamera != 4 && !(stereoMask & (1 << 4)) && !hdmi;
}

// Any failed IO, timeout, changed lease or malformed completion is uncertain.
// quarantine() must stop this owner without closing/reopening/releasing hardware.
// There is deliberately no destructor, exception cleanup or automatic release.
template<class Transport> class Reader {
    Transport& io;
    uint32_t get(uint32_t reg) {
        uint32_t v = 0;
        if (!io.read(reg, v)) io.quarantine("thumbnail MMIO read failed");
        return v;
    }
    void check(bool ok, const char* reason) { if (!ok) io.quarantine(reason); }
    void put(uint32_t reg, uint32_t v) {
        if (!io.write(reg, v)) io.quarantine("thumbnail MMIO write failed");
    }
    uint32_t status() {
        const uint32_t s = get(Status);
        check(!(s & ErrorMask), "thumbnail FPGA failed/config/quarantine");
        return s;
    }
    void wait(uint32_t mask, uint32_t value) {
        const int64_t start = io.nowMs();
        do {
            if ((status() & mask) == value) return;
            io.delay();
        } while (io.nowMs() - start < 2000);
        io.quarantine("thumbnail lease/completion deadline");
    }
    void identity(uint32_t epoch, uint32_t source) {
        check((status() & 7) == 3 && get(Epoch) == epoch && get(Source) == source &&
              get(Mode) == 1 && get(Destination) == ThumbDestination &&
              get(OutputBytes) == Bytes, "thumbnail lease identity changed");
    }
public:
    explicit Reader(Transport& transport) : io(transport) {}
    void read(void* destination, size_t capacity, uint32_t& tag) {
        check(destination && capacity == Bytes, "thumbnail destination size");
        check(get(SignatureReg) == Signature && (get(Caps) & 3) == 3,
              "thumbnail DLV2 signature/capabilities unsupported");
        check((status() & 7) == 0 && get(Mode) == 0 &&
              get(Destination) == RgbDestination && get(OutputBytes) == RgbBytes &&
              get(InputBytes) == RawBytes, "thumbnail requires idle default RGB mode");
        put(Mode, 1);
        check((status() & 7) == 0 && get(Mode) == 1 &&
              get(Destination) == ThumbDestination && get(OutputBytes) == Bytes,
              "thumbnail mode configuration mismatch");
        put(Command, 1);
        wait(7, 3);
        const uint32_t epoch = get(Epoch), source = get(Source), jobs = get(Jobs);
        check(source == 0x01800000 || source == 0x01a00000, "thumbnail unknown C5 source");
        check(io.readTag(source + RawBytes, tag) && tag != 0, "thumbnail source tag invalid");
        identity(epoch, source);
        put(Command, 3);
        wait(15, 11); // held, frozen, completed, !busy
        check(get(Jobs) == uint32_t(jobs + 1), "thumbnail job count mismatch");
        identity(epoch, source); // Byte count checked BEFORE DMA/copy.
        check(io.readPixels(ThumbDestination, Bytes, destination), "thumbnail DMA failed");
        identity(epoch, source);
        uint32_t finalTag = 0;
        check(io.readTag(source + RawBytes, finalTag) && finalTag == tag,
              "thumbnail frozen source tag changed");
        put(Command, 0); // Only a fully validated completed transfer may release.
        wait(7, 0);
        put(Mode, 0);
        check((status() & 7) == 0 && get(Mode) == 0 &&
              get(Destination) == RgbDestination && get(OutputBytes) == RgbBytes,
              "thumbnail default RGB restore failed");
    }
};
int runSelfTest();
} // namespace thumbnail
