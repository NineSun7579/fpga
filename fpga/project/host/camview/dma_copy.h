#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

// The coherent DMA mapping is expensive for narrow CPU loads on RK3568.
// Transfer four 128-bit vectors per iteration; retain exact pixel bytes.
inline void copyDmaPixels(void *destination, const void *source, size_t size) {
#if defined(__aarch64__)
    auto *dst = static_cast<uint8_t *>(destination);
    auto *src = static_cast<const uint8_t *>(source);
    while (size >= 64) {
        asm volatile(
            "ldp q0, q1, [%[src]]\n\t"
            "ldp q2, q3, [%[src], #32]\n\t"
            "stp q0, q1, [%[dst]]\n\t"
            "stp q2, q3, [%[dst], #32]\n\t"
            : : [src] "r" (src), [dst] "r" (dst)
            : "v0", "v1", "v2", "v3", "memory");
        src += 64; dst += 64;
        size -= 64;
    }
    if (size) std::memcpy(dst, src, size);
#else
    std::memcpy(destination, source, size);
#endif
}
