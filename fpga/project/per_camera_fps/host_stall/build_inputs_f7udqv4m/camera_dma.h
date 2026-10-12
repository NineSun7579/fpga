#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace tdm {
constexpr uint32_t cameraFrameBytes = 640u * 480u * 2u;
constexpr uint32_t cameraSlotStride = 0x97000u;
constexpr uint32_t cameraScratchOffset = 0x3ff000u;
constexpr uint32_t cameraAllocationBytes = 4u * 1024u * 1024u;
constexpr uint32_t cameraSlotOffset(int camera) { return uint32_t(camera) * cameraSlotStride; }
static_assert(cameraFrameBytes + 16 <= cameraSlotStride, "Frame and commit tag must fit in one slot");
static_assert(cameraSlotOffset(5) + cameraFrameBytes + 16 <= cameraScratchOffset,
              "Six frame slots must not overlap the shared metadata scratch area");
static_assert(cameraScratchOffset + 16 <= cameraAllocationBytes, "Scratch must fit RX allocation");

inline bool newerCameraTag(uint32_t a, uint32_t b) {
    return a != b && uint32_t(a - b) < 0x80000000u;
}
inline int newestCameraBank(uint32_t a, uint32_t b, bool delivered, uint32_t last) {
    const int bank = newerCameraTag(a, b) ? 0 : 1;
    const uint32_t selected = bank == 0 ? a : b;
    if ((!delivered && a == 0 && b == 0) || (delivered && !newerCameraTag(selected, last))) return -1;
    return bank;
}

// Ported from the running camview's dma_copy.h. Preserve exact bytes including
// tails; four 128-bit loads reduce narrow-load overhead on coherent mappings.
inline void copyCameraPixels(void* destination, const void* source, size_t size) {
#if defined(__aarch64__)
    auto* dst = static_cast<uint8_t*>(destination);
    const auto* src = static_cast<const uint8_t*>(source);
    while (size >= 64) {
        asm volatile(
            "ldp q0, q1, [%[src]]\n\t"
            "ldp q2, q3, [%[src], #32]\n\t"
            "stp q0, q1, [%[dst]]\n\t"
            "stp q2, q3, [%[dst], #32]\n\t"
            : : [src] "r" (src), [dst] "r" (dst)
            : "v0", "v1", "v2", "v3", "memory");
        src += 64; dst += 64; size -= 64;
    }
    if (size) std::memcpy(dst, src, size);
#else
    std::memcpy(destination, source, size);
#endif
}
int runCameraDmaSelfTest();
} // namespace tdm
