#pragma once
#include <cstddef>
#include <cstdint>

namespace runtime_camera {
// Isolated descendant of motion_viewer/runtime_camera_geometry.h.
// Geometry only: wire mode 2 still requires future capability/ABI admission.
// Camera indices are zero based. This contract assigns no runtime registers.
constexpr int count = 6;
constexpr uint32_t bankBytes = 2u * 1024u * 1024u;
constexpr uint32_t commitBytes = 16;
enum class Mode { Default = 0, Hd720 = 1, FullVga = 2 };
constexpr bool supportsHd(int camera) { return camera == 0 || camera == 2 || camera == 3 || camera == 4; }
constexpr bool validCamera(int camera) { return camera >= 0 && camera < count; }
constexpr bool supportsMode(int camera, Mode mode) {
    return validCamera(camera) &&
        (mode == Mode::Default ||
         (mode == Mode::Hd720 && supportsHd(camera)) ||
         (mode == Mode::FullVga && (camera == 2 || camera == 3)));
}

// Explicit transport encoding; never infer sensor HD from a nonzero mode.
// On failure the caller's output is unchanged. Camera support is checked separately.
inline bool modeFromWire(uint32_t wire, Mode& mode) {
    switch (wire) {
    case 0: mode = Mode::Default; return true;
    case 1: mode = Mode::Hd720; return true;
    case 2: mode = Mode::FullVga; return true;
    default: return false;
    }
}
inline bool modeToWire(Mode mode, uint32_t& wire) {
    switch (mode) {
    case Mode::Default: wire = 0; return true;
    case Mode::Hd720: wire = 1; return true;
    case Mode::FullVga: wire = 2; return true;
    default: return false;
    }
}

struct Geometry {
    int camera = -1;
    Mode mode = Mode::Default;
    uint32_t width = 0, height = 0, stride = 0;
    uint32_t pixelBytes = 0, tagOffset = 0;
    uint32_t ping = 0, pong = 0;
    uint64_t generation = 0;
    uint32_t transferBytes() const { return pixelBytes + commitBytes; }
    uint32_t bank(int index) const { return index == 0 ? ping : pong; }
    uint32_t tagAddress(int index) const { return bank(index) + tagOffset; }
    bool valid() const {
        if (!supportsMode(camera, mode) || !generation) return false;
        const bool compressed = mode == Mode::Default && (camera == 2 || camera == 3);
        const uint32_t w = mode == Mode::Hd720 ? 1280 : compressed ? 320 : 640;
        const uint32_t h = mode == Mode::Hd720 ? 720 : compressed ? 240 : 480;
        const uint32_t base = 0x00800000u + uint32_t(camera) * 0x00400000u;
        return width == w && height == h && stride == w * 2 &&
            pixelBytes == stride * height && tagOffset == pixelBytes &&
            uint64_t(pixelBytes) + commitBytes <= bankBytes &&
            ping == base && pong == base + bankBytes;
    }
    bool acceptsPublication(uint64_t frameGeneration, size_t bytes) const {
        return valid() && frameGeneration == generation && bytes == pixelBytes;
    }
};

// A C3/C4 transfer larger than the compressed frame is only ever admitted against
// an exact uncompressed descriptor: HD/VGA mode, contract length, offset 0 and one
// of the two documented banks. The host wire-guard consults this for the target
// descriptor of an in-flight pair transaction as well as for the committed one,
// and its hardware-free regression exercises the same predicate.
inline bool admitsLargeTransfer(const Geometry& geometry, uint32_t address,
                               uint32_t totalLength, uint32_t offset) {
    return geometry.valid() && (geometry.camera == 2 || geometry.camera == 3) &&
        (geometry.mode == Mode::Hd720 || geometry.mode == Mode::FullVga) &&
        totalLength == geometry.transferBytes() && offset == 0 &&
        (address == geometry.ping || address == geometry.pong);
}

inline Geometry geometry(int camera, Mode mode = Mode::Default, uint64_t generation = 1) {
    Geometry g;
    if (!supportsMode(camera, mode) || !generation) return g;
    const bool compressed = mode == Mode::Default && (camera == 2 || camera == 3);
    g.camera = camera; g.mode = mode; g.generation = generation;
    g.width = mode == Mode::Hd720 ? 1280 : compressed ? 320 : 640;
    g.height = mode == Mode::Hd720 ? 720 : compressed ? 240 : 480;
    g.stride = g.width * 2; g.pixelBytes = g.stride * g.height; g.tagOffset = g.pixelBytes;
    g.ping = 0x00800000u + uint32_t(camera) * 0x00400000u; g.pong = g.ping + bankBytes;
    return g;
}
} // namespace runtime_camera
