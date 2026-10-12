#pragma once
#include <cstdint>
#include <cstring>
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

namespace tdm {
// Input is owned, native-endian RGB565 RAM, never a borrowed DMA mapping.
// Bit replication deliberately matches the previous inference input exactly.
inline void rgb565ToRgb888Line(const uint8_t* src, int pixels, uint8_t* dst) {
#if defined(__aarch64__)
    while (pixels >= 8) {
        const uint16x8_t v = vreinterpretq_u16_u8(vld1q_u8(src));
        const uint16x8_t r = vshrq_n_u16(v, 11);
        const uint16x8_t g = vandq_u16(vshrq_n_u16(v, 5), vdupq_n_u16(63));
        const uint16x8_t b = vandq_u16(v, vdupq_n_u16(31));
        uint8x8x3_t rgb;
        rgb.val[0] = vmovn_u16(vorrq_u16(vshlq_n_u16(r, 3), vshrq_n_u16(r, 2)));
        rgb.val[1] = vmovn_u16(vorrq_u16(vshlq_n_u16(g, 2), vshrq_n_u16(g, 4)));
        rgb.val[2] = vmovn_u16(vorrq_u16(vshlq_n_u16(b, 3), vshrq_n_u16(b, 2)));
        vst3_u8(dst, rgb);
        src += 16; dst += 24; pixels -= 8;
    }
#endif
    for (int i = 0; i < pixels; ++i) {
        uint16_t v;
        std::memcpy(&v, src + 2 * i, sizeof(v));
        const uint8_t r = (v >> 11) & 31, g = (v >> 5) & 63, b = v & 31;
        dst[3 * i] = (r << 3) | (r >> 2);
        dst[3 * i + 1] = (g << 2) | (g >> 4);
        dst[3 * i + 2] = (b << 3) | (b >> 2);
    }
}
}
